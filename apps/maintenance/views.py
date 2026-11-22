from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST

from apps.projects.models import Project
from apps.projects.services import create_revision, user_can_edit_project
from .models import MaintenanceRecord
from .forms import MaintenanceRecordForm


@login_required
@require_http_methods(["GET", "POST"])
def record_create_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        form = MaintenanceRecordForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.project = project
            obj.performed_by = request.user
            obj.save()
            create_revision(project, request.user, "Xizmat yozuvi qo'shildi", obj.title)
            messages.success(request, "Yozuv qo'shildi.")
            return redirect("projects:detail", pk=project_pk)
    else:
        form = MaintenanceRecordForm()
    return render(request, "maintenance/record_form.html", {"form": form, "project": project})


@login_required
@require_http_methods(["GET", "POST"])
def record_edit_view(request, pk):
    record = get_object_or_404(MaintenanceRecord.objects.select_related("project"), pk=pk)
    if not user_can_edit_project(request.user, record.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        form = MaintenanceRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            create_revision(record.project, request.user, "Xizmat yozuvi yangilandi", record.title)
            messages.success(request, "Yozuv yangilandi.")
            return redirect("projects:detail", pk=record.project_id)
    else:
        form = MaintenanceRecordForm(instance=record)
    return render(request, "maintenance/record_form.html", {
        "form": form,
        "project": record.project,
        "record": record,
    })


@login_required
@require_POST
def record_delete_view(request, pk):
    record = get_object_or_404(MaintenanceRecord.objects.select_related("project"), pk=pk)
    if not user_can_edit_project(request.user, record.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    project = record.project
    title = record.title
    record.delete()
    create_revision(project, request.user, "Xizmat yozuvi o'chirildi", title)
    messages.success(request, "Xizmat yozuvi o'chirildi.")
    return redirect("projects:detail", pk=project.pk)