import os
import json
from typing import Tuple, Dict, Any

CONFIG_DIR = os.path.join(os.environ["USERPROFILE"], "Documents", "Movie_Tracker")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_ML_SETTINGS = {
    # Global defaults for recommendation parameters
    "top_k": 20,  # Default number of recommendations to return
    "min_score": 7.5,  # Minimum similarity score for a movie to be included
    "features": {
        # If True, include the plot (from OMDb) in the final textual features (TF-IDF)
        # Increases "thematic" relevance but may add noise if plots are too generic.
        "use_plot": True,
        # Maximum number of words to extract from the plot (limits noise and processing time)
        "plot_max_words": 25,
        # Relative weights for tokens in the feature space (used in final ranking and discovery TF-IDF)
        "weights": {
            "director": 3,  # Increase if you want the director's "signature" to guide recommendations
            "actor": 2,  # Increase if you want recurring cast to matter more
            "writer": 2,  # Narrative tone from the writer
            "genre": 1,  # Increase for more thematic recommendations
            "plot": 1,  # Plot semantics (works well with use_plot=True)
            "keywords": 1,  # Narrative keywords (if indexed)
            "language": 1,  # Original language
            "country": 1,  # Country of production
            "decade": 1,  # E.g., "1990s" for period affinity
        },
    },
    "tfidf": {
        "ngram_range": [1, 2],  # (1,2) = unigrams + bigrams
        "min_df": 2,  # Ignore terms appearing in fewer than min_df docs
        "max_df": 0.85,  # Ignore terms appearing in >85% of docs
        "stop_words": "english",  # Stopwords for plot text (entity tokens unaffected)
    },
    "blend": {
        "w_sim": 0.70,  # Weight for TF-IDF similarity
        "w_rating": 0.20,  # Weight for IMDb rating
        "w_recency": 0.10,  # Weight for recency boost
        "recency_tau_years": 8,  # Decay constant for recency effect
    },
    "diversity": {
        "max_per_director": 2,  # Max titles per director before penalty
        "penalty": 0.15,  # Penalty intensity for extra titles
    },
    "discovery": {
        "min_votes": 5000,  # Minimum IMDb votes
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
