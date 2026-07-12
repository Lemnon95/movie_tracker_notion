import json
import os
from typing import Any, Tuple

from movie_tracker.notion_id import normalize_notion_database_id


CONFIG_DIR = os.path.join(os.environ["USERPROFILE"], "Documents", "Movie_Tracker")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_METADATA_REFRESH_DAYS = 150


def _normalize_refresh_days(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("METADATA_REFRESH_DAYS must be a positive integer")
    if isinstance(value, int):
        days = value
    elif isinstance(value, str) and value.strip().isdigit():
        days = int(value.strip())
    else:
        raise ValueError("METADATA_REFRESH_DAYS must be a positive integer")
    if days <= 0:
        raise ValueError("METADATA_REFRESH_DAYS must be a positive integer")
    return days


def ensure_config_file() -> str:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        print(
            "Welcome to the Movie Tracker application! Please, configure your settings."
        )
        token = input("Enter your Notion integration token: ")
        db_id = input("Enter the Notion table's URL: ")
        data_source_id = input(
            "Enter the Notion data source ID, or leave blank to detect it automatically: "
        ).strip()
        omdb_api_key = input("Enter your OMDb API key: ")
        tmdb_api_token = input("Enter your TMDB API read access token: ").strip()
        save_config(
            token,
            db_id,
            omdb_api_key,
            data_source_id=data_source_id,
            tmdb_api_token=tmdb_api_token,
        )
    return CONFIG_FILE


def load_config(path: str) -> Tuple[str, str, str, str]:
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if not all(key in config for key in ("TOKEN", "DATABASE_ID", "OMDB_API_KEY")):
        update_config(path)
        return load_config(path)

    tmdb_token_added = not config.get("TMDB_API_TOKEN")
    if tmdb_token_added:
        tmdb_token = input("Enter your TMDB API read access token: ").strip()
        if not tmdb_token:
            raise ValueError("TMDB API token cannot be empty")
        config["TMDB_API_TOKEN"] = tmdb_token

    normalized_database_id = normalize_notion_database_id(config["DATABASE_ID"])
    database_id_changed = config["DATABASE_ID"] != normalized_database_id
    config["DATABASE_ID"] = normalized_database_id

    data_source_id_missing = "DATA_SOURCE_ID" not in config
    data_source_id = config.get("DATA_SOURCE_ID") or ""
    normalized_data_source_id = (
        normalize_notion_database_id(data_source_id) if data_source_id else ""
    )
    data_source_id_changed = data_source_id != normalized_data_source_id
    config["DATA_SOURCE_ID"] = normalized_data_source_id

    refresh_days_missing = "METADATA_REFRESH_DAYS" not in config
    if refresh_days_missing:
        config["METADATA_REFRESH_DAYS"] = DEFAULT_METADATA_REFRESH_DAYS

    # Recommender support was removed. Delete obsolete settings during migration so
    # runtime configuration no longer advertises or configures ML functionality.
    obsolete_ml_settings = "ML_SETTINGS" in config
    config.pop("ML_SETTINGS", None)

    if any(
        (
            database_id_changed,
            data_source_id_changed,
            data_source_id_missing,
            tmdb_token_added,
            refresh_days_missing,
            obsolete_ml_settings,
        )
    ):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

    return (
        config["TOKEN"],
        normalized_database_id,
        normalized_data_source_id,
        config["OMDB_API_KEY"],
    )


def load_tmdb_token(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        token = json.load(f).get("TMDB_API_TOKEN", "")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("TMDB API token is missing")
    return token.strip()


def load_metadata_refresh_days(path: str) -> int:
    with open(path, "r", encoding="utf-8") as f:
        value = json.load(f).get("METADATA_REFRESH_DAYS", DEFAULT_METADATA_REFRESH_DAYS)
    return _normalize_refresh_days(value)


def save_config(
    token: str,
    db_id: str,
    omdb_api_key: str,
    path: str = None,
    data_source_id: str = "",
    tmdb_api_token: str = "",
    metadata_refresh_days: int = DEFAULT_METADATA_REFRESH_DAYS,
):
    if not all(
        isinstance(value, str) and value.strip()
        for value in (token, db_id, omdb_api_key, tmdb_api_token)
    ):
        raise ValueError("Notion, database, OMDb, and TMDB credentials are required")
    normalized_refresh_days = _normalize_refresh_days(metadata_refresh_days)
    target_path = path or CONFIG_FILE
    normalized_database_id = normalize_notion_database_id(db_id)
    normalized_data_source_id = (
        normalize_notion_database_id(data_source_id) if data_source_id else ""
    )
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "TOKEN": token,
                "DATABASE_ID": normalized_database_id,
                "DATA_SOURCE_ID": normalized_data_source_id,
                "OMDB_API_KEY": omdb_api_key,
                "TMDB_API_TOKEN": tmdb_api_token,
                "METADATA_REFRESH_DAYS": normalized_refresh_days,
            },
            f,
            ensure_ascii=False,
            indent=4,
        )
    print("Configuration saved.")


def update_config(path: str) -> Tuple[str, str, str, str]:
    existing = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            existing = loaded
    token = input("Please, enter your Notion integration token: ")
    db_id = input("Enter the Notion table's URL: ")
    data_source_id = input(
        "Enter the Notion data source ID, or leave blank to detect it automatically: "
    ).strip()
    omdb_api_key = input("Enter your OMDb API key: ")
    tmdb_api_token = input("Enter your TMDB API read access token: ").strip()
    save_config(
        token,
        db_id,
        omdb_api_key,
        path=path,
        data_source_id=data_source_id,
        tmdb_api_token=tmdb_api_token,
        metadata_refresh_days=existing.get(
            "METADATA_REFRESH_DAYS", DEFAULT_METADATA_REFRESH_DAYS
        ),
    )
    return (
        token,
        normalize_notion_database_id(db_id),
        normalize_notion_database_id(data_source_id) if data_source_id else "",
        omdb_api_key,
    )


def save_data_source_id(path: str, data_source_id: str) -> str:
    normalized = normalize_notion_database_id(data_source_id)
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)
    config["DATA_SOURCE_ID"] = normalized
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    return normalized
