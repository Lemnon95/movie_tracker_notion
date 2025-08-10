import os
import json
from typing import Tuple, Dict, Any

CONFIG_DIR = os.path.join(os.environ["USERPROFILE"], "Documents", "Movie_Tracker")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_ML_SETTINGS = {
    "features": {
        "use_plot": True,
        "plot_max_words": 25,
        "weights": {
            "director": 3,
            "actor": 2,
            "writer": 2,
            "genre": 1,
            "plot": 1,
            "keywords": 1,
            "language": 1,
            "country": 1,
            "decade": 1,
        },
    },
    "tfidf": {
        "ngram_range": [1, 2],
        "min_df": 2,
        "max_df": 0.85,
        "stop_words": "english",
    },
    "blend": {
        "w_sim": 0.70,
        "w_rating": 0.20,
        "w_recency": 0.10,
        "recency_tau_years": 8,
    },
    "diversity": {"max_per_director": 2, "penalty": 0.15},
    "discovery": {
        "min_votes": 5000,
        "year_from": 1970,
        "year_to": 2100,
        "candidate_top_k": 200,
        "eligibility_quantile": 0.60,
        "quality_min_rating": 6.5,
        "quality_min_votes": 2000,
        "enrich_budget": {"per_top_k": 7, "per_anchor": 5, "min": 30},
        "include_fields": [
            "actors",
            "directors",
            "writers",
            "genres",
            "plot",
            "keywords",
            "language",
            "country",
            "decade",
        ],
    },
}


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


def load_config(path: str) -> Tuple[str, str, str, Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if (
        ("TOKEN" not in config)
        or ("DATABASE_ID" not in config)
        or ("OMDB_API_KEY" not in config)
    ):
        token, db_id, omdb_api_key = update_config(path)
        with open(path, "r", encoding="utf-8") as f2:
            cfg2 = json.load(f2)
        ml_settings = cfg2.get("ML_SETTINGS", DEFAULT_ML_SETTINGS)
        return token, db_id, omdb_api_key, ml_settings

    if "ML_SETTINGS" not in config:
        config["ML_SETTINGS"] = DEFAULT_ML_SETTINGS
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

    ml_settings = config.get("ML_SETTINGS", DEFAULT_ML_SETTINGS)
    return config["TOKEN"], config["DATABASE_ID"], config["OMDB_API_KEY"], ml_settings


def save_config(token: str, db_id: str, omdb_api_key: str):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "TOKEN": token,
                "DATABASE_ID": db_id,
                "OMDB_API_KEY": omdb_api_key,
                "ML_SETTINGS": DEFAULT_ML_SETTINGS,
            },
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
