"""Thin LLM client — no LangChain. Structured JSON outputs only."""

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from job_os.config import LLMProvider, get_settings
from job_os.services.credentials_service import CredentialsService

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    def __init__(self) -> None:
        self._settings = get_settings()

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        response_model: type[T],
        temperature: float = 0.2,
    ) -> T:
        raw = await self._complete_raw(system=system, user=user, temperature=temperature)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned non-JSON: {raw[:500]}") from exc
        return response_model.model_validate(data)

    async def _complete_raw(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
    ) -> str:
        settings = self._settings
        if settings.llm_provider == LLMProvider.ANTHROPIC:
            return await self._anthropic(system, user, temperature)
        if settings.llm_provider == LLMProvider.GEMINI:
            return await self._gemini(system, user, temperature)
        return await self._openai(system, user, temperature)

    async def _openai(self, system: str, user: str, temperature: float) -> str:
        from openai import AsyncOpenAI

        settings = self._settings
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.llm_model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or "{}"

    async def _anthropic(self, system: str, user: str, temperature: float) -> str:
        from anthropic import AsyncAnthropic

        settings = self._settings
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.llm_model,
            max_tokens=4096,
            temperature=temperature,
            system=system + "\nRespond with valid JSON only.",
            messages=[{"role": "user", "content": user}],
        )
        text_blocks = [b.text for b in response.content if hasattr(b, "text")]
        return "".join(text_blocks) or "{}"

    async def _gemini(self, system: str, user: str, temperature: float) -> str:
        settings = self._settings
        gemini_key = settings.gemini_api_key or CredentialsService().load().get("gemini_api_key")
        if not gemini_key:
            raise RuntimeError("GEMINI_API_KEY not configured")

        model = settings.llm_model
        if "gemini" not in model.lower():
            model = "gemini-1.5-flash"

        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        )
        payload = {
            "system_instruction": {
                "parts": [{"text": system + "\nRespond with valid JSON only."}],
            },
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
            },
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                endpoint,
                params={"key": gemini_key},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates") or []
        if not candidates:
            return "{}"
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        return text or "{}"

    async def complete_text(self, *, system: str, user: str, temperature: float = 0.3) -> str:
        settings = self._settings
        if settings.llm_provider == LLMProvider.ANTHROPIC:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            response = await client.messages.create(
                model=settings.llm_model,
                max_tokens=4096,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return "".join(b.text for b in response.content if hasattr(b, "text"))
        if settings.llm_provider == LLMProvider.GEMINI:
            raw = await self._gemini(system, user, temperature)
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    if "content_text" in data:
                        return str(data["content_text"])
                    return json.dumps(data)
            except json.JSONDecodeError:
                pass
            return raw

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.llm_model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""
