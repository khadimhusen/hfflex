from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import FeedbackRating, StageLog

# Ready-made scorecards HR can load into a new opening and then edit.
CRITERIA_TEMPLATES = {
    'production_manager': {
        'label': 'Production Manager (flexible packaging)',
        'criteria': [
            ('Process knowledge', 5,
             'Extrusion / printing / lamination / slitting / pouching. Ask: low bond strength after 48 h of '
             'aging, what do you check?'),
            ('Planning and scheduling', 4,
             'Sequencing jobs to cut changeovers, finding the bottleneck, giving a realistic delivery date.'),
            ('Cost and wastage control', 4,
             'Waste % by stage, OEE, solvent / adhesive consumption. Ask for the numbers from the last plant.'),
            ('Quality mindset', 3,
             'Works with QC, root-cause analysis (5-Why / 8D), food-safety exposure (BRC / FSSC / ISO 22000).'),
            ('People leadership', 4,
             'Ran a shop floor, trains operators, builds supervisors, handles shift discipline.'),
            ('Maintenance and safety', 3,
             'Preventive maintenance habits, solvent fire safety, earthing, 5S.'),
            ('Systems and reporting', 2,
             'Daily MIS, job cards, uses ERP data to decide rather than paper.'),
            ('Ownership and communication', 3,
             'Takes responsibility, says "this cannot be done by Friday" early, works across sales / purchase / QC.'),
        ],
    },
    'general': {
        'label': 'General role',
        'criteria': [
            ('Technical skills', 5, 'Knowledge needed for the role.'),
            ('Relevant experience', 4, 'Similar work, similar scale.'),
            ('Communication', 3, ''),
            ('Attitude and ownership', 4, ''),
            ('Stability and notice period', 2, 'Job history, reason for leaving, ability to join on time.'),
        ],
    },
}


def criteria_templates():
    return [
        {'key': key, 'label': tpl['label'],
         'criteria': [{'name': name, 'weight': weight, 'description': desc, 'order': i}
                      for i, (name, weight, desc) in enumerate(tpl['criteria'])]}
        for key, tpl in CRITERIA_TEMPLATES.items()
    ]


# ---------------------------------------------------------------- pipeline

@transaction.atomic
def move_stage(candidate, to_stage, user, note='', rejection_reason='', joining_date=None):
    """Move a candidate along the pipeline and write the log line."""
    from_stage = candidate.stage
    if to_stage == from_stage:
        raise ValidationError({'stage': 'The candidate is already in this stage.'})
    if from_stage == 'joined':
        raise ValidationError({'stage': 'A candidate who has joined cannot be moved.'})
    if to_stage == 'rejected' and not rejection_reason.strip():
        raise ValidationError({'rejection_reason': 'Say why the candidate is being rejected.'})
    if to_stage == 'joined':
        if from_stage not in ('selected', 'offered'):
            raise ValidationError({'stage': 'Only a selected or offered candidate can be marked as joined.'})
        joining_date = joining_date or candidate.joining_date
        if not joining_date:
            raise ValidationError({'joining_date': 'Enter the joining date.'})
        candidate.joining_date = joining_date
    if to_stage == 'offered' and not candidate.offer_date:
        candidate.offer_date = timezone.now().date()

    candidate.stage = to_stage
    candidate.rejection_reason = rejection_reason.strip() if to_stage == 'rejected' else ''
    candidate.save()
    StageLog.objects.create(candidate=candidate, from_stage=from_stage, to_stage=to_stage,
                            note=note.strip(), changed_by=user)
    return candidate


def next_round_no(candidate):
    last = candidate.interviews.order_by('-round_no').values_list('round_no', flat=True).first()
    return (last or 0) + 1


def on_interview_scheduled(candidate, user):
    """Scheduling an interview moves a fresh candidate into the Interview stage."""
    if candidate.stage in ('applied', 'shortlisted'):
        move_stage(candidate, 'interview', user, note='Interview scheduled')


# ---------------------------------------------------------------- scoring

def feedback_score(feedback):
    """Weighted average (1-5) of one interviewer's ratings; None until they rate."""
    pairs = [(r.rating, r.criterion.weight) for r in feedback.ratings.all()]
    total_weight = sum(w for _, w in pairs)
    if not total_weight:
        return None
    return round(sum(r * w for r, w in pairs) / total_weight, 2)


def interview_score(interview):
    scores = [feedback_score(f) for f in interview.feedbacks.all() if f.submitted_at]
    scores = [s for s in scores if s is not None]
    return round(sum(scores) / len(scores), 2) if scores else None


def candidate_score(candidate):
    """Average across the candidate's interviews that were not cancelled."""
    scores = [interview_score(i) for i in candidate.interviews.all() if i.status != 'cancelled']
    scores = [s for s in scores if s is not None]
    return round(sum(scores) / len(scores), 2) if scores else None


# ---------------------------------------------------------------- feedback

@transaction.atomic
def submit_feedback(feedback, recommendation, comments, ratings):
    """Save (or re-save) one interviewer's scorecard. `ratings` is a list of
    {'criterion': OpeningCriterion, 'rating': int, 'comment': str}."""
    feedback.ratings.all().delete()
    FeedbackRating.objects.bulk_create([
        FeedbackRating(feedback=feedback, criterion=r['criterion'], rating=r['rating'],
                       comment=r.get('comment', ''))
        for r in ratings
    ])
    feedback.recommendation = recommendation
    feedback.comments = comments
    feedback.submitted_at = timezone.now()
    feedback.save()

    # Everyone on the panel has answered: the interview is done.
    interview = feedback.interview
    if interview.status == 'scheduled' and not interview.feedbacks.filter(submitted_at__isnull=True).exists():
        interview.status = 'completed'
        interview.save(update_fields=['status', 'updated_at'])
    return feedback
