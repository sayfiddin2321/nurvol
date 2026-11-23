from django.urls import path
from . import views

app_name = "documents"

urlpatterns = [
    path("projects/<int:project_pk>/images/upload/", views.image_upload_view, name="image_upload"),
    path("projects/<int:project_pk>/media/upload/", views.media_upload_view, name="media_upload"),
    path("images/<int:pk>/view/", views.image_view, name="image_view"),
    path("images/<int:pk>/display/", views.image_display_view, name="image_display"),
    path("images/<int:pk>/edit/", views.image_edit_view, name="image_edit"),
    path("images/<int:pk>/thumbnail/", views.image_thumbnail_view, name="image_thumbnail"),
    path("images/<int:pk>/delete/", views.image_delete_view, name="image_delete"),
    path("images/<int:pk>/delete/confirm/", views.media_delete_confirm_view, {"kind": "image"}, name="image_delete_confirm"),
    path("projects/<int:project_pk>/documents/upload/", views.document_upload_view, name="document_upload"),
    path("documents/<int:pk>/download/", views.document_download_view, name="document_download"),
    path("documents/<int:pk>/preview/", views.document_preview_view, name="document_preview"),
    path("documents/<int:pk>/edit/", views.document_edit_view, name="document_edit"),
    path("documents/<int:pk>/delete/", views.document_delete_view, name="document_delete"),
    path("documents/<int:pk>/delete/confirm/", views.media_delete_confirm_view, {"kind": "document"}, name="document_delete_confirm"),
    path("projects/<int:project_pk>/revisions/", views.revision_list_view, name="revision_list"),
]
