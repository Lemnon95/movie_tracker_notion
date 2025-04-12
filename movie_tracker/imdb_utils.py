from imdb import Cinemagoer, IMDbError, Person
from typing import Union


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


def get_movie_values(movie_id: str) -> Union[dict, int]:
    values = {}
    ia = Cinemagoer()
    try:
        movie = ia.get_movie(movie_id)
    except IMDbError as e:
        print(e)
        return 1
    values["Title"] = movie.get("title")
    values["Plot"] = movie.get("plot", [None])[0]
    values["Year"] = movie.get("year")
    values["Directors"] = names(movie.get("directors", []))
    values["Runtime"] = (
        int(movie.get("runtime", [0])[0]) if "runtime" in movie else None
    )
    values["Cover"] = movie.get("full-size cover url")
    values["Writers"] = names(movie.get("writers", []))
    values["IMDb URL"] = "https://www.imdb.com/title/tt" + movie.get("imdbID", "")
    values["Rating - IMDb"] = movie.get("rating")
    values["Actors"] = names(movie.get("cast", [])[:6])
    try:
        values["Release Date"] = isodate(movie["original air date"])
    except:
        values["Release Date"] = None
    return values
