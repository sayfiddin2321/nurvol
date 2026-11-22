from django import forms
from .models import MaintenanceRecord


class MaintenanceRecordForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRecord
        fields = ("title", "description", "maintenance_date", "notes", "is_public")
        widgets = {"maintenance_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].label = "Xizmat nomi"
        self.fields["description"].label = "Bajarilgan ishlar"
        self.fields["maintenance_date"].label = "Xizmat sanasi"