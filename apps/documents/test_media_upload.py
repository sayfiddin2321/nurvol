import errno
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape

from apps.accounts.models import User
from apps.projects.models import Project
from apps.qrcodes.models import QRCode
from apps.test_utils import consume_response
from .models import ProjectDocument, ProjectImage


def photo(color="blue", name="panel.jpg"):
    data = BytesIO()
    Image.new("RGB", (80, 60), color).save(data, "JPEG")
    return SimpleUploadedFile(name, data.getvalue(), content_type="image/jpeg")


def video():
    return SimpleUploadedFile("panel.mp4", b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100, content_type="video/mp4")


class MediaUploadTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.directory = TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.settings_override = override_settings(MEDIA_ROOT=cls.directory.name)
        cls.settings_override.enable()
        cls.addClassCleanup(cls.settings_override.disable)

    def setUp(self):
        self.owner = User.objects.create_user(username="media-owner", role="electrician")
        self.other = User.objects.create_user(username="media-other", role="electrician")
        self.project = Project.objects.create(name="Media project", electrician=self.owner)
        self.url = reverse("documents:media_upload", args=[self.project.pk])
        self.client.force_login(self.owner)

    def upload(self, file=None, **values):
        data = {"file": file if file is not None else photo(), "upload_token": uuid4(), "category": "panel", "title": "1-shit", "description": ""}
        data.update(values)
        return self.client.post(self.url, data)

    def test_panel_name_and_optional_comment_are_saved_separately(self):
        response = self.upload(description="")
        self.assertEqual(response.status_code, 201, response.content)
        image = self.project.images.get()
        self.assertEqual((image.title, image.description, image.category), ("1-shit", "", "panel"))
        self.assertEqual(len(image.content_sha256), 64)
        self.assertEqual(image.uploaded_by, self.owner)
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_public)
        self.assertEqual(self.project.revisions.count(), 1)
        qr = QRCode.objects.get(project=self.project)
        self.client.logout()
        response = self.client.get(reverse("qrcodes:public", args=[qr.token]))
        self.assertEqual(response.context["gallery_page"].paginator.count, 0)
        self.assertEqual(response.context["panel_gallery_page"].paginator.count, 1)
        self.assertContains(response, "1-shit")

    def test_each_general_image_has_its_own_name_comment_and_category(self):
        self.assertEqual(self.upload(photo("red"), title="Xona", description="Birinchi izoh", category="room").status_code, 201)
        self.assertEqual(self.upload(photo("green"), title="Kabel", description="", category="cables").status_code, 201)
        images = list(self.project.images.all())
        self.assertEqual([(item.title, item.description, item.category) for item in images], [("Xona", "Birinchi izoh", "room"), ("Kabel", "", "cables")])

    def test_repeated_request_and_same_content_with_new_token_do_not_duplicate(self):
        token = uuid4()
        first = self.upload(upload_token=token)
        self.assertEqual(first.status_code, 201)
        for next_token in [token, uuid4()]:
            response = self.upload(upload_token=next_token)
            self.assertEqual(response.status_code, 200, response.content)
            self.assertFalse(response.json()["created"])
            self.assertEqual(response.json()["id"], first.json()["id"])
        self.assertEqual(self.project.images.count(), 1)
        self.assertEqual(self.project.revisions.count(), 1)

    def test_legacy_image_is_recognized_without_changing_its_metadata(self):
        existing = ProjectImage.objects.create(project=self.project, image=photo(), title="Eski nom", description="Eski izoh")
        response = self.upload(title="Yangi nom")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], existing.pk)
        existing.refresh_from_db()
        self.assertEqual(existing.title, "Eski nom")
        self.assertEqual(existing.description, "Eski izoh")
        self.assertEqual(len(existing.content_sha256), 64)

    def test_request_token_cannot_be_reused_for_different_image_or_video(self):
        token = uuid4()
        self.upload(upload_token=token)
        for file in [photo("red"), video()]:
            response = self.upload(file, upload_token=token)
            self.assertEqual(response.status_code, 400)
            self.assertIn("boshqa fayl", response.json()["error"])
        self.assertEqual(self.project.images.count(), 1)
        self.assertEqual(self.project.documents.count(), 0)

    def test_same_file_in_different_projects_is_allowed(self):
        self.assertEqual(self.upload().status_code, 201)
        other_project = Project.objects.create(name="Other project", electrician=self.owner)
        self.url = reverse("documents:media_upload", args=[other_project.pk])
        self.assertEqual(self.upload().status_code, 201)
        self.assertEqual(ProjectImage.objects.count(), 2)

    def test_database_rejects_duplicate_fingerprints(self):
        self.upload()
        image = self.project.images.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProjectImage.objects.create(project=self.project, image="unused.jpg", content_sha256=image.content_sha256)

    def test_video_uses_existing_storage_and_range_endpoint_and_can_be_edited(self):
        token = uuid4()
        response = self.upload(video(), upload_token=token, title="2-shit", description="Yig'ish jarayoni")
        self.assertEqual(response.status_code, 201, response.content)
        document = self.project.documents.get()
        self.assertTrue(document.is_video)
        self.assertTrue(document.is_public)
        self.assertEqual(document.category, "panel")
        self.assertEqual(self.upload(video(), upload_token=token).status_code, 200)
        self.assertEqual(self.project.documents.count(), 1)
        response = self.client.post(reverse("documents:document_edit", args=[document.pk]), {"title": "Qavat shiti", "description": ""})
        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual((document.title, document.description), ("Qavat shiti", ""))
        self.client.logout()
        response = self.client.get(reverse("documents:document_preview", args=[document.pk]), HTTP_RANGE="bytes=4-11")
        try:
            self.assertEqual(response.status_code, 206)
            self.assertEqual(b"".join(response.streaming_content), b"ftypisom")
        finally:
            consume_response(response)

    def test_blank_image_title_and_comment_can_be_saved_and_later_cleared(self):
        self.assertEqual(self.upload(title="", description="").status_code, 201)
        image = self.project.images.get()
        edit = reverse("documents:image_edit", args=[image.pk])
        self.client.post(edit, {"title": "Yangi nom", "description": "Alohida izoh"})
        image.refresh_from_db()
        self.assertEqual((image.title, image.description), ("Yangi nom", "Alohida izoh"))
        response = self.client.post(edit, {"title": "", "description": ""})
        self.assertEqual(response.status_code, 302)
        image.refresh_from_db()
        self.assertEqual((image.title, image.description), ("", ""))

    def test_unauthorized_users_and_missing_csrf_cannot_upload(self):
        self.client.force_login(self.other)
        self.assertEqual(self.upload().status_code, 403)
        self.assertFalse(self.project.images.exists())
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        self.assertEqual(csrf_client.post(self.url, {"file": photo()}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.upload().status_code, 302)

    def test_invalid_files_metadata_and_missing_token_return_clear_json_errors(self):
        for data in [
            {"file": SimpleUploadedFile("fake.jpg", b"not an image")},
            {"file": SimpleUploadedFile("fake.mp4", b"not a video")},
            {"description": "x" * 256},
            {"category": "forged"},
            {"upload_token": ""},
        ]:
            response = self.upload(**data)
            self.assertEqual(response.status_code, 400, response.content)
            self.assertFalse(response.json()["ok"])
            self.assertTrue(response.json()["error"])
        self.assertFalse(self.project.images.exists())
        self.assertFalse(self.project.documents.exists())

    def test_storage_failure_preserves_no_rows_and_retry_succeeds(self):
        token = uuid4()
        with patch("apps.documents.services.build_image_thumbnail", side_effect=PermissionError(errno.EACCES, "private/path")):
            response = self.upload(upload_token=token)
        self.assertEqual(response.status_code, 503)
        self.assertIn("yozish ruxsati", response.json()["error"])
        self.assertNotIn("private/path", response.json()["error"])
        self.assertFalse(self.project.images.exists())
        self.assertEqual(self.upload(upload_token=token).status_code, 201)

    def test_qr_failure_rolls_back_image_files_and_publication(self):
        before = {path for path in Path(self.directory.name).rglob("*") if path.is_file()}
        with patch("apps.qrcodes.services.get_or_create_building_qr", side_effect=OSError("QR unavailable")):
            self.assertEqual(self.upload().status_code, 503)
        self.assertFalse(self.project.images.exists())
        self.assertFalse(self.project.revisions.exists())
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_public)
        self.assertEqual(before, {path for path in Path(self.directory.name).rglob("*") if path.is_file()})

    def test_native_batch_form_supports_both_sections_and_video_without_javascript(self):
        response = self.client.post(reverse("documents:image_upload", args=[self.project.pk]), {
            "upload_version": "2", "general_files": [photo("red")], "panel_files": [photo("blue"), video()],
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.project.images.count(), 2)
        self.assertEqual(self.project.images.filter(category="panel").count(), 1)
        self.assertEqual(self.project.documents.filter(category="panel").count(), 1)

    def test_galleries_paginate_independently_and_private_videos_are_not_exposed(self):
        for category in ["other", "panel"]:
            for index in range(25):
                ProjectImage.objects.create(project=self.project, image=f"unused-{category}-{index}.jpg", category=category, title=f"{category}-{index}")
        private = ProjectDocument.objects.create(project=self.project, title="Private video", file="secret.mp4", is_public=False)
        self.project.is_public = True
        self.project.save()
        response = self.client.get(reverse("projects:detail", args=[self.project.pk]), {"photos": 2, "panels": 1})
        self.assertEqual(response.context["gallery_page"].number, 2)
        self.assertEqual(response.context["panel_gallery_page"].number, 1)
        self.assertContains(response, "Private video")
        self.assertContains(response, "photos=2&amp;panels=2#tab-panels")
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("documents:document_edit", args=[private.pk]), {"title": "Forbidden"}).status_code, 403)
        qr, _ = QRCode.objects.get_or_create(project=self.project)
        self.client.logout()
        response = self.client.get(reverse("qrcodes:public", args=[qr.token]))
        self.assertNotContains(response, "Private video")
        self.assertEqual(self.client.get(reverse("documents:document_preview", args=[private.pk])).status_code, 403)

    def test_delete_confirmation_get_is_safe_and_requires_ownership(self):
        self.upload()
        self.upload(video())
        image = self.project.images.get()
        document = self.project.documents.get()
        for kind, item in [("image", image), ("document", document)]:
            url = reverse(f"documents:{kind}_delete_confirm", args=[item.pk])
            response = self.client.get(url)
            self.assertContains(response, 'method="post"')
            self.assertContains(response, reverse(f"documents:{kind}_delete", args=[item.pk]))
            self.assertTrue(type(item).objects.filter(pk=item.pk).exists())
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.force_login(self.owner)

    def test_native_batch_rejects_more_than_twenty_files_without_partial_save(self):
        response = self.client.post(reverse("documents:image_upload", args=[self.project.pk]), {
            "upload_version": "2", "panel_files": [photo(name=f"{index}.jpg") for index in range(21)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.project.images.exists())
        self.assertIn("20 ta fayl", str(response.context["form"].errors))

    def test_category_shortcuts_are_visible_before_any_upload(self):
        response = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        for category in ["room", "cables", "connections", "device", "other"]:
            self.assertContains(response, f"?category={category}#general-uploads")
        self.assertContains(response, "?media=video#general-uploads")
        self.assertContains(response, "#panel-uploads")
        self.assertContains(response, "Rasm va video yuklash")

    def test_category_shortcut_preselects_picker_and_native_upload_saves_that_category(self):
        url = reverse("documents:image_upload", args=[self.project.pk])
        for category in ["room", "cables", "connections", "device"]:
            response = self.client.get(url, {"category": category})
            self.assertEqual(response.context["media_form"]["general_category"].value(), category)
            self.assertContains(response, "Qaysi turdagi faylni yuklaysiz?")
        response = self.client.post(url, {"upload_version": "2", "general_category": "cables", "general_files": [photo()]})
        self.assertEqual(response.status_code, 302)
        image = self.project.images.get()
        self.assertEqual(image.category, "cables")
        self.assertEqual(image.description, "")

    def test_video_shortcut_opens_video_picker_and_invalid_category_is_not_accepted(self):
        url = reverse("documents:image_upload", args=[self.project.pk])
        response = self.client.get(url, {"media": "video"})
        self.assertContains(response, 'data-video-only="true"')
        self.assertContains(response, "Video tanlash")
        self.assertEqual(response.context["media_form"].fields["general_files"].widget.attrs["accept"], ".mp4,.webm,video/mp4,video/webm")
        response = self.client.get(url, {"category": "forged"})
        self.assertEqual(response.context["media_form"]["general_category"].value(), "other")
        response = self.client.post(url, {"upload_version": "2", "general_category": "forged", "general_files": [photo()]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.project.images.exists())

    def test_category_labels_remain_visible_without_title_or_comment_on_project_and_qr(self):
        for category in ["room", "cables", "connections", "device", "panel"]:
            ProjectImage.objects.create(project=self.project, image=f"unused-{category}.jpg", category=category)
        self.project.is_public = True
        self.project.save()
        response = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        for image in self.project.images.all():
            self.assertContains(response, f'<span class="media-category-label">{escape(image.get_category_display())}</span>', html=True)
        qr = QRCode.objects.get(project=self.project, panel=None)
        self.client.logout()
        response = self.client.get(reverse("qrcodes:public", args=[qr.token]))
        for image in self.project.images.all():
            self.assertContains(response, f'<span class="media-category-label">{escape(image.get_category_display())}</span>', html=True)

    def test_connection_image_can_be_categorized_later_without_uploading_again(self):
        response = self.upload(category="connections", title="", description="")
        self.assertEqual(response.status_code, 201, response.content)
        image = self.project.images.get()
        path, digest = image.image.name, image.content_sha256
        response = self.client.post(reverse("documents:image_edit", args=[image.pk]), {"title": "Ulanish qutisi", "description": "", "category": "cables"})
        self.assertEqual(response.status_code, 302)
        image.refresh_from_db()
        self.assertEqual((image.category, image.title, image.description), ("cables", "Ulanish qutisi", ""))
        self.assertEqual((image.image.name, image.content_sha256), (path, digest))
        self.assertEqual(self.project.images.count(), 1)
        self.client.post(reverse("documents:image_edit", args=[image.pk]), {"title": "", "description": ""})
        image.refresh_from_db()
        self.assertEqual(image.category, "cables")

    def test_connection_video_category_and_caption_are_visible_and_editable(self):
        response = self.upload(video(), category="connections", title="Ulanish", description="")
        self.assertEqual(response.status_code, 201, response.content)
        document = self.project.documents.get()
        response = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        self.assertContains(response, '<span class="media-category-label">Simlar ulangan joylar</span>', html=True)
        response = self.client.post(reverse("documents:document_edit", args=[document.pk]), {"title": "Yoritish", "description": "", "category": "device"})
        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual(document.category, "device")
