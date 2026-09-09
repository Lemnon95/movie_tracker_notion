from unittest.mock import Mock

import pytest

from movie_tracker import movie_inserter
from movie_tracker.metadata import MetadataError
from movie_tracker.metadata.models import MovieMetadata
from movie_tracker.metadata.provider import MetadataApiError
from movie_tracker.metadata.tracker_service import TrackerMetadataService


DATA_SOURCE_ID = "248104cd-477e-80fd-b757-e945d38000bd"


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    monkeypatch.setattr(
        "requests.sessions.Session.request",
        Mock(side_effect=AssertionError("Tests must stay offline")),
    )


@pytest.mark.parametrize("title", [None, "", " \t", "N/A", 123])
@pytest.mark.parametrize("operation", ["insert", "update", "refresh"])
def test_titleless_metadata_never_writes_to_notion(
    monkeypatch, tmp_path, notion_page, title, operation
):
    service = Mock()
    service.get_by_imdb_id.return_value = MovieMetadata(
        title=title, imdb_id="tt2543164", primary_source="TMDB"
    )
    service.last_warning = None
    monkeypatch.setattr(movie_inserter, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(movie_inserter, "_build_metadata_service", lambda *_: service)
    notion_page["properties"]["Metadata Source"] = {"select": {"name": "TMDB"}}
    monkeypatch.setattr(
        movie_inserter, "query_database", Mock(return_value=[notion_page])
    )
    create = Mock()
    update = Mock()
    monkeypatch.setattr(movie_inserter, "create_page", create)
    monkeypatch.setattr(movie_inserter, "update_page", update)
    answers = iter(["2543164 ", "0", "y"] if operation == "insert" else [""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    if operation == "insert":
        with pytest.raises(MetadataError, match="title"):
            movie_inserter.insert_movie("n", DATA_SOURCE_ID, "o", "t")
    elif operation == "update":
        movie_inserter.update_movie("n", DATA_SOURCE_ID, "o", "t")
    else:
        assert movie_inserter.refresh_stale_movies(
            "n", DATA_SOURCE_ID, "o", "t", confirm=lambda _: "y"
        ) == (0, 1)

    create.assert_not_called()
    update.assert_not_called()
    service.synced_at.assert_not_called()
    if operation != "insert":
        log = (tmp_path / "logs" / "update_log.txt").read_text(encoding="utf-8")
        assert "title" in log


def test_omdb_can_complete_missing_tmdb_title_before_validation(monkeypatch):
    tmdb = Mock(
        get_by_imdb_id=Mock(
            return_value=MovieMetadata(
                imdb_id="tt2543164", primary_source="TMDB", plot="TMDB plot"
            )
        )
    )
    omdb = Mock(
        get_by_imdb_id=Mock(
            return_value=MovieMetadata(
                imdb_id="tt2543164", title="Arrival", primary_source="OMDb"
            )
        )
    )
    service = TrackerMetadataService(tmdb, omdb)

    values = movie_inserter._metadata_values("tt2543164", "o", "t", service)

    assert values["Title"] == "Arrival"
    assert values["Plot"] == "TMDB plot"
    assert values["Metadata Synced At"]


def test_titleless_primary_is_rejected_when_omdb_is_unavailable():
    service = TrackerMetadataService(
        Mock(get_by_imdb_id=Mock(return_value=MovieMetadata(imdb_id="tt2543164"))),
        Mock(get_by_imdb_id=Mock(side_effect=MetadataApiError("OMDb unavailable"))),
    )

    with pytest.raises(MetadataError, match="title"):
        movie_inserter._metadata_values("tt2543164", "o", "t", service)
