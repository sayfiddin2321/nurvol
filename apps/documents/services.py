from io import BytesIO
from pathlib import Path
import logging
import warnings
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction

from .models import ProjectDocument, ProjectImage
from apps.projects.services import create_revision


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
THUMBNAIL_SIZE = (720, 720)
DISPLAY_SIZE = (2560, 2560)
MAX_IMAGE_PIXELS = 40_000_000
logger = logging.getLogger(__name__)


def build_image_thumbnail(uploaded_file, size=THUMBNAIL_SIZE, quality=78):
    uploaded_file.seek(0)
    with Image.open(uploaded_file) as source:
        image = ImageOps.exif_transpose(source)
        image.thumbnail(size, Image.Resampling.LANCZOS)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="WEBP", quality=quality, method=4)
    uploaded_file.seek(0)
    name = f"{uuid4().hex}.webp"
    return ContentFile(buffer.getvalue(), name=name)


def ensure_image_thumbnail(image):
    if not image.thumbnail:
        with image.image.open("rb") as source:
            thumbnail = build_image_thumbnail(source)
        image.thumbnail.save(thumbnail.name, thumbnail, save=False)
        image.save(update_fields=["thumbnail"])
    return image.thumbnail


def ensure_display_image(image):
    if not image.display_image:
        with image.image.open("rb") as source:
            preview = build_image_thumbnail(source, DISPLAY_SIZE, quality=90)
        image.display_image.save(preview.name, preview, save=False)
        image.save(update_fields=["display_image"])
    return image.display_image


def validate_image_file(uploaded_file):
    if uploaded_file.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Rasm hajmi 20 MB dan oshmasligi kerak.")
    if Path(uploaded_file.name).suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("Faqat JPG, PNG yoki WebP rasmlarni yuklash mumkin.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(uploaded_file) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValidationError("Rasm formati qo'llab-quvvatlanmaydi.")
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValidationError("Rasm 40 megapikseldan oshmasligi kerak.")
                image.verify()
            uploaded_file.seek(0)
            with Image.open(uploaded_file) as image:
                image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        logger.warning("Invalid image upload rejected: %s", type(exc).__name__)
        raise ValidationError("Yuklangan fayl haqiqiy rasm emas.") from exc
    finally:
        uploaded_file.seek(0)


def save_project_image(project, uploaded_file, category, user, description="", title=""):
    validate_image_file(uploaded_file)
    thumbnail = build_image_thumbnail(uploaded_file)
    preview = build_image_thumbnail(uploaded_file, DISPLAY_SIZE, quality=90)
    image = ProjectImage(
        project=project,
        image=uploaded_file,
        thumbnail=thumbnail,
        display_image=preview,
        title=title,
        category=category,
        uploaded_by=user,
        description=description,
    )
    image.full_clean()
    try:
        with transaction.atomic():
            image.save()
            create_revision(project, user, "Rasm qo'shildi", image.description or image.category)
    except Exception:
        for field in (image.image, image.thumbnail, image.display_image):
            if field and field._committed:
                field.delete(save=False)
        raise
    return image


def save_project_document(project, document, user):
    instance = ProjectDocument(
        project=project,
        uploaded_by=user,
        **document.cleaned_data,
    )
    instance.full_clean()
    try:
        with transaction.atomic():
            instance.save()
            create_revision(project, user, "Hujjat qo'shildi", instance.title)
    except Exception:
        if instance.file and instance.file._committed:
            instance.file.delete(save=False)
        raise
    return instance
