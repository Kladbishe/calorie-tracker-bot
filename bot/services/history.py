import aiosqlite

from bot.db import food_log as food_log_repo
from bot.db import weight_log as weight_log_repo
from bot.texts import t
from bot.utils.dates import date_days_ago, today_str
from bot.utils.formatting import fmt_num


async def build_history_report(db: aiosqlite.Connection, user_id: int, period: str, tz_name: str, lang: str) -> str:
    today = today_str(tz_name)

    if period == "today":
        date_from = date_to = today
    elif period == "yesterday":
        date_from = date_to = date_days_ago(tz_name, 1)
    elif period == "week":
        date_from = date_days_ago(tz_name, 6)
        date_to = today
    else:
        date_from = date_days_ago(tz_name, 6)
        date_to = today

    daily_totals = await food_log_repo.get_totals_for_range(db, user_id, date_from, date_to)
    weights = await weight_log_repo.get_weight_for_range(db, user_id, date_from, date_to)
    weight_by_date = {row["date"]: row["weight"] for row in weights}

    if not daily_totals:
        return t(lang, "history_no_entries", date_from=date_from, date_to=date_to)

    lines = [t(lang, "history_header", date_from=date_from, date_to=date_to)]
    for day in daily_totals:
        weight_part = (
            t(lang, "history_weight_part", weight=fmt_num(weight_by_date[day.date]))
            if day.date in weight_by_date
            else ""
        )
        lines.append(f"— {day.date} —")

        entries = await food_log_repo.get_entries_for_date(db, user_id, day.date)
        for entry in entries:
            lines.append(
                f"  • {entry['item_name']} ({fmt_num(entry['grams'])} {t(lang, 'unit_g')}) — "
                f"{fmt_num(entry['kcal'])} {t(lang, 'unit_kcal')}"
            )

        lines.append(
            t(
                lang,
                "history_total",
                kcal=fmt_num(day.kcal),
                protein=fmt_num(day.protein),
                fat=fmt_num(day.fat),
                carbs=fmt_num(day.carbs),
                weight_part=weight_part,
            )
        )
    return "\n".join(lines)
