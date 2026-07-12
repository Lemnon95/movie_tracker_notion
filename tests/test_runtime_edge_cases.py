import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from movie_tracker import config, movie_inserter


DATABASE_ID = "248104cd-477e-80fd-b757-e945d38000bd"


@pytest.mark.parametrize(
    "value, expected",
    [(1, 1), (150, 150), ("1", 1), (" 150 ", 150), (9999, 9999)],
)
def test_refresh_days_accepts_only_positive_integer_forms(value, expected):
    assert config._normalize_refresh_days(value) == expected


@pytest.mark.parametrize(
    "value",
    [True, False, 0, -1, 1.5, "1.5", "-1", "", " ", None, [], {}],
)
def test_refresh_days_rejects_ambiguous_or_non_positive_values(value):
    with pytest.raises(ValueError, match="positive integer"):
        config._normalize_refresh_days(value)


@pytest.mark.parametrize(
    "overrides",
    [
        {"token": ""},
        {"db_id": ""},
        {"omdb_api_key": ""},
        {"tmdb_api_token": ""},
        {"token": None},
    ],
)
def test_save_config_rejects_missing_credentials_without_touching_file(
    tmp_path, overrides
):
    path = tmp_path / "config.json"
    path.write_text("preserve-me", encoding="utf-8")
    arguments = {
        "token": "notion",
        "db_id": DATABASE_ID,
        "omdb_api_key": "omdb",
        "tmdb_api_token": "tmdb",
        "path": str(path),
    }
    arguments.update(overrides)

    with pytest.raises(ValueError, match="credentials are required"):
        config.save_config(**arguments)

    assert path.read_text(encoding="utf-8") == "preserve-me"


def test_incremental_tmdb_migration_rejects_blank_without_rewriting(
    monkeypatch, tmp_path
):
    path = tmp_path / "config.json"
    original = {
        "TOKEN": "notion",
        "DATABASE_ID": DATABASE_ID,
        "DATA_SOURCE_ID": "",
        "OMDB_API_KEY": "omdb",
        "ML_SETTINGS": {"obsolete": True},
    }
    serialized = json.dumps(original)
    path.write_text(serialized, encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _: "")

    with pytest.raises(ValueError, match="cannot be empty"):
        config.load_config(str(path))

    assert path.read_text(encoding="utf-8") == serialized


def test_full_reconfiguration_invalid_credentials_does_not_rewrite(
    monkeypatch, tmp_path
):
    path = tmp_path / "config.json"
    original = {"ML_SETTINGS": {"top_k": 3}, "METADATA_REFRESH_DAYS": 90}
    serialized = json.dumps(original)
    path.write_text(serialized, encoding="utf-8")
    answers = iter(["", DATABASE_ID, "", "omdb", "tmdb"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    with pytest.raises(ValueError, match="credentials are required"):
        config.update_config(str(path))

    assert path.read_text(encoding="utf-8") == serialized


def test_load_refresh_days_does_not_coerce_json_float(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"METADATA_REFRESH_DAYS": 1.5}), encoding="utf-8")

    with pytest.raises(ValueError, match="positive integer"):
        config.load_metadata_refresh_days(str(path))


def _stale_page(page_id="page", tags=None):
    return {
        "id": page_id,
        "properties": {
            "Metadata Source": {"select": {"name": "TMDB"}},
            "Metadata Synced At": {"date": {"start": "2020-01-01T00:00:00Z"}},
            "IMDb URL": {"url": "https://www.imdb.com/title/tt1234567"},
            "Tags": {"multi_select": tags if tags is not None else []},
        },
    }


def test_stale_detection_handles_missing_and_malformed_properties():
    now = datetime.now(timezone.utc)
    assert not movie_inserter.is_stale_tmdb_page({})
    assert not movie_inserter.is_stale_tmdb_page({"properties": None})
    assert movie_inserter.is_stale_tmdb_page(
        {
            "properties": {
                "Metadata Source": {"select": {"name": "TMDB"}},
                "Metadata Synced At": {"date": {"start": "not-a-date"}},
            }
        },
        now=now,
    )


def test_stale_detection_treats_exact_threshold_as_stale():
    now = datetime(2026, 7, 12, tzinfo=timezone.utc)
    threshold = now - timedelta(days=150)
    page = _stale_page()
    page["properties"]["Metadata Synced At"]["date"]["start"] = threshold.isoformat()

    assert movie_inserter.is_stale_tmdb_page(page, max_age_days=150, now=now)


def test_refresh_with_no_candidates_never_prompts_or_builds_service(monkeypatch):
    monkeypatch.setattr(movie_inserter, "query_database", Mock(return_value=[]))
    confirm = Mock(side_effect=AssertionError("must not prompt"))
    build = Mock(side_effect=AssertionError("must not build"))
    monkeypatch.setattr(movie_inserter, "_build_metadata_service", build)

    assert movie_inserter.refresh_stale_movies(
        "n",
        DATABASE_ID,
        "o",
        "t",
        confirm=confirm,
    ) == (0, 0)
    confirm.assert_not_called()
    build.assert_not_called()


def test_refresh_declined_never_builds_service(monkeypatch):
    monkeypatch.setattr(
        movie_inserter, "query_database", Mock(return_value=[_stale_page()])
    )
    build = Mock(side_effect=AssertionError("must not build"))
    monkeypatch.setattr(movie_inserter, "_build_metadata_service", build)

    assert movie_inserter.refresh_stale_movies(
        "n",
        DATABASE_ID,
        "o",
        "t",
        confirm=lambda _: "N",
    ) == (0, 0)
    build.assert_not_called()


def test_refresh_ignores_malformed_tag_items_instead_of_losing_record(
    monkeypatch, tmp_path
):
    page = _stale_page(tags=[None, {}, {"name": "Seen"}, {"name": ""}])
    monkeypatch.setattr(movie_inserter, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(movie_inserter, "query_database", Mock(return_value=[page]))
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
                "Metadata Synced At": "2026-07-12T00:00:00+00:00",
            }
        ),
    )
    update = Mock()
    monkeypatch.setattr(movie_inserter, "update_page", update)

    assert movie_inserter.refresh_stale_movies(
        "n",
        DATABASE_ID,
        "o",
        "t",
        confirm=lambda _: "y",
    ) == (1, 0)
    tags = update.call_args.args[2]["Tags"]["multi_select"]
    assert tags == [{"name": "Seen"}]
