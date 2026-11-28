from rest_framework.permissions import BasePermission

from crm.querysets import is_hr as crm_is_hr


def is_hr(user):
    """Staff, superusers and the 'hr' department run recruitment: openings, candidates, salaries."""
    return crm_is_hr(user)


class IsHR(BasePermission):
    def has_permission(self, request, view):
        return is_hr(request.user)


class IsLoggedIn(BasePermission):
    """Any logged-in user. (The API default also demands a CRM user, which would lock
    out interviewers who only ever see their own interviews.) What a user can see
    is decided by visible_interviews()."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


def visible_interviews(user, queryset):
    """HR sees every interview; an interviewer only the ones they are on the panel of."""
    if is_hr(user):
        return queryset
    return queryset.filter(feedbacks__interviewer=user).distinct()
