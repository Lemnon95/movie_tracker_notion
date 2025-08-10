# -*- coding: utf-8 -*-
"""
Content-based recommendations on top of Movie Tracker DataFrame.

- Entity-aware features with configurable weights (director/actor/genre/writer/plot)
- TF-IDF with configurable params
- Optional Discovery: IMDb datasets + dynamic OMDb enrichment (with cache in provider)
- Blended scoring (similarity + IMDb rating + recency)
- Diversity penalty to avoid rank collapse on the same director
- All knobs read from ML_SETTINGS (with safe defaults + deep-merge)

Public API:
    recommend(
        df: pd.DataFrame,
        top_k: int = 10,
        min_score: float = 8.0,
        include_plot: bool = False,    # kept for backward compat; ML_SETTINGS.features.use_plot overrides if set
        discovery: bool = False,
        omdb_api_key: str = "",
        ml_settings: dict = None,
    ) -> pd.DataFrame
"""

from __future__ import annotations
from typing import Tuple, Dict, Any, Optional

import re
import math
import datetime as dt

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from movie_tracker.recommender.providers.imdb_datasets_provider import (
    ensure_datasets,
    build_index,
    discover_candidates,
    enrich_with_omdb,
)

# -----------------------
# Defaults & utils
# -----------------------

DEFAULT_SETTINGS: Dict[str, Any] = {
    "features": {
        "use_plot": True,
        "plot_max_words": 25,
        "weights": {"director": 3, "actor": 2, "genre": 2, "writer": 1, "plot": 1},
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
    "diversity": {
        "max_per_director": 2,
        "penalty": 0.15,
    },
    "discovery": {
        "min_votes": 5000,
        "year_from": 1970,
        "year_to": 2100,
        "candidate_top_k": 200,
        "eligibility_quantile": 0.60,  # keep top 40% by score before enrichment
        "quality_min_rating": 6.5,
        "quality_min_votes": 2000,
        "enrich_budget": {"per_top_k": 7, "per_anchor": 5, "min": 30},
    },
}


def _deep_merge(
    base: Dict[str, Any], override: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Deep-merge override into base without modifying inputs."""
    if not override:
        return dict(base)
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# -----------------------
# Feature building
# -----------------------


def _norm_list(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in str(value).split(",") if x and str(x).strip()]


def _tok(prefix: str, items: list[str]) -> list[str]:
    return [f"{prefix}:{i.replace(' ', '_')}" for i in items if i]


def _extract_plot_tokens(s: Optional[str], max_words: int = 25) -> list[str]:
    if not s:
        return []
    text = str(s).lower()
    text = re.sub(r"[^a-z0-9àèéìòùçñ\s]", " ", text)
    words = [w for w in text.split() if len(w) > 2]
    return [f"kw:{w}" for w in words[:max_words]]


def _build_features_series(
    df: pd.DataFrame,
    use_plot: bool,
    plot_max_words: int,
    weights: Dict[str, int],
) -> pd.Series:
    actors = (
        df.get("actors", "")
        .fillna("")
        .map(_norm_list)
        .map(lambda xs: _tok("actor", xs))
    )
    directors = (
        df.get("directors", "")
        .fillna("")
        .map(_norm_list)
        .map(lambda xs: _tok("director", xs))
    )
    writers = df.get("writers", "").fillna("").map(lambda xs: _tok("writer", xs))
    genres = (
        df.get("genres", "")
        .fillna("")
        .map(_norm_list)
        .map(lambda xs: _tok("genre", xs))
    )

    def build_row(i: int) -> str:
        toks: list[str] = []
        toks += directors.iloc[i] * int(weights.get("director", 3))
        toks += actors.iloc[i] * int(weights.get("actor", 2))
        toks += genres.iloc[i] * int(weights.get("genre", 2))
        toks += writers.iloc[i] * int(weights.get("writer", 1))
        if use_plot:
            toks += _extract_plot_tokens(
                df.get("plot", "").iloc[i] or "", max_words=plot_max_words
            ) * int(max(1, weights.get("plot", 1)))
        return " ".join(toks) if toks else ""

    return pd.Series([build_row(i) for i in range(len(df))], index=df.index).fillna("")


def _tfidf_matrix(
    features: pd.Series, tfidf_cfg: Dict[str, Any]
) -> Tuple[np.ndarray, TfidfVectorizer]:
    ngram = tuple(tfidf_cfg.get("ngram_range", [1, 1]))
    vec = TfidfVectorizer(
        ngram_range=ngram,
        min_df=int(tfidf_cfg.get("min_df", 1)),
        max_df=float(tfidf_cfg.get("max_df", 1.0)),
        stop_words=tfidf_cfg.get("stop_words", None),
    )
    X = vec.fit_transform(features.values)
    return X, vec


# -----------------------
# Enrichment selector (dynamic)
# -----------------------


def enrich_external_candidates(
    ext: pd.DataFrame,
    anchors_n: int,
    top_k: int,
    omdb_api_key: str,
    disc_cfg: Dict[str, Any],
) -> pd.DataFrame:
    """
    Selects and enriches (via OMDb) only the most promising external candidates,
    using a dynamic budget and optional quality/score filters, then writes back
    the enriched columns to 'ext' in-place (by index).
    """
    if ext.empty or not omdb_api_key:
        return ext

    from movie_tracker.recommender.providers.imdb_datasets_provider import (
        enrich_with_omdb,
    )

    budget_cfg = disc_cfg.get("enrich_budget", {})
    budget = max(
        top_k * int(budget_cfg.get("per_top_k", 7)),
        anchors_n * int(budget_cfg.get("per_anchor", 5)),
        int(budget_cfg.get("min", 30)),
    )

    # Sort by score -> rating -> votes when present
    sort_cols = [c for c in ["score", "imdb_rating", "imdb_votes"] if c in ext.columns]
    ext_sorted = (
        ext.sort_values(by=sort_cols, ascending=[False] * len(sort_cols))
        if sort_cols
        else ext
    )

    # Cutoff by score quantile
    q = float(disc_cfg.get("eligibility_quantile", 0.60))
    if "score" in ext_sorted.columns and not ext_sorted["score"].isna().all():
        score_cut = ext_sorted["score"].quantile(q)
        ext_sorted = ext_sorted[ext_sorted["score"] >= score_cut]
    else:
        score_cut = None

    # Quality filter (if present)
    rmin = float(disc_cfg.get("quality_min_rating", 0))
    vmin = int(disc_cfg.get("quality_min_votes", 0))
    if "imdb_rating" in ext_sorted.columns and "imdb_votes" in ext_sorted.columns:
        qm = (ext_sorted["imdb_rating"].fillna(0) >= rmin) & (
            ext_sorted["imdb_votes"].fillna(0) >= vmin
        )
        if qm.any():
            ext_sorted = ext_sorted[qm]

    max_items = int(min(len(ext_sorted), budget))
    print(
        f"🔧 Enriching {max_items} of {len(ext)} external candidates via OMDb "
        f"(budget={budget}, anchors={anchors_n}, score_cut={score_cut if score_cut is not None else 'n/a'})"
    )

    # Keep original index for reinsertion
    subset = ext_sorted.head(max_items).copy().reset_index(drop=False)
    orig_idx_col = "orig_index"
    subset.rename(columns={"index": orig_idx_col}, inplace=True)

    enriched_subset = enrich_with_omdb(
        subset.drop(columns=[orig_idx_col]),
        omdb_api_key,
        max_items=max_items,
        verbose=True,
    )
    enriched_subset[orig_idx_col] = subset[orig_idx_col].values

    for col in ["actors", "directors", "writers", "plot"]:
        if col in enriched_subset.columns:
            ext.loc[enriched_subset[orig_idx_col], col] = enriched_subset[col].values

    print("✅ OMDb enrichment done.")
    return ext


# -----------------------
# Blending & diversity
# -----------------------


def _blend_score(
    row: pd.Series, blend_cfg: Dict[str, Any], current_year: Optional[int] = None
) -> float:
    if current_year is None:
        current_year = dt.datetime.now().year

    w_sim = float(blend_cfg.get("w_sim", 0.7))
    w_rating = float(blend_cfg.get("w_rating", 0.2))
    w_rec = float(blend_cfg.get("w_recency", 0.1))
    tau = float(blend_cfg.get("recency_tau_years", 8))

    sim = float(row.get("similarity", 0) or 0)

    rating = row.get("imdb_rating")
    rating_norm = (
        (float(rating) - 5.0) / 5.0 if pd.notna(rating) else 0.0
    )  # 5..10 -> 0..1 approx

    year = row.get("year")
    if pd.notna(year):
        age = max(0, current_year - int(year))
        recency = math.exp(-age / max(1e-6, tau))
    else:
        recency = 0.3  # mild neutral

    return w_sim * sim + w_rating * rating_norm + w_rec * recency


def _apply_diversity_penalty(
    df: pd.DataFrame, max_per_director: int, penalty: float
) -> pd.DataFrame:
    if df.empty:
        return df
    counts: Dict[str, int] = {}
    adj = df.copy()
    base = adj.get("final_score", adj.get("similarity")).astype(float).values.copy()
    dirs = adj.get("directors", "").fillna("")

    for i in range(len(adj)):
        dfield = dirs.iloc[i]
        first_dir = dfield.split(",")[0].strip().lower() if dfield else ""
        counts.setdefault(first_dir, 0)
        if first_dir and counts[first_dir] >= max_per_director:
            base[i] *= 1.0 - float(penalty)
        counts[first_dir] += 1

    adj["final_score_div"] = base
    return adj


# -----------------------
# Main API
# -----------------------


def recommend(
    df: pd.DataFrame,
    top_k: int = 10,
    min_score: float = 8.0,
    include_plot: bool = False,
    discovery: bool = False,
    omdb_api_key: str = "",
    ml_settings: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    If discovery=True, expand candidate set with external IMDb pool (filtered by votes/year),
    enrich the most promising items via OMDb (dynamic budget), then rank with TF-IDF.
    """
    if df.empty:
        return pd.DataFrame(columns=["title", "imdb_id", "similarity"])

    # Merge user overrides into defaults
    S = _deep_merge(DEFAULT_SETTINGS, ml_settings or {})

    # 1) Select anchors
    anchors = df[(df.get("my_score").notna()) & (df["my_score"] >= float(min_score))]
    if anchors.empty:
        anchors = df[df.get("imdb_rating").notna()].nlargest(5, "imdb_rating")
    if anchors.empty:
        return pd.DataFrame(columns=["title", "imdb_id", "similarity"])

    candidate_pool = df.copy()

    print(f"Anchors used: {len(anchors)} (threshold={min_score})")
    if discovery:
        print("🔎 Discovery mode ON")

    if discovery:
        # 2) Build/load IMDb index using discovery settings
        paths = ensure_datasets()
        disc_cfg = S["discovery"]
        index = build_index(
            paths,
            min_votes=int(disc_cfg.get("min_votes", 5000)),
            year_from=int(disc_cfg.get("year_from", 1970)),
            year_to=int(disc_cfg.get("year_to", 2100)),
            include_fields=S["features"].get(
                "include_fields",
                ["actors", "directors", "genres", "writers", "language", "country"],
            ),
        )

        # IDs already in Notion
        notion_ids = set(df["imdb_id"].dropna().astype(str).tolist())

        # 3) Discover external candidates using configurable fields & weights
        ext = discover_candidates(
            anchors=anchors,
            all_notion_imdb_ids=notion_ids,
            index=index,
            ml_settings=S,
            top_k=int(disc_cfg.get("candidate_top_k", 200)),
        )

        # 4) Dynamic OMDb enrichment
        if not ext.empty and omdb_api_key:
            ext = enrich_external_candidates(
                ext=ext,
                anchors_n=len(anchors),
                top_k=top_k,
                omdb_api_key=omdb_api_key,
                disc_cfg=disc_cfg,
            )
        else:
            if ext.empty:
                print("ℹ️ No external candidates to enrich.")
            elif not omdb_api_key:
                print("ℹ️ OMDb API key missing, skipping enrichment.")

        # 5) Align schema
        for col in [
            "actors",
            "directors",
            "writers",
            "plot",
            "genres",
            "language",
            "country",
            "my_score",
            "imdb_rating",
            "runtime_min",
            "year",
        ]:
            if col not in ext.columns:
                ext[col] = (
                    ""
                    if col
                    in (
                        "actors",
                        "directors",
                        "writers",
                        "plot",
                        "genres",
                        "language",
                        "country",
                    )
                    else np.nan
                )

        for col in [
            "actors",
            "directors",
            "writers",
            "plot",
            "genres",
            "language",
            "country",
        ]:
            ext[col] = ext[col].fillna("")
        for col in ["my_score", "imdb_rating", "runtime_min", "year"]:
            ext[col] = pd.to_numeric(ext[col], errors="coerce")

        candidate_pool = pd.concat([df, ext], ignore_index=True, sort=False)

    # --- TF-IDF ranking ---
    feat_cfg = S["features"]
    use_plot_effective = bool(feat_cfg.get("use_plot", include_plot or False))
    features = _build_features_series(
        candidate_pool,
        use_plot=use_plot_effective,
        plot_max_words=int(feat_cfg.get("plot_max_words", 25)),
        weights=feat_cfg.get("weights", {}),
    )
    X, _ = _tfidf_matrix(features, S["tfidf"])

    idx_anchors = anchors.index.to_list()
    sims = cosine_similarity(X[idx_anchors], X)
    mean_sim = sims.mean(axis=0)

    result = candidate_pool.copy()
    result["similarity"] = mean_sim

    # Exclude already rated
    seen_mask = result["my_score"].notna()
    result = result[~seen_mask]

    # If discovery, keep only externals
    if discovery:
        result = result[~result["imdb_id"].isin(df["imdb_id"].dropna().astype(str))]

    # Blend score
    for col in ["imdb_rating", "year"]:
        if col not in result.columns:
            result[col] = np.nan
    result["final_score"] = result.apply(lambda r: _blend_score(r, S["blend"]), axis=1)

    # Diversity penalty
    div_cfg = S["diversity"]
    result = _apply_diversity_penalty(
        result,
        max_per_director=int(div_cfg.get("max_per_director", 2)),
        penalty=float(div_cfg.get("penalty", 0.15)),
    )

    # Sort and return
    sort_col = (
        "final_score_div" if "final_score_div" in result.columns else "final_score"
    )
    result = result.sort_values(sort_col, ascending=False).head(top_k)

    for c in ["actors", "directors", "genres"]:
        if c not in result.columns:
            result[c] = ""
    return result[["title", "imdb_id", "similarity", "actors", "directors", "genres"]]
