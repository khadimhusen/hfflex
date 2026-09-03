from django.db import models
from django.contrib.auth.models import User
from material.models import PurchaseMaterial


class Customer(models.Model):
    name = models.CharField(max_length=128, unique=True)
    gst = models.CharField(max_length=17, unique=True, blank=True, null=True)
    is_customer = models.BooleanField(default=True)
    is_supplier = models.BooleanField(default=False)
    email = models.EmailField(null=True, blank=True)
    marketing_person = models.ForeignKey(User,related_name='customers',on_delete=models.PROTECT, null=True,
                                         limit_choices_to={'department__department_name': 'marketing',
                                                           'is_active':True})
    # credit_period = models.PositiveSmallIntegerField(blank=True, null=True)
    # credit_cap = models.PositiveIntegerField(blank=True, null=True)
    # outstanding = models.PositiveIntegerField(default=0)
    supplier_item=models.ManyToManyField(PurchaseMaterial, related_name="supplier_items")
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='customercreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='customeredited')

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        self.name = self.name.upper()
        super(Customer, self).save(*args, **kwargs)
        if self.active == False:
            self.itemmasters.all().update(active=False)


    # @property
    # def can_order(self):
    #     return self.credit_cap == 0


class Pincode(models.Model):
    """India Post pincode -> lat/lng lookup, loaded once from
    customer/data/india_pincodes.csv via `manage.py load_pincodes` (see
    that command's docstring for the source and how the file was built).
    Not a FK target for Address.pincode -- joined by the plain 6-digit
    value so existing Address rows need no backfill/migration of their
    own. Powers CustomerViewSet.nearby (find customers near a pincode)."""
    code = models.PositiveIntegerField(unique=True, db_index=True)
    place_name = models.CharField(max_length=64, blank=True)
    district = models.CharField(max_length=64, blank=True)
    state = models.CharField(max_length=64, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    def __str__(self):
        return f'{self.code} - {self.place_name}, {self.district}'


class Address(models.Model):
    customer = models.ForeignKey(Customer, related_name='addresses', on_delete=models.PROTECT)
    addname = models.CharField(max_length=32)
    add1 = models.CharField(max_length=128, blank=True)
    add2 = models.CharField(max_length=128, blank=True)
    pincode = models.IntegerField(blank=True, null=True)
    phone = models.CharField(max_length=16, blank=True)
    remark = models.CharField(max_length=26, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='addresscreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='addressedited')

    def __str__(self):
        return f'{self.customer}-{self.addname} - {self.add1} - {self.add2}'

    class Meta:
        ordering = ['customer']


class Person(models.Model):
    customer = models.ForeignKey(Customer, related_name='persons', on_delete=models.PROTECT)
    name = models.CharField(max_length=64)
    designation = models.CharField(max_length=32)
    mobile = models.CharField(max_length=16, blank=True)
    email = models.EmailField(max_length=256, blank=True)
    remark = models.CharField(max_length=26, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='personcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='personedited')

    def __str__(self):
        return f'{self.name} - {self.customer}'

    class Meta:
        ordering = ['customer']
