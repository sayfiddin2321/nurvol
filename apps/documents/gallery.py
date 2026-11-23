from django.core.paginator import Paginator
from django.db.models import Q


def project_gallery_context(project, request, can_edit=False):
    images = project.images.order_by("uploaded_at", "pk")
    videos = project.documents.filter(Q(file__iendswith=".mp4") | Q(file__iendswith=".webm")).order_by("uploaded_at", "pk")
    if not can_edit:
        videos = videos.filter(is_public=True)
    return {
        "gallery_page": Paginator(images.exclude(category="panel"), 24).get_page(request.GET.get("photos")),
        "panel_gallery_page": Paginator(images.filter(category="panel"), 24).get_page(request.GET.get("panels")),
        "general_videos": videos.exclude(category="panel"),
        "panel_videos": videos.filter(category="panel"),
    }
