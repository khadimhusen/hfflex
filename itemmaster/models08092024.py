from django.db import models
from django.db.models import Sum
from material.models import Material, MatType, Grade, Unit, Commodity
from customer.models import Customer
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator


class Machine(models.Model):
    machinename = models.CharField(max_length=32)
    est_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.machinename


class PouchType(models.Model):
    pouchtype = models.CharField(max_length=128, unique=True, blank=False)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='pouchtypecreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='pouchtypeedited')

    def __str__(self):
        return self.pouchtype


class LamiRubber(models.Model):
    rubber = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, choices=[("Ok", "Ok"), ("NotOk", "NotOk")], default="Ok")
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='lamirubbercreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='lamirubberedited')

    def __str__(self):
        return str(self.rubber) + " mm" + " - " + str(self.status) + " ( id=" + str(self.id) + " )"

    class Meta:
        ordering = ["-rubber"]


class ItemMasterManager(models.Manager):
    def get_queryset(self):
        return super(ItemMasterManager, self).get_queryset().select_related()


class ItemMaster(models.Model):
    SUPPLY_CHOICES = [('ROLL', 'ROLL'), ('POUCH', 'POUCH'), ('AS PER JOB', 'AS PER JOB')]

    DIRECTION = [('ANY', 'ANY'), ('READABLE', 'READABLE'), ('UNREADABLE', 'UNREADABLE')]

    CYLINDER = [('Available', 'Available'), ('for design', 'for design'),
                ('Art work Pending From cylinder Mfg', 'Art work Pending From cylinder Mfg'),
                ('Correction Pending From Cylinder Mfg', 'Correction Pending From Cylinder Mfg'),
                ('for design approval', 'for design approval'),
                ('for dispatch', 'for dispatch'), ('in Transist', 'in Transist'), ('Not Applicable', 'Not Applicable'),
                ('Sent For Repairing', 'Sent For Repairing'), ('Returned To Customer', 'Returned To Customer')]

    itemname = models.CharField(max_length=256)
    itemcode = models.CharField(max_length=8, null=True, blank=True)
    itemcustomer = models.ForeignKey(Customer, related_name='itemmasters', on_delete=models.PROTECT)
    barcode = models.CharField(max_length=32, blank=True)
    packsize = models.CharField(max_length=16, default="-")
    replength = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    openwidth = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    slit_size = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    no_of_repeat = models.DecimalField(max_digits=5, decimal_places=1, blank=True, default=0)
    no_of_ups = models.DecimalField(max_digits=5, decimal_places=1, blank=True, default=0)
    cyl_length = models.DecimalField(max_digits=4, decimal_places=0, blank=True, null=True, default=0)
    cyl_circum = models.DecimalField(max_digits=10, decimal_places=1, blank=True,
                                     null=True, default=0, validators=[MaxValueValidator(1300), MinValueValidator(360)])
    cylinder_status = models.CharField(max_length=126, choices=CYLINDER, default="Not Applicable", blank=True,
                                       null=True)
    printing = models.CharField(max_length=32, choices=[('Surface', 'Surface'),
                                                        ('Reverse', 'Reverse'),
                                                        ('Unprinted', 'Unprinted')], default="Reverse")
    total_gsm = models.DecimalField(max_digits=7, decimal_places=3, blank=True, null=True)
    pouch_weight = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    pouch_per_kg = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    pouch_type = models.ForeignKey(PouchType, related_name='itemmaster', on_delete=models.PROTECT, blank=True,
                                   null=True)
    supply_form = models.CharField(max_length=16, choices=SUPPLY_CHOICES, default="ROLL")
    film_size = models.IntegerField(default=0)
    remark = models.TextField(null=True, blank=True)
    unwind_direction = models.CharField(max_length=32, choices=DIRECTION, default="ANY")
    lami_rubber = models.ForeignKey(LamiRubber, related_name='itemmaster', on_delete=models.PROTECT,
                                    blank=True, null=True)
    active = models.BooleanField(default=True)
    shade_accuracy = models.CharField(max_length=8,
                                      choices=[("Excact", "Excact"), ("Fair", "Fair"), ("Approx", "Approx")],
                                      default="Fair")
    commodity = models.ForeignKey(Commodity, related_name='itemmaster', on_delete=models.PROTECT, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='itemmastercreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='itemmasteredited')

    objects = ItemMasterManager()

    class Meta:
        unique_together = ("itemname", "itemcustomer")
        ordering = ["-id"]

    def __str__(self):
        return f"{self.itemname} - {self.itemcustomer}-{self.id}"

    def save(self, *args, **kwargs):
        self.itemname = self.itemname.upper()
        self.total_gsm = round((self.gsm or 0), 3)
        self.pouch_weight = round((self.total_gsm or 0) * (self.openwidth or 0) * (self.replength or 0) / 1000000, 2)
        if self.pouch_weight == 0 or self.pouch_weight == None:
            self.pouch_per_kg = 0
        else:
            self.pouch_per_kg = round(1000 / self.pouch_weight, 2)
        super(ItemMaster, self).save(*args, **kwargs)

    @property
    def micron(self):
        result = RawMaterial.objects.filter(itemmaster=self).aggregate(Sum('micron'))
        return result['micron__sum']

    @property
    def gsm(self):
        result = RawMaterial.objects.filter(itemmaster=self).aggregate(Sum('gsm'))
        return result['gsm__sum']

    @property
    def ply(self):
        newresult = RawMaterial.objects.filter(itemmaster=self, materialname__state='Film').count()
        return newresult

    @property
    def isnew(self):
        totaljobs = self.jobitem.count()
        if totaljobs == 0:
            return "No Jobs"
        elif totaljobs == 1:
            return "Once"
        else:
            return "RepeatJobs"


class ItemImage(models.Model):
    imagename = models.ImageField(upload_to='itemmaster/', blank=True)
    itemname = models.ForeignKey(ItemMaster, related_name='itemimage', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='itemimagecreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='itemimageedited')

    def __str__(self):
        return str(self.id)


class RawMaterial(models.Model):
    itemmaster = models.ForeignKey(ItemMaster, related_name='rawmaterial', on_delete=models.PROTECT)
    materialname = models.ForeignKey(Material, related_name='rawmaterial', on_delete=models.PROTECT)
    item_mat_type = models.ForeignKey(MatType, related_name='rawmaterial', on_delete=models.PROTECT, default=1)
    item_grade = models.ForeignKey(Grade, related_name='rawmaterial', on_delete=models.PROTECT, default=1)
    size = models.IntegerField(null=True)
    micron = models.DecimalField(max_digits=7, decimal_places=3, blank=True, null=True)
    gsm = models.DecimalField(max_digits=7, decimal_places=3, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='rawmaterialcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='rawmaterialedited')

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.materialname}-{self.item_mat_type}-{self.item_grade} {self.size}mm X {self.micron}"

    def save(self, *args, **kwargs):
        if self.itemmaster.film_size != 0:
            self.gsm = round(self.materialname.density * self.micron * self.size / self.itemmaster.film_size, 3)
        super(RawMaterial, self).save(*args, **kwargs)

    @property
    def required(self):
        result = RawMaterial.objects.filter(itemmaster=self.itemmaster).aggregate(Sum('gsm'))
        return self.gsm / result['gsm__sum']


class Process(models.Model):
    process = models.CharField(max_length=32, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='processcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='processedited')

    def __str__(self):
        return self.process


class ItemProcess(models.Model):
    itemmaster = models.ForeignKey(ItemMaster, related_name='itemprocess', on_delete=models.PROTECT)
    process = models.ForeignKey(Process, related_name='itemprocess', on_delete=models.PROTECT)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    machine=models.ForeignKey(Machine,on_delete=models.PROTECT,null=True,blank=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='itemprocesscreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='itemprocessedited')

    def __str__(self):
        return str(self.itemmaster) + str(self.process)


class Color(models.Model):
    colorname = models.CharField(max_length=16, unique=True)
    pantonecolor = models.CharField(max_length=32, null=True, blank=True)
    hexcode = models.CharField(max_length=8, null=True, blank=True)

    def __str__(self):
        return f'{self.colorname} - {self.pantonecolor or ""} - {self.hexcode or ""} '


class ItemColor(models.Model):
    itemmaster = models.ForeignKey(ItemMaster, on_delete=models.PROTECT, related_name='itemcolors', null=True,
                                   blank=True)
    color = models.ForeignKey(Color, on_delete=models.PROTECT, related_name='itemcolors', null=True, blank=True)

    remark = models.CharField(max_length=128, null=True, blank=True)

    def __str__(self):
        return str(self.color)

    class Meta:
        ordering = ['id']


class Problem(models.Model):
    problem = models.CharField(max_length=256)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.problem


class AttributeMaster(models.Model):
    attribute=models.CharField(max_length=32)

    def __str__(self):
        return self.attribute

class ItemAttribute(models.Model):
    item_attirbuate=models.ForeignKey(AttributeMaster,on_delete=models.PROTECT,related_name="itemattribute")
    itemmaster=models.ForeignKey(ItemMaster,on_delete=models.PROTECT,related_name="itemattribute")
    attri_value = models.CharField(max_length=32)

    def __str__(self):
        return f'{self.item_attirbuate} = {self.attri_value}'
