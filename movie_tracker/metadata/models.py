from dataclasses import dataclass, field
from typing import Dict, List, Optional

from movie_tracker.imdb_id import build_imdb_url, normalize_imdb_id


@dataclass
class MovieMetadata:
    title: Optional[str] = None
    plot: Optional[str] = None
    year: Optional[int] = None
    runtime_min: Optional[int] = None
    directors: List[str] = field(default_factory=list)
    writers: List[str] = field(default_factory=list)
    actors: List[str] = field(default_factory=list)
    release_date: Optional[str] = None
    cover_url: Optional[str] = None
    imdb_id: Optional[str] = None
    imdb_rating: Optional[float] = None
    primary_source: Optional[str] = None
    field_sources: Dict[str, str] = field(default_factory=dict)

    @property
    def imdb_url(self) -> Optional[str]:
        return build_imdb_url(self.imdb_id) if self.imdb_id else None

    def canonicalize(self) -> "MovieMetadata":
        if self.imdb_id:
            self.imdb_id = normalize_imdb_id(self.imdb_id)
        return self

    def to_notion_values(self) -> dict:
        return {
            "Title": self.title,
            "Plot": self.plot,
            "Year": self.year,
            "Runtime": self.runtime_min,
            "Directors": ", ".join(self.directors) or None,
            "Writers": ", ".join(self.writers) or None,
            "Actors": ", ".join(self.actors) or None,
            "Release Date": self.release_date,
            "Cover": self.cover_url,
            "IMDb URL": self.imdb_url,
            "Rating - IMDb": self.imdb_rating,
        }
