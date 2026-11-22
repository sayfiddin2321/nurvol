from django.urls import path
from . import views

app_name = "electricians"

urlpatterns = [
    path("", views.electrician_list_view, name="list"),
    path("me/", views.my_profile_view, name="my_profile"),
    path("me/edit/", views.edit_profile_view, name="edit_profile"),
    path("me/clients/", views.electrician_clients_view, name="clients"),
    path(
        "me/clients/create/",
        views.create_client_account_view,
        name="create_client",
    ),
    path("inquiries/", views.electrician_inquiries_view, name="inquiries"),
    path(
        "inquiries/<int:inquiry_id>/read/",
        views.mark_inquiry_read_view,
        name="mark_inquiry_read",
    ),
    path(
        "<int:user_id>/inquiry/",
        views.send_electrician_inquiry_view,
        name="send_inquiry",
    ),
    path("<int:user_id>/", views.public_profile_view, name="public_profile"),
    path("<int:user_id>/review/", views.add_review_view, name="add_review"),
]