import json

import pytest

from movie_tracker import config


DATABASE_ID = "248104cd-477e-80fd-b757-e945d38000bd"
DATABASE_URL = (
    "https://www.notion.so/example/248104cd477e80fdb757e945d38000bd"
    "?v=148104cd477e80bb928f000ce197ddf2"
)


def test_load_config_migrates_database_url_to_canonical_id(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "tmdb-token")
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "TOKEN": "token-123",
                "DATABASE_ID": DATABASE_URL,
                "OMDB_API_KEY": "omdb-key",
                "ML_SETTINGS": {"obsolete": True},
            }
        ),
        encoding="utf-8",
    )

    token, database_id, data_source_id, omdb_key = config.load_config(str(path))

    assert (token, database_id, omdb_key) == (
        "token-123",
        DATABASE_ID,
        "omdb-key",
    )
    assert data_source_id == ""
    assert json.loads(path.read_text(encoding="utf-8"))["DATABASE_ID"] == DATABASE_ID
    assert json.loads(path.read_text(encoding="utf-8"))["DATA_SOURCE_ID"] == ""
    assert (
        json.loads(path.read_text(encoding="utf-8"))["TMDB_API_TOKEN"] == "tmdb-token"
    )
    assert "ML_SETTINGS" not in json.loads(path.read_text(encoding="utf-8"))


def test_save_config_stores_canonical_database_id(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", str(path))

    config.save_config(
        "token-123", DATABASE_URL, "omdb-key", tmdb_api_token="tmdb-token"
    )

    assert json.loads(path.read_text(encoding="utf-8"))["DATABASE_ID"] == DATABASE_ID


def test_save_config_honors_explicit_path(tmp_path):
    path = tmp_path / "custom-config.json"

    config.save_config(
        "token-123",
        DATABASE_ID,
        "omdb-key",
        path=str(path),
        data_source_id="148104cd477e80bb928f000ce197ddf2",
        tmdb_api_token="tmdb-token",
    )

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["DATA_SOURCE_ID"] == "148104cd-477e-80bb-928f-000ce197ddf2"


def test_full_reconfiguration_removes_ml_and_preserves_refresh_setting(
    monkeypatch, tmp_path
):
    path = tmp_path / "config.json"
    custom_ml = {"top_k": 7, "features": {"use_plot": False}}
    path.write_text(
        json.dumps(
            {
                "TOKEN": "old-token",
                "DATABASE_ID": DATABASE_ID,
                "DATA_SOURCE_ID": "",
                "OMDB_API_KEY": "old-omdb",
                "TMDB_API_TOKEN": "old-tmdb",
                "METADATA_REFRESH_DAYS": 91,
                "ML_SETTINGS": custom_ml,
            }
        ),
        encoding="utf-8",
    )
    answers = iter(["new-token", DATABASE_ID, "", "new-omdb", "new-tmdb"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    config.update_config(str(path))

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert "ML_SETTINGS" not in saved
    assert saved["METADATA_REFRESH_DAYS"] == 91


def test_invalid_refresh_setting_does_not_truncate_existing_config(tmp_path):
    path = tmp_path / "config.json"
    original = '{"preserve": true}'
    path.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError, match="positive integer"):
        config.save_config(
            "token",
            DATABASE_ID,
            "omdb",
            path=str(path),
            tmdb_api_token="tmdb",
            metadata_refresh_days="invalid",
        )

    assert path.read_text(encoding="utf-8") == original
