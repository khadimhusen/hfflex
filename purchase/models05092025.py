from math import floor
from django.db import models
from myproject.utils import num2words
from customer.models import Customer, Address
from .choices import pochoices, material_category
from django.contrib.auth.models import User
from material.models import Unit
from datetime import datetime


class Term(models.Model):
    term = models.CharField(max_length=512, unique=True)
    bydefault = models.BooleanField(default=False)

    def __str__(self):
        return self.term


def allterm():
    return Term.objects.filter(bydefault=True)


class PoManager(models.Manager):
    def get_queryset(self):
        return super(PoManager, self).get_queryset().select_related()


class Po(models.Model):
    supplier = models.ForeignKey(Customer, related_name='po', on_delete=models.PROTECT)
    delivery_date = models.DateTimeField(blank=True, null=True, )
    payment_terms = models.IntegerField(null=True, blank=True, default=30)
    tax1 = models.DecimalField(max_digits=10, decimal_places=3, default=9)
    tax2 = models.DecimalField(max_digits=10, decimal_places=3, default=9)
    transport = models.CharField(max_length=64, blank=True)
    remark = models.CharField(max_length=512, null=True, blank=True, default="-")
    delivery_at = models.ForeignKey(Address, related_name='po', on_delete=models.PROTECT,
                                    null=True, blank=True, default=146)
    poterm = models.ManyToManyField(Term, related_name='poterms', default=allterm, blank=True)
    status = models.CharField(max_length=16, choices=pochoices, default="Pending", null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='pocreated')
    approvedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                   related_name='poapproved')
    approve_date = models.DateTimeField(null=True, blank=True)
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='poedited')

    objects = PoManager()

    def __str__(self):
        return f"#PO/{self.id}/{self.supplier}"

    def save(self, *args, **kwargs):
        if self.id:

            print("self.id", self.id)
            super(Po,self).save(*args, **kwargs)
        else:

            super(Po,self).save(*args, **kwargs)
            ExpectedDate.objects.create(
                po=self,
                expected_date=self.delivery_date,
                createdby=self.createdby)




    @property
    def totalqty(self):
        poitems = self.poitem.all()
        result = 0
        for poitem in poitems:
            result += poitem.qty
        return round(result, 2)

    @property
    def totalrecqty(self):
        poitems = self.poitem.all()
        result = 0
        for poitem in poitems:
            result += (poitem.rec_qty or 0)
        return round(result, 2)

    @property
    def totalpendingqty(self):
        poitems = self.poitem.all()
        result = 0
        for poitem in poitems:
            result += (poitem.pendingqty or 0)
        return round(result, 2)

    @property
    def pototal(self):
        poitems = self.poitem.all()
        result = 0
        for poitem in poitems:
            result += round(poitem.qty * poitem.rate, 2)
        return round(result, 2)

    @property
    def cgst(self):
        return round(self.pototal * self.tax1 / 100, 2)

    @property
    def sgst(self):
        return round(self.pototal * self.tax2 / 100, 2)

    @property
    def grosstotal(self):
        return round(self.pototal + self.sgst + self.cgst, 2)

    @property
    def inword(self):
        rupees = int(self.grosstotal)
        paise = int((self.grosstotal - int(self.grosstotal)) * 100)
        print("rupees", rupees, "paise", paise)

        if rupees and paise:
            result = "Rupees " + num2words(rupees) + " & " + num2words(paise) + " Paise Only"
        elif rupees:
            result = "Rupees " + num2words(rupees) + " Only"
        elif paise == 1:
            result = num2words(paise) + " Paisa Only"
        elif paise:
            result = num2words(paise) + " Paise Only"
        else:
            result = " "

        return result

    @property
    def delayed(self):
        return datetime.now() > self.delivery_date and (self.status == "Pending" or self.status == "Incomplete")

    class Meta:
        ordering = ['-id']


class PoItem(models.Model):
    purchaseorder = models.ForeignKey(Po, on_delete=models.PROTECT, related_name="poitem")
    description = models.TextField(max_length=1024)
    category = models.CharField(max_length=16, choices=material_category, null=True, blank=True)
    qty = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="poitem")
    rate = models.DecimalField(max_digits=10, decimal_places=3)
    rec_qty = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='poitemcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='poitemedited')

    def __str__(self):
        return self.description

    @property
    def total(self):
        return round(self.qty * self.rate, 2)

    @property
    def pendingqty(self):
        return self.qty - (self.rec_qty or 0)


class PoImage(models.Model):
    po = models.ForeignKey(Po, related_name="poimage", on_delete=models.PROTECT)
    imagename = models.CharField(max_length=125)
    poimage = models.ImageField(upload_to='PoImage/')
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='poimagecreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='poimageedited')

    def __str__(self):
        return self.imagename + str(self.po)


class ExpectedDate(models.Model):
    po = models.ForeignKey(Po, related_name="itemexpecteddate", on_delete=models.PROTECT)
    expected_date = models.DateField()
    remark = models.CharField(max_length=256, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, on_delete=models.PROTECT,
                                  related_name='poitemexpecteddate')


    class Meta:
        ordering = ["id"]
