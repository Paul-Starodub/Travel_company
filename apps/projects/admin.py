from django.contrib import admin

from apps.projects.models import ProjectPlace, TravelProject


@admin.register(TravelProject)
class TravelProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "is_completed"]
    search_fields = ["name"]


@admin.register(ProjectPlace)
class ProjectPlaceAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "external_id", "visited"]
    list_filter = ["visited"]
    search_fields = ["title", "external_id"]
