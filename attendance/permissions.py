from rest_framework.permissions import BasePermission


class IsAttendanceUser(BasePermission):
    """Attendance holds every worker's times, so for now it is for staff users only
    (the same rollout rule manpower uses). Loosen it here when other people need it."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))
