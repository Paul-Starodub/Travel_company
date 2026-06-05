from django.db import models


class TravelProject(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)

    @property
    def is_completed(self) -> bool:
        return self.places.exists() and not self.places.filter(visited=False).exists()

    def __str__(self) -> str:
        return self.name


class ProjectPlace(models.Model):
    project = models.ForeignKey(TravelProject, on_delete=models.CASCADE, related_name="places")
    external_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    notes = models.TextField(blank=True, null=True)
    visited = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "external_id"], name="unique_place_per_project")]

    def __str__(self) -> str:
        return self.title
