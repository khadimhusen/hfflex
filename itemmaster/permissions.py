from rest_framework.permissions import BasePermission

from .querysets import itemmaster_department_users


class IsItemmasterUser(BasePermission):
    # TEMPORARY: restricted to staff/superuser only during rollout —
    # restore department-based access via the commented-out line once
    # ready for wider access.
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or user.is_superuser
        # return user.is_staff or user.is_superuser or itemmaster_department_users().filter(id=user.id).exists()
