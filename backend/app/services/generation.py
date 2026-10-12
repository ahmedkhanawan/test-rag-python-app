import logging

import openai
from openai import OpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class GenerationError(RuntimeError):
    """The LLM call failed or is not configured."""


class GenerationService:
    """The only place that calls the OpenAI chat model."""

    def __init__(self, client: OpenAI | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.openai_chat_model
        self._client = client
        self._api_key = settings.openai_api_key

    def _get_client(self) -> OpenAI:
        if self._client is None:
            if not self._api_key:
                raise GenerationError("OPENAI_API_KEY is not configured")
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except openai.OpenAIError as exc:
            logger.error("OpenAI generation failed: %s", type(exc).__name__)
            raise GenerationError(f"OpenAI generation failed ({type(exc).__name__})") from exc
        content = (response.choices[0].message.content or "").strip() if response.choices else ""
        if not content:
            raise GenerationError("OpenAI returned an empty answer")
        return content
