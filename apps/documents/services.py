from io import BytesIO
import hashlib
from pathlib import Path
import logging
import warnings
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError, features
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
        # Some Linux Pillow builds do not include libwebp. PNG preserves alpha
        # and avoids making every JPEG/PNG upload depend on that optional codec.
        if features.check("webp"):
            image.save(buffer, format="WEBP", quality=quality, method=4)
            extension = "webp"
        else:
            image.save(buffer, format="PNG")
            extension = "png"
    uploaded_file.seek(0)
    name = f"{uuid4().hex}.{extension}"
    return ContentFile(buffer.getvalue(), name=name)


def cleanup_uploaded_files(fields):
    """Attempt every rollback deletion without hiding the original failure."""
    for field in fields:
        if field and field._committed:
            try:
                field.delete(save=False)
            except OSError:
                logger.exception("Unable to clean up failed upload: %s", field.name)


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


def save_project_image(project, uploaded_file, category, user, description="", title="", content_sha256="", upload_token=None):
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
        content_sha256=content_sha256,
        upload_token=upload_token,
    )
    image.full_clean()
    try:
        with transaction.atomic():
            image.save()
            create_revision(project, user, "Rasm qo'shildi", image.description or image.category)
    except Exception:
        cleanup_uploaded_files((image.image, image.thumbnail, image.display_image))
        raise
    return image


def save_project_document(project, document, user, **extra):
    instance = ProjectDocument(
        project=project,
        uploaded_by=user,
        **document.cleaned_data,
        **extra,
    )
    instance.full_clean()
    try:
        with transaction.atomic():
            instance.save()
            create_revision(project, user, "Hujjat qo'shildi", instance.title)
    except Exception:
        cleanup_uploaded_files((instance.file,))
        raise
    return instance


def file_sha256(file):
    digest = hashlib.sha256()
    try:
        file.seek(0)
        for chunk in file.chunks():
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        file.seek(0)


def save_project_media(project, uploaded_file, category, user, title="", description="", upload_token=None):
    """Serialize gallery writes, deduplicate content and make retries idempotent."""
    from django.core.exceptions import PermissionDenied
    from apps.projects.models import Project
    from apps.projects.services import user_can_edit_project
    from apps.qrcodes.services import get_or_create_building_qr
    from .forms import ProjectDocumentForm

    is_video = Path(uploaded_file.name).suffix.lower() in {".mp4", ".webm"}
    model = ProjectDocument if is_video else ProjectImage
    digest = file_sha256(uploaded_file)
    saved = None
    created = False
    try:
        with transaction.atomic():
            locked = Project.objects.select_for_update().get(pk=project.pk)
            if not user_can_edit_project(user, locked):
                raise PermissionDenied("Ruxsat yo'q.")
            existing = model.objects.filter(project=locked)
            if upload_token:
                other_model = ProjectImage if is_video else ProjectDocument
                if other_model.objects.filter(project=locked, upload_token=upload_token).exists():
                    raise ValidationError("Bu yuklash so'rovi boshqa fayl uchun ishlatilgan. Faylni qayta tanlang.")
                saved = existing.filter(upload_token=upload_token).first()
                if saved and saved.content_sha256 != digest:
                    raise ValidationError("Bu yuklash so'rovi boshqa fayl uchun ishlatilgan. Faylni qayta tanlang.")
            if saved is None:
                saved = existing.filter(content_sha256=digest).first()
            # Older uploads have no fingerprint. Match them before creating a copy.
            if saved is None:
                for previous in existing.filter(content_sha256="").iterator():
                    field = previous.file if is_video else previous.image
                    try:
                        with field.open("rb") as source:
                            matches = file_sha256(source) == digest
                    except OSError:
                        logger.warning("Unable to fingerprint existing %s %s", model.__name__, previous.pk, exc_info=True)
                        continue
                    if matches:
                        previous.content_sha256 = digest
                        previous.save(update_fields=["content_sha256"])
                        saved = previous
                        break
            if saved is None:
                if is_video:
                    form = ProjectDocumentForm(
                        {"title": title or Path(uploaded_file.name).stem[:150], "description": description, "is_public": True},
                        {"file": uploaded_file},
                    )
                    if not form.is_valid():
                        raise ValidationError(form.errors.get("file", ["Video ma'lumotlari noto'g'ri."]))
                    saved = save_project_document(locked, form, user, category=category, content_sha256=digest, upload_token=upload_token)
                else:
                    saved = save_project_image(locked, uploaded_file, category, user, description, title, digest, upload_token)
                created = True
            if not locked.is_public:
                locked.is_public = True
                locked.save(update_fields=["is_public", "updated_at"])
            qr = get_or_create_building_qr(locked)
            if not qr.is_active:
                qr.is_active = True
                qr.save(update_fields=["is_active"])
        return saved, created
    except Exception:
        if created and saved:
            cleanup_uploaded_files((saved.file,) if is_video else (saved.image, saved.thumbnail, saved.display_image))
        raise
