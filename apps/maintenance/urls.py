from django.urls import path
from . import views

app_name = "maintenance"

urlpatterns = [
    path("projects/<int:project_pk>/create/", views.record_create_view, name="record_create"),
    path("records/<int:pk>/edit/", views.record_edit_view, name="record_edit"),
    path("records/<int:pk>/delete/", views.record_delete_view, name="record_delete"),
]