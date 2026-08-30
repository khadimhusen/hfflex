from django.contrib.auth.models import User


def documents_department_users():
    """Mirrors the old app's 'sidedocuments' department gate -- nav
    visibility only. The Documents module itself has no department-level
    access control (unlike purchase/bank/etc): any logged-in user can see
    documents.list, scoped per-document by Document.has_access()."""
    return User.objects.filter(
        department__department_name__iexact='sidedocuments', is_active=True
    )
