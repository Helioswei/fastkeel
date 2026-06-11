# fastkeel/contrib/llm.py
import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from fastkeel.core.config import Config

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM API client with retry, rate limiting, and structured output."""

    def __init__(self, config: Config) -> None:
        self.api_base = config.llm_api_base.rstrip("/")
        self.model = config.llm_model
        self.max_retries = config.llm_max_retries
        self.semaphore = asyncio.Semaphore(config.llm_rate_limit)
        self._client = httpx.AsyncClient(
            base_url=self.api_base,
            headers={"Authorization": f"Bearer {config.llm_api_key}"},
            timeout=60,
        )

    async def chat(self, messages: list[dict], **kwargs: Any) -> str:
        """Send a chat request and return the response text."""
        payload = {
            "model": self.model,
            "messages": messages,
            **kwargs,
        }

        for attempt in range(self.max_retries + 1):
            async with self.semaphore:
                try:
                    response = await self._client.post("/chat/completions", json=payload)
                except httpx.RequestError as e:
                    if attempt < self.max_retries:
                        wait = 2 ** attempt
                        logger.warning("Request failed (attempt %d): %s, retrying in %ds", attempt + 1, e, wait)
                        await asyncio.sleep(wait)
                        continue
                    raise RuntimeError(f"API request failed after {self.max_retries} retries") from e

                if response.status_code in (429, 502, 503, 504) and attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning("HTTP %d (attempt %d), retrying in %ds", response.status_code, attempt + 1, wait)
                    await asyncio.sleep(wait)
                    continue

                if response.status_code != 200:
                    raise RuntimeError(
                        f"API error: HTTP {response.status_code} — {response.text[:200]}"
                    )

                data = response.json()
                return data["choices"][0]["message"]["content"]

        raise RuntimeError(f"API request failed after {self.max_retries} retries")

    async def chat_stream(self, messages: list[dict], **kwargs: Any) -> AsyncGenerator[str, None]:
        """Stream a chat response chunk by chunk."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            **kwargs,
        }

        async with self.semaphore:
            async with self._client.stream(
                "POST", "/chat/completions", json=payload
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content

    async def chat_structured(
        self,
        messages: list[dict],
        response_model: type[BaseModel],
        **kwargs: Any,
    ) -> BaseModel:
        """Send a chat request and parse the response as a Pydantic model."""
        text = await self.chat(messages, **kwargs)
        try:
            data = json.loads(text)
            return response_model.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(f"Failed to parse structured output: {e}") from e
