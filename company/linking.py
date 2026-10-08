from django.db import transaction

from customer.models import Address, Customer


def find_customer(company):
    """The existing customer record that is this company: matched by GSTIN,
    then by name (H F Flex's legacy record included). None if there is none."""
    customer = None
    if company.gstin:
        customer = Customer.objects.filter(gst=company.gstin).first()
    return (customer or Customer.objects.filter(name=company.name.upper()).first()
            or company.receiving_customer)


def link_customer(company, create=False):
    """Point `company.customer` at its customer record, creating the record
    (with the company's address as its delivery address) when `create` and
    none exists. Returns the customer, or None if nothing was linked."""
    if company.customer_id:
        return company.customer
    with transaction.atomic():
        customer = find_customer(company)
        if customer is None and create:
            customer = Customer.objects.create(
                name=company.name, gst=company.gstin or None, email=company.email or None,
                is_customer=False, is_supplier=False)
            if company.address_line1 or company.address_line2:
                Address.objects.create(customer=customer, addname='Factory',
                                       add1=company.address_line1, add2=company.address_line2,
                                       phone=company.phone[:16])
        if customer is not None:
            company.customer = customer
            company.save(update_fields=['customer', 'edited'])
        return customer
