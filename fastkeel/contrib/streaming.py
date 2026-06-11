# fastkeel/contrib/streaming.py
from collections.abc import AsyncGenerator
from typing import Any

from fastapi.responses import StreamingResponse


class SSEStreamer:
    """SSE (Server-Sent Events) streaming response utilities."""

    @staticmethod
    def from_generator(gen: AsyncGenerator[str, None]) -> StreamingResponse:
        """Wrap an async string generator as an SSE StreamingResponse."""
        async def event_stream() -> AsyncGenerator[bytes, None]:
            async for chunk in gen:
                yield f"data: {chunk}\n\n".encode("utf-8")

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
        )

    @staticmethod
    async def from_llm_stream(
        llm_client: Any,
        messages: list[dict],
    ) -> StreamingResponse:
        """Convenience: wrap LLM streaming response as SSE."""
        return SSEStreamer.from_generator(
            llm_client.chat_stream(messages)
        )
