from datetime import datetime, timezone
from typing import Optional

from movie_tracker.metadata.models import MovieMetadata
from movie_tracker.metadata.provider import MetadataError, MovieMetadataProvider


class CombinedMetadataError(MetadataError):
    pass


class TrackerMetadataService:
    def __init__(self, tmdb: MovieMetadataProvider, omdb: MovieMetadataProvider):
        self.tmdb = tmdb
        self.omdb = omdb
        self.last_warning: Optional[str] = None

    def get_by_imdb_id(self, imdb_id: str) -> MovieMetadata:
        self.last_warning = None
        primary = None
        tmdb_error = None
        try:
            primary = self.tmdb.get_by_imdb_id(imdb_id)
        except MetadataError as exc:
            tmdb_error = exc
        try:
            fallback = self.omdb.get_by_imdb_id(imdb_id)
        except MetadataError as omdb_error:
            if primary is not None:
                self.last_warning = str(omdb_error)
                return primary
            raise CombinedMetadataError(
                "Both metadata providers failed (TMDB: {}; OMDb: {})".format(
                    tmdb_error, omdb_error
                )
            ) from omdb_error
        if primary is None:
            return fallback
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
        ):
            if getattr(primary, field) in (None, "", []):
                setattr(primary, field, getattr(fallback, field))
                if getattr(primary, field) not in (None, "", []):
                    primary.field_sources[field] = "OMDb"
        primary.imdb_rating = fallback.imdb_rating
        if fallback.imdb_rating is not None:
            primary.field_sources["imdb_rating"] = "OMDb"
        return primary

    @staticmethod
    def synced_at() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
