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


def can_delete_job_subresource(user, job):
    """Mirrors jobdetailedit's exact check for its inline formsets:
    can_delete = request.user == job.joborder.createdby — adding/editing a
    material/process/color/image/attribute/COA row on a job is open to any
    IsOrderUser (matches jobdetailedit having no ownership check at all for
    saves), but DELETING one is restricted to the parent order's creator."""
    if user.is_staff or user.is_superuser:
        return True
    return job.joborder.createdby_id == user.id


def can_delete_material_allotment(user):
    """Mirrors jobmaterialstatusedit's exact check:
    can_delete = request.user.username in ("khadimhusen", "admin") — unlike
    every other job sub-resource, this is NOT open to the order's creator,
    only to those two hardcoded admin accounts. Both happen to be the
    system's only superusers, so user.is_superuser replicates it exactly
    (and, unlike hardcoding usernames, still works if a new superuser is
    ever added)."""
    return user.is_superuser


def account_clearance_users():
    """'accountclearance' department — the old jobdetail page's real
    authority for the "Approval for production" action (only shown, per
    the old template, to this department when a job is sitting in
    Account clearance status)."""
    return User.objects.filter(department__department_name__iexact='accountclearance', is_active=True)


def can_approve_account_clearance(user):
    if user.is_staff or user.is_superuser:
        return True
    return account_clearance_users().filter(id=user.id).exists()
