import os
import re

from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from . import services
from .models import (
    ACTIVE_STAGES, RECOMMENDATIONS, STAGES, Candidate, FeedbackRating, Interview, InterviewFeedback, JobOpening,
    OpeningCriterion, StageLog,
)
from .permissions import is_hr

RESUME_EXTENSIONS = {'.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png'}
RESUME_MAX_BYTES = 5 * 1024 * 1024


def full_name(user):
    if user is None:
        return None
    return user.get_full_name().strip() or user.username


# ---------------------------------------------------------------- openings

class CriterionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = OpeningCriterion
        fields = ['id', 'name', 'description', 'weight', 'order']


class JobOpeningSerializer(serializers.ModelSerializer):
    criteria = CriterionSerializer(many=True, required=False)
    hiring_manager_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    # Counts come from annotations on the viewset queryset.
    candidate_count = serializers.IntegerField(read_only=True)
    active_count = serializers.IntegerField(read_only=True)
    joined_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = JobOpening
        fields = [
            'id', 'number', 'title', 'department', 'positions', 'location', 'experience_min', 'experience_max',
            'salary_min', 'salary_max', 'description', 'requirements', 'status', 'opened_date', 'target_date',
            'closed_date', 'hiring_manager', 'hiring_manager_name', 'created_by_name', 'criteria',
            'candidate_count', 'active_count', 'joined_count',
        ]
        read_only_fields = ['number', 'closed_date']

    def get_hiring_manager_name(self, obj):
        return full_name(obj.hiring_manager)

    def get_created_by_name(self, obj):
        return full_name(obj.created_by)

    def validate(self, attrs):
        def pick(name):
            return attrs[name] if name in attrs else getattr(self.instance, name, None)
        for low, high, label in (('experience_min', 'experience_max', 'experience'),
                                 ('salary_min', 'salary_max', 'salary')):
            if pick(low) is not None and pick(high) is not None and pick(low) > pick(high):
                raise serializers.ValidationError({high: f'Maximum {label} is below the minimum.'})
        opened, target = pick('opened_date'), pick('target_date')
        if opened and target and target < opened:
            raise serializers.ValidationError({'target_date': 'The target date is before the opening date.'})
        return attrs

    def _save_criteria(self, opening, rows):
        existing = {c.id: c for c in opening.criteria.all()}
        keep = set()
        for order, row in enumerate(rows):
            row = {**row, 'order': order}
            criterion = existing.get(row.pop('id', None))
            if criterion:
                for key, value in row.items():
                    setattr(criterion, key, value)
                criterion.save()
            else:
                criterion = OpeningCriterion.objects.create(opening=opening, **row)
            keep.add(criterion.id)
        for cid, criterion in existing.items():
            if cid in keep:
                continue
            if criterion.ratings.exists():
                raise serializers.ValidationError(
                    {'criteria': f'"{criterion.name}" already has interview ratings and cannot be removed.'})
            criterion.delete()

    @transaction.atomic
    def create(self, validated_data):
        rows = validated_data.pop('criteria', [])
        opening = JobOpening.objects.create(created_by=self.context['request'].user, **validated_data)
        self._save_criteria(opening, rows)
        return opening

    @transaction.atomic
    def update(self, instance, validated_data):
        rows = validated_data.pop('criteria', None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if rows is not None:
            self._save_criteria(instance, rows)
        return instance


# ---------------------------------------------------------------- candidates

class StageLogSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StageLog
        fields = ['id', 'from_stage', 'to_stage', 'note', 'changed_by_name', 'changed_at']

    def get_changed_by_name(self, obj):
        return full_name(obj.changed_by)


def digits(value):
    return re.sub(r'\D', '', value or '')


class CandidateSerializer(serializers.ModelSerializer):
    opening_number = serializers.CharField(source='opening.number', read_only=True)
    opening_title = serializers.CharField(source='opening.title', read_only=True)
    resume = serializers.FileField(write_only=True, required=False, allow_null=True)
    clear_resume = serializers.BooleanField(write_only=True, required=False, default=False)
    has_resume = serializers.SerializerMethodField()
    resume_url = serializers.SerializerMethodField()
    resume_name = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()
    interview_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    stage_logs = StageLogSerializer(many=True, read_only=True)

    class Meta:
        model = Candidate
        fields = [
            'id', 'opening', 'opening_number', 'opening_title', 'name', 'mobile', 'email', 'location',
            'current_company', 'current_designation', 'experience_years', 'current_salary', 'expected_salary',
            'notice_period_days', 'source', 'source_detail', 'resume', 'clear_resume', 'has_resume',
            'resume_url', 'resume_name', 'notes', 'stage', 'rejection_reason', 'offered_salary', 'offer_date',
            'joining_date', 'score', 'interview_count', 'created_by_name', 'created_at', 'stage_logs',
        ]
        # The stage only changes through the move action, which writes the log.
        read_only_fields = ['stage', 'rejection_reason']

    def get_has_resume(self, obj):
        return bool(obj.resume)

    def get_resume_url(self, obj):
        return f'/api/recruitment/candidates/{obj.pk}/resume/' if obj.resume else None

    def get_resume_name(self, obj):
        return os.path.basename(obj.resume.name) if obj.resume else None

    def get_score(self, obj):
        return services.candidate_score(obj)

    def get_interview_count(self, obj):
        return len(obj.interviews.all())

    def get_created_by_name(self, obj):
        return full_name(obj.created_by)

    def validate_resume(self, value):
        if value is None:
            return value
        if os.path.splitext(value.name)[1].lower() not in RESUME_EXTENSIONS:
            raise serializers.ValidationError('Upload a PDF, Word document or image (jpg / png).')
        if value.size > RESUME_MAX_BYTES:
            raise serializers.ValidationError('The resume is larger than 5 MB.')
        return value

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Enter the candidate name.')
        return value

    def validate(self, attrs):
        opening = attrs.get('opening') or getattr(self.instance, 'opening', None)
        mobile = attrs.get('mobile', getattr(self.instance, 'mobile', ''))
        if opening and digits(mobile):
            clash = Candidate.objects.filter(opening=opening)
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            for other in clash.exclude(mobile='').only('name', 'mobile'):
                if digits(other.mobile)[-10:] == digits(mobile)[-10:]:
                    raise serializers.ValidationError(
                        {'mobile': f'{other.name} is already on this opening with this mobile number.'})
        if self.instance and 'opening' in attrs and attrs['opening'].pk != self.instance.opening_id \
                and self.instance.interviews.exists():
            raise serializers.ValidationError(
                {'opening': 'This candidate has interviews scored on the old opening; it cannot be changed.'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('clear_resume', None)
        candidate = Candidate.objects.create(created_by=self.context['request'].user, **validated_data)
        StageLog.objects.create(candidate=candidate, to_stage='applied', note='Added',
                                changed_by=self.context['request'].user)
        return candidate

    def update(self, instance, validated_data):
        clear = validated_data.pop('clear_resume', False)
        if clear and 'resume' not in validated_data:
            validated_data['resume'] = None
        return super().update(instance, validated_data)


class MoveSerializer(serializers.Serializer):
    stage = serializers.ChoiceField(choices=STAGES)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500, default='')
    rejection_reason = serializers.CharField(required=False, allow_blank=True, max_length=300, default='')
    joining_date = serializers.DateField(required=False, allow_null=True)


# ---------------------------------------------------------------- interviews

class RatingReadSerializer(serializers.ModelSerializer):
    criterion_name = serializers.CharField(source='criterion.name', read_only=True)
    weight = serializers.IntegerField(source='criterion.weight', read_only=True)

    class Meta:
        model = FeedbackRating
        fields = ['criterion', 'criterion_name', 'weight', 'rating', 'comment']


class FeedbackReadSerializer(serializers.ModelSerializer):
    interviewer_name = serializers.SerializerMethodField()
    is_submitted = serializers.BooleanField(read_only=True)
    score = serializers.SerializerMethodField()
    ratings = RatingReadSerializer(many=True, read_only=True)

    class Meta:
        model = InterviewFeedback
        fields = ['id', 'interviewer', 'interviewer_name', 'is_submitted', 'recommendation', 'comments',
                  'submitted_at', 'score', 'ratings']

    def get_interviewer_name(self, obj):
        return full_name(obj.interviewer)

    def get_score(self, obj):
        return services.feedback_score(obj)


class InterviewSerializer(serializers.ModelSerializer):
    candidate_name = serializers.CharField(source='candidate.name', read_only=True)
    candidate_stage = serializers.CharField(source='candidate.stage', read_only=True)
    candidate_company = serializers.CharField(source='candidate.current_company', read_only=True)
    candidate_designation = serializers.CharField(source='candidate.current_designation', read_only=True)
    candidate_experience = serializers.DecimalField(source='candidate.experience_years', max_digits=4,
                                                    decimal_places=1, read_only=True)
    has_resume = serializers.SerializerMethodField()
    opening = serializers.IntegerField(source='candidate.opening_id', read_only=True)
    opening_number = serializers.CharField(source='candidate.opening.number', read_only=True)
    opening_title = serializers.CharField(source='candidate.opening.title', read_only=True)
    round_no = serializers.IntegerField(required=False, min_value=1)
    panel_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False,
                                      allow_empty=False)
    panel = serializers.SerializerMethodField()
    feedbacks = serializers.SerializerMethodField()
    criteria = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()
    my_feedback = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Interview
        fields = [
            'id', 'candidate', 'candidate_name', 'candidate_stage', 'candidate_company', 'candidate_designation',
            'candidate_experience', 'has_resume', 'opening', 'opening_number', 'opening_title', 'round_no',
            'round_type', 'scheduled_at', 'duration_minutes', 'mode', 'location', 'status', 'summary',
            'panel_ids', 'panel', 'feedbacks', 'criteria', 'score', 'my_feedback', 'created_by_name',
        ]

    # --- read side
    def get_has_resume(self, obj):
        return bool(obj.candidate.resume)

    def get_panel(self, obj):
        return [{'interviewer': f.interviewer_id, 'interviewer_name': full_name(f.interviewer),
                 'is_submitted': f.is_submitted} for f in obj.feedbacks.all()]

    def get_feedbacks(self, obj):
        """HR sees every scorecard. An interviewer sees only their own, so one
        panel member's marks do not sway another's."""
        user = self.context['request'].user
        rows = obj.feedbacks.all() if is_hr(user) else [f for f in obj.feedbacks.all() if f.interviewer_id == user.id]
        return FeedbackReadSerializer(rows, many=True, context=self.context).data

    def get_criteria(self, obj):
        return CriterionSerializer(obj.candidate.opening.criteria.all(), many=True).data

    def get_score(self, obj):
        return services.interview_score(obj) if is_hr(self.context['request'].user) else None

    def get_my_feedback(self, obj):
        """'pending' / 'submitted' for a panel member, else None."""
        user = self.context['request'].user
        for f in obj.feedbacks.all():
            if f.interviewer_id == user.id:
                return 'submitted' if f.is_submitted else 'pending'
        return None

    def get_created_by_name(self, obj):
        return full_name(obj.created_by)

    # --- write side
    def validate_panel_ids(self, ids):
        users = User.objects.filter(pk__in=set(ids), is_active=True)
        if users.count() != len(set(ids)):
            raise serializers.ValidationError('One of the interviewers is not an active user.')
        return list(users)

    def validate(self, attrs):
        if self.instance is None:
            if not attrs.get('panel_ids'):
                raise serializers.ValidationError({'panel_ids': 'Pick at least one interviewer.'})
            if attrs['candidate'].stage not in ACTIVE_STAGES:
                raise serializers.ValidationError({'candidate': 'This candidate is no longer in the pipeline.'})
        elif 'candidate' in attrs and attrs['candidate'].pk != self.instance.candidate_id:
            raise serializers.ValidationError({'candidate': 'The candidate of an interview cannot be changed.'})
        return attrs

    def _set_panel(self, interview, users):
        wanted = {u.pk: u for u in users}
        for feedback in list(interview.feedbacks.all()):
            if feedback.interviewer_id in wanted:
                del wanted[feedback.interviewer_id]
            elif feedback.is_submitted:
                raise serializers.ValidationError(
                    {'panel_ids': f'{full_name(feedback.interviewer)} has already given feedback.'})
            else:
                feedback.delete()
        for user in wanted.values():
            InterviewFeedback.objects.create(interview=interview, interviewer=user)

    @transaction.atomic
    def create(self, validated_data):
        users = validated_data.pop('panel_ids')
        request_user = self.context['request'].user
        candidate = validated_data['candidate']
        validated_data.setdefault('round_no', services.next_round_no(candidate))
        interview = Interview.objects.create(created_by=request_user, **validated_data)
        self._set_panel(interview, users)
        services.on_interview_scheduled(candidate, request_user)
        return interview

    @transaction.atomic
    def update(self, instance, validated_data):
        users = validated_data.pop('panel_ids', None)
        validated_data.pop('candidate', None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if users is not None:
            self._set_panel(instance, users)
        return instance


class RatingInputSerializer(serializers.Serializer):
    criterion = serializers.PrimaryKeyRelatedField(queryset=OpeningCriterion.objects.all())
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=500, default='')


class FeedbackSubmitSerializer(serializers.Serializer):
    recommendation = serializers.ChoiceField(choices=RECOMMENDATIONS)
    comments = serializers.CharField(required=False, allow_blank=True, default='')
    ratings = RatingInputSerializer(many=True, required=False)

    def validate(self, attrs):
        """Every criterion of the opening must be rated exactly once."""
        opening_criteria = {c.pk for c in self.context['interview'].candidate.opening.criteria.all()}
        given = [r['criterion'].pk for r in attrs.get('ratings', [])]
        if len(given) != len(set(given)):
            raise serializers.ValidationError({'ratings': 'A criterion is rated twice.'})
        if not set(given) <= opening_criteria:
            raise serializers.ValidationError({'ratings': 'A rating is for a criterion of another opening.'})
        missing = opening_criteria - set(given)
        if missing:
            raise serializers.ValidationError({'ratings': 'Rate every criterion before submitting.'})
        return attrs
