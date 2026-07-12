import re
import uuid
from urllib.parse import urlparse


_COMPACT_UUID_RE = re.compile(r"(?<![0-9a-f])([0-9a-f]{32})(?![0-9a-f])", re.IGNORECASE)
_HYPHENATED_UUID_RE = re.compile(
    r"(?<![0-9a-f])([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?![0-9a-f])",
    re.IGNORECASE,
)


def _canonical_uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid Notion database ID: {value}") from exc


def normalize_notion_database_id(value: str) -> str:
    """Return a canonical hyphenated UUID from a Notion database ID or URL."""
    if not isinstance(value, str):
        raise ValueError("Notion database ID must be a string")

    candidate = value.strip()
    if not candidate:
        raise ValueError("Notion database ID cannot be empty")

    try:
        return _canonical_uuid(candidate)
    except ValueError:
        pass

    parsed = urlparse(candidate)
    hostname = (parsed.hostname or "").lower()
    is_notion_host = hostname in {"notion.so", "notion.site"} or hostname.endswith(
        (".notion.so", ".notion.site")
    )
    if parsed.scheme not in {"http", "https"} or not is_notion_host:
        raise ValueError(f"Invalid Notion database ID or URL: {value}")

    match = _HYPHENATED_UUID_RE.search(parsed.path) or _COMPACT_UUID_RE.search(
        parsed.path
    )
    if not match:
        raise ValueError(f"Invalid Notion database ID or URL: {value}")
    return _canonical_uuid(match.group(1))
