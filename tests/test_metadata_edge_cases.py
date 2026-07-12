from unittest.mock import Mock

import pytest

from movie_tracker.http_client import HttpNetworkError
from movie_tracker.metadata.models import MovieMetadata
from movie_tracker.metadata.omdb_provider import OmdbProvider
from movie_tracker.metadata.provider import (
    MetadataApiError,
    MetadataNotFoundError,
    MetadataTransportError,
)
from movie_tracker.metadata.tmdb_provider import TmdbProvider
from movie_tracker.metadata.tracker_service import TrackerMetadataService


class FakeHttp:
    def __init__(self, get_responses, head_statuses=None):
        self.get_responses = list(get_responses)
        self.head_statuses = list(head_statuses or [])
        self.get_calls = []
        self.head_calls = []

    def get_json(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        response = self.get_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def head(self, url, **kwargs):
        self.head_calls.append((url, kwargs))
        response = self.head_statuses.pop(0)
        if isinstance(response, Exception):
            raise response
        return Mock(status_code=response)


def _tmdb_http(details, configuration=None, find_result=None):
    responses = [
        {"movie_results": [find_result if find_result is not None else {"id": 42}]},
        details,
    ]
    if details.get("poster_path"):
        responses.append(
            configuration
            or {
                "images": {
                    "secure_base_url": "https://img.test/",
                    "poster_sizes": ["w500"],
                }
            }
        )
    return FakeHttp(responses)


@pytest.mark.parametrize("bad_id", [True, 0, -1, "42", None])
def test_tmdb_rejects_invalid_internal_movie_ids(bad_id):
    provider = TmdbProvider("token", FakeHttp([{"movie_results": [{"id": bad_id}]}]))

    with pytest.raises(MetadataApiError, match="valid movie ID"):
        provider.get_by_imdb_id("tt1234567")


@pytest.mark.parametrize("movie_results", [None, {}, "bad", 42])
def test_tmdb_rejects_non_list_find_results(movie_results):
    with pytest.raises(MetadataApiError, match="movie_results list"):
        TmdbProvider(
            "token", FakeHttp([{"movie_results": movie_results}])
        ).get_by_imdb_id("tt1234567")


def test_tmdb_rejects_non_mapping_first_result():
    with pytest.raises(MetadataApiError, match="unexpected shape"):
        TmdbProvider("token", FakeHttp([{"movie_results": [None]}])).get_by_imdb_id(
            "tt1234567"
        )


def test_tmdb_uses_original_title_and_ignores_boolean_runtime():
    result = TmdbProvider(
        "token",
        _tmdb_http(
            {
                "title": "",
                "original_title": "Original",
                "runtime": True,
                "release_date": "2024-02-29",
                "credits": {},
            }
        ),
    ).get_by_imdb_id("1234567")

    assert result.title == "Original"
    assert result.runtime_min is None
    assert result.release_date == "2024-02-29"
    assert result.year == 2024


def test_tmdb_rejects_invalid_calendar_date_and_non_string_overview():
    result = TmdbProvider(
        "token",
        _tmdb_http(
            {
                "title": "T",
                "overview": {"bad": "shape"},
                "release_date": "2023-02-29",
                "runtime": -3,
                "credits": {},
            }
        ),
    ).get_by_imdb_id("tt1234567")

    assert result.plot is None
    assert result.release_date is None
    assert result.year is None
    assert result.runtime_min is None


def test_tmdb_cast_is_case_insensitively_deduplicated_and_limited_to_six():
    cast = [
        {"name": name}
        for name in [
            " Alice ",
            "alice",
            "Bob",
            "Cara",
            "Dan",
            "Eve",
            "Frank",
            "Grace",
        ]
    ]
    result = TmdbProvider(
        "token",
        _tmdb_http(
            {
                "title": "T",
                "credits": {"cast": cast, "crew": []},
            }
        ),
    ).get_by_imdb_id("tt1234567")

    assert result.actors == ["Alice", "Bob", "Cara", "Dan", "Eve", "Frank"]


def test_tmdb_crew_filters_jobs_and_deduplicates_names():
    crew = [
        {"name": "Director", "job": "Director"},
        {"name": " director ", "job": "Director"},
        {"name": "Writer A", "job": "Writer"},
        {"name": "Writer B", "job": "Screenplay"},
        {"name": "Writer C", "job": "Story"},
        {"name": "Producer", "job": "Producer"},
        None,
    ]
    result = TmdbProvider(
        "token",
        _tmdb_http(
            {
                "title": "T",
                "credits": {"cast": [], "crew": crew},
            }
        ),
    ).get_by_imdb_id("tt1234567")

    assert result.directors == ["Director"]
    assert result.writers == ["Writer A", "Writer B", "Writer C"]


@pytest.mark.parametrize(
    "sizes, expected_size",
    [
        (["w92", "w500", "original"], "w500"),
        (["w92", "w185"], "w185"),
        (["original"], "original"),
        (["banana", None, 123], None),
        ([], None),
    ],
)
def test_tmdb_poster_size_selection_edge_cases(sizes, expected_size):
    http = _tmdb_http(
        {"title": "T", "poster_path": "/poster.jpg", "credits": {}},
        {"images": {"secure_base_url": "https://img.test/", "poster_sizes": sizes}},
    )
    result = TmdbProvider("token", http).get_by_imdb_id("tt1234567")

    expected = (
        "https://img.test/{}/poster.jpg".format(expected_size)
        if expected_size
        else None
    )
    assert result.cover_url == expected


@pytest.mark.parametrize(
    "base_url, poster_path",
    [
        ("http://img.test/", "/p.jpg"),
        ("not-a-url", "/p.jpg"),
        ("https://img.test/", "p.jpg"),
        (None, "/p.jpg"),
    ],
)
def test_tmdb_rejects_unsafe_image_configuration(base_url, poster_path):
    http = _tmdb_http(
        {"title": "T", "poster_path": poster_path, "credits": {}},
        {"images": {"secure_base_url": base_url, "poster_sizes": ["w500"]}},
    )

    assert TmdbProvider("token", http).get_by_imdb_id("tt1234567").cover_url is None


def test_tmdb_api_failure_does_not_expose_bearer_token():
    provider = TmdbProvider(
        "very-secret-token",
        FakeHttp(
            [
                {
                    "success": False,
                    "status_message": "Invalid API key",
                }
            ]
        ),
    )

    with pytest.raises(MetadataApiError) as raised:
        provider.get_by_imdb_id("tt1234567")

    assert "very-secret-token" not in str(raised.value)


def test_tmdb_network_failure_is_a_transport_error():
    with pytest.raises(MetadataTransportError):
        TmdbProvider("token", FakeHttp([HttpNetworkError("offline")])).get_by_imdb_id(
            "tt1234567"
        )


@pytest.mark.parametrize(
    "rating, expected",
    [
        ("0", 0.0),
        ("10", 10.0),
        ("7.25", 7.25),
        ("-1", None),
        ("10.1", None),
        ("Infinity", None),
        ("-Infinity", None),
        ("abc", None),
    ],
)
def test_omdb_rating_boundaries(rating, expected):
    result = OmdbProvider(
        "key",
        FakeHttp(
            [
                {
                    "Response": "True",
                    "imdbRating": rating,
                }
            ]
        ),
    ).get_by_imdb_id("tt1234567")

    assert result.imdb_rating == expected


@pytest.mark.parametrize(
    "runtime, expected",
    [
        ("1 min", 1),
        (" 90 MIN ", 90),
        ("0 min", None),
        ("90 mins", None),
        ("1h 30min", None),
        ("", None),
        ("N/A", None),
    ],
)
def test_omdb_runtime_boundaries(runtime, expected):
    result = OmdbProvider(
        "key",
        FakeHttp(
            [
                {
                    "Response": "True",
                    "Runtime": runtime,
                }
            ]
        ),
    ).get_by_imdb_id("tt1234567")

    assert result.runtime_min == expected


@pytest.mark.parametrize(
    "year, expected",
    [
        ("1800", 1800),
        ("2026", 2026),
        ("1799", None),
        ("999", None),
        ("2020–2021", None),
        ("N/A", None),
        ("", None),
    ],
)
def test_omdb_year_boundaries(year, expected):
    result = OmdbProvider(
        "key",
        FakeHttp(
            [
                {
                    "Response": "True",
                    "Year": year,
                }
            ]
        ),
    ).get_by_imdb_id("tt1234567")

    assert result.year == expected


def test_omdb_na_and_blank_values_become_missing():
    result = OmdbProvider(
        "key",
        FakeHttp(
            [
                {
                    "Response": "True",
                    "Title": " ",
                    "Plot": "N/A",
                    "Actors": "N/A",
                    "Director": "",
                    "Writer": "N/A",
                    "Poster": "N/A",
                    "Released": "N/A",
                }
            ]
        ),
    ).get_by_imdb_id("tt1234567")

    assert result.title is None and result.plot is None
    assert result.actors == [] and result.directors == [] and result.writers == []
    assert result.cover_url is None and result.release_date is None


def test_omdb_distinguishes_not_found_from_other_api_errors():
    with pytest.raises(MetadataNotFoundError):
        OmdbProvider(
            "key",
            FakeHttp(
                [
                    {
                        "Response": "False",
                        "Error": "Movie not found!",
                    }
                ]
            ),
        ).get_by_imdb_id("tt1234567")

    with pytest.raises(MetadataApiError, match="Request limit reached"):
        OmdbProvider(
            "key",
            FakeHttp(
                [
                    {
                        "Response": "False",
                        "Error": "Request limit reached!",
                    }
                ]
            ),
        ).get_by_imdb_id("tt1234567")


def test_omdb_high_resolution_cover_uses_first_successful_candidate():
    http = FakeHttp(
        [
            {
                "Response": "True",
                "Poster": "https://img.test/poster.SX300.jpg",
            }
        ],
        head_statuses=[404, 200],
    )

    result = OmdbProvider("key", http).get_by_imdb_id("tt1234567")

    assert result.cover_url == "https://img.test/poster.SX1500.jpg"
    assert [call[0] for call in http.head_calls] == [
        "https://img.test/poster.SX2000.jpg",
        "https://img.test/poster.SX1500.jpg",
    ]


def test_omdb_high_resolution_cover_survives_head_network_errors():
    http = FakeHttp(
        [
            {
                "Response": "True",
                "Poster": "https://img.test/poster.SX300.jpg",
            }
        ],
        head_statuses=[HttpNetworkError("offline"), 200],
    )

    result = OmdbProvider("key", http).get_by_imdb_id("tt1234567")

    assert result.cover_url == "https://img.test/poster.SX1500.jpg"


def test_tracker_completes_every_missing_primary_field_and_tracks_sources():
    primary = MovieMetadata(
        title="TMDB",
        imdb_id="tt1234567",
        primary_source="TMDB",
    )
    fallback = MovieMetadata(
        title="OMDb",
        plot="Plot",
        year=2020,
        runtime_min=100,
        directors=["D"],
        writers=["W"],
        actors=["A"],
        release_date="2020-01-02",
        cover_url="https://cover.test/p.jpg",
        imdb_id="tt1234567",
        imdb_rating=8.0,
        primary_source="OMDb",
    )

    result = TrackerMetadataService(
        Mock(get_by_imdb_id=Mock(return_value=primary)),
        Mock(get_by_imdb_id=Mock(return_value=fallback)),
    ).get_by_imdb_id("tt1234567")

    assert result.title == "TMDB"
    assert result.plot == "Plot" and result.year == 2020 and result.runtime_min == 100
    assert result.directors == ["D"] and result.writers == ["W"]
    assert result.actors == ["A"] and result.release_date == "2020-01-02"
    assert result.cover_url == "https://cover.test/p.jpg" and result.imdb_rating == 8.0
    assert result.field_sources["plot"] == "OMDb"
    assert result.field_sources["imdb_rating"] == "OMDb"


def test_tracker_never_preserves_a_rogue_tmdb_rating():
    primary = MovieMetadata(
        title="T",
        imdb_id="tt1234567",
        imdb_rating=9.9,
        primary_source="TMDB",
    )
    fallback = MovieMetadata(
        imdb_id="tt1234567", imdb_rating=None, primary_source="OMDb"
    )

    result = TrackerMetadataService(
        Mock(get_by_imdb_id=Mock(return_value=primary)),
        Mock(get_by_imdb_id=Mock(return_value=fallback)),
    ).get_by_imdb_id("tt1234567")

    assert result.imdb_rating is None


def test_tracker_clears_warning_between_reused_calls():
    tmdb = Mock(
        get_by_imdb_id=Mock(
            side_effect=[
                MovieMetadata(title="One", imdb_id="tt1234567", primary_source="TMDB"),
                MovieMetadata(title="Two", imdb_id="tt7654321", primary_source="TMDB"),
            ]
        )
    )
    omdb = Mock(
        get_by_imdb_id=Mock(
            side_effect=[
                MetadataApiError("temporary failure"),
                MovieMetadata(
                    imdb_id="tt7654321", imdb_rating=8.0, primary_source="OMDb"
                ),
            ]
        )
    )
    service = TrackerMetadataService(tmdb, omdb)

    service.get_by_imdb_id("tt1234567")
    assert service.last_warning == "temporary failure"
    service.get_by_imdb_id("tt7654321")
    assert service.last_warning is None
