from django.contrib.auth.models import User


def report_department_users():
    """'sidereport' department — Production Report section, previously
    nav-visibility only."""
    return User.objects.filter(department__department_name__iexact='sidereport', is_active=True)


def dispatch_department_users():
    """'sidedispatch' department — Dispatch section."""
    return User.objects.filter(department__department_name__iexact='sidedispatch', is_active=True)


def stock_department_users():
    """'sidestock' department — Inward + Stock section."""
    return User.objects.filter(department__department_name__iexact='sidestock', is_active=True)


def supervisor_users():
    """'supervisor' department — ProdReportForm scopes its supervisor field
    to this exact queryset."""
    return User.objects.filter(department__department_name__iexact='supervisor', is_active=True)
