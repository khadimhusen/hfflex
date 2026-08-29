from rest_framework.permissions import BasePermission

from .utils import get_planning_role


class IsPlanningUser(BasePermission):
    """Real role check, mirroring the old app's planning_access_required
    exactly (get_planning_role != None) -- manager/supervisor/operator/
    viewer. Finer-grained rules (operator confined to their own machine,
    manager/supervisor-only actions like reorder/idle slots) are enforced
    per-action in the viewsets themselves, matching where the old views
    enforced them (decorators on individual view functions, not uniformly)."""
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return get_planning_role(user) is not None
