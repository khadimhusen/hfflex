from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

# 2-digit state code + 10-character PAN + entity number + 'Z' + check character.
gstin_validator = RegexValidator(
    regex=r'^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$',
    message='Enter a valid 15-character GSTIN, e.g. 27AADCH3462K1ZF.',
)


# H F Flex's own record in the customer table (what Po.ship_to defaulted to).
LEGACY_CUSTOMER_NAME = 'H F FLEX PRIVATE LIMITED'


class Company(models.Model):
    """One of our own legal entities (H F Flex, H F Printpack, ...) -- what a
    document's letterhead, GSTIN and sign-off should say.

    Not a Customer: customers are the parties we trade with. A company is us,
    and documents will point at one by role -- a purchase order's buyer, a
    delivery challan's issuing company, later a production order's company.
    Nothing refers to this table yet; it is the first step.
    """
    name = models.CharField(max_length=128, unique=True,
                            help_text='As printed on documents, e.g. H F FLEX PVT. LTD.')
    short_name = models.CharField(max_length=16, unique=True,
                                  help_text='Short code, e.g. HF or HP -- for prefixes and filters.')
    gstin = models.CharField(max_length=15, blank=True, validators=[gstin_validator], verbose_name='GSTIN')
    address_line1 = models.CharField(max_length=128, blank=True)
    address_line2 = models.CharField(max_length=128, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    website = models.CharField(max_length=128, blank=True)
    logo = models.ImageField(upload_to='company/', blank=True, null=True, max_length=256)
    customer = models.ForeignKey(
        'customer.Customer', null=True, blank=True, on_delete=models.PROTECT, related_name='company_records',
        help_text='The customer record that stands for this company -- where goods bought by it are '
                  'delivered. Its addresses are the delivery addresses offered on its purchase orders.')
    is_default = models.BooleanField(
        default=False,
        help_text='Used wherever a document does not say which company. Only one company can be the default.')
    is_active = models.BooleanField(default=True, help_text='Untick to stop offering it on new documents.')
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='companycreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='companyedited')

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'companies'
        constraints = [
            # At most one default: a partial unique index over just the
            # default rows, so any number of non-default companies can exist.
            models.UniqueConstraint(fields=['is_default'], condition=Q(is_default=True),
                                    name='company_single_default'),
        ]

    def __str__(self):
        return self.name

    def clean_fields(self, exclude=None):
        # Tidy the GSTIN *before* the format check (which runs inside this),
        # so "27aadch3462k1zf " from the admin is accepted rather than refused.
        self.gstin = (self.gstin or '').strip().upper()
        super().clean_fields(exclude=exclude)

    def clean(self):
        if self.is_default and not self.is_active:
            raise ValidationError('The default company has to be active.')

    def save(self, *args, **kwargs):
        # Same tidy-up for code that saves without going through a form.
        self.gstin = (self.gstin or '').strip().upper()
        super().save(*args, **kwargs)

    @property
    def receiving_customer(self):
        """The customer record goods bought by this company are delivered to.

        The linked customer, or -- for H F Flex only, which was wired to its
        customer record before companies existed -- that record found by name.
        None for any other company that has not been linked yet.
        """
        if self.customer_id:
            return self.customer
        from .defaults import HF_FLEX
        if self.gstin == HF_FLEX['gstin']:
            from customer.models import Customer
            return Customer.objects.filter(name=LEGACY_CUSTOMER_NAME).first()
        return None

    def delivery_addresses(self):
        """Addresses of the receiving customer, for a purchase order's delivery address."""
        from customer.models import Address
        customer = self.receiving_customer
        if customer is None:
            return Address.objects.none()
        return Address.objects.filter(customer=customer).order_by('addname', 'id')

    @property
    def state_code(self):
        """GST state code, the first two digits of the GSTIN ('27' =
        Maharashtra). Will decide CGST+SGST versus IGST between two parties."""
        return self.gstin[:2]


def default_company():
    """The company used where a document does not say which one: the active
    company flagged is_default, or None if there isn't one."""
    return Company.objects.filter(is_default=True, is_active=True).first()


def company_for_customer(customer):
    """Our company that `customer` is the record of, or None if it is an
    ordinary customer/supplier. H F Flex's record counts even before it is
    linked in the admin."""
    if customer is None:
        return None
    from .defaults import HF_FLEX
    company = Company.objects.filter(customer_id=customer.pk).first()
    if company is None and customer.name == LEGACY_CUSTOMER_NAME:
        company = Company.objects.filter(gstin=HF_FLEX['gstin']).first()
    return company


def default_company_id():
    """default_company().pk, for use as a model field's callable default."""
    return Company.objects.filter(is_default=True, is_active=True).values_list('pk', flat=True).first()
