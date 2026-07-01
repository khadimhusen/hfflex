from itemmaster.models import StdParameter
from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from order.models import Job


class Coa(models.Model):
    from production.models import DispatchRegister

    jobname = models.ForeignKey(Job, on_delete=models.PROTECT, related_name="coas")
    work_order = models.CharField(max_length=32, null=True, blank=True)
    delivery_challan = models.ForeignKey(DispatchRegister, on_delete=models.PROTECT,
                                         null=True, blank=True, related_name="coa")
    invoice_no = models.CharField(max_length=64, null=True, blank=True)
    qty = models.CharField(max_length=32)
    remark = models.TextField(max_length=1024, null=True, blank=True)

    # NEW FIELDS for yearly-reset numbering
    year = models.PositiveIntegerField(editable=False, db_index=True, null=True)
    serial = models.PositiveIntegerField(editable=False, null=True)

    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='coacreated')
    approvedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                   related_name='coaapproved')
    approve_date = models.DateTimeField(null=True, blank=True)
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='coaedited')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['year', 'serial'], name='unique_coa_year_serial'),
        ]

    def save(self, *args, **kwargs):
        if not self.pk:
            with transaction.atomic():
                current_year = timezone.now().year
                last = (
                    Coa.objects
                    .select_for_update()
                    .filter(year=current_year)
                    .order_by('-serial')
                    .first()
                )
                self.year = current_year
                self.serial = (last.serial + 1) if last else 1
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.coa_number} / {self.jobname.itemname}"

    @property
    def coa_number(self):
        return f"{self.year}/{self.serial}"

    @property
    def approver_name(self):
        if not self.approvedby:
            return "—"
        return self.approvedby.get_full_name() or self.approvedby.username

    @property
    def is_approved(self):
        return self.approvedby_id is not None
class TestParameter(models.Model):
    coa = models.ForeignKey(Coa, on_delete=models.PROTECT, related_name="testparameter")
    standard_parameter = models.ForeignKey(StdParameter, on_delete=models.PROTECT, related_name="testparameter")
    result = models.CharField(max_length=32)

    def __str__(self):
        return str(self.coa.jobname)
