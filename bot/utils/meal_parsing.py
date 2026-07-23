import re

MEAL_KEYWORDS = {
    "завтрак": "breakfast",
    "обед": "lunch",
    "ужин": "dinner",
    "перекус": "snack",
}

_HEADER_RE = re.compile(r"(?im)^\s*(" + "|".join(MEAL_KEYWORDS) + r")\s*:?\s*$")


def split_by_meal_sections(text: str) -> list[tuple[str, str]]:
    """Splits a free-text food log message into (meal_type, segment_text) chunks based on
    Завтрак:/Обед:/Ужин:/Перекус: headers. Falls back to a single 'unspecified' section if
    no headers are present."""
    sections: list[tuple[str, list[str]]] = []
    current_meal = "unspecified"
    current_lines: list[str] = []
    found_header = False

    for line in text.splitlines():
        match = _HEADER_RE.match(line)
        if match:
            if current_lines:
                sections.append((current_meal, current_lines))
            current_meal = MEAL_KEYWORDS[match.group(1).lower()]
            current_lines = []
            found_header = True
        elif line.strip():
            current_lines.append(line)

    if current_lines:
        sections.append((current_meal, current_lines))

    if not found_header:
        return [("unspecified", text)]

    return [(meal, "\n".join(lines)) for meal, lines in sections if lines]
