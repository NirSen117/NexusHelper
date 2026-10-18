"""Send a minimal, non-sensitive request to the configured Gemini and Groq models."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx


def read_backend_env() -> dict[str, str]:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    values: dict[str, str] = {}
    if not env_path.is_file():
        raise SystemExit("Backend .env not found. Run this from the NexusHelper project setup.")
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


async def check_gemini(client: httpx.AsyncClient, env: dict[str, str]) -> str:
    key = env.get("GEMINI_API_KEY", "")
    model = env.get("GEMINI_MODEL", "gemini-3.8-flash")
    if not key:
        return "Gemini: SKIPPED — GEMINI_API_KEY is empty in the root .env"
    try:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": key},
            json={
                "contents": [{"role": "user", "parts": [{"text": "Reply with exactly API_OK."}]}],
                "generationConfig": {"maxOutputTokens": 8},
            },
        )
    except httpx.HTTPError as exc:
        return f"Gemini: NO CONNECTION — {type(exc).__name__}; the key could not be verified"
    return _http_result("Gemini", model, response.status_code)


async def check_groq(client: httpx.AsyncClient, env: dict[str, str]) -> str:
    key = env.get("GROQ_API_KEY", "")
    model = env.get("GROQ_MODEL", "openai/gpt-oss-20b")
    if not key:
        return "Groq: SKIPPED — GROQ_API_KEY is empty in the root .env"
    try:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly API_OK."}],
                "max_tokens": 8,
                "temperature": 0,
            },
        )
    except httpx.HTTPError as exc:
        return f"Groq: NO CONNECTION — {type(exc).__name__}; the key could not be verified"
    return _http_result("Groq", model, response.status_code)


def _http_result(provider: str, model: str, status: int) -> str:
    if 200 <= status < 300:
        return f"{provider}: PASS — HTTP {status}, model {model} accepted the test request"
    if status in (401, 403):
        reason = "key rejected or does not have access"
    elif status == 404:
        reason = "model or endpoint not found"
    elif status == 429:
        reason = "rate limit or quota reached (key was recognized by the API)"
    else:
        reason = "provider returned an error; check model access/configuration"
    return f"{provider}: FAIL — HTTP {status}, {reason}"


async def main() -> None:
    env = read_backend_env()
    async with httpx.AsyncClient(timeout=20) as client:
        results = await asyncio.gather(check_gemini(client, env), check_groq(client, env))
    print("NexusHelper AI credential check (keys and response bodies are never printed)")
    for result in results:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
