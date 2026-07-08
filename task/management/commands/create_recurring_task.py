from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, date
from task.models import RecurringTask, Task, Notification


class Command(BaseCommand):
    help = 'Create tasks from recurring task templates'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        recurring = RecurringTask.objects.filter(is_active=True).select_related(
            'task_alloted_to', 'createdby'
        )

        for r in recurring:
            due_date = self.get_due_date(r, today)
            if due_date is None:
                continue

            trigger_date = due_date - timedelta(days=r.advance_days)

            if trigger_date != today:
                continue

            # avoid duplicate — check if task already created for this due date
            already_exists = Task.objects.filter(
                taskname=r.taskname,
                target_date__date=due_date,
                createdby=r.createdby,
            ).exists()

            if already_exists:
                self.stdout.write(f'Skipping duplicate: {r.taskname} for {due_date}')
                continue

            # create task
            task = Task.objects.create(
                taskname=r.taskname,
                description=r.description,
                priority=r.priority,
                task_alloted_to=r.task_alloted_to,
                createdby=r.createdby,
                target_date=timezone.datetime.combine(
                    due_date, timezone.datetime.min.time()
                ),
            )

            # update last_created_date for interval type
            if r.recur_type == 'interval':
                r.last_created_date = today
                r.save()

            # notify
            if r.task_alloted_to != r.createdby:
                Notification.objects.create(
                    user=r.task_alloted_to,
                    task=task,
                    message=f'Recurring task due: "{r.taskname}" — due on {due_date}'
                )

            self.stdout.write(self.style.SUCCESS(f'Created: {r.taskname} due {due_date}'))

    def get_due_date(self, r, today):
        if r.recur_type == 'monthly':
            # check if today's month is in the configured months
            months = [int(m.strip()) for m in r.months.split(',')]
            if today.month not in months:
                return None
            try:
                return date(today.year, today.month, r.day_of_month)
            except ValueError:
                # day doesn't exist in this month (e.g. 31 in April)
                return None

        elif r.recur_type == 'interval':
            if r.last_created_date is None:
                # never created — treat today as trigger
                return today + timedelta(days=r.advance_days)
            next_due = r.last_created_date + timedelta(days=r.interval_days)
            return next_due

        return None