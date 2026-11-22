from django.contrib import admin
from .models import QRCode, QRScanLog

@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ("token", "project", "panel", "is_active", "created_at")
    list_filter = ("is_active",)

@admin.register(QRScanLog)
class QRScanLogAdmin(admin.ModelAdmin):
    list_display = ("qr_code", "scanned_at", "user_agent")