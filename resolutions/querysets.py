from .models import ResolutionEditor


def can_edit_resolution(user):
    """Verbatim port of the old view's can_edit(): admin, or an explicitly
    authorized ResolutionEditor."""
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return ResolutionEditor.objects.filter(user=user, can_edit=True).exists()


def can_delete_resolution(user):
    """Mirrors resolution_delete(): admin-only, stricter than can_edit --
    an authorized ResolutionEditor could create/edit but never delete."""
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))
