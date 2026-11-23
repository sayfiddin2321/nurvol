import os
from io import BytesIO
from tempfile import NamedTemporaryFile

from PIL import Image, features
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from apps.documents.models import ProjectImage
from apps.documents.services import build_image_thumbnail, DISPLAY_SIZE


class Command(BaseCommand):
    help = "Check upload encoding, temporary files and media write/read/delete permissions. Run as the Gunicorn user."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--project-id", type=int, required=True, help="ID of the project whose upload failed; no database records are changed.")

    def handle(self, *args, **options):
        if options["project_id"] < 1:
            raise CommandError("--project-id must be a positive integer.")
        self.stdout.write(f"MEDIA_ROOT={settings.MEDIA_ROOT}")
        if hasattr(os, "geteuid"):
            self.stdout.write(f"Effective uid={os.geteuid()} (must match the Gunicorn service user)")
        self.stdout.write(f"Pillow WebP={features.check('webp')}")
        failures = []
        try:
            with NamedTemporaryFile(dir=settings.FILE_UPLOAD_TEMP_DIR) as temporary:
                temporary.write(b"upload-check")
                temporary.flush()
            self.stdout.write("OK: upload temporary directory")
        except OSError as exc:
            failures.append(f"Upload temporary directory: {exc}")

        buffer = BytesIO()
        Image.new("RGB", (16, 16), "blue").save(buffer, format="JPEG")
        original = ContentFile(buffer.getvalue(), name="upload-check.jpg")
        image = ProjectImage(project_id=options["project_id"])
        for field_name in ("image", "thumbnail", "display_image"):
            stored_name = None
            field = ProjectImage._meta.get_field(field_name)
            try:
                content = original if field_name == "image" else build_image_thumbnail(
                    original, DISPLAY_SIZE if field_name == "display_image" else (720, 720),
                )
                content.seek(0)
                expected = content.read()
                content.seek(0)
                name = field.generate_filename(image, content.name)
                stored_name = field.storage.save(name, content)
                with field.storage.open(stored_name, "rb") as stored:
                    if stored.read() != expected:
                        raise OSError("Stored bytes differ from the uploaded image")
                self.stdout.write(f"OK: {field_name} write/read ({stored_name})")
            except Exception as exc:
                failures.append(f"{field_name}: {type(exc).__name__}: {exc}")
            finally:
                if stored_name:
                    try:
                        field.storage.delete(stored_name)
                    except Exception as exc:
                        failures.append(f"{field_name} cleanup ({stored_name}): {exc}")
        if failures:
            raise CommandError("Upload storage check failed:\n" + "\n".join(failures))
        self.stdout.write(self.style.SUCCESS("Upload storage OK; diagnostic files removed. No database records changed."))
