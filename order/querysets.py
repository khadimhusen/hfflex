from django.contrib.auth.models import User


def order_department_users():
    """Users authorized for the Order/Job module — mirrors the old app's
    'sideorder' and 'sidejob' department gates (previously nav-visibility
    only; accessview itself was always a no-op, so any authenticated user
    could actually reach every view in this app regardless of department)."""
    return User.objects.filter(
        department__department_name__in=['sideorder', 'sidejob'], is_active=True
    ).distinct()


def order_directors():
    """'directors' department — the old app's real authority here: can
    cancel a job (jobdcancel), and can edit ANY order regardless of who
    created it (orderdetailedit)."""
    return User.objects.filter(department__department_name__iexact='directors', is_active=True)


def can_edit_order(user, order):
    """Mirrors orderdetailedit's exact check: creator, or a director."""
    if user.is_staff or user.is_superuser:
        return True
    if order.createdby_id == user.id:
        return True
    return order_directors().filter(id=user.id).exists()


def can_cancel_job(user):
    """Mirrors jobdcancel's exact check: directors only — notably NOT even
    the job's own creator."""
    if user.is_staff or user.is_superuser:
        return True
    return order_directors().filter(id=user.id).exists()
