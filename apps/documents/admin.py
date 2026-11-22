from django.contrib import admin
from .models import ProjectImage, ProjectDocument, ProjectRevision

@admin.register(ProjectImage)
class ProjectImageAdmin(admin.ModelAdmin):
    list_display = ("project", "category", "uploaded_at")
    list_filter = ("category",)

@admin.register(ProjectDocument)
class ProjectDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "is_public", "uploaded_at")
    list_filter = ("is_public",)

@admin.register(ProjectRevision)
class ProjectRevisionAdmin(admin.ModelAdmin):
    list_display = ("project", "revision_number", "title", "created_at")
