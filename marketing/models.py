from django.db import models
from django.contrib.auth.models import User

from marketing.choices import RATING


class Lead(models.Model):
    customername = models.CharField(max_length=126,unique=True)
    cityname = models.CharField(max_length=126)
    locationlink = models.URLField(max_length=512)
    contact_number = models.CharField(max_length=50)
    websitelink = models.URLField(max_length=256)
    industry = models.CharField(max_length=64)
    lead_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='createdlead')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='editedlead')

    def __str__(self):
        return f'{self.customername} - {self.cityname}'

class Bunch(models.Model):
    leaduser=models.ForeignKey(User,on_delete=models.PROTECT,related_name='bunch')
    lead=models.ManyToManyField(Lead,blank=True)
    completed=models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='createdbunch')


    def __str__(self):
        return f'{str(self.leaduser)} -{str(self.id)}'



class Route(models.Model):
    route_date = models.DateField()
    is_closed = models.BooleanField(default=False)
    route_link = models.URLField(max_length=256, null=True, blank=True)
    marketing_person = models.ForeignKey(User, on_delete=models.PROTECT, related_name='route')
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='createdroute')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='editedroute')

    def __str__(self):
        if self.is_closed:
            routestatus = "Closed"
        else:
            routestatus = "Pending"
        return f'Route-{self.id}-{routestatus}'


class RouteCustomer(models.Model):
    customername = models.ForeignKey(Lead, on_delete=models.PROTECT)
    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name='routecustomer')
    visitstatus = models.CharField(max_length=16, default="Pending")
    presentation = models.PositiveSmallIntegerField(choices=RATING, null=True, blank=True)
    need_analysis = models.PositiveSmallIntegerField(choices=RATING, null=True, blank=True)
    packing_use=models.PositiveSmallIntegerField(choices=RATING,null=True,blank=True)
    cost = models.PositiveSmallIntegerField(choices=RATING, null=True, blank=True)
    terms_and_condition = models.PositiveSmallIntegerField(choices=RATING, null=True, blank=True)
    old_supplier_relation = models.PositiveSmallIntegerField(choices=RATING, null=True, blank=True)
    customer_sample = models.PositiveSmallIntegerField(choices=RATING, null=True, blank=True)
    our_relation = models.PositiveSmallIntegerField(choices=RATING, null=True, blank=True)
    reason=models.CharField(max_length=256,null=True,blank=True)
    action_plan=models.TextField(null=True,blank=True)
    nextvisit = models.ForeignKey(Route, on_delete=models.PROTECT, null=True, blank=True, related_name='nextvisitroute')

    def save(self, *args, **kwargs):
        if self.pk:
            old_instance = RouteCustomer.objects.get(pk=self.pk)
            if old_instance.nextvisit == None and self.nextvisit != None:
                RouteCustomer.objects.create(customername=self.customername, route=self.nextvisit,
                                             visitstatus="Pending")

        super(RouteCustomer, self).save(*args, **kwargs)
