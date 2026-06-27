from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Copy all departments from a source user to a target user.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--from',
            dest='from_user',
            required=True,
            help='Username to copy departments FROM',
        )
        parser.add_argument(
            '--to',
            dest='to_user',
            required=True,
            help='Username to copy departments TO',
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            default=False,
            help='If set, replaces target user departments instead of merging.',
        )

    def handle(self, *args, **options):
        from_username = options['from_user']
        to_username = options['to_user']
        replace = options['replace']

        # --- Validate users ---
        try:
            source_user = User.objects.get(username=from_username)
        except User.DoesNotExist:
            raise CommandError(f"Source user '{from_username}' does not exist.")

        try:
            target_user = User.objects.get(username=to_username)
        except User.DoesNotExist:
            raise CommandError(f"Target user '{to_username}' does not exist.")

        if source_user == target_user:
            raise CommandError("Source and target users cannot be the same.")

        # --- Fetch departments ---
        source_departments = source_user.department.all()

        if not source_departments.exists():
            self.stdout.write(self.style.WARNING(
                f"User '{from_username}' has no departments. Nothing to copy."
            ))
            return

        source_names = list(source_departments.values_list('department_name', flat=True))
        self.stdout.write(f"\nDepartments on '{from_username}': {', '.join(source_names)}")

        if replace:
            # Clear existing and set exactly the source departments
            existing = list(target_user.department.values_list('department_name', flat=True))
            target_user.department.set(source_departments)
            self.stdout.write(self.style.WARNING(
                f"Replaced departments on '{to_username}'. "
                f"Previous: {', '.join(existing) or 'none'}"
            ))
        else:
            # Merge: add only departments not already assigned
            existing_ids = set(target_user.department.values_list('id', flat=True))
            new_departments = source_departments.exclude(id__in=existing_ids)

            if not new_departments.exists():
                self.stdout.write(self.style.WARNING(
                    f"'{to_username}' already has all departments from '{from_username}'. Nothing added."
                ))
                return

            new_names = list(new_departments.values_list('department_name', flat=True))
            target_user.department.add(*new_departments)
            self.stdout.write(f"Added departments to '{to_username}': {', '.join(new_names)}")

        final = list(target_user.department.values_list('department_name', flat=True))
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Done. '{to_username}' now has: {', '.join(final)}"
        ))