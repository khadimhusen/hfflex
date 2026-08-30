from django.contrib.auth.models import User


def manpower_department_users():
    """Users authorized for the ManPower module -- mirrors the old app's
    'sidemanpower' department gate (previously nav-visibility only)."""
    return User.objects.filter(
        department__department_name__iexact='sidemanpower', is_active=True
    )


def shift_approve_users():
    """Users who can approve a shift -- mirrors shiftdetail.html's
    user_in_department:"directors" gate, which was button-visibility only;
    the approveshift VIEW itself had no server-side check at all (not even
    @login_required). Enforced here for real."""
    return User.objects.filter(
        department__department_name__iexact='directors', is_active=True
    )


def can_approve_shift(user):
    if user.is_staff or user.is_superuser:
        return True
    return shift_approve_users().filter(id=user.id).exists()
