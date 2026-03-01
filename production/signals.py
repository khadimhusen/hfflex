from django.db.models.signals import post_save
from .models import ProdInput, JobMaterialStatus, Stockdetail, ProdReport
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType


@receiver(post_save, sender=ProdInput)
def rawmaterial_is_created(sender, instance, **kwargs):
    instance.material.save()
    instance.prodreport.prodprocess.job.save()


@receiver(post_save, sender=JobMaterialStatus)
def newrawmaterial_is_created(sender, instance, **kwargs):
    instance.jobmaterial.save()
    instance.allote.save()

@receiver(post_save, sender=Stockdetail)
def rawmaterial_is_saved(sender, instance, **kwargs):
    ctypes=ContentType.objects.get(model="prodreport")
    if instance.content_type==ctypes:
       obj= ProdReport.objects.get(id=instance.object_id)
       obj.prodprocess.job.save()
       print("done")