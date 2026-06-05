from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import filters, mixins, status, viewsets
from rest_framework.response import Response

from apps.common.paginators import StandardPagination
from apps.projects.models import ProjectPlace, TravelProject
from apps.projects.serializers import (
    ProjectPlaceCreateSerializer,
    ProjectPlaceReadSerializer,
    ProjectPlaceUpdateSerializer,
    TravelProjectSerializer,
)


class TravelProjectViewSet(viewsets.ModelViewSet):
    serializer_class = TravelProjectSerializer
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["start_date", "name"]

    def get_queryset(self):
        qs = TravelProject.objects.prefetch_related("places")
        completed = self.request.query_params.get("completed")
        if completed is not None:
            flag = completed.lower() == "true"
            qs = [project for project in qs if project.is_completed == flag]
        return qs

    @transaction.atomic
    def destroy(self, request, *args, **kwargs) -> Response:
        project = self.get_object()
        if project.places.filter(visited=True).exists():
            return Response(
                {"detail": "Cannot delete a project that has visited places."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class ProjectPlaceViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    pagination_class = StandardPagination

    def _get_project(self):
        return get_object_or_404(TravelProject, pk=self.kwargs["project_pk"])

    def get_queryset(self):
        return ProjectPlace.objects.filter(project=self._get_project()).order_by("id")

    def get_serializer_class(self):
        match self.action:
            case "create":
                return ProjectPlaceCreateSerializer
            case "update" | "partial_update":
                return ProjectPlaceUpdateSerializer
            case _:
                return ProjectPlaceReadSerializer

    def get_serializer_context(self) -> dict:
        context = super().get_serializer_context()
        context["project"] = self._get_project()
        return context

    def create(self, request, *args, **kwargs) -> Response:
        raw = request.data if isinstance(request.data, list) else [request.data]
        serializer = self.get_serializer(data={"places": raw}, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        places = serializer.save()
        return Response(ProjectPlaceReadSerializer(places, many=True).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        place = serializer.save()
        return Response(ProjectPlaceReadSerializer(place).data)
