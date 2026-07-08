from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from task.models import RecurringTask, Task, Notification


class Command(BaseCommand):
    help = 'Create tasks from recurring task templates'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        recurring = RecurringTask.objects.filter(is_active=True).select_related(
            'task_alloted_to', 'createdby'
        )

        for r in recurring:
            trigger_date = r.next_due_date - timedelta(days=r.advance_days)

            if trigger_date <= today:
                # create the actual task
                task = Task.objects.create(
                    taskname=r.taskname,
                    description=r.description,
                    priority=r.priority,
                    task_alloted_to=r.task_alloted_to,
                    createdby=r.createdby,
                    target_date=timezone.datetime.combine(
                        r.next_due_date, timezone.datetime.min.time()
                    ),
                )

                # notify assignee
                if r.task_alloted_to != r.createdby:
                    Notification.objects.create(
                        user=r.task_alloted_to,
                        task=task,
                        message=f'Recurring task due: "{r.taskname}" — due on {r.next_due_date}'
                    )

                # advance next_due_date
                r.next_due_date = r.next_due_date + timedelta(days=r.interval_days)
                r.save()

                self.stdout.write(
                    self.style.SUCCESS(f'Created task: {r.taskname} — next due: {r.next_due_date}')
                )