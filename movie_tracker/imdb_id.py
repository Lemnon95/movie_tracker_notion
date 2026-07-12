import re
from urllib.parse import urlparse


_IMDB_ID_RE = re.compile(r"tt(?P<digits>\d{7,})", re.IGNORECASE)
_IMDB_NUMERIC_ID_RE = re.compile(r"\d{7,}")


def normalize_imdb_id(value: str) -> str:
    """Return a canonical IMDb title ID (``tt`` plus at least seven digits)."""
    if not isinstance(value, str):
        raise ValueError("IMDb ID must be a string")

    candidate = value.strip()
    if _IMDB_NUMERIC_ID_RE.fullmatch(candidate):
        return f"tt{candidate}"

    match = _IMDB_ID_RE.fullmatch(candidate)
    if match:
        return f"tt{match.group('digits')}"

    parsed = urlparse(candidate)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not (
        hostname == "imdb.com" or hostname.endswith(".imdb.com")
    ):
        raise ValueError(f"Invalid IMDb title ID or URL: {value}")

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2 or path_parts[0].lower() != "title":
        raise ValueError(f"Invalid IMDb title ID or URL: {value}")

    match = _IMDB_ID_RE.fullmatch(path_parts[1])
    if not match:
        raise ValueError(f"Invalid IMDb title ID or URL: {value}")
    return f"tt{match.group('digits')}"


def build_imdb_url(value: str) -> str:
    """Build the canonical title URL for an IMDb title ID or URL."""
    return f"https://www.imdb.com/title/{normalize_imdb_id(value)}"
