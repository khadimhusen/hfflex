from rest_framework.permissions import BasePermission, SAFE_METHODS

from crm.querysets import crm_users

from .querysets import itemmaster_department_users


def has_full_itemmaster_access(user):
    # TEMPORARY: restricted to staff/superuser only during rollout —
    # restore department-based access via the commented-out line once
    # ready for wider access.
    if not user or not user.is_authenticated:
        return False
    return user.is_staff or user.is_superuser
    # return user.is_staff or user.is_superuser or itemmaster_department_users().filter(id=user.id).exists()


class IsItemmasterUser(BasePermission):
    def has_permission(self, request, view):
        return has_full_itemmaster_access(request.user)


class IsItemmasterUserOrCrmReadOnly(BasePermission):
    """Full access for itemmaster users (as IsItemmasterUser), read-only for
    CRM users: marketing can browse the item list and open an item, but can
    never create, edit, clone or delete anything -- GET/HEAD/OPTIONS only."""
    def has_permission(self, request, view):
        user = request.user
        if has_full_itemmaster_access(user):
            return True
        return (
            request.method in SAFE_METHODS
            and bool(user and user.is_authenticated)
            and crm_users().filter(id=user.id).exists()
        )
