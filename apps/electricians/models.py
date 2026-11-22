from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class ElectricianProfile(models.Model):
    class AccessStatus(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "To'lov kutilmoqda"
        PAYMENT_SUBMITTED = "payment_submitted", "To'lov tekshirilmoqda"
        ACTIVE = "active", "Faol"
        REJECTED = "rejected", "Rad etilgan"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="electrician_profile",
    )
    access_status = models.CharField(
        max_length=24,
        choices=AccessStatus.choices,
        default=AccessStatus.ACTIVE,
    )
    payment_reference = models.CharField(max_length=120, blank=True)
    payment_receipt = models.ImageField(
        upload_to="electricians/payment-receipts/",
        blank=True,
        null=True,
    )
    avatar = models.ImageField(upload_to="electricians/avatars/", blank=True, null=True)
    bio = models.TextField(blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    specialization = models.CharField(max_length=150, blank=True)
    city = models.CharField(max_length=100, blank=True)
    telegram = models.CharField(max_length=100, blank=True)
    instagram = models.CharField(max_length=100, blank=True)
    company_name = models.CharField(max_length=150, blank=True)
    show_phone_public = models.BooleanField(default=False)
    show_telegram_public = models.BooleanField(default=False)
    show_instagram_public = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    @property
    def telegram_url(self):
        from .contacts import social_url
        return social_url(self.telegram, "telegram")

    @property
    def instagram_url(self):
        from .contacts import social_url
        return social_url(self.instagram, "instagram")

    @property
    def public_phone_url(self):
        from .contacts import phone_uri
        return phone_uri(self.user.phone) if self.show_phone_public else ""

    @property
    def public_telegram_url(self):
        return self.telegram_url if self.show_telegram_public else ""

    @property
    def public_instagram_url(self):
        return self.instagram_url if self.show_instagram_public else ""

    @property
    def average_rating(self):
        reviews = self.user.reviews_received.all()
        if not reviews.exists():
            return 5.0
        return round(sum(r.rating for r in reviews) / reviews.count(), 1)

    @property
    def review_count(self):
        return self.user.reviews_received.count()


class ElectricianClient(models.Model):
    electrician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="managed_clients",
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="electrician_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("electrician", "client"),
                name="unique_electrician_client_link",
            ),
        ]
        verbose_name = "elektrik mijozi"
        verbose_name_plural = "elektrik mijozlari"

    def __str__(self):
        return f"{self.electrician} → {self.client}"


class ElectricianReview(models.Model):
    electrician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_received",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_written",
    )
    rating = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review for {self.electrician} ({self.rating}/5)"


class ElectricianInquiry(models.Model):
    electrician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="service_inquiries",
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="service_requests",
    )
    phone = models.CharField(max_length=20)
    message = models.TextField(max_length=2000)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "mijoz so'rovi"
        verbose_name_plural = "mijoz so'rovlari"

    def __str__(self):
        return f"{self.client} → {self.electrician}"
