from django.db.models.signals import post_save, post_delete
from .models import JobMaterial
from django.dispatch import receiver
from production.models import JobMaterialStatus

@receiver(post_save, sender=JobMaterial)
def jobmaterial_is_created(sender, instance, created, **kwargs):
    if not created:
        instance.job.save()

@receiver(post_save, sender=JobMaterialStatus)
def jobmaterialstatus_is_updated(sender, instance,  **kwargs):
    instance.jobmaterial.save()
    instance.allote.save()

@receiver(post_delete, sender=JobMaterialStatus)
def jobmaterialstatus_is_delete(sender, instance,  **kwargs):
    instance.jobmaterial.save()
    instance.allote.save()