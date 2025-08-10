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
    ml_settings: Dict[str, Any],
    top_k: int = None,
) -> pd.DataFrame:
    """
    Discovery con TF-IDF:
    1) raccoglie candidati via inverted indexes (actors/directors/writers/genres/decade, ecc.)
    2) costruisce documenti testuali tokenizzati per anchor e candidati
    3) calcola TF-IDF su (anchors + candidati) e usa la cosine similarity media verso gli anchor come score
    4) ordina per tfidf_sim (poi rating, votes) e ritorna i top_k
    """
    import numpy as np
    import pandas as pd
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    if anchors.empty:
        return pd.DataFrame(columns=["imdb_id", "title"])

    # --- config ---
    discovery_cfg = ml_settings.get("discovery", {})
    include_fields = discovery_cfg.get(
        "include_fields", ["actors", "directors", "writers", "genres", "decade"]
    )
    weights = ml_settings.get("features", {}).get("weights", {})
    tfidf_cfg = ml_settings.get(
        "tfidf",
        {"ngram_range": [1, 2], "min_df": 2, "max_df": 0.85, "stop_words": "english"},
    )
    if top_k is None:
        top_k = int(discovery_cfg.get("candidate_top_k", 200))

    # --- helpers ---
    def _resolve_names_to_nconsts(names: list[str]) -> list[str]:
        # usa la mappa name->nconst; nomi ambigui possono mappare a più nconst (li includiamo tutti)
        out: list[str] = []
        name_map = index.get("name_to_nconst", {})
        for nm in names:
            key = (nm or "").strip().lower()
            out.extend(name_map.get(key, []))
        # dedup preservando ordine
        seen = set()
        res = []
        for x in out:
            if x not in seen:
                seen.add(x)
                res.append(x)
        return res

    def _split_csv(s: str) -> list[str]:
        return [x.strip() for x in (s or "").split(",") if x.strip()]

    def _decade_token(year: t.Optional[int]) -> t.Optional[str]:
        if year is None or year < 1800:
            return None
        return f"{(int(year)//10)*10}s"  # "1990s"

    def _repeat(tokens: list[str], w: int) -> list[str]:
        w = max(1, int(w))
        # ripetere i token "emula" un peso nel TF (funziona bene con TF-IDF)
        return [tok for tok in tokens for _ in range(w)]

    # --- 1) raccogli candidati via inverted indexes (come prima, ma generico) ---
    tconst_info = index["tconst_info"]

    # indici disponibili
    inv = {
        "genres": index.get("genre_index", {}),
        "actors": index.get("actor_index", {}),
        "directors": index.get("director_index", {}),
        "writers": index.get("writer_index", {}),
        "decade": index.get("decade_index", {}),
        "language": index.get("language_index", {}),  # placeholder (vuoto di solito)
        "country": index.get("country_index", {}),  # placeholder
        "keywords": index.get("keyword_index", {}),  # placeholder
    }

    # 1a) seed dei candidati basato su match ponderati
    raw_scores: dict[str, float] = {}
    for r in anchors.itertuples(index=False):
        # per ogni campo richiesto dalla config
        for field in include_fields:
            w = weights.get(field.rstrip("s"), 1)
            if field in ("actors", "directors", "writers"):
                names = _split_csv(getattr(r, field, "") or "")
                nconsts = _resolve_names_to_nconsts(names)
                idx = inv.get(field, {})
                for nc in nconsts:
                    for tconst in idx.get(nc, []):
                        raw_scores[tconst] = raw_scores.get(tconst, 0.0) + w
            elif field == "genres":
                idx = inv["genres"]
                for g in _split_csv(getattr(r, "genres", "") or ""):
                    for tconst in idx.get(g, []):
                        raw_scores[tconst] = raw_scores.get(tconst, 0.0) + w
            elif field == "decade":
                dec = _decade_token(getattr(r, "year", None))
                if dec:
                    for tconst in inv["decade"].get(dec, []):
                        raw_scores[tconst] = raw_scores.get(tconst, 0.0) + w
            elif field in ("language", "country", "keywords"):
                idx = inv.get(field, {})
                for v in _split_csv(getattr(r, field, "") or ""):
                    for tconst in idx.get(v, []):
                        raw_scores[tconst] = raw_scores.get(tconst, 0.0) + w
            elif field == "plot":
                # nei dump IMDb non c'è nel discovery: lo useremo dopo l'enrichment
                pass

    # rimuovi quelli già nel tuo Notion
    for seen_id in list(all_notion_imdb_ids):
        raw_scores.pop(seen_id, None)

    # se non abbiamo nulla, esci
    if not raw_scores:
        return pd.DataFrame(columns=["imdb_id", "title"])

    # prendi candidati ordinati per score statico (limita per non esplodere TF-IDF)
    # es: tieni i primi 200-400 per passare poi al TF-IDF
    prelim = sorted(raw_scores.items(), key=lambda kv: kv[1], reverse=True)
    max_seed = max(top_k * 8, 300)  # seed ampio ma ragionevole
    seed_tconsts = [t for t, _ in prelim[:max_seed]]

    # --- 2) costruisci feature tokens per anchors e candidati ---
    # per candidati: usiamo nconst per persone, generi e decade dai tconst_info / indici
    # serve una mappa tconst -> set(nconst) per ciascun ruolo; costruiamola SOLO sul sottoinsieme seed per efficienza
    def _invert_people_index(
        field_idx: dict[str, t.Set[str]], wanted_tconsts: t.Set[str]
    ) -> dict[str, t.Set[str]]:
        # ritorna: tconst -> set(nconst) (solo per i tconsts di interesse)
        out: dict[str, t.Set[str]] = {}
        for nconst, titles in field_idx.items():
            inter = titles & wanted_tconsts
            if not inter:
                continue
            for tc in inter:
                out.setdefault(tc, set()).add(nconst)
        return out

    seed_set = set(seed_tconsts)
    tconst_actors = (
        _invert_people_index(inv["actors"], seed_set) if inv["actors"] else {}
    )
    tconst_directors = (
        _invert_people_index(inv["directors"], seed_set) if inv["directors"] else {}
    )
    tconst_writers = (
        _invert_people_index(inv["writers"], seed_set) if inv["writers"] else {}
    )

    def _candidate_tokens(tconst: str) -> list[str]:
        info = tconst_info.get(tconst, {})
        toks: list[str] = []

        if "actors" in include_fields and tconst in tconst_actors:
            toks += _repeat(
                [f"actor:{nc}" for nc in sorted(tconst_actors[tconst])],
                weights.get("actor", 2),
            )

        if "directors" in include_fields and tconst in tconst_directors:
            toks += _repeat(
                [f"director:{nc}" for nc in sorted(tconst_directors[tconst])],
                weights.get("director", 3),
            )

        if "writers" in include_fields and tconst in tconst_writers:
            toks += _repeat(
                [f"writer:{nc}" for nc in sorted(tconst_writers[tconst])],
                weights.get("writer", 2),
            )

        if "genres" in include_fields:
            for g in info.get("genres", []):
                toks += _repeat([f"genre:{g}"], weights.get("genre", 1))

        if "decade" in include_fields:
            dec = _decade_token(info.get("year"))
            if dec:
                toks += _repeat([f"decade:{dec}"], weights.get("decade", 1))

        # language/country/keywords non disponibili qui → ignorati
        return toks

    def _anchor_tokens(row: pd.Series) -> list[str]:
        toks: list[str] = []

        if "actors" in include_fields:
            nconsts = _resolve_names_to_nconsts(_split_csv(row.get("actors", "")))
            toks += _repeat([f"actor:{nc}" for nc in nconsts], weights.get("actor", 2))

        if "directors" in include_fields:
            nconsts = _resolve_names_to_nconsts(_split_csv(row.get("directors", "")))
            toks += _repeat(
                [f"director:{nc}" for nc in nconsts], weights.get("director", 3)
            )

        if "writers" in include_fields:
            nconsts = _resolve_names_to_nconsts(_split_csv(row.get("writers", "")))
            toks += _repeat(
                [f"writer:{nc}" for nc in nconsts], weights.get("writer", 2)
            )

        if "genres" in include_fields:
            for g in _split_csv(row.get("genres", "")):
                toks += _repeat([f"genre:{g}"], weights.get("genre", 1))

        if "decade" in include_fields:
            dec = _decade_token(row.get("year"))
            if dec:
                toks += _repeat([f"decade:{dec}"], weights.get("decade", 1))

        # language/country/keywords/plot non usati qui (mancano in index)
        return toks

    # documenti: prima gli anchor, poi i candidati
    anchor_docs = [
        " ".join(_anchor_tokens(r._asdict() if hasattr(r, "_asdict") else r))
        for r in anchors.itertuples(index=False)
    ]
    cand_docs = [" ".join(_candidate_tokens(t)) for t in seed_tconsts]

    # --- 3) TF-IDF su (anchors + candidati) ---
    vec = TfidfVectorizer(
        ngram_range=tuple(tfidf_cfg.get("ngram_range", [1, 2])),
        min_df=int(tfidf_cfg.get("min_df", 2)),
        max_df=float(tfidf_cfg.get("max_df", 0.85)),
        stop_words=tfidf_cfg.get("stop_words", "english"),
    )
    X = vec.fit_transform(anchor_docs + cand_docs)
    na = len(anchor_docs)
    Xa = X[:na, :]
    Xc = X[na:, :]

    sims = cosine_similarity(Xa, Xc)  # (na x nc)
    mean_sim = sims.mean(axis=0)  # (nc,)

    # --- 4) output DataFrame ordinato ---
    rows = []
    for i, tconst in enumerate(seed_tconsts):
        info = tconst_info.get(tconst)
        if not info:
            continue
        rows.append(
            {
                "imdb_id": tconst,
                "title": info.get("title", ""),
                "year": info.get("year", np.nan),
                "genres": ", ".join(info.get("genres", [])),
                "tfidf_sim": float(mean_sim[i]),
                "imdb_rating": info.get("rating", np.nan),
                "imdb_votes": info.get("votes", np.nan),
            }
        )
    if not rows:
        return pd.DataFrame(columns=["imdb_id", "title"])

    cand = pd.DataFrame(rows)

    # Ordine: TF-IDF sim, poi rating, poi votes
    cand = (
        cand.sort_values(
            by=["tfidf_sim", "imdb_rating", "imdb_votes"],
            ascending=[False, False, False],
            kind="mergesort",
        )
        .head(top_k)
        .reset_index(drop=True)
    )
    # per compat: esponiamo anche 'score' = tfidf_sim
    cand["score"] = cand["tfidf_sim"]
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
