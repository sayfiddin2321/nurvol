from importlib import import_module
from io import StringIO
import os
from unittest.mock import patch

from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from .models import User


class SuperuserRoleTests(TestCase):
    def test_createsuperuser_command_creates_an_application_administrator(self):
        with patch.dict(os.environ, {"DJANGO_SUPERUSER_PASSWORD": "Admin-Test-927!"}):
            call_command(
                "createsuperuser", username="command-admin", email="admin@example.com",
                interactive=False, stdout=StringIO(),
            )
        user = User.objects.get(username="command-admin")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("Admin-Test-927!"))
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Administrator")
        self.assertContains(response, reverse("projects:create"))
        self.assertEqual(self.client.get(reverse("accounts:manage_electricians")).status_code, 200)

    def test_superuser_role_cannot_default_to_client(self):
        user = User.objects.create_superuser(username="explicit-admin", role=User.Role.CLIENT)
        user.refresh_from_db()
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertFalse(user.is_client)

    async def test_async_superuser_creation_also_sets_admin_role(self):
        user = await User.objects.acreate_superuser(username="async-admin")
        await user.arefresh_from_db()
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_regular_users_keep_their_requested_roles(self):
        client = User.objects.create_user(username="regular-client")
        electrician = User.objects.create_user(username="regular-electrician", role=User.Role.ELECTRICIAN)
        self.assertEqual(client.role, User.Role.CLIENT)
        self.assertFalse(client.is_superuser)
        self.assertEqual(electrician.role, User.Role.ELECTRICIAN)
        self.assertFalse(electrician.is_superuser)

    def test_superuser_staff_and_permission_requirements_are_preserved(self):
        for field in ("is_staff", "is_superuser"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                User.objects.create_superuser(username="invalid-admin", **{field: False})
        self.assertFalse(User.objects.filter(username="invalid-admin").exists())

    def test_migration_repairs_existing_superusers_without_changing_passwords_or_clients(self):
        legacy_admin = User.objects.create_user(
            username="legacy-admin", password="Old-Password-927!", is_superuser=True, is_staff=True,
        )
        client = User.objects.create_user(username="unmodified-client")
        original_hash = legacy_admin.password
        migration = import_module("apps.accounts.migrations.0005_superuser_admin_role")
        migration.repair_superuser_roles(apps, connection.schema_editor())
        legacy_admin.refresh_from_db()
        client.refresh_from_db()
        self.assertEqual(legacy_admin.role, User.Role.ADMIN)
        self.assertEqual(legacy_admin.password, original_hash)
        self.assertEqual(client.role, User.Role.CLIENT)
