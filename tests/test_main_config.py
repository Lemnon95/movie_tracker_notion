from unittest.mock import Mock

from movie_tracker import main


def test_runtime_config_resolves_and_persists_missing_data_source(monkeypatch):
    monkeypatch.setattr(
        main,
        "load_config",
        Mock(return_value=("token", "database-id", "", "omdb-key")),
    )
    monkeypatch.setattr(main, "load_tmdb_token", Mock(return_value="tmdb-token"))
    monkeypatch.setattr(main, "load_metadata_refresh_days", Mock(return_value=150))
    monkeypatch.setattr(
        main, "resolve_data_source_id", Mock(return_value="data-source-id")
    )
    save = Mock(return_value="data-source-id")
    monkeypatch.setattr(main, "save_data_source_id", save)

    result = main._load_runtime_config("config.json")

    assert result == (
        "token",
        "database-id",
        "data-source-id",
        "omdb-key",
        "tmdb-token",
        150,
    )
    save.assert_called_once_with("config.json", "data-source-id")


def test_runtime_config_keeps_resolved_data_source_without_rewriting(monkeypatch):
    loaded = ("token", "database-id", "data-source-id", "omdb-key")
    monkeypatch.setattr(main, "load_config", Mock(return_value=loaded))
    monkeypatch.setattr(main, "load_tmdb_token", Mock(return_value="tmdb-token"))
    monkeypatch.setattr(main, "load_metadata_refresh_days", Mock(return_value=150))
    monkeypatch.setattr(
        main, "resolve_data_source_id", Mock(return_value="data-source-id")
    )
    save = Mock()
    monkeypatch.setattr(main, "save_data_source_id", save)

    assert main._load_runtime_config("config.json") == (
        "token",
        "database-id",
        "data-source-id",
        "omdb-key",
        "tmdb-token",
        150,
    )
    save.assert_not_called()
