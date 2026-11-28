from rest_framework.permissions import BasePermission

from crm.querysets import is_hr


class IsAttendanceUser(BasePermission):
    """Attendance holds every worker's times, so it is for HR only: staff, superusers
    and the 'hr' department. Loosen it here when other people need it."""

    def has_permission(self, request, view):
        return is_hr(request.user)
