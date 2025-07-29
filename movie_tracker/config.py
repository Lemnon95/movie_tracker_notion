import os
import json
from typing import Tuple

CONFIG_DIR = os.path.join(os.environ["USERPROFILE"], "Documents", "Movie_Tracker")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def ensure_config_file() -> str:
    if not os.path.exists(CONFIG_DIR):
        os.mkdir(CONFIG_DIR)
    if not os.path.exists(CONFIG_FILE):
        print(
            "Welcome to the Movie Tracker application! Please, configure your settings."
        )
        token = input("Enter your Notion integration token: ")
        db_id = input("Enter the Notion table's URL: ")
        omdb_api_key = input("Enter your OMDb API key: ")
        save_config(token, db_id, omdb_api_key)
    return CONFIG_FILE


def load_config(path: str) -> Tuple[str, str, str]:
    with open(path, "r") as f:
        config = json.load(f)
    if (
        "TOKEN" not in config
        or "DATABASE_ID" not in config
        or "OMDB_API_KEY" not in config
    ):
        return update_config(path)
    return config["TOKEN"], config["DATABASE_ID"], config["OMDB_API_KEY"]


def save_config(token: str, db_id: str, omdb_api_key: str):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"TOKEN": token, "DATABASE_ID": db_id, "OMDB_API_KEY": omdb_api_key},
            f,
            ensure_ascii=False,
            indent=4,
        )
    print("Configuration saved.")


def update_config(path: str) -> Tuple[str, str, str]:
    token = input("Please, enter your Notion integration token: ")
    db_id = input("Enter the Notion table's URL: ")
    omdb_api_key = input("Enter your OMDb API key: ")
    save_config(token, db_id, omdb_api_key)
    return token, db_id, omdb_api_key
