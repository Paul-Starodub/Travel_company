from django.db import transaction
from rest_framework import serializers

from apps.projects.models import ProjectPlace, TravelProject
from apps.projects.services.art_institute_service import ArtInstituteService


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
        project = self.context["project"]
        items = attrs["places"]
        if project.places.count() + len(items) > 10:
            raise serializers.ValidationError(f"Adding {len(items)} place(s) would exceed the maximum of 10.")
        seen_ids: set[str] = set()
        enriched = []
        for item in items:
            eid = item["external_id"]
            if eid in seen_ids:
                raise serializers.ValidationError(f"Duplicate place '{eid}' in the request.")
            seen_ids.add(eid)
            if project.places.filter(external_id=eid).exists():
                raise serializers.ValidationError(f"Place '{eid}' is already in the project.")
            artwork = ArtInstituteService.get_artwork(eid)
            if not artwork:
                raise serializers.ValidationError(f"Place '{eid}' not found in Art Institute API.")
            enriched.append({**item, "artwork": artwork})
        attrs["places"] = enriched
        return attrs

    @transaction.atomic
    def save(self, **kwargs) -> list[ProjectPlace]:
        project = self.context["project"]
        return [
            ProjectPlace.objects.create(
                project=project,
                external_id=str(item["artwork"]["id"]),
                title=item["artwork"]["title"],
                notes=item.get("notes", ""),
            )
            for item in self.validated_data["places"]
        ]


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
        if len(places_data) > 10:
            raise serializers.ValidationError("A project can have at most 10 places.")
        seen_ids = set()
        enriched = []
        for place_data in places_data:
            eid = place_data["external_id"]
            if eid in seen_ids:
                raise serializers.ValidationError(f"Duplicate place '{eid}' in the request.")
            seen_ids.add(eid)
            artwork = ArtInstituteService.get_artwork(eid)
            if not artwork:
                raise serializers.ValidationError(f"Place '{eid}' not found in Art Institute API.")
            enriched.append({**place_data, "artwork": artwork})
        return enriched

    @transaction.atomic
    def create(self, validated_data) -> TravelProject:
        places_data = validated_data.pop("places_input", [])
        project = TravelProject.objects.create(**validated_data)
        for place_data in places_data:
            artwork = place_data["artwork"]
            ProjectPlace.objects.create(
                project=project,
                external_id=str(artwork["id"]),
                title=artwork["title"],
                notes=place_data.get("notes", ""),
            )
        return project
