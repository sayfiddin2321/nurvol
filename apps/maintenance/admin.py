from django.contrib import admin
from .models import MaintenanceRecord

@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "performed_by", "maintenance_date", "is_public")
    list_filter = ("is_public",)