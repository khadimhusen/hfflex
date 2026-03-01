from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.contrib.auth.models import User
from employee.models import Worker
from itemmaster.models import Problem
from order.models import Job
from django.db.models import Sum
from .choices import SHIFTCHOICE, MAKEREADY


class Machine(models.Model):
    machinename = models.CharField(max_length=32)
    est_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.machinename


class TimeMaster(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT)
    makeready = models.CharField(max_length=16, choices=MAKEREADY)
    allotedtime = models.IntegerField()

    class Meta:
        unique_together = ["machine", "makeready"]

    def __str__(self):
        return str(self.machine) + " - " + str(self.makeready) + " - " + str(self.allotedtime)


class Shift(models.Model):
    shift = models.CharField(max_length=16, choices=SHIFTCHOICE)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT)
    production_date = models.DateField()
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='shiftcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='shiftedited')
    is_approved = models.BooleanField(default=False)

    class Meta:
        unique_together = ["shift", "machine", 'production_date']
        ordering = ['-production_date']

    def __str__(self):
        return str(self.production_date) + " " + str(self.shift) + " Shift- " + str(self.machine)

    @property
    def actualtime(self):
        result = Activity.objects.filter(shift=self).aggregate(Sum('totaltime'))
        return round(result['totaltime__sum'] or 0, 0)

    @property
    def totalroll(self):
        result = Activity.objects.filter(shift=self).aggregate(Sum('rolls'))
        return round(result['rolls__sum'] or 0, 0)

    @property
    def totaltag(self):
        result = Activity.objects.filter(shift=self).aggregate(Sum('tag'))
        return round(result['tag__sum'] or 0, 0)

    @property
    def totallot(self):
        result = Activity.objects.filter(shift=self).aggregate(Sum('lot'))
        return round(result['lot__sum'] or 0, 0)

    @property
    def totaldowntime(self):
        result2 = DowntimeReport.objects.filter(activity__shift=self).aggregate(Sum('downtime'))
        return round( (result2['downtime__sum'] or 0), 0)

    @property
    def totalqty(self):
        result = Activity.objects.filter(shift=self).aggregate(Sum('qty'))
        return round(result['qty__sum'] or 0, 0)

    @property
    def totalmakereadytime(self):
        result = Activity.objects.filter(shift=self).aggregate(Sum('makereadytime'))
        return round(result['makereadytime__sum'] or 0, 0)

    @property
    def totalrunningtime(self):
        result = 0
        for act in Activity.objects.filter(shift=self):
            if not act.speed == 0:
                result += act.qty / act.speed
        return round(result, 0)

    @property
    def wastetime(self):
        result = Activity.objects.filter(shift=self).aggregate(Sum('totaltime'))
        return (result['totaltime__sum'] or 0) - (690)

    @property
    def efficiency(self):
        return round((self.actualtime or 0) * 100 / 690, 1)


class Activity(models.Model):
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name="activity")
    jobid = models.ForeignKey(Job, on_delete=models.PROTECT, related_name='activity')
    qty = models.IntegerField(default=0)
    speed = models.IntegerField(default=0)
    makeready = models.CharField(max_length=16, choices=MAKEREADY)
    makereadytime = models.IntegerField(default=0)
    rolls = models.IntegerField(default=0)
    lot = models.IntegerField(default=0)
    tag = models.IntegerField(default=0)
    #downtime = models.IntegerField(default=0)
    totaltime = models.IntegerField(default=0)
    #other = models.CharField(max_length=128, null=True, blank=True)
    #reason = models.ForeignKey(Problem, on_delete=models.PROTECT, null=True, blank=True)

    def __str__(self):
        return str(self.shift) + str(self.jobid)

    def save(self, *args, **kwargs):
        downtime = (DowntimeReport.objects.filter(activity=self).aggregate(Sum('downtime'))["downtime__sum"] or 0)

        self.makereadytime = TimeMaster.objects.filter(machine=self.shift.machine, makeready=self.makeready)[
                                 0].allotedtime or 0
        if self.speed == 0:
            self.totaltime = round(self.makereadytime + (self.rolls * 5) + (self.lot * 10) +  (self.tag * 5) +downtime, 0)
        else:
            self.totaltime = round(
                (self.qty / self.speed) + self.makereadytime +
                (self.rolls * 5) + (self.lot * 10)+ (self.tag * 5) + downtime, 0)


        super(Activity, self).save(*args, **kwargs)

    @property
    def runningtime(self):
        if self.speed == 0:
            return 0
        return round(self.qty / self.speed, 0)

    @property
    def totaldowntime(self):
        result = DowntimeReport.objects.filter(activity=self).aggregate(Sum('downtime'))

        return (result['downtime__sum'] or 0)


class ShiftPerson(models.Model):
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name="shiftperson")
    person = models.ForeignKey(Worker, on_delete=models.PROTECT, related_name='shiftperson')

    def __str__(self):
        return str(self.person) + " - " + str(self.shift)

    class Meta:
        unique_together = ["shift", "person"]


class DowntimeReport(models.Model):
    activity = models.ForeignKey(Activity, related_name='downtimes', on_delete=models.CASCADE, null=True, blank=True)
    reason = models.ForeignKey(Problem, on_delete=models.PROTECT, null=True, blank=True)
    downtime = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='downtimecreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='downtimeedited')

    def __str__(self):
        return str(self.reason) + ":- " + str(self.downtime)
