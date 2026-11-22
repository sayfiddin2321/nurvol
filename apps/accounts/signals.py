from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User
from apps.electricians.models import ElectricianProfile

@receiver(post_save, sender=User)
def create_electrician_profile(sender, instance, created, **kwargs):
    if created and instance.role == User.Role.ELECTRICIAN:
        ElectricianProfile.objects.get_or_create(user=instance)