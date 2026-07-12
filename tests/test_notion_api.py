from unittest.mock import Mock

import pytest

from movie_tracker import notion_api
from movie_tracker.http_client import HttpStatusError


DATABASE_ID = "248104cd-477e-80fd-b757-e945d38000bd"
DATA_SOURCE_ID = "148104cd-477e-80bb-928f-000ce197ddf2"


def test_create_page_uses_current_api_and_returns_json(monkeypatch):
    request_json = Mock(return_value={"id": "page-1"})
    monkeypatch.setattr(notion_api, "_request_json", request_json)
    payload = {"parent": {"type": "data_source_id", "data_source_id": DATA_SOURCE_ID}}

    result = notion_api.create_page("token-123", payload)

    assert result == {"id": "page-1"}
    request_json.assert_called_once_with(
        "POST", "https://api.notion.com/v1/pages", "token-123", json=payload
    )


def test_query_data_source_collects_all_pages_and_preserves_filter(monkeypatch):
    request_json = Mock(
        side_effect=[
            {
                "results": [{"id": "page-1"}],
                "has_more": True,
                "next_cursor": "cursor-2",
            },
            {"results": [{"id": "page-2"}], "has_more": False},
        ]
    )
    monkeypatch.setattr(notion_api, "_request_json", request_json)
    imdb_url = "https://www.imdb.com/title/tt2543164"

    result = notion_api.query_database("token-123", DATA_SOURCE_ID, imdb_url=imdb_url)

    assert result == [{"id": "page-1"}, {"id": "page-2"}]
    endpoint = f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query"
    assert request_json.call_args_list[0].args == ("POST", endpoint, "token-123")
    assert request_json.call_args_list[0].kwargs["json"] == {
        "page_size": 100,
        "filter": {"property": "IMDb URL", "url": {"equals": imdb_url}},
    }
    assert request_json.call_args_list[1].kwargs["json"]["start_cursor"] == "cursor-2"


def test_query_data_source_rejects_missing_cursor(monkeypatch):
    monkeypatch.setattr(
        notion_api,
        "_request_json",
        Mock(return_value={"results": [], "has_more": True, "next_cursor": None}),
    )

    with pytest.raises(notion_api.NotionApiError, match="without next_cursor"):
        notion_api.query_database("token-123", DATA_SOURCE_ID)


def test_update_page_returns_json(monkeypatch):
    request_json = Mock(return_value={"id": "page-1"})
    monkeypatch.setattr(notion_api, "_request_json", request_json)
    properties = {"Title": {"title": []}}

    result = notion_api.update_page("token-123", "page-1", properties)

    assert result == {"id": "page-1"}
    request_json.assert_called_once_with(
        "PATCH",
        "https://api.notion.com/v1/pages/page-1",
        "token-123",
        json={"properties": properties},
    )


def test_resolve_single_data_source(monkeypatch):
    monkeypatch.setattr(
        notion_api,
        "_request_json",
        Mock(return_value={"data_sources": [{"id": DATA_SOURCE_ID, "name": "Movies"}]}),
    )

    assert notion_api.resolve_data_source_id("token-123", DATABASE_ID) == DATA_SOURCE_ID


def test_resolve_validates_explicit_data_source_parent(monkeypatch):
    request_json = Mock(
        return_value={"parent": {"type": "database_id", "database_id": DATABASE_ID}}
    )
    monkeypatch.setattr(notion_api, "_request_json", request_json)

    assert (
        notion_api.resolve_data_source_id("token-123", DATABASE_ID, DATA_SOURCE_ID)
        == DATA_SOURCE_ID
    )
    request_json.assert_called_once_with(
        "GET",
        f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}",
        "token-123",
    )


def test_resolve_rejects_data_source_from_another_database(monkeypatch):
    other_database = "348104cd-477e-80fd-b757-e945d38000bd"
    monkeypatch.setattr(
        notion_api,
        "_request_json",
        Mock(return_value={"parent": {"database_id": other_database}}),
    )

    with pytest.raises(notion_api.NotionConfigurationError, match="does not belong"):
        notion_api.resolve_data_source_id("token-123", DATABASE_ID, DATA_SOURCE_ID)


def test_resolve_requires_explicit_choice_for_multiple_sources(monkeypatch):
    monkeypatch.setattr(
        notion_api,
        "_request_json",
        Mock(
            return_value={
                "data_sources": [
                    {"id": DATA_SOURCE_ID, "name": "Movies"},
                    {"id": DATABASE_ID, "name": "Archive"},
                ]
            }
        ),
    )

    with pytest.raises(notion_api.NotionConfigurationError, match="multiple"):
        notion_api.resolve_data_source_id("token-123", DATABASE_ID)


def test_request_errors_are_not_confused_with_empty_results(monkeypatch):
    client = Mock()
    client.request.side_effect = HttpStatusError(
        401, "https://api.notion.com", "bad token"
    )
    monkeypatch.setattr(notion_api, "default_http_client", client)

    with pytest.raises(notion_api.NotionApiError) as error:
        notion_api.query_database("token-123", DATA_SOURCE_ID)

    assert error.value.status_code == 401
    assert "bad token" in str(error.value)


def test_headers_use_current_notion_version():
    assert notion_api._get_headers("token-123")["Notion-Version"] == "2026-03-11"
