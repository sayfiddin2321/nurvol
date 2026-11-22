from io import BytesIO
from django.conf import settings
from django.urls import reverse
import qrcode

from .models import QRCode


def build_qr_url(token, request=None):
    path = reverse("qrcodes:public", args=[token])
    if request is not None:
        return request.build_absolute_uri(path)
    base = getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")
    return f"{base}{path}"


def generate_qr_png_bytes(token, request=None):
    url = build_qr_url(token, request=request)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#071426", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def get_or_create_building_qr(project):
    qr, _ = QRCode.objects.get_or_create(project=project, panel=None)
    return qr


def get_or_create_panel_qr(panel):
    qr, _ = QRCode.objects.get_or_create(project=panel.project, panel=panel)
    return qr