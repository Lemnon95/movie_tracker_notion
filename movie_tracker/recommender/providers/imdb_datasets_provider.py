# -*- coding: utf-8 -*-
"""
IMDb datasets provider for "Discovery" recommendations.

Pipeline:
1) ensure_datasets(...) -> download (or reuse cached) IMDb TSV.GZ files
2) build_index(...)     -> build light indices on disk (pickle) for fast reuse
3) discover_candidates(...) -> given anchor movies (from Notion) produce external candidates (NOT in Notion)
4) enrich_with_omdb(...) -> optional: fetch plot/cast/genres for the top-N via OMDb

Notes:
- Designed for Python 3.9
- No external deps beyond pandas/requests.
- Indices are cached under CONFIG_DIR/cache/imdb_index_v1.pkl
- Uses simple scoring: overlap on directors (3x), actors (2x), genres (1x), tie-break by IMDb rating & votes
"""

from __future__ import annotations
import os
import io
import gzip
import json
import time
import pickle
import typing as t
import requests
import pandas as pd

from movie_tracker.config import CONFIG_DIR
from movie_tracker.imdb_utils import get_movie_values
from movie_tracker.recommender.omdb_cache import fetch_omdb_cached


IMDB_BASE = "https://datasets.imdbws.com"
FILES = {
    "title_basics": "title.basics.tsv.gz",  # tconst, titleType, primaryTitle, startYear, isAdult, genres
    "title_ratings": "title.ratings.tsv.gz",  # tconst, averageRating, numVotes
    "title_principals": "title.principals.tsv.gz",  # tconst, nconst, category
    "name_basics": "name.basics.tsv.gz",  # nconst, primaryName
}
INDEX_PATH = os.path.join(CONFIG_DIR, "cache", "imdb_index_v1.pkl")


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def ensure_datasets(download_dir: str = None) -> dict:
    """
    Download IMDb dataset files if missing. Return local paths.
    """
    if download_dir is None:
        download_dir = os.path.join(CONFIG_DIR, "datasets")
    _ensure_dir(download_dir)

    paths = {}
    for key, fname in FILES.items():
        local_path = os.path.join(download_dir, fname)
        paths[key] = local_path
        if not os.path.exists(local_path):
            url = f"{IMDB_BASE}/{fname}"
            print(f"Downloading {fname} ...")
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(r.content)
            # be nice to the server
            time.sleep(1.0)
    return paths


def _read_tsv_gz(path: str, usecols: t.Optional[list] = None) -> pd.DataFrame:
    return pd.read_csv(
        path, sep="\t", compression="gzip", low_memory=False, usecols=usecols
    )


def build_index(
    paths: dict,
    min_votes: int = 5000,
    year_from: int = 1970,
    year_to: int = 2100,
    force_rebuild: bool = False,
) -> dict:
    """
    Build a light index for discovery:
    - Keep only titleType == "movie"
    - Filter by numVotes and year range
    - Build:
        * tconst -> {genres, year, rating, votes}
        * genre  -> set(tconst)
        * nconst-> set(tconst) for actors and directors separately
        * name   -> list(nconst) (lowercased) to resolve anchors' names into IDs

    Returns an index dict and saves it to INDEX_PATH for reuse.
    """
    _ensure_dir(os.path.dirname(INDEX_PATH))

    if os.path.exists(INDEX_PATH) and not force_rebuild:
        with open(INDEX_PATH, "rb") as f:
            return pickle.load(f)

    print("Building IMDb index (first time might take 1–2 minutes)...")

    # basics
    basics = _read_tsv_gz(
        paths["title_basics"],
        usecols=[
            "tconst",
            "titleType",
            "primaryTitle",
            "startYear",
            "isAdult",
            "genres",
        ],
    )
    basics = basics[basics["titleType"] == "movie"].copy()
    # normalize year
    basics["startYear"] = pd.to_numeric(basics["startYear"], errors="coerce")
    basics = basics[
        (basics["startYear"].fillna(0) >= year_from)
        & (basics["startYear"].fillna(9999) <= year_to)
    ]
    # split genres
    basics["genres"] = (
        basics["genres"]
        .fillna("")
        .apply(lambda s: [] if s in ["", "\\N"] else s.split(","))
    )

    # ratings
    ratings = _read_tsv_gz(
        paths["title_ratings"], usecols=["tconst", "averageRating", "numVotes"]
    )
    ratings["numVotes"] = (
        pd.to_numeric(ratings["numVotes"], errors="coerce").fillna(0).astype(int)
    )
    ratings["averageRating"] = pd.to_numeric(ratings["averageRating"], errors="coerce")

    df = basics.merge(ratings, on="tconst", how="left")
    df["numVotes"] = df["numVotes"].fillna(0).astype(int)
    df = df[df["numVotes"] >= int(min_votes)]

    # indices: tconst info
    tconst_info = {
        r.tconst: {
            "title": r.primaryTitle,
            "year": int(r.startYear) if pd.notna(r.startYear) else None,
            "genres": list(r.genres),
            "rating": float(r.averageRating) if pd.notna(r.averageRating) else None,
            "votes": int(r.numVotes),
        }
        for r in df.itertuples(index=False)
    }

    # genre -> set(tconst)
    genre_index = {}
    for tconst, info in tconst_info.items():
        for g in info["genres"]:
            genre_index.setdefault(g, set()).add(tconst)

    # principals
    principals = _read_tsv_gz(
        paths["title_principals"], usecols=["tconst", "nconst", "category"]
    )
    principals = principals[principals["tconst"].isin(tconst_info.keys())]

    actor_index = {}
    director_index = {}
    for r in principals.itertuples(index=False):
        if r.category == "actor" or r.category == "actress":
            actor_index.setdefault(r.nconst, set()).add(r.tconst)
        elif r.category == "director":
            director_index.setdefault(r.nconst, set()).add(r.tconst)

    # names
    names = _read_tsv_gz(paths["name_basics"], usecols=["nconst", "primaryName"])
    # normalize
    names["key"] = names["primaryName"].fillna("").str.lower().str.strip()
    # name -> list(nconst) (ambiguous names -> multiple ids)
    name_to_nconst = {}
    for r in names.itertuples(index=False):
        if not r.key:
            continue
        name_to_nconst.setdefault(r.key, []).append(r.nconst)

    index = {
        "tconst_info": tconst_info,
        "genre_index": genre_index,
        "actor_index": actor_index,
        "director_index": director_index,
        "name_to_nconst": name_to_nconst,
    }

    with open(INDEX_PATH, "wb") as f:
        pickle.dump(index, f)

    print(f"IMDb index built and cached at {INDEX_PATH}")
    return index


def _normalize_person_names(s: str) -> list:
    if not s:
        return []
    # your Notion stores comma-separated names in rich text; split & strip
    return [p.strip() for p in s.split(",") if p.strip()]


def _gather_titles_for_names(
    names: list, role: str, index: dict, limit_per_name: int = 500
) -> set:
    """
    Resolve person names to nconst(s) and collect titles from role index.
    """
    out: set = set()
    role_idx = index["director_index"] if role == "director" else index["actor_index"]
    for name in names:
        candidates = index["name_to_nconst"].get(name.lower(), [])
        for nconst in candidates[:3]:  # cap ambiguity
            titles = role_idx.get(nconst, set())
            if titles:
                # add a limited subset to avoid exploding the set
                for i, t in enumerate(titles):
                    out.add(t)
                    if i + 1 >= limit_per_name:
                        break
    return out


def discover_candidates(
    anchors: pd.DataFrame,
    all_notion_imdb_ids: t.Set[str],
    index: dict,
    top_k: int = 200,
) -> pd.DataFrame:
    """
    Produce external candidates similar to the given anchor movies.
    - anchors: DataFrame rows with columns ['imdb_id','actors','directors','genres'] (genres optional)
    - all_notion_imdb_ids: set of ttids already in Notion (exclude)
    - index: built by build_index(...)
    Returns a DataFrame with columns: ['imdb_id','title','year','genres','score','imdb_rating','imdb_votes']
    """
    if anchors.empty:
        return pd.DataFrame(columns=["imdb_id", "title"])

    tconst_info = index["tconst_info"]
    genre_index = index["genre_index"]

    # 1) Collect candidate tconsts by people overlap
    candidates: dict = {}  # tconst -> raw score
    for r in anchors.itertuples(index=False):
        actor_names = _normalize_person_names(getattr(r, "actors", "") or "")
        director_names = _normalize_person_names(getattr(r, "directors", "") or "")
        anchor_genres = [
            g.strip() for g in (getattr(r, "genres", "") or "").split(",") if g.strip()
        ]

        # directors: weight x3
        dir_titles = _gather_titles_for_names(director_names, "director", index)
        for t in dir_titles:
            candidates[t] = candidates.get(t, 0) + 3

        # actors: weight x2
        act_titles = _gather_titles_for_names(actor_names, "actor", index)
        for t in act_titles:
            candidates[t] = candidates.get(t, 0) + 2

        # genres: weight x1
        for g in anchor_genres:
            for t in genre_index.get(g, []):
                candidates[t] = candidates.get(t, 0) + 1

    # 2) Convert to DataFrame and enrich with ratings
    rows = []
    for tconst, score in candidates.items():
        info = tconst_info.get(tconst)
        if not info:
            continue
        imdb_id = tconst  # already like 'tt1234567'
        if imdb_id in all_notion_imdb_ids:
            continue  # exclude entries already in Notion
        rows.append(
            {
                "imdb_id": imdb_id,
                "title": info["title"],
                "year": info["year"],
                "genres": ", ".join(info["genres"]),
                "score": score,
                "imdb_rating": info["rating"],
                "imdb_votes": info["votes"],
            }
        )

    if not rows:
        return pd.DataFrame(columns=["imdb_id", "title"])

    cand = pd.DataFrame(rows)
    # 3) final sort: score desc, then rating and votes as tiebreakers
    cand = (
        cand.sort_values(
            by=["score", "imdb_rating", "imdb_votes"],
            ascending=[False, False, False],
            kind="mergesort",
        )
        .head(top_k)
        .reset_index(drop=True)
    )

    return cand


def enrich_with_omdb(
    df: pd.DataFrame,
    omdb_api_key: str,
    max_items: int = 50,
    verbose: bool = False,
) -> pd.DataFrame:
    """
    Enrich top candidates with OMDb using local cache.
    """
    out = df.copy()
    take = min(max_items, len(out))

    if verbose:
        print(f"OMDb enrichment: processing {take} item(s), cache-enabled.")

    actors, directors, writers, plots = [], [], [], []
    for i in range(take):
        imdb_id = out.loc[i, "imdb_id"]
        ok = False
        try:
            data = fetch_omdb_cached(imdb_id, omdb_api_key)  # <-- usa cache
            if isinstance(data, dict) and data.get("Response") == "True":
                actors.append(data.get("Actors") or "")
                directors.append(data.get("Director") or data.get("Directors") or "")
                writers.append(data.get("Writer") or data.get("Writers") or "")
                plots.append(data.get("Plot") or "")
                ok = True
            else:
                actors.append("")
                directors.append("")
                writers.append("")
                plots.append("")
        except Exception as e:
            actors.append("")
            directors.append("")
            writers.append("")
            plots.append("")
            if verbose:
                print(f"  [{i+1}/{take}] {imdb_id} -> ERROR: {e}")

        if verbose:
            title_preview = out.loc[i, "title"] if "title" in out.columns else ""
            status = "OK" if ok else "MISS"
            print(f"  [{i+1}/{take}] {imdb_id}  {title_preview} -> {status}")

        # niente sleep qui: fetch_omdb_cached gestisce rate‑limit con sleep interno
        # (se vuoi puoi aggiungere una micro‑pausa di sicurezza)

    # riempi eventuali restanti senza chiamare OMDb
    pad = len(out) - take
    if pad > 0:
        actors += [""] * pad
        directors += [""] * pad
        writers += [""] * pad
        plots += [""] * pad

    out["actors"] = actors
    out["directors"] = directors
    out["writers"] = writers
    out["plot"] = plots
    return out
