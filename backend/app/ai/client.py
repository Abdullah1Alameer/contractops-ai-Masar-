"""The ONLY file in the repo allowed to import openai.

Everything goes through complete_json(system, user, schema) so the provider
can be swapped later by rewriting this single function.
"""
import json

from openai import OpenAI

from ..config import AI_MODEL, OPENAI_API_KEY


class AIError(Exception):
    """Raised when the model failed to return valid JSON after one retry."""


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def complete_json(system: str, user: str, schema: dict) -> dict:
    """Call the chat completions API with structured outputs (strict json_schema).

    `schema` is the full json_schema wrapper: {"name": ..., "strict": True, "schema": {...}}.
    Malformed JSON → one retry with a corrective message → AIError.
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    for _attempt in range(2):
        resp = _get_client().chat.completions.create(
            model=AI_MODEL,
            temperature=0,
            response_format={"type": "json_schema", "json_schema": schema},
            messages=messages,
        )
        content = resp.choices[0].message.content or ""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": "Return ONLY valid JSON matching the schema."})
    raise AIError("ai_failed")
