from django.contrib.auth.models import User

def crm_users():
    return User.objects.filter(department__department_name__iexact='crm_user', is_active=True)


def all_lead_access_users():
    """Users in the can_see_edit_all_lead department -- same department-name
    gate the rest of the app uses (see manpower.querysets, order's
    user_in_department tag)."""
    return User.objects.filter(
        department__department_name__iexact='can_see_edit_all_lead', is_active=True,
    )


def can_see_all_leads(user):
    """Whether a user works every lead rather than only the ones they own.

    LeadViewSet has no separate per-object edit check -- get_queryset() is
    the only gate -- so this grants viewing, editing AND converting
    together, which is the point: these users act as lead converters for
    leads owned by other people.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return all_lead_access_users().filter(id=user.id).exists()
