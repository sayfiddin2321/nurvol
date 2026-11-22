from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

class Project(models.Model):
    class ProjectType(models.TextChoices):
        HOUSE = "house", "Uy"
        APARTMENT = "apartment", "Kvartira"
        OFFICE = "office", "Ofis"
        SHOP = "shop", "Do'kon"
        INDUSTRIAL = "industrial", "Sanoat"
        OTHER = "other", "Boshqa"

    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        IN_PROGRESS = "in_progress", "Jarayonda"
        COMPLETED = "completed", "Tugallangan"
        ARCHIVED = "archived", "Arxivlangan"

    electrician = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="projects"
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="client_projects"
    )
    name = models.CharField(max_length=200)
    project_type = models.CharField(max_length=20, choices=ProjectType.choices, default=ProjectType.HOUSE, db_index=True)
    description = models.TextField(blank=True)
    work_summary = models.CharField(max_length=500, blank=True)
    address = models.CharField(max_length=255, blank=True)
    building_type = models.CharField(max_length=100, blank=True)
    floors_count = models.PositiveSmallIntegerField(default=1)
    start_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    is_public = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.start_date and self.completion_date and self.completion_date < self.start_date:
            raise ValidationError("Tugash sanasi boshlanish sanasidan oldin bo'lmaydi.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectShowcaseSettings(models.Model):
    featured_electrician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        limit_choices_to={"role": "electrician"},
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "bosh sahifa ishlari"
        verbose_name_plural = "bosh sahifa ishlari"

    def __str__(self):
        return "Bosh sahifa ishlari"

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings


def showcase_video_upload_path(instance, filename):
    return f"showcase/videos/{instance.pk or 'new'}-{filename}"


class ShowcaseVideo(models.Model):
    title = models.CharField(max_length=150)
    description = models.CharField(max_length=300, blank=True)
    video = models.FileField(
        upload_to=showcase_video_upload_path,
        blank=True,
        help_text="MP4 yoki WebM formatidagi video.",
    )
    video_url = models.URLField(
        blank=True,
        help_text="YouTube yoki boshqa to'g'ridan-to'g'ri video havolasi.",
    )
    poster = models.ImageField(
        upload_to="showcase/posters/",
        blank=True,
        help_text="Video uchun katta poster/cover rasmi.",
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at"]
        verbose_name = "bosh sahifa videosi"
        verbose_name_plural = "bosh sahifa videolari"

    def __str__(self):
        return self.title

    def clean(self):
        if not self.video and not self.video_url:
            raise ValidationError("Video faylini yoki video havolasini kiriting.")

    @property
    def youtube_embed_url(self):
        if not self.video_url:
            return ""
        url = self.video_url.strip()
        video_id = ""
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/", 1)[1].split("?", 1)[0]
        elif "youtube.com/watch" in url:
            from urllib.parse import parse_qs, urlparse
            video_id = parse_qs(urlparse(url).query).get("v", [""])[0]
        elif "youtube.com/embed/" in url:
            video_id = url.split("youtube.com/embed/", 1)[1].split("?", 1)[0]
        return f"https://www.youtube.com/embed/{video_id}" if video_id else ""


class Floor(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="floors")
    name = models.CharField(max_length=100)
    floor_number = models.IntegerField(default=1)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["floor_number"]
        constraints = [
            models.UniqueConstraint(fields=["project", "floor_number"], name="unique_floor_number_per_project")
        ]

    def __str__(self):
        return f"{self.project.name} - {self.name}"


class Room(models.Model):
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=100)
    room_type = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.floor.name} - {self.name}"