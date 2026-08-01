"""Data types, prompts, and JSON post-processing used by bot/services/gemini_service.py.
Kept separate from the client/API-call code so prompt wording and validation logic are
easy to find and edit in one place."""

from dataclasses import dataclass

from bot.texts import DEFAULT_LANGUAGE, t

LANGUAGE_NAMES = {"ru": "Russian", "en": "English", "he": "Hebrew"}


class ApiKeyInvalidError(Exception):
    pass


class FoodParseError(Exception):
    pass


@dataclass
class TargetsResult:
    tdee: int
    target_kcal: int
    target_protein: int
    target_fat: int
    target_carbs: int
    explanation: str = ""


@dataclass
class FoodItem:
    name: str
    grams: float
    kcal: float
    protein: float
    fat: float
    carbs: float


@dataclass
class FoodParseResult:
    items: list[FoodItem]
    meal_total: FoodItem
    comment: str = ""


TARGETS_SYSTEM_PROMPT = (
    "You are a nutrition assistant. From the user's body metrics, calculate their basal metabolic "
    "rate (BMR) and total daily energy expenditure (TDEE) accounting for activity level, then propose "
    "daily target calories and macros (protein/fat/carbs) based on their goal (loss/gain/maintain) "
    "and desired deficit/surplus percentage. "
    "Respond STRICTLY in JSON with no text outside the JSON, using this schema: "
    '{"tdee": int, "target_kcal": int, "target_protein": int, "target_fat": int, '
    '"target_carbs": int, "explanation": "a short explanation, in the language specified by the user"}'
)

FOOD_TEXT_SYSTEM_PROMPT = (
    "You are a calorie-counting assistant. The user describes food they ate in free-form text "
    "(any language), with or without weights or quantities. Identify each food item and estimate its "
    "weight in grams: use the stated amount if given, otherwise estimate from any portion description "
    "in the message, and if there's neither — assume a typical/average real-world serving size for that "
    "specific dish (e.g. a sushi roll, a slice of pizza, a cup of coffee all have reasonable typical "
    "portions) rather than giving up. Only return an empty item for genuinely unidentifiable text, never "
    "just because no quantity was mentioned. Calculate calories and macros for each item, and sum the total. "
    "IMPORTANT: if the user THEMSELVES states a calorie or macro value — per 100g, per portion, per "
    "slice/piece — use exactly those figures as the basis for your calculation (scaled to the actual "
    "amount eaten), not your own independent estimate. For example, if they say '100g is 250 kcal' and "
    "435g were eaten, the result must be 250 * 435 / 100 = 1087.5 kcal, not your own rough guess for the dish. "
    "If the user describes a fraction of a whole (e.g. 'cut into 8 slices, ate 6'), carefully compute the "
    "actual weight eaten as that fraction of the total weight. If they instead give a count of WHOLE items "
    "(e.g. '10 watermelons', '3 pizzas'), multiply that many whole units at their typical real-world weight "
    "each — not a single small reference serving. "
    "When the user specifies a product variant — fat percentage, brand, cooking method, or similar — you "
    "MUST base your numbers on that exact variant, never silently substitute a different one (e.g. '5% "
    "cottage cheese' must use 5% cottage cheese's values, not 0% or 9%; '3% milk' isn't skim milk). Note: "
    "for dairy (cottage cheese, yogurt, milk), the fat % label changes mainly the FAT and calorie content — "
    "protein stays roughly similar (often 11-18g/100g for cottage cheese) across fat-percentage variants of "
    "the same product, so don't scale protein down just because the fat % is low. "
    "SELF-CHECK before answering: for each item, kcal should roughly equal protein*4 + fat*9 + carbs*4 "
    "(the standard Atwater formula, small rounding differences are fine). If your kcal figure doesn't "
    "roughly match that formula given your own protein/fat/carbs numbers, your numbers are inconsistent — "
    "recompute rather than reporting mismatched values. "
    "Also write a short, casual one-sentence comment reacting to this specific meal, like a friend would — "
    "not clinical or generic. If it's notably high in fat, salt, or sugar, gently call that out (with a "
    "light, non-judgmental tone); if it's balanced or nutritious, say something encouraging; otherwise a "
    "brief neutral remark is fine. Base it on the actual numbers, not a template. "
    "Respond STRICTLY in JSON with no text outside the JSON, using this schema — note \"reasoning\" comes "
    "FIRST: work through your per-100g reference values and the scaling math there for every item, in 1-2 "
    "sentences per item, BEFORE settling on the final numbers below, so the final numbers follow your own "
    "worked reasoning rather than being guessed independently of it: "
    '{"reasoning": str, "items": [{"name": str, "grams": number, "kcal": number, "protein": number, "fat": number, "carbs": number}], '
    '"meal_total": {"kcal": number, "protein": number, "fat": number, "carbs": number}, "comment": str}. '
    "If the text doesn't describe food at all and there's nothing to parse, return items: []."
)

FOOD_PHOTO_SYSTEM_PROMPT = (
    "You are a calorie-counting assistant. The user sent a photo of a product label or the food itself, "
    "which may show calories and macros per 100g. The caption or a follow-up message may state how many "
    "grams they ate, and sometimes explicit calories/macros as text. Read the data from the photo, and "
    "scale it to the stated amount if needed. The photo may be rotated, sideways, or at an angle — try to "
    "read the label regardless of its orientation before giving up. "
    "NUTRITION TABLES ARE EASY TO MISREAD — be careful: match each number to its printed row LABEL, don't "
    "guess by position, since rows are often close together (energy/calories, protein, fat — of which "
    "saturated, carbohydrate — of which sugars, fiber, sodium/salt are the usual rows, sometimes translated "
    "or abbreviated in the label's language). Protein and fiber/carbs are the rows most often confused — "
    "double-check you're reading the protein row specifically, not fiber, sugar, or sodium. "
    "If the label has multiple value columns (e.g. 'per 100g' and 'per serving'), first decide which ONE "
    "column matches the amount you're calculating for, then read EVERY row (calories, protein, fat, carbs) "
    "from that SAME column only — never mix values from different columns for different rows in one answer. "
    "As a sanity check, the per-serving column's numbers should be roughly proportional to the per-100g "
    "column's numbers scaled by the serving size; if they don't line up, you've likely misaligned rows or "
    "columns — re-examine before answering. "
    "IMPORTANT: if the caption states a calorie or macro value THEMSELVES (per 100g, per portion, per "
    "slice/piece), use exactly those figures as the basis for your calculation, not your own estimate "
    "from the photo. If the user describes a fraction of a whole (e.g. 'cut into 8 slices, ate 6'), "
    "carefully compute the actual weight eaten as that fraction of the total weight. "
    "If the full nutrition table isn't visible (e.g. only the front of the package is shown, with maybe a "
    "marketing claim like \"18g protein\" but no full table), you should ACTIVELY try to identify the exact "
    "product and brand from the packaging — logo, name, any visible text — before considering giving up. "
    "Brand-name packaged products (protein bars, snacks, drinks, etc.) are usually products you already "
    "have real knowledge about from training; use its known typical nutrition facts (per 100g) as the basis "
    "for your answer, scaled to the amount eaten. Giving up should be the exception, not the default — only "
    "do it when you genuinely don't recognize the product at all, not just because the full table isn't in "
    "frame. When you do use general knowledge instead of the photo, say so in the comment so the user knows "
    "to double check if it matters. If you truly cannot identify the product with real confidence, return "
    "items: [] and explain "
    'in a separate "note" field what is missing. NEVER invent 0 or any other number when you have neither '
    "photo data nor reliable product knowledge to base it on. "
    "SELF-CHECK before answering: for each item, kcal should roughly equal protein*4 + fat*9 + carbs*4 "
    "(the standard Atwater formula, small rounding differences are fine) — if it doesn't, your numbers are "
    "inconsistent with each other; recompute rather than reporting mismatched values. "
    "Otherwise also write a short, casual one-sentence comment "
    "reacting to this specific food, like a friend would — not clinical or generic. If it's notably high "
    "in fat, salt, or sugar, gently call that out (light, non-judgmental tone); if it's balanced or "
    "nutritious, say something encouraging. Base it on the actual numbers, not a template. "
    "Respond STRICTLY in JSON with no text outside the JSON, using this schema — note \"reasoning\" comes "
    "FIRST: work through what you can read from the photo (or your per-100g reference knowledge of the "
    "product) and the scaling math, in 1-2 sentences per item, BEFORE settling on the final numbers below. "
    '{"reasoning": str, "items": [{"name": str, "grams": number, "kcal": number, "protein": number, "fat": number, "carbs": number}], '
    '"meal_total": {"kcal": number, "protein": number, "fat": number, "carbs": number}, "note": str, "comment": str}'
)

ADVICE_SYSTEM_PROMPT_TEMPLATE = (
    "You are a friendly, practical nutrition coach. The user is asking whether they should eat "
    "something right now. Given how many calories/macros they have left in their daily budget and "
    "their goal, give brief, casual, human advice — 2-4 sentences, not clinical. Say clearly whether "
    "it fits, fits in moderation, or would blow the budget, and why, based on the actual numbers. "
    "Be careful with quantities: a count of whole items (e.g. '10 watermelons', '5 pizzas') means "
    "that many WHOLE units at their typical real-world weight each — not 10x a 100g reference "
    "serving. Do the math for the realistic total weight/calories first. If the total is absurdly "
    "large for a human to physically eat, say so plainly and with a bit of humor instead of just "
    "approving a lowball number. "
    "Write your entire reply in {language}, as plain text, no JSON, no markdown."
)


def build_advice_prompt(
    *,
    food_description: str,
    remaining_kcal: float,
    remaining_protein: float,
    remaining_fat: float,
    remaining_carbs: float,
    goal: str,
) -> str:
    return (
        f"Remaining today: {remaining_kcal:.0f} kcal, {remaining_protein:.0f}g protein, "
        f"{remaining_fat:.0f}g fat, {remaining_carbs:.0f}g carbs. Goal: {goal}. "
        f'They\'re thinking about eating: "{food_description}"'
    )


def known_items_hint(known_items: list[dict] | None) -> str:
    if not known_items:
        return ""
    lines = "\n".join(
        f'- "{i["display_name"]}": {i["kcal_per_100g"]} kcal, P {i["protein_per_100g"]}, '
        f'F {i["fat_per_100g"]}, C {i["carbs_per_100g"]} per 100g'
        for i in known_items
    )
    return (
        "\n\nThis user has these previously known foods (values per 100g). If an item in the "
        "message resembles one of them, use exactly these per-100g values and scale to the stated "
        f"weight instead of estimating from scratch:\n{lines}"
    )


def comment_language_hint(lang: str) -> str:
    language = LANGUAGE_NAMES.get(lang, "English")
    return f'\n\nWrite the "comment" field, and every item\'s "name" field, in {language} — not English, unless {language} is English.'


def food_item_to_dict(item: FoodItem) -> dict:
    return {"name": item.name, "grams": item.grams, "kcal": item.kcal, "protein": item.protein, "fat": item.fat, "carbs": item.carbs}


def food_parse_result_to_dict(result: FoodParseResult) -> dict:
    return {
        "items": [food_item_to_dict(i) for i in result.items],
        "meal_total": food_item_to_dict(result.meal_total),
        "comment": result.comment,
    }


def food_parse_result_from_dict(data: dict) -> FoodParseResult:
    return FoodParseResult(
        items=[FoodItem(**i) for i in data["items"]],
        meal_total=FoodItem(**data["meal_total"]),
        comment=data.get("comment", ""),
    )


def num(value, default: float = 0.0) -> float:
    """Coerces a JSON value to float, treating None/missing (models sometimes emit
    null instead of omitting a field) as `default` rather than raising."""
    return float(value) if value is not None else default


def reconcile_kcal(kcal: float, protein: float, fat: float, carbs: float) -> float:
    """Models sometimes report a kcal figure that's inconsistent with their own protein/fat/
    carbs numbers (real example: P16.8/F9.6/C4.8 reported as 96 kcal, when the Atwater formula
    on those exact macros gives ~173 kcal). In testing, the macros were consistently closer to
    reality than the model's own kcal arithmetic, so when they disagree by a lot, trust the
    macros and recompute kcal deterministically instead. (This slightly under/overcounts drinks
    with significant alcohol, which isn't tracked in our schema — an accepted, rare tradeoff.)"""
    atwater_kcal = protein * 4 + fat * 9 + carbs * 4
    if atwater_kcal <= 0:
        return kcal
    if abs(kcal - atwater_kcal) / atwater_kcal > 0.15:
        return round(atwater_kcal, 1)
    return kcal


def parse_food_json(data: dict, lang: str) -> FoodParseResult:
    items = []
    for item in data.get("items", []):
        protein, fat, carbs = num(item.get("protein")), num(item.get("fat")), num(item.get("carbs"))
        items.append(
            FoodItem(
                name=item["name"],
                grams=num(item.get("grams")),
                kcal=reconcile_kcal(num(item.get("kcal")), protein, fat, carbs),
                protein=protein,
                fat=fat,
                carbs=carbs,
            )
        )
    if not items:
        raise FoodParseError(data.get("note") or t(lang, "ai_no_items_recognized"))

    total = data.get("meal_total") or {}
    total_protein = num(total.get("protein"), sum(i.protein for i in items))
    total_fat = num(total.get("fat"), sum(i.fat for i in items))
    total_carbs = num(total.get("carbs"), sum(i.carbs for i in items))
    meal_total = FoodItem(
        name="Total",
        grams=sum(i.grams for i in items),
        kcal=reconcile_kcal(num(total.get("kcal"), sum(i.kcal for i in items)), total_protein, total_fat, total_carbs),
        protein=total_protein,
        fat=total_fat,
        carbs=total_carbs,
    )
    return FoodParseResult(items=items, meal_total=meal_total, comment=data.get("comment") or "")
