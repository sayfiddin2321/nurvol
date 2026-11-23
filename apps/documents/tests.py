from io import BytesIO

from PIL import Image as PILImage
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.test_utils import consume_response
from tempfile import TemporaryDirectory

from apps.accounts.models import User
from apps.projects.models import Project

from .forms import ProjectDocumentForm, ProjectImageForm
from .models import ProjectDocument, ProjectImage


class ProjectDocumentSecurityTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_dir = TemporaryDirectory()
        cls.override = override_settings(MEDIA_ROOT=cls.media_dir.name)
        cls.override.enable()
        cls.addClassCleanup(cls.override.disable)
        cls.addClassCleanup(cls.media_dir.cleanup)

    def setUp(self):
        self.owner = User.objects.create_user(
            username="document-owner",
            password="test-password",
            role=User.Role.ELECTRICIAN,
        )
        self.project = Project.objects.create(
            electrician=self.owner,
            name="Document test",
            is_public=True,
        )
        image_buffer = BytesIO()
        PILImage.new("RGB", (900, 450), color="blue").save(image_buffer, format="JPEG")
        self.document = ProjectDocument.objects.create(
            project=self.project,
            title="Public drawing",
            file=SimpleUploadedFile("drawing.pdf", b"%PDF-1.4 test content"),
            is_public=True,
            uploaded_by=self.owner,
        )
        self.image = ProjectImage.objects.create(
            project=self.project,
            image=SimpleUploadedFile(
                "installation.jpg",
                image_buffer.getvalue(),
                content_type="image/jpeg",
            ),
            uploaded_by=self.owner,
        )

    def tearDown(self):
        if self.document.file:
            self.document.file.delete(save=False)
        if self.image.image:
            self.image.image.delete(save=False)
        if self.image.thumbnail:
            self.image.thumbnail.delete(save=False)

    def test_public_document_is_downloadable_without_login(self):
        response = self.client.get(
            reverse("documents:document_download", args=[self.document.pk])
        )
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIn('attachment;', response["Content-Disposition"])
            self.assertIn('Public drawing', response["Content-Disposition"])
            self.assertTrue(response["Content-Disposition"].endswith('.pdf"'))
        finally:
            consume_response(response)

    def test_private_project_document_is_not_public_even_if_document_flag_is_set(self):
        self.project.is_public = False
        self.project.save()

        response = self.client.get(
            reverse("documents:document_download", args=[self.document.pk])
        )

        self.assertEqual(response.status_code, 403)

    def test_private_project_image_requires_owner_access(self):
        self.project.is_public = False
        self.project.save()
        image_url = reverse("documents:image_view", args=[self.image.pk])

        response = self.client.get(image_url)
        self.assertEqual(response.status_code, 403)
        thumbnail_response = self.client.get(
            reverse("documents:image_thumbnail", args=[self.image.pk])
        )
        self.assertEqual(thumbnail_response.status_code, 403)

        self.client.force_login(self.owner)
        response = self.client.get(image_url)
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/jpeg")
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        finally:
            consume_response(response)

    def test_thumbnail_is_generated_and_served_as_webp(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("documents:image_thumbnail", args=[self.image.pk])
        )
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/webp")
            thumbnail_content = b"".join(response.streaming_content)
        finally:
            consume_response(response)

        with PILImage.open(BytesIO(thumbnail_content)) as thumbnail:
            self.assertEqual(thumbnail.format, "WEBP")
            self.assertEqual(thumbnail.size, (720, 360))
        self.image.refresh_from_db()
        self.assertTrue(self.image.thumbnail)

    def test_public_image_can_be_viewed_without_login(self):
        response = self.client.get(
            reverse("documents:image_view", args=[self.image.pk])
        )
        thumbnail_response = self.client.get(
            reverse("documents:image_thumbnail", args=[self.image.pk])
        )
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/jpeg")
            self.assertEqual(thumbnail_response.status_code, 200)
            self.assertEqual(thumbnail_response["Content-Type"], "image/webp")
        finally:
            consume_response(response)
            consume_response(thumbnail_response)

    def test_document_form_rejects_pdf_extension_with_non_pdf_contents(self):
        form = ProjectDocumentForm(
            data={"title": "Bad upload", "description": "", "is_public": ""},
            files={"file": SimpleUploadedFile("fake.pdf", b"not a PDF")},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)

    def test_project_image_input_supports_camera_and_multiple_files(self):
        widget = ProjectImageForm().fields["images"].widget

        self.assertTrue(widget.allow_multiple_selected)
        self.assertEqual(widget.attrs["accept"], "image/*")
        self.assertNotIn("capture", widget.attrs)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("documents:image_upload", args=[self.project.pk]))
        self.assertContains(response, 'capture="environment"')
        self.assertContains(response, 'data-camera-input')

    def test_upload_has_no_category_or_permission_and_returns_to_gallery(self):
        self.client.force_login(self.owner)
        upload_url = reverse("documents:image_upload", args=[self.project.pk])
        response = self.client.get(upload_url)
        self.assertEqual(list(response.context["form"].fields), ["general_files", "panel_files", "description", "general_category"])
        self.assertNotContains(response, 'name="is_public"')
        self.assertNotContains(response, 'name="category"')
        image_buffer = BytesIO()
        PILImage.new("RGB", (4, 4), color="blue").save(image_buffer, format="JPEG")
        response = self.client.post(upload_url, {
            "description": "Montaj rasmi",
            "images": SimpleUploadedFile("circuit.jpg", image_buffer.getvalue(), content_type="image/jpeg"),
        })
        self.assertRedirects(response, f"{reverse('projects:detail', args=[self.project.pk])}#tab-images")
        uploaded = ProjectImage.objects.exclude(pk=self.image.pk).get(project=self.project)
        self.assertEqual(uploaded.description, "Montaj rasmi")
        self.assertTrue(uploaded.thumbnail)
        detail = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        self.assertContains(detail, "Montaj rasmi")
        self.assertNotContains(detail, "QR: yopiq")

