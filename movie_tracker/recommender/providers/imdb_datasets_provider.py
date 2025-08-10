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
    include_fields: list[str] | None = None,
    force_rebuild: bool = False,
) -> dict:
    """
    Build a light IMDb index for discovery, dynamically based on include_fields.

    - Keeps only titleType == "movie"
    - Filters by numVotes and year range
    - Always builds:
        * tconst_info: tconst -> {title, year, genres(list), rating, votes}
        * genre_index: genre -> set(tconst)   (if "genres" in include_fields)
        * actor_index: nconst -> set(tconst)  (if "actors" in include_fields)
        * director_index: nconst -> set(tconst) (if "directors" in include_fields)
        * writer_index: nconst -> set(tconst) (if "writers" in include_fields)
        * name_to_nconst: name(lower) -> list(nconst)  (if any people-field requested)
        * decade_index: "1990s" -> set(tconst) (if "decade" in include_fields)
        * language_index / country_index / keyword_index: dict vuoti (placeholder)
    """
    import pickle
    import os
    import pandas as pd

    # fallback default
    if include_fields is None:
        include_fields = ["actors", "directors", "genres", "writers"]

    # --- Cache handling ---
    _ensure_dir(os.path.dirname(INDEX_PATH))
    if os.path.exists(INDEX_PATH) and not force_rebuild:
        try:
            with open(INDEX_PATH, "rb") as f:
                cached = pickle.load(f)
            meta = cached.get("_meta", {})
            # se i parametri combaciano, riusa la cache
            if (
                meta.get("min_votes") == int(min_votes)
                and meta.get("year_from") == int(year_from)
                and meta.get("year_to") == int(year_to)
                and sorted(meta.get("include_fields", [])) == sorted(include_fields)
            ):
                return cached
        except Exception:
            pass  # cache non valida, si ricostruisce

    print("Building IMDb index (first time might take 1–2 minutes)...")

    # --- basics ---
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
    basics["startYear"] = pd.to_numeric(basics["startYear"], errors="coerce")

    # filtri anno
    basics = basics[
        (basics["startYear"].fillna(0) >= year_from)
        & (basics["startYear"].fillna(9999) <= year_to)
    ]

    # split generi
    basics["genres"] = (
        basics["genres"]
        .fillna("")
        .apply(lambda s: [] if s in ["", "\\N"] else s.split(","))
    )

    # --- ratings ---
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

    # --- tconst_info ---
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

    index = {
        "tconst_info": tconst_info,
        "_meta": {
            "min_votes": int(min_votes),
            "year_from": int(year_from),
            "year_to": int(year_to),
            "include_fields": list(include_fields),
        },
    }

    # --- Inverted indexes dinamici ---

    # 1) Generi
    if "genres" in include_fields:
        genre_index: dict[str, set] = {}
        for tconst, info in tconst_info.items():
            for g in info["genres"]:
                genre_index.setdefault(g, set()).add(tconst)
        index["genre_index"] = genre_index

    # 2) Persone (actors/directors/writers) -> servono principals + names
    need_people = any(f in include_fields for f in ("actors", "directors", "writers"))
    if need_people:
        principals = _read_tsv_gz(
            paths["title_principals"], usecols=["tconst", "nconst", "category"]
        )
        principals = principals[principals["tconst"].isin(tconst_info.keys())]

        # mappa nome -> nconst (per risolvere gli anchor)
        names = _read_tsv_gz(paths["name_basics"], usecols=["nconst", "primaryName"])
        names["key"] = names["primaryName"].fillna("").str.lower().str.strip()
        name_to_nconst: dict[str, list[str]] = {}
        for r in names.itertuples(index=False):
            if not r.key:
                continue
            name_to_nconst.setdefault(r.key, []).append(r.nconst)
        index["name_to_nconst"] = name_to_nconst

        if "actors" in include_fields:
            actor_index: dict[str, set] = {}
            sub = principals[principals["category"].isin({"actor", "actress"})]
            for r in sub.itertuples(index=False):
                actor_index.setdefault(r.nconst, set()).add(r.tconst)
            index["actor_index"] = actor_index

        if "directors" in include_fields:
            director_index: dict[str, set] = {}
            sub = principals[principals["category"] == "director"]
            for r in sub.itertuples(index=False):
                director_index.setdefault(r.nconst, set()).add(r.tconst)
            index["director_index"] = director_index

        if "writers" in include_fields:
            writer_index: dict[str, set] = {}
            sub = principals[principals["category"] == "writer"]
            for r in sub.itertuples(index=False):
                writer_index.setdefault(r.nconst, set()).add(r.tconst)
            index["writer_index"] = writer_index

    # 3) Decade (derivata da year)
    if "decade" in include_fields:
        decade_index: dict[str, set] = {}
        for tconst, info in tconst_info.items():
            y = info.get("year")
            if y is None or y < 1800:
                continue
            decade = f"{(y // 10) * 10}s"  # "1990s"
            decade_index.setdefault(decade, set()).add(tconst)
        index["decade_index"] = decade_index

    # 4) Language / Country / Keywords (placeholder: non presenti nei dump IMDb standard)
    #    Rimangono indici vuoti per compatibilità con discover_candidates.
    if "language" in include_fields:
        index["language_index"] = {}
    if "country" in include_fields:
        index["country_index"] = {}
    if "keywords" in include_fields:
        index["keyword_index"] = {}

    # --- save cache ---
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
    ml_settings: dict,
    top_k: int = None,
) -> pd.DataFrame:
    """
    Produce external candidates similar to the given anchor movies.

    Parameters
    ----------
    anchors : pd.DataFrame
        Must contain ['imdb_id', plus any fields in include_fields].
    all_notion_imdb_ids : set
        Set of IMDb IDs already in Notion (exclude them).
    index : dict
        Built by build_index(...)
    ml_settings : dict
        From config.json (ML_SETTINGS)
    top_k : int, optional
        Number of candidates to return (defaults to discovery.candidate_top_k)
    """

    if anchors.empty:
        return pd.DataFrame(columns=["imdb_id", "title"])

    # Load discovery params from config
    discovery_cfg = ml_settings.get("discovery", {})
    include_fields = discovery_cfg.get(
        "include_fields", ["actors", "directors", "writers", "genres"]
    )
    weights = ml_settings.get("features", {}).get("weights", {})
    if top_k is None:
        top_k = discovery_cfg.get("candidate_top_k", 200)

    tconst_info = index["tconst_info"]
    genre_index = index.get("genre_index", {})
    keyword_index = index.get("keyword_index", {})  # If present
    language_index = index.get("language_index", {})
    country_index = index.get("country_index", {})
    decade_index = index.get("decade_index", {})

    candidates: dict = {}  # tconst -> score

    for r in anchors.itertuples(index=False):
        # --- Process each field dynamically ---
        for field in include_fields:
            value = getattr(r, field, "") or ""
            weight = weights.get(field.rstrip("s"), 1)  # fallback 1

            if field in ("actors", "directors", "writers"):
                names = _normalize_person_names(value)
                role = field[:-1]  # actor/director/writer
                for name in names:
                    titles = _gather_titles_for_names([name], role, index)
                    for t in titles:
                        candidates[t] = candidates.get(t, 0) + weight

            elif field == "genres":
                genres = [g.strip() for g in value.split(",") if g.strip()]
                for g in genres:
                    for t in genre_index.get(g, []):
                        candidates[t] = candidates.get(t, 0) + weight

            elif field == "keywords" and keyword_index:
                kws = [k.strip() for k in value.split(",") if k.strip()]
                for k in kws:
                    for t in keyword_index.get(k, []):
                        candidates[t] = candidates.get(t, 0) + weight

            elif field == "language" and language_index:
                langs = [l.strip() for l in value.split(",") if l.strip()]
                for l in langs:
                    for t in language_index.get(l, []):
                        candidates[t] = candidates.get(t, 0) + weight

            elif field == "country" and country_index:
                countries = [c.strip() for c in value.split(",") if c.strip()]
                for c in countries:
                    for t in country_index.get(c, []):
                        candidates[t] = candidates.get(t, 0) + weight

            elif field == "decade" and decade_index:
                decades = [d.strip() for d in value.split(",") if d.strip()]
                for d in decades:
                    for t in decade_index.get(d, []):
                        candidates[t] = candidates.get(t, 0) + weight

            elif field == "plot":
                # For plot, maybe no direct index, skip or implement later
                continue

    # Convert to DataFrame
    rows = []
    for tconst, score in candidates.items():
        info = tconst_info.get(tconst)
        if not info or tconst in all_notion_imdb_ids:
            continue
        rows.append(
            {
                "imdb_id": tconst,
                "title": info["title"],
                "year": info["year"],
                "genres": ", ".join(info.get("genres", [])),
                "score": score,
                "imdb_rating": info.get("rating"),
                "imdb_votes": info.get("votes"),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["imdb_id", "title"])

    cand = pd.DataFrame(rows)
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
