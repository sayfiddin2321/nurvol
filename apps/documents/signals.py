import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import ProjectImage, ProjectDocument

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=ProjectImage)
@receiver(post_delete, sender=ProjectDocument)
def delete_project_files(sender, instance, **kwargs):
    fields = (instance.image, instance.thumbnail, instance.display_image) if sender is ProjectImage else (instance.file,)
    files = [(field.storage, field.name) for field in fields if field]

    def cleanup():
        for storage, name in files:
            try:
                storage.delete(name)
            except OSError:
                logger.exception("Unable to remove project media: %s", name)

    transaction.on_commit(cleanup)
