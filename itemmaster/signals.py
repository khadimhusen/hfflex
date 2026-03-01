from django.db.models.signals import post_save
from .models import RawMaterial, ItemMaster
from django.dispatch import receiver


@receiver(post_save, sender=RawMaterial)
def rawmaterial_is_created(sender, instance, **kwargs):
    instance.itemmaster.save()
