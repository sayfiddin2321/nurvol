from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q, Avg, Count
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from django.db import transaction

from apps.accounts.models import User
from apps.accounts.forms import ElectricianClientCreateForm
from apps.projects.models import Project
from .models import (
    ElectricianClient,
    ElectricianInquiry,
    ElectricianProfile,
    ElectricianReview,
)
from .forms import (
    ElectricianContactForm,
    ElectricianInquiryForm,
    ElectricianProfileForm,
    ElectricianReviewForm,
)


def electrician_list_view(request):
    qs = ElectricianProfile.objects.select_related("user").annotate(
        avg_rating=Avg("user__reviews_received__rating"),
        total_reviews=Count("user__reviews_received"),
    ).filter(
        user__role=User.Role.ELECTRICIAN,
        access_status=ElectricianProfile.AccessStatus.ACTIVE,
    )

    search = request.GET.get("q", "").strip()
    city = request.GET.get("city", "").strip()
    verified_only = request.GET.get("verified") == "1"
    min_exp = request.GET.get("exp", "").strip()

    if search:
        qs = qs.filter(
            Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(user__username__icontains=search)
            | Q(specialization__icontains=search)
            | Q(city__icontains=search)
        )
    if city:
        qs = qs.filter(city__iexact=city)
    if verified_only:
        qs = qs.filter(is_verified=True)
    if min_exp.isdigit():
        qs = qs.filter(experience_years__gte=int(min_exp))

    qs = qs.order_by("-is_verified", "-experience_years", "-created_at")

    # Available cities for filter pills
    cities = ElectricianProfile.objects.filter(
        user__role=User.Role.ELECTRICIAN,
        access_status=ElectricianProfile.AccessStatus.ACTIVE,
    ).exclude(city="").values_list("city", flat=True).distinct()

    page_obj = Paginator(qs, 12).get_page(request.GET.get("page"))

    return render(request, "electricians/list.html", {
        "electricians": page_obj.object_list,
        "page_obj": page_obj,
        "search": search,
        "selected_city": city,
        "verified_only": verified_only,
        "min_exp": min_exp,
        "cities": cities,
        "total_count": page_obj.paginator.count,
    })


@login_required
def my_profile_view(request):
    if not request.user.can_use_electrician_tools:
        messages.error(request, "Faqat elektriklar profilga ega bo'lishi mumkin.")
        return redirect("dashboard")
    profile, _ = ElectricianProfile.objects.get_or_create(user=request.user)
    return render(request, "electricians/profile.html", {"profile": profile})


@login_required
def electrician_clients_view(request):
    if not request.user.can_use_electrician_tools:
        messages.error(request, "Mijozlar ro'yxati faqat elektriklar uchun.")
        return redirect("dashboard")
    clients = User.objects.filter(
        electrician_links__electrician=request.user,
        role=User.Role.CLIENT,
    ).annotate(
        project_count=Count(
            "client_projects",
            filter=Q(client_projects__electrician=request.user),
        ),
    ).order_by("first_name", "last_name", "username").distinct()
    return render(request, "electricians/clients.html", {"clients": clients})


@login_required
@require_http_methods(["GET", "POST"])
def create_client_account_view(request):
    if not request.user.can_use_electrician_tools:
        messages.error(request, "Mijoz akkauntini faqat elektrik yaratishi mumkin.")
        return redirect("dashboard")

    form = ElectricianClientCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            client = User.objects.create_user(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password1"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                phone=form.cleaned_data["phone"],
                role=User.Role.CLIENT,
            )
            ElectricianClient.objects.create(
                electrician=request.user,
                client=client,
            )
        response = render(request, "electricians/client_credentials.html", {
            "client": client,
            "password": form.cleaned_data["password1"],
        })
        response["Cache-Control"] = "no-store, private"
        return response
    return render(request, "electricians/create_client.html", {"form": form})


@login_required
def edit_profile_view(request):
    if not request.user.can_use_electrician_tools:
        return redirect("dashboard")
    profile, _ = ElectricianProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = ElectricianProfileForm(request.POST, request.FILES, instance=profile)
        contact_form = ElectricianContactForm(request.POST, instance=request.user)
        profile_valid = form.is_valid()
        contact_valid = contact_form.is_valid()
        if profile_valid and contact_valid:
            with transaction.atomic():
                form.save()
                contact_form.save()
            messages.success(request, "Profil saqlandi.")
            return redirect("electricians:my_profile")
    else:
        form = ElectricianProfileForm(instance=profile)
        contact_form = ElectricianContactForm(instance=request.user)
    return render(request, "electricians/edit_profile.html", {"form": form, "contact_form": contact_form, "profile": profile})


def _public_profile_context(profile, request_form=None):
    reviews = profile.user.reviews_received.select_related("author").order_by("-created_at")
    public_projects = Project.objects.filter(electrician=profile.user, is_public=True).order_by("-created_at")
    review_form = ElectricianReviewForm()

    return {
        "profile": profile,
        "reviews": reviews,
        "public_projects": public_projects,
        "review_form": review_form,
        "request_form": request_form,
        "avg_rating": profile.average_rating,
        "review_count": reviews.count(),
    }


def _get_active_electrician_profile(user_id):
    return get_object_or_404(
        ElectricianProfile.objects.select_related("user"),
        user_id=user_id,
        user__role=User.Role.ELECTRICIAN,
        access_status=ElectricianProfile.AccessStatus.ACTIVE,
    )


def public_profile_view(request, user_id):
    profile = _get_active_electrician_profile(user_id)
    request_form = None
    if request.user.is_authenticated and request.user.is_client:
        request_form = ElectricianInquiryForm(initial={"phone": request.user.phone})
    return render(
        request,
        "electricians/public_profile.html",
        _public_profile_context(profile, request_form),
    )


@login_required
@require_POST
def send_electrician_inquiry_view(request, user_id):
    if not request.user.is_client:
        messages.error(request, "Elektrikka so'rov yuborish uchun mijoz akkaunti kerak.")
        return redirect("electricians:public_profile", user_id=user_id)

    profile = _get_active_electrician_profile(user_id)
    form = ElectricianInquiryForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "electricians/public_profile.html",
            _public_profile_context(profile, form),
            status=400,
        )

    inquiry = form.save(commit=False)
    inquiry.client = request.user
    inquiry.electrician = profile.user
    with transaction.atomic():
        inquiry.save()
        ElectricianClient.objects.get_or_create(
            electrician=profile.user,
            client=request.user,
        )
    messages.success(request, "So'rovingiz elektrikga yuborildi.")
    return redirect("electricians:public_profile", user_id=user_id)


@login_required
def electrician_inquiries_view(request):
    if not request.user.can_use_electrician_tools:
        messages.error(request, "So'rovlar faqat elektrik akkauntida ko'rinadi.")
        return redirect("dashboard")
    inquiries = ElectricianInquiry.objects.filter(
        electrician=request.user,
    ).select_related("client")
    return render(request, "electricians/inquiries.html", {
        "inquiries": inquiries,
        "unread_count": inquiries.filter(is_read=False).count(),
    })


@login_required
@require_POST
def mark_inquiry_read_view(request, inquiry_id):
    if not request.user.can_use_electrician_tools:
        messages.error(request, "So'rovni faqat elektrik ko'rilgan deb belgilashi mumkin.")
        return redirect("dashboard")
    inquiry = get_object_or_404(
        ElectricianInquiry,
        pk=inquiry_id,
        electrician=request.user,
    )
    if not inquiry.is_read:
        inquiry.is_read = True
        inquiry.save(update_fields=["is_read"])
    return redirect("electricians:inquiries")


@login_required
@require_POST
def add_review_view(request, user_id):
    electrician_user = get_object_or_404(User, pk=user_id, role=User.Role.ELECTRICIAN)
    if request.user == electrician_user:
        messages.error(request, "O'zingizga sharh qoldira olmaysiz.")
        return redirect("electricians:public_profile", user_id=user_id)

    form = ElectricianReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.electrician = electrician_user
        review.author = request.user
        review.save()
        messages.success(request, "Sharhingiz muvaffaqiyatli saqlandi!")
    else:
        messages.error(request, "Sharh formasi to'liq to'ldirilmadi.")
    return redirect("electricians:public_profile", user_id=user_id)
