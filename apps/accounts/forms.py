import re

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.documents.services import validate_image_file
from apps.electricians.models import ElectricianProfile
from .models import ContactInquiry, PaymentSettings, User


TERMS_VERSION = "1"


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=100, required=True, label="Ism")
    last_name = forms.CharField(max_length=100, required=True, label="Familiya")
    phone = forms.CharField(max_length=20, required=False, label="Telefon")
    city = forms.CharField(max_length=100, required=False, label="Shahar")
    experience_years = forms.IntegerField(min_value=0, required=False, label="Tajriba (yil)")
    accepted_terms = forms.BooleanField(required=True, label="Foydalanish shartlariga roziman")
    role = forms.ChoiceField(
        choices=[(User.Role.ELECTRICIAN, "Elektrik"), (User.Role.CLIENT, "Mijoz")],
        label="Rol",
    )

    class Meta:
        model = User
        fields = (
            "username", "first_name", "last_name", "email", "phone", "role",
            "password1", "password2",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.phone = self.cleaned_data.get("phone", "")
        user.role = self.cleaned_data["role"]
        user.terms_accepted_at = timezone.now()
        user.terms_version = TERMS_VERSION
        if commit:
            user.save()
            if user.is_electrician:
                profile = user.electrician_profile
                profile.city = self.cleaned_data.get("city", "")
                profile.experience_years = self.cleaned_data.get("experience_years") or 0
                profile.access_status = ElectricianProfile.AccessStatus.PENDING_PAYMENT
                profile.save(update_fields=[
                    "city",
                    "experience_years",
                    "access_status",
                    "updated_at",
                ])
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Foydalanuvchi nomi")
    password = forms.CharField(label="Parol", widget=forms.PasswordInput)


class ElectricianClientCreateForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label="Mijoz login",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    first_name = forms.CharField(max_length=100, label="Ism")
    last_name = forms.CharField(max_length=100, label="Familiya")
    phone = forms.CharField(max_length=20, required=False, label="Telefon")
    password1 = forms.CharField(
        min_length=8,
        label="Vaqtinchalik parol",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Kamida 8 belgi. Login va parolni mijozga xavfsiz yo'l bilan bering.",
    )
    password2 = forms.CharField(
        min_length=8,
        label="Parolni takrorlang",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_username(self):
        username = User.normalize_username(self.cleaned_data["username"].strip())
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Bu login band. Boshqa login tanlang.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Parollar bir-biriga mos kelmadi.")
        return cleaned_data


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone")


class ContactInquiryForm(forms.ModelForm):
    class Meta:
        model = ContactInquiry
        fields = ("name", "phone", "plan", "message")


class PaymentSettingsForm(forms.ModelForm):
    class Meta:
        model = PaymentSettings
        fields = (
            "card_number",
            "cardholder_name",
            "phone",
            "telegram_username",
            "public_phone",
            "public_telegram_username",
            "pro_monthly_price",
            "team_monthly_price",
        )
        labels = {
            "card_number": "Karta raqami",
            "cardholder_name": "Karta egasining ismi",
            "phone": "Admin telefoni",
            "telegram_username": "Telegram username",
            "public_phone": "Bosh sahifadagi telefon raqami",
            "public_telegram_username": "Bosh sahifadagi Telegram",
            "pro_monthly_price": "Pro Usta oylik narxi",
            "team_monthly_price": "Jamoaviy tarif oylik narxi",
        }
        widgets = {
            "card_number": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "8600 0000 0000 0000",
            }),
            "cardholder_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ism Familiya",
            }),
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "+998 90 123 45 67",
            }),
            "telegram_username": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "@username",
            }),
            "public_phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "+998 90 123 45 67",
            }),
            "public_telegram_username": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "@username",
            }),
            "pro_monthly_price": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "79 000",
            }),
            "team_monthly_price": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "199 000",
            }),
        }

    def clean_card_number(self):
        return self.cleaned_data["card_number"].strip()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in (
            "public_phone",
            "public_telegram_username",
            "pro_monthly_price",
            "team_monthly_price",
        ):
            self.fields[field_name].required = False

    def clean_pro_monthly_price(self):
        value = self.cleaned_data["pro_monthly_price"].strip()
        return value or "79 000"

    def clean_team_monthly_price(self):
        value = self.cleaned_data["team_monthly_price"].strip()
        return value or "199 000"

    def clean_telegram_username(self):
        username = self.cleaned_data["telegram_username"].strip().lstrip("@")
        if username and not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
            raise ValidationError("Telegram username 5–32 ta harf, raqam yoki pastki chiziqdan iborat bo'lishi kerak.")
        return username

    def clean_public_telegram_username(self):
        username = self.cleaned_data["public_telegram_username"].strip().lstrip("@")
        if username and not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
            raise ValidationError("Telegram username 5–32 ta harf, raqam yoki pastki chiziqdan iborat bo'lishi kerak.")
        return username


class PaymentSubmissionForm(forms.Form):
    payment_reference = forms.CharField(
        max_length=120,
        required=False,
        label="To'lov izohi yoki tranzaksiya raqami",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Masalan, tranzaksiya raqami"}),
    )
    receipt = forms.ImageField(
        required=True,
        label="To'lov cheki rasmi",
        help_text="JPG, PNG yoki WebP; 20 MB gacha.",
        widget=forms.ClearableFileInput(attrs={
            "class": "form-control",
            "accept": "image/jpeg,image/png,image/webp",
        }),
    )

    def clean_receipt(self):
        receipt = self.cleaned_data["receipt"]
        validate_image_file(receipt)
        return receipt