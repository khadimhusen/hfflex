from django.db import models
from django.contrib.auth.models import User
from datetime import date
from myproject.utils import num2words
from quotation.choices import quotation_status


class Term(models.Model):
    term = models.CharField(max_length=512, unique=True)
    bydefault = models.BooleanField(default=False)

    def __str__(self):
        return self.term


def defaultterm():
    return Term.objects.filter(bydefault=True)


class MaterialRate(models.Model):
    material = models.CharField(max_length=32)
    density = models.DecimalField(max_digits=6, decimal_places=3)
    rate = models.DecimalField(max_digits=6, decimal_places=2)
    solid = models.DecimalField(max_digits=6, decimal_places=2)
    state = models.CharField(max_length=8,choices=[("Film", "Film"), ("Liquid", "Liquid")], default="Film")
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='materialratecreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='materialrateedited')

    def __str__(self):
        return self.material


class Quotation(models.Model):
    partyname = models.CharField(max_length=128)
    add = models.TextField(max_length= 256)
    contact = models.CharField(max_length=16)
    quotedate = models.DateField(default=date.today)
    remark = models.CharField(max_length=256, null=True, blank=True)
    status= models.CharField(max_length=32 ,choices=quotation_status, default="Pending")
    design_rate = models.PositiveIntegerField(default=2000)
    no_of_design = models.PositiveSmallIntegerField(default=0)
    approvedby= models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='quotationapproved')
    cylinder_gst = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    material_gst = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    quote_term = models.ManyToManyField(Term, related_name='quoteterms', default=defaultterm, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    approved = models.DateTimeField(null=True,blank=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='quotationcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='quotationedited')
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ['-id']



    def __str__(self):
        return str(self.partyname) + " = " + str(self.quotedate) + " = (" + str(self.id) + ") "



    @property
    def designcost(self):
        if self.design_rate and self.no_of_design:
            return self.design_rate * self.no_of_design
        else:
            return 0

    @property
    def totalcylindercost(self):
        quoteitems=self.quotationitems.all()
        result = 0
        for item in quoteitems:
            result += round(item.item_cylinder_cost,0)
        return result
    @property
    def grosscylindercost(self):
        return (self.totalcylindercost * self.cylinder_gst / 100)+(self.totalcylindercost)
    @property
    def grossmaterialcost(self):
        return (self.totalmaterialcost * self.material_gst / 100)+(self.totalmaterialcost)
    @property
    def cylindergst(self):
        return self.totalcylindercost * self.cylinder_gst / 100
    @property
    def materialgst(self):
        return self.totalmaterialcost * self.material_gst / 100

    @property
    def totalmaterialcost(self):
        quoteitems = self.quotationitems.all()
        result = 0
        for item in quoteitems:
            result += round(item.itemtotalcost, 2)
        return result

    @property
    def totalquotationcost(self):
        return round(self.grosscylindercost + self.grossmaterialcost + self.designcost, 2)

    @property
    def amountinword(self):
        rupees = int(abs(self.totalquotationcost) or 0)
        paise = int((abs(self.totalquotationcost or 0) - int(abs(self.totalquotationcost) or 0)) * 100)


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


class QuotationItem(models.Model):
    quote = models.ForeignKey(Quotation, on_delete=models.PROTECT, related_name="quotationitems")
    jobname = models.CharField(max_length=128)
    dimension = models.CharField(max_length=128)
    supply = models.CharField(max_length=16,choices=[("Pouch", "Pouch"), ("Roll", "Roll"),("Fabric Bag","Fabric Bag")])
    structure = models.CharField(max_length=128)
    cyl_rate = models.DecimalField(max_digits=8, decimal_places=2)
    no_of_cyl = models.IntegerField()
    material_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    pouch_per_kg = models.IntegerField(null=True, blank=True)
    per_pouch_cost = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    moq = models.IntegerField()
    unit = models.CharField(max_length=8,choices=[("Kg", "Kg"), ("Nos.", "Nos.")])
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='quotationitemcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='quotationitemedited')


    class Meta:
        ordering = ['-id']


    @property
    def item_cylinder_cost(self):
        if self.cyl_rate and self.no_of_cyl:
            return self.cyl_rate * self.no_of_cyl
        else:
            return 0

    @property
    def itemtotalcost(self):
        if self.unit == "Kg":
            return (self.material_rate or 0) * (self.moq or 0)
        elif self.unit == "Nos.":
            return (self.per_pouch_cost or 0) * (self.moq or 0)
        else:
            return None

    def save(self, *args, **kwargs):
        if self.material_rate and self.pouch_per_kg and self.pouch_per_kg > 0:
            self.per_pouch_cost = round(self.material_rate / self.pouch_per_kg, 2)
        super(QuotationItem, self).save(*args, **kwargs)




class AdditionTerm(models.Model):
    quote = models.ForeignKey(Quotation, on_delete=models.PROTECT, related_name="additionalterms")
    term = models.CharField(max_length=256)


class NewRate(models.Model):
    material=models.ForeignKey(MaterialRate,on_delete=models.PROTECT)
    rate = models.DecimalField(max_digits=6, decimal_places=2)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='ratecreated')


    def __str__(self):
        return f'{self.material}- Rate:- {self.rate} - Date:- {self.created}'



    def save(self,*args,**kwargs):
        a=MaterialRate.objects.get(id=self.material.id)
        a.rate=self.rate
        a.save()
        super(NewRate,self).save(*args,**kwargs)


class PreDefinedMaterial(models.Model):
    structure=models.CharField(max_length=64)

    def __str__(self):
        return self.structure

class MaterialStructure(models.Model):
    predefined=models.ForeignKey(PreDefinedMaterial,related_name='materialstructure',
                                 on_delete=models.PROTECT)
    material=models.ForeignKey(MaterialRate,on_delete=models.PROTECT)
    micron=models.DecimalField(max_digits=5,decimal_places=2,blank=True,null=True)




