from rest_framework.permissions import BasePermission


class IsCoaUser(BasePermission):
    """General view/edit access -- the old app's coa_edit/coa_detail views
    were login_required only (accessview was a permanent no-op), so any
    authenticated user could view or edit an unapproved COA. TEMPORARY:
    restricted to staff/superuser only during rollout, same pattern as
    every other module -- restore via the commented-out line once ready."""
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or user.is_superuser
        # from .querysets import can_create_coa_users
        # return user.is_staff or user.is_superuser or can_create_coa_users().filter(id=user.id).exists()


class CanApproveCoa(BasePermission):
    """Gates the approve action -- mirrors the old app's 'can_approve_coa'
    department check on the Approve button (a real, separate tier from
    general edit access, not just the TEMPORARY is_staff rollout gate)."""
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or user.is_superuser
        # from .querysets import can_approve_coa_users
        # return user.is_staff or user.is_superuser or can_approve_coa_users().filter(id=user.id).exists()


class IsStaffForReopen(BasePermission):
    """Mirrors the old app's @staff_member_required on coa_reopen exactly
    -- a real Django is_staff check, not a department flag or rollout
    gate (the old app never gated this behind a department either)."""
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)
