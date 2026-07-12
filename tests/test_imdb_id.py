import pytest

from movie_tracker.imdb_id import build_imdb_url, normalize_imdb_id
from movie_tracker.notion_api import extract_imdb_id_from_url


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0111161", "tt0111161"),
        ("tt0111161", "tt0111161"),
        ("TT0111161", "tt0111161"),
        ("  tt0111161  ", "tt0111161"),
        ("tt123456789", "tt123456789"),
        ("https://www.imdb.com/title/tt0111161/", "tt0111161"),
        ("https://m.imdb.com/title/tt0111161/?ref_=fn_all_ttl_1", "tt0111161"),
    ],
)
def test_normalize_imdb_id(value, expected):
    assert normalize_imdb_id(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "tt123456",
        "nm0000158",
        "watch tt0111161",
        "https://example.com/title/tt0111161/",
        "https://www.imdb.com/name/nm0000158/",
    ],
)
def test_normalize_imdb_id_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_imdb_id(value)


def test_normalize_imdb_id_rejects_non_string():
    with pytest.raises(ValueError):
        normalize_imdb_id(111161)


def test_build_imdb_url_is_canonical():
    assert build_imdb_url("0111161") == "https://www.imdb.com/title/tt0111161"


def test_legacy_extractor_uses_shared_normalization():
    assert (
        extract_imdb_id_from_url("https://www.imdb.com/title/tt123456789/")
        == "tt123456789"
    )
