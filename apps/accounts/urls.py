from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("contact/", views.contact_inquiry_view, name="contact"),
    path("electrician/access/", views.electrician_access_view, name="electrician_access"),
    path("electrician/payment/", views.submit_payment_view, name="submit_payment"),
    path(
        "electrician/payment-receipt/<int:user_id>/",
        views.payment_receipt_view,
        name="payment_receipt",
    ),
    path("manage/electricians/", views.manage_electricians_view, name="manage_electricians"),
    path(
        "manage/payment-settings/",
        views.payment_settings_view,
        name="payment_settings",
    ),
    path(
        "manage/contact-inquiries/<int:inquiry_id>/read/",
        views.mark_contact_inquiry_read_view,
        name="mark_contact_inquiry_read",
    ),
    path(
        "manage/electricians/<int:profile_id>/access/",
        views.update_electrician_access_view,
        name="update_electrician_access",
    ),
    path(
        "manage/electricians/<int:profile_id>/account/",
        views.set_electrician_account_active_view,
        name="set_electrician_account_active",
    ),
    path("logout/", views.logout_view, name="logout"),
    path("profile/edit/", views.profile_edit_view, name="profile_edit"),
    path("settings/", views.settings_view, name="settings"),
    path("password/change/", views.change_password_view, name="password_change"),
    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]