import os
import uuid

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.utils import timezone

OPENING_STATUS = [('draft', 'Draft'), ('open', 'Open'), ('on_hold', 'On hold'), ('closed', 'Closed')]

SOURCES = [
    ('Reference', 'Reference'),
    ('Job portal', 'Job portal'),
    ('Walk-in', 'Walk-in'),
    ('Consultant', 'Consultant'),
    ('Social media', 'Social media'),
    ('Other', 'Other'),
]

STAGES = [
    ('applied', 'Applied'),
    ('shortlisted', 'Shortlisted'),
    ('interview', 'Interview'),
    ('selected', 'Selected'),
    ('offered', 'Offered'),
    ('joined', 'Joined'),
    ('rejected', 'Rejected'),
    ('withdrawn', 'Withdrawn'),
]
ACTIVE_STAGES = ['applied', 'shortlisted', 'interview', 'selected', 'offered']
CLOSED_STAGES = ['joined', 'rejected', 'withdrawn']

ROUND_TYPES = [('HR', 'HR'), ('Technical', 'Technical'), ('Plant visit', 'Plant visit'), ('Final', 'Final')]
INTERVIEW_MODES = [('in_person', 'In person'), ('phone', 'Phone'), ('video', 'Video')]
INTERVIEW_STATUS = [
    ('scheduled', 'Scheduled'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('no_show', 'No show'),
]
RECOMMENDATIONS = [
    ('strong_yes', 'Strong yes'), ('yes', 'Yes'), ('no', 'No'), ('strong_no', 'Strong no'),
]


def today():
    # USE_TZ is off in this project, so timezone.localdate() would fail.
    return timezone.now().date()


def resume_path(instance, filename):
    """Resumes are personal data and /media/ is served as plain files, so the stored
    name is random: a path cannot be guessed. The app serves them through a
    logged-in endpoint instead of this path."""
    ext = os.path.splitext(filename)[1].lower()
    return f'recruitment/resumes/{today():%Y/%m}/{uuid.uuid4().hex}{ext}'


class JobOpening(models.Model):
    """A requirement: a role the plant wants to fill."""
    number = models.CharField(max_length=20, unique=True, editable=False)       # REQ-2026-001
    title = models.CharField(max_length=200)
    department = models.CharField(max_length=100, blank=True)
    positions = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    location = models.CharField(max_length=200, blank=True)
    experience_min = models.PositiveSmallIntegerField(null=True, blank=True)    # years
    experience_max = models.PositiveSmallIntegerField(null=True, blank=True)
    salary_min = models.PositiveIntegerField(null=True, blank=True)             # monthly, rupees
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=OPENING_STATUS, default='open')
    opened_date = models.DateField(default=today)
    target_date = models.DateField(null=True, blank=True)                       # fill it by
    closed_date = models.DateField(null=True, blank=True)
    hiring_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='openings_managed')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='openings_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-opened_date', '-id']

    def __str__(self):
        return f'{self.number} {self.title}'

    def save(self, *args, **kwargs):
        if self.status == 'closed' and not self.closed_date:
            self.closed_date = today()
        elif self.status != 'closed':
            self.closed_date = None
        if self.number:
            return super().save(*args, **kwargs)
        # REQ-<year>-<running count>. A clash from two simultaneous saves is caught by
        # the unique constraint and the loop takes the next number (same as meetings).
        year = (self.opened_date or today()).year
        for _ in range(5):
            self.number = self.next_number(year)
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ''
                if self.pk:
                    raise
        raise IntegrityError('Could not allocate an opening number.')

    @staticmethod
    def next_number(year):
        prefix = f'REQ-{year}-'
        taken = JobOpening.objects.filter(number__startswith=prefix).values_list('number', flat=True)
        highest = max((int(n[len(prefix):]) for n in taken if n[len(prefix):].isdigit()), default=0)
        return f'{prefix}{highest + 1:03d}'


class OpeningCriterion(models.Model):
    """One line of the interview scorecard for an opening (e.g. "Planning and
    scheduling"). Interviewers rate each 1-5; weight says how much it counts."""
    opening = models.ForeignKey(JobOpening, on_delete=models.CASCADE, related_name='criteria')
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=500, blank=True)      # what to look for / ask
    weight = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.name


class Candidate(models.Model):
    opening = models.ForeignKey(JobOpening, on_delete=models.PROTECT, related_name='candidates')
    name = models.CharField(max_length=200)
    mobile = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    current_company = models.CharField(max_length=200, blank=True)
    current_designation = models.CharField(max_length=200, blank=True)
    experience_years = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    current_salary = models.PositiveIntegerField(null=True, blank=True)      # monthly, rupees
    expected_salary = models.PositiveIntegerField(null=True, blank=True)
    notice_period_days = models.PositiveSmallIntegerField(null=True, blank=True)
    source = models.CharField(max_length=20, choices=SOURCES, default='Reference')
    source_detail = models.CharField(max_length=200, blank=True)             # who referred / which portal
    resume = models.FileField(upload_to=resume_path, max_length=255, null=True, blank=True)
    notes = models.TextField(blank=True)

    stage = models.CharField(max_length=12, choices=STAGES, default='applied')
    rejection_reason = models.CharField(max_length=300, blank=True)
    offered_salary = models.PositiveIntegerField(null=True, blank=True)
    offer_date = models.DateField(null=True, blank=True)
    joining_date = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='candidates_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.name} ({self.opening.number})'

    @property
    def is_active(self):
        return self.stage in ACTIVE_STAGES


class StageLog(models.Model):
    """Who moved a candidate to which stage, and when."""
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='stage_logs')
    from_stage = models.CharField(max_length=12, blank=True)
    to_stage = models.CharField(max_length=12, choices=STAGES)
    note = models.CharField(max_length=500, blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['changed_at', 'id']


class Interview(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='interviews')
    round_no = models.PositiveSmallIntegerField(default=1)
    round_type = models.CharField(max_length=20, choices=ROUND_TYPES, default='HR')
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=45)
    mode = models.CharField(max_length=10, choices=INTERVIEW_MODES, default='in_person')
    location = models.CharField(max_length=300, blank=True)                 # room, address or meeting link
    status = models.CharField(max_length=10, choices=INTERVIEW_STATUS, default='scheduled')
    summary = models.TextField(blank=True)                                  # HR's overall remarks
    cancel_reason = models.TextField(blank=True)                            # why it was cancelled
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='interviews_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_at', '-id']

    def __str__(self):
        return f'{self.candidate.name} round {self.round_no}'


class InterviewLog(models.Model):
    """History of an interview being moved to another time or cancelled."""
    ACTIONS = [('rescheduled', 'Rescheduled'), ('cancelled', 'Cancelled')]
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=12, choices=ACTIONS)
    old_time = models.DateTimeField(null=True, blank=True)
    new_time = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at', '-id']


class InterviewFeedback(models.Model):
    """One panel member's slot on an interview. It exists from the moment the
    interview is scheduled (so "who still owes feedback" is a plain query) and
    is filled in when `submitted_at` is set."""
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name='feedbacks')
    interviewer = models.ForeignKey(User, on_delete=models.PROTECT, related_name='interview_feedbacks')
    recommendation = models.CharField(max_length=12, choices=RECOMMENDATIONS, blank=True)
    comments = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['interview', 'interviewer']
        ordering = ['id']

    @property
    def is_submitted(self):
        return self.submitted_at is not None


class FeedbackRating(models.Model):
    feedback = models.ForeignKey(InterviewFeedback, on_delete=models.CASCADE, related_name='ratings')
    criterion = models.ForeignKey(OpeningCriterion, on_delete=models.CASCADE, related_name='ratings')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.CharField(max_length=500, blank=True)

    class Meta:
        unique_together = ['feedback', 'criterion']
        ordering = ['criterion__order', 'criterion_id']
