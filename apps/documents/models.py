from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from pathlib import Path
from uuid import uuid4


def image_upload_path(instance, filename):
    return f"projects/{instance.project_id}/images/{uuid4().hex}{Path(filename).suffix.lower()}"


def document_upload_path(instance, filename):
    return f"projects/{instance.project_id}/documents/{uuid4().hex}{Path(filename).suffix.lower()}"


def validate_file_size(file):
    max_mb = 20
    if file.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Fayl hajmi {max_mb} MB dan oshmasligi kerak.")


class ProjectImage(models.Model):
    class Category(models.TextChoices):
        FLOOR_PLAN = "floor_plan", "Qavat rejasi"
        CIRCUIT = "circuit", "Elektr zanjiri / sxema"
        BEFORE = "before", "Ishdan oldin"
        PROCESS = "process", "Jarayon"
        CABLES = "cables", "Kabel yo'nalishlari"
        PANEL = "panel", "Elektr shit"
        DEVICE = "device", "Elektr qurilma"
        FINAL = "final", "Yakuniy natija"
        OTHER = "other", "Boshqa"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=image_upload_path, validators=[validate_file_size])
    thumbnail = models.ImageField(upload_to="projects/thumbnails/", blank=True)
    display_image = models.ImageField(upload_to="projects/previews/", blank=True)
    title = models.CharField(max_length=150, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at", "pk"]

    @property
    def caption(self):
        return self.title or self.description or self.get_category_display()


class ProjectDocument(models.Model):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to=document_upload_path, validators=[validate_file_size])
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_video(self):
        return Path(self.file.name).suffix.lower() in {".mp4", ".webm"}


class ProjectRevision(models.Model):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="revisions")
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    revision_number = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-revision_number"]
        constraints = [
            models.UniqueConstraint(fields=["project", "revision_number"], name="unique_project_revision")
        ]

    def __str__(self):
        return f"{self.project.name} - V{self.revision_number}"
