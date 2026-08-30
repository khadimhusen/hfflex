from django.contrib.auth.models import User


def can_create_coa_users():
    """Mirrors the old app's 'can_create_coa' department gate on the
    Job detail page's "Add COA" link."""
    return User.objects.filter(
        department__department_name__iexact='can_create_coa', is_active=True,
    )


def can_approve_coa_users():
    """Mirrors the old app's 'can_approve_coa' department gate on the
    COA detail page's Approve button."""
    return User.objects.filter(
        department__department_name__iexact='can_approve_coa', is_active=True,
    )
