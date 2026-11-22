from django import forms
from .models import ElectricalPanel, Circuit, Cable, ElectricalDevice
from .services import evaluate_cable_safety, parse_cross_section_mm2, parse_breaker_amperage
from apps.projects.models import Room


class ElectricalPanelForm(forms.ModelForm):
    class Meta:
        model = ElectricalPanel
        fields = ("name", "panel_code", "location_description", "description", "installed_at", "is_public")
        widgets = {"installed_at": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "name": "Shit nomi",
            "panel_code": "Shit kodi",
            "location_description": "Qayerda joylashgan?",
            "description": "Qo'shimcha izoh",
            "installed_at": "O'rnatilgan sana",
            "is_public": "Ommaviy pasportda ko'rsatish",
        }
        help_texts = {
            "name": "Masalan: 1-qavat taqsimlash shiti.",
            "panel_code": "Shit yorlig'idagi kodni kiriting. Masalan: ЩР-1.",
            "location_description": "Masalan: 1-qavat, kirish yo'lagi.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class CircuitForm(forms.ModelForm):
    class Meta:
        model = Circuit
        fields = ("panel", "name", "circuit_code", "description", "is_public")
        labels = {
            "panel": "Qaysi shitdan chiqadi?",
            "name": "Bu liniya nimani ta'minlaydi?",
            "circuit_code": "Avtomat / liniya kodi",
            "description": "Himoya avtomati va izoh",
            "is_public": "Ommaviy pasportda ko'rsatish",
        }
        help_texts = {
            "name": "Masalan: Oshxona rozetkalari yoki yotoqxona chiroqlari.",
            "circuit_code": "Avtomatdagi belgini kiriting. Masalan: QF1 yoki B16.",
            "description": "Masalan: C16, 1 qutbli avtomat, 30 mA UZO.",
        }

    def __init__(self, *args, **kwargs):
        project = kwargs.pop("project", None)
        super().__init__(*args, **kwargs)
        _style_fields(self)
        if project:
            self.fields["panel"].queryset = ElectricalPanel.objects.filter(project=project)
        self.fields["panel"].empty_label = "Shitni tanlang"


class CableForm(forms.ModelForm):
    class Meta:
        model = Cable
        fields = (
            "circuit", "room", "name", "cable_type", "manufacturer",
            "cross_section", "core_count", "length_meters",
            "installation_location", "notes", "is_public",
        )
        labels = {
            "circuit": "Qaysi liniyaga bog'laymiz? (ixtiyoriy)",
            "room": "Qaysi xonaga boradi? (ixtiyoriy)",
            "name": "Kabel nomi",
            "cable_type": "Kabel markasi",
            "manufacturer": "Ishlab chiqaruvchi",
            "cross_section": "Tomir soni va kesimi",
            "core_count": "Tomirlar soni",
            "length_meters": "Uzunligi (metr)",
            "installation_location": "Qayerdan va qanday yotqizilgan?",
            "notes": "Qo'shimcha izoh",
            "is_public": "Ommaviy pasportda ko'rsatish",
        }
        help_texts = {
            "name": "Masalan: Oshxona rozetkalari kabeli.",
            "cable_type": "Kabel qobig'idagi markani yozing. Masalan: ВВГнг-LS.",
            "cross_section": "Masalan: 3×2.5 mm². Kabel markirovkasidan qarang.",
            "core_count": "Masalan: 3 tomir — faza, nol va yer.",
            "length_meters": "Taxminiy uzunlikni kiritishingiz mumkin.",
            "installation_location": "Masalan: quvur ichida, devor bo'ylab.",
        }

    def __init__(self, *args, **kwargs):
        project = kwargs.pop("project", None)
        super().__init__(*args, **kwargs)
        _style_fields(self)
        if project:
            self.fields["circuit"].queryset = Circuit.objects.filter(project=project)
            self.fields["room"].queryset = Room.objects.filter(floor__project=project)
        self.fields["circuit"].empty_label = "Liniya tanlanmagan"
        self.fields["room"].empty_label = "Xona tanlanmagan"

    def clean(self):
        cleaned_data = super().clean()
        cross_section_str = cleaned_data.get("cross_section")
        circuit = cleaned_data.get("circuit")
        if cross_section_str and circuit:
            mm2 = parse_cross_section_mm2(cross_section_str)
            circuit_text = f"{circuit.circuit_code} {circuit.description}"
            amps = parse_breaker_amperage(circuit_text)
            if mm2 and amps:
                safety = evaluate_cable_safety(mm2, amps)
                if safety["status"] == "danger":
                    notes = cleaned_data.get("notes") or ""
                    if "XAVFSIZLIK OGOHLANTIRISHI" not in notes:
                        cleaned_data["notes"] = f"{notes}\n[PUE Xavfsizlik Ogohlantirishi: {safety['message']}]".strip()
        return cleaned_data


class ElectricalDeviceForm(forms.ModelForm):
    class Meta:
        model = ElectricalDevice
        fields = ("room", "circuit", "name", "device_type", "identifier", "description", "installed_at", "is_public")
        widgets = {"installed_at": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "room": "Qaysi xonada?",
            "circuit": "Qaysi liniyaga ulangan?",
            "name": "Qurilma nomi",
            "device_type": "Qurilma turi",
            "identifier": "Belgi yoki raqami",
            "description": "Izoh",
            "installed_at": "O'rnatilgan sana",
            "is_public": "Ommaviy pasportda ko'rsatish",
        }
        help_texts = {
            "name": "Masalan: Oshxona rozetkasi yoki kirish chirog'i.",
            "identifier": "Chizma yoki qurilmadagi raqam bo'lsa, kiriting.",
        }

    def __init__(self, *args, **kwargs):
        project = kwargs.pop("project", None)
        super().__init__(*args, **kwargs)
        _style_fields(self)
        if project:
            self.fields["room"].queryset = Room.objects.filter(floor__project=project)
            self.fields["circuit"].queryset = Circuit.objects.filter(project=project)
        self.fields["room"].empty_label = "Xona tanlanmagan"
        self.fields["circuit"].empty_label = "Liniya tanlanmagan"


def _style_fields(form):
    for field in form.fields.values():
        if not isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs.setdefault("class", "form-control")