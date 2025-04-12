from imdb_utils import get_movie_values
from notion_api import (
    create_page,
    update_page,
    query_database,
    extract_imdb_id_from_url,
)
from helpers import is_float, is_valid_date
import os
from datetime import datetime
from config import CONFIG_DIR


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


def update_movie(token: str, database_id: str):
    logs_dir = os.path.join(CONFIG_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    imdb_id = input(
        "Enter IMDb ID to update a specific movie or press Enter to update all: "
    ).strip()
    imdb_url = f"https://www.imdb.com/title/tt{imdb_id}" if imdb_id else None

    pages = query_database(token, database_id, imdb_url=imdb_url)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_lines = [f"=== Update started at {timestamp} ==="]

    updated_count = 0
    failed_count = 0

    if not pages:
        log_lines.append("No matching movies found.")
    else:
        total_pages = len(pages)
        for index, page in enumerate(pages, start=1):
            page_id = page["id"]
            props = page["properties"]

            imdb_url = props.get("IMDb URL", {}).get("url", "")
            if not imdb_url:
                log_lines.append("Skipped a page with no IMDb URL")
                failed_count += 1
                continue

            title = (
                props.get("Title", {})
                .get("title", [{}])[0]
                .get("text", {})
                .get("content", "Unknown")
            )
            print(f"\nUpdating ({index}/{total_pages}): '{title}'...")
            log_lines.append(f"Starting update for: {title}")

            imdb_id = extract_imdb_id_from_url(imdb_url)
            imdb_data = get_movie_values(imdb_id)
            if imdb_data == 1:
                log_lines.append(f"❌ Failed to fetch IMDb data for {title}")
                failed_count += 1
                continue

            user_tags = []
            if isinstance(props.get("Tags"), dict):
                user_tags = props["Tags"].get("multi_select", []) or []

            user_score = None
            if isinstance(props.get("My Score"), dict):
                user_score = props["My Score"].get("number")

            last_seen = None
            if isinstance(props.get("Last Seen"), dict):
                date_field = props["Last Seen"].get("date")
                if date_field:
                    last_seen = date_field.get("start")

            imdb_data["Tags"] = user_tags[0]["name"] if user_tags else None
            imdb_data["My Score"] = user_score
            imdb_data["Last Seen"] = last_seen

            seen = imdb_data["Tags"] == "Seen"
            payload = create_payload(database_id, imdb_data, seen)

            for key in list(imdb_data.keys()):
                if imdb_data[key] is None:
                    payload["properties"].pop(key, None)

            status_code, _ = update_page(token, page_id, payload["properties"])
            if status_code == 200:
                log_lines.append(f"✔️ Finished updating: {title}")
                updated_count += 1
            else:
                log_lines.append(f"❌ Failed to update: {title}")
                failed_count += 1

    log_lines.append(
        f"\nSummary: Updated {updated_count} movie(s), Failed {failed_count}."
    )

    log_path = os.path.join(logs_dir, "update_log.txt")
    with open(log_path, "w", encoding="utf-8") as log_file:
        for line in log_lines:
            print(line)
            log_file.write(line + "\n")
