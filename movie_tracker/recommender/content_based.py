# -*- coding: utf-8 -*-
"""
Content-based recommendations on top of Movie Tracker DataFrame.

Strategy:
- Build a 'features' text field by concatenating actors + directors + writers (+ optionally plot).
- TF-IDF vectorization and cosine similarity.
- Use user's favorites (my_score >= threshold) as anchors; rank others by mean similarity to anchors.

Public API:
- recommend(df, top_k=10, min_score=8.0, include_plot=False) -> pd.DataFrame
"""

from __future__ import annotations
from typing import Tuple

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


def _build_features_series(
    df: pd.DataFrame,
    include_plot: bool = False,
) -> pd.Series:
    cols = ["actors", "directors", "writers"]
    if include_plot:
        cols.append("plot")

    parts = []
    for c in cols:
        if c not in df.columns:
            continue
        parts.append(df[c].fillna(""))

    if not parts:
        return pd.Series([""] * len(df), index=df.index)

    # space-separated tokens; commas are fine but we normalize anyway
    merged = (
        parts[0]
        if len(parts) == 1
        else parts[0]
        .astype(str)
        .str.replace(",", " ")
        .str.cat([p.astype(str).str.replace(",", " ") for p in parts[1:]], sep=" ")
    )
    return merged.fillna("")


def _tfidf_matrix(features: pd.Series) -> Tuple[np.ndarray, TfidfVectorizer]:
    vec = TfidfVectorizer()
    X = vec.fit_transform(features.values)
    return X, vec


def enrich_external_candidates(
    ext: pd.DataFrame, anchors_n: int, top_k: int, omdb_api_key: str
) -> pd.DataFrame:
    """
    Selects and enriches the most promising external candidates via OMDb,
    using a dynamic budget and optional quality filters.

    Parameters
    ----------
    ext : pd.DataFrame
        External candidates from IMDb index (before enrichment).
    anchors_n : int
        Number of anchor movies used for similarity calculation.
    top_k : int
        Number of final recommendations to produce.
    omdb_api_key : str
        OMDb API key for enrichment.

    Returns
    -------
    pd.DataFrame
        'ext' DataFrame with selected rows enriched via OMDb.
    """
    if ext.empty or not omdb_api_key:
        return ext

    from movie_tracker.recommender.providers.imdb_datasets_provider import (
        enrich_with_omdb,
    )

    # Dynamic budget: proportional to top_k and number of anchors
    budget = max(top_k * 7, anchors_n * 5, 30)

    # Sort by score + rating + votes if available
    sort_cols = []
    if "score" in ext.columns:
        sort_cols.append("score")
    if "imdb_rating" in ext.columns:
        sort_cols.append("imdb_rating")
    if "imdb_votes" in ext.columns:
        sort_cols.append("imdb_votes")

    ext_sorted = (
        ext.sort_values(by=sort_cols, ascending=[False] * len(sort_cols))
        if sort_cols
        else ext
    )

    # Cutoff: top 40% by score if available
    score_cut = None
    if "score" in ext_sorted.columns and not ext_sorted["score"].isna().all():
        score_cut = ext_sorted["score"].quantile(0.60)
        ext_sorted = ext_sorted[ext_sorted["score"] >= score_cut]

    # Optional quality filter
    if "imdb_rating" in ext_sorted.columns and "imdb_votes" in ext_sorted.columns:
        quality_mask = (ext_sorted["imdb_rating"].fillna(0) >= 6.5) & (
            ext_sorted["imdb_votes"].fillna(0) >= 2000
        )
        if quality_mask.any():
            ext_sorted = ext_sorted[quality_mask]

    max_items = int(min(len(ext_sorted), budget))
    print(
        f"🔧 Enriching {max_items} of {len(ext)} external candidates via OMDb "
        f"(budget={budget}, anchors={anchors_n}, score_cut={score_cut if score_cut is not None else 'n/a'})"
    )

    # Keep original index for reinsertion
    subset = ext_sorted.head(max_items).copy().reset_index(drop=False)
    orig_idx_col = "orig_index"
    subset.rename(columns={"index": orig_idx_col}, inplace=True)

    # Enrich subset
    enriched_subset = enrich_with_omdb(
        subset.drop(columns=[orig_idx_col]),
        omdb_api_key,
        max_items=max_items,
        verbose=True,
    )
    enriched_subset[orig_idx_col] = subset[orig_idx_col].values

    # Reinstate enriched rows into 'ext'
    for col in ["actors", "directors", "writers", "plot"]:
        if col in enriched_subset.columns:
            ext.loc[enriched_subset[orig_idx_col], col] = enriched_subset[col].values

    print("✅ OMDb enrichment done.")
    return ext


def recommend(
    df: pd.DataFrame,
    top_k: int = 10,
    min_score: float = 8.0,
    include_plot: bool = False,
    discovery: bool = False,
    omdb_api_key: str = "",
) -> pd.DataFrame:
    """
    If discovery=True, expand candidate set with external IMDb pool (filtered by votes/year),
    enrich the most promising items via OMDb (dynamic budget), then rank with TF-IDF.
    """
    if df.empty:
        return pd.DataFrame(columns=["title", "imdb_id", "similarity"])

    # 1) anchors
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
        # 2) build or load IMDb index
        paths = ensure_datasets()
        index = build_index(paths, min_votes=5000, year_from=1970, year_to=2100)

        # set of imdb_ids already in Notion
        notion_ids = set(df["imdb_id"].dropna().astype(str).tolist())

        # 3) discover external candidates
        cols_base = ["imdb_id", "actors", "directors"]
        cols = cols_base + (["genres"] if "genres" in anchors.columns else [])
        ext = discover_candidates(anchors[cols], notion_ids, index, top_k=200)

        # 4) dynamic enrichment via OMDb (only the promising subset)
        if not ext.empty and omdb_api_key:
            ext = enrich_external_candidates(
                ext=ext,
                anchors_n=len(anchors),
                top_k=top_k,
                omdb_api_key=omdb_api_key,
            )
        else:
            if ext.empty:
                print("ℹ️ No external candidates to enrich.")
            elif not omdb_api_key:
                print("ℹ️ OMDb API key missing, skipping enrichment.")

        # 5) unify schema with Notion df so TF-IDF can work
        for col in [
            "actors",
            "directors",
            "writers",
            "plot",
            "genres",
            "my_score",
            "imdb_rating",
            "runtime_min",
        ]:
            if col not in ext.columns:
                ext[col] = (
                    ""
                    if col in ("actors", "directors", "writers", "plot", "genres")
                    else None
                )

        # fill text with "", numeric coerced to NaN
        text_cols = ["actors", "directors", "writers", "plot", "genres"]
        for col in text_cols:
            ext[col] = ext[col].fillna("")
        num_cols = ["my_score", "imdb_rating", "runtime_min"]
        for col in num_cols:
            ext[col] = pd.to_numeric(ext[col], errors="coerce")

        candidate_pool = pd.concat([df, ext], ignore_index=True, sort=False)

    # --- TF-IDF ranking ---
    features = _build_features_series(candidate_pool, include_plot=include_plot)
    X, _ = _tfidf_matrix(features)

    idx_anchors = anchors.index.to_list()
    sims = cosine_similarity(X[idx_anchors], X)
    mean_sim = sims.mean(axis=0)

    result = candidate_pool.copy()
    result["similarity"] = mean_sim

    # Exclude already rated (your Notion seen)
    seen_mask = result["my_score"].notna()
    result = result[~seen_mask]

    # If discovery, keep only externals (not in your Notion)
    if discovery:
        result = result[~result["imdb_id"].isin(df["imdb_id"].dropna().astype(str))]

    result = result.sort_values("similarity", ascending=False).head(top_k)
    # ensure columns exist for output
    for c in ["actors", "directors", "genres"]:
        if c not in result.columns:
            result[c] = ""
    return result[["title", "imdb_id", "similarity", "actors", "directors", "genres"]]
