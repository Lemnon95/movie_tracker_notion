from movie_tracker.metadata import MetadataError
from movie_tracker.metadata.omdb_provider import OmdbProvider
from movie_tracker.metadata.tmdb_provider import TmdbProvider
from movie_tracker.metadata.tracker_service import TrackerMetadataService
from movie_tracker.notion_api import (
    create_page,
    update_page,
    query_database,
    extract_imdb_id_from_url,
    NotionApiError,
)
from movie_tracker.helpers import is_float, is_valid_date
import os
from datetime import datetime, timedelta, timezone
from movie_tracker.config import CONFIG_DIR
from movie_tracker.imdb_id import build_imdb_url, normalize_imdb_id
from movie_tracker.notion_id import normalize_notion_database_id


def _append_update_log(logs_dir: str, log_lines: list) -> str:
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, "update_log.txt")
    with open(log_path, "a", encoding="utf-8") as log_file:
        if log_file.tell() > 0:
            log_file.write("\n")
        for line in log_lines:
            log_file.write(line + "\n")
    return log_path


def create_payload(data_source_id: str, values: dict, seen: bool) -> dict:
    data_source_id = normalize_notion_database_id(data_source_id)
    tags = values["Tags"]
    if isinstance(tags, str):
        tags = [tags]
    properties = {
        "Title": {
            "type": "title",
            "title": [{"type": "text", "text": {"content": values["Title"]}}],
        },
        "Tags": {
            "type": "multi_select",
            "multi_select": [{"name": tag} for tag in tags],
        },
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
    if values.get("Metadata Source"):
        properties["Metadata Source"] = {"select": {"name": values["Metadata Source"]}}
    if values.get("Metadata Synced At"):
        properties["Metadata Synced At"] = {
            "date": {"start": values["Metadata Synced At"]}
        }
    if seen:
        properties["Last Seen"] = {"date": {"start": values["Last Seen"]}}
        properties["My Score"] = {"type": "number", "number": values["My Score"]}

    return {
        "parent": {"type": "data_source_id", "data_source_id": data_source_id},
        "properties": properties,
    }


def _build_metadata_service(
    omdb_api_key: str, tmdb_api_token: str
) -> TrackerMetadataService:
    return TrackerMetadataService(
        TmdbProvider(tmdb_api_token), OmdbProvider(omdb_api_key)
    )


def _metadata_values(
    imdb_id: str,
    omdb_api_key: str,
    tmdb_api_token: str,
    service: TrackerMetadataService = None,
) -> dict:
    service = service or _build_metadata_service(omdb_api_key, tmdb_api_token)
    metadata = service.get_by_imdb_id(imdb_id)
    # Validate the combined result so OMDb can still complete a missing TMDB title.
    title = metadata.title
    if (
        not isinstance(title, str)
        or not title.strip()
        or title.strip().upper() == "N/A"
    ):
        raise MetadataError("Movie metadata has no valid title; no changes were saved.")
    values = metadata.to_notion_values()
    values["Metadata Source"] = metadata.primary_source
    values["Metadata Synced At"] = service.synced_at()
    if service.last_warning:
        print("Warning: " + service.last_warning)
    return values


def insert_movie(
    token: str, data_source_id: str, omdb_api_key: str, tmdb_api_token: str
) -> tuple:
    values = {}
    movie_id = normalize_imdb_id(input("Insert movie ID: "))
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

    service = _build_metadata_service(omdb_api_key, tmdb_api_token)
    imdb_data = _metadata_values(
        movie_id, omdb_api_key, tmdb_api_token, service=service
    )
    values.update(imdb_data)

    payload = create_payload(data_source_id, values, seen)
    for key in list(values.keys()):
        if values[key] is None:
            payload["properties"].pop(key, None)

    create_page(token, payload)
    return 200, values["Title"]


def update_movie(
    token: str, data_source_id: str, omdb_api_key: str, tmdb_api_token: str
):
    logs_dir = os.path.join(CONFIG_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    imdb_id = input(
        "Enter IMDb ID to update a specific movie or press Enter to update all: "
    ).strip()
    imdb_url = build_imdb_url(imdb_id) if imdb_id else None

    pages = query_database(token, data_source_id, imdb_url=imdb_url)
    service = _build_metadata_service(omdb_api_key, tmdb_api_token)

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

            title_parts = props.get("Title", {}).get("title", [])
            title = (
                "".join(
                    part.get("plain_text") or part.get("text", {}).get("content", "")
                    for part in title_parts
                )
                or "Unknown"
            )
            print(f"\nUpdating ({index}/{total_pages}): '{title}'...")
            log_lines.append(f"Starting update for: {title}")

            try:
                imdb_id = extract_imdb_id_from_url(imdb_url)
            except ValueError as e:
                log_lines.append(f"❌ {e}")
                failed_count += 1
                continue

            log_lines.append(f"Extracted IMDb ID: {imdb_id}")
            try:
                imdb_data = _metadata_values(
                    imdb_id, omdb_api_key, tmdb_api_token, service=service
                )
            except (MetadataError, ValueError) as exc:
                log_lines.append(f"❌ Failed to fetch data for {title}: {exc}")
                failed_count += 1
                continue
            # Ensure IMDb URL is always the full URL
            imdb_data["IMDb URL"] = imdb_url

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

            imdb_data["Tags"] = [tag["name"] for tag in user_tags if tag.get("name")]
            imdb_data["My Score"] = user_score
            imdb_data["Last Seen"] = last_seen

            seen = "Seen" in imdb_data["Tags"]
            payload = create_payload(data_source_id, imdb_data, seen)

            for key in list(imdb_data.keys()):
                if imdb_data[key] is None:
                    payload["properties"].pop(key, None)

            try:
                update_page(token, page_id, payload["properties"])
                log_lines.append(f"✔️ Finished updating: {title}")
                updated_count += 1
            except (NotionApiError, ValueError) as exc:
                log_lines.append(f"❌ Failed to update {title}: {exc}")
                failed_count += 1

    log_lines.append(
        f"\nSummary: Updated {updated_count} movie(s), Failed {failed_count}."
    )

    for line in log_lines:
        print(line)
    _append_update_log(logs_dir, log_lines)


def is_stale_tmdb_page(
    page: dict, max_age_days: int = 150, now: datetime = None
) -> bool:
    if not isinstance(page, dict):
        return False
    props = page.get("properties")
    if not isinstance(props, dict):
        return False
    source_prop = props.get("Metadata Source")
    source_prop = source_prop if isinstance(source_prop, dict) else {}
    source = source_prop.get("select") or {}
    source = source if isinstance(source, dict) else {}
    if source.get("name") != "TMDB":
        return False
    synced_prop = props.get("Metadata Synced At")
    synced_prop = synced_prop if isinstance(synced_prop, dict) else {}
    date_value = synced_prop.get("date") or {}
    date_value = date_value if isinstance(date_value, dict) else {}
    synced = date_value.get("start")
    if not synced:
        return True
    try:
        parsed = datetime.fromisoformat(synced.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return True
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return parsed <= reference - timedelta(days=max_age_days)


def refresh_stale_movies(
    token: str,
    data_source_id: str,
    omdb_api_key: str,
    tmdb_api_token: str,
    max_age_days: int = 150,
    confirm=input,
) -> tuple:
    """Refresh stale records; ``confirm=None`` runs without a prompt at startup."""
    pages = query_database(token, data_source_id)
    stale = [page for page in pages if is_stale_tmdb_page(page, max_age_days)]
    print("{} stale TMDB record(s) found.".format(len(stale)))
    if not stale:
        return 0, 0
    if (
        confirm is not None
        and confirm("Refresh them now? y/n: ").strip().lower() != "y"
    ):
        return 0, 0
    updated = failed = 0
    log_lines = [
        "=== Stale TMDB refresh started ===",
        "Candidates: {}".format(len(stale)),
    ]
    service = _build_metadata_service(omdb_api_key, tmdb_api_token)
    for page in stale:
        props = page.get("properties", {})
        props = props if isinstance(props, dict) else {}
        try:
            page_id = page.get("id")
            if not isinstance(page_id, str) or not page_id:
                raise ValueError("Notion page has no valid ID")
            imdb_prop = props.get("IMDb URL")
            imdb_prop = imdb_prop if isinstance(imdb_prop, dict) else {}
            imdb_id = extract_imdb_id_from_url(imdb_prop.get("url", ""))
            values = _metadata_values(
                imdb_id, omdb_api_key, tmdb_api_token, service=service
            )
            tags_prop = props.get("Tags")
            tags_prop = tags_prop if isinstance(tags_prop, dict) else {}
            tag_items = tags_prop.get("multi_select")
            tag_items = tag_items if isinstance(tag_items, list) else []
            values["Tags"] = [
                item["name"].strip()
                for item in tag_items
                if isinstance(item, dict)
                and isinstance(item.get("name"), str)
                and item.get("name").strip()
            ]
            score_prop = props.get("My Score")
            score_prop = score_prop if isinstance(score_prop, dict) else {}
            values["My Score"] = score_prop.get("number")
            seen_prop = props.get("Last Seen")
            seen_prop = seen_prop if isinstance(seen_prop, dict) else {}
            seen_date = seen_prop.get("date") or {}
            seen_date = seen_date if isinstance(seen_date, dict) else {}
            values["Last Seen"] = seen_date.get("start")
            payload = create_payload(data_source_id, values, "Seen" in values["Tags"])
            for key, value in values.items():
                if value is None:
                    payload["properties"].pop(key, None)
            update_page(token, page_id, payload["properties"])
            updated += 1
        except (MetadataError, NotionApiError, ValueError) as exc:
            failed += 1
            log_lines.append("Failed {}: {}".format(page.get("id", "unknown"), exc))
    summary = "Summary: Updated {}, Failed {}.".format(updated, failed)
    log_lines.append(summary)
    log_path = _append_update_log(os.path.join(CONFIG_DIR, "logs"), log_lines)
    print(summary)
    if failed:
        print("Some movies could not be refreshed. Details: " + log_path)
    return updated, failed
