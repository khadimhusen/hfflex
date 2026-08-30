from rest_framework.permissions import BasePermission


class IsTaskUser(BasePermission):
    """The old app's task views were @login_required only (accessview is a
    permanent no-op) -- no department gate ever existed here, unlike
    every other module's rollout restriction."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
