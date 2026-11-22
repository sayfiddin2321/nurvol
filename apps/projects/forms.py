from django import forms
from apps.accounts.models import User
from apps.electricians.models import ElectricianProfile
from .models import Project, ProjectShowcaseSettings, Floor, Room


class ProjectCreateForm(forms.ModelForm):
    address = forms.CharField(max_length=255, required=False, label="Manzil (ixtiyoriy)")

    class Meta:
        model = Project
        fields = ("name", "address", "description", "status")
        labels = {
            "name": "Obyekt nomi",
            "description": "Qisqa izoh (ixtiyoriy)",
            "status": "Obyekt holati",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 3, "maxlength": 1000})}

    def __init__(self, *args, **kwargs):
        kwargs.pop("electrician", None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["name"].widget.attrs.update(autofocus=True, placeholder="Masalan: Chilonzordagi xonadon")
        self.fields["address"].widget.attrs["autocomplete"] = "street-address"
        self.fields["status"].required = False
        self.fields["status"].initial = Project.Status.DRAFT

    def clean_status(self):
        return self.cleaned_data.get("status") or Project.Status.DRAFT


class ProjectForm(ProjectCreateForm):
    pass


class ProjectShowcaseSettingsForm(forms.ModelForm):
    class Meta:
        model = ProjectShowcaseSettings
        fields = ("featured_electrician",)
        labels = {"featured_electrician": "Bosh elektrik"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["featured_electrician"].queryset = User.objects.filter(
            role=User.Role.ELECTRICIAN,
            is_active=True,
            electrician_profile__access_status=ElectricianProfile.AccessStatus.ACTIVE,
        ).order_by("first_name", "last_name", "username")
        self.fields["featured_electrician"].required = False
        self.fields["featured_electrician"].empty_label = "Tanlanmagan"
        self.fields["featured_electrician"].widget.attrs["class"] = "form-control"
        self.fields["featured_electrician"].help_text = (
            "Bosh sahifada shu elektrikning ommaga ochiq va tugallangan ishlari ko'rsatiladi."
        )


class FloorForm(forms.ModelForm):
    class Meta:
        model = Floor
        fields = ("name", "floor_number", "description")


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ("name", "room_type", "description")
