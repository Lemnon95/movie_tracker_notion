from pathlib import Path
from typing import Callable
import webbrowser


TMDB_URL = "https://www.themoviedb.org"
TMDB_NOTICE = (
    "This application uses TMDB and the TMDB APIs but is not endorsed, certified, "
    "or otherwise approved by TMDB."
)


def credits_page_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "credits.html"


def show_credits(opener: Callable[..., bool] = webbrowser.open) -> bool:
    print("Movie metadata: TMDB (primary) and OMDb (IMDb rating/fallback).")
    print(TMDB_NOTICE)
    print("TMDB: " + TMDB_URL)
    print("Movie Tracker does not contain recommendation, ML, or AI functionality.")

    page = credits_page_path()
    if not page.is_file():
        print("The local Credits page is unavailable.")
        return False

    try:
        opened = bool(opener(page.as_uri(), new=2))
    except (OSError, webbrowser.Error):
        opened = False
    if not opened:
        print("Unable to open the local Credits page in a browser.")
    return opened
