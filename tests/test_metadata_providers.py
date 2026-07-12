from unittest.mock import Mock

import pytest

from movie_tracker.http_client import (
    HttpDecodeError,
    HttpNetworkError,
    HttpStatusError,
)
from movie_tracker.metadata.models import MovieMetadata
from movie_tracker.metadata.omdb_provider import OmdbProvider
from movie_tracker.metadata.provider import (
    MetadataApiError,
    MetadataNotFoundError,
)
from movie_tracker.metadata.tmdb_provider import TmdbProvider
from movie_tracker.metadata.tracker_service import (
    CombinedMetadataError,
    TrackerMetadataService,
)


class FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get_json(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_tmdb_maps_find_details_credits_and_dynamic_poster():
    http = FakeHttp(
        [
            {"movie_results": [{"id": 42}]},
            {
                "title": "Localized",
                "overview": "Plot",
                "release_date": "2020-02-03",
                "runtime": 123,
                "poster_path": "/p.jpg",
                "credits": {
                    "cast": [{"name": "A"}, {"name": "A"}, {"name": "B"}],
                    "crew": [
                        {"name": "D", "job": "Director"},
                        {"name": "W", "job": "Story"},
                    ],
                },
            },
            {
                "images": {
                    "secure_base_url": "https://img.test/",
                    "poster_sizes": ["w342", "original"],
                }
            },
        ]
    )
    result = TmdbProvider("secret", http).get_by_imdb_id("tt1234567")
    assert (result.title, result.year, result.runtime_min) == ("Localized", 2020, 123)
    assert result.actors == ["A", "B"]
    assert result.directors == ["D"] and result.writers == ["W"]
    assert result.cover_url == "https://img.test/w342/p.jpg"
    assert result.imdb_rating is None


def test_tmdb_no_match_is_typed():
    with pytest.raises(MetadataNotFoundError):
        TmdbProvider("secret", FakeHttp([{"movie_results": []}])).get_by_imdb_id(
            "tt1234567"
        )


def test_tmdb_configuration_failure_keeps_primary_metadata_for_omdb_completion():
    http = FakeHttp(
        [
            {"movie_results": [{"id": 42}]},
            {
                "title": "TMDB title",
                "overview": "TMDB plot",
                "release_date": "2020-02-03",
                "runtime": 123,
                "poster_path": "/poster.jpg",
                "credits": {},
            },
            HttpNetworkError("configuration unavailable"),
        ]
    )
    tmdb_metadata = TmdbProvider("secret", http).get_by_imdb_id("tt1234567")
    omdb_metadata = MovieMetadata(
        imdb_id="tt1234567",
        cover_url="https://omdb.test/poster.jpg",
        imdb_rating=8.0,
        primary_source="OMDb",
    )

    result = TrackerMetadataService(
        Mock(get_by_imdb_id=Mock(return_value=tmdb_metadata)),
        Mock(get_by_imdb_id=Mock(return_value=omdb_metadata)),
    ).get_by_imdb_id("tt1234567")

    assert result.title == "TMDB title"
    assert result.plot == "TMDB plot"
    assert result.cover_url == "https://omdb.test/poster.jpg"
    assert result.primary_source == "TMDB"


def test_tmdb_ignores_malformed_credit_items_without_generic_exception():
    http = FakeHttp(
        [
            {"movie_results": [{"id": 42}]},
            {
                "title": "T",
                "release_date": "bad",
                "runtime": "bad",
                "credits": {
                    "cast": [None, "invalid", {"name": "Actor"}],
                    "crew": "invalid",
                },
            },
        ]
    )

    result = TmdbProvider("secret", http).get_by_imdb_id("tt1234567")

    assert result.actors == ["Actor"]
    assert result.directors == []
    assert result.writers == []
    assert result.year is None and result.runtime_min is None


@pytest.mark.parametrize(
    "error, message",
    [
        (HttpStatusError(503, "https://tmdb.test"), "HTTP 503"),
        (HttpDecodeError("bad JSON"), "invalid JSON"),
    ],
)
def test_tmdb_distinguishes_http_and_decode_errors(error, message):
    with pytest.raises(MetadataApiError, match=message):
        TmdbProvider("secret", FakeHttp([error])).get_by_imdb_id("tt1234567")


def test_omdb_rejects_malformed_runtime_rating_and_response_shape():
    malformed = OmdbProvider(
        "key",
        FakeHttp(
            [
                {
                    "Response": "True",
                    "Runtime": "90 bananas",
                    "imdbRating": "NaN",
                    "Year": "2",
                }
            ]
        ),
    ).get_by_imdb_id("tt1234567")
    assert malformed.runtime_min is None
    assert malformed.imdb_rating is None
    assert malformed.year is None

    with pytest.raises(MetadataApiError, match="unexpected response"):
        OmdbProvider(
            "key", FakeHttp([{"Title": "Missing response flag"}])
        ).get_by_imdb_id("tt1234567")


@pytest.mark.parametrize(
    "error, message",
    [
        (HttpStatusError(500, "https://omdb.test"), "HTTP 500"),
        (HttpDecodeError("bad JSON"), "invalid JSON"),
    ],
)
def test_omdb_distinguishes_http_and_decode_errors(error, message):
    with pytest.raises(MetadataApiError, match=message):
        OmdbProvider("key", FakeHttp([error])).get_by_imdb_id("tt1234567")


def test_tmdb_image_configuration_is_reused_across_movies():
    http = FakeHttp(
        [
            {"movie_results": [{"id": 1}]},
            {"title": "One", "poster_path": "/one.jpg", "credits": {}},
            {
                "images": {
                    "secure_base_url": "https://img.test/",
                    "poster_sizes": ["w500"],
                }
            },
            {"movie_results": [{"id": 2}]},
            {"title": "Two", "poster_path": "/two.jpg", "credits": {}},
        ]
    )
    provider = TmdbProvider("secret", http)

    provider.get_by_imdb_id("tt1234567")
    provider.get_by_imdb_id("tt7654321")

    assert sum(url.endswith("/configuration") for url, _ in http.calls) == 1


def test_tracker_merges_omdb_but_rating_is_never_tmdb():
    tmdb = Mock(
        get_by_imdb_id=Mock(
            return_value=MovieMetadata(
                title="T", imdb_id="tt1234567", primary_source="TMDB"
            )
        )
    )
    omdb = Mock(
        get_by_imdb_id=Mock(
            return_value=MovieMetadata(
                plot="P", imdb_id="tt1234567", imdb_rating=8.1, primary_source="OMDb"
            )
        )
    )
    result = TrackerMetadataService(tmdb, omdb).get_by_imdb_id("tt1234567")
    assert (result.title, result.plot, result.imdb_rating, result.primary_source) == (
        "T",
        "P",
        8.1,
        "TMDB",
    )


def test_tracker_uses_complete_omdb_fallback_when_tmdb_fails():
    tmdb = Mock(get_by_imdb_id=Mock(side_effect=MetadataApiError("tmdb failed")))
    fallback = MovieMetadata(
        title="OMDb title",
        plot="OMDb plot",
        imdb_id="tt1234567",
        imdb_rating=7.5,
        primary_source="OMDb",
    )
    omdb = Mock(get_by_imdb_id=Mock(return_value=fallback))

    result = TrackerMetadataService(tmdb, omdb).get_by_imdb_id("tt1234567")

    assert result is fallback
    assert result.primary_source == "OMDb"


def test_tracker_keeps_tmdb_and_missing_rating_when_omdb_fails():
    primary = MovieMetadata(
        title="TMDB title",
        imdb_id="tt1234567",
        primary_source="TMDB",
    )
    service = TrackerMetadataService(
        Mock(get_by_imdb_id=Mock(return_value=primary)),
        Mock(get_by_imdb_id=Mock(side_effect=MetadataApiError("omdb failed"))),
    )

    result = service.get_by_imdb_id("tt1234567")

    assert result is primary
    assert result.imdb_rating is None
    assert service.last_warning == "omdb failed"


def test_tracker_reports_both_failures_without_credentials():
    tmdb = Mock(get_by_imdb_id=Mock(side_effect=MetadataApiError("tmdb failed")))
    omdb = Mock(get_by_imdb_id=Mock(side_effect=MetadataApiError("omdb failed")))
    with pytest.raises(
        CombinedMetadataError, match="TMDB: tmdb failed; OMDb: omdb failed"
    ):
        TrackerMetadataService(tmdb, omdb).get_by_imdb_id("tt1234567")
