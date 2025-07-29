from imdb import Cinemagoer, IMDbError, Person
from typing import Union
import requests
from movie_tracker.helpers import omdb_to_isodate


def names(people: list[Person]) -> str:
    return ", ".join([person.get("name", "") for person in people])


def isodate(date_str: str) -> str:
    months = {
        "Jan": "01",
        "Feb": "02",
        "Mar": "03",
        "Apr": "04",
        "May": "05",
        "Jun": "06",
        "Jul": "07",
        "Aug": "08",
        "Sep": "09",
        "Oct": "10",
        "Nov": "11",
        "Dec": "12",
    }
    day, mon, year = date_str.split(" ")
    return f"{year}-{months[mon]}-{day}"


def get_movie_values_omdb(imdb_id: str, omdb_api_key: str) -> dict:
    url = f"http://www.omdbapi.com/?i=tt{imdb_id}&apikey={omdb_api_key}&plot=full"
    response = requests.get(url)
    data = response.json()
    if data.get("Response") == "False":
        print(f"OMDb API error: {data.get('Error')}")
        return {}
    release_date = data.get("Released")
    iso_release_date = (
        omdb_to_isodate(release_date)
        if release_date and release_date != "N/A"
        else None
    )
    return {
        "Title": data.get("Title"),
        "Plot": data.get("Plot"),
        "Year": int(data.get("Year"))
        if data.get("Year") and data.get("Year").isdigit()
        else None,
        "Directors": data.get("Director"),
        "Runtime": int(data.get("Runtime", "0").split(" ")[0])
        if data.get("Runtime", "N/A") != "N/A"
        else None,
        "Cover": data.get("Poster") if data.get("Poster") != "N/A" else None,
        "Writers": data.get("Writer"),
        "IMDb URL": f"https://www.imdb.com/title/tt{imdb_id}",
        "Rating - IMDb": float(data.get("imdbRating"))
        if data.get("imdbRating") and data.get("imdbRating") != "N/A"
        else None,
        "Actors": data.get("Actors"),
        "Release Date": iso_release_date,
    }


def get_movie_values(movie_id: str, omdb_api_key: str) -> Union[dict, int]:
    values = {}
    ia = Cinemagoer()
    try:
        movie = ia.get_movie(movie_id)
        ia.update(movie)
    except IMDbError as e:
        return get_movie_values_omdb(movie_id)  # fallback

    values["Title"] = movie.get("title")
    values["Plot"] = movie.get("plot", [None])[0]
    values["Year"] = movie.get("year")
    values["Directors"] = names(movie.get("directors", []))
    values["Runtime"] = (
        int(movie.get("runtime", [0])[0]) if "runtime" in movie else None
    )
    values["Cover"] = movie.get("full-size cover url")
    values["Writers"] = names(movie.get("writers", []))
    values["IMDb URL"] = f"https://www.imdb.com/title/tt{movie_id}"
    values["Rating - IMDb"] = movie.get("rating")
    values["Actors"] = names(movie.get("cast", [])[:6])
    try:
        values["Release Date"] = isodate(movie["original air date"])
    except:
        values["Release Date"] = None

    # Fallback for None fields using OMDb
    omdb_values = get_movie_values_omdb(movie_id, omdb_api_key)
    for key in values:
        if values[key] in (None, "", []):
            values[key] = omdb_values.get(key, values[key])

    cover = omdb_values.get("Cover")
    values["Cover"] = get_high_res_cover(cover)

    return values


def get_high_res_cover(cover_url: str) -> str:
    """
    Tries to get the highest resolution cover by testing several size tags.
    Returns the first valid high-res URL found, otherwise returns the original URL.
    """
    if cover_url and "SX300" in cover_url:
        for size in ["SX2000", "SX1500", "SX1200", "SX1000", "SX700", "SX500"]:
            high_res_url = cover_url.replace("SX300", size)
            try:
                response = requests.head(high_res_url, timeout=3)
                if response.status_code == 200:
                    return high_res_url
            except Exception:
                continue
    return cover_url
