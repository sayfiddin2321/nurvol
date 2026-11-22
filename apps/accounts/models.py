from django.contrib.auth.models import AbstractUser
from django.db import models
from .managers import UserManager

class User(AbstractUser):
    objects = UserManager()

    class Role(models.TextChoices):
        ELECTRICIAN = "electrician", "Electrician"
        CLIENT = "client", "Client"
        ADMIN = "admin", "Admin"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    phone = models.CharField(max_length=20, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username

    @property
    def is_electrician(self):
        return self.role == self.Role.ELECTRICIAN

    @property
    def is_client(self):
        return self.role == self.Role.CLIENT

    @property
    def is_administrator(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def role_label(self):
        if self.is_administrator:
            return "Bosh elektrik"
        return "Elektrik" if self.is_electrician else "Mijoz"

    @property
    def can_use_electrician_tools(self):
        return self.is_electrician or self.is_administrator


class ContactInquiry(models.Model):
    class Plan(models.TextChoices):
        GENERAL = "general", "Umumiy murojaat"
        PRO = "pro", "Pro Usta"
        TEAM = "team", "Jamoaviy"

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=32)
    plan = models.CharField(
        max_length=16,
        choices=Plan.choices,
        default=Plan.GENERAL,
    )
    message = models.TextField(max_length=2000)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "murojaat"
        verbose_name_plural = "murojaatlar"

    def __str__(self):
        return f"{self.name} — {self.get_plan_display()}"


class PaymentSettings(models.Model):
    card_number = models.CharField(max_length=32, blank=True)
    cardholder_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    telegram_username = models.CharField(max_length=32, blank=True)
    public_phone = models.CharField(max_length=32, blank=True)
    public_telegram_username = models.CharField(max_length=32, blank=True)
    pro_monthly_price = models.CharField(max_length=32, default="79 000")
    team_monthly_price = models.CharField(max_length=32, default="199 000")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "to'lov rekvizitlari"
        verbose_name_plural = "to'lov rekvizitlari"

    def __str__(self):
        return "To'lov rekvizitlari"

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
