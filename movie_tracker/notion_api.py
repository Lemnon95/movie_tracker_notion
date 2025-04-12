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
