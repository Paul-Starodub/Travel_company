from django.db import transaction
from rest_framework import serializers

from apps.projects.models import ProjectPlace, TravelProject
from apps.projects.services.art_institute_service import ArtInstituteService


def _validate_and_enrich_places(items: list[dict], project: TravelProject | None = None) -> list[dict]:
    existing_count = project.places.count() if project else 0
    if existing_count + len(items) > 10:
        raise serializers.ValidationError(f"Adding {len(items)} place(s) would exceed the maximum of 10.")
    seen_ids: set[str] = set()
    enriched = []
    for item in items:
        eid = item["external_id"]
        if eid in seen_ids:
            raise serializers.ValidationError(f"Duplicate place '{eid}' in the request.")
        seen_ids.add(eid)
        if project and project.places.filter(external_id=eid).exists():
            raise serializers.ValidationError(f"Place '{eid}' is already in the project.")
        artwork = ArtInstituteService.get_artwork(eid)
        if not artwork:
            raise serializers.ValidationError(f"Place '{eid}' not found in Art Institute API.")
        enriched.append({**item, "artwork": artwork})
    return enriched


def _bulk_create_places(project: TravelProject, places_data: list[dict]) -> list[ProjectPlace]:
    return ProjectPlace.objects.bulk_create(
        [
            ProjectPlace(
                project=project,
                external_id=str(item["artwork"]["id"]),
                title=item["artwork"]["title"],
                notes=item.get("notes", ""),
            )
            for item in places_data
        ]
    )


class ProjectPlaceReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPlace
        fields = ["id", "external_id", "title", "notes", "visited"]


class PlaceInputSerializer(serializers.Serializer):
    external_id = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ProjectPlaceCreateSerializer(serializers.Serializer):
    places = PlaceInputSerializer(many=True, min_length=1)

    def validate(self, attrs) -> dict:
        attrs["places"] = _validate_and_enrich_places(attrs["places"], project=self.context["project"])
        return attrs

    @transaction.atomic
    def save(self, **kwargs) -> list[ProjectPlace]:
        return _bulk_create_places(self.context["project"], self.validated_data["places"])


class ProjectPlaceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPlace
        fields = ["notes", "visited"]


class TravelProjectSerializer(serializers.ModelSerializer):
    places = ProjectPlaceReadSerializer(many=True, read_only=True)
    places_input = PlaceInputSerializer(many=True, write_only=True, required=False)
    is_completed = serializers.BooleanField(read_only=True)

    class Meta:
        model = TravelProject
        fields = ["id", "name", "description", "start_date", "is_completed", "places", "places_input"]

    def validate_places_input(self, places_data) -> list[dict]:
        return _validate_and_enrich_places(places_data)

    @transaction.atomic
    def create(self, validated_data) -> TravelProject:
        places_data = validated_data.pop("places_input", [])
        project = TravelProject.objects.create(**validated_data)
        if places_data:
            _bulk_create_places(project, places_data)
        return project
