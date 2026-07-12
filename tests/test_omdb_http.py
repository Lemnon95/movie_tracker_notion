from unittest.mock import Mock

import pytest

from movie_tracker.metadata.omdb_provider import OmdbProvider
from movie_tracker.metadata.provider import MetadataApiError


def test_movie_metadata_uses_shared_https_client(monkeypatch):
    client = Mock()
    client.get_json.return_value = {
        "Response": "True",
        "Title": "Arrival",
        "Plot": "First contact.",
        "Year": "2016",
        "Director": "Denis Villeneuve",
        "Runtime": "116 min",
        "Poster": "https://example.test/poster.jpg",
        "Writer": "Eric Heisserer",
        "imdbRating": "7.9",
        "Actors": "Amy Adams",
        "Released": "11 Nov 2016",
    }
    result = OmdbProvider("api-key", client).get_by_imdb_id("2543164")

    assert result.title == "Arrival"
    assert result.imdb_url == "https://www.imdb.com/title/tt2543164"
    client.get_json.assert_called_once_with(
        "https://www.omdbapi.com/",
        params={"i": "tt2543164", "apikey": "api-key", "plot": "full"},
    )


def test_movie_metadata_exposes_omdb_api_errors(monkeypatch):
    client = Mock()
    client.get_json.return_value = {"Response": "False", "Error": "Invalid API key!"}
    with pytest.raises(MetadataApiError, match="Invalid API key"):
        OmdbProvider("bad-key", client).get_by_imdb_id("2543164")
