from rest_framework.permissions import BasePermission, SAFE_METHODS

from .querysets import can_edit_resolution


class ResolutionPermission(BasePermission):
    """Mirrors the old app's actual access rules exactly (this module was
    never staff-only -- resolution_list/resolution_detail had no
    @login_required at all, matching many companies' statutory duty to
    publish board resolutions publicly):

    - list/retrieve: open to anyone, including anonymous users. The
      queryset itself (see ResolutionViewSet.get_queryset) is what hides
      drafts from non-editors, same as the old views' own filtering.
    - create/update (and the nested documents action): requires
      can_edit_resolution (admin or an authorized ResolutionEditor).
    - destroy: admin-only (can_delete_resolution) -- stricter than edit,
      matching resolution_delete()'s own separate, tighter check.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return can_edit_resolution(request.user)
