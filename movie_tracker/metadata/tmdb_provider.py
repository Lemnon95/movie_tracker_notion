from datetime import datetime
from typing import Any, Dict, List, Optional, Set

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
    MetadataError,
    MetadataNotFoundError,
    MetadataTransportError,
)


def _dedupe_names(
    items: Any,
    jobs: Optional[Set[str]] = None,
    limit: Optional[int] = None,
) -> List[str]:
    if not isinstance(items, list):
        return []
    result: List[str] = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        if jobs is not None and item.get("job") not in jobs:
            continue
        name = item.get("name")
        key = name.strip().casefold() if isinstance(name, str) else ""
        if key and key not in seen:
            seen.add(key)
            result.append(name.strip())
            if limit and len(result) >= limit:
                break
    return result


class TmdbProvider:
    BASE_URL = "https://api.themoviedb.org/3"
    POSTER_PREFERENCE = ["w780", "w500", "w342", "w300", "original"]

    def __init__(self, api_token: str, http_client: HttpClient = default_http_client):
        self.api_token = api_token
        self.http_client = http_client
        self._images: Optional[Dict[str, Any]] = None

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        try:
            data = self.http_client.get_json(
                self.BASE_URL + path,
                headers={
                    "Authorization": "Bearer " + self.api_token,
                    "accept": "application/json",
                },
                params=params or {},
            )
        except (HttpTimeoutError, HttpNetworkError) as exc:
            raise MetadataTransportError("Unable to contact TMDB") from exc
        except HttpStatusError as exc:
            raise MetadataApiError(
                "TMDB returned HTTP {}".format(exc.status_code)
            ) from exc
        except HttpDecodeError as exc:
            raise MetadataApiError("TMDB returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise MetadataApiError("TMDB returned an unexpected response")
        if data.get("success") is False:
            raise MetadataApiError(
                "TMDB API error: " + str(data.get("status_message") or "unknown error")
            )
        return data

    def _poster_url(self, path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        if self._images is None:
            try:
                configuration = self._get("/configuration")
            except MetadataError:
                self._images = {}
                return None
            images = configuration.get("images")
            self._images = images if isinstance(images, dict) else {}
        base = self._images.get("secure_base_url")
        sizes = self._images.get("poster_sizes") or []
        if (
            not isinstance(base, str)
            or not base.startswith("https://")
            or not isinstance(sizes, list)
        ):
            return None
        valid_sizes = [size for size in sizes if isinstance(size, str) and size]
        if not valid_sizes:
            return None
        size = next((s for s in self.POSTER_PREFERENCE if s in valid_sizes), None)
        if size is None:
            numeric = sorted(
                (int(s[1:]), s)
                for s in valid_sizes
                if s.startswith("w") and s[1:].isdigit()
            )
            if not numeric:
                return None
            size = numeric[-1][1]
        if not isinstance(path, str) or not path.startswith("/"):
            return None
        return base.rstrip("/") + "/" + size + "/" + path.lstrip("/")

    def get_by_imdb_id(self, imdb_id: str) -> MovieMetadata:
        canonical_id = normalize_imdb_id(imdb_id)
        found = self._get("/find/" + canonical_id, {"external_source": "imdb_id"})
        results = found.get("movie_results")
        if not isinstance(results, list):
            raise MetadataApiError("TMDB find response has no movie_results list")
        if not results:
            raise MetadataNotFoundError("Movie not found on TMDB")
        first_result = results[0]
        if not isinstance(first_result, dict):
            raise MetadataApiError("TMDB find result has an unexpected shape")
        tmdb_id = first_result.get("id")
        if not isinstance(tmdb_id, int) or isinstance(tmdb_id, bool) or tmdb_id <= 0:
            raise MetadataApiError("TMDB find result has no valid movie ID")
        details = self._get("/movie/" + str(tmdb_id), {"append_to_response": "credits"})
        credits = (
            details.get("credits") if isinstance(details.get("credits"), dict) else {}
        )
        date_text = details.get("release_date")
        try:
            release_date = datetime.strptime(date_text, "%Y-%m-%d").date().isoformat()
        except (TypeError, ValueError):
            release_date = None
        runtime = details.get("runtime")
        runtime = (
            runtime
            if isinstance(runtime, int)
            and not isinstance(runtime, bool)
            and runtime > 0
            else None
        )
        title = details.get("title") or details.get("original_title")
        overview = details.get("overview")
        overview = (
            overview.strip() if isinstance(overview, str) and overview.strip() else None
        )
        metadata = MovieMetadata(
            title=title.strip() if isinstance(title, str) and title.strip() else None,
            plot=overview,
            year=int(release_date[:4]) if release_date else None,
            runtime_min=runtime,
            actors=_dedupe_names(credits.get("cast", []), limit=6),
            directors=_dedupe_names(credits.get("crew", []), {"Director"}),
            writers=_dedupe_names(
                credits.get("crew", []), {"Writer", "Screenplay", "Story"}
            ),
            release_date=release_date,
            cover_url=self._poster_url(details.get("poster_path")),
            imdb_id=canonical_id,
            imdb_rating=None,
            primary_source="TMDB",
        )
        metadata.field_sources = {
            field: "TMDB"
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
            )
            if getattr(metadata, field) not in (None, "", [])
        }
        return metadata
