from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.electricians.models import ElectricianInquiry, ElectricianProfile
from apps.projects.models import Project, ProjectShowcaseSettings
from .models import PaymentSettings, User


class ElectricianPermissionBoundaryTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media = TemporaryDirectory()
        cls.addClassCleanup(cls.media.cleanup)
        cls.media_override = override_settings(MEDIA_ROOT=cls.media.name)
        cls.media_override.enable()
        cls.addClassCleanup(cls.media_override.disable)

    def setUp(self):
        self.head = User.objects.create_superuser(username="head-electrician")
        self.electrician = User.objects.create_user(username="regular-electrician", role=User.Role.ELECTRICIAN)
        self.other = User.objects.create_user(username="another-electrician", role=User.Role.ELECTRICIAN)
        self.customer = User.objects.create_user(username="request-customer")
        self.payment_settings = PaymentSettings.objects.create(pk=1, card_number="8600 1111 2222 3333")

    def assert_regular_electrician(self, user):
        user.refresh_from_db()
        self.assertEqual(user.role, User.Role.ELECTRICIAN)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_administrator)

    def test_head_and_regular_electrician_have_distinct_labels_and_menus(self):
        self.assertEqual(self.head.role_label, "Bosh elektrik")
        self.assertEqual(self.electrician.role_label, "Elektrik")
        self.client.force_login(self.head)
        self.assertContains(self.client.get(reverse("dashboard")), "Bosh elektrik (Administrator)")
        self.client.force_login(self.electrician)
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, "Bosh elektrik")
        self.assertNotContains(response, "Bosh Elektromontyor")
        for route in ("accounts:manage_electricians", "accounts:payment_settings", "projects:showcase_settings"):
            self.assertNotContains(response, reverse(route))
        self.assertEqual(response.context["pending_electrician_count"], 0)

    def test_head_can_suspend_and_reactivate_electrician_account(self):
        profile = self.electrician.electrician_profile
        profile.access_status = ElectricianProfile.AccessStatus.ACTIVE
        profile.save(update_fields=["access_status"])
        self.client.force_login(self.head)

        response = self.client.post(
            reverse("accounts:set_electrician_account_active", args=[profile.pk]),
            {"action": "suspend"},
        )
        self.assertRedirects(response, reverse("accounts:manage_electricians"))
        self.electrician.refresh_from_db()
        self.assertFalse(self.electrician.is_active)

        response = self.client.get(
            reverse("accounts:manage_electricians"),
            {"status": "suspended"},
        )
        self.assertContains(response, "Akkauntni faollashtirish")
        self.assertEqual(response.context["counts"]["suspended"], 1)

        response = self.client.post(
            reverse("accounts:set_electrician_account_active", args=[profile.pk]),
            {"action": "activate"},
        )
        self.assertRedirects(response, reverse("accounts:manage_electricians"))
        self.electrician.refresh_from_db()
        profile.refresh_from_db()
        self.assertTrue(self.electrician.is_active)
        self.assertEqual(profile.access_status, ElectricianProfile.AccessStatus.ACTIVE)

    def test_head_can_delete_electrician_and_all_electrician_projects(self):
        project = Project.objects.create(
            name="Eskirgan ish",
            electrician=self.electrician,
            is_public=True,
        )
        electrician_id = self.electrician.pk
        profile_id = self.electrician.electrician_profile.pk
        self.client.force_login(self.head)

        response = self.client.post(
            reverse("accounts:set_electrician_account_active", args=[profile_id]),
            {"action": "delete"},
        )

        self.assertRedirects(response, reverse("accounts:manage_electricians"))
        self.assertFalse(User.objects.filter(pk=electrician_id).exists())
        self.assertFalse(ElectricianProfile.objects.filter(pk=profile_id).exists())
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())

    def test_admin_and_head_accounts_cannot_be_deleted(self):
        self.client.force_login(self.head)
        self.other.is_superuser = True
        self.other.is_staff = True
        self.other.save(update_fields=["is_superuser", "is_staff"])
        admin_profile = self.other.electrician_profile
        response = self.client.post(
            reverse("accounts:set_electrician_account_active", args=[admin_profile.pk]),
            {"action": "delete"},
        )
        self.assertRedirects(response, reverse("accounts:manage_electricians"))
        self.other.refresh_from_db()
        self.assertTrue(self.other.is_administrator)

        for action in ("suspend", "activate", "delete"):
            response = self.client.post(
                reverse("accounts:set_electrician_account_active", args=[admin_profile.pk]),
                {"action": action},
            )
            self.assertRedirects(response, reverse("accounts:manage_electricians"))
            self.other.refresh_from_db()
            self.assertTrue(self.other.is_active)

    def test_head_cannot_suspend_or_delete_own_electrician_profile(self):
        self.head.role = User.Role.ELECTRICIAN
        self.head.save(update_fields=["role"])
        profile = ElectricianProfile.objects.create(user=self.head)
        self.client.force_login(self.head)

        for action in ("suspend", "delete"):
            response = self.client.post(
                reverse("accounts:set_electrician_account_active", args=[profile.pk]),
                {"action": action},
            )
            self.assertRedirects(response, reverse("accounts:manage_electricians"))
            self.head.refresh_from_db()
            self.assertTrue(self.head.is_active)

    def test_active_electrician_cannot_read_or_write_global_management_pages(self):
        self.client.force_login(self.electrician)
        for route in ("accounts:manage_electricians", "accounts:payment_settings", "projects:showcase_settings"):
            with self.subTest(route=route):
                url = reverse(route)
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {"card_number": "Tampered", "featured_electrician": self.electrician.pk}).status_code, 403)
        self.payment_settings.refresh_from_db()
        self.assertEqual(self.payment_settings.card_number, "8600 1111 2222 3333")
        self.assertFalse(ProjectShowcaseSettings.objects.exists())

    def test_electrician_cannot_approve_other_accounts_or_read_their_receipts(self):
        profile = self.other.electrician_profile
        profile.access_status = ElectricianProfile.AccessStatus.PAYMENT_SUBMITTED
        profile.payment_receipt = "electricians/payment-receipts/another-user.png"
        profile.save()
        self.client.force_login(self.electrician)
        response = self.client.post(reverse("accounts:update_electrician_access", args=[profile.pk]), {"action": "approve"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get(reverse("accounts:payment_receipt", args=[self.other.pk])).status_code, 403)
        profile.refresh_from_db()
        self.assertEqual(profile.access_status, ElectricianProfile.AccessStatus.PAYMENT_SUBMITTED)

    def test_public_registration_ignores_privilege_fields_and_rejects_head_role(self):
        data = {
            "username": "registered-electrician", "first_name": "New", "last_name": "Electrician",
            "email": "electrician@example.com", "role": User.Role.ELECTRICIAN,
            "password1": "Registration-Test-927!", "password2": "Registration-Test-927!",
            "accepted_terms": "on", "is_staff": "on", "is_superuser": "on",
        }
        self.client.post(reverse("accounts:register"), data)
        registered = User.objects.get(username=data["username"])
        self.assert_regular_electrician(registered)
        self.assertEqual(registered.electrician_profile.access_status, ElectricianProfile.AccessStatus.PENDING_PAYMENT)
        self.client.logout()
        data.update(username="unauthorized-head", role=User.Role.ADMIN)
        response = self.client.post(reverse("accounts:register"), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("role", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="unauthorized-head").exists())

    def test_payment_and_approval_activate_only_personal_electrician_access(self):
        profile = self.electrician.electrician_profile
        profile.access_status = ElectricianProfile.AccessStatus.PENDING_PAYMENT
        profile.save()
        self.client.force_login(self.electrician)
        self.assertContains(self.client.get(reverse("accounts:electrician_access")), self.payment_settings.card_number)
        image = BytesIO()
        Image.new("RGB", (8, 8), "blue").save(image, "PNG")
        self.client.post(reverse("accounts:submit_payment"), {
            "receipt": SimpleUploadedFile("payment.png", image.getvalue(), content_type="image/png"),
            "role": "admin", "is_staff": "on", "is_superuser": "on",
        })
        self.assert_regular_electrician(self.electrician)
        self.client.force_login(self.head)
        self.client.post(reverse("accounts:update_electrician_access", args=[profile.pk]), {
            "action": "approve", "role": "admin", "is_staff": "on", "is_superuser": "on",
        })
        profile.refresh_from_db()
        self.assertEqual(profile.access_status, ElectricianProfile.AccessStatus.ACTIVE)
        self.assert_regular_electrician(self.electrician)
        own = ElectricianInquiry.objects.create(electrician=self.electrician, client=self.customer, phone="+998901112233", message="OWN-REQUEST")
        ElectricianInquiry.objects.create(electrician=self.head, client=self.customer, phone="+998901112233", message="HEAD-ONLY-REQUEST")
        ElectricianInquiry.objects.create(electrician=self.other, client=self.customer, phone="+998901112233", message="OTHER-ONLY-REQUEST")
        self.client.force_login(self.electrician)
        dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertNotContains(dashboard, reverse("accounts:payment_settings"))
        inbox = self.client.get(reverse("electricians:inquiries"))
        self.assertQuerySetEqual(inbox.context["inquiries"], [own])
        self.assertEqual(inbox.context["unread_count"], 1)
        self.assertNotContains(inbox, "HEAD-ONLY-REQUEST")
        self.assertNotContains(inbox, "OTHER-ONLY-REQUEST")
        self.assertRedirects(self.client.get(reverse("accounts:electrician_access")), reverse("dashboard"))
        self.assertRedirects(self.client.post(reverse("accounts:submit_payment"), {}), reverse("dashboard"))

    def test_personal_profile_cannot_be_used_to_change_role_or_permissions(self):
        self.client.force_login(self.electrician)
        response = self.client.post(reverse("accounts:settings"), {
            "first_name": "Updated", "last_name": "Electrician", "email": "updated@example.com", "phone": "",
            "role": "admin", "is_staff": "on", "is_superuser": "on",
        })
        self.assertRedirects(response, reverse("accounts:settings"))
        self.assert_regular_electrician(self.electrician)

    def test_superuser_with_electrician_role_remains_head_and_projects_stay_scoped(self):
        self.head.role = User.Role.ELECTRICIAN
        self.head.save(update_fields=["role"])
        self.assertEqual(self.head.role_label, "Bosh elektrik")
        first = Project.objects.create(name="First electrician project", electrician=self.electrician)
        second = Project.objects.create(name="Other electrician project", electrician=self.other)
        self.client.force_login(self.head)
        self.assertEqual(self.client.get(reverse("dashboard")).context["stats"]["total"], 2)
        self.client.force_login(self.electrician)
        self.assertEqual(self.client.get(reverse("dashboard")).context["stats"]["total"], 1)
        self.assertEqual(self.client.get(reverse("projects:detail", args=[first.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("projects:detail", args=[second.pk])).status_code, 403)
