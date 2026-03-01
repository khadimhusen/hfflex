from django.db import models
from customer.models import Customer
from django.contrib.auth.models import User

# Create your models here.
from myproject.utils import num2words


class Bank(models.Model):
    account_name = models.CharField(max_length=64)
    bankname = models.CharField(max_length=64)
    account_number = models.CharField(max_length=32)
    ifsc = models.CharField(max_length=11)
    branch = models.CharField(max_length=32)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='bankcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='bankedited')

    def __str__(self):
        return self.account_name + "/" + self.account_number

    class Meta:
        unique_together = ["account_name", "bankname", "account_number"]


class Cheque(models.Model):
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE)
    number = models.IntegerField()
    party = models.CharField(max_length=64, null=True, blank=True)
    cheque_date = models.DateField(blank=True, null=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=16,
                              choices=[("Unissued", "Unissued"), ("Issued", "Issued"), ("Hold", "Hold"),
                                       ("Cleared", "Cleared"),
                                       ("Stop Payment", "Stop Payment"), ("Cancel", "Cancel")], default="Unissued")
    expected_date = models.DateField(blank=True, null=True)
    bill_number = models.CharField(max_length=16, blank=True, null=True)
    bill_date = models.DateField(blank=True, null=True)
    remark = models.CharField(max_length=256, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='chequecreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='chequeedited')
    lock_record = models.BooleanField(default=False)

    class Meta:
        unique_together = ["bank", "number"]
        ordering=["expected_date"]


    def save(self,*args,**kwargs):
        if not self.expected_date and self.cheque_date:
            self.expected_date=self.cheque_date
        super(Cheque, self).save(*args, **kwargs)

    @property
    def amountinword(self):
        rupees = int(self.amount or 0)
        paise = int(((self.amount or 0) - int(self.amount or 0)) * 100)

        if rupees and paise:
            result = num2words(rupees) + " Rupees & " + num2words(paise) + " Paise Only"
        elif rupees:
            result = num2words(rupees) + " Rupees Only"
        elif paise == 1:
            result = num2words(paise) + " Paisa Only"
        elif paise:
            result = num2words(paise) + " Paise Only"
        else:
            result = " "
        return result

    @property
    def amountint(self):
        rupees = int(self.amount or 0)
        paise = int(((self.amount or 0) - int(self.amount or 0)) * 100)

        if not paise:
            result = rupees
        else:
            result = self.amount
        return result
