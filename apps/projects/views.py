import base64
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.db.models import Count, Q, Prefetch
from django.db.models.functions import TruncDate
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .models import Project, ProjectShowcaseSettings, ShowcaseVideo, Floor, Room
from .forms import (
    ProjectCreateForm,
    ProjectForm,
    ProjectShowcaseSettingsForm,
    FloorForm,
    RoomForm,
)
from .services import create_revision, user_can_access_project, user_can_edit_project
from apps.accounts.models import User
from apps.accounts.models import PaymentSettings
from apps.accounts.decorators import head_electrician_required
from apps.documents.models import ProjectImage
from apps.electricians.models import ElectricianProfile
from apps.qrcodes.models import QRScanLog
from apps.qrcodes.services import build_qr_url, get_or_create_building_qr, generate_qr_png_bytes


def home_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    settings = ProjectShowcaseSettings.objects.filter(pk=1).select_related(
        "featured_electrician"
    ).first()
    featured_electrician = settings.featured_electrician if settings else None
    showcase_projects = Project.objects.none()
    showcase_project_count = 0
    showcase_client_count = 0
    showcase_videos = ShowcaseVideo.objects.filter(is_active=True).order_by("order", "-created_at")

    if featured_electrician and featured_electrician.is_active and ElectricianProfile.objects.filter(
        user=featured_electrician,
        access_status=ElectricianProfile.AccessStatus.ACTIVE,
    ).exists():
        public_projects = Project.objects.filter(
            electrician=featured_electrician,
            is_public=True,
            status=Project.Status.COMPLETED,
        )
        showcase_project_count = public_projects.count()
        showcase_client_count = public_projects.filter(
            client__isnull=False
        ).values("client_id").distinct().count()
        showcase_projects = public_projects.prefetch_related(
            Prefetch(
                "images",
                queryset=ProjectImage.objects.order_by("uploaded_at"),
                to_attr="public_images",
            )
        ).order_by("-completion_date", "-updated_at")[:6]
    else:
        featured_electrician = None

    return render(request, "landing.html", {
        "showcase_electrician": featured_electrician,
        "showcase_projects": showcase_projects,
        "showcase_project_count": showcase_project_count,
        "showcase_client_count": showcase_client_count,
        "showcase_videos": showcase_videos,
        "public_settings": PaymentSettings.get_solo(),
    })


@head_electrician_required
@require_http_methods(["GET", "POST"])
def project_showcase_settings_view(request):
    settings = ProjectShowcaseSettings.get_solo()
    form = ProjectShowcaseSettingsForm(request.POST or None, instance=settings)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Bosh sahifa uchun bosh elektrik saqlandi.")
        return redirect("projects:showcase_settings")
    return render(request, "projects/showcase_settings.html", {"form": form})


@login_required
def dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")

    if request.user.is_administrator:
        projects = Project.objects.all()
    elif request.user.is_electrician:
        projects = Project.objects.filter(electrician=request.user)
    else:
        projects = Project.objects.filter(client=request.user)

    stats = {
        "total": projects.count(),
        "completed": projects.filter(status=Project.Status.COMPLETED).count(),
        "in_progress": projects.filter(status=Project.Status.IN_PROGRESS).count(),
        "draft": projects.filter(status=Project.Status.DRAFT).count(),
    }
    recent = projects.order_by("-created_at")[:5]

    today = timezone.localdate()
    first_day = today - timedelta(days=6)
    daily_scans = QRScanLog.objects.filter(
        qr_code__project__in=projects,
        scanned_at__date__gte=first_day,
        scanned_at__date__lte=today,
    ).annotate(day=TruncDate("scanned_at")).values("day").annotate(
        total=Count("pk")
    )
    scans_by_day = {item["day"]: item["total"] for item in daily_scans}
    scan_activity = [
        {"label": (first_day + timedelta(days=offset)).strftime("%a"),
         "date": first_day + timedelta(days=offset),
         "count": scans_by_day.get(first_day + timedelta(days=offset), 0)}
        for offset in range(7)
    ]
    max_scans = max((item["count"] for item in scan_activity), default=0)
    for item in scan_activity:
        item["height"] = max(8, round(item["count"] / max_scans * 100)) if max_scans else 8

    return render(request, "dashboard/index.html", {
        "stats": stats,
        "recent": recent,
        "scan_activity": scan_activity,
        "scan_total": sum(item["count"] for item in scan_activity),
    })


@login_required
def project_list_view(request):
    if request.user.is_administrator:
        qs = Project.objects.all()
    elif request.user.is_electrician:
        qs = Project.objects.filter(electrician=request.user)
    else:
        qs = Project.objects.filter(client=request.user)

    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    project_type = request.GET.get("type", "")
    valid_statuses = {value for value, _ in Project.Status.choices}
    valid_types = {value for value, _ in Project.ProjectType.choices}

    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(address__icontains=search))
    if status in valid_statuses:
        qs = qs.filter(status=status)
    if project_type in valid_types:
        qs = qs.filter(project_type=project_type)

    page_obj = Paginator(qs.order_by("-created_at"), 12).get_page(request.GET.get("page"))
    query = request.GET.copy()
    page_urls = []
    for page_number in page_obj.paginator.page_range:
        query["page"] = page_number
        page_urls.append({"number": page_number, "url": f"?{query.urlencode()}"})

    return render(request, "projects/list.html", {
        "projects": page_obj.object_list,
        "page_obj": page_obj,
        "page_urls": page_urls,
        "sidebar_project": page_obj.object_list.first(),
        "search": search,
        "selected_status": status,
        "selected_type": project_type,
        "statuses": Project.Status.choices,
        "project_types": Project.ProjectType.choices,
        "project_count": page_obj.paginator.count,
    })


@login_required
@require_http_methods(["GET", "POST"])
def project_create_view(request):
    if not request.user.can_use_electrician_tools:
        messages.error(
            request,
            "Loyiha yaratish faqat elektrik akkauntida mumkin. "
            "Mijoz sifatida sizga biriktirilgan loyihalarni ko'rishingiz mumkin.",
        )
        return redirect("dashboard")
    if request.method == "POST":
        form = ProjectCreateForm(request.POST, electrician=request.user)
        if form.is_valid():
            project = form.save(commit=False)
            project.electrician = request.user
            project.project_type = Project.ProjectType.OTHER
            project.is_public = True
            project.save()
            create_revision(project, request.user, "Loyiha yaratildi")
            messages.success(request, "Loyiha yaratildi.")
            return redirect("projects:detail", pk=project.pk)
    else:
        form = ProjectCreateForm(electrician=request.user)
    return render(request, "projects/create.html", {"form": form})


@login_required
def project_setup_view(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not user_can_access_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    return redirect("projects:detail", pk=project.pk)


@login_required
def project_detail_view(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not user_can_access_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    can_edit = user_can_edit_project(request.user, project)
    images = project.images.order_by("uploaded_at", "pk")
    building_qr = get_or_create_building_qr(project) if can_edit else None
    context = {
        "project": project,
        "can_edit": can_edit,
        "building_qr": building_qr,
        "share_url": build_qr_url(building_qr.token, request) if building_qr else "",
        "images": images,
        "gallery_page": Paginator(images, 24).get_page(request.GET.get("photos")),
    }
    return render(request, "projects/detail.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def project_edit_view(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        form = ProjectForm(
            request.POST,
            instance=project,
            electrician=project.electrician,
        )
        if form.is_valid():
            form.save()
            create_revision(project, request.user, "Loyiha yangilandi")
            messages.success(request, "Loyiha yangilandi.")
            return redirect("projects:detail", pk=pk)
    else:
        form = ProjectForm(instance=project, electrician=project.electrician)
    return render(request, "projects/edit.html", {"form": form, "project": project})


@login_required
@require_POST
def project_share_view(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if not project.is_public:
        project.is_public = True
        project.save(update_fields=["is_public", "updated_at"])
    qr = get_or_create_building_qr(project)
    if not qr.is_active:
        qr.is_active = True
        qr.save(update_fields=["is_active"])
    return redirect(f"{reverse('projects:detail', args=[pk])}#qr")


@login_required
@require_POST
def project_toggle_public_view(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    project.is_public = not project.is_public
    project.save(update_fields=["is_public", "updated_at"])
    create_revision(
        project,
        request.user,
        "Ommaviy ko'rinish o'zgartirildi",
        "Loyiha ommaga ochildi." if project.is_public else "Loyiha yopiq qilindi.",
    )
    messages.success(
        request,
        "Loyiha ommaga ochildi." if project.is_public else "Loyiha yopiq qilindi.",
    )
    return redirect("projects:detail", pk=pk)


@login_required
def project_delete_view(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        project.delete()
        messages.success(request, "Loyiha o'chirildi.")
        return redirect("projects:list")
    return render(request, "projects/confirm_delete.html", {"project": project})


# ---------- FLOORS / ROOMS ----------

@login_required
@require_http_methods(["GET", "POST"])
def floor_create_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        form = FloorForm(request.POST)
        if form.is_valid():
            floor = form.save(commit=False)
            floor.project = project
            floor.save()
            create_revision(project, request.user, "Qavat qo'shildi", floor.name)
            messages.success(request, "Qavat qo'shildi.")
            return redirect(f"{reverse('projects:detail', args=[project_pk])}#tab-technical")
    else:
        form = FloorForm()
    return render(request, "projects/floor_form.html", {"form": form, "project": project})


@login_required
@require_http_methods(["GET", "POST"])
def floor_edit_view(request, pk):
    floor = get_object_or_404(Floor.objects.select_related("project"), pk=pk)
    if not user_can_edit_project(request.user, floor.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        form = FloorForm(request.POST, instance=floor)
        if form.is_valid():
            form.save()
            create_revision(floor.project, request.user, "Qavat yangilandi", floor.name)
            messages.success(request, "Qavat yangilandi.")
            return redirect("projects:detail", pk=floor.project_id)
    else:
        form = FloorForm(instance=floor)
    return render(request, "projects/floor_form.html", {
        "form": form,
        "project": floor.project,
        "floor": floor,
    })


@login_required
@require_POST
def floor_delete_view(request, pk):
    floor = get_object_or_404(Floor.objects.select_related("project"), pk=pk)
    if not user_can_edit_project(request.user, floor.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    project_id = floor.project_id
    name = floor.name
    project = floor.project
    floor.delete()
    create_revision(project, request.user, "Qavat o'chirildi", name)
    messages.success(request, "Qavat o'chirildi.")
    return redirect("projects:detail", pk=project_id)


@login_required
@require_http_methods(["GET", "POST"])
def room_create_view(request, floor_pk):
    floor = get_object_or_404(Floor, pk=floor_pk)
    if not user_can_edit_project(request.user, floor.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.floor = floor
            room.save()
            create_revision(floor.project, request.user, "Xona qo'shildi", room.name)
            messages.success(request, "Xona qo'shildi.")
            return redirect(f"{reverse('projects:detail', args=[floor.project_id])}#tab-technical")
    else:
        form = RoomForm()
    return render(request, "projects/room_form.html", {"form": form, "floor": floor})


@login_required
@require_http_methods(["GET", "POST"])
def room_edit_view(request, pk):
    room = get_object_or_404(Room.objects.select_related("floor__project"), pk=pk)
    project = room.floor.project
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            create_revision(project, request.user, "Xona yangilandi", room.name)
            messages.success(request, "Xona yangilandi.")
            return redirect("projects:detail", pk=project.pk)
    else:
        form = RoomForm(instance=room)
    return render(request, "projects/room_form.html", {
        "form": form,
        "floor": room.floor,
        "room": room,
    })


@login_required
@require_POST
def room_delete_view(request, pk):
    room = get_object_or_404(Room.objects.select_related("floor__project"), pk=pk)
    project = room.floor.project
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    project_id = project.pk
    name = room.name
    room.delete()
    create_revision(project, request.user, "Xona o'chirildi", name)
    messages.success(request, "Xona o'chirildi.")
    return redirect("projects:detail", pk=project_id)


@login_required
def project_passport_view(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not user_can_access_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")

    building_qr = get_or_create_building_qr(project)
    qr_png = generate_qr_png_bytes(building_qr.token, request=request)
    qr_base64 = base64.b64encode(qr_png).decode("utf-8")

    panels = project.panels.all().prefetch_related("circuits")
    circuits = project.circuits.select_related("panel").order_by("panel__name", "circuit_code")
    cables = project.cables.select_related("circuit", "room")
    devices = project.devices.select_related("room", "circuit")
    maintenance_records = project.maintenance_records.select_related("performed_by").order_by("-maintenance_date")
    images = project.images.all()
    documents = project.documents.all()
    if not user_can_edit_project(request.user, project):
        panels = panels.filter(is_public=True)
        circuits = circuits.filter(is_public=True, panel__is_public=True)
        cables = cables.filter(is_public=True)
        devices = devices.filter(is_public=True)
        maintenance_records = maintenance_records.filter(is_public=True)
        documents = documents.filter(is_public=True)

    context = {
        "project": project,
        "building_qr": building_qr,
        "qr_base64": qr_base64,
        "images": images,
        "documents": documents,
        "panels": panels,
        "circuits": circuits,
        "cables": cables,
        "devices": devices,
        "maintenance_records": maintenance_records,
        "electrician_profile": getattr(project.electrician, "electrician_profile", None),
        "now": timezone.now(),
    }
    return render(request, "projects/passport_pdf.html", context)
