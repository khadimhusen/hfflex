from django.contrib.auth.models import User


def returnable_department_users():
    """Users authorized for the Returnable module -- mirrors the old app's
    'sidereturnable' department gate (previously nav-visibility only; the
    old app's own @accessview decorator was a permanent no-op, so this was
    never actually enforced server-side either)."""
    return User.objects.filter(
        department__department_name__iexact='sidereturnable', is_active=True,
    )
