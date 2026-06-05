from rest_framework import serializers

from apps.projects.models import ProjectPlace, TravelProject
from apps.projects.services.art_institute_service import ArtInstituteService


def validate_and_enrich_places(items: list[dict], project: TravelProject | None = None) -> list[dict]:
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


def bulk_create_places(project: TravelProject, places_data: list[dict]) -> list[ProjectPlace]:
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
