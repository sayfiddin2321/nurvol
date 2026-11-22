from django.contrib import admin
from .models import ElectricalPanel, Circuit, Cable, ElectricalDevice

@admin.register(ElectricalPanel)
class ElectricalPanelAdmin(admin.ModelAdmin):
    list_display = ("name", "panel_code", "project", "is_public")

@admin.register(Circuit)
class CircuitAdmin(admin.ModelAdmin):
    list_display = ("circuit_code", "name", "panel", "project")

@admin.register(Cable)
class CableAdmin(admin.ModelAdmin):
    list_display = ("name", "cable_type", "project", "cross_section")

@admin.register(ElectricalDevice)
class ElectricalDeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "device_type", "project", "room")