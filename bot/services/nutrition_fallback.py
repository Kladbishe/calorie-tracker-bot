from bot.services.ai_types import TargetsResult
from bot.texts import t

_ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "high": 1.725,
    "very_high": 1.9,
}

DEFAULT_DEFICIT_PERCENT = {"loss": 15, "gain": 15, "maintain": 0}


def compute_fallback_targets(
    *,
    weight: float,
    height: float,
    age: int,
    gender: str,
    activity_level: str,
    goal: str,
    deficit_percent: int | None,
    lang: str,
) -> TargetsResult:
    """Local Mifflin-St Jeor based estimate, used when the Gemini call fails so onboarding
    never gets stuck — user can still fine-tune each field afterwards."""
    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    tdee = bmr * _ACTIVITY_MULTIPLIERS.get(activity_level, 1.375)

    percent = deficit_percent if deficit_percent is not None else DEFAULT_DEFICIT_PERCENT.get(goal, 0)
    if goal == "loss":
        target_kcal = tdee * (1 - percent / 100)
    elif goal == "gain":
        target_kcal = tdee * (1 + percent / 100)
    else:
        target_kcal = tdee

    protein = weight * 1.8
    fat = weight * 1.0
    remaining_kcal = max(target_kcal - protein * 4 - fat * 9, 0)
    carbs = remaining_kcal / 4

    return TargetsResult(
        tdee=round(tdee),
        target_kcal=round(target_kcal),
        target_protein=round(protein),
        target_fat=round(fat),
        target_carbs=round(carbs),
        explanation=t(lang, "fallback_explanation"),
    )
