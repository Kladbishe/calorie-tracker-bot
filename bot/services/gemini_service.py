import json
import logging

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from bot.services.ai_types import (
    ADVICE_SYSTEM_PROMPT_TEMPLATE,
    FOOD_PHOTO_SYSTEM_PROMPT,
    FOOD_TEXT_SYSTEM_PROMPT,
    LANGUAGE_NAMES,
    TARGETS_SYSTEM_PROMPT,
    ApiKeyInvalidError,
    FoodParseError,
    FoodParseResult,
    TargetsResult,
    comment_language_hint,
    known_items_hint,
    parse_food_json,
)
from bot.texts import DEFAULT_LANGUAGE, t

logger = logging.getLogger(__name__)

# 400 covers Gemini's "API key not valid" response; 401/403 are the more conventional auth codes.
_AUTH_ERROR_CODES = {400, 401, 403}

_retry_gemini = retry(
    retry=retry_if_exception_type(genai_errors.ServerError),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)


class GeminiService:
    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def validate_api_key(self) -> None:
        try:
            pager = await self._client.aio.models.list()
            async for _ in pager:
                break
        except genai_errors.ClientError as e:
            if e.code in _AUTH_ERROR_CODES:
                raise ApiKeyInvalidError(str(e)) from e
            raise

    async def _generate_json(self, messages: list[dict], lang: str = DEFAULT_LANGUAGE) -> dict:
        system_instruction, contents = _split_system_prompt(messages)

        async def _call(sys_instruction: str) -> dict:
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=sys_instruction,
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
            except genai_errors.ClientError as e:
                if e.code in _AUTH_ERROR_CODES:
                    raise ApiKeyInvalidError(str(e)) from e
                raise
            return json.loads(response.text)

        call_with_retry = _retry_gemini(_call)
        try:
            return await call_with_retry(system_instruction)
        except json.JSONDecodeError:
            logger.warning("Gemini returned invalid JSON, retrying once with a corrective instruction")
            corrective = system_instruction + "\n\nYour previous response was not valid JSON. Respond with ONLY valid JSON."
            try:
                return await call_with_retry(corrective)
            except json.JSONDecodeError as e:
                raise FoodParseError(t(lang, "ai_invalid_response")) from e

    async def _generate_text(self, system_instruction: str, user_text: str) -> str:
        async def _call() -> str:
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=user_text,
                    config=types.GenerateContentConfig(system_instruction=system_instruction),
                )
            except genai_errors.ClientError as e:
                if e.code in _AUTH_ERROR_CODES:
                    raise ApiKeyInvalidError(str(e)) from e
                raise
            return response.text.strip()

        return await _retry_gemini(_call)()

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
        system_prompt = ADVICE_SYSTEM_PROMPT_TEMPLATE.format(language=LANGUAGE_NAMES.get(lang, "English"))
        user_prompt = (
            f"Remaining today: {remaining_kcal:.0f} kcal, {remaining_protein:.0f}g protein, "
            f"{remaining_fat:.0f}g fat, {remaining_carbs:.0f}g carbs. Goal: {goal}. "
            f'They\'re thinking about eating: "{food_description}"'
        )
        return await self._generate_text(system_prompt, user_prompt)

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
            f"Write the \"explanation\" field in {LANGUAGE_NAMES.get(lang, 'English')}."
        )
        data = await self._generate_json(
            [
                {"role": "system", "content": TARGETS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
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
        user_content = text + known_items_hint(known_items) + comment_language_hint(lang)
        data = await self._generate_json(
            [
                {"role": "system", "content": FOOD_TEXT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            lang=lang,
        )
        return parse_food_json(data, lang)

    async def parse_food_photo(
        self,
        image_bytes: bytes,
        mime_type: str,
        grams_hint: str | None,
        known_items: list[dict] | None = None,
        lang: str = DEFAULT_LANGUAGE,
    ) -> FoodParseResult:
        text_hint = (
            (grams_hint or "Amount in grams not specified, estimate from the photo if possible.")
            + known_items_hint(known_items)
            + comment_language_hint(lang)
        )

        async def _call(sys_instruction: str) -> dict:
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), text_hint],
                    config=types.GenerateContentConfig(
                        system_instruction=sys_instruction,
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
            except genai_errors.ClientError as e:
                if e.code in _AUTH_ERROR_CODES:
                    raise ApiKeyInvalidError(str(e)) from e
                raise
            return json.loads(response.text)

        call_with_retry = _retry_gemini(_call)
        try:
            data = await call_with_retry(FOOD_PHOTO_SYSTEM_PROMPT)
        except json.JSONDecodeError:
            logger.warning("Gemini returned invalid JSON for a photo, retrying once")
            corrective = FOOD_PHOTO_SYSTEM_PROMPT + "\n\nYour previous response was not valid JSON. Respond with ONLY valid JSON."
            try:
                data = await call_with_retry(corrective)
            except json.JSONDecodeError as e:
                raise FoodParseError(t(lang, "ai_invalid_response")) from e
        return parse_food_json(data, lang)


def _split_system_prompt(messages: list[dict]) -> tuple[str, str]:
    """The prompt-building helpers in ai_types.py produce {role, content} message lists;
    Gemini takes a separate system_instruction plus plain contents instead. Both callers here
    only ever build a 2-message [system, user] list, so this just pulls those apart."""
    system_instruction = next(m["content"] for m in messages if m["role"] == "system")
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    return system_instruction, user_content


_service_cache: dict[int, GeminiService] = {}


def invalidate_user_service(user_id: int) -> None:
    _service_cache.pop(user_id, None)


def get_cached_service(user_id: int) -> GeminiService | None:
    return _service_cache.get(user_id)


def cache_service(user_id: int, service: GeminiService) -> None:
    _service_cache[user_id] = service


async def get_service_for_user(db, user_id: int, settings) -> GeminiService | None:
    from bot.db import users as users_repo
    from bot.services.encryption import decrypt_api_key

    cached = get_cached_service(user_id)
    if cached is not None:
        return cached

    encrypted = await users_repo.get_encrypted_api_key(db, user_id)
    if encrypted is None:
        return None

    raw_key = decrypt_api_key(encrypted)
    service = GeminiService(api_key=raw_key, model=settings.gemini_model)
    cache_service(user_id, service)
    return service
