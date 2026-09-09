from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from movie_tracker import main, movie_inserter
from movie_tracker.metadata import MetadataError
from movie_tracker.metadata.models import MovieMetadata
from movie_tracker.notion_api import NotionApiError


DATA_SOURCE_ID = "248104cd-477e-80fd-b757-e945d38000bd"


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "requests.sessions.Session.request",
        Mock(side_effect=AssertionError("Tests must stay offline")),
    )
    monkeypatch.setattr(main, "ensure_config_file", lambda: "test-config.json")
    monkeypatch.setattr(
        main,
        "_load_runtime_config",
        lambda _: ("n", "database", DATA_SOURCE_ID, "o", "t", 150),
    )
    monkeypatch.setattr(movie_inserter, "CONFIG_DIR", str(tmp_path))
    inputs = Mock(return_value="6")
    monkeypatch.setattr("builtins.input", inputs)
    menu = Mock()
    monkeypatch.setattr(main, "print_menu", menu)
    return inputs, menu


def _page(page_id, source="TMDB", synced="2020-01-01T00:00:00Z"):
    return {
        "id": page_id,
        "properties": {
            "Metadata Source": {"select": {"name": source}},
            "Metadata Synced At": {"date": {"start": synced}},
            "IMDb URL": {"url": "https://www.imdb.com/title/tt2543164"},
            "Tags": {"multi_select": [{"name": "Seen"}, {"name": "Favorite"}]},
            "My Score": {"number": 9.0},
            "Last Seen": {"date": {"start": "2026-01-02"}},
        },
    }


def test_startup_refreshes_only_stale_tmdb_before_menu_without_prompt(app, monkeypatch):
    inputs, menu = app
    recent = datetime.now(timezone.utc).isoformat()
    query = Mock(
        return_value=[
            _page("stale"),
            _page("fresh", synced=recent),
            _page("omdb", source="OMDb"),
        ]
    )
    monkeypatch.setattr(movie_inserter, "query_database", query)
    service = Mock()
    service.get_by_imdb_id.return_value = MovieMetadata(
        title="Arrival", imdb_id="tt2543164", primary_source="TMDB"
    )
    service.last_warning = None
    service.synced_at.return_value = recent
    monkeypatch.setattr(movie_inserter, "_build_metadata_service", lambda *_: service)

    def patch_before_menu(*_):
        menu.assert_not_called()

    update = Mock(side_effect=patch_before_menu)
    monkeypatch.setattr(movie_inserter, "update_page", update)

    main.main()

    query.assert_called_once_with("n", DATA_SOURCE_ID)
    update.assert_called_once()
    assert update.call_args.args[1] == "stale"
    props = update.call_args.args[2]
    assert props["Tags"]["multi_select"] == [{"name": "Seen"}, {"name": "Favorite"}]
    assert props["My Score"]["number"] == 9.0
    assert props["Last Seen"]["date"]["start"] == "2026-01-02"
    assert props["Metadata Synced At"]["date"]["start"] == recent
    inputs.assert_called_once_with("Enter your choice: ")
    menu.assert_called_once()


@pytest.mark.parametrize(
    "error", [NotionApiError("Notion unavailable"), OSError("Log unavailable")]
)
def test_startup_refresh_failure_leaves_menu_available(app, monkeypatch, capsys, error):
    inputs, menu = app
    refresh = Mock(side_effect=error)
    monkeypatch.setattr(main, "refresh_stale_movies", refresh)

    main.main()

    refresh.assert_called_once_with(
        "n", DATA_SOURCE_ID, "o", "t", max_age_days=150, confirm=None
    )
    menu.assert_called_once()
    inputs.assert_called_once_with("Enter your choice: ")
    assert "Unable to refresh" in capsys.readouterr().out


def test_startup_continues_after_one_failed_movie(app, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        movie_inserter,
        "query_database",
        Mock(return_value=[_page("failed"), _page("success")]),
    )
    service = Mock()
    service.last_warning = None
    service.get_by_imdb_id.side_effect = [
        MetadataError("Metadata unavailable"),
        MovieMetadata(title="Arrival", imdb_id="tt2543164", primary_source="TMDB"),
    ]
    service.synced_at.return_value = "2026-09-09T00:00:00+00:00"
    monkeypatch.setattr(movie_inserter, "_build_metadata_service", lambda *_: service)
    update = Mock()
    monkeypatch.setattr(movie_inserter, "update_page", update)

    main.main()

    update.assert_called_once()
    assert update.call_args.args[1] == "success"
    assert "Updated 1, Failed 1" in capsys.readouterr().out
    assert "Failed failed: Metadata unavailable" in (
        tmp_path / "logs" / "update_log.txt"
    ).read_text(encoding="utf-8")


def test_startup_with_no_stale_movies_does_not_fetch_metadata(app, monkeypatch):
    monkeypatch.setattr(movie_inserter, "query_database", Mock(return_value=[]))
    build = Mock()
    monkeypatch.setattr(movie_inserter, "_build_metadata_service", build)

    main.main()

    build.assert_not_called()
    app[1].assert_called_once()


def test_manual_refresh_still_requests_confirmation(app, monkeypatch):
    app[0].side_effect = ["4", "n", "6"]
    query = Mock(side_effect=[[], [_page("stale")]])
    monkeypatch.setattr(movie_inserter, "query_database", query)
    build = Mock()
    monkeypatch.setattr(movie_inserter, "_build_metadata_service", build)

    main.main()

    assert query.call_count == 2
    app[0].assert_any_call("Refresh them now? y/n: ")
    build.assert_not_called()
