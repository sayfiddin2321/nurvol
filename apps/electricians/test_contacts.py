from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.projects.models import Project
from apps.qrcodes.models import QRCode
from .contacts import normalize_social, social_url, phone_uri


class ElectricianContactTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="contact-owner", role="electrician", phone="+998 (90) 123-45-67")
        self.profile = self.owner.electrician_profile

    def test_social_handles_and_full_urls_normalize(self):
        for value in ["@usta_ali", "usta_ali", "https://t.me/usta_ali/", "telegram.me/usta_ali"]:
            self.assertEqual(normalize_social(value, "telegram"), "usta_ali")
        for value in ["@usta.ali", "https://www.instagram.com/usta.ali/?igsh=abc", "instagram.com/usta.ali"]:
            self.assertEqual(social_url(value, "instagram"), "https://instagram.com/usta.ali")
        self.assertEqual(phone_uri(self.owner.phone), "tel:+998901234567")

    def test_invalid_external_and_executable_links_are_rejected(self):
        for value in ["https://evil.example/usta_ali", "javascript:alert(1)", "https://t.me/usta_ali/extra", "https://t.me@evil.example/usta_ali"]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                normalize_social(value, "telegram")
            self.assertEqual(social_url(value, "telegram"), "")
        self.assertEqual(phone_uri("+998901234567?body=hello"), "")
        self.assertEqual(social_url("https://instagram.com/p/", "instagram"), "")

    def test_one_profile_form_saves_identity_company_and_all_contacts(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("electricians:edit_profile"), {
            "first_name": "Ali", "last_name": "Valiyev", "phone": "+998 90 123 45 67",
            "company_name": "Ali Elektr", "telegram": "https://t.me/usta_ali",
            "instagram": "https://instagram.com/usta.ali/", "show_phone_public": "on",
            "show_telegram_public": "on", "show_instagram_public": "on",
        })
        self.assertRedirects(response, reverse("electricians:my_profile"))
        self.profile.refresh_from_db()
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.get_full_name(), "Ali Valiyev")
        self.assertEqual(self.profile.telegram, "usta_ali")
        self.assertEqual(self.profile.instagram, "usta.ali")
        self.assertEqual(self.profile.company_name, "Ali Elektr")
        project = Project.objects.create(electrician=self.owner, name="Contact test", is_public=True)
        qr = QRCode.objects.create(project=project)
        self.client.logout()
        response = self.client.get(reverse("qrcodes:public", args=[qr.token]))
        for value in ['href="tel:+998901234567"', 'href="https://t.me/usta_ali"', 'href="https://instagram.com/usta.ali"', "Ali Elektr"]:
            self.assertContains(response, value)

    def test_invalid_profile_does_not_partially_save_identity(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("electricians:edit_profile"), {"first_name": "Must not save", "telegram": "https://evil.example/username"})
        self.assertEqual(response.status_code, 200)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.first_name, "")

    def test_instagram_and_phone_are_hidden_without_opt_in(self):
        self.profile.instagram = "@hidden.contact"
        self.profile.save()
        project = Project.objects.create(electrician=self.owner, name="Hidden contacts", is_public=True)
        qr = QRCode.objects.create(project=project)
        response = self.client.get(reverse("qrcodes:public", args=[qr.token]))
        self.assertNotContains(response, "instagram.com/hidden.contact")
        self.assertNotContains(response, "tel:")
        self.assertNotContains(response, "Sertifikatlangan")
