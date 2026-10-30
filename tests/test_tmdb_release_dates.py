import pytest

from movie_tracker.metadata.tmdb_provider import TmdbProvider
from test_metadata_providers import FakeHttp


def fetch(releases):
    http = FakeHttp(
        [
            {"movie_results": [{"id": 42}]},
            {
                "title": "Example",
                "release_date": "2025-05-20",
                "release_dates": releases,
            },
        ]
    )
    result = TmdbProvider("test-token", http).get_by_imdb_id("tt1234567")
    assert http.calls[1][1]["params"] == {"append_to_response": "credits,release_dates"}
    return result


def entry(kind, date):
    return {"type": kind, "release_date": date}


def italian(releases):
    return {"results": [{"iso_3166_1": "IT", "release_dates": releases}]}


def test_italian_theatrical_date_overrides_primary_without_changing_year():
    result = fetch(
        italian(
            [
                entry(1, "2026-10-01T00:00:00.000Z"),
                entry(2, "2026-10-15T00:00:00.000Z"),
                entry(4, "2026-10-20T00:00:00.000Z"),
                entry(3, "2026-11-05T00:00:00.000Z"),
                entry(3, "2030-01-01T00:00:00.000Z"),
            ]
        )
    )
    assert result.release_date == "2026-11-05"
    assert result.to_notion_values()["Release Date"] == "2026-11-05"
    assert result.year == 2025
    assert result.field_sources["release_date"] == "TMDB"


@pytest.mark.parametrize("kind", [2, 4, 5, 6])
def test_other_italian_distribution_used_when_theatrical_missing(kind):
    assert fetch(italian([entry(kind, "2026-11-05")])).release_date == "2026-11-05"


def test_distribution_priority_and_order_independent_earliest_date():
    result = fetch(
        italian(
            [
                entry(6, "2026-01-01"),
                entry(5, "2026-02-01"),
                entry(4, "2026-04-01"),
                entry(4, "2026-03-01"),
            ]
        )
    )
    assert result.release_date == "2026-03-01"


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        {},
        {"results": None},
        {"results": [None, "bad"]},
        {"results": [{"iso_3166_1": "US", "release_dates": [entry(3, "2026-11-05")]}]},
        italian(None),
        italian([None, "bad", {}, entry(True, "2026-11-05")]),
        italian([entry(3, "2026-02-30"), entry(3, None), entry(3, {})]),
        italian([entry(1, "2026-11-05")]),
    ],
)
def test_missing_or_invalid_italian_distribution_falls_back_to_primary(data):
    assert fetch(data).release_date == "2025-05-20"
