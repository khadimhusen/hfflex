from django.db import models
from material.models import Material, MatType, Grade, Unit
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from order.models import JobProcess, JobMaterial
from customer.models import Customer, Address
from itemmaster.models import Problem, Process
from django.db.models import Sum
from employee.models import Worker
from quality.models import QCTest



class StockdetailManager(models.Manager):
    def get_queryset(self):
        return super(StockdetailManager, self).get_queryset().select_related()


class Stockdetail(models.Model):
    materialname = models.ForeignKey(Material, related_name='stock', on_delete=models.PROTECT)
    item_mat_type = models.ForeignKey(MatType, related_name='stock', on_delete=models.PROTECT, default=1)
    item_grade = models.ForeignKey(Grade, related_name='stock', on_delete=models.PROTECT, default=1)
    size = models.IntegerField(null=True, blank=True)
    micron = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True)
    gsm = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True)
    rate = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    qc_status = models.CharField(max_length=16,
                                 choices=[("Ok", "Ok"), ("Hold", "Hold"), ("Rejected", "Rejected"),
                                          ("Nil", "Nil"), ("Finished", "Finished"),
                                          ("Dispatched","Dispatched")],
                                 default="Ok")
    remark = models.CharField(max_length=255, null=True, blank=True)
    gross_wt = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    tare_wt = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    recieved = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    available = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    nos = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    alloted = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    created = models.DateTimeField(auto_now_add=True, null=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='stockcreated')
    edited = models.DateTimeField(auto_now=True, null=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='stockedited')

    objects = StockdetailManager()

    def save(self, *args, **kwargs):

        if self.tare_wt is not None and self.gross_wt:
            self.recieved = round(self.gross_wt - self.tare_wt, 3)
        elif self.gross_wt and self.recieved:
            self.tare_wt = round(self.gross_wt - self.recieved, 3)

        self.balance = (self.recieved or 0) - (self.used or 0)
        self.alloted = (self.allo or 0)
        self.available = (self.recieved or 0) - (self.alloted or 0)

        if self.content_type.model=="inward":
            if self.available == 0 and self.balance==0 :
                self.qc_status = "Nil"
            if self.balance!=0 and self.qc_status=="Nil":
                self.qc_status = "Ok"

        if self.content_type.model == "prodreport":

            if self.balance==0 :
                self.qc_status = "Nil"
            if self.balance!=0 and self.qc_status=="Nil" :
                self.qc_status = "Ok"

            # if self.dispached.all().exists() == True:
            #     if self.dispached.all().first().lock == True:
            #         self.qc_status = "Dispatched"
            # if self.qc_status=="Dispatched" and self.dispached.all().exists() == False:
            #     self.qc_status = "Finished"

        super(Stockdetail, self).save(*args, **kwargs)


    def __str__(self):
        return str(self.id) + ") " + str(self.materialname) + " - " + str(self.item_mat_type) + " - " + str(
            self.item_grade) + "-" + str(self.size) + "mm X " + str(self.micron) + "mic : R" + str(
            self.recieved or 0) + " - U" + str(round((self.recieved or 0) - (self.balance or 0), 2)) + " = B" + str(
            self.balance or 0) + " (" + str(self.alloted or 0) + "/" + str(self.available or 0) + ") || " + str(
            self.created.day or 0) + "-" + str(self.created.month or 0) + "-" + str(
            self.created.year or 0)

    @property
    def full_name(self):
        return str(self.materialname) + "-" + str(self.item_mat_type) + "-" + str(
            self.item_grade) + " " + str(self.size) + " mm X " + str(self.micron)

    @property
    def used(self):
        result = ProdInput.objects.filter(material=self).aggregate(Sum('inputqty'))
        return round(result['inputqty__sum'] or 0, 3)

    @property
    def allo(self):
        result = JobMaterialStatus.objects.filter(allote=self).aggregate(Sum('qty'))
        return result['qty__sum'] or 0

    @property
    def mate_name(self):
        return str(self.materialname) + " - " + str(self.item_mat_type) + " - " + str(
            self.item_grade) + "-" + str(self.size) + "mm X " + str(self.micron) + "mic"

    @property
    def dispatched(self):
        if len(self.dispached.all()) > 0 :
            return True
        else:
            return False


class Inward(models.Model):
    docdate = models.DateTimeField(blank=True, null=True)
    supplier = models.ForeignKey(Customer, related_name='inward', on_delete=models.PROTECT)
    inwarddate = models.DateTimeField(blank=True, null=True)
    invoice=models.CharField(max_length=32,null=True,blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='inwardcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='inwardedited')
    stock = GenericRelation(Stockdetail, related_query_name='inwards')

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return str(self.id) + "-" + str(self.supplier)


class ProdReport(models.Model):
    prodprocess = models.ForeignKey(JobProcess, related_name='jobreport', on_delete=models.PROTECT)
    processdate = models.DateTimeField()
    qty = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.PROTECT)
    totalkg = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    checked = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    remark = models.TextField(null=True, blank=True)
    supervisor = models.ForeignKey(User,on_delete=models.PROTECT, related_name='reportsupervisor',null=True,blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='prodcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='prodedited')
    output = GenericRelation(Stockdetail, related_query_name='prodreports')

    def __str__(self):
        return str(self.id) + " = " + str(self.prodprocess)

    class Meta:
        ordering = ["processdate"]

    @property
    def grossinput(self):
        result = self.prodinput.all().aggregate(Sum("grossinput"))
        return round((result["grossinput__sum"] or 0), 3)

    @property
    def totalbalance(self):
        result = self.prodinput.all().aggregate(Sum("returned"))
        return round((result["returned__sum"] or 0), 3)

    @property
    def totalinput(self):
        result = self.prodinput.all().aggregate(Sum("inputqty"))
        return round((result["inputqty__sum"] or 0), 3)

    @property
    def totalwtgain(self):
        result = self.prodinput.all().aggregate(Sum("wtgain"))
        return round((result["wtgain__sum"] or 0), 3)

    @property
    def grossoutput(self):
        result = self.output.all().aggregate(Sum("gross_wt"))
        return round((result["gross_wt__sum"] or 0), 3)

    @property
    def netoutput(self):
        result = self.output.exclude(materialname__name="WASTE").aggregate(Sum("recieved"))
        return round((result["recieved__sum"] or 0), 3)

    @property
    def grosstarewt(self):
        result = self.output.all().aggregate(Sum("tare_wt"))
        return round((result["tare_wt__sum"] or 0), 3)

    @property
    def grossrecieved(self):
        result = self.output.all().aggregate(Sum("recieved"))
        return round((result["recieved__sum"] or 0), 3)

    @property
    def grossnos(self):
        result = self.output.all().aggregate(Sum("nos"))
        return round((result["nos__sum"] or 0), 3)

    @property
    def wastepercentage(self):
        if self.netoutput and self.totalwtgain:
            return round((self.totalwtgain - self.netoutput) * 100 / self.totalwtgain, 2)
        else:
            return 0


class ProdInput(models.Model):
    material = models.ForeignKey(Stockdetail, related_name='prodinput', on_delete=models.PROTECT)
    grossinput = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    returned = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, default=0)
    inputqty = models.DecimalField(max_digits=10, decimal_places=3)
    wtgain = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    prodreport = models.ForeignKey(ProdReport, related_name='prodinput', on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True, null=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='prodinputcreated')
    edited = models.DateTimeField(auto_now=True, null=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='prodinputedited')

    def __str__(self):
        return str(self.id) + "-" + str(self.material) + "= " + str(self.inputqty)

    def save(self, *args, **kwargs):
        self.wtgain = self.material.materialname.solid * self.inputqty / 100
        super(ProdInput, self).save(*args, **kwargs)


class ProdPerson(models.Model):
    person = models.ForeignKey(Worker, related_name='prodperson', on_delete=models.PROTECT)
    prodreport = models.ForeignKey(ProdReport, related_name='prodperson', on_delete=models.PROTECT)

    class Meta:
        unique_together = ['person', 'prodreport']


class JobMaterialStatus(models.Model):
    jobmaterial = models.ForeignKey(JobMaterial, related_name='jobmaterialstatus', on_delete=models.PROTECT)
    allote = models.ForeignKey(Stockdetail, related_name='jobmaterialstatus', on_delete=models.PROTECT)
    qty = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='jobmaterialstatuscreated')
    edited = models.DateTimeField(auto_now=True, null=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='jobmaterialstatusedited')

    def __str__(self):
        return str(self.jobmaterial) + " kg " + str(self.qty)


class DispatchRegister(models.Model):
    customer = models.ForeignKey(Customer, related_name='dispatches', on_delete=models.PROTECT)
    dispatch_material = models.ManyToManyField(Stockdetail, related_name="dispached", blank=True)
    dispatchdate = models.DateTimeField()
    address = models.ForeignKey(Address, related_name='address', on_delete=models.PROTECT)
    value = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    recievedby = models.CharField(max_length=64, null=True, blank=True)
    contact = models.CharField(max_length=64, null=True, blank=True)
    recieptnumber = models.CharField(max_length=64, null=True, blank=True)
    transport = models.CharField(max_length=64, null=True, blank=True)
    person = models.CharField(max_length=64, null=True, blank=True)
    vehicle = models.CharField(max_length=64, null=True, blank=True)
    remark = models.CharField(max_length=255, null=True, blank=True)
    imagename1 = models.ImageField(upload_to='dispatch1/', blank=True,null=True, max_length=256)
    imagename2 = models.ImageField(upload_to='dispatch2/', blank=True,null=True, max_length=256)
    lock = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, null=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='dispatchcreated')
    edited = models.DateTimeField(auto_now=True, null=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='dispatchedited')

    def __str__(self):
        return str(self.id) + '/dispatched'

    class Meta:
        ordering = ["-id"]

    @property
    def totalsum(self):
        result = self.dispatch_material.all().aggregate(Sum('recieved'))
        return round(result['recieved__sum'] or 0, 3)


class DispatchDetail(models.Model):
    dispatch = models.ForeignKey(DispatchRegister, on_delete=models.PROTECT, related_name='dispatchdetail')
    dispatchstock = models.OneToOneField(Stockdetail, on_delete=models.PROTECT, related_name='dispatchdetail',
                                         null=True, blank=True)

    def __str__(self):
        return str(self.dispatch.dispatchdate)


class ProdProblem(models.Model):
    problem = models.ForeignKey(Problem, related_name='prodproblem', on_delete=models.PROTECT)
    prodreport = models.ForeignKey(ProdReport, related_name='prodproblem', on_delete=models.PROTECT)
    timewaste = models.IntegerField(null=True, blank=True)
    action = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.problem


class JobQc(models.Model):
    qctest = models.ForeignKey(QCTest, related_name='jobqc', on_delete=models.PROTECT)
    prodreport = models.ForeignKey(ProdReport, related_name='jobqc', on_delete=models.PROTECT)
    result = models.CharField(max_length=128)
    lock=models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, null=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='qccreated')
    edited = models.DateTimeField(auto_now=True, null=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='qcedited')


    def __str__(self):
        return f'{self.prodreport}={self.qctest}'


class ProductionProblem(models.Model):
    process=models.ForeignKey(Process,on_delete=models.PROTECT,related_name='productionproblems')
    problem=models.CharField(max_length=256)

    def __str__(self):
        return self.problem

class ProblemTag(models.Model):
    outputroll=models.ForeignKey(Stockdetail,on_delete=models.CASCADE,related_name='problemtags')
    tagname=models.ForeignKey(ProductionProblem,on_delete=models.CASCADE,related_name='problemstags')
    created = models.DateTimeField(auto_now_add=True, null=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='problemcreated')
    edited = models.DateTimeField(auto_now=True, null=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='problemedited')

    def __str__(self):
        return str(self.tagname)
