import re
import math
from typing import Any, Optional

from movie_tracker.helpers import omdb_to_isodate
from movie_tracker.http_client import (
    HttpClient,
    HttpDecodeError,
    HttpNetworkError,
    HttpStatusError,
    HttpTimeoutError,
    default_http_client,
)
from movie_tracker.imdb_id import normalize_imdb_id
from movie_tracker.metadata.models import MovieMetadata
from movie_tracker.metadata.provider import (
    MetadataApiError,
    MetadataNotFoundError,
    MetadataTransportError,
)


def _value(data: dict, key: str) -> Optional[str]:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or value.strip() == "N/A":
        return None
    return value.strip()


def _runtime_minutes(value: Optional[str]) -> Optional[int]:
    match = re.fullmatch(r"\s*(\d+)\s+min\s*", value or "", re.IGNORECASE)
    number = int(match.group(1)) if match else 0
    return number if number > 0 else None


def _float(value: Optional[str]) -> Optional[float]:
    try:
        number = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    if number is None or not math.isfinite(number) or not 0 <= number <= 10:
        return None
    return number


def _year(value: Optional[str]) -> Optional[int]:
    if not value or not re.fullmatch(r"\d{4}", value):
        return None
    year = int(value)
    return year if year >= 1800 else None


class OmdbProvider:
    def __init__(self, api_key: str, http_client: HttpClient = default_http_client):
        self.api_key = api_key
        self.http_client = http_client

    def get_by_imdb_id(self, imdb_id: str) -> MovieMetadata:
        canonical_id = normalize_imdb_id(imdb_id)
        try:
            data: Any = self.http_client.get_json(
                "https://www.omdbapi.com/",
                params={"i": canonical_id, "apikey": self.api_key, "plot": "full"},
            )
        except (HttpTimeoutError, HttpNetworkError) as exc:
            raise MetadataTransportError("Unable to contact OMDb") from exc
        except HttpStatusError as exc:
            raise MetadataApiError(
                "OMDb returned HTTP {}".format(exc.status_code)
            ) from exc
        except HttpDecodeError as exc:
            raise MetadataApiError("OMDb returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise MetadataApiError("OMDb returned an unexpected response")
        if data.get("Response") == "False":
            message = str(data.get("Error") or "unknown API error")
            if "not found" in message.lower():
                raise MetadataNotFoundError("Movie not found on OMDb")
            raise MetadataApiError("OMDb API error: " + message)
        if data.get("Response") != "True":
            raise MetadataApiError("OMDb returned an unexpected response")

        released = _value(data, "Released")
        try:
            release_date = omdb_to_isodate(released) if released else None
        except (TypeError, ValueError, KeyError):
            release_date = None
        year = _year(_value(data, "Year"))
        split = lambda key: [
            x.strip() for x in (_value(data, key) or "").split(",") if x.strip()
        ]
        metadata = MovieMetadata(
            title=_value(data, "Title"),
            plot=_value(data, "Plot"),
            year=year,
            runtime_min=_runtime_minutes(_value(data, "Runtime")),
            directors=split("Director"),
            writers=split("Writer"),
            actors=split("Actors")[:6],
            release_date=release_date,
            cover_url=self._high_res_cover(_value(data, "Poster")),
            imdb_id=canonical_id,
            imdb_rating=_float(_value(data, "imdbRating")),
            primary_source="OMDb",
        )
        metadata.field_sources = {
            field: "OMDb"
            for field in (
                "title",
                "plot",
                "year",
                "runtime_min",
                "directors",
                "writers",
                "actors",
                "release_date",
                "cover_url",
                "imdb_id",
                "imdb_rating",
            )
            if getattr(metadata, field) not in (None, "", [])
        }
        return metadata

    def _high_res_cover(self, cover_url: Optional[str]) -> Optional[str]:
        if not cover_url or "SX300" not in cover_url:
            return cover_url
        for size in ("SX2000", "SX1500", "SX1200", "SX1000", "SX700", "SX500"):
            candidate = cover_url.replace("SX300", size)
            try:
                response = self.http_client.head(
                    candidate, timeout=3, raise_for_status=False
                )
                if response.status_code == 200:
                    return candidate
            except (
                HttpTimeoutError,
                HttpNetworkError,
                HttpStatusError,
                HttpDecodeError,
            ):
                continue
        return cover_url
