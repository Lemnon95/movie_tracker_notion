from datetime import datetime, timezone
from unittest.mock import Mock

from movie_tracker import movie_inserter
from movie_tracker.notion_api import NotionApiError


def _page(source="TMDB", synced="2025-01-01T00:00:00+00:00"):
    return {
        "id": "page-1",
        "properties": {
            "Metadata Source": {"select": {"name": source}},
            "Metadata Synced At": {"date": {"start": synced}},
            "IMDb URL": {"url": "https://www.imdb.com/title/tt1234567"},
            "Tags": {"multi_select": [{"name": "Seen"}, {"name": "Favorite"}]},
            "My Score": {"number": 9.0},
            "Last Seen": {"date": {"start": "2026-01-02"}},
        },
    }


def test_stale_selection_requires_tmdb_and_age_threshold():
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert movie_inserter.is_stale_tmdb_page(_page(), 150, now)
    assert not movie_inserter.is_stale_tmdb_page(_page(source="OMDb"), 150, now)
    assert not movie_inserter.is_stale_tmdb_page(
        _page(synced="2026-06-01T00:00:00Z"), 150, now
    )


def test_refresh_preserves_personal_fields_and_patches_after_fetch(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(movie_inserter, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(movie_inserter, "query_database", Mock(return_value=[_page()]))
    service = object()
    build_service = Mock(return_value=service)
    monkeypatch.setattr(movie_inserter, "_build_metadata_service", build_service)
    metadata_values = Mock(
        return_value={
            "Title": "T",
            "Plot": None,
            "Year": 2020,
            "Runtime": 100,
            "Directors": "D",
            "Writers": "W",
            "Actors": "A",
            "Release Date": None,
            "Cover": None,
            "IMDb URL": "https://www.imdb.com/title/tt1234567",
            "Rating - IMDb": 8.0,
            "Metadata Source": "TMDB",
            "Metadata Synced At": "2026-07-01T00:00:00+00:00",
        }
    )
    monkeypatch.setattr(movie_inserter, "_metadata_values", metadata_values)
    update = Mock()
    monkeypatch.setattr(movie_inserter, "update_page", update)

    assert movie_inserter.refresh_stale_movies(
        "n", "248104cd-477e-80fd-b757-e945d38000bd", "o", "t", confirm=lambda _: "y"
    ) == (1, 0)
    properties = update.call_args.args[2]
    assert [x["name"] for x in properties["Tags"]["multi_select"]] == [
        "Seen",
        "Favorite",
    ]
    assert properties["My Score"]["number"] == 9.0
    assert properties["Last Seen"]["date"]["start"] == "2026-01-02"
    assert properties["Metadata Synced At"]["date"]["start"].startswith("2026-07-01")
    build_service.assert_called_once_with("o", "t")
    assert metadata_values.call_args.kwargs["service"] is service


def test_refresh_counts_failed_patch_without_reporting_success(monkeypatch, tmp_path):
    monkeypatch.setattr(movie_inserter, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(movie_inserter, "query_database", Mock(return_value=[_page()]))
    monkeypatch.setattr(
        movie_inserter, "_build_metadata_service", Mock(return_value=object())
    )
    monkeypatch.setattr(
        movie_inserter,
        "_metadata_values",
        Mock(
            return_value={
                "Title": "T",
                "Plot": None,
                "Year": None,
                "Runtime": None,
                "Directors": None,
                "Writers": None,
                "Actors": None,
                "Release Date": None,
                "Cover": None,
                "IMDb URL": "https://www.imdb.com/title/tt1234567",
                "Rating - IMDb": None,
                "Metadata Source": "TMDB",
                "Metadata Synced At": "2026-07-01T00:00:00+00:00",
            }
        ),
    )
    update = Mock(side_effect=NotionApiError("patch failed"))
    monkeypatch.setattr(movie_inserter, "update_page", update)

    result = movie_inserter.refresh_stale_movies(
        "n",
        "248104cd-477e-80fd-b757-e945d38000bd",
        "o",
        "t",
        confirm=lambda _: "y",
    )

    assert result == (0, 1)
    log = (tmp_path / "logs" / "update_log.txt").read_text(encoding="utf-8")
    assert "Updated 0, Failed 1" in log
