from django.contrib.auth.models import User
from django.db import models

KINDS = [('National', 'National'), ('Festival', 'Festival'), ('Company', 'Company'), ('Other', 'Other')]


class Holiday(models.Model):
    """One day the company is closed. The list is the same for everybody; attendance
    reads it (see holidaylist.services) so nobody has to be marked by hand."""
    date = models.DateField(unique=True)
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=KINDS, default='Festival')
    notes = models.CharField(max_length=300, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    edited = models.DateTimeField(auto_now=True)
    edited_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f'{self.date:%d/%m/%Y} {self.name}'
