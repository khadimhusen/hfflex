from django.contrib.auth.models import User


def purchase_department_users():
    """Users authorized for the Purchase module — mirrors the old app's
    'sidepurchase' department gate (previously nav-visibility only)."""
    return User.objects.filter(
        department__department_name__iexact='sidepurchase', is_active=True
    )


def purchase_see_all_users():
    """Users who can see every PO, not just their own — mirrors the old
    purchaselist view's 'can_see_all_po' department check."""
    return User.objects.filter(
        department__department_name__iexact='can_see_all_po', is_active=True
    )


def purchase_price_users():
    """Users who can view/set PoItem.rate and the PO's money totals —
    mirrors the old purchaseedit view's 'can_add_price' department check
    (everyone else got the PoItemFormMarketing variant, which excluded
    'rate' from the form entirely)."""
    return User.objects.filter(
        department__department_name__iexact='can_add_price', is_active=True
    )


def purchase_approve_users():
    """Users who can approve/unapprove a PO — mirrors the old detail
    template's 'can_approve_po' department gate, which was nav/button-
    visibility only; the approve and remove-approval VIEWS themselves had
    no server-side check at all. Enforced here for real."""
    return User.objects.filter(
        department__department_name__iexact='can_approve_po', is_active=True
    )


def can_see_all_po(user):
    if user.is_staff or user.is_superuser:
        return True
    return purchase_see_all_users().filter(id=user.id).exists()


def can_add_price(user):
    if user.is_staff or user.is_superuser:
        return True
    return purchase_price_users().filter(id=user.id).exists()


def can_approve_po(user):
    if user.is_staff or user.is_superuser:
        return True
    return purchase_approve_users().filter(id=user.id).exists()


def can_edit_po(user, po):
    """Same rule the viewsets' get_queryset() scoping already enforces for
    GET/PATCH/DELETE (can_see_all_po, or the PO's own creator) — needed
    explicitly for POST too, since a fresh PoItem/PoImage/ExpectedDate
    create never goes through get_object()/get_queryset() at all, so
    without this a limited user could add items/images/follow-up dates to
    a PO they don't own just by guessing its id."""
    if can_see_all_po(user):
        return True
    return po.createdby_id == user.id
