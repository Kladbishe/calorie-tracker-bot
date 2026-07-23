import re

_GENDERS = {"male", "female"}
_ACTIVITY_LEVELS = {"sedentary", "light", "moderate", "high", "very_high"}
_GOALS = {"loss", "gain", "maintain"}


def parse_positive_float(text: str, min_value: float = 0, max_value: float = 500) -> float | None:
    text = text.strip().replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        return None
    if not (min_value < value <= max_value):
        return None
    return value


def parse_positive_int(text: str, min_value: int = 0, max_value: int = 250) -> int | None:
    text = text.strip()
    if not re.fullmatch(r"\d+", text):
        return None
    value = int(text)
    if not (min_value < value <= max_value):
        return None
    return value


def parse_weight(text: str) -> float | None:
    return parse_positive_float(text, min_value=20, max_value=400)


def parse_height(text: str) -> float | None:
    return parse_positive_float(text, min_value=100, max_value=250)


def parse_age(text: str) -> int | None:
    return parse_positive_int(text, min_value=9, max_value=120)


def parse_target_value(text: str) -> int | None:
    """Single macro/kcal target field, e.g. when editing one target value manually."""
    return parse_positive_int(text, min_value=0, max_value=10000)
