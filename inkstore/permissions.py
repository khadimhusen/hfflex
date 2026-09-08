from rest_framework.permissions import BasePermission


class IsInkStoreUser(BasePermission):
    """The old app's ink_list/search_ink/edit_ink views were login_required
    only -- any authenticated user could view and edit an ink can.
    TEMPORARY: restricted to staff/superuser during rollout, the same
    pattern every other migrated module uses. There is no 'sideink'
    department to fall back to, so widening this later means either
    creating one or dropping the check back to plain authentication."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or user.is_superuser
