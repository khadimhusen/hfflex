from rest_framework.permissions import BasePermission


class IsPlanningUser(BasePermission):
    # TEMPORARY: restricted to staff/superuser only during rollout, matching
    # every other newly-exposed module this round (order/production/
    # itemmaster/preorder/purchase) -- this app never had an API before
    # this, so there's no existing department-based queryset to restore
    # here later; add one when planning is ready for wider access.
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or user.is_superuser
