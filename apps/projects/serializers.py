from django.db import transaction
from rest_framework import serializers

from apps.projects.models import ProjectPlace, TravelProject
from apps.projects.services.art_institute_service import ArtInstituteService


class ProjectPlaceReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPlace
        fields = ["id", "external_id", "title", "notes", "visited"]


class ProjectPlaceCreateSerializer(serializers.Serializer):
    external_id = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_external_id(self, value):
        artwork = ArtInstituteService.get_artwork(value)
        if not artwork:
            raise serializers.ValidationError("Place not found in Art Institute API.")
        self._artwork = artwork
        return value

    def validate(self, attrs):
        project = self.context["project"]
        if project.places.count() >= 10:
            raise serializers.ValidationError("Project already has the maximum of 10 places.")
        if project.places.filter(external_id=attrs["external_id"]).exists():
            raise serializers.ValidationError("This place is already in the project.")
        return attrs

    def save(self, **kwargs) -> ProjectPlace:
        project = self.context["project"]
        return ProjectPlace.objects.create(
            project=project,
            external_id=str(self._artwork["id"]),
            title=self._artwork["title"],
            notes=self.validated_data.get("notes", ""),
        )


class ProjectPlaceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPlace
        fields = ["notes", "visited"]


class PlaceInputSerializer(serializers.Serializer):
    external_id = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class TravelProjectSerializer(serializers.ModelSerializer):
    places = ProjectPlaceReadSerializer(many=True, read_only=True)
    places_input = PlaceInputSerializer(many=True, write_only=True, required=False)
    is_completed = serializers.BooleanField(read_only=True)

    class Meta:
        model = TravelProject
        fields = [
            "id",
            "name",
            "description",
            "start_date",
            "is_completed",
            "created_at",
            "updated_at",
            "places",
            "places_input",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_places_input(self, places_data):
        if len(places_data) > 10:
            raise serializers.ValidationError("A project can have at most 10 places.")

        seen_ids = set()
        artworks = []
        for place_data in places_data:
            eid = place_data["external_id"]
            if eid in seen_ids:
                raise serializers.ValidationError(f"Duplicate place '{eid}' in the request.")
            seen_ids.add(eid)

            artwork = ArtInstituteService.get_artwork(eid)
            if not artwork:
                raise serializers.ValidationError(f"Place '{eid}' not found in Art Institute API.")
            artworks.append((place_data, artwork))

        self._validated_artworks = artworks
        return places_data

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("places_input", [])
        project = TravelProject.objects.create(**validated_data)

        for place_data, artwork in getattr(self, "_validated_artworks", []):
            ProjectPlace.objects.create(
                project=project,
                external_id=str(artwork["id"]),
                title=artwork["title"],
                notes=place_data.get("notes", ""),
            )

        return project