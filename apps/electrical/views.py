from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models.deletion import ProtectedError, RestrictedError

from apps.projects.models import Project
from apps.projects.services import create_revision, user_can_edit_project
from .models import ElectricalPanel, Circuit, Cable, ElectricalDevice
from .forms import ElectricalPanelForm, CircuitForm, CableForm, ElectricalDeviceForm


def _check_edit(request, project):
    if not user_can_edit_project(request.user, project):
        return False
    return True


@login_required
@require_http_methods(["GET", "POST"])
def panel_create_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not _check_edit(request, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        form = ElectricalPanelForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.project = project
            obj.save()
            create_revision(project, request.user, "Elektr shit qo'shildi", obj.name)
            messages.success(request, "Elektr shit qo'shildi.")
            return redirect(f"{reverse('projects:detail', args=[project_pk])}#tab-technical")
    else:
        form = ElectricalPanelForm()
    return render(request, "electrical/panel_form.html", {"form": form, "project": project})


@login_required
@require_http_methods(["GET", "POST"])
def circuit_create_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not _check_edit(request, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        form = CircuitForm(request.POST, project=project)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.project = project
            obj.save()
            create_revision(project, request.user, "Liniya qo'shildi", obj.name)
            messages.success(request, "Liniya qo'shildi.")
            return redirect(f"{reverse('projects:detail', args=[project_pk])}#tab-technical")
    else:
        initial = {}
        panel_id = request.GET.get("panel")
        if panel_id:
            initial["panel"] = ElectricalPanel.objects.filter(
                project=project,
                pk=panel_id,
            ).first()
        form = CircuitForm(project=project, initial=initial)
    return render(request, "electrical/circuit_form.html", {"form": form, "project": project})


@login_required
@require_http_methods(["GET", "POST"])
def cable_create_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not _check_edit(request, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        form = CableForm(request.POST, project=project)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.project = project
            obj.save()
            create_revision(project, request.user, "Kabel qo'shildi", obj.name)
            messages.success(request, "Kabel qo'shildi.")
            return redirect(f"{reverse('projects:detail', args=[project_pk])}#tab-technical")
    else:
        form = CableForm(project=project)
    return render(request, "electrical/cable_form.html", {"form": form, "project": project})


@login_required
@require_http_methods(["GET", "POST"])
def device_create_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not _check_edit(request, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        form = ElectricalDeviceForm(request.POST, project=project)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.project = project
            obj.save()
            create_revision(project, request.user, "Qurilma qo'shildi", obj.name)
            messages.success(request, "Qurilma qo'shildi.")
            return redirect(f"{reverse('projects:detail', args=[project_pk])}#tab-technical")
    else:
        form = ElectricalDeviceForm(project=project)
    return render(request, "electrical/device_form.html", {"form": form, "project": project})


def _edit_resource(request, obj, form_class, template_name, success_message, revision_title):
    project = obj.project
    form_kwargs = {"instance": obj}
    if form_class is not ElectricalPanelForm:
        form_kwargs["project"] = project
    if request.method == "POST":
        form = form_class(request.POST, **form_kwargs)
        if form.is_valid():
            saved_obj = form.save()
            create_revision(project, request.user, revision_title, saved_obj.name)
            messages.success(request, success_message)
            return redirect("projects:detail", pk=project.pk)
    else:
        form = form_class(**form_kwargs)
    return render(request, template_name, {
        "form": form,
        "project": project,
        "object": obj,
    })


@login_required
@require_http_methods(["GET", "POST"])
def panel_edit_view(request, pk):
    obj = get_object_or_404(ElectricalPanel.objects.select_related("project"), pk=pk)
    if not _check_edit(request, obj.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    return _edit_resource(
        request, obj, ElectricalPanelForm, "electrical/panel_form.html",
        "Elektr shit yangilandi.", "Elektr shit yangilandi",
    )


@login_required
@require_http_methods(["GET", "POST"])
def circuit_edit_view(request, pk):
    obj = get_object_or_404(Circuit.objects.select_related("project"), pk=pk)
    if not _check_edit(request, obj.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    return _edit_resource(
        request, obj, CircuitForm, "electrical/circuit_form.html",
        "Liniya yangilandi.", "Liniya yangilandi",
    )


@login_required
@require_http_methods(["GET", "POST"])
def cable_edit_view(request, pk):
    obj = get_object_or_404(Cable.objects.select_related("project"), pk=pk)
    if not _check_edit(request, obj.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    return _edit_resource(
        request, obj, CableForm, "electrical/cable_form.html",
        "Kabel yangilandi.", "Kabel yangilandi",
    )


@login_required
@require_http_methods(["GET", "POST"])
def device_edit_view(request, pk):
    obj = get_object_or_404(ElectricalDevice.objects.select_related("project"), pk=pk)
    if not _check_edit(request, obj.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    return _edit_resource(
        request, obj, ElectricalDeviceForm, "electrical/device_form.html",
        "Qurilma yangilandi.", "Qurilma yangilandi",
    )


def _delete_resource(request, obj, item_name):
    project = obj.project
    if not _check_edit(request, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        label = obj.name
        try:
            obj.delete()
        except (ProtectedError, RestrictedError):
            messages.error(request, "Avval shu panelga bog'langan liniyalarni o'chiring yoki boshqa panelga o'tkazing.")
            return redirect("projects:detail", pk=project.pk)
        create_revision(project, request.user, f"{item_name} o'chirildi", label)
        messages.success(request, f"{item_name} o'chirildi.")
        return redirect("projects:detail", pk=project.pk)
    return render(request, "shared/confirm_delete.html", {
        "object_label": obj.name,
        "item_name": item_name,
        "cancel_url": redirect("projects:detail", pk=project.pk).url,
    })


@login_required
@require_http_methods(["GET", "POST"])
def panel_delete_view(request, pk):
    obj = get_object_or_404(ElectricalPanel.objects.select_related("project"), pk=pk)
    return _delete_resource(request, obj, "Elektr shit")


@login_required
@require_http_methods(["GET", "POST"])
def circuit_delete_view(request, pk):
    obj = get_object_or_404(Circuit.objects.select_related("project"), pk=pk)
    return _delete_resource(request, obj, "Liniya")


@login_required
@require_http_methods(["GET", "POST"])
def cable_delete_view(request, pk):
    obj = get_object_or_404(Cable.objects.select_related("project"), pk=pk)
    return _delete_resource(request, obj, "Kabel")


@login_required
@require_http_methods(["GET", "POST"])
def device_delete_view(request, pk):
    obj = get_object_or_404(ElectricalDevice.objects.select_related("project"), pk=pk)
    return _delete_resource(request, obj, "Qurilma")
