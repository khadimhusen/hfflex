from rest_framework.permissions import BasePermission, SAFE_METHODS

from crm.querysets import crm_users

from .querysets import order_department_users


def has_full_order_access(user):
    # TEMPORARY: order module restricted to staff/superuser only during
    # rollout — restore department-based access by swapping the return
    # below for the commented-out line once ready for wider access.
    if not user or not user.is_authenticated:
        return False
    return user.is_staff or user.is_superuser
    # return user.is_staff or user.is_superuser or order_department_users().filter(id=user.id).exists()


class IsOrderUser(BasePermission):
    def has_permission(self, request, view):
        return has_full_order_access(request.user)


class IsOrderUserOrCrmReadOnly(BasePermission):
    """Full access for order users (as IsOrderUser), read-only for CRM users:
    marketing can look a job up from the top-bar Job Search, but can never
    create, edit, cancel, scale or approve anything -- GET/HEAD/OPTIONS only."""
    def has_permission(self, request, view):
        user = request.user
        if has_full_order_access(user):
            return True
        return (
            request.method in SAFE_METHODS
            and bool(user and user.is_authenticated)
            and crm_users().filter(id=user.id).exists()
        )
