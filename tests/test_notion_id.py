import pytest

from movie_tracker.notion_id import normalize_notion_database_id


DATABASE_ID = "248104cd-477e-80fd-b757-e945d38000bd"


@pytest.mark.parametrize(
    "value",
    [
        DATABASE_ID,
        "248104cd477e80fdb757e945d38000bd",
        "  248104CD477E80FDB757E945D38000BD  ",
        "https://www.notion.so/example/248104cd477e80fdb757e945d38000bd?v=148104cd477e80bb928f000ce197ddf2",
        "https://www.notion.so/Movie-Tracker-248104cd477e80fdb757e945d38000bd?pvs=4",
        "https://workspace.notion.site/Movie-Tracker-248104cd477e80fdb757e945d38000bd",
    ],
)
def test_normalize_notion_database_id(value):
    assert normalize_notion_database_id(value) == DATABASE_ID


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-database-id",
        "248104cd477e80fdb757e945d38000b",
        "https://example.com/248104cd477e80fdb757e945d38000bd",
        "https://www.notion.so/example/no-database-id",
    ],
)
def test_normalize_notion_database_id_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_notion_database_id(value)


def test_normalize_notion_database_id_rejects_non_string():
    with pytest.raises(ValueError):
        normalize_notion_database_id(123)
