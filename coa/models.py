from django.db import models
from django.contrib.auth.models import User
from order.models import Job
from itemmaster.models import StdParameter


class Coa(models.Model):
    from production.models import DispatchRegister

    jobname = models.ForeignKey(Job, on_delete=models.PROTECT, related_name="coas")
    work_order = models.CharField(max_length=32, null=True, blank=True)
    delivery_challan = models.ForeignKey(DispatchRegister, on_delete=models.PROTECT,
                                         null=True, blank=True, related_name="coa")
    invoice_no = models.CharField(max_length=64, null=True, blank=True)
    qty = models.CharField(max_length=32)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='coacreated')
    approvedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                   related_name='coaapproved')
    approve_date = models.DateTimeField(null=True, blank=True)
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='coaedited')

    def __str__(self):
        return str(self.id) + " / " + str(self.jobname.itemname)


class TestParameter(models.Model):
    coa = models.ForeignKey(Coa, on_delete=models.PROTECT, related_name="testparameter")
    standard_parameter = models.ForeignKey(StdParameter, on_delete=models.PROTECT, related_name="testparameter")
    result = models.CharField(max_length=32)

    def __str__(self):
        return str(self.coa.jobname)
