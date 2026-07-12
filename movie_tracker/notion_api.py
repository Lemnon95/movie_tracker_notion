from typing import Any, Dict, List, Optional

from movie_tracker.http_client import (
    HttpClientError,
    HttpStatusError,
    default_http_client,
)
from movie_tracker.imdb_id import normalize_imdb_id
from movie_tracker.notion_id import normalize_notion_database_id


NOTION_VERSION = "2026-03-11"
NOTION_BASE_URL = "https://api.notion.com/v1"


class NotionApiError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message)


class NotionConfigurationError(NotionApiError):
    pass


def _get_headers(token: str, content_type: bool = False) -> Dict[str, str]:
    headers = {
        "accept": "application/json",
        "Notion-Version": NOTION_VERSION,
        "authorization": "Bearer " + token,
    }
    if content_type:
        headers["content-type"] = "application/json"
    return headers


def _request_json(method: str, url: str, token: str, **kwargs: Any) -> Any:
    try:
        response = default_http_client.request(
            method,
            url,
            headers=_get_headers(token, content_type=method.upper() != "GET"),
            **kwargs,
        )
        return default_http_client.parse_json(response)
    except HttpStatusError as exc:
        detail = exc.response_text.strip() or str(exc)
        raise NotionApiError(
            f"Notion request failed ({exc.status_code}): {detail}",
            status_code=exc.status_code,
        ) from exc
    except HttpClientError as exc:
        raise NotionApiError(f"Unable to contact Notion: {exc}") from exc


def resolve_data_source_id(
    token: str, database_id: str, preferred_data_source_id: str = ""
) -> str:
    database_id = normalize_notion_database_id(database_id)
    if preferred_data_source_id:
        preferred = normalize_notion_database_id(preferred_data_source_id)
        data = _request_json(
            "GET", f"{NOTION_BASE_URL}/data_sources/{preferred}", token
        )
        parent_database_id = data.get("parent", {}).get("database_id")
        if (
            parent_database_id
            and normalize_notion_database_id(parent_database_id) != database_id
        ):
            raise NotionConfigurationError(
                "DATA_SOURCE_ID does not belong to the configured DATABASE_ID."
            )
        return preferred

    data = _request_json("GET", f"{NOTION_BASE_URL}/databases/{database_id}", token)
    sources: List[dict] = data.get("data_sources", [])
    if not sources:
        raise NotionConfigurationError(
            "The Notion database has no accessible data sources. Check integration access."
        )
    if len(sources) > 1:
        choices = ", ".join(
            f"{item.get('name', 'Unnamed')} ({item.get('id', 'missing id')})"
            for item in sources
        )
        raise NotionConfigurationError(
            "The Notion database contains multiple data sources. "
            f"Set DATA_SOURCE_ID explicitly. Available: {choices}"
        )
    return normalize_notion_database_id(sources[0]["id"])


def create_page(token: str, payload: dict) -> dict:
    return _request_json("POST", f"{NOTION_BASE_URL}/pages", token, json=payload)


def query_database(token: str, data_source_id: str, imdb_url: str = None) -> list:
    data_source_id = normalize_notion_database_id(data_source_id)
    url = f"{NOTION_BASE_URL}/data_sources/{data_source_id}/query"
    base_payload = {"page_size": 100}
    if imdb_url:
        base_payload["filter"] = {
            "property": "IMDb URL",
            "url": {"equals": imdb_url},
        }

    results = []
    next_cursor = None
    while True:
        payload = dict(base_payload)
        if next_cursor is not None:
            payload["start_cursor"] = next_cursor

        data = _request_json("POST", url, token, json=payload)
        results.extend(data.get("results", []))
        if not data.get("has_more", False):
            return results

        next_cursor = data.get("next_cursor")
        if not next_cursor:
            raise NotionApiError(
                "Notion pagination response has_more=true without next_cursor"
            )


def update_page(token: str, page_id: str, new_properties: dict) -> dict:
    return _request_json(
        "PATCH",
        f"{NOTION_BASE_URL}/pages/{page_id}",
        token,
        json={"properties": new_properties},
    )


def extract_imdb_id_from_url(url: str) -> str:
    return normalize_imdb_id(url)
