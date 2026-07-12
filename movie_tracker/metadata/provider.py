from typing import Protocol

from movie_tracker.metadata.models import MovieMetadata


class MetadataError(Exception):
    """Base error for metadata acquisition (never contains credentials)."""


class MetadataTransportError(MetadataError):
    pass


class MetadataApiError(MetadataError):
    pass


class MetadataNotFoundError(MetadataError):
    pass


class MovieMetadataProvider(Protocol):
    def get_by_imdb_id(self, imdb_id: str) -> MovieMetadata:
        ...
