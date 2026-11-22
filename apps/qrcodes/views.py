import time
import uuid

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods, require_POST

from apps.projects.models import Project
from apps.projects.services import user_can_edit_project
from apps.electrical.models import ElectricalPanel
from .models import QRCode, QRScanLog
from .services import generate_qr_png_bytes, get_or_create_building_qr, get_or_create_panel_qr


@login_required
def qr_manage_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    building_qr = get_or_create_building_qr(project)
    panels = list(project.panels.prefetch_related("qr_codes"))
    panel_qrs = {
        qr.panel_id: qr
        for qr in QRCode.objects.filter(project=project, panel__isnull=False)
    }
    for panel in panels:
        panel.qr_code = panel_qrs.get(panel.pk)
    return render(request, "qrcodes/manage.html", {
        "project": project,
        "building_qr": building_qr,
        "panels": panels,
        "panel_qrs": panel_qrs,
        "scan_count": building_qr.scans.count(),
    })


@login_required
@require_POST
def building_qr_generate_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    get_or_create_building_qr(project)
    messages.success(request, "Bino QR kodi tayyor.")
    return redirect("qrcodes:manage", project_pk=project.pk)


@login_required
@require_POST
def qr_create_for_panel_view(request, panel_pk):
    panel = get_object_or_404(ElectricalPanel, pk=panel_pk)
    if not user_can_edit_project(request.user, panel.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    get_or_create_panel_qr(panel)
    messages.success(request, "Panel uchun QR yaratildi.")
    return redirect("qrcodes:manage", project_pk=panel.project_id)


@login_required
def qr_print_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    building_qr = get_or_create_building_qr(project)
    return render(request, "qrcodes/print.html", {
        "project": project,
        "qrs": [building_qr],
    })


@login_required
def qr_scans_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    scans = QRScanLog.objects.filter(
        qr_code__project=project
    ).select_related("qr_code", "qr_code__panel").order_by("-scanned_at")
    scan_counts = QRCode.objects.filter(project=project).annotate(
        scan_count=Count("scans")
    ).select_related("panel")
    return render(request, "qrcodes/scans.html", {
        "project": project,
        "scans": scans,
        "scan_counts": scan_counts,
    })


@login_required
def qr_download_view(request, token, download=True):
    qr = get_object_or_404(QRCode, token=token)
    if not user_can_edit_project(request.user, qr.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    png = generate_qr_png_bytes(qr.token, request=request)
    response = HttpResponse(png, content_type="image/png")
    disposition = "attachment" if download else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="nurvolt-{qr.token}.png"'
    return response


@login_required
@require_POST
def qr_toggle_active_view(request, token):
    qr = get_object_or_404(QRCode.objects.select_related("project"), token=token)
    if not user_can_edit_project(request.user, qr.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    qr.is_active = not qr.is_active
    qr.save(update_fields=["is_active"])
    messages.success(request, "QR kodi holati yangilandi.")
    return redirect("qrcodes:manage", project_pk=qr.project_id)


@login_required
@require_POST
def qr_regenerate_view(request, token):
    qr = get_object_or_404(QRCode.objects.select_related("project"), token=token)
    if not user_can_edit_project(request.user, qr.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    qr.token = uuid.uuid4()
    qr.is_active = True
    qr.save(update_fields=["token", "is_active"])
    messages.success(request, "Yangi QR kod yaratildi. Eski havola endi ishlamaydi.")
    return redirect("qrcodes:manage", project_pk=qr.project_id)


def public_qr_view(request, token):
    qr = get_object_or_404(
        QRCode.objects.select_related("project", "project__electrician", "project__electrician__electrician_profile", "panel"),
        token=token, is_active=True,
    )
    project = qr.project
    is_owner_or_admin = request.user.is_authenticated and (
        request.user == project.electrician or request.user.is_administrator
    )
    if not project.is_public and not is_owner_or_admin:
        return render(request, "public/private.html", {"qr": qr}, status=403)

    # Flood protection & deduplication: limit scan logs to once every 60s per session
    session_scans = request.session.get("scanned_qrs", {})
    str_token = str(qr.token)
    now_ts = int(time.time())
    last_scanned = session_scans.get(str_token, 0)

    if now_ts - last_scanned > 60:
        QRScanLog.objects.create(
            qr_code=qr,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            referer=request.META.get("HTTP_REFERER", "")[:255],
        )
        session_scans[str_token] = now_ts
        request.session["scanned_qrs"] = session_scans

    context = {
        "qr": qr,
        "project": project,
        "electrician_profile": getattr(project.electrician, "electrician_profile", None),
        "gallery_page": Paginator(project.images.order_by("uploaded_at", "pk"), 24).get_page(request.GET.get("photos")),
    }
    return render(request, "public/qr_project.html", context)
