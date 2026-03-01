from django.db import models
from django.contrib.auth.models import User


class Commodity(models.Model):
    commodity = models.CharField(max_length=126, unique=True)

    def __str__(self):
        return self.commodity


class Material(models.Model):
    name = models.CharField(max_length=32, unique=True)
    density = models.DecimalField(max_digits=10, decimal_places=3)
    solid = models.DecimalField(max_digits=10, decimal_places=3)
    weightgain = models.BooleanField(default=True)
    state = models.CharField(max_length=8, choices=[('Film', 'Film'), ('Liquid', 'Liquid'),("Other","Other")], null=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='materialcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='materialedited')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = self.name.upper()
        super(Material, self).save(*args, **kwargs)


class MatType(models.Model):
    mat_type = models.CharField(max_length=32, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='mattypecreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='mattypeedited')

    def __str__(self):
        return self.mat_type

    def save(self, *args, **kwargs):
        self.mat_type = self.mat_type.upper()
        super(MatType, self).save(*args, **kwargs)


class Grade(models.Model):
    grade = models.CharField(max_length=32, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='gradecreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='gradeedited')

    def __str__(self):
        return self.grade

    def save(self, *args, **kwargs):
        self.grade = self.grade.upper()
        super(Grade, self).save(*args, **kwargs)


class Unit(models.Model):
    unit = models.CharField(max_length=8, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='unitcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='unitedited')

    def __str__(self):
        return self.unit

    def save(self, *args, **kwargs):
        self.unit = self.unit.upper()
        super(Unit, self).save(*args, **kwargs)
