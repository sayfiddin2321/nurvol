from io import BytesIO, StringIO
import errno
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape

from apps.test_utils import consume_response

from apps.accounts.models import User
from apps.projects.models import Project
from apps.qrcodes.models import QRCode
from .forms import ProjectImageForm, ProjectDocumentForm
from .models import ProjectImage, ProjectDocument
from .services import save_project_image


def photo(name="image.jpg", size=(1200, 600), exif=None):
    buffer = BytesIO()
    kwargs = {"exif": exif} if exif else {}
    Image.new("RGB", size, "#2563eb").save(buffer, "JPEG", **kwargs)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


class GalleryWorkflowTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_dir = TemporaryDirectory()
        cls.addClassCleanup(cls.media_dir.cleanup)
        cls.override = override_settings(MEDIA_ROOT=cls.media_dir.name)
        cls.override.enable()
        cls.addClassCleanup(cls.override.disable)

    def setUp(self):
        self.owner = User.objects.create_user(username="gallery-owner", role="electrician")
        self.other = User.objects.create_user(username="gallery-other", role="electrician")
        self.project = Project.objects.create(electrician=self.owner, name="Gallery", is_public=True)
        self.client.force_login(self.owner)
        self.upload_url = reverse("documents:image_upload", args=[self.project.pk])

    def test_multiple_uploads_need_only_images_and_optional_description(self):
        response = self.client.post(self.upload_url, {
            "images": [photo("landscape.jpg"), photo("portrait.jpg", (400, 1200))],
            "description": "Montaj rasmlari",
        })
        self.assertRedirects(response, f"{reverse('projects:detail', args=[self.project.pk])}#tab-images")
        images = list(self.project.images.all())
        self.assertEqual(len(images), 2)
        self.assertTrue(all(image.description == "Montaj rasmlari" for image in images))
        self.assertTrue(all(image.category == "other" for image in images))
        self.assertEqual(self.project.revisions.count(), 2)
        for image in images:
            self.assertTrue(image.thumbnail)
            self.assertTrue(image.display_image)
            self.assertNotIn("landscape", image.image.name)
        self.client.logout()
        qr = QRCode.objects.get(project=self.project, panel=None)
        response = self.client.get(reverse("qrcodes:public", args=[qr.token]))
        self.assertEqual(len(response.context["gallery_page"]), 2)
        self.assertContains(response, "Montaj rasmlari")
        for image in images:
            for route in ["image_view", "image_thumbnail", "image_display"]:
                response = self.client.get(reverse("documents:" + route, args=[image.pk]))
                self.assertEqual(response.status_code, 200)
                consume_response(response)


    def test_large_original_is_preserved_while_preview_is_bounded(self):
        uploaded = photo(size=(3600, 1800))
        original = uploaded.read()
        uploaded.seek(0)
        image = save_project_image(self.project, uploaded, "circuit", self.owner)
        with image.image.open("rb") as file:
            self.assertEqual(file.read(), original)
        with image.thumbnail.open("rb") as file, Image.open(file) as thumbnail:
            self.assertEqual(thumbnail.size, (720, 360))
        with image.display_image.open("rb") as file, Image.open(file) as preview:
            self.assertEqual(preview.size, (2560, 1280))

    def test_exif_rotation_is_applied_to_thumbnail_and_metadata_is_removed(self):
        exif = Image.Exif()
        exif[274] = 6
        image = save_project_image(self.project, photo(size=(900, 450), exif=exif), "before", self.owner)
        with image.thumbnail.open("rb") as file, Image.open(file) as thumbnail:
            self.assertEqual(thumbnail.size, (360, 720))
            self.assertFalse(thumbnail.getexif())

    def test_any_invalid_file_prevents_partial_upload(self):
        response = self.client.post(self.upload_url, {
            "images": [photo(), SimpleUploadedFile("fake.jpg", b"not an image", content_type="image/jpeg")],
            "category": "other",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.project.images.exists())
        self.assertFalse(self.project.revisions.exists())

    def test_invalid_caption_and_oversized_batch_are_rejected(self):
        response = self.client.post(self.upload_url, {"images": [photo()], "category": "other", "description": "x" * 256})
        self.assertEqual(response.status_code, 200)
        self.assertIn("description", response.context["form"].errors)
        response = self.client.post(self.upload_url, {"images": [photo(f"{i}.jpg", (2, 2)) for i in range(21)], "category": "other"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.project.images.exists())

    def test_pixel_limit_rejects_images_before_derivative_generation(self):
        with patch("apps.documents.services.MAX_IMAGE_PIXELS", 100):
            response = self.client.post(self.upload_url, {"images": [photo(size=(11, 10))], "category": "other"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.project.images.exists())

    def test_storage_error_rolls_back_images_revisions_and_files(self):
        from . import views
        self.project.is_public = False
        self.project.save()
        original = views.save_project_image
        paths_before = set(Path(self.media_dir.name).rglob("*"))
        def second_fails(*args, **kwargs):
            if self.project.images.exists():
                raise OSError("Storage unavailable")
            return original(*args, **kwargs)
        with patch.object(views, "save_project_image", side_effect=second_fails):
            response = self.client.post(self.upload_url, {"images": [photo("one.jpg"), photo("two.jpg")], "category": "other"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.project.images.exists())
        self.assertFalse(self.project.revisions.exists())
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_public)
        added_files = [p for p in set(Path(self.media_dir.name).rglob("*")) - paths_before if p.is_file()]
        self.assertEqual(added_files, [])

    def test_missing_webp_support_uploads_and_serves_png_variants(self):
        with patch("apps.documents.services.features.check", return_value=False):
            response = self.client.post(self.upload_url, {"images": [photo()]})
        self.assertEqual(response.status_code, 302)
        image = self.project.images.get()
        for field, route in [(image.thumbnail, "image_thumbnail"), (image.display_image, "image_display")]:
            self.assertTrue(field.name.endswith(".png"))
            response = self.client.get(reverse("documents:" + route, args=[image.pk]))
            try:
                self.assertEqual(response["Content-Type"], "image/png")
                with Image.open(BytesIO(b"".join(response.streaming_content))) as variant:
                    self.assertEqual(variant.format, "PNG")
            finally:
                consume_response(response)

    def test_permission_and_disk_failures_show_actionable_errors(self):
        for error, message in [
            (PermissionError(errno.EACCES, "Permission denied"), "yozish ruxsati yo'q"),
            (OSError(errno.EROFS, "Read-only filesystem"), "yozish ruxsati yo'q"),
            (OSError(errno.ENOSPC, "No space left"), "disk kvotasi yetarli emas"),
        ]:
            with self.subTest(error=error):
                with patch("apps.documents.views.save_project_image", side_effect=error):
                    response = self.client.post(self.upload_url, {"images": [photo()]})
                self.assertContains(response, escape(message))
                self.assertFalse(self.project.images.exists())

    def test_cleanup_failure_does_not_hide_original_storage_error(self):
        original_save = FileSystemStorage.save

        def fail_thumbnail(storage, name, content, **kwargs):
            if name.replace("\\", "/").startswith("projects/thumbnails/"):
                raise OSError(errno.ENOSPC, "No space left")
            return original_save(storage, name, content, **kwargs)

        with patch.object(FileSystemStorage, "save", autospec=True, side_effect=fail_thumbnail), patch.object(
            FileSystemStorage, "delete", side_effect=PermissionError(errno.EACCES, "Cleanup denied")
        ):
            response = self.client.post(self.upload_url, {"images": [photo()]})
        self.assertContains(response, "disk kvotasi yetarli emas")
        self.assertFalse(self.project.images.exists())
        self.assertFalse(self.project.revisions.exists())

    def test_storage_diagnostic_checks_actual_project_and_cleans_test_files(self):
        before = {path for path in Path(self.media_dir.name).rglob("*") if path.is_file()}
        output = StringIO()
        call_command("check_upload_storage", project_id=self.project.pk, stdout=output)
        self.assertIn("Upload storage OK", output.getvalue())
        self.assertIn(f"projects/{self.project.pk}/images/", output.getvalue())
        self.assertEqual(before, {path for path in Path(self.media_dir.name).rglob("*") if path.is_file()})
        self.assertFalse(self.project.images.exists())

    def test_storage_diagnostic_exposes_permission_failure(self):
        storage = ProjectImage._meta.get_field("image").storage
        with patch.object(storage, "save", side_effect=PermissionError(errno.EACCES, "Permission denied")):
            with self.assertRaisesMessage(CommandError, "Permission denied"):
                call_command("check_upload_storage", project_id=self.project.pk, stdout=StringIO())

    def test_upload_automatically_shares_legacy_project_and_preserves_printed_qr(self):
        self.project.is_public = False
        self.project.save()
        qr = QRCode.objects.create(project=self.project, is_active=False)
        token = qr.token
        for name in ["first.jpg", "second.jpg"]:
            response = self.client.post(self.upload_url, {"images": [photo(name)]})
            self.assertEqual(response.status_code, 302)
            qr.refresh_from_db()
            self.assertEqual(qr.token, token)
            self.assertTrue(qr.is_active)
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_public)
        self.assertEqual(self.project.qr_codes.count(), 1)
        self.client.logout()
        response = self.client.get(reverse("qrcodes:public", args=[token]))
        self.assertEqual(len(response.context["gallery_page"]), 2)

    def test_another_electrician_cannot_upload_or_publish_a_private_project(self):
        self.project.is_public = False
        self.project.save()
        self.client.force_login(self.other)
        response = self.client.post(self.upload_url, {"images": [photo()]})
        self.assertEqual(response.status_code, 403)
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_public)
        self.assertFalse(self.project.images.exists())

    def test_image_edit_and_delete_are_owned_and_remove_all_variants(self):
        image = save_project_image(self.project, photo(), "other", self.owner)
        self.client.force_login(self.other)
        for action in ["image_edit", "image_delete"]:
            response = self.client.post(reverse("documents:" + action, args=[image.pk]), {"title": "Unauthorized", "category": "other"})
            self.assertEqual(response.status_code, 403)
        self.client.force_login(self.owner)
        self.client.post(reverse("documents:image_edit", args=[image.pk]), {"title": "Changed", "description": "New caption", "category": "panel", "is_public": "on"})
        image.refresh_from_db()
        self.assertEqual(image.title, "Changed")
        self.assertEqual(image.description, "New caption")
        self.assertEqual(image.caption, "Changed")
        files = [Path(field.path) for field in (image.image, image.thumbnail, image.display_image)]
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("documents:image_delete", args=[image.pk]))
        self.assertFalse(ProjectImage.objects.filter(pk=image.pk).exists())
        self.assertTrue(all(not path.exists() for path in files))

    def test_images_are_accessible_to_visitors_and_private_projects_are_denied(self):
        image = save_project_image(self.project, photo(), "other", self.owner)
        self.client.force_login(self.other)
        for route in ["image_view", "image_thumbnail", "image_display"]:
            response = self.client.get(reverse("documents:" + route, args=[image.pk]))
            self.assertEqual(response.status_code, 200)
            consume_response(response)
        self.project.is_public = False
        self.project.save()
        for route in ["image_view", "image_thumbnail", "image_display"]:
            self.assertEqual(self.client.get(reverse("documents:" + route, args=[image.pk])).status_code, 403)
        self.assertEqual(self.client.get("/media/" + image.image.name).status_code, 404)

    def test_public_gallery_paginates_all_uploaded_images(self):
        for index in range(27):
            ProjectImage.objects.create(project=self.project, image=f"projects/{index}.jpg", title=f"Photo {index}")
        qr = QRCode.objects.create(project=self.project)
        self.client.logout()
        response = self.client.get(reverse("qrcodes:public", args=[qr.token]))
        self.assertEqual(len(response.context["gallery_page"]), 24)
        self.assertNotContains(response, "Photo 26")
        response = self.client.get(reverse("qrcodes:public", args=[qr.token]), {"photos": 2})
        self.assertEqual(len(response.context["gallery_page"]), 3)
        self.assertContains(response, "Photo 26")

    def test_video_has_permission_checked_byte_range_playback(self):
        data = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100
        form = ProjectDocumentForm({"title": "Montaj video", "is_public": "on"}, {"file": SimpleUploadedFile("clip.mp4", data, content_type="video/mp4")})
        self.assertTrue(form.is_valid(), form.errors)
        doc = ProjectDocument.objects.create(project=self.project, title="Video", file=form.cleaned_data["file"], uploaded_by=self.owner, is_public=True)
        self.client.logout()
        response = self.client.get(reverse("documents:document_preview", args=[doc.pk]), HTTP_RANGE="bytes=4-11")
        try:
            self.assertEqual(response.status_code, 206)
            self.assertEqual(b"".join(response.streaming_content), data[4:12])
            self.assertEqual(response["Content-Type"], "video/mp4")
        finally:
            consume_response(response)
        self.assertEqual(self.client.get(reverse("documents:document_preview", args=[doc.pk]), HTTP_RANGE="bytes=9999-").status_code, 416)
        doc.is_public = False
        doc.save()
        self.assertEqual(self.client.get(reverse("documents:document_preview", args=[doc.pk])).status_code, 403)
