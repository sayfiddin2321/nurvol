from django import forms
from .models import ElectricianInquiry, ElectricianProfile, ElectricianReview
from .contacts import normalize_social, phone_uri
from apps.accounts.models import User


class ElectricianContactForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone")
        labels = {"first_name": "Ism", "last_name": "Familiya", "phone": "Telefon raqami"}
        widgets = {"phone": forms.TextInput(attrs={"type": "tel", "placeholder": "+998 90 123 45 67"})}

    def clean_phone(self):
        value = self.cleaned_data["phone"].strip()
        if value and not phone_uri(value):
            raise forms.ValidationError("Telefon raqamini to'g'ri kiriting.")
        return value

class ElectricianProfileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["experience_years"].required = False

    class Meta:
        model = ElectricianProfile
        fields = (
            "avatar", "bio", "experience_years", "specialization", "city",
            "company_name", "telegram", "instagram", "show_phone_public", "show_telegram_public", "show_instagram_public",
        )
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_telegram(self):
        return normalize_social(self.cleaned_data["telegram"], "telegram")

    def clean_experience_years(self):
        return self.cleaned_data["experience_years"] or 0

    def clean_instagram(self):
        return normalize_social(self.cleaned_data["instagram"], "instagram")

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and hasattr(avatar, "content_type"):
            from apps.documents.services import validate_image_file, build_image_thumbnail
            validate_image_file(avatar)
            return build_image_thumbnail(avatar)
        return avatar


class ElectricianReviewForm(forms.ModelForm):
    class Meta:
        model = ElectricianReview
        fields = ("rating", "comment")
        widgets = {
            "rating": forms.Select(
                choices=[(5, "5 ★★★★★ (A'lo)"), (4, "4 ★★★★☆ (Yaxshi)"), (3, "3 ★★★☆☆ (O'rtacha)"), (2, "2 ★★☆☆☆ (Qoniqarsiz)"), (1, "1 ★☆☆☆☆ (Yomon)")],
                attrs={"class": "form-control"}
            ),
            "comment": forms.Textarea(attrs={"rows": 3, "class": "form-control", "placeholder": "Bajarilgan ish sifati va usta haqida fikringizni yozing..."}),
        }


class ElectricianInquiryForm(forms.ModelForm):
    class Meta:
        model = ElectricianInquiry
        fields = ("phone", "message")
        labels = {
            "phone": "Telefon raqamingiz",
            "message": "Qanday xizmat kerak?",
        }
        widgets = {
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "type": "tel",
                "placeholder": "+998 90 123 45 67",
            }),
            "message": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Ish haqida qisqacha yozing",
            }),
        }

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if not phone_uri(phone):
            raise forms.ValidationError("Telefon raqamini to'g'ri kiriting.")
        return phone
