from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.projects import views

router = DefaultRouter()
router.register("projects", views.TravelProjectViewSet, basename="project")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "projects/<int:project_pk>/places/",
        views.ProjectPlaceViewSet.as_view({"get": "list", "post": "create"}),
        name="project-place-list",
    ),
    path(
        "projects/<int:project_pk>/places/<int:pk>/",
        views.ProjectPlaceViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update"}),
        name="project-place-detail",
    ),
]
