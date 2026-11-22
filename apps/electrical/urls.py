from django.urls import path
from . import views

app_name = "electrical"

urlpatterns = [
    path("projects/<int:project_pk>/panels/create/", views.panel_create_view, name="panel_create"),
    path("panels/<int:pk>/edit/", views.panel_edit_view, name="panel_edit"),
    path("panels/<int:pk>/delete/", views.panel_delete_view, name="panel_delete"),
    path("projects/<int:project_pk>/circuits/create/", views.circuit_create_view, name="circuit_create"),
    path("circuits/<int:pk>/edit/", views.circuit_edit_view, name="circuit_edit"),
    path("circuits/<int:pk>/delete/", views.circuit_delete_view, name="circuit_delete"),
    path("projects/<int:project_pk>/cables/create/", views.cable_create_view, name="cable_create"),
    path("cables/<int:pk>/edit/", views.cable_edit_view, name="cable_edit"),
    path("cables/<int:pk>/delete/", views.cable_delete_view, name="cable_delete"),
    path("projects/<int:project_pk>/devices/create/", views.device_create_view, name="device_create"),
    path("devices/<int:pk>/edit/", views.device_edit_view, name="device_edit"),
    path("devices/<int:pk>/delete/", views.device_delete_view, name="device_delete"),
]