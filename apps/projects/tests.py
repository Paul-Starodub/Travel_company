from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APITestCase

from apps.projects.exceptions import ExternalServiceError, PlaceValidationError
from apps.projects.models import ProjectPlace, TravelProject
from apps.projects.services.place_service import bulk_create_places, enrich_with_artwork, validate_places

User = get_user_model()

ARTWORK_1 = {"id": "111", "title": "Artwork One"}
ARTWORK_2 = {"id": "222", "title": "Artwork Two"}


def make_project(**kwargs) -> TravelProject:
    defaults = {"name": "Test Trip"}
    defaults.update(kwargs)
    return TravelProject.objects.create(**defaults)


def make_place(project, external_id="111", title="Place One", visited=False) -> ProjectPlace:
    return ProjectPlace.objects.create(project=project, external_id=external_id, title=title, visited=visited)


class TravelProjectModelTest(APITestCase):
    def test_str(self):
        project = make_project(name="Paris Trip")
        self.assertEqual(str(project), "Paris Trip")

    def test_is_completed_no_places(self):
        project = make_project()
        self.assertFalse(project.is_completed)

    def test_is_completed_all_visited(self):
        project = make_project()
        make_place(project, external_id="a", visited=True)
        make_place(project, external_id="b", visited=True)
        self.assertTrue(project.is_completed)

    def test_is_completed_some_unvisited(self):
        project = make_project()
        make_place(project, external_id="a", visited=True)
        make_place(project, external_id="b", visited=False)
        self.assertFalse(project.is_completed)

    def test_is_completed_all_unvisited(self):
        project = make_project()
        make_place(project, external_id="a", visited=False)
        self.assertFalse(project.is_completed)


class ProjectPlaceModelTest(APITestCase):
    def test_str(self):
        project = make_project()
        place = make_place(project, title="Louvre")
        self.assertEqual(str(place), "Louvre")

    def test_unique_place_per_project_constraint(self):
        project = make_project()
        make_place(project, external_id="dup")
        with self.assertRaises(IntegrityError):
            make_place(project, external_id="dup")

    def test_same_external_id_allowed_in_different_projects(self):
        p1 = make_project(name="Trip A")
        p2 = make_project(name="Trip B")
        make_place(p1, external_id="shared")
        make_place(p2, external_id="shared")  # should not raise


class ValidatePlacesTest(APITestCase):
    def test_no_project_passes(self):
        validate_places([{"external_id": "1"}, {"external_id": "2"}])

    def test_exceeds_limit_without_project(self):
        items = [{"external_id": str(i)} for i in range(11)]
        with self.assertRaises(PlaceValidationError):
            validate_places(items)

    def test_exceeds_limit_with_existing_places(self):
        project = make_project()
        for i in range(8):
            make_place(project, external_id=str(i))
        with self.assertRaises(PlaceValidationError):
            validate_places([{"external_id": "100"}, {"external_id": "101"}, {"external_id": "102"}], project=project)

    def test_exactly_at_limit_passes(self):
        project = make_project()
        for i in range(8):
            make_place(project, external_id=str(i))
        validate_places([{"external_id": "100"}, {"external_id": "101"}], project=project)

    def test_duplicate_in_request(self):
        with self.assertRaises(PlaceValidationError):
            validate_places([{"external_id": "same"}, {"external_id": "same"}])

    def test_already_in_project(self):
        project = make_project()
        make_place(project, external_id="existing")
        with self.assertRaises(PlaceValidationError):
            validate_places([{"external_id": "existing"}], project=project)

    def test_valid_new_places_with_project(self):
        project = make_project()
        make_place(project, external_id="old")
        validate_places([{"external_id": "new1"}, {"external_id": "new2"}], project=project)


class EnrichWithArtworkTest(APITestCase):
    @patch("apps.projects.services.place_service.ArtInstituteService.get_artwork")
    def test_enriches_items(self, mock_get):
        mock_get.return_value = ARTWORK_1
        result = enrich_with_artwork([{"external_id": "111", "notes": "nice"}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["artwork"], ARTWORK_1)
        self.assertEqual(result[0]["notes"], "nice")

    @patch("apps.projects.services.place_service.ArtInstituteService.get_artwork")
    def test_raises_when_artwork_not_found(self, mock_get):
        mock_get.return_value = None
        with self.assertRaises(PlaceValidationError):
            enrich_with_artwork([{"external_id": "999"}])


class BulkCreatePlacesTest(APITestCase):
    def test_creates_places(self):
        project = make_project()
        places_data = [
            {"artwork": {"id": "111", "title": "One"}, "notes": "note"},
            {"artwork": {"id": "222", "title": "Two"}, "notes": ""},
        ]
        places = bulk_create_places(project, places_data)
        self.assertEqual(len(places), 2)
        self.assertEqual(ProjectPlace.objects.filter(project=project).count(), 2)

    def test_sets_correct_fields(self):
        project = make_project()
        places = bulk_create_places(project, [{"artwork": {"id": "555", "title": "Five"}, "notes": "my note"}])
        self.assertEqual(places[0].external_id, "555")
        self.assertEqual(places[0].title, "Five")
        self.assertEqual(places[0].notes, "my note")


class ArtInstituteServiceTest(APITestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    @patch("apps.projects.services.art_institute_service.requests.get")
    def test_returns_data_on_success(self, mock_get):
        from apps.projects.services.art_institute_service import ArtInstituteService

        mock_get.return_value = MagicMock(status_code=200, ok=True, json=lambda: {"data": ARTWORK_1})
        self.assertEqual(ArtInstituteService.get_artwork("111"), ARTWORK_1)

    @patch("apps.projects.services.art_institute_service.requests.get")
    def test_returns_none_on_404(self, mock_get):
        from apps.projects.services.art_institute_service import ArtInstituteService

        mock_get.return_value = MagicMock(status_code=404, ok=False)
        self.assertIsNone(ArtInstituteService.get_artwork("999"))

    @patch("apps.projects.services.art_institute_service.requests.get")
    def test_raises_on_server_error(self, mock_get):
        from apps.projects.services.art_institute_service import ArtInstituteService

        mock_get.return_value = MagicMock(status_code=500, ok=False)
        with self.assertRaises(ExternalServiceError):
            ArtInstituteService.get_artwork("111")

    @patch("apps.projects.services.art_institute_service.requests.get")
    def test_raises_on_request_exception(self, mock_get):
        import requests as req
        from apps.projects.services.art_institute_service import ArtInstituteService

        mock_get.side_effect = req.RequestException("timeout")
        with self.assertRaises(ExternalServiceError):
            ArtInstituteService.get_artwork("111")

    @patch("apps.projects.services.art_institute_service.requests.get")
    def test_uses_cache_on_second_call(self, mock_get):
        from apps.projects.services.art_institute_service import ArtInstituteService

        mock_get.return_value = MagicMock(status_code=200, ok=True, json=lambda: {"data": ARTWORK_1})
        ArtInstituteService.get_artwork("111")
        ArtInstituteService.get_artwork("111")
        self.assertEqual(mock_get.call_count, 1)


class ProjectAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testname", password="pass")
        self.client.force_authenticate(user=self.user)

    def project_list_url(self):
        return "/api/projects/"

    def project_detail_url(self, pk):
        return f"/api/projects/{pk}/"

    def place_list_url(self, project_pk):
        return f"/api/projects/{project_pk}/places/"

    def place_detail_url(self, project_pk, pk):
        return f"/api/projects/{project_pk}/places/{pk}/"


class TravelProjectViewSetTest(ProjectAPITestCase):
    @patch("apps.projects.serializers.validate_places")
    @patch("apps.projects.serializers.enrich_with_artwork")
    def test_create_project(self, mock_enrich, mock_validate):
        mock_enrich.return_value = [{"external_id": "111", "artwork": ARTWORK_1, "notes": ""}]
        response = self.client.post(
            self.project_list_url(),
            {"name": "Tokyo Trip", "places_input": [{"external_id": "111"}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TravelProject.objects.count(), 1)

    def test_list_projects(self):
        make_project(name="A")
        make_project(name="B")
        response = self.client.get(self.project_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_retrieve_project(self):
        project = make_project(name="Rome")
        response = self.client.get(self.project_detail_url(project.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Rome")

    def test_partial_update_project_name(self):
        project = make_project(name="Old Name")
        response = self.client.patch(self.project_detail_url(project.pk), {"name": "New Name"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.name, "New Name")

    def test_delete_project_without_visited_places(self):
        project = make_project()
        make_place(project, visited=False)
        response = self.client.delete(self.project_detail_url(project.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TravelProject.objects.filter(pk=project.pk).exists())

    def test_delete_project_blocked_when_has_visited_places(self):
        project = make_project()
        make_place(project, visited=True)
        response = self.client.delete(self.project_detail_url(project.pk))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(TravelProject.objects.filter(pk=project.pk).exists())

    def test_delete_project_with_no_places(self):
        project = make_project()
        response = self.client.delete(self.project_detail_url(project.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_filter_completed_true_returns_only_completed(self):
        done = make_project(name="Done")
        make_place(done, external_id="a", visited=True)
        in_progress = make_project(name="InProgress")
        make_place(in_progress, external_id="b", visited=False)
        make_project(name="Empty")

        response = self.client.get(self.project_list_url() + "?completed=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [p["name"] for p in response.data["results"]]
        self.assertIn("Done", names)
        self.assertNotIn("InProgress", names)
        self.assertNotIn("Empty", names)

    def test_filter_completed_false_excludes_completed(self):
        done = make_project(name="Done")
        make_place(done, external_id="a", visited=True)
        in_progress = make_project(name="InProgress")
        make_place(in_progress, external_id="b", visited=False)
        make_project(name="Empty")

        response = self.client.get(self.project_list_url() + "?completed=false")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [p["name"] for p in response.data["results"]]
        self.assertNotIn("Done", names)
        self.assertIn("InProgress", names)
        self.assertIn("Empty", names)

    def test_search_by_name(self):
        make_project(name="Paris Adventure")
        make_project(name="Tokyo Tour")
        response = self.client.get(self.project_list_url() + "?search=Paris")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Paris Adventure")

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.project_list_url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProjectPlaceViewSetTest(ProjectAPITestCase):
    def setUp(self):
        super().setUp()
        self.project = make_project()

    @patch("apps.projects.serializers.validate_places")
    @patch("apps.projects.serializers.enrich_with_artwork")
    def test_create_single_place(self, mock_enrich, mock_validate):
        mock_enrich.return_value = [{"external_id": "111", "artwork": ARTWORK_1, "notes": ""}]
        response = self.client.post(self.place_list_url(self.project.pk), {"external_id": "111"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProjectPlace.objects.filter(project=self.project).count(), 1)

    @patch("apps.projects.serializers.validate_places")
    @patch("apps.projects.serializers.enrich_with_artwork")
    def test_create_multiple_places(self, mock_enrich, mock_validate):
        mock_enrich.return_value = [
            {"external_id": "111", "artwork": ARTWORK_1, "notes": ""},
            {"external_id": "222", "artwork": ARTWORK_2, "notes": ""},
        ]
        response = self.client.post(
            self.place_list_url(self.project.pk),
            [{"external_id": "111"}, {"external_id": "222"}],
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProjectPlace.objects.filter(project=self.project).count(), 2)

    def test_list_places(self):
        make_place(self.project, external_id="a")
        make_place(self.project, external_id="b")
        response = self.client.get(self.place_list_url(self.project.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_retrieve_place(self):
        place = make_place(self.project, title="Gallery")
        response = self.client.get(self.place_detail_url(self.project.pk, place.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Gallery")

    def test_update_place_visited(self):
        place = make_place(self.project, visited=False)
        response = self.client.patch(self.place_detail_url(self.project.pk, place.pk), {"visited": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        place.refresh_from_db()
        self.assertTrue(place.visited)

    def test_update_place_notes(self):
        place = make_place(self.project)
        response = self.client.patch(
            self.place_detail_url(self.project.pk, place.pk), {"notes": "updated"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        place.refresh_from_db()
        self.assertEqual(place.notes, "updated")

    def test_places_for_nonexistent_project_returns_404(self):
        response = self.client.get(self.place_list_url(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_places_scoped_to_project(self):
        other = make_project(name="Other")
        make_place(other, external_id="other")
        make_place(self.project, external_id="mine")
        response = self.client.get(self.place_list_url(self.project.pk))
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["external_id"], "mine")


class TravelProjectSerializerTest(APITestCase):
    @patch("apps.projects.serializers.validate_places")
    @patch("apps.projects.serializers.enrich_with_artwork")
    def test_create_requires_places_input(self, mock_enrich, mock_validate):
        from apps.projects.serializers import TravelProjectSerializer

        serializer = TravelProjectSerializer(data={"name": "No Places"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("places_input", serializer.errors)

    def test_places_input_not_required_on_update(self):
        from apps.projects.serializers import TravelProjectSerializer

        project = make_project()
        serializer = TravelProjectSerializer(project, data={"name": "Updated"}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_places_input_min_length_one(self):
        from apps.projects.serializers import TravelProjectSerializer

        serializer = TravelProjectSerializer(data={"name": "Trip", "places_input": []})
        self.assertFalse(serializer.is_valid())
        self.assertIn("places_input", serializer.errors)

    @patch("apps.projects.serializers.enrich_with_artwork")
    @patch("apps.projects.serializers.validate_places")
    def test_validate_places_input_raises_on_service_error(self, mock_validate, mock_enrich):
        from apps.projects.serializers import TravelProjectSerializer

        mock_validate.side_effect = PlaceValidationError("bad place")
        serializer = TravelProjectSerializer(data={"name": "Trip", "places_input": [{"external_id": "bad"}]})
        self.assertFalse(serializer.is_valid())
        self.assertIn("places_input", serializer.errors)


class ProjectPlaceCreateSerializerTest(APITestCase):
    def setUp(self):
        self.project = make_project()

    @patch("apps.projects.serializers.enrich_with_artwork")
    @patch("apps.projects.serializers.validate_places")
    def test_valid_data_saves_places(self, mock_validate, mock_enrich):
        from apps.projects.serializers import ProjectPlaceCreateSerializer

        mock_enrich.return_value = [{"external_id": "111", "artwork": ARTWORK_1, "notes": ""}]
        serializer = ProjectPlaceCreateSerializer(
            data={"places": [{"external_id": "111"}]},
            context={"project": self.project},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        places = serializer.save()
        self.assertEqual(len(places), 1)

    def test_empty_places_fails_validation(self):
        from apps.projects.serializers import ProjectPlaceCreateSerializer

        serializer = ProjectPlaceCreateSerializer(data={"places": []}, context={"project": self.project})
        self.assertFalse(serializer.is_valid())

    @patch("apps.projects.serializers.enrich_with_artwork")
    @patch("apps.projects.serializers.validate_places")
    def test_place_validation_error_propagates(self, mock_validate, mock_enrich):
        from apps.projects.serializers import ProjectPlaceCreateSerializer

        mock_validate.side_effect = PlaceValidationError("already exists")
        serializer = ProjectPlaceCreateSerializer(
            data={"places": [{"external_id": "111"}]},
            context={"project": self.project},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)
