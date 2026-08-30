from django.contrib.auth.models import User


def bank_department_users():
    """Users authorized for the Bank module -- mirrors the old app's
    'sidebank' department gate (previously nav-visibility only)."""
    return User.objects.filter(
        department__department_name__iexact='sidebank', is_active=True
    )
