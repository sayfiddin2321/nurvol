from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.projects.models import Project
from apps.documents.models import ProjectRevision

from .models import Circuit, ElectricalPanel


class ElectricalPanelCrudTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="panel-owner",
            password="test-password",
            role=User.Role.ELECTRICIAN,
        )
        self.other_user = User.objects.create_user(
            username="not-owner",
            password="test-password",
            role=User.Role.ELECTRICIAN,
        )
        self.project = Project.objects.create(
            electrician=self.owner,
            name="Panel test project",
        )
        self.panel = ElectricalPanel.objects.create(
            project=self.project,
            name="Main panel",
            panel_code="P-01",
        )

    def test_owner_can_edit_panel_and_change_is_audited(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("electrical:panel_edit", args=[self.panel.pk]),
            {
                "name": "Updated panel",
                "panel_code": "P-02",
                "location_description": "Ground floor",
                "description": "",
                "installed_at": "",
            },
        )

        self.assertRedirects(response, reverse("projects:detail", args=[self.project.pk]))
        self.panel.refresh_from_db()
        self.assertEqual(self.panel.name, "Updated panel")
        self.assertTrue(
            ProjectRevision.objects.filter(
                project=self.project,
                title="Elektr shit yangilandi",
            ).exists()
        )

    def test_non_owner_cannot_edit_or_delete_panel(self):
        self.client.force_login(self.other_user)

        edit_response = self.client.get(
            reverse("electrical:panel_edit", args=[self.panel.pk])
        )
        delete_response = self.client.post(
            reverse("electrical:panel_delete", args=[self.panel.pk])
        )

        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertTrue(ElectricalPanel.objects.filter(pk=self.panel.pk).exists())

    def test_panel_delete_requires_post_confirmation(self):
        self.client.force_login(self.owner)

        confirm_response = self.client.get(
            reverse("electrical:panel_delete", args=[self.panel.pk])
        )
        self.assertEqual(confirm_response.status_code, 200)
        self.assertContains(confirm_response, "O'chirishni tasdiqlang")

        delete_response = self.client.post(
            reverse("electrical:panel_delete", args=[self.panel.pk])
        )
        self.assertRedirects(
            delete_response,
            reverse("projects:detail", args=[self.project.pk]),
        )
        self.assertFalse(ElectricalPanel.objects.filter(pk=self.panel.pk).exists())

    def test_circuit_form_preselects_the_requested_project_panel(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("electrical:circuit_create", args=[self.project.pk]),
            {"panel": self.panel.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"]["panel"].value(), self.panel.pk)

    def test_owner_can_create_circuit_and_returns_to_setup(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("electrical:circuit_create", args=[self.project.pk]),
            {
                "panel": self.panel.pk,
                "name": "Yoritish liniyasi",
                "circuit_code": "QF1",
                "description": "C16 avtomat",
                "is_public": "",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('projects:detail', args=[self.project.pk])}#tab-technical",
        )
        self.assertTrue(
            Circuit.objects.filter(
                project=self.project,
                panel=self.panel,
                circuit_code="QF1",
            ).exists()
        )

    def test_owner_can_create_cable_and_returns_to_setup(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("electrical:cable_create", args=[self.project.pk]),
            {
                "circuit": "",
                "room": "",
                "name": "Oshxona rozetkalari",
                "cable_type": "VVGng-LS",
                "manufacturer": "",
                "cross_section": "3x2.5 mm2",
                "core_count": "3",
                "length_meters": "12.5",
                "installation_location": "Devor ichida",
                "notes": "",
                "is_public": "",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('projects:detail', args=[self.project.pk])}#tab-technical",
        )


class SmartSafetyAdvisorTests(TestCase):
    def test_parse_cross_section(self):
        from .services import parse_cross_section_mm2
        self.assertEqual(parse_cross_section_mm2("3x2.5"), 2.5)
        self.assertEqual(parse_cross_section_mm2("3×1,5 mm²"), 1.5)
        self.assertEqual(parse_cross_section_mm2("4 mm2"), 4.0)
        self.assertEqual(parse_cross_section_mm2("10"), 10.0)

    def test_parse_breaker_amperage(self):
        from .services import parse_breaker_amperage
        self.assertEqual(parse_breaker_amperage("C16"), 16)
        self.assertEqual(parse_breaker_amperage("B10"), 10)
        self.assertEqual(parse_breaker_amperage("QF-25"), 25)
        self.assertEqual(parse_breaker_amperage("32A"), 32)

    def test_evaluate_cable_safety_rules(self):
        from .services import evaluate_cable_safety
        # Safe 2.5mm² on 16A
        safe = evaluate_cable_safety(2.5, 16)
        self.assertEqual(safe["status"], "safe")
        self.assertEqual(safe["recommended_breaker"], "16A")

        # Dangerous 1.5mm² on 25A
        danger = evaluate_cable_safety(1.5, 25)
        self.assertEqual(danger["status"], "danger")
        self.assertIn("O'TA XAVFLI", danger["message"])

