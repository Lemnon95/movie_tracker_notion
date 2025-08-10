import os
import json
import time
import requests
from typing import Optional

from movie_tracker.config import CONFIG_DIR

CACHE_DIR = os.path.join(CONFIG_DIR, "cache", "omdb")
os.makedirs(CACHE_DIR, exist_ok=True)

OMDB_URL = "http://www.omdbapi.com/"


def fetch_omdb_cached(
    imdb_id: str, api_key: str, sleep_s: float = 0.2
) -> Optional[dict]:
    """
    Fetches OMDb data for a given IMDb ID using a local JSON cache.
    Returns None if API fails or movie not found.
    """
    cache_file = os.path.join(CACHE_DIR, f"{imdb_id}.json")

    # 1. Read from cache if exists
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass  # corrupted cache file, re-fetch

    # 2. Fetch from OMDb
    params = {"i": imdb_id, "apikey": api_key}
    try:
        resp = requests.get(OMDB_URL, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("Response") == "True":
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                time.sleep(sleep_s)  # be polite to API
                return data
            else:
                print(f"[OMDb] No data for {imdb_id}: {data.get('Error')}")
        else:
            print(f"[OMDb] HTTP {resp.status_code} for {imdb_id}")
    except Exception as e:
        print(f"[OMDb] Error fetching {imdb_id}: {e}")

    return None
