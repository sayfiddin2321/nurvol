import logging
from mimetypes import guess_type
from django.db import transaction

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Case, Count, IntegerField, When

from apps.electricians.models import ElectricianProfile
from .forms import (
    ContactInquiryForm,
    PaymentSettingsForm,
    PaymentSubmissionForm,
    ProfileEditForm,
    RegisterForm,
)
from .models import ContactInquiry, PaymentSettings, User
from .decorators import head_electrician_required


logger = logging.getLogger(__name__)


def _safe_next_url(request):
    next_url = request.POST.get("next") or request.GET.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return ""


def _is_electrician_manager(user):
    return user.is_authenticated and user.is_administrator


def _electrician_access_context(user, profile, payment_form):
    full_name = user.get_full_name() or user.username
    if profile.access_status == ElectricianProfile.AccessStatus.PAYMENT_SUBMITTED:
        telegram_message = f"Salom, {full_name}. To'lov chekini saytda yubordim."
    else:
        telegram_message = f"Salom, {full_name}. To'lov bo'yicha ma'lumot olmoqchiman."
    return {
        "profile": profile,
        "payment_settings": PaymentSettings.get_solo(),
        "payment_form": payment_form,
        "telegram_message": telegram_message,
    }


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next_url(request) or "dashboard")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Ro'yxatdan muvaffaqiyatli o'tdingiz!")
            return redirect(_safe_next_url(request) or "dashboard")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {
        "form": form,
        "next_url": _safe_next_url(request),
    })


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next_url(request) or "dashboard")
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect(_safe_next_url(request) or "dashboard")
        messages.error(request, "Login yoki parol xato.")
    else:
        form = AuthenticationForm()
    return render(request, "accounts/login.html", {
        "form": form,
        "next_url": _safe_next_url(request),
    })


@require_POST
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


@require_POST
def contact_inquiry_view(request):
    form = ContactInquiryForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(
            request,
            "Murojaatingiz adminga yuborildi. Tez orada siz bilan bog'lanamiz.",
        )
        return redirect(f"{reverse('home')}#biz-bilan-aloqa")
    return render(request, "landing.html", {
        "contact_form": form,
        "public_settings": PaymentSettings.get_solo(),
        "showcase_electrician": None,
        "showcase_projects": [],
        "showcase_project_count": 0,
        "showcase_client_count": 0,
        "showcase_videos": [],
    }, status=400)


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit_view(request):
    if request.method == "POST":
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil saqlandi.")
            return redirect("dashboard")
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def settings_view(request):
    active_tab = request.GET.get("tab", "profile")
    if active_tab not in {"profile", "security", "notifications", "appearance"}:
        active_tab = "profile"

    if request.method == "POST":
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil saqlandi.")
            return redirect("accounts:settings")
    else:
        form = ProfileEditForm(instance=request.user)

    return render(request, "accounts/settings.html", {
        "form": form,
        "active_tab": active_tab,
    })


@login_required
@require_http_methods(["GET", "POST"])
def change_password_view(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Parol muvaffaqiyatli o'zgartirildi.")
            return redirect("accounts:settings")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "accounts/password_change.html", {"form": form})


@login_required
def electrician_access_view(request):
    if not request.user.is_electrician or request.user.is_administrator:
        return redirect("dashboard")
    profile = get_object_or_404(ElectricianProfile, user=request.user)
    if profile.access_status == ElectricianProfile.AccessStatus.ACTIVE:
        return redirect("dashboard")
    form = PaymentSubmissionForm(initial={
            "payment_reference": profile.payment_reference,
        })
    return render(
        request,
        "accounts/electrician_access.html",
        _electrician_access_context(request.user, profile, form),
    )


@login_required
@require_POST
def submit_payment_view(request):
    if not request.user.is_electrician or request.user.is_administrator:
        return redirect("dashboard")
    profile = get_object_or_404(ElectricianProfile, user=request.user)
    if profile.access_status == ElectricianProfile.AccessStatus.ACTIVE:
        return redirect("dashboard")
    if profile.access_status not in {
        ElectricianProfile.AccessStatus.PENDING_PAYMENT,
        ElectricianProfile.AccessStatus.REJECTED,
    }:
        messages.error(request, "To'lov so'rovingiz allaqachon yuborilgan.")
        return redirect("accounts:electrician_access")
    form = PaymentSubmissionForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(
            request,
            "accounts/electrician_access.html",
            _electrician_access_context(request.user, profile, form),
            status=400,
        )
    old_receipt = profile.payment_receipt
    profile.access_status = ElectricianProfile.AccessStatus.PAYMENT_SUBMITTED
    profile.payment_reference = form.cleaned_data["payment_reference"]
    profile.payment_receipt = form.cleaned_data["receipt"]
    try:
        profile.save(update_fields=[
            "access_status",
            "payment_reference",
            "payment_receipt",
            "updated_at",
        ])
    except (OSError, ValidationError):
        logger.exception("Unable to save payment receipt for electrician %s", profile.pk)
        profile.refresh_from_db()
        form.add_error("receipt", "Chek rasmi saqlanmadi. Boshqa rasm tanlab qayta urinib ko'ring.")
        return render(
            request,
            "accounts/electrician_access.html",
            _electrician_access_context(request.user, profile, form),
        )
    if old_receipt and old_receipt.name != profile.payment_receipt.name:
        try:
            old_receipt.delete(save=False)
        except OSError:
            logger.exception("Unable to remove replaced payment receipt for electrician %s", profile.pk)
    messages.success(request, "To'lov ma'lumoti adminga yuborildi.")
    return redirect("accounts:electrician_access")


@head_electrician_required
def manage_electricians_view(request):
    profiles = ElectricianProfile.objects.select_related("user").filter(
        user__role=User.Role.ELECTRICIAN
    ).annotate(project_count=Count("user__projects"))
    counts = {
        "total": profiles.count(),
        "pending_payment": profiles.filter(
            access_status=ElectricianProfile.AccessStatus.PENDING_PAYMENT
        ).count(),
        "payment_submitted": profiles.filter(
            access_status=ElectricianProfile.AccessStatus.PAYMENT_SUBMITTED
        ).count(),
        "active": profiles.filter(
            access_status=ElectricianProfile.AccessStatus.ACTIVE
        ).count(),
        "suspended": profiles.filter(user__is_active=False).count(),
    }
    selected_status = request.GET.get("status", "")
    if selected_status == "suspended":
        profiles = profiles.filter(user__is_active=False)
    elif selected_status in ElectricianProfile.AccessStatus.values:
        profiles = profiles.filter(access_status=selected_status)
    else:
        selected_status = ""
    profiles = profiles.order_by(Case(
        When(access_status=ElectricianProfile.AccessStatus.PAYMENT_SUBMITTED, then=0),
        When(access_status=ElectricianProfile.AccessStatus.PENDING_PAYMENT, then=1),
        When(access_status=ElectricianProfile.AccessStatus.REJECTED, then=2),
        default=3,
        output_field=IntegerField(),
    ), "-created_at")
    return render(request, "accounts/manage_electricians.html", {
        "profiles": profiles,
        "counts": counts,
        "selected_status": selected_status,
        "contact_inquiries": ContactInquiry.objects.order_by("-created_at")[:20],
    })


@head_electrician_required
@require_http_methods(["GET", "POST"])
def payment_settings_view(request):
    settings = PaymentSettings.get_solo()
    form = PaymentSettingsForm(request.POST or None, instance=settings)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "To'lov rekvizitlari saqlandi.")
        return redirect("accounts:payment_settings")
    return render(request, "accounts/payment_settings.html", {"form": form})


@login_required
@require_http_methods(["GET"])
def payment_receipt_view(request, user_id):
    profile = get_object_or_404(
        ElectricianProfile.objects.select_related("user"),
        user_id=user_id,
        user__role=User.Role.ELECTRICIAN,
    )
    if request.user.pk != profile.user_id and not _is_electrician_manager(request.user):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if not profile.payment_receipt:
        raise Http404("To'lov cheki topilmadi.")
    try:
        receipt_file = profile.payment_receipt.open("rb")
    except OSError:
        logger.exception("Unable to open payment receipt for electrician %s", profile.pk)
        raise Http404("To'lov cheki topilmadi.")
    response = FileResponse(
        receipt_file,
        content_type=guess_type(profile.payment_receipt.name)[0] or "application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@head_electrician_required
@require_POST
def mark_contact_inquiry_read_view(request, inquiry_id):
    inquiry = get_object_or_404(ContactInquiry, pk=inquiry_id)
    inquiry.is_read = True
    inquiry.save(update_fields=["is_read"])
    messages.success(request, "Murojaat ko'rilgan deb belgilandi.")
    return redirect("accounts:manage_electricians")


@head_electrician_required
@require_POST
def set_electrician_account_active_view(request, profile_id):
    profile = get_object_or_404(
        ElectricianProfile.objects.select_related("user"),
        pk=profile_id,
        user__role=User.Role.ELECTRICIAN,
    )
    action = request.POST.get("action")
    user = profile.user

    if user.is_administrator or user.pk == request.user.pk:
        messages.error(
            request,
            "O‘z akkaunti, admin yoki bosh elektrik akkaunti o‘chirilishi yoki to‘xtatilishi mumkin emas.",
        )
        return redirect("accounts:manage_electricians")

    if action == "delete":
        name = user.get_full_name() or user.username
        with transaction.atomic():
            user.projects.all().delete()
            user.delete()
        messages.success(request, f"{name} akkaunti va uning barcha ishlarini o'chirildi.")
        return redirect("accounts:manage_electricians")

    if action == "suspend":
        user.is_active = False
        user.save(update_fields=["is_active"])
        messages.success(
            request,
            f"{user.get_full_name() or user.username} akkaunti vaqtincha to‘xtatildi.",
        )
    elif action == "activate":
        user.is_active = True
        user.save(update_fields=["is_active"])
        if profile.access_status != ElectricianProfile.AccessStatus.ACTIVE:
            profile.access_status = ElectricianProfile.AccessStatus.ACTIVE
            profile.save(update_fields=["access_status", "updated_at"])
        messages.success(
            request,
            f"{user.get_full_name() or user.username} akkaunti qayta faollashtirildi.",
        )
    else:
        messages.error(request, "Noma'lum amal.")
    return redirect("accounts:manage_electricians")


@head_electrician_required
@require_POST
def update_electrician_access_view(request, profile_id):
    profile = get_object_or_404(
        ElectricianProfile.objects.select_related("user"),
        pk=profile_id,
        user__role=User.Role.ELECTRICIAN,
    )
    action = request.POST.get("action")
    if profile.access_status != ElectricianProfile.AccessStatus.PAYMENT_SUBMITTED:
        messages.error(request, "Faqat to'lov tekshirilayotgan elektrikning holatini o'zgartirish mumkin.")
    elif action == "approve":
        profile.access_status = ElectricianProfile.AccessStatus.ACTIVE
        profile.save(update_fields=["access_status", "updated_at"])
        messages.success(request, f"{profile.user.get_full_name() or profile.user.username} faollashtirildi.")
    elif action == "reject":
        profile.access_status = ElectricianProfile.AccessStatus.REJECTED
        profile.save(update_fields=["access_status", "updated_at"])
        messages.success(request, "To'lov so'rovi rad etildi.")
    else:
        messages.error(request, "Noma'lum amal.")
    return redirect("accounts:manage_electricians")
