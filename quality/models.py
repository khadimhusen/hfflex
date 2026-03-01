from django.db import models
from itemmaster.models import Process


class QCTest(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)
    process = models.ManyToManyField(Process)

    def __str__(self):
        return self.name
