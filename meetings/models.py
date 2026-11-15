from django.contrib.auth.models import User
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from task.choices import PRIORITY

MEETING_TYPES = [
    ('Production', 'Production'),
    ('Management', 'Management'),
    ('Customer', 'Customer'),
    ('Board', 'Board'),
]
STATUS_CHOICES = [('draft', 'Draft'), ('final', 'Final')]


class Meeting(models.Model):
    number = models.CharField(max_length=20, unique=True, editable=False)   # MOM-2026-014
    title = models.CharField(max_length=300)
    meeting_type = models.CharField(max_length=30, choices=MEETING_TYPES, default='Production')
    meeting_date = models.DateField()
    meeting_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=300, blank=True)
    agenda = models.TextField(blank=True)
    minutes = models.TextField(blank=True)              # the discussion and decisions
    next_meeting_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='meetings_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalised_at = models.DateTimeField(null=True, blank=True)
    finalised_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='meetings_finalised')

    class Meta:
        ordering = ['-meeting_date', '-id']

    def __str__(self):
        return f'{self.number} {self.title}'

    @property
    def is_final(self):
        return self.status == 'final'

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        # Number = MOM-<year>-<running count for that year>. Two people saving at
        # the same instant could pick the same number; the unique constraint
        # catches that and the loop simply takes the next one.
        year = (self.meeting_date or timezone.now().date()).year
        for _ in range(5):
            self.number = self.next_number(year)
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ''
                if self.pk:
                    raise
        raise IntegrityError('Could not allocate a meeting number.')

    @staticmethod
    def next_number(year):
        prefix = f'MOM-{year}-'
        taken = Meeting.objects.filter(number__startswith=prefix).values_list('number', flat=True)
        highest = max((int(n[len(prefix):]) for n in taken if n[len(prefix):].isdigit()), default=0)
        return f'{prefix}{highest + 1:03d}'


class MeetingAttendee(models.Model):
    """Someone who was there: a user of the system, or an outside person typed in
    by name. `name` is always filled so the minutes still read right if the user
    is later removed."""
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='attendees')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='meetings_attended')
    name = models.CharField(max_length=200)
    organisation = models.CharField(max_length=200, blank=True)     # for outside people

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['meeting', 'user'], condition=models.Q(user__isnull=False),
                                    name='one_attendee_row_per_user_per_meeting'),
        ]

    def __str__(self):
        return self.name

    @property
    def is_external(self):
        return self.user_id is None


class ActionItem(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='action_items')
    description = models.CharField(max_length=500)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='meeting_action_items')
    due_date = models.DateField()
    priority = models.CharField(max_length=16, choices=PRIORITY, default='NORMAL')
    # Created when the meeting is finalised, so the owner gets it in their tasks.
    task = models.OneToOneField('task.Task', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='meeting_action_item')
    is_done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    done_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'id']

    def __str__(self):
        return self.description

    @property
    def status(self):
        """'done' once marked done here, or once its task has been closed in Tasks."""
        if self.is_done or (self.task_id and self.task.is_closed):
            return 'done'
        return 'open'
