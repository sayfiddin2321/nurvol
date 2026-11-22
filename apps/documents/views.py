from mimetypes import guess_type
import logging

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, HttpResponseForbidden, Http404, HttpResponse, StreamingHttpResponse
import re
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from apps.projects.models import Project
from apps.projects.services import create_revision, user_can_edit_project, user_can_view_project_media
from apps.qrcodes.services import get_or_create_building_qr
from .models import ProjectImage, ProjectDocument
from .forms import ProjectImageForm, ProjectImageEditForm, ProjectDocumentForm
from .services import ensure_image_thumbnail, ensure_display_image, save_project_document, save_project_image

logger = logging.getLogger(__name__)


def _image_response(image, variant):
    try:
        file = ensure_image_thumbnail(image) if variant == "thumbnail" else ensure_display_image(image) if variant == "display" else image.image
        response = FileResponse(file.open("rb"), content_type="image/webp" if variant != "original" else guess_type(file.name)[0] or "application/octet-stream")
    except (OSError, ValueError, ValidationError):
        logger.exception("Unable to serve project image %s (%s)", image.pk, variant)
        raise Http404("Rasm topilmadi.")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-cache"
    return response


@require_http_methods(["GET"])
def image_view(request, pk):
    image = get_object_or_404(
        ProjectImage.objects.select_related("project", "project__electrician"),
        pk=pk,
    )
    if not user_can_view_project_media(request.user, image.project):
        return HttpResponseForbidden("Ruxsat yo'q.")

    return _image_response(image, "original")


@require_http_methods(["GET"])
def image_display_view(request, pk):
    image = get_object_or_404(ProjectImage.objects.select_related("project"), pk=pk)
    if not user_can_view_project_media(request.user, image.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    return _image_response(image, "display")


@require_http_methods(["GET"])
def image_thumbnail_view(request, pk):
    image = get_object_or_404(
        ProjectImage.objects.select_related("project", "project__electrician"),
        pk=pk,
    )
    if not user_can_view_project_media(request.user, image.project):
        return HttpResponseForbidden("Ruxsat yo'q.")

    return _image_response(image, "thumbnail")


@login_required
@require_http_methods(["GET", "POST"])
def image_upload_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        form = ProjectImageForm(request.POST, request.FILES)
        if form.is_valid():
            images = form.cleaned_data["images"]
            saved = []
            try:
                with transaction.atomic():
                    for image in images:
                        saved.append(save_project_image(
                            project, image, ProjectImage.Category.OTHER, request.user,
                            form.cleaned_data["description"],
                        ))
                    # Uploading shares this gallery without a separate visibility step.
                    if not project.is_public:
                        project.is_public = True
                        project.save(update_fields=["is_public", "updated_at"])
                    qr = get_or_create_building_qr(project)
                    if not qr.is_active:
                        qr.is_active = True
                        qr.save(update_fields=["is_active"])
            except (OSError, ValidationError):
                for image in saved:
                    for field in (image.image, image.thumbnail, image.display_image):
                        if field:
                            field.delete(save=False)
                logger.exception("Image batch upload failed for project %s", project.pk)
                form.add_error(None, "Rasmlar saqlanmadi. Qayta tanlab, yana urinib ko'ring.")
            else:
                messages.success(request, f"{len(images)} ta rasm yuklandi.")
                return redirect(f"{reverse('projects:detail', args=[project_pk])}#tab-images")
    else:
        form = ProjectImageForm()
    return render(request, "documents/upload.html", {
        "form": form,
        "project": project,
        "type": "image",
    })


@login_required
@require_http_methods(["GET", "POST"])
def document_upload_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if request.method == "POST":
        form = ProjectDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                save_project_document(project, form, request.user)
            except (OSError, ValidationError):
                logger.exception("Document upload failed for project %s", project.pk)
                form.add_error(None, "Fayl saqlanmadi. Qayta tanlab, yana urinib ko'ring.")
            else:
                messages.success(request, "Fayl yuklandi.")
                return redirect(f"{reverse('projects:detail', args=[project_pk])}#tab-documents")
    else:
        form = ProjectDocumentForm()
    return render(request, "documents/upload.html", {"form": form, "project": project, "type": "document"})


@login_required
@require_POST
def image_delete_view(request, pk):
    image = get_object_or_404(ProjectImage.objects.select_related("project"), pk=pk)
    if not user_can_edit_project(request.user, image.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    project = image.project
    title = image.description or image.image.name
    image.delete()
    create_revision(project, request.user, "Rasm o'chirildi", title)
    messages.success(request, "Rasm o'chirildi.")
    return redirect(f"{reverse('projects:detail', args=[project.pk])}#tab-images")


@login_required
@require_http_methods(["GET", "POST"])
def image_edit_view(request, pk):
    image = get_object_or_404(ProjectImage.objects.select_related("project"), pk=pk)
    if not user_can_edit_project(request.user, image.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    form = ProjectImageEditForm(request.POST or None, instance=image)
    if request.method == "POST" and form.is_valid():
        form.save()
        create_revision(image.project, request.user, "Rasm ma'lumoti yangilandi", image.caption)
        return redirect(f"{reverse('projects:detail', args=[image.project_id])}#tab-images")
    return render(request, "documents/image_edit.html", {"form": form, "image": image, "project": image.project})


@login_required
@require_POST
def document_delete_view(request, pk):
    document = get_object_or_404(ProjectDocument.objects.select_related("project"), pk=pk)
    if not user_can_edit_project(request.user, document.project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    project = document.project
    title = document.title
    document.delete()
    create_revision(project, request.user, "Hujjat o'chirildi", title)
    messages.success(request, "Hujjat o'chirildi.")
    return redirect("projects:detail", pk=project.pk)


@login_required
def revision_list_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not user_can_edit_project(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    revisions = project.revisions.select_related("changed_by")
    return render(request, "documents/revisions.html", {
        "project": project,
        "revisions": revisions,
    })


@require_http_methods(["GET"])
def document_download_view(request, pk):
    doc = get_object_or_404(ProjectDocument, pk=pk)
    project = doc.project
    if not user_can_view_project_media(request.user, project):
        return HttpResponseForbidden("Ruxsat yo'q.")
    is_owner_or_admin = request.user.is_authenticated and (
        request.user == project.electrician or request.user.is_administrator
    )
    if not doc.is_public and not is_owner_or_admin:
        return HttpResponseForbidden("Ruxsat yo'q.")
    try:
        response = FileResponse(doc.file.open("rb"), as_attachment=True, filename=doc.title + "." + doc.file.name.rsplit(".", 1)[-1])
    except OSError:
        logger.exception("Unable to download document %s", doc.pk)
        raise Http404("Fayl topilmadi.")
    response["Cache-Control"] = "private, no-cache"
    return response


@require_http_methods(["GET"])
def document_preview_view(request, pk):
    doc = get_object_or_404(ProjectDocument.objects.select_related("project"), pk=pk)
    if not user_can_view_project_media(request.user, doc.project) or (
        not doc.is_public and not user_can_edit_project(request.user, doc.project)
    ):
        return HttpResponseForbidden("Ruxsat yo'q.")
    if not doc.is_video:
        raise Http404("Video topilmadi.")
    try:
        size = doc.file.size
        stream = doc.file.open("rb")
    except OSError:
        logger.exception("Unable to preview video %s", doc.pk)
        raise Http404("Fayl topilmadi.")
    content_type = "video/webm" if doc.file.name.lower().endswith(".webm") else "video/mp4"
    header = request.headers.get("Range", "")
    if header:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
        start, end = 0, size - 1
        try:
            if not match or not any(match.groups()):
                raise ValueError
            left, right = match.groups()
            if left:
                start = int(left)
                end = min(int(right), size - 1) if right else size - 1
            else:
                start = max(size - int(right), 0)
            if start > end or start >= size:
                raise ValueError
        except ValueError:
            stream.close()
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response
        stream.seek(start)
        def chunks():
            remaining = end - start + 1
            try:
                while remaining:
                    chunk = stream.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
            finally:
                stream.close()
        response = StreamingHttpResponse(chunks(), status=206, content_type=content_type)
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
        response["Content-Length"] = end - start + 1
    else:
        response = FileResponse(stream, content_type=content_type)
    response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "private, no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def protected_media_view(request, path):
    """Project uploads must be served by the permission-checked endpoints."""
    raise Http404("Faylni pasport orqali oching.")
