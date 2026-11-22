from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.documents.models import ProjectDocument
from apps.electrical.models import ElectricalPanel, Circuit
from .models import Project


class SimplifiedProjectWorkflowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="quick-owner", role="electrician")
        self.other = User.objects.create_user(username="other-owner", role="electrician")
        self.client.force_login(self.owner)

    def test_name_is_sufficient_and_extra_fields_cannot_change_owner_or_assign_client(self):
        response = self.client.post(reverse("projects:create"), {
            "name": "Yangi obyekt", "electrician": self.other.pk, "client": self.other.pk, "is_public": "",
        })
        project = Project.objects.get(name="Yangi obyekt")
        self.assertRedirects(response, reverse("projects:detail", args=[project.pk]))
        self.assertEqual(project.electrician, self.owner)
        self.assertEqual(project.project_type, Project.ProjectType.OTHER)
        self.assertTrue(project.is_public)
        self.assertEqual(project.address, "")
        self.assertIsNone(project.client)
        self.assertEqual(project.status, Project.Status.DRAFT)
        self.assertEqual(project.revisions.count(), 1)

    def test_missing_name_does_not_create_an_object(self):
        response = self.client.post(reverse("projects:create"), {"address": "Toshkent"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)
        self.assertFalse(Project.objects.exists())


    def test_other_electrician_cannot_edit_publish_or_delete(self):
        project = Project.objects.create(electrician=self.owner, name="Private")
        self.client.force_login(self.other)
        for route in ["edit", "share", "toggle_public", "delete"]:
            self.assertEqual(self.client.post(reverse("projects:" + route, args=[project.pk]), {"name": "Changed"}).status_code, 403)
        project.refresh_from_db()
        self.assertEqual(project.name, "Private")
        self.assertFalse(project.is_public)

    def test_assigned_client_print_contains_only_public_technical_data(self):
        customer = User.objects.create_user(username="assigned-customer", role="client")
        project = Project.objects.create(electrician=self.owner, client=customer, name="Client passport")
        private_panel = ElectricalPanel.objects.create(project=project, name="Secret panel", panel_code="SECRET-PANEL")
        Circuit.objects.create(project=project, panel=private_panel, name="Secret circuit", circuit_code="SECRET-CIRCUIT")
        public_panel = ElectricalPanel.objects.create(project=project, name="Visible panel", panel_code="PUBLIC-PANEL", is_public=True)
        Circuit.objects.create(project=project, panel=public_panel, name="Actual circuit", circuit_code="QF1", description="C20, 30 mA", is_public=True)
        self.client.force_login(customer)
        response = self.client.get(reverse("projects:passport", args=[project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PUBLIC-PANEL")
        self.assertContains(response, "C20, 30 mA")
        self.assertNotContains(response, "SECRET-PANEL")
        self.assertNotContains(response, "SECRET-CIRCUIT")
        self.assertNotContains(response, "VVGng-LS")
        self.assertNotContains(response, "C16A")

    def test_project_with_panel_and_circuit_can_be_deleted_together(self):
        project = Project.objects.create(electrician=self.owner, name="Remove all")
        panel = ElectricalPanel.objects.create(project=project, name="Panel", panel_code="P1")
        Circuit.objects.create(project=project, panel=panel, name="Circuit", circuit_code="Q1")
        response = self.client.post(reverse("projects:delete", args=[project.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())

    def test_panel_with_circuits_has_a_readable_deletion_error(self):
        project = Project.objects.create(electrician=self.owner, name="Panel removal")
        panel = ElectricalPanel.objects.create(project=project, name="Panel", panel_code="P1")
        Circuit.objects.create(project=project, panel=panel, name="Circuit", circuit_code="Q1")
        response = self.client.post(reverse("electrical:panel_delete", args=[panel.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Avval shu panelga bog&#x27;langan liniyalarni")
        self.assertTrue(ElectricalPanel.objects.filter(pk=panel.pk).exists())

    def test_legacy_private_project_can_be_shared_only_by_owner_using_post(self):
        from apps.qrcodes.models import QRCode
        project = Project.objects.create(electrician=self.owner, name="Legacy", is_public=False)
        qr = QRCode.objects.create(project=project, is_active=False)
        url = reverse("projects:share", args=[project.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse("projects:detail", args=[project.pk]) + "#qr")
        project.refresh_from_db()
        qr.refresh_from_db()
        self.assertTrue(project.is_public)
        self.assertTrue(qr.is_active)
        original_token = qr.token
        self.client.post(url)
        qr.refresh_from_db()
        self.assertEqual(qr.token, original_token)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("qrcodes:public", args=[qr.token])).status_code, 200)

    def test_simple_edit_preserves_existing_metadata_and_cannot_change_owner(self):
        project = Project.objects.create(electrician=self.owner, name="Original", floors_count=4, work_summary="Old work", status="completed", is_public=True)
        response = self.client.post(reverse("projects:edit", args=[project.pk]), {
            "name": "Updated", "description": "New note", "electrician": self.other.pk,
            "floors_count": 1, "status": "draft", "is_public": "",
        })
        self.assertRedirects(response, reverse("projects:detail", args=[project.pk]))
        project.refresh_from_db()
        self.assertEqual(project.name, "Updated")
        self.assertEqual(project.description, "New note")
        self.assertEqual(project.floors_count, 4)
        self.assertEqual(project.work_summary, "Old work")
        self.assertEqual(project.status, "draft")
        self.assertEqual(project.electrician, self.owner)
        self.assertTrue(project.is_public)
