from movie_tracker.movie_inserter import create_payload


DATABASE_ID = "248104cd-477e-80fd-b757-e945d38000bd"


def test_create_seen_payload_matches_notion_contract(movie_values):
    payload = create_payload(DATABASE_ID, movie_values, seen=True)

    assert payload["parent"] == {
        "type": "data_source_id",
        "data_source_id": DATABASE_ID,
    }
    properties = payload["properties"]
    assert properties["Title"] == {
        "type": "title",
        "title": [{"type": "text", "text": {"content": "Arrival"}}],
    }
    assert properties["Tags"] == {
        "type": "multi_select",
        "multi_select": [{"name": "Seen"}],
    }
    assert properties["IMDb URL"] == {
        "type": "url",
        "url": "https://www.imdb.com/title/tt2543164",
    }
    assert properties["Cover"] == {
        "files": [
            {
                "type": "external",
                "name": "Movie Cover",
                "external": {"url": "https://example.test/arrival.jpg"},
            }
        ]
    }
    assert properties["Last Seen"] == {"date": {"start": "2026-07-01"}}
    assert properties["My Score"] == {"type": "number", "number": 9.0}


def test_create_unseen_payload_omits_personal_viewing_fields(movie_values):
    movie_values["Tags"] = "Want to see"

    properties = create_payload(DATABASE_ID, movie_values, seen=False)["properties"]

    assert "Last Seen" not in properties
    assert "My Score" not in properties
    assert properties["Tags"]["multi_select"] == [{"name": "Want to see"}]


def test_create_payload_does_not_mutate_values(movie_values, clone):
    original = clone(movie_values)

    create_payload(DATABASE_ID, movie_values, seen=True)

    assert movie_values == original


def test_create_payload_preserves_all_tags(movie_values):
    movie_values["Tags"] = ["Seen", "Sci-Fi", "Favorite"]

    properties = create_payload(DATABASE_ID, movie_values, seen=True)["properties"]

    assert properties["Tags"]["multi_select"] == [
        {"name": "Seen"},
        {"name": "Sci-Fi"},
        {"name": "Favorite"},
    ]


def test_create_payload_writes_metadata_provenance(movie_values):
    movie_values["Metadata Source"] = "TMDB"
    movie_values["Metadata Synced At"] = "2026-07-12T10:00:00+00:00"

    properties = create_payload(DATABASE_ID, movie_values, seen=True)["properties"]

    assert properties["Metadata Source"] == {"select": {"name": "TMDB"}}
    assert properties["Metadata Synced At"] == {
        "date": {"start": "2026-07-12T10:00:00+00:00"}
    }
