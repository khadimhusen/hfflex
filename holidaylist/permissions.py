from rest_framework.permissions import SAFE_METHODS, BasePermission

from crm.querysets import is_hr


def can_edit_holidays(user):
    return is_hr(user)


class HolidayPermission(BasePermission):
    """Everybody who is logged in can read the list (it is posted on the notice board
    anyway); only staff users change it. (The API's default also demands a CRM user,
    which would lock out people who are not in the CRM.)"""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or can_edit_holidays(user)
