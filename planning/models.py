from django.db import models
from itemmaster.models import Machine, MachineTask
from order.models import JobProcess
from django.contrib.auth.models import User
from material.models import Unit
from .choices import PROCESS_STATUS, SCHEDULE_TYPE, IDLE_TYPE, MATERIAL_STATUS
from django.core.exceptions import ValidationError
from datetime import timedelta


class IdleTime(models.Model):
    name = models.CharField(max_length=256, unique=True)
    category = models.CharField(max_length=16, choices=IDLE_TYPE, default='Unplanned')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class MachineScheduleQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(queue_position__gt=0)

    def running(self):
        return self.filter(queue_position=0)

    def completed(self):
        return self.filter(queue_position=-1)

    def active(self):
        """Pending + Running"""
        return self.filter(queue_position__gte=0)

    def for_machine(self, machine):
        return self.filter(machine=machine)


class MachineSchedule(models.Model):
    schedule_type = models.CharField(max_length=16, choices=SCHEDULE_TYPE, default='Production')
    jobprocess = models.ForeignKey(JobProcess, related_name='schedules', on_delete=models.CASCADE, null=True,
                                   blank=True)
    raw_material_status = models.CharField(choices=MATERIAL_STATUS,default="Not Available")
    idle_reason = models.ForeignKey(IdleTime, on_delete=models.PROTECT, null=True, blank=True)
    idle_notes = models.TextField(null=True, blank=True)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="schedules")
    qty = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True)
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.PROTECT)
    speed = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=PROCESS_STATUS, default="Pending")
    persons_assigned = models.PositiveSmallIntegerField(default=2)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    makeready_duration = models.DurationField(null=True, blank=True)
    running_duration = models.DurationField(null=True, blank=True)
    downtime_duration = models.DurationField(null=True, blank=True)
    estimated_duration = models.DurationField()
    time_variance = models.DurationField(null=True, blank=True, help_text="Positive =delayed, Negative =finished early")
    remark = models.CharField(max_length=1024, null=True, blank=True)
    queue_position = models.IntegerField(
        help_text="-1 = completed, 0 = running, positive = queue position"
    )
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='machineschedulecreated')
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='machinescheduleeditedby')
    edited = models.DateTimeField(auto_now=True)

    objects = MachineScheduleQuerySet.as_manager()

    class Meta:
        ordering = ['machine', 'queue_position', '-end_time']
        constraints = [
            # Only ONE position=0 per machine
            models.UniqueConstraint(
                fields=['machine'],
                condition=models.Q(queue_position=0),
                name='one_running_per_machine',
            ),
            # Positive positions unique per machine
            models.UniqueConstraint(
                fields=['machine', 'queue_position'],
                condition=models.Q(queue_position__gt=0),
                name='unique_pending_position',
            ),
            # Status must match queue_position
            models.CheckConstraint(
                check=(
                        (models.Q(queue_position=-1) & models.Q(status='Completed')) |
                        (models.Q(queue_position=0) & models.Q(status='Running')) |
                        (models.Q(queue_position__gt=0) & models.Q(status__in=['Pending', 'Hold']))
                ),
                name='status_matches_position',
            ),

            models.CheckConstraint(
                name="exactly_one_field_filled",
                check=(
                    # either field must be filled.
                        (models.Q(jobprocess__isnull=False) & models.Q(idle_reason__isnull=True)) |
                        (models.Q(jobprocess__isnull=True) & models.Q(idle_reason__isnull=False))
                )
            )
        ]

    @property
    def is_completed(self):
        return self.queue_position == -1

    @property
    def is_running(self):
        return self.queue_position == 0

    @property
    def is_pending(self):
        return self.queue_position > 0

    @property
    def time_variance_seconds(self):
        if self.time_variance is None:
            return 0
        return int(self.time_variance.total_seconds())

    def clean(self):
        # Auto-assign queue_position
        if self.queue_position is None:
            if not self.machine:
                raise ValidationError("Machine is required to auto-assign queue position.")
            last = (
                MachineSchedule.objects
                .for_machine(self.machine)
                .pending()
                .order_by('-queue_position')
                .first()
            )
            self.queue_position = (last.queue_position + 1) if last else 1

        # Auto-assign estimated_duration if not provided
        if self.estimated_duration is None:
            self.estimated_duration = (
                    (self.makeready_duration or timedelta(0)) +
                    (self.running_duration or timedelta(0)) +
                    (self.downtime_duration or timedelta(0))
            )

        # Status must match queue_position
        if self.queue_position == -1 and self.status != 'Completed':
            raise ValidationError(
                f"Status '{self.status}' doesn't match queue_position -1. "
                f"Expected 'Completed'."
            )
        elif self.queue_position == 0 and self.status != 'Running':
            raise ValidationError(
                f"Status '{self.status}' doesn't match queue_position 0. "
                f"Expected 'Running'."
            )
        elif self.queue_position > 0 and self.status not in ('Pending', 'Hold'):
            raise ValidationError(
                f"Status '{self.status}' doesn't match queue_position {self.queue_position}. "
                f"Expected 'Pending' or 'Hold'."
            )

        if self.schedule_type == 'Job' and not self.jobprocess:
            raise ValidationError("Job schedule requires jobprocess.")
        if self.schedule_type == 'Idle' and not self.idle_reason:
            raise ValidationError("Idle schedule requires idle reason.")

    def __str__(self):
        if self.schedule_type == 'Idle':
            return f"{self.machine} #{self.queue_position} | IDLE: {self.idle_reason}"
        return f"{self.machine} #{self.queue_position} | {self.jobprocess}"


class ProductionTask(models.Model):
    machine_schedule = models.ForeignKey(MachineSchedule, on_delete=models.CASCADE, related_name='productiontasks')
    qty = models.PositiveSmallIntegerField(default=0)
    task = models.ForeignKey(MachineTask, on_delete=models.PROTECT, related_name='productiontasks')
    time_per_task = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return f'{str(self.machine_schedule.machine)} :- {str(self.time_per_task)} - {self.task}'

    @property
    def total_time(self):
        return self.qty * self.time_per_task

    @property
    def effective_duration(self):
        persons_assigned = self.machine_schedule.persons_assigned or 1
        persons_required = self.task.persons_required or 1
        return round((self.time_per_task * persons_required * self.qty) / persons_assigned)


class MachineDowntime(models.Model):
    machine_schedule = models.ForeignKey(MachineSchedule, on_delete=models.CASCADE, related_name='downtimes')
    reason = models.ForeignKey(IdleTime, on_delete=models.PROTECT,
                               limit_choices_to={'category': 'Unplanned'},
                               related_name="machinedowntimes")
    duration = models.DurationField()
    notes = models.CharField(max_length=512, null=True, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT,null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.machine_schedule} | {self.reason} | {self.duration}"
