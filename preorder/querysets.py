from django.contrib.auth.models import User


def preorder_department_users():
    """Users authorized for the Preorder module — mirrors the old app's
    'sidepreorder' department gate (previously nav-visibility only)."""
    return User.objects.filter(
        department__department_name__iexact='sidepreorder', is_active=True
    )


def can_edit_preorder(user, preorder):
    """Mirrors the old preorderlist template's edit-link logic: staff could
    always edit; everyone else only their own, and only before final
    submission locks it. The old template hardcoded a specific username
    ('khadimhusen') as the always-allowed case — replaced here with
    is_staff, which that account already has, rather than carrying a
    literal username into new code."""
    if user.is_staff or user.is_superuser:
        return True
    return preorder.createdby_id == user.id and not preorder.final_submition
