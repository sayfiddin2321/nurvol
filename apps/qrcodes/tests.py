from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.documents.models import ProjectImage
from apps.electricians.models import ElectricianProfile
from apps.projects.models import Project

from .models import QRCode, QRScanLog
from .services import build_qr_url


@override_settings(ALLOWED_HOSTS=["electropass.example.com"])
class BuildQRCodeURLTests(TestCase):
    def test_uses_current_request_domain_when_available(self):
        token = "12345678-1234-5678-1234-567812345678"
        request = RequestFactory().get(
            "/",
            secure=True,
            HTTP_HOST="electropass.example.com",
        )

        url = build_qr_url(token, request=request)

        self.assertEqual(
            url,
            f"https://electropass.example.com/qr/{token}/",
        )

    @override_settings(SITE_URL="https://electropass.pythonanywhere.com/")
    def test_uses_site_url_without_request(self):
        token = "12345678-1234-5678-1234-567812345678"
        self.assertEqual(
            build_qr_url(token),
            f"https://electropass.pythonanywhere.com/qr/{token}/",
        )


class PublicQRCodeAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="qr-owner",
            password="test-password",
            role=User.Role.ELECTRICIAN,
        )
        self.project = Project.objects.create(
            electrician=self.owner,
            name="QR test project",
        )
        self.qr = QRCode.objects.create(project=self.project)
        self.url = reverse("qrcodes:public", args=[self.qr.token])

    def test_anonymous_visitor_gets_private_page_for_private_project(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "public/private.html")
        self.assertEqual(QRScanLog.objects.count(), 0)

    def test_public_qr_page_records_scan(self):
        self.project.is_public = True
        self.project.save()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "public/qr_project.html")
        self.assertNotContains(response, "Ishlar haqida")
        self.assertNotContains(response, "Muammo bo'lsa, nima qilish kerak?")
        self.assertContains(response, 'class="qr-passport__contact"')
        self.assertEqual(QRScanLog.objects.count(), 1)

    def test_public_page_shows_all_uploaded_images_before_contact(self):
        self.project.is_public = True
        self.project.save()
        public_image = ProjectImage.objects.create(
            project=self.project,
            image="projects/images/public.jpg",
            description="Public photo",
        )
        second_image = ProjectImage.objects.create(
            project=self.project,
            image="projects/images/private.jpg",
            description="Private photo",
        )

        response = self.client.get(self.url)
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("documents:image_thumbnail", args=[public_image.pk]),
        )
        self.assertContains(response, reverse("documents:image_thumbnail", args=[second_image.pk]))
        self.assertContains(response, "Private photo")
        self.assertLess(
            html.index('id="gallery"'),
            html.index('<section class="qr-passport__contact"'),
        )
        self.assertContains(response, 'class="passport-gallery"')
        self.assertContains(response, 'loading="lazy"')
        self.assertContains(response, 'data-gallery-item')

    def test_public_passport_hides_contact_and_verification_claim_by_default(self):
        self.project.is_public = True
        self.project.save()
        self.owner.phone = "+998901234567"
        self.owner.save(update_fields=["phone"])
        ElectricianProfile.objects.update_or_create(
            user=self.owner,
            defaults={"telegram": "@private_contact"},
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "+998901234567")
        self.assertNotContains(response, "@private_contact")
        self.assertContains(response, "Aloqa ma'lumoti ommaga ochilmagan.")
        self.assertNotContains(response, "Mutaxassis profili")

    def test_public_passport_shows_contacts_only_after_opt_in(self):
        self.project.is_public = True
        self.project.save()
        self.owner.phone = "+998901234567"
        self.owner.save(update_fields=["phone"])
        ElectricianProfile.objects.update_or_create(
            user=self.owner,
            defaults={
                "telegram": "@public_contact",
                "show_phone_public": True,
                "show_telegram_public": True,
                "is_verified": True,
            },
        )

        response = self.client.get(self.url)

        self.assertContains(response, "+998901234567")
        self.assertContains(response, 'href="tel:+998901234567"')
        self.assertContains(response, "https://t.me/public_contact")

    def test_owner_can_regenerate_token_and_old_url_stops_working(self):
        self.client.force_login(self.owner)
        old_token = self.qr.token

        response = self.client.post(
            reverse("qrcodes:regenerate", args=[old_token])
        )

        self.assertRedirects(
            response,
            reverse("qrcodes:manage", args=[self.project.pk]),
        )
        self.qr.refresh_from_db()
        self.assertNotEqual(self.qr.token, old_token)
        self.assertEqual(self.client.get(reverse("qrcodes:public", args=[old_token])).status_code, 404)

    def test_qr_management_actions_require_post(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("qrcodes:toggle", args=[self.qr.token])
        )

        self.assertEqual(response.status_code, 405)
        self.qr.refresh_from_db()
        self.assertTrue(self.qr.is_active)

    def test_owner_can_view_qr_inline_and_still_download_the_png(self):
        self.project.is_public = True
        self.project.save()
        self.client.force_login(self.owner)
        image_url = reverse("qrcodes:image", args=[self.qr.token])
        response = self.client.get(image_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response["Content-Disposition"].startswith("inline;"))
        self.assertTrue(response.content.startswith(b"\x89PNG\r\n\x1a\n"))
        download = self.client.get(reverse("qrcodes:download", args=[self.qr.token]))
        self.assertTrue(download["Content-Disposition"].startswith("attachment;"))
        self.assertEqual(download.content, response.content)
        detail = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        self.assertContains(detail, image_url)
        self.assertContains(detail, "QR kodni ko'rish")
        self.assertNotContains(detail, 'id="share-url"')

    def test_qr_image_preview_requires_owner_or_admin(self):
        image_url = reverse("qrcodes:image", args=[self.qr.token])
        self.assertRedirects(
            self.client.get(image_url), reverse("accounts:login") + "?next=" + image_url,
            fetch_redirect_response=False,
        )
        other = User.objects.create_user(username="qr-image-visitor", role=User.Role.CLIENT)
        self.client.force_login(other)
        self.assertEqual(self.client.get(image_url).status_code, 403)

    def test_print_has_one_building_qr_even_when_panel_qrs_exist(self):
        from apps.electrical.models import ElectricalPanel

        panel = ElectricalPanel.objects.create(project=self.project, name="Panel", panel_code="P1")
        panel_qr = QRCode.objects.create(project=self.project, panel=panel)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("qrcodes:print", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([qr.pk for qr in response.context["qrs"]], [self.qr.pk])
        self.assertContains(response, 'class="qr-sticker"', count=1)
        self.assertContains(response, reverse("qrcodes:image", args=[self.qr.token]))
        self.assertNotContains(response, reverse("qrcodes:image", args=[panel_qr.token]))
        self.assertEqual(self.project.qr_codes.count(), 2)
