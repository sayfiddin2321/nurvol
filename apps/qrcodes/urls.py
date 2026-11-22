from django.urls import path
from . import views

app_name = "qrcodes"

urlpatterns = [
    path("projects/<int:project_pk>/manage/", views.qr_manage_view, name="manage"),
    path("projects/<int:project_pk>/building/generate/", views.building_qr_generate_view, name="building_generate"),
    path("projects/<int:project_pk>/print/", views.qr_print_view, name="print"),
    path("projects/<int:project_pk>/scans/", views.qr_scans_view, name="scans"),
    path("panels/<int:panel_pk>/create/", views.qr_create_for_panel_view, name="panel_create"),
    path("panels/<int:panel_pk>/generate/", views.qr_create_for_panel_view, name="panel_generate"),
    path("download/<uuid:token>/", views.qr_download_view, name="download"),
    path("image/<uuid:token>/", views.qr_download_view, {"download": False}, name="image"),
    path("<uuid:token>/toggle/", views.qr_toggle_active_view, name="toggle"),
    path("<uuid:token>/regenerate/", views.qr_regenerate_view, name="regenerate"),
    path("<uuid:token>/", views.public_qr_view, name="public"),
]
