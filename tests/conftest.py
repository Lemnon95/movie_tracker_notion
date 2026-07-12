import copy

import pytest


@pytest.fixture
def movie_values():
    return {
        "Title": "Arrival",
        "Tags": "Seen",
        "Plot": "A linguist works with the military to communicate with aliens.",
        "Actors": "Amy Adams, Jeremy Renner",
        "Directors": "Denis Villeneuve",
        "Writers": "Eric Heisserer, Ted Chiang",
        "Year": 2016,
        "Runtime": 116,
        "Rating - IMDb": 7.9,
        "IMDb URL": "https://www.imdb.com/title/tt2543164",
        "Cover": "https://example.test/arrival.jpg",
        "Release Date": "2016-11-11",
        "Last Seen": "2026-07-01",
        "My Score": 9.0,
    }


@pytest.fixture
def notion_page():
    def text_part(value):
        return {"type": "text", "plain_text": value, "text": {"content": value}}

    return {
        "id": "page-123",
        "properties": {
            "Title": {"type": "title", "title": [text_part("Arri"), text_part("val")]},
            "IMDb URL": {
                "type": "url",
                "url": "https://www.imdb.com/title/tt2543164/?ref_=fn_all_ttl_1",
            },
            "Actors": {
                "type": "rich_text",
                "rich_text": [text_part("Amy Adams"), text_part(", Jeremy Renner")],
            },
            "Directors": {
                "type": "rich_text",
                "rich_text": [text_part("Denis Villeneuve")],
            },
            "Writers": {
                "type": "rich_text",
                "rich_text": [text_part("Eric Heisserer")],
            },
            "Year": {"type": "number", "number": 2016},
            "Runtime": {"type": "number", "number": 116},
            "Rating - IMDb": {"type": "number", "number": 7.9},
            "Tags": {
                "type": "multi_select",
                "multi_select": [{"name": "Seen"}, {"name": "Sci-Fi"}],
            },
            "Plot": {"type": "rich_text", "rich_text": [text_part("First contact.")]},
            "Release Date": {"type": "date", "date": {"start": "2016-11-11"}},
            "Last Seen": {"type": "date", "date": {"start": "2026-07-01"}},
            "My Score": {"type": "number", "number": 9.0},
        },
    }


@pytest.fixture
def clone():
    return copy.deepcopy
