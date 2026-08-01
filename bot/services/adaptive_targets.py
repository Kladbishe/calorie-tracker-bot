from dataclasses import dataclass

from bot.db import food_log as food_log_repo
from bot.db import weight_log as weight_log_repo
from bot.db.profiles import Profile
from bot.services.nutrition_fallback import DEFAULT_DEFICIT_PERCENT
from bot.utils.dates import days_between

KCAL_PER_KG = 7700
MIN_ELAPSED_DAYS = 5
MIN_LOGGED_DAYS = 4
NUDGE_THRESHOLD_KCAL = 100
_PLAUSIBLE_TDEE_RANGE = (800, 6000)


@dataclass
class TrendAdjustment:
    target_kcal: int
    target_protein: int
    target_fat: int
    target_carbs: int
    days_elapsed: int
    weight_change_kg: float
    avg_daily_kcal: float


async def suggest_target_adjustment(
    db, user_id: int, profile: Profile, new_weight: float, new_date: str
) -> TrendAdjustment | None:
    """Compares the user's actual weight trend against what they actually ate (not the
    activity-level guess from onboarding) and proposes a new target_kcal when the two
    noticeably disagree. Returns None when there isn't enough data yet, or when the
    current target already matches the observed trend closely enough."""
    if not profile.target_kcal or not profile.goal:
        return None

    history = await weight_log_repo.get_weight_history(db, user_id, limit=2)
    if len(history) < 2:
        return None
    prev_date, prev_weight = history[1]["date"], history[1]["weight"]

    days_elapsed = days_between(prev_date, new_date)
    if days_elapsed < MIN_ELAPSED_DAYS:
        return None

    daily_totals = await food_log_repo.get_totals_for_range(db, user_id, prev_date, new_date)
    logged_days = len(daily_totals)
    if logged_days < min(MIN_LOGGED_DAYS, days_elapsed):
        return None

    weight_change_kg = new_weight - prev_weight
    avg_daily_kcal = sum(day.kcal for day in daily_totals) / logged_days
    implied_tdee = avg_daily_kcal - (weight_change_kg * KCAL_PER_KG / days_elapsed)
    if not (_PLAUSIBLE_TDEE_RANGE[0] <= implied_tdee <= _PLAUSIBLE_TDEE_RANGE[1]):
        return None

    percent = profile.deficit_percent if profile.deficit_percent is not None else DEFAULT_DEFICIT_PERCENT.get(profile.goal, 0)
    if profile.goal == "loss":
        new_target_kcal = implied_tdee * (1 - percent / 100)
    elif profile.goal == "gain":
        new_target_kcal = implied_tdee * (1 + percent / 100)
    else:
        new_target_kcal = implied_tdee
    new_target_kcal = round(new_target_kcal)

    if abs(new_target_kcal - profile.target_kcal) < NUDGE_THRESHOLD_KCAL:
        return None

    ratio = new_target_kcal / profile.target_kcal
    return TrendAdjustment(
        target_kcal=new_target_kcal,
        target_protein=round((profile.target_protein or 0) * ratio),
        target_fat=round((profile.target_fat or 0) * ratio),
        target_carbs=round((profile.target_carbs or 0) * ratio),
        days_elapsed=days_elapsed,
        weight_change_kg=weight_change_kg,
        avg_daily_kcal=avg_daily_kcal,
    )
