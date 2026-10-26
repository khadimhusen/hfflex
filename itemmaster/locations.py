from django.db.models import Q

from customer.models import Customer


def cylinder_locations_for(itemmaster):
    """Where a cylinder of `itemmaster` may be put: our own storage places (the
    active customers ticked "Cylinder location" -- GODOWN-1, PRODUCTION, any
    godown added later) or the item's own customer. Storage places first."""
    return Customer.objects.filter(
        Q(is_cylinder_location=True, active=True) | Q(pk=itemmaster.itemcustomer_id)
    ).order_by('-is_cylinder_location', 'name')
