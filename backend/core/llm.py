"""Thin wrapper around OpenAI structured outputs.

Every call is schema-constrained: the model must return JSON matching a Pydantic
model, so there is no free-text parsing anywhere in the app.
"""

from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLM:
    def __init__(self, model: str):
        self.model = model
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        # created lazily so the API can start (and tests can run) without a key
        if self._client is None:
            self._client = AsyncOpenAI()
        return self._client

    async def structured(self, instructions: str, user: str, schema: type[T]) -> T:
        response = await self.client.responses.parse(
            model=self.model,
            instructions=instructions,
            input=user,
            text_format=schema,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("model returned no parseable output (refusal or truncation)")
        return parsed
