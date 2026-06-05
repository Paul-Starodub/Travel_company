import os

import requests
from django.core.cache import cache


class ArtInstituteService:
    BASE_URL = os.getenv("ART_INSTITUTE_API_URL", "https://api.artic.edu/api/v1")
    CACHE_TTL = 3600

    @classmethod
    def get_artwork(cls, external_id: str) -> dict | None:
        cache_key = f"artwork_{external_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            url = f"{cls.BASE_URL}/artworks/{external_id}?fields=id,title"
            response = requests.get(url, timeout=10)
        except requests.RequestException:
            return None

        if response.status_code != 200:
            return None

        data = response.json().get("data")
        if data:
            cache.set(cache_key, data, cls.CACHE_TTL)
        return data
