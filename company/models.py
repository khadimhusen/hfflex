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
    def state_code(self):
        """GST state code, the first two digits of the GSTIN ('27' =
        Maharashtra). Will decide CGST+SGST versus IGST between two parties."""
        return self.gstin[:2]
