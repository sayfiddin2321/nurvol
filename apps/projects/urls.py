from django.urls import path
from . import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list_view, name="list"),
    path(
        "manage/showcase/",
        views.project_showcase_settings_view,
        name="showcase_settings",
    ),
    path("create/", views.project_create_view, name="create"),
    path("<int:pk>/setup/", views.project_setup_view, name="setup"),
    path("<int:pk>/", views.project_detail_view, name="detail"),
    path("<int:pk>/passport/", views.project_passport_view, name="passport"),
    path("<int:pk>/edit/", views.project_edit_view, name="edit"),
    path("<int:pk>/delete/", views.project_delete_view, name="delete"),
    path("<int:pk>/share/", views.project_share_view, name="share"),
    path("<int:pk>/toggle-public/", views.project_toggle_public_view, name="toggle_public"),
    path("<int:project_pk>/floors/create/", views.floor_create_view, name="floor_create"),
    path("floors/<int:pk>/edit/", views.floor_edit_view, name="floor_edit"),
    path("floors/<int:pk>/delete/", views.floor_delete_view, name="floor_delete"),
    path("floors/<int:floor_pk>/rooms/create/", views.room_create_view, name="room_create"),
    path("rooms/<int:pk>/edit/", views.room_edit_view, name="room_edit"),
    path("rooms/<int:pk>/delete/", views.room_delete_view, name="room_delete"),
]
