from django.db import models
from django.db.models import Sum

from customer.models import Customer, Address
from django.contrib.auth.models import User
from material.models import Unit
from datetime import datetime

from purchase.choices import material_category
from returnable.choices import returnablechoice, okstatus


class Returnable(models.Model):
    party_name = models.ForeignKey(Customer, related_name='returnable', on_delete=models.PROTECT)
    dispatch_date = models.DateTimeField()
    expected_date = models.DateTimeField()
    address = models.ForeignKey(Address, related_name='partyaddress', on_delete=models.PROTECT)
    receivedby = models.CharField(max_length=64, null=True, blank=True)
    contact = models.CharField(max_length=64, null=True, blank=True)
    recieptnumber = models.CharField(max_length=64, null=True, blank=True)
    transportby = models.CharField(max_length=64, null=True, blank=True)
    person = models.CharField(max_length=64, null=True, blank=True)
    vehicle = models.CharField(max_length=64, null=True, blank=True)
    remark = models.TextField(max_length=512, default="-")
    status = models.CharField(choices=returnablechoice, max_length=32,default="Dispatched")
    lock = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, null=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='returnablecreated')
    edited = models.DateTimeField(auto_now=True, null=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='returnableedited')

    def __str__(self):
        return self.party_name.name + str(self.id)

    @property
    def totalamount(self):
        result = self.challanitem.aggregate(Sum('approxvalue'))
        return result["approxvalue__sum"] or 0

    @property
    def totalqty(self):
        result = self.challanitem.aggregate(Sum('qty'))
        return result["qty__sum"] or 0

    @property
    def total_rec_qty(self):
        total = 0
        for item in self.challanitem.all():
            total += item.receivedqty
        return total

    @property
    def totalpendingqty(self):
        result = self.challanitem.aggregate(Sum('qty'))
        total_qty = result["qty__sum"] or 0
        return total_qty - self.total_rec_qty



class ChallanItem(models.Model):
    returnable = models.ForeignKey(Returnable,related_name='challanitem', on_delete=models.PROTECT)
    itemname = models.CharField(max_length=128,null=True,blank=True)
    description = models.TextField(max_length=1024, blank=True, null=True)
    category = models.CharField(max_length=16, choices=material_category, null=True, blank=True)
    qty = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="challanitem")
    approxvalue = models.DecimalField(max_digits=10, decimal_places=3, default=0.0)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='challancreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='challanedited')

    def __str__(self):
        return self.itemname + str(self.returnable)

    @property
    def pendingqty(self):
        result = self.receiveditem.aggregate(Sum('qty'))
        return self.qty- (result["qty__sum"] or 0)

    @property
    def receivedqty(self):
        result = self.receiveditem.aggregate(Sum('qty'))
        return result["qty__sum"] or 0


class ReceivedChallan(models.Model):
    party_name = models.ForeignKey(Customer, related_name='receivedchallan', on_delete=models.PROTECT)
    received_date = models.DateTimeField()
    transport = models.CharField(max_length=64)
    recieptnumber = models.CharField(max_length=64, null=True, blank=True)
    remark = models.CharField(max_length=255, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='receivedchallancreated')
    edited = models.DateTimeField(auto_now=True, null=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='receivedchallanedited')


class ReceivedItem(models.Model):
    received_challan= models.ForeignKey(ReceivedChallan,related_name="receiveditem", on_delete=models.PROTECT)
    received_item = models.ForeignKey(ChallanItem,related_name="receiveditem", on_delete=models.PROTECT)
    qty = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="receiveditem")
    status = models.CharField(max_length=32, choices=okstatus, default="Ok")
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='receiveditemcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='receiveditemedited')
