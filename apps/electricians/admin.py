from django.contrib import admin
from .models import ElectricianClient, ElectricianInquiry, ElectricianProfile

@admin.register(ElectricianProfile)
class ElectricianProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "city",
        "experience_years",
        "access_status",
        "payment_reference",
        "is_verified",
    )
    list_filter = ("access_status", "is_verified", "city")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "payment_reference",
    )


@admin.register(ElectricianInquiry)
class ElectricianInquiryAdmin(admin.ModelAdmin):
    list_display = ("client", "electrician", "phone", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = (
        "client__username",
        "client__first_name",
        "client__last_name",
        "electrician__username",
        "electrician__first_name",
        "electrician__last_name",
        "phone",
        "message",
    )
    readonly_fields = ("created_at",)


@admin.register(ElectricianClient)
class ElectricianClientAdmin(admin.ModelAdmin):
    list_display = ("client", "electrician", "created_at")
    search_fields = (
        "client__username",
        "client__first_name",
        "client__last_name",
        "electrician__username",
        "electrician__first_name",
        "electrician__last_name",
    )
    readonly_fields = ("created_at",)