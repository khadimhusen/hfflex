from django.db.models import Q
from rest_framework.permissions import BasePermission


class IsMeetingUser(BasePermission):
    """Any logged-in user, like Tasks. (The API's default also demands a CRM
    user, which would lock out attendees who only ever see meetings.) What a
    user can actually see is decided by visible_meetings()."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


def is_staff_user(user):
    return bool(user.is_staff or user.is_superuser)


def visible_meetings(user, queryset):
    """Staff see every meeting; everyone else only the ones they created, attended
    or were given an action item in (minutes can be confidential)."""
    if is_staff_user(user):
        return queryset
    return queryset.filter(
        Q(created_by=user) | Q(attendees__user=user) | Q(action_items__owner=user)).distinct()


def can_edit_meeting(user, meeting):
    """The creator or a staff user -- drafts and finalised minutes alike."""
    return is_staff_user(user) or meeting.created_by_id == user.id


def can_delete_meeting(user, meeting):
    """A draft: its creator or staff. A finalised meeting (it has made tasks): staff only."""
    if is_staff_user(user):
        return True
    return meeting.created_by_id == user.id and not meeting.is_final


def can_update_action_status(user, item):
    """Mark done / reopen: the item's owner, the meeting's creator, or staff."""
    return is_staff_user(user) or item.owner_id == user.id or item.meeting.created_by_id == user.id
