from django.contrib.auth.models import User


def itemmaster_department_users():
    """Users authorized for the Itemmaster module — mirrors the old app's
    'sideitemmaster' department gate (previously nav-visibility only)."""
    return User.objects.filter(
        department__department_name__iexact='sideitemmaster', is_active=True
    )


def itemmaster_editors():
    """Users who can edit ANY itemmaster (not just their own) — mirrors the
    old app's 'can_edit_all_itemmaster' department check in
    itemmasterdetailedit."""
    return User.objects.filter(
        department__department_name__iexact='can_edit_all_itemmaster', is_active=True
    )


def can_edit_itemmaster(user, itemmaster):
    """Same rule the old itemmasterdetailedit view enforced for the whole
    edit page (and therefore every sub-formset on it — raw materials,
    processes, colors, attributes, images, COA parameters all lived behind
    this one check): staff, 'can_edit_all_itemmaster' department, or the
    itemmaster's own creator."""
    if user.is_staff or user.is_superuser:
        return True
    if itemmaster.createdby_id == user.id:
        return True
    return itemmaster_editors().filter(id=user.id).exists()
