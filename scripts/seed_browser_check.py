"""Run with: python -m scripts.seed_browser_check (isolated database and media)."""
import json
import os
from io import BytesIO
from pathlib import Path

os.environ["DJANGO_SETTINGS_MODULE"] = "scripts.qa_settings"
import django
django.setup()

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from PIL import Image, ImageDraw
from apps.accounts.models import User
from apps.projects.models import Project
from apps.documents.services import save_project_image
from apps.electrical.models import ElectricalPanel, Circuit, Cable
from apps.qrcodes.services import get_or_create_building_qr

call_command("migrate", verbosity=0)
owner, _ = User.objects.get_or_create(username="browser-electrician", defaults={"role": "electrician"})
owner.set_password("Browser-QA-927!")
owner.first_name, owner.last_name, owner.phone = "Ali", "Valiyev", "+998 90 123 45 67"
owner.save()
profile = owner.electrician_profile
profile.company_name, profile.telegram, profile.instagram = "Ali Elektr", "usta_ali", "usta.ali"
profile.show_phone_public = profile.show_telegram_public = profile.show_instagram_public = True
profile.save()
admin, _ = User.objects.get_or_create(username="browser-admin", defaults={"role": "admin"})
admin.set_password("Browser-QA-927!")
admin.first_name, admin.last_name = "QA", "Administrator"
admin.is_staff = True
admin.is_superuser = True
admin.is_active = True
admin.role = "admin"
admin.save()
project, _ = Project.objects.get_or_create(electrician=owner, name="Chilonzor xonadoni", defaults={"address": "Toshkent, Chilonzor 12-mavze", "is_public": True, "description": "Yoritish va rozetka liniyalari yangilandi.", "work_summary": "Panel yig'ildi, liniyalar belgilandi va sinovdan o'tkazildi."})
panel, _ = ElectricalPanel.objects.get_or_create(project=project, panel_code="SH-1", defaults={"name": "Asosiy elektr paneli", "location_description": "Kirish yo'lagi", "is_public": True})
Circuit.objects.get_or_create(project=project, circuit_code="QF1", defaults={"panel": panel, "name": "Oshxona rozetkalari", "description": "C20, 30 mA UZO", "is_public": True})
Cable.objects.get_or_create(project=project, name="Oshxona kabeli", defaults={"cable_type": "VVGng-LS", "cross_section": "3×2.5", "core_count": 3, "length_meters": "18.5", "is_public": True})
fixtures = settings.QA_ROOT / "fixtures"
fixtures.mkdir(exist_ok=True)
samples = [("panel-wide.jpg", (1600, 900), "#1e293b", "Elektr paneli"), ("cable-portrait.jpg", (600, 1200), "#075985", "Kabel yo'nalishi"), ("plan-square.jpg", (1000, 1000), "#e2e8f0", "Qavat rejasi")]
for index, (name, size, color, title) in enumerate(samples):
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    for offset in range(80, min(size), 100):
        draw.rounded_rectangle((offset, 60, offset + 40, size[1] - 60), radius=10, outline="#38bdf8", width=8)
    draw.text((24, 24), title, fill="#2563eb" if index == 2 else "white")
    buffer = BytesIO(); image.save(buffer, "JPEG")
    (fixtures / name).write_bytes(buffer.getvalue())
    if not project.images.filter(title=title).exists():
        save_project_image(project, SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg"), "floor_plan" if index == 2 else "panel", owner, "Montaj tekshiruvi", title=title)
qr = get_or_create_building_qr(project)
data = {"base": settings.SITE_URL, "project": project.pk, "qr": str(qr.token), "fixtures": [str((fixtures / sample[0]).resolve()) for sample in samples]}
(settings.QA_ROOT / "fixture.json").write_text(json.dumps(data), encoding="utf-8")
print("Isolated browser fixtures ready:", project.pk)
