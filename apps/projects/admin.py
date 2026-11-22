from django.contrib import admin
from .models import Project, ProjectShowcaseSettings, ShowcaseVideo, Floor, Room

class FloorInline(admin.TabularInline):
    model = Floor
    extra = 0

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "electrician", "project_type", "status", "is_public", "created_at")
    list_filter = ("status", "project_type", "is_public")
    search_fields = ("name", "address")
    inlines = [FloorInline]

@admin.register(ProjectShowcaseSettings)
class ProjectShowcaseSettingsAdmin(admin.ModelAdmin):
    list_display = ("__str__", "featured_electrician", "updated_at")

@admin.register(ShowcaseVideo)
class ShowcaseVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "order", "created_at")
    list_filter = ("is_active",)
    list_editable = ("is_active", "order")
    search_fields = ("title", "description")

@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "floor_number")

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "floor", "room_type")