from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.projects.models import Project

from .models import MaintenanceRecord


class MaintenanceRecordViewsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="maintenance-owner",
            password="test-password",
            role=User.Role.ELECTRICIAN,
        )
        self.project = Project.objects.create(
            electrician=self.owner,
            name="Maintenance test project",
        )
        self.client.force_login(self.owner)

    def test_create_form_uses_existing_model_fields(self):
        response = self.client.get(
            reverse("maintenance:record_create", args=[self.project.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="title"')
        self.assertContains(response, 'name="maintenance_date"')
        self.assertNotContains(response, 'name="record_type"')

    def test_create_saves_public_service_history(self):
        response = self.client.post(
            reverse("maintenance:record_create", args=[self.project.pk]),
            {
                "title": "Shit tekshiruvi",
                "description": "Ulanishlar va himoya avtomatlari tekshirildi.",
                "maintenance_date": "2026-11-05",
                "notes": "Ichki izoh",
                "is_public": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse("projects:detail", args=[self.project.pk]),
        )
        record = MaintenanceRecord.objects.get(project=self.project)
        self.assertEqual(record.title, "Shit tekshiruvi")
        self.assertEqual(record.maintenance_date.isoformat(), "2026-11-05")
        self.assertTrue(record.is_public)
