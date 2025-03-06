import os

from django.db.models.signals import pre_save, pre_delete, post_save
from django.dispatch import receiver

from .models import ImagenPost
from core.utils import eliminar_imagenes


@receiver(pre_save, sender=ImagenPost)
def pre_save_eliminar_imagen_antigua(sender, instance, **kwargs):
    eliminar_imagenes(sender, instance, ['imagen'])

@receiver(pre_delete, sender=ImagenPost)
def pre_delete_eliminar_imagen(sender, instance, **kwargs):
    eliminar_imagenes(sender, instance, ['imagen'], delete=True)

