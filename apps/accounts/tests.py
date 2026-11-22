from io import BytesIO
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from apps.test_utils import consume_response
from PIL import Image

from .models import ContactInquiry, PaymentSettings, User
from apps.electricians.models import ElectricianProfile


class AccountViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="account-user",
            email="account@example.com",
            password="OriginalPassword123!",
        )

    def test_anonymous_home_shows_landing_page(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "landing.html")
        self.assertContains(response, "/static/favicon.svg?v=2")
        self.assertContains(response, "Pro tarif uchun so‘rov yuborish")
        self.assertNotContains(response, "Bepul boshlash")

    def test_authenticated_home_redirects_to_dashboard(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )

    def test_dashboard_uses_nurvolt_brand_mark(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "NURVOLT")
        self.assertContains(response, "/static/favicon.svg?v=2")
        self.assertContains(response, "images/nurvolt-mark.svg")

    def test_settings_requires_login_and_displays_profile_form(self):
        response = self.client.get(reverse("accounts:settings"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:settings')}",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profil ma'lumotlari")

    def test_password_change_preserves_authenticated_session(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("accounts:password_change"), {
            "old_password": "OriginalPassword123!",
            "new_password1": "NewPassword456!",
            "new_password2": "NewPassword456!",
        })

        self.assertRedirects(response, reverse("accounts:settings"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPassword456!"))
        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 405)

        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))


class RegisterViewTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_settings = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)
        self.addCleanup(self.media_dir.cleanup)

    def receipt_file(self, name="receipt.png"):
        image_bytes = BytesIO()
        Image.new("RGB", (10, 10), color="white").save(image_bytes, format="PNG")
        return SimpleUploadedFile(
            name,
            image_bytes.getvalue(),
            content_type="image/png",
        )

    def registration_data(self, **overrides):
        data = {
            "username": "new-electrician",
            "first_name": "Ali",
            "last_name": "Valiyev",
            "email": "ali@example.com",
            "phone": "+998901234567",
            "role": User.Role.ELECTRICIAN,
            "city": "Toshkent",
            "experience_years": "5",
            "password1": "A-very-strong-Password-987!",
            "password2": "A-very-strong-Password-987!",
            "accepted_terms": "on",
        }
        data.update(overrides)
        return data

    def test_registration_requires_terms_acceptance(self):
        response = self.client.post(
            reverse("accounts:register"),
            self.registration_data(accepted_terms=""),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, '<small class="field-error">')
        self.assertFalse(User.objects.filter(username="new-electrician").exists())

    def test_registration_shows_duplicate_login_and_email_errors(self):
        User.objects.create_user(
            username="admin_2321",
            email="admin@example.com",
            password="OriginalPassword123!",
        )

        response = self.client.post(
            reverse("accounts:register"),
            self.registration_data(
                username="admin_2321",
                email="new@example.com",
            ),
        )

        form = response.context["form"]
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(form.errors["username"][0]))
        self.assertNotIn("email", form.errors)
        self.assertContains(response, 'value="admin_2321"')
        self.assertContains(response, 'value="new@example.com"')
        self.assertEqual(User.objects.filter(username="admin_2321").count(), 1)

    def test_electrician_registration_saves_profile_details(self):
        response = self.client.post(
            reverse("accounts:register"),
            self.registration_data(),
        )

        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )
        user = User.objects.get(username="new-electrician")
        self.assertEqual(user.role, User.Role.ELECTRICIAN)
        self.assertEqual(user.electrician_profile.city, "Toshkent")
        self.assertEqual(user.electrician_profile.experience_years, 5)
        self.assertEqual(
            user.electrician_profile.access_status,
            ElectricianProfile.AccessStatus.PENDING_PAYMENT,
        )
        self.assertIsNotNone(user.terms_accepted_at)
        self.assertEqual(user.terms_version, "1")

    def test_simple_eight_character_password_and_safe_next_are_accepted(self):
        electrician = User.objects.create_user(
            username="target-electrician",
            role=User.Role.ELECTRICIAN,
            first_name="Usta",
        )
        profile_url = reverse(
            "electricians:public_profile",
            args=[electrician.pk],
        )
        registration_url = f"{reverse('accounts:register')}?next={profile_url}"

        response = self.client.post(
            registration_url,
            self.registration_data(
                username="ali-login",
                password1="Ali12345",
                password2="Ali12345",
                role=User.Role.CLIENT,
            ),
        )

        self.assertRedirects(
            response,
            profile_url,
            fetch_redirect_response=False,
        )

    def test_electrician_must_submit_payment_and_be_approved_before_using_site(self):
        self.client.post(reverse("accounts:register"), self.registration_data())
        user = User.objects.get(username="new-electrician")

        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("accounts:electrician_access"))
        response = self.client.get(reverse("projects:list"))
        self.assertRedirects(response, reverse("accounts:electrician_access"))

        response = self.client.post(reverse("accounts:submit_payment"), {
            "payment_reference": "TX-4821",
        })
        self.assertEqual(response.status_code, 400)
        user.electrician_profile.refresh_from_db()
        self.assertEqual(
            user.electrician_profile.access_status,
            ElectricianProfile.AccessStatus.PENDING_PAYMENT,
        )

        invalid_receipt = SimpleUploadedFile(
            "receipt.png",
            b"not an image",
            content_type="image/png",
        )
        response = self.client.post(reverse("accounts:submit_payment"), {
            "payment_reference": "TX-4821",
            "receipt": invalid_receipt,
        })
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context["payment_form"].errors["receipt"])
        user.electrician_profile.refresh_from_db()
        self.assertEqual(
            user.electrician_profile.access_status,
            ElectricianProfile.AccessStatus.PENDING_PAYMENT,
        )

        response = self.client.post(reverse("accounts:submit_payment"), {
            "payment_reference": "TX-4821",
            "receipt": self.receipt_file(),
        })
        self.assertRedirects(response, reverse("accounts:electrician_access"))
        user.electrician_profile.refresh_from_db()
        self.assertEqual(
            user.electrician_profile.access_status,
            ElectricianProfile.AccessStatus.PAYMENT_SUBMITTED,
        )
        self.assertEqual(user.electrician_profile.payment_reference, "TX-4821")
        self.assertTrue(user.electrician_profile.payment_receipt)

        admin = User.objects.create_user(
            username="electrician-manager",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:manage_electricians"))
        self.assertContains(response, "TX-4821")
        self.assertContains(response, "new-electrician")
        self.assertContains(response, "Chekni ko'rish")
        other_user = User.objects.create_user(
            username="payment-observer",
            role=User.Role.CLIENT,
        )
        self.client.force_login(other_user)
        forbidden_receipt = self.client.get(
            reverse("accounts:payment_receipt", args=[user.pk]),
        )
        self.assertEqual(forbidden_receipt.status_code, 403)
        self.client.force_login(admin)
        receipt_response = self.client.get(
            reverse("accounts:payment_receipt", args=[user.pk]),
        )
        self.assertEqual(receipt_response.status_code, 200)
        self.assertEqual(receipt_response["Content-Type"], "image/png")
        consume_response(receipt_response)
        direct_media_response = self.client.get(
            f"/media/{user.electrician_profile.payment_receipt.name}",
        )
        self.assertEqual(direct_media_response.status_code, 404)
        response = self.client.post(
            reverse("accounts:update_electrician_access", args=[user.electrician_profile.pk]),
            {"action": "approve"},
        )
        self.assertRedirects(response, reverse("accounts:manage_electricians"))

        user.electrician_profile.refresh_from_db()
        self.assertEqual(
            user.electrician_profile.access_status,
            ElectricianProfile.AccessStatus.ACTIVE,
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_payment_settings_are_admin_managed_and_visible_to_electricians(self):
        admin = User.objects.create_user(
            username="payment-admin",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
        )
        self.client.force_login(admin)

        response = self.client.post(reverse("accounts:payment_settings"), {
            "card_number": "8600 1234 5678 9012",
            "cardholder_name": "Ali Valiyev",
            "phone": "+998901234567",
            "telegram_username": "@volt_admin",
        })
        self.assertRedirects(response, reverse("accounts:payment_settings"))
        settings = PaymentSettings.objects.get(pk=1)
        self.assertEqual(settings.telegram_username, "volt_admin")

        electrician = User.objects.create_user(
            username="payment-electrician",
            role=User.Role.ELECTRICIAN,
        )
        electrician.electrician_profile.access_status = ElectricianProfile.AccessStatus.PENDING_PAYMENT
        electrician.electrician_profile.save(update_fields=["access_status"])
        self.client.force_login(electrician)
        response = self.client.get(reverse("accounts:electrician_access"))
        self.assertContains(response, "8600 1234 5678 9012")
        self.assertContains(response, "Ali Valiyev")
        self.assertContains(response, "+998901234567")
        self.assertContains(response, "https://t.me/volt_admin")

    def test_admin_cannot_activate_electrician_without_payment_submission(self):
        user = User.objects.create_user(
            username="waiting-electrician",
            password="ElectricianPassword123!",
            role=User.Role.ELECTRICIAN,
        )
        user.electrician_profile.access_status = ElectricianProfile.AccessStatus.PENDING_PAYMENT
        user.electrician_profile.save(update_fields=["access_status"])
        admin = User.objects.create_user(
            username="manager",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
        )
        self.client.force_login(admin)

        self.client.post(
            reverse("accounts:update_electrician_access", args=[user.electrician_profile.pk]),
            {"action": "approve"},
        )

        user.electrician_profile.refresh_from_db()
        self.assertEqual(
            user.electrician_profile.access_status,
            ElectricianProfile.AccessStatus.PENDING_PAYMENT,
        )

    def test_registration_and_payment_requests_appear_in_admin_navigation_and_filters(self):
        self.client.post(reverse("accounts:register"), self.registration_data())
        electrician = User.objects.get(username="new-electrician")
        admin = User.objects.create_superuser(username="request-notifications-admin")
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:manage_electricians"), {"status": "pending_payment"})
        self.assertContains(response, "new-electrician")
        self.assertEqual(response.context["pending_electrician_count"], 1)
        self.assertEqual(response.context["counts"]["pending_payment"], 1)
        self.assertEqual(response.context["counts"]["payment_submitted"], 0)
        self.client.force_login(electrician)
        self.client.post(reverse("accounts:submit_payment"), {"receipt": self.receipt_file(), "payment_reference": "REQUEST-TEST"})
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:manage_electricians"), {"status": "payment_submitted"})
        self.assertContains(response, "REQUEST-TEST")
        self.assertEqual(response.context["counts"]["payment_submitted"], 1)
        self.assertEqual(response.context["counts"]["pending_payment"], 0)
        self.assertEqual(response.context["pending_electrician_count"], 1)
        self.client.post(reverse("accounts:update_electrician_access", args=[electrician.electrician_profile.pk]), {"action": "approve"})
        response = self.client.get(reverse("accounts:manage_electricians"))
        self.assertEqual(response.context["pending_electrician_count"], 0)
        self.assertEqual(response.context["counts"]["active"], 1)


class ContactInquiryViewTests(TestCase):
    def inquiry_data(self, **overrides):
        data = {
            "name": "Sardor",
            "phone": "+998 90 123-45-67",
            "plan": ContactInquiry.Plan.PRO,
            "message": "Pro tarif haqida ma'lumot kerak.",
        }
        data.update(overrides)
        return data

    def test_plan_request_is_saved_and_visible_in_admin(self):
        response = self.client.post(
            reverse("accounts:contact"),
            self.inquiry_data(),
        )

        self.assertRedirects(response, f"{reverse('home')}#biz-bilan-aloqa")
        inquiry = ContactInquiry.objects.get()
        self.assertEqual(inquiry.name, "Sardor")
        self.assertEqual(inquiry.plan, ContactInquiry.Plan.PRO)

        admin_user = User.objects.create_superuser(
            username="inquiry-admin",
            email="admin@example.com",
            password="AdminPassword123!",
        )
        self.client.force_login(admin_user)
        admin_response = self.client.get(
            reverse("admin:accounts_contactinquiry_changelist"),
        )
        self.assertContains(admin_response, "Sardor")
        self.assertContains(admin_response, "Pro Usta")

    def test_invalid_plan_does_not_create_inquiry(self):
        response = self.client.post(
            reverse("accounts:contact"),
            self.inquiry_data(plan="unknown"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ContactInquiry.objects.exists())
