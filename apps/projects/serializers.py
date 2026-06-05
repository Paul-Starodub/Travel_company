from django.db import transaction
from rest_framework import serializers

from apps.projects.exceptions import PlaceValidationError
from apps.projects.models import ProjectPlace, TravelProject
from apps.projects.services.place_service import bulk_create_places, enrich_with_artwork, validate_places


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
        try:
            validate_places(attrs["places"], project=self.context["project"])
            attrs["places"] = enrich_with_artwork(attrs["places"])
        except PlaceValidationError as e:
            raise serializers.ValidationError(str(e))
        return attrs

    @transaction.atomic
    def save(self, **kwargs) -> list[ProjectPlace]:
        return bulk_create_places(self.context["project"], self.validated_data["places"])


class ProjectPlaceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPlace
        fields = ["notes", "visited"]


class TravelProjectSerializer(serializers.ModelSerializer):
    places = ProjectPlaceReadSerializer(many=True, read_only=True)
    places_input = PlaceInputSerializer(many=True, write_only=True, min_length=1)
    is_completed = serializers.BooleanField(read_only=True)

    class Meta:
        model = TravelProject
        fields = ["id", "name", "description", "start_date", "is_completed", "places", "places_input"]

    def get_fields(self) -> dict:
        fields = super().get_fields()
        if self.instance is not None:
            fields["places_input"].required = False
        return fields

    def validate_places_input(self, places_data) -> list[dict]:
        try:
            validate_places(places_data)
            return enrich_with_artwork(places_data)
        except PlaceValidationError as e:
            raise serializers.ValidationError(str(e))

    @transaction.atomic
    def create(self, validated_data) -> TravelProject:
        places_data = validated_data.pop("places_input")
        project = TravelProject.objects.create(**validated_data)
        bulk_create_places(project, places_data)
        return project
