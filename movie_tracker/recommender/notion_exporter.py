# -*- coding: utf-8 -*-
"""
Export Movie Tracker pages from Notion into a pandas.DataFrame ready for recommendations.

- No SDK: reuses existing notion_api.query_database(token, database_id, imdb_url=None).

Returned DataFrame columns (best-effort):
['title','imdb_url','imdb_id','actors','directors','writers','year',
 'runtime_min','imdb_rating','tags','plot','release_date','last_seen',
 'my_score','notion_page_id']

All multi-values are flattened to comma-separated strings.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

import re
import pandas as pd

from movie_tracker.notion_api import query_database


def _safe_get_title(prop: Dict[str, Any]) -> Optional[str]:
    if not prop or prop.get("type") != "title":
        return None
    parts = prop.get("title", [])
    if not parts:
        return None
    return "".join(p.get("plain_text", "") for p in parts).strip() or None


def _safe_rich_text(prop: Dict[str, Any]) -> Optional[str]:
    if not prop or prop.get("type") != "rich_text":
        return None
    parts = prop.get("rich_text", [])
    text = "".join(p.get("plain_text", "") for p in parts).strip()
    return text or None


def _safe_number(prop: Dict[str, Any]) -> Optional[float]:
    if not prop or prop.get("type") != "number":
        return None
    return prop.get("number")


def _safe_url(prop: Dict[str, Any]) -> Optional[str]:
    if not prop or prop.get("type") != "url":
        return None
    return prop.get("url")


def _safe_date(prop: Dict[str, Any]) -> Optional[str]:
    if not prop or prop.get("type") != "date":
        return None
    date = prop.get("date")
    return date.get("start") if date else None


def _safe_multiselect_names(prop: Dict[str, Any]) -> Optional[List[str]]:
    if not prop or prop.get("type") != "multi_select":
        return None
    return [o.get("name") for o in prop.get("multi_select", []) if o.get("name")]


def _flatten_list(v: Optional[List[str]]) -> Optional[str]:
    if not v:
        return None
    return ", ".join([x for x in v if x])


def _extract_imdb_id_from_url(url: str) -> Optional[str]:
    m = re.search(r"(tt\d{7,8})", url or "")
    return m.group(1) if m else None


def export_movies_df(token: str, database_id: str) -> pd.DataFrame:
    """Fetch all pages from the Notion database and normalize into a DataFrame."""
    pages = query_database(token, database_id, imdb_url=None) or []
    rows: List[Dict[str, Any]] = []

    for page in pages:
        props = page.get("properties", {})

        title = _safe_get_title(props.get("Title", {}))
        imdb_url = _safe_url(props.get("IMDb URL", {}))
        imdb_id = _extract_imdb_id_from_url(imdb_url) if imdb_url else None

        row = {
            "title": title,
            "imdb_url": imdb_url,
            "imdb_id": imdb_id,
            "actors": _safe_rich_text(props.get("Actors", {})),
            "directors": _safe_rich_text(props.get("Directors", {})),
            "writers": _safe_rich_text(props.get("Writers", {})),
            "year": _safe_number(props.get("Year", {})),
            "runtime_min": _safe_number(props.get("Runtime", {})),
            "imdb_rating": _safe_number(props.get("Rating - IMDb", {})),
            "tags": _flatten_list(_safe_multiselect_names(props.get("Tags", {}))),
            "plot": _safe_rich_text(props.get("Plot", {})),
            "release_date": _safe_date(props.get("Release Date", {})),
            "last_seen": _safe_date(props.get("Last Seen", {})),
            "my_score": _safe_number(props.get("My Score", {})),
            "notion_page_id": page.get("id"),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    # Basic sanity: drop completely empty titles
    df = df.dropna(subset=["title"]).reset_index(drop=True)
    return df
