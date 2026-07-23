import base64
import json
import logging
from dataclasses import dataclass

import openai
from openai import AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from bot.texts import DEFAULT_LANGUAGE, t

logger = logging.getLogger(__name__)

RETRYABLE_ERRORS = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
)

_retry_openai = retry(
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)

_LANGUAGE_NAMES = {"ru": "Russian", "en": "English", "he": "Hebrew"}


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


_TARGETS_SYSTEM_PROMPT = (
    "You are a nutrition assistant. From the user's body metrics, calculate their basal metabolic "
    "rate (BMR) and total daily energy expenditure (TDEE) accounting for activity level, then propose "
    "daily target calories and macros (protein/fat/carbs) based on their goal (loss/gain/maintain) "
    "and desired deficit/surplus percentage. "
    "Respond STRICTLY in JSON with no text outside the JSON, using this schema: "
    '{"tdee": int, "target_kcal": int, "target_protein": int, "target_fat": int, '
    '"target_carbs": int, "explanation": "a short explanation, in the language specified by the user"}'
)

_FOOD_TEXT_SYSTEM_PROMPT = (
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
    "Also write a short, casual one-sentence comment reacting to this specific meal, like a friend would — "
    "not clinical or generic. If it's notably high in fat, salt, or sugar, gently call that out (with a "
    "light, non-judgmental tone); if it's balanced or nutritious, say something encouraging; otherwise a "
    "brief neutral remark is fine. Base it on the actual numbers, not a template. "
    "Respond STRICTLY in JSON with no text outside the JSON, using this schema: "
    '{"items": [{"name": str, "grams": number, "kcal": number, "protein": number, "fat": number, "carbs": number}], '
    '"meal_total": {"kcal": number, "protein": number, "fat": number, "carbs": number}, "comment": str}. '
    "If the text doesn't describe food at all and there's nothing to parse, return items: []."
)

_FOOD_PHOTO_SYSTEM_PROMPT = (
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
    "marketing claim like \"18g protein\" but no full table), FIRST try to identify the exact product and "
    "brand from the packaging, and if you recognize it as a real, well-known product you have reliable "
    "general knowledge about from training, use its known typical nutrition facts (per 100g) as the basis "
    "for your answer, scaled to the amount eaten — mention in the comment that this is from general "
    "knowledge of the product, not read directly off this photo, so the user knows to double check if it "
    "matters. Only if you cannot identify the product with real confidence, return items: [] and explain "
    'in a separate "note" field what is missing. NEVER invent 0 or any other number when you have neither '
    "photo data nor reliable product knowledge to base it on. "
    "Otherwise also write a short, casual one-sentence comment "
    "reacting to this specific food, like a friend would — not clinical or generic. If it's notably high "
    "in fat, salt, or sugar, gently call that out (light, non-judgmental tone); if it's balanced or "
    "nutritious, say something encouraging. Base it on the actual numbers, not a template. "
    "Respond STRICTLY in JSON with no text outside the JSON, using this schema: "
    '{"items": [{"name": str, "grams": number, "kcal": number, "protein": number, "fat": number, "carbs": number}], '
    '"meal_total": {"kcal": number, "protein": number, "fat": number, "carbs": number}, "note": str, "comment": str}'
)


def _known_items_hint(known_items: list[dict] | None) -> str:
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


def _comment_language_hint(lang: str) -> str:
    return f"\n\nWrite the \"comment\" field in {_LANGUAGE_NAMES.get(lang, 'English')}."


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


def _num(value, default: float = 0.0) -> float:
    """Coerces a JSON value to float, treating None/missing (the model sometimes emits
    null instead of omitting a field) as `default` rather than raising."""
    return float(value) if value is not None else default


def _parse_food_json(data: dict, lang: str) -> FoodParseResult:
    items = [
        FoodItem(
            name=item["name"],
            grams=_num(item.get("grams")),
            kcal=_num(item.get("kcal")),
            protein=_num(item.get("protein")),
            fat=_num(item.get("fat")),
            carbs=_num(item.get("carbs")),
        )
        for item in data.get("items", [])
    ]
    if not items:
        raise FoodParseError(data.get("note") or t(lang, "ai_no_items_recognized"))

    total = data.get("meal_total") or {}
    meal_total = FoodItem(
        name="Total",
        grams=sum(i.grams for i in items),
        kcal=_num(total.get("kcal"), sum(i.kcal for i in items)),
        protein=_num(total.get("protein"), sum(i.protein for i in items)),
        fat=_num(total.get("fat"), sum(i.fat for i in items)),
        carbs=_num(total.get("carbs"), sum(i.carbs for i in items)),
    )
    return FoodParseResult(items=items, meal_total=meal_total, comment=data.get("comment") or "")


class OpenAIService:
    def __init__(self, api_key: str, text_model: str, vision_model: str):
        self._client = AsyncOpenAI(api_key=api_key)
        self._text_model = text_model
        self._vision_model = vision_model

    async def validate_api_key(self) -> None:
        try:
            await self._client.models.list()
        except openai.AuthenticationError as e:
            raise ApiKeyInvalidError(str(e)) from e

    async def _chat_json(self, model: str, messages: list[dict], lang: str = DEFAULT_LANGUAGE) -> dict:
        async def _call(msgs: list[dict]) -> dict:
            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=msgs,
                    response_format={"type": "json_object"},
                )
            except openai.AuthenticationError as e:
                raise ApiKeyInvalidError(str(e)) from e
            content = response.choices[0].message.content
            return json.loads(content)

        call_with_retry = _retry_openai(_call)
        try:
            return await call_with_retry(messages)
        except json.JSONDecodeError:
            logger.warning("OpenAI returned invalid JSON, retrying once with a corrective message")
            corrective = messages + [
                {"role": "user", "content": "Your previous response was not valid JSON. Respond with ONLY valid JSON."}
            ]
            try:
                return await call_with_retry(corrective)
            except json.JSONDecodeError as e:
                raise FoodParseError(t(lang, "ai_invalid_response")) from e

    async def _chat_text(self, model: str, messages: list[dict]) -> str:
        async def _call(msgs: list[dict]) -> str:
            try:
                response = await self._client.chat.completions.create(model=model, messages=msgs)
            except openai.AuthenticationError as e:
                raise ApiKeyInvalidError(str(e)) from e
            return response.choices[0].message.content.strip()

        return await _retry_openai(_call)(messages)

    async def get_food_advice(
        self,
        *,
        food_description: str,
        remaining_kcal: float,
        remaining_protein: float,
        remaining_fat: float,
        remaining_carbs: float,
        goal: str,
        lang: str = DEFAULT_LANGUAGE,
    ) -> str:
        system_prompt = (
            "You are a friendly, practical nutrition coach. The user is asking whether they should eat "
            "something right now. Given how many calories/macros they have left in their daily budget and "
            "their goal, give brief, casual, human advice — 2-4 sentences, not clinical. Say clearly whether "
            "it fits, fits in moderation, or would blow the budget, and why, based on the actual numbers. "
            "Be careful with quantities: a count of whole items (e.g. '10 watermelons', '5 pizzas') means "
            "that many WHOLE units at their typical real-world weight each — not 10x a 100g reference "
            "serving. Do the math for the realistic total weight/calories first. If the total is absurdly "
            "large for a human to physically eat, say so plainly and with a bit of humor instead of just "
            "approving a lowball number. "
            f"Write your entire reply in {_LANGUAGE_NAMES.get(lang, 'English')}, as plain text, no JSON, no markdown."
        )
        user_prompt = (
            f"Remaining today: {remaining_kcal:.0f} kcal, {remaining_protein:.0f}g protein, "
            f"{remaining_fat:.0f}g fat, {remaining_carbs:.0f}g carbs. Goal: {goal}. "
            f'They\'re thinking about eating: "{food_description}"'
        )
        return await self._chat_text(
            self._text_model,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

    async def compute_nutrition_targets(
        self,
        *,
        weight: float,
        height: float,
        age: int,
        gender: str,
        activity_level: str,
        goal: str,
        deficit_percent: int | None,
        lang: str = DEFAULT_LANGUAGE,
    ) -> TargetsResult:
        user_prompt = (
            f"Weight: {weight} kg, height: {height} cm, age: {age}, gender: {gender}, "
            f"activity level: {activity_level}, goal: {goal}, "
            f"desired deficit/surplus %: {deficit_percent if deficit_percent is not None else 'suggest one yourself'}. "
            f"Write the \"explanation\" field in {_LANGUAGE_NAMES.get(lang, 'English')}."
        )
        data = await self._chat_json(
            self._text_model,
            [
                {"role": "system", "content": _TARGETS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        return TargetsResult(
            tdee=int(data["tdee"]),
            target_kcal=int(data["target_kcal"]),
            target_protein=int(data["target_protein"]),
            target_fat=int(data["target_fat"]),
            target_carbs=int(data["target_carbs"]),
            explanation=data.get("explanation", ""),
        )

    async def parse_food_text(
        self, text: str, known_items: list[dict] | None = None, lang: str = DEFAULT_LANGUAGE
    ) -> FoodParseResult:
        user_content = text + _known_items_hint(known_items) + _comment_language_hint(lang)
        data = await self._chat_json(
            self._text_model,
            [
                {"role": "system", "content": _FOOD_TEXT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            lang=lang,
        )
        return _parse_food_json(data, lang)

    async def parse_food_photo(
        self,
        image_bytes: bytes,
        mime_type: str,
        grams_hint: str | None,
        known_items: list[dict] | None = None,
        lang: str = DEFAULT_LANGUAGE,
    ) -> FoodParseResult:
        b64_image = base64.b64encode(image_bytes).decode()
        user_content = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{b64_image}"},
            }
        ]
        text_hint = (
            (grams_hint or "Amount in grams not specified, estimate from the photo if possible.")
            + _known_items_hint(known_items)
            + _comment_language_hint(lang)
        )
        user_content.append({"type": "text", "text": text_hint})

        data = await self._chat_json(
            self._vision_model,
            [
                {"role": "system", "content": _FOOD_PHOTO_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            lang=lang,
        )
        return _parse_food_json(data, lang)


_service_cache: dict[int, OpenAIService] = {}


def invalidate_user_service(user_id: int) -> None:
    _service_cache.pop(user_id, None)


def get_cached_service(user_id: int) -> OpenAIService | None:
    return _service_cache.get(user_id)


def cache_service(user_id: int, service: OpenAIService) -> None:
    _service_cache[user_id] = service


async def get_service_for_user(db, user_id: int, text_model: str, vision_model: str) -> OpenAIService | None:
    """Builds (or returns cached) OpenAIService for a user from their stored encrypted key.
    Returns None if the user has no key stored yet. Raises InvalidToken if ENCRYPTION_KEY
    can no longer decrypt the stored key — callers should treat this like an invalid API key."""
    from bot.db import users as users_repo
    from bot.services.encryption import decrypt_api_key

    cached = get_cached_service(user_id)
    if cached is not None:
        return cached

    encrypted = await users_repo.get_encrypted_api_key(db, user_id)
    if encrypted is None:
        return None

    raw_key = decrypt_api_key(encrypted)
    service = OpenAIService(api_key=raw_key, text_model=text_model, vision_model=vision_model)
    cache_service(user_id, service)
    return service
