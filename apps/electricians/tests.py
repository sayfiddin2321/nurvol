from django.test import TestCase
from django.urls import reverse
from apps.accounts.models import User
from .models import (
    ElectricianClient,
    ElectricianInquiry,
    ElectricianProfile,
    ElectricianReview,
)


class ElectricianMarketplaceTests(TestCase):
    def setUp(self):
        self.electrician_user = User.objects.create_user(
            username="electrician_pro",
            email="pro@example.com",
            password="testpassword123",
            role=User.Role.ELECTRICIAN,
            first_name="Usta",
            last_name="Ali",
        )
        self.profile = self.electrician_user.electrician_profile
        self.profile.specialization = "Avtomatika va Elektr Montaj"
        self.profile.city = "Toshkent"
        self.profile.experience_years = 7
        self.profile.is_verified = True
        self.profile.show_phone_public = True
        self.profile.show_telegram_public = True
        self.profile.save()

        self.client_user = User.objects.create_user(
            username="client_user",
            email="client@example.com",
            password="testpassword123",
            role=User.Role.CLIENT,
            first_name="Mijoz",
            last_name="Vali",
        )

    def test_marketplace_list_view_accessible(self):
        response = self.client.get(reverse("electricians:list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "electricians/list.html")
        self.assertContains(response, "Usta Ali")
        self.assertContains(response, "Toshkent")

    def test_marketplace_search_filter(self):
        # Search by city
        response = self.client.get(reverse("electricians:list"), {"city": "Toshkent"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Usta Ali")

        # Search by non-matching query
        response2 = self.client.get(reverse("electricians:list"), {"q": "NonExistentName"})
        self.assertEqual(response2.status_code, 200)
        self.assertNotContains(response2, "Usta Ali")

    def test_public_profile_view(self):
        url = reverse("electricians:public_profile", args=[self.electrician_user.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "electricians/public_profile.html")
        self.assertContains(response, "Usta Ali")
        self.assertContains(response, "Avtomatika va Elektr Montaj")

    def test_client_can_send_request_and_electrician_receives_it_in_inbox(self):
        self.client.force_login(self.client_user)
        profile_url = reverse(
            "electricians:public_profile",
            args=[self.electrician_user.pk],
        )
        response = self.client.get(profile_url)
        self.assertContains(response, "Elektrikka so'rov yuborish")

        response = self.client.post(
            reverse("electricians:send_inquiry", args=[self.electrician_user.pk]),
            {
                "phone": "+998901112233",
                "message": "Uy elektr simlarini tekshirtirmoqchiman.",
            },
        )
        self.assertRedirects(response, profile_url)
        inquiry = ElectricianInquiry.objects.get()
        self.assertEqual(inquiry.client, self.client_user)
        self.assertEqual(inquiry.electrician, self.electrician_user)
        self.assertEqual(inquiry.phone, "+998901112233")
        self.assertTrue(ElectricianClient.objects.filter(
            electrician=self.electrician_user,
            client=self.client_user,
        ).exists())

        self.client.force_login(self.electrician_user)
        inbox_url = reverse("electricians:inquiries")
        response = self.client.get(inbox_url)
        self.assertContains(response, "Uy elektr simlarini tekshirtirmoqchiman.")
        self.assertContains(response, "Mijoz Vali")
        self.assertEqual(response.context["unread_count"], 1)

        response = self.client.post(
            reverse("electricians:mark_inquiry_read", args=[inquiry.pk]),
        )
        self.assertRedirects(response, inbox_url)
        inquiry.refresh_from_db()
        self.assertTrue(inquiry.is_read)

    def test_electrician_can_only_see_and_mark_their_own_requests(self):
        inquiry = ElectricianInquiry.objects.create(
            electrician=self.electrician_user,
            client=self.client_user,
            phone="+998901112233",
            message="Usta kerak.",
        )
        another_electrician = User.objects.create_user(
            username="another-electrician",
            password="testpassword123",
            role=User.Role.ELECTRICIAN,
        )
        self.client.force_login(another_electrician)

        response = self.client.get(reverse("electricians:inquiries"))
        self.assertNotContains(response, "Usta kerak.")
        response = self.client.post(
            reverse("electricians:mark_inquiry_read", args=[inquiry.pk]),
        )
        self.assertEqual(response.status_code, 404)
        inquiry.refresh_from_db()
        self.assertFalse(inquiry.is_read)

    def test_electrician_can_create_private_client_account_and_one_time_credentials(self):
        self.client.force_login(self.electrician_user)

        response = self.client.post(
            reverse("electricians:create_client"),
            {
                "username": "usta-mijozi",
                "first_name": "Yangi",
                "last_name": "Mijoz",
                "phone": "+998901234567",
                "password1": "MijozParol123",
                "password2": "MijozParol123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "electricians/client_credentials.html")
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertContains(response, "usta-mijozi")
        client_user = User.objects.get(username="usta-mijozi")
        self.assertEqual(client_user.role, User.Role.CLIENT)
        self.assertTrue(client_user.check_password("MijozParol123"))
        self.assertTrue(ElectricianClient.objects.filter(
            electrician=self.electrician_user,
            client=client_user,
        ).exists())

        another_electrician = User.objects.create_user(
            username="different-electrician",
            role=User.Role.ELECTRICIAN,
        )
        self.client.force_login(another_electrician)
        response = self.client.get(reverse("electricians:clients"))
        self.assertNotContains(response, "usta-mijozi")

    def test_electrician_client_account_rejects_mismatched_passwords(self):
        self.client.force_login(self.electrician_user)

        response = self.client.post(
            reverse("electricians:create_client"),
            {
                "username": "mismatch-customer",
                "first_name": "Yangi",
                "last_name": "Mijoz",
                "password1": "MijozParol123",
                "password2": "BoshqaParol123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("password2", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="mismatch-customer").exists())

    def test_add_review_as_client(self):
        self.client.login(username="client_user", password="testpassword123")
        url = reverse("electricians:add_review", args=[self.electrician_user.pk])
        response = self.client.post(url, {
            "rating": 5,
            "comment": "Ajoyib mutaxassis, ishini puxta va o'z vaqtida bajardi!",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ElectricianReview.objects.count(), 1)
        review = ElectricianReview.objects.first()
        self.assertEqual(review.electrician, self.electrician_user)
        self.assertEqual(review.author, self.client_user)
        self.assertEqual(review.rating, 5)

    def test_cannot_review_self(self):
        self.client.login(username="electrician_pro", password="testpassword123")
        url = reverse("electricians:add_review", args=[self.electrician_user.pk])
        response = self.client.post(url, {
            "rating": 5,
            "comment": "O'zimga 5 yulduz!",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ElectricianReview.objects.count(), 0)
