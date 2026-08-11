"""Streaming chat call to Ollama (reusing the cv-analysis-agent streaming pattern)."""
from typing import Iterator

import ollama

from app.config import settings


def stream_chat(system_prompt: str, user_prompt: str) -> Iterator[str]:
    """Stream token deltas from Ollama for one request. Yields text fragments."""
    client = ollama.Client(host=settings.OLLAMA_HOST)
    stream = client.chat(
        model=settings.OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
    )
    for part in stream:
        yield part["message"]["content"]
