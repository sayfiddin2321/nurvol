from django.core.exceptions import ValidationError
from django.db import models
from apps.projects.models import Project, Room


class ElectricalPanel(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="panels")
    name = models.CharField(max_length=150)
    panel_code = models.CharField(max_length=50)
    location_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    installed_at = models.DateField(null=True, blank=True)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "panel_code"], name="unique_panel_code_per_project")
        ]

    def __str__(self):
        return f"{self.name} ({self.panel_code})"


class Circuit(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="circuits")
    panel = models.ForeignKey(ElectricalPanel, on_delete=models.RESTRICT, related_name="circuits")
    name = models.CharField(max_length=150)
    circuit_code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "circuit_code"], name="unique_circuit_code_per_project")
        ]

    def clean(self):
        if self.panel_id and self.project_id and self.panel.project_id != self.project_id:
            raise ValidationError("Panel va liniya bir loyihaga tegishli bo'lishi shart.")

    def __str__(self):
        return self.circuit_code


class Cable(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="cables")
    circuit = models.ForeignKey(Circuit, on_delete=models.SET_NULL, null=True, blank=True, related_name="cables")
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name="cables")
    name = models.CharField(max_length=150)
    cable_type = models.CharField(max_length=100)
    manufacturer = models.CharField(max_length=100, blank=True)
    cross_section = models.CharField(max_length=50)
    core_count = models.PositiveSmallIntegerField(default=1)
    length_meters = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    installation_location = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.circuit_id and self.circuit.project_id != self.project_id:
            raise ValidationError("Liniya boshqa loyihaga tegishli.")
        if self.room_id and self.room.floor.project_id != self.project_id:
            raise ValidationError("Xona boshqa loyihaga tegishli.")

    def __str__(self):
        return self.name


class ElectricalDevice(models.Model):
    class DeviceType(models.TextChoices):
        SOCKET = "socket", "Rozetka"
        SWITCH = "switch", "Viklyuchatel"
        LIGHT = "light", "Chiroq"
        OTHER = "other", "Boshqa"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="devices")
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name="devices")
    circuit = models.ForeignKey(Circuit, on_delete=models.SET_NULL, null=True, blank=True, related_name="devices")
    name = models.CharField(max_length=150)
    device_type = models.CharField(max_length=30, choices=DeviceType.choices)
    identifier = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    installed_at = models.DateField(null=True, blank=True)
    is_public = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.device_type})"
