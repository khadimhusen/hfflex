from rest_framework.permissions import BasePermission


class IsReturnableUser(BasePermission):
    # TEMPORARY: restricted to staff/superuser only during rollout --
    # restore department-based access via the commented-out line once
    # ready for wider access. Matches the same rollout pattern used by
    # bank/manpower/documents's own permission classes.
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or user.is_superuser
        # from .querysets import returnable_department_users
        # return user.is_staff or user.is_superuser or returnable_department_users().filter(id=user.id).exists()
