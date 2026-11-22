import uuid
from django.db import models


class QRCode(models.Model):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="qr_codes")
    panel = models.ForeignKey(
        "electrical.ElectricalPanel",
        on_delete=models.PROTECT,
        null=True, blank=True, related_name="qr_codes",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project"],
                condition=models.Q(panel__isnull=True),
                name="unique_building_qr_per_project",
            ),
            models.UniqueConstraint(
                fields=["panel"],
                condition=models.Q(panel__isnull=False),
                name="unique_panel_qr_per_panel",
            ),
        ]

    def __str__(self):
        return f"QR {self.project.name}" + (f" / {self.panel.panel_code}" if self.panel else "")


class QRScanLog(models.Model):
    qr_code = models.ForeignKey(QRCode, on_delete=models.CASCADE, related_name="scans")
    scanned_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user_agent = models.CharField(max_length=255, blank=True)
    referer = models.CharField(max_length=255, blank=True)