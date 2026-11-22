from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import ContactInquiry, PaymentSettings, User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Qo'shimcha", {"fields": ("role", "phone")}),
    )
    list_display = ("username", "email", "account_role", "is_staff")
    list_filter = ("role", "is_staff", "is_superuser")

    @admin.display(description="Akkaunt turi")
    def account_role(self, user):
        return user.role_label


@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "plan", "is_read", "created_at")
    list_filter = ("plan", "is_read", "created_at")
    list_editable = ("is_read",)
    search_fields = ("name", "phone", "message")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    list_display = ("__str__", "card_number", "phone", "public_phone", "updated_at")
