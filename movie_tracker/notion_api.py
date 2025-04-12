import requests
from typing import Dict

NOTION_VERSION = "2022-06-28"


def _get_headers(token: str, content_type: bool = False) -> Dict[str, str]:
    headers = {
        "accept": "application/json",
        "Notion-Version": NOTION_VERSION,
        "authorization": "Bearer " + token,
    }
    if content_type:
        headers["content-type"] = "application/json"
    return headers


def create_page(token: str, payload: dict):
    url = "https://api.notion.com/v1/pages"
    headers = _get_headers(token, content_type=True)
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code, response.text


import requests


def query_database(token: str, database_id: str, imdb_url: str = None):
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "accept": "application/json",
        "Notion-Version": "2022-06-28",
        "authorization": f"Bearer {token}",
        "content-type": "application/json",
    }

    if imdb_url:
        filter_payload = {
            "filter": {"property": "IMDb URL", "url": {"equals": imdb_url}}
        }
    else:
        filter_payload = {}

    response = requests.post(url, headers=headers, json=filter_payload)
    if response.status_code == 200:
        return response.json().get("results", [])
    else:
        print(f"Failed to query Notion: {response.status_code}")
        return []


def update_page(token: str, page_id: str, new_properties: dict):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "accept": "application/json",
        "Notion-Version": "2022-06-28",
        "authorization": f"Bearer {token}",
        "content-type": "application/json",
    }
    payload = {"properties": new_properties}
    response = requests.patch(url, headers=headers, json=payload)
    return response.status_code, response.text


def extract_imdb_id_from_url(url: str) -> str:
    # Esempio: https://www.imdb.com/title/tt1234567
    if "tt" in url:
        return url.split("tt")[-1]
    return ""
