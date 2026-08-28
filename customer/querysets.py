from django.contrib.auth.models import User


def marketing_users():
    return User.objects.filter(
        department__department_name__iexact='marketing', is_active=True
    ).order_by('first_name', 'last_name')


def customer_department_users():
    """Users authorized for the Customer module — mirrors the old app's
    'sidecustomer' department gate (previously nav-visibility only)."""
    return User.objects.filter(
        department__department_name__iexact='sidecustomer', is_active=True
    )
