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
