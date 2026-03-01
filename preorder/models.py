from django.contrib.auth.models import User
from django.db import models

from material.models import Unit


class PreOrder(models.Model):
    customer = models.CharField(max_length=128)
    address = models.TextField()
    gst=models.CharField(max_length=15)
    contact_number = models.CharField(max_length=32)
    schedule = models.DateField()
    final_submition=models.BooleanField(default=False)
    is_locked=models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='preordercreated_by')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='preordereditedby')

    def __str__(self):
        return str(self.id)+ " - " + self.customer

    @property
    def done(self):
        if JobName.objects.filter(preorder=self, job__isnull=False).count()>0:
            return True
        else:
            return False

    class Meta:
        ordering = ["-id"]


class JobName(models.Model):
    preorder=models.ForeignKey(PreOrder,on_delete=models.PROTECT, related_name="jobname")
    jobname=models.CharField(max_length=128)
    qty=models.PositiveIntegerField()
    unit=models.ForeignKey(Unit, on_delete=models.PROTECT)
    new_cyl_qty=models.PositiveSmallIntegerField()
    cyl_invoice=models.CharField(max_length=32, blank=True,null=True)
    cyl_cost=models.DecimalField(max_digits=7, decimal_places=2)
    design_charges=models.DecimalField(max_digits=7,decimal_places=2)
    rate=models.DecimalField(max_digits=6, decimal_places=2)
    preimg = models.ImageField(upload_to='preimg/', blank=True,null=True)
    prefile = models.FileField(upload_to='prefile/', blank=True,null=True)
    remark=models.CharField(max_length=256,null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='jobnamecreated_by')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='jobnameeditedby')

    def __str__(self):
        return str(self.preorder) + " - " + self.jobname + "| Qty.=" + str(self.qty) + " " + str(self.unit) + "| Rate = Rs." + str(self.rate)