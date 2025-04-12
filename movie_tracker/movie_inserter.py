from imdb_utils import get_movie_values
from notion_api import create_page
from helpers import is_float, is_valid_date


def create_payload(database_id: str, values: dict, seen: bool) -> dict:
    properties = {
        "Title": {
            "type": "title",
            "title": [{"type": "text", "text": {"content": values["Title"]}}],
        },
        "Tags": {"type": "multi_select", "multi_select": [{"name": values["Tags"]}]},
        "Plot": {"rich_text": [{"type": "text", "text": {"content": values["Plot"]}}]},
        "Actors": {
            "rich_text": [{"type": "text", "text": {"content": values["Actors"]}}]
        },
        "Directors": {
            "rich_text": [{"type": "text", "text": {"content": values["Directors"]}}]
        },
        "Writers": {
            "rich_text": [{"type": "text", "text": {"content": values["Writers"]}}]
        },
        "Year": {"type": "number", "number": values["Year"]},
        "Runtime": {"type": "number", "number": values["Runtime"]},
        "Rating - IMDb": {"type": "number", "number": values["Rating - IMDb"]},
        "IMDb URL": {"type": "url", "url": values["IMDb URL"]},
        "Cover": {
            "files": [
                {
                    "type": "external",
                    "name": "Movie Cover",
                    "external": {"url": values["Cover"]},
                }
            ]
        },
        "Release Date": {"date": {"start": values["Release Date"]}},
    }
    if seen:
        properties["Last Seen"] = {"date": {"start": values["Last Seen"]}}
        properties["My Score"] = {"type": "number", "number": values["My Score"]}
    return {"parent": {"database_id": database_id}, "properties": properties}


def insert_movie(token: str, database_id: str) -> tuple:
    values = {}
    movie_id = input("Insert movie ID: ")
    seen = input("Have you seen the movie? Type 0 for no, 1 for yes: ") == "1"

    if not seen:
        tag = input("Is the movie out yet? y/n: ")
        values["Tags"] = "Want to see" if tag == "y" else "Not Yet Released"
    else:
        score = input("What's your score? (0.0 to 10.0): ")
        values["My Score"] = float(score) if score and is_float(score) else None
        last_seen = input("When did you watch it? yyyy-mm-dd: ")
        values["Last Seen"] = (
            last_seen if last_seen and is_valid_date(last_seen) else None
        )
        values["Tags"] = "Seen"

    imdb_data = get_movie_values(movie_id)
    if imdb_data == 1:
        return 400, f"{movie_id} movie id"
    values.update(imdb_data)

    payload = create_payload(database_id, values, seen)
    for key in list(values.keys()):
        if values[key] is None:
            payload["properties"].pop(key, None)

    return create_page(token, payload)[0], values["Title"]
