from datetime import date


def is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def is_valid_date(date_str: str) -> bool:
    try:
        date.fromisoformat(date_str)
        return True
    except ValueError:
        return False


def omdb_to_isodate(date_str: str) -> str:
    """
    Converts OMDb date format '14 Feb 2025' to ISO format '2025-02-14'.
    Returns None if conversion fails.
    """
    try:
        day, mon, year = date_str.split(" ")
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
        return f"{year}-{months[mon]}-{day.zfill(2)}"
    except Exception:
        return
