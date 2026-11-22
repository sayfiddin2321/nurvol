from django.test import TestCase
from django.urls import reverse

from apps.electricians.models import ElectricianClient, ElectricianInquiry, ElectricianProfile
from .models import PaymentSettings, User


class AdministratorNavigationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="workspace-admin")
        self.client.force_login(self.admin)

    def test_admin_has_all_management_and_personal_workspace_links(self):
        routes = [
            "accounts:manage_electricians", "accounts:payment_settings", "projects:showcase_settings",
            "electricians:my_profile", "electricians:clients", "electricians:inquiries", "accounts:settings",
        ]
        dashboard = self.client.get(reverse("dashboard"))
        for route in routes:
            with self.subTest(route=route):
                url = reverse(route)
                self.assertContains(dashboard, url)
                self.assertEqual(self.client.get(url).status_code, 200)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMIN)
        self.assertTrue(self.admin.is_superuser)

    def test_staff_flag_alone_does_not_grant_head_electrician_access(self):
        staff = User.objects.create_user(username="staff-electrician", role=User.Role.ELECTRICIAN, is_staff=True)
        profile = staff.electrician_profile
        profile.access_status = ElectricianProfile.AccessStatus.PENDING_PAYMENT
        profile.save()
        self.client.force_login(staff)
        self.assertFalse(staff.is_administrator)
        self.assertRedirects(self.client.get(reverse("accounts:manage_electricians")), reverse("accounts:electrician_access"))
        profile.access_status = ElectricianProfile.AccessStatus.ACTIVE
        profile.save()
        for route in ("accounts:manage_electricians", "accounts:payment_settings", "projects:showcase_settings"):
            self.assertEqual(self.client.get(reverse(route)).status_code, 403)

    def test_pending_electrician_still_needs_payment_and_approval(self):
        user = User.objects.create_user(username="waiting-user", role=User.Role.ELECTRICIAN)
        profile = user.electrician_profile
        profile.access_status = ElectricianProfile.AccessStatus.PENDING_PAYMENT
        profile.save()
        self.client.force_login(user)
        for route in ("electricians:my_profile", "accounts:manage_electricians", "accounts:payment_settings"):
            self.assertRedirects(self.client.get(reverse(route)), reverse("accounts:electrician_access"))

    def test_client_cannot_open_admin_settings_or_electrician_workspace(self):
        client = User.objects.create_user(username="regular-customer")
        self.client.force_login(client)
        response = self.client.get(reverse("dashboard"))
        for route in ("accounts:manage_electricians", "accounts:payment_settings", "electricians:clients", "electricians:inquiries"):
            self.assertNotContains(response, reverse(route))
            expected_status = 403 if route.startswith("accounts:") else 302
            self.assertEqual(self.client.get(reverse(route)).status_code, expected_status)
        self.assertFalse(ElectricianProfile.objects.filter(user=client).exists())

    def test_admin_workspace_keeps_other_electricians_customers_and_inquiries_separate(self):
        own = User.objects.create_user(username="own-customer")
        other = User.objects.create_user(username="other-customer")
        electrician = User.objects.create_user(username="other-electrician", role=User.Role.ELECTRICIAN)
        ElectricianClient.objects.create(electrician=self.admin, client=own)
        ElectricianClient.objects.create(electrician=electrician, client=other)
        ElectricianInquiry.objects.create(electrician=self.admin, client=own, phone="+998901112233", message="Admin's own inquiry")
        private = ElectricianInquiry.objects.create(electrician=electrician, client=other, phone="+998901112234", message="Other electrician's inquiry")
        clients = self.client.get(reverse("electricians:clients"))
        self.assertQuerySetEqual(clients.context["clients"], [own])
        inbox = self.client.get(reverse("electricians:inquiries"))
        self.assertEqual(inbox.context["unread_count"], 1)
        self.assertNotContains(inbox, private.message)
        self.assertEqual(self.client.post(reverse("electricians:mark_inquiry_read", args=[private.pk])).status_code, 404)

    def test_admin_can_create_a_customer_without_losing_admin_role(self):
        response = self.client.post(reverse("electricians:create_client"), {
            "username": "admin-customer", "first_name": "New", "last_name": "Customer",
            "password1": "Customer-Test-927!", "password2": "Customer-Test-927!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ElectricianClient.objects.filter(electrician=self.admin, client__username="admin-customer").exists())
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMIN)

    def test_payment_settings_are_linked_from_admin_settings(self):
        response = self.client.get(reverse("accounts:settings"))
        self.assertContains(response, reverse("accounts:payment_settings"))
        self.assertContains(response, "To'lov rekvizitlarini kiritish")
        client = User.objects.create_user(username="payment-visitor")
        self.client.force_login(client)
        response = self.client.post(reverse("accounts:payment_settings"), {"card_number": "Unauthorized"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PaymentSettings.objects.filter(card_number="Unauthorized").exists())
