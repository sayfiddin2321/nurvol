from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.electricians.models import ElectricianClient
from apps.qrcodes.models import QRCode, QRScanLog

from apps.projects.models import Floor, Project, ProjectShowcaseSettings, ShowcaseVideo


class DashboardViewTests(TestCase):
    def setUp(self):
        self.electrician = User.objects.create_user(
            username="electrician",
            password="test-password",
            role=User.Role.ELECTRICIAN,
        )
        self.project = Project.objects.create(
            electrician=self.electrician,
            name="Birinchi loyiha",
            status=Project.Status.COMPLETED,
        )
        self.client.force_login(self.electrician)

    def test_dashboard_shows_project_statistics(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats"]["total"], 1)
        self.assertEqual(response.context["stats"]["completed"], 1)
        self.assertEqual(response.context["stats"]["in_progress"], 0)
        self.assertContains(response, "Birinchi loyiha")
        self.assertContains(response, "So'nggi loyihalar")
        self.assertContains(response, 'class="mobile-bottom-nav"')
        self.assertContains(response, "QR kod markazi")
        self.assertContains(response, "Sozlamalar")
        self.assertContains(response, 'class="dashboard-project-cards"')

    def test_dashboard_shows_create_project_empty_state(self):
        self.project.delete()

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hali loyihangiz yo'q")
        self.assertContains(response, "Birinchi loyihani yarating")

    def test_scan_activity_is_limited_to_the_user_projects(self):
        qr_code = QRCode.objects.create(project=self.project)
        for _ in range(2):
            QRScanLog.objects.create(qr_code=qr_code)

        other_electrician = User.objects.create_user(
            username="other-electrician",
            password="test-password",
            role=User.Role.ELECTRICIAN,
        )
        other_project = Project.objects.create(
            electrician=other_electrician,
            name="Boshqa loyiha",
        )
        other_qr = QRCode.objects.create(project=other_project)
        QRScanLog.objects.create(qr_code=other_qr)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.context["scan_total"], 2)
        self.assertEqual(len(response.context["scan_activity"]), 7)
        self.assertEqual(
            sum(day["count"] for day in response.context["scan_activity"]),
            2,
        )

    def test_homepage_only_shows_featured_electricians_public_completed_projects(self):
        customer = User.objects.create_user(username="showcase-customer", role=User.Role.CLIENT)
        another_customer = User.objects.create_user(username="second-customer", role=User.Role.CLIENT)
        featured_project = Project.objects.create(
            electrician=self.electrician,
            client=customer,
            name="Asosiy elektrik ishi",
            work_summary="Yangi elektr tarmog'i",
            is_public=True,
            status=Project.Status.COMPLETED,
        )
        Project.objects.create(
            electrician=self.electrician,
            client=another_customer,
            name="Yashirin loyiha",
            is_public=False,
            status=Project.Status.COMPLETED,
        )
        Project.objects.create(
            electrician=self.electrician,
            name="Tugallanmagan loyiha",
            is_public=True,
            status=Project.Status.IN_PROGRESS,
        )
        other_electrician = User.objects.create_user(
            username="other-featured-electrician",
            role=User.Role.ELECTRICIAN,
        )
        Project.objects.create(
            electrician=other_electrician,
            name="Boshqa elektrik ishi",
            is_public=True,
            status=Project.Status.COMPLETED,
        )
        ProjectShowcaseSettings.objects.create(featured_electrician=self.electrician)

        self.client.logout()
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, featured_project.name)
        self.assertNotContains(response, "Yashirin loyiha")
        self.assertNotContains(response, "Tugallanmagan loyiha")
        self.assertNotContains(response, "Boshqa elektrik ishi")
        self.assertEqual(response.context["showcase_project_count"], 1)
        self.assertEqual(response.context["showcase_client_count"], 1)

    def test_admin_can_choose_active_electrician_for_homepage(self):
        admin = User.objects.create_user(
            username="showcase-admin",
            password="test-password",
            role=User.Role.ADMIN,
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse("projects:showcase_settings"),
            {"featured_electrician": str(self.electrician.pk)},
        )

        self.assertRedirects(response, reverse("projects:showcase_settings"))
        self.assertEqual(
            ProjectShowcaseSettings.objects.get(pk=1).featured_electrician,
            self.electrician,
        )

    def test_homepage_only_shows_active_showcase_videos(self):
        active_video = ShowcaseVideo.objects.create(
            title="Faol ish videosi",
            video_url="https://youtu.be/dQw4w9WgXcQ",
            is_active=True,
        )
        ShowcaseVideo.objects.create(
            title="Yashirin ish videosi",
            video_url="https://youtu.be/abcdefghijk",
            is_active=False,
        )

        self.client.logout()
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, active_video.title)
        self.assertNotContains(response, "Yashirin ish videosi")
        self.assertContains(
            response,
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
        )

    def test_project_list_filters_by_search_status_and_type(self):
        matching = Project.objects.create(
            electrician=self.electrician,
            name="Chilonzor office",
            address="Toshkent, Chilonzor",
            project_type=Project.ProjectType.OFFICE,
            status=Project.Status.IN_PROGRESS,
        )
        Project.objects.create(
            electrician=self.electrician,
            name="Other residence",
            project_type=Project.ProjectType.HOUSE,
            status=Project.Status.DRAFT,
        )

        response = self.client.get(reverse("projects:list"), {
            "q": "Chilonzor",
            "status": Project.Status.IN_PROGRESS,
            "type": Project.ProjectType.OFFICE,
        })

        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(
            response.context["projects"],
            [matching],
        )
        self.assertContains(response, "Chilonzor office")
        self.assertNotContains(response, "Other residence")

    def test_project_detail_shows_gallery_and_qr_without_tabs_or_visibility_controls(self):
        response = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="tab-images"')
        self.assertContains(response, reverse("documents:image_upload", args=[self.project.pk]))
        self.assertContains(response, "QR orqali ulashish")
        self.assertNotContains(response, 'data-tab=')
        self.assertNotContains(response, "Elektr tizimi")
        self.assertNotContains(response, "Sxema va fayllar")
        self.assertNotContains(response, "Pasportni ko'rish")
        self.assertNotContains(response, reverse("projects:toggle_public", args=[self.project.pk]))


    def test_legacy_technical_data_is_preserved_without_showing_extra_sections(self):
        floor = Floor.objects.create(project=self.project, name="1-qavat", floor_number=1)
        response = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="tab-architecture"')
        self.assertTrue(Floor.objects.filter(pk=floor.pk).exists())


    def test_sidebar_technical_links_open_project_tabs(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, reverse("projects:list"))
        self.assertNotContains(response, "Texnik boshqaruv")
        self.assertContains(response, 'name="q"')
        self.assertNotContains(response, 'aria-label="Bildirishnomalar"')

    def test_sidebar_marks_only_electrician_management_active_on_admin_route(self):
        self.electrician.role = User.Role.ADMIN
        self.electrician.save(update_fields=["role"])

        response = self.client.get(reverse("accounts:manage_electricians"))

        management_link = (
            f'href="{reverse("accounts:manage_electricians")}" '
            'class="sidebar-link active"'
        )
        profile_link = (
            f'href="{reverse("electricians:my_profile")}" '
            'class="sidebar-link active"'
        )
        self.assertContains(response, management_link)
        self.assertNotContains(response, profile_link)

    def test_client_without_projects_is_not_shown_a_broken_create_link(self):
        client_user = User.objects.create_user(
            username="client-without-project",
            password="OriginalPassword123!",
            role=User.Role.CLIENT,
        )
        self.client.force_login(client_user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elektrikingizdan")
        self.assertNotContains(response, reverse("projects:create"))

    def test_client_direct_project_creation_redirects_with_explanation(self):
        client_user = User.objects.create_user(
            username="client-cannot-create",
            password="OriginalPassword123!",
            role=User.Role.CLIENT,
        )
        self.client.force_login(client_user)

        response = self.client.get(reverse("projects:create"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Loyiha yaratish faqat elektrik akkauntida mumkin",
        )

    def test_admin_can_open_project_creation_form(self):
        admin_user = User.objects.create_user(
            username="project-admin",
            password="OriginalPassword123!",
            role=User.Role.ADMIN,
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("projects:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Obyekt yarating")

    def test_electrician_can_create_project_and_revision(self):
        response = self.client.post(reverse("projects:create"), {
            "name": "Yangi turar joy",
            "project_type": Project.ProjectType.HOUSE,
            "description": "Sinov loyihasi",
            "address": "Toshkent",
            "building_type": "Kottej",
            "floors_count": "2",
            "start_date": "",
            "completion_date": "",
            "status": Project.Status.IN_PROGRESS,
            "client": "",
            "is_public": "",
        })

        project = Project.objects.get(name="Yangi turar joy")
        self.assertRedirects(
            response,
            reverse("projects:detail", args=[project.pk]),
        )
        self.assertEqual(project.electrician, self.electrician)
        self.assertEqual(project.revisions.count(), 1)

    def test_existing_client_assignment_still_limits_client_project_access(self):
        customer = User.objects.create_user(
            username="assigned-customer",
            password="OriginalPassword123!",
            role=User.Role.CLIENT,
            first_name="Mijoz",
            last_name="Aliyev",
        )
        another_customer = User.objects.create_user(
            username="another-customer",
            role=User.Role.CLIENT,
        )
        ElectricianClient.objects.create(
            electrician=self.electrician,
            client=customer,
        )
        ElectricianClient.objects.create(
            electrician=self.electrician,
            client=another_customer,
        )
        response = self.client.post(reverse("projects:create"), {
            "name": "Mijoz uyi",
            "address": "Toshkent",
            "project_type": Project.ProjectType.HOUSE,
            "description": "",
            "client": str(customer.pk),
        })
        assigned_project = Project.objects.get(name="Mijoz uyi")
        self.assertRedirects(
            response,
            reverse("projects:detail", args=[assigned_project.pk]),
        )
        self.assertIsNone(assigned_project.client)
        assigned_project.client = customer
        assigned_project.save()

        other_project = Project.objects.create(
            electrician=self.electrician,
            client=another_customer,
            name="Boshqa mijoz uyi",
        )
        self.client.force_login(customer)
        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard_response.context["stats"]["total"], 1)
        self.assertContains(dashboard_response, "Mijoz uyi")
        self.assertNotContains(dashboard_response, "Boshqa mijoz uyi")

        list_response = self.client.get(reverse("projects:list"))
        self.assertContains(list_response, "Mijoz uyi")
        self.assertNotContains(list_response, "Boshqa mijoz uyi")
        self.assertEqual(
            self.client.get(
                reverse("projects:detail", args=[assigned_project.pk]),
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("projects:detail", args=[other_project.pk]),
            ).status_code,
            403,
        )

    def test_create_ignores_another_electricians_client(self):
        customer = User.objects.create_user(
            username="private-customer",
            role=User.Role.CLIENT,
        )
        other_electrician = User.objects.create_user(
            username="client-owner-electrician",
            role=User.Role.ELECTRICIAN,
        )
        ElectricianClient.objects.create(
            electrician=other_electrician,
            client=customer,
        )

        response = self.client.post(reverse("projects:create"), {
            "name": "Boshqa elektrik mijozi",
            "address": "Toshkent",
            "project_type": Project.ProjectType.HOUSE,
            "description": "",
            "client": str(customer.pk),
        })

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Project.objects.get(name="Boshqa elektrik mijozi").client)

    def test_project_creation_ignores_electrician_posted_as_client(self):
        response = self.client.post(reverse("projects:create"), {
            "name": "Noto'g'ri mijoz",
            "address": "Toshkent",
            "client": str(self.electrician.pk),
        })

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Project.objects.get(name="Noto'g'ri mijoz").client)

    def test_setup_guide_shows_clear_first_action_and_progress(self):
        response = self.client.get(reverse("projects:setup", args=[self.project.pk]))
        self.assertRedirects(response, reverse("projects:detail", args=[self.project.pk]))

    def test_setup_progress_updates_when_core_records_are_created(self):
        from apps.electrical.models import Circuit, ElectricalPanel
        panel = ElectricalPanel.objects.create(project=self.project, name="Asosiy shit", panel_code="SH-1")
        Circuit.objects.create(project=self.project, panel=panel, name="Yoritish", circuit_code="QF1")
        response = self.client.get(reverse("projects:setup", args=[self.project.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "QF1")
        self.assertNotContains(response, "SH-1")
        self.assertTrue(self.project.circuits.filter(circuit_code="QF1").exists())

    def test_project_passport_orders_circuits_by_circuit_code(self):
        from apps.electrical.models import Circuit, ElectricalPanel
        from apps.maintenance.models import MaintenanceRecord

        panel = ElectricalPanel.objects.create(
            project=self.project,
            name="Asosiy shit",
            panel_code="SH-1",
        )
        Circuit.objects.create(
            project=self.project,
            panel=panel,
            name="Ikkinchi liniya",
            circuit_code="QF2",
        )
        Circuit.objects.create(
            project=self.project,
            panel=panel,
            name="Birinchi liniya",
            circuit_code="QF1",
        )
        MaintenanceRecord.objects.create(
            project=self.project,
            performed_by=self.electrician,
            title="Yillik tekshiruv",
            description="Sinov muvaffaqiyatli.",
            maintenance_date="2026-11-05",
        )

        response = self.client.get(
            reverse("projects:passport", args=[self.project.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["circuits"].values_list("circuit_code", flat=True)),
            ["QF1", "QF2"],
        )
        self.assertContains(response, "QF1")
        self.assertContains(response, "QF2")
        self.assertContains(response, "Yillik tekshiruv")
        self.assertContains(response, "05.11.2026")

    def test_client_is_directed_to_project_detail_instead_of_setup_actions(self):
        client_user = User.objects.create_user(
            username="setup-client",
            role=User.Role.CLIENT,
        )
        self.project.client = client_user
        self.project.save()
        self.client.force_login(client_user)

        response = self.client.get(
            reverse("projects:setup", args=[self.project.pk])
        )

        self.assertRedirects(
            response,
            reverse("projects:detail", args=[self.project.pk]),
        )
