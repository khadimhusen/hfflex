from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from itemmaster.models import (ItemMaster, RawMaterial, PouchType, LamiRubber,
                               Process, ItemProcess, Color, ItemColor, ItemImage, Machine, AttributeMaster,
                               ItemAttribute)
from customer.models import Customer, Address
from material.models import Unit, Material, MatType, Grade
from preorder.models import JobName
from .choices import jobchoices, orderchoices, SUPPLY_CHOICES, DIRECTION, processchoices
from datetime import datetime, timedelta
from purchase.models import Po


class OrderManager(models.Manager):
    def get_queryset(self):
        return super(OrderManager, self).get_queryset().select_related()


class Order(models.Model):
    customer = models.ForeignKey(Customer, related_name='order', on_delete=models.PROTECT)
    po = models.CharField(max_length=32, blank=True)
    orderdate = models.DateTimeField(auto_now_add=True, )
    podate = models.DateTimeField(blank=True, null=True)
    deliverydate = models.DateTimeField(blank=True, null=True)
    paymentterms = models.IntegerField(null=True, blank=True)
    tax1 = models.DecimalField(max_digits=10, decimal_places=3)
    tax2 = models.DecimalField(max_digits=10, decimal_places=3)
    transport = models.CharField(max_length=64, blank=True)
    remark = models.CharField(max_length=512, null=True, blank=True)
    delivery_at = models.ForeignKey(Address, related_name='order', on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=16, choices=orderchoices, default="Pending", null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='ordercreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='orderedited')

    objects = OrderManager()

    def __str__(self):
        return f" {self.id} - {self.customer}"

    class Meta:
        ordering = ['-id']


class JobManager(models.Manager):
    def get_queryset(self):
        return super(JobManager, self).get_queryset().select_related()


class Job(models.Model):
    prejob = models.OneToOneField(JobName, on_delete=models.PROTECT, related_name="job", null=True, blank=True)
    joborder = models.ForeignKey(Order, related_name='job', on_delete=models.PROTECT)
    itemmaster = models.ForeignKey(ItemMaster, related_name='jobitem', on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=0)
    unit = models.ForeignKey(Unit, related_name='job', on_delete=models.PROTECT)
    rate = models.DecimalField(max_digits=10, decimal_places=3)
    waste = models.DecimalField(max_digits=10, decimal_places=1, blank=True, null=True, default=12)
    jobstatus = models.CharField(max_length=32, choices=jobchoices, default="Account clearance")
    dispatch_approval = models.BooleanField(default=False, blank=True)
    dispatch_approval_date = models.DateTimeField(null=True, blank=True)
    dispatch_remark = models.CharField(max_length=256, null=True, blank=True)
    jobremark = models.CharField(max_length=256, blank=True, null=True)
    kgqty = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    itemname = models.CharField(max_length=256, )
    invoice = models.CharField(max_length=32, null=True, blank=True)
    barcode = models.CharField(max_length=32, blank=True)
    packsize = models.CharField(max_length=16, default="-")
    replength = models.DecimalField(max_digits=10, decimal_places=1, blank=True, null=True)
    openwidth = models.DecimalField(max_digits=10, decimal_places=1, blank=True, null=True)
    slit_size = models.DecimalField(max_digits=10, decimal_places=1, blank=True, null=True)
    no_of_repeat = models.DecimalField(max_digits=10, decimal_places=1, blank=True, default=0)
    no_of_ups = models.DecimalField(max_digits=10, decimal_places=1, blank=True, default=0)
    cyl_length = models.DecimalField(max_digits=4, decimal_places=0, blank=True, default=0)
    cyl_circum = models.DecimalField(max_digits=10, decimal_places=1, blank=True, default=0)
    printing = models.CharField(max_length=32, choices=[('Surface', 'Surface'),
                                                        ('Reverse', 'Reverse'),
                                                        ('Unprinted', 'Unprinted')], default="Reverse")
    total_gsm = models.DecimalField(max_digits=10, decimal_places=1, blank=True, null=True)
    pouch_weight = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    pouch_per_kg = models.DecimalField(max_digits=10, decimal_places=1, blank=True, null=True)
    pouch_type = models.ForeignKey(PouchType, related_name='jobitemmaster', on_delete=models.PROTECT, blank=True,
                                   null=True)
    supply_form = models.CharField(max_length=16, choices=SUPPLY_CHOICES, default="ROLL")
    film_size = models.IntegerField(default=0)
    remark = models.TextField(null=True, blank=True)
    unwind_direction = models.CharField(max_length=32, choices=DIRECTION, default="ANY")
    lami_rubber = models.ForeignKey(LamiRubber, related_name='jobitemmaster', on_delete=models.SET_NULL, null=True,
                                    blank=True)
    totalpouch = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True, default=0)  #
    totalmeter = models.DecimalField(max_digits=10, decimal_places=1, blank=True, null=True, default=0)  #
    job_waste = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, default=0)
    job_repeat_status = models.CharField(max_length=16, choices=[("New", "New"), ("Repeat", "Repeat")], default="New",
                                         blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='jobcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='jobedited')

    objects = JobManager()

    def save(self, *args, **kwargs):

        if self.id:
            flag = False
            self.job_waste = self.jobwaste
            self.total_gsm = round((self.totalgsm) or 0, 1)
            self.pouch_weight = round((self.total_gsm or 0) * (self.openwidth or 0) * (self.replength or 0) / 1000000,
                                      2)
            if self.pouch_weight == 0 or self.pouch_weight == None:
                self.pouch_per_kg = 0
            else:
                if str(self.unit) == "KG.":
                    self.kgqty = round(self.quantity, 0)
                    self.totalpouch = round(self.quantity * 1000 / (self.pouch_weight), 0)
                else:
                    self.kgqty = round(self.quantity * self.pouch_weight / 1000, 0)
                    self.totalpouch = self.quantity
                self.pouch_per_kg = round(1000 / (self.pouch_weight), 1)
                self.totalmeter = round(
                    self.kgqty * 1000000 * ((self.waste / 100) + 1) / (self.total_gsm * self.film_size), 0)
        else:
            flag = True

            baseitem = self.itemmaster
            if baseitem.isnew == "No Jobs":
                self.job_repeat_status = "New"
            else:
                self.job_repeat_status = "Repeat"

            self.itemname = str(baseitem.itemname) + " / " + str(baseitem.itemcustomer)
            self.itemcode = baseitem.itemcode
            self.barcode = baseitem.barcode
            self.packsize = baseitem.packsize
            self.replength = baseitem.replength
            self.openwidth = baseitem.openwidth
            self.slit_size = baseitem.slit_size
            self.no_of_repeat = baseitem.no_of_repeat
            self.no_of_ups = baseitem.no_of_ups
            self.cyl_length = baseitem.cyl_length
            self.cyl_circum = baseitem.cyl_circum
            self.printing = baseitem.printing
            self.total_gsm = baseitem.total_gsm
            self.pouch_weight = baseitem.pouch_weight
            self.pouch_per_kg = baseitem.pouch_per_kg
            self.pouch_type = baseitem.pouch_type
            self.supply_form = baseitem.supply_form
            self.film_size = baseitem.film_size
            self.unwind_direction = baseitem.unwind_direction
            self.lami_rubber = baseitem.lami_rubber
            if self.unit.unit == "KG.":
                self.kgqty = round(self.quantity, 0)
                self.totalpouch = round(self.quantity * 1000 / (self.pouch_weight), 0)
            elif self.unit.unit == "MTR.":
                self.kgqty = round(self.quantity * self.film_size * self.total_gsm / 1000000, 0)
                self.totalpouch = round(self.quantity * 1000 / (self.pouch_weight), 0)
            else:
                self.kgqty = round(self.quantity * self.pouch_weight / 1000, 0)
                self.totalpouch = self.quantity
            self.pouch_per_kg = round(1000 / (self.pouch_weight), 1)
            self.totalmeter = round(
                self.kgqty * 1000000 * ((self.waste / 100) + 1) / (self.total_gsm * self.film_size), 0)
        super(Job, self).save(*args, **kwargs)
        if flag:
            obj = RawMaterial.objects.filter(itemmaster=self.itemmaster)
            for ob in obj:
                JobMaterial.objects.create(job=self,
                                           materialname=ob.materialname,
                                           item_mat_type=ob.item_mat_type,
                                           item_grade=ob.item_grade, size=ob.size,
                                           micron=ob.micron,
                                           gsm=ob.gsm,
                                           req=round((ob.required / ob.materialname.solid) * 100 * self.kgqty * (
                                                   (self.waste + 100) / 100), 1),
                                           length=round(
                                               ob.required * self.kgqty * ((self.waste + 100) / 100) * 1000000 / (
                                                       ob.size * ob.gsm), 1)
                                           )

            colors = ItemColor.objects.filter(itemmaster=self.itemmaster)
            for colo in colors:
                JobColor.objects.create(job=self, color=colo.color, remark=colo.remark)

            images = ItemImage.objects.filter(itemname=self.itemmaster)
            for img in images:
                JobImage.objects.create(job=self, imagename=img.imagename)

            jobitemattributes = ItemAttribute.objects.filter(itemmaster=self.itemmaster)
            for att in jobitemattributes:
                JobItemAttribute.objects.create(job=self,
                                                item_attirbuate=att.item_attirbuate,attri_value=att.attri_value)


            proc = ItemProcess.objects.filter(itemmaster=self.itemmaster)
            for pro in proc:
                prounit = pro.unit.unit
                if prounit == "NOS.":
                    processqty = self.totalpouch
                elif prounit == "KG.":
                    processqty = self.kgqty
                elif prounit == "MTR.":
                    if pro.process.process=="Printing":
                        processqty = self.totalmeter+200
                    else:
                        processqty = self.totalmeter
                else:
                    processqty = self.kgqty
                JobProcess.objects.create(job=self, process=pro.process, unit=pro.unit,
                                          qty=processqty, machine=pro.machine)


    def __str__(self):
        return f"{self.id} - {self.itemname}"

    class Meta:
        ordering = ['-id']

    @property
    def totalgsm(self):
        result = JobMaterial.objects.filter(job=self).aggregate(Sum('gsm'))
        return result['gsm__sum']

    @property
    def totalmicron(self):
        result = JobMaterial.objects.filter(job=self).aggregate(Sum('micron'))
        return result['micron__sum']

    @property
    def ply(self):
        newresult = JobMaterial.objects.filter(job=self, materialname__state='Film').count()
        return newresult

    @property
    def nearschedule(self):
        return int(datetime.now().strftime("%Y%m%d")) + 2 > int(self.joborder.deliverydate.strftime("%Y%m%d")) and (
                self.jobstatus == "Pending" or self.jobstatus == "Unplanned")

    @property
    def late(self):
        return datetime.now() > self.joborder.deliverydate and (
                self.jobstatus == "Pending" or self.jobstatus == "Unplanned")

    @property
    def oneweek(self):
        return datetime.now() + timedelta(days=7) > self.joborder.deliverydate and (
                self.jobstatus == "Pending" or self.jobstatus == "Unplanned")

    @property
    def twoweek(self):
        return datetime.now() + timedelta(days=14) > self.joborder.deliverydate and (
                self.jobstatus == "Pending" or self.jobstatus == "Unplanned")

    @property
    def threeweek(self):
        return datetime.now() + timedelta(days=21) > self.joborder.deliverydate and (
                self.jobstatus == "Pending" or self.jobstatus == "Unplanned")

    @property
    def fourweek(self):
        return datetime.now() + timedelta(days=28) > self.joborder.deliverydate and (
                self.jobstatus == "Pending" or self.jobstatus == "Unplanned")

    @property
    def pouchqty(self):
        newresult = (self.kgqty or 0) * (self.pouch_per_kg or 0)
        return newresult

    @property
    def jobwaste(self):

        from production.models import ProdInput, Stockdetail, ProdReport

        allreport_id = ProdReport.objects.filter(prodprocess__job=self).values_list('id', flat=True)
        allinput = ProdInput.objects.filter(prodreport__prodprocess__job=self).select_related()
        alloutput = Stockdetail.objects.filter(content_type__model="prodreport",
                                               object_id__in=allreport_id).select_related()
        netinput = 0
        netoutput = 0
        matedetail = {}
        context = {}
        for item in allinput:
            if not matedetail.get(item.material):
                matedetail[item.material] = round((-item.wtgain or 0), 3)
            else:
                matedetail[item.material] = round(matedetail[item.material] + (-item.wtgain or 0), 3)

        for item in alloutput:
            if not matedetail.get(item):
                matedetail[item] = round((item.recieved or 0), 3)
            else:
                matedetail[item] = round(matedetail[item] + (item.recieved or 0), 3)

        for key in matedetail:
            if matedetail[key] < -0.0001:
                netinput = round(netinput + matedetail[key], 3)
            elif matedetail[key] > 0.0001:
                if not 'WASTE' in key.__str__():
                    netoutput = round(netoutput + matedetail[key], 3)

        netwaste = netinput + netoutput
        wastepercent = 0
        if not netinput == 0:
            wastepercent = round(netwaste * 100 / netinput, 3)
        context['wastepercent'] = wastepercent
        return context['wastepercent']

    @property
    def job_disptached(self):
        from production.models import Stockdetail
        obj = Stockdetail.objects.filter(prodreports__prodprocess__job=self, qc_status="Finished")
        return obj

    @property
    def totalreq(self):
        materials = self.jobmaterial.all()
        result = {}
        result['requirment'] = 0
        for mate in materials:
            result['requirment'] += mate.req * mate.density
        return round(result['requirment'], 2)

    @property
    def kgrate(self):
        if self.unit.unit == "KG.":
            return self.rate

        elif self.unit.unit == "NOS.":
            return round(self.rate * self.pouch_per_kg, 0)
        return 0


class JobMaterialManager(models.Manager):
    def get_queryset(self):
        return super(JobMaterialManager, self).get_queryset().select_related()


class JobMaterial(models.Model):
    job = models.ForeignKey(Job, related_name='jobmaterial', on_delete=models.CASCADE)
    materialname = models.ForeignKey(Material, related_name='jobmaterial', on_delete=models.PROTECT)
    item_mat_type = models.ForeignKey(MatType, related_name='jobmaterial', on_delete=models.PROTECT)
    item_grade = models.ForeignKey(Grade, related_name='jobmaterial', on_delete=models.PROTECT)
    size = models.IntegerField(null=True)
    micron = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    gsm = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)
    req = models.DecimalField(max_digits=10, decimal_places=1, blank=True, null=True)
    available = models.DecimalField(max_digits=10, decimal_places=1, blank=True, null=True)
    to_order = models.DecimalField(max_digits=10, decimal_places=1, blank=True, null=True)
    orderedqty = models.DecimalField(max_digits=10, decimal_places=1, default=0.0)
    receivedqty = models.DecimalField(max_digits=10, decimal_places=1, default=0.0)
    po = models.ForeignKey(Po, related_name='jobmaterial', on_delete=models.PROTECT, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    length = models.DecimalField(max_digits=10, decimal_places=1, blank=True, null=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='jobmaterialcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='jobmaterialedited')

    objects = JobMaterialManager()

    def __str__(self):
        return f" {self.materialname}-{self.item_mat_type}-{self.item_grade}-{self.size}mm X {self.micron} = {self.req}"

    @property
    def mat_length(self):
        if self.required and self.gsm and self.size:
            return round(self.required * 1000000 / (self.micron * self.materialname.density * self.size), 1)
        else:
            return None

    @property
    def required(self):
        result = JobMaterial.objects.filter(job=self.job).aggregate(Sum('gsm'))
        if result['gsm__sum'] is None or result['gsm__sum'] == 0:
            result['gsm__sum'] = self.micron * self.materialname.density
        return round((self.gsm or 0) * (self.job.kgqty or 0) * ((self.job.waste + 100) / 100) / result['gsm__sum'],
                     2)

    @property
    def material(self):
        return f'{self.materialname} - {self.item_mat_type} - {self.item_grade} =  {self.size}mm X {self.micron}Mic '

    @property
    def avail(self):
        from production.models import JobMaterialStatus
        result = JobMaterialStatus.objects.filter(jobmaterial=self).aggregate(Sum('qty'))
        return round((result['qty__sum'] or 0), 1)



    def save(self, *args, **kwargs):
        if self.job.film_size != 0:
            self.gsm = round(
                self.materialname.density * self.micron * self.size * self.materialname.weightgain / self.job.film_size,
                3)
        else:
            self.gsm = self.micron * self.materialname.density * self.materialname.weightgain
        self.length = self.mat_length
        self.available = self.avail
        self.to_order = (self.req or 0) - (self.available or 0) - (self.orderedqty or 0) + (self.receivedqty or 0)
        super(JobMaterial, self).save(*args, **kwargs)


class JobProcessManager(models.Manager):
    def get_queryset(self):
        return super(JobProcessManager, self).get_queryset().select_related()


class JobProcess(models.Model):
    job = models.ForeignKey(Job, related_name='jobprocess', on_delete=models.CASCADE)
    srno = models.IntegerField(null=True, blank=True)
    process = models.ForeignKey(Process, related_name='jobprocess', on_delete=models.PROTECT)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, null=True, blank=True)
    prod_duration = models.DurationField(null=True, blank=True)
    qty = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True)
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=processchoices, default="Pending")
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='jobprocesscreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='jobprocessedited')

    objects = JobProcessManager()

    class Meta:
        unique_together = ('srno', 'machine')

    def __str__(self):
        return str(self.job) + "/" + str(self.id) + "/" + str(self.process)

    @property
    def jobdispatch(self):
        result = JobMaterial.objects.filter(job=self.job).aggregate(Sum('gsm'))
        return result

    @property
    def pendingqty(self):
        if self.status == "Completed":
            return 0
        else:
            from production.models import ProdReport
            producedqty = ProdReport.objects.filter(prodprocess=self).aggregate(Sum('qty'))
            result = max(self.qty - (producedqty['qty__sum'] or 0), 0)
            return round(result)

    @property
    def produced_qty(self):
        from production.models import ProdReport
        result = ProdReport.objects.filter(prodprocess=self).aggregate(Sum('qty'))
        return round(result["qty__sum"] or 0)


class JobColor(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='jobcolors', null=True, blank=True)
    color = models.ForeignKey(Color, on_delete=models.PROTECT, related_name='jobcolors', null=True, blank=True)
    remark = models.CharField(max_length=128, null=True, blank=True)

    def __str__(self):
        return str(self.color)


class JobImage(models.Model):
    imagename = models.ImageField(upload_to='itemmaster/', blank=True)
    job = models.ForeignKey(Job, related_name='jobimages', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='jobimagecreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='jobimageedited')


class JobItemAttribute(models.Model):
    item_attirbuate=models.ForeignKey(AttributeMaster,on_delete=models.PROTECT,related_name="jobitemattribute")
    job = models.ForeignKey(Job, related_name='jobitemattribute', on_delete=models.CASCADE)
    attri_value = models.CharField(max_length=32)

    def __str__(self):
        return f'{self.item_attirbuate} = {self.attri_value}'
