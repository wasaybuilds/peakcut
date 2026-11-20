"""chat_json(): ask the LLM chain for a JSON answer, falling back on errors/rate limits."""

import json
import logging
import re
import time
from typing import Any

from app.config import Settings, get_settings
from app.llm.providers import PROVIDERS, ProviderSpec, configured_chain

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


def strip_code_fence(text: str) -> str:
    """Remove ```json fences and any <think> block some reasoning models emit.

    Adapted from MoneyPrinterTurbo's _strip_code_fence (MIT, see NOTICE).
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    if m:
        text = m.group(1).strip()
    return text


def parse_json(text: str) -> Any:
    text = strip_code_fence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # last resort: grab the outermost {...} or [...]
        m = re.search(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(1))


def _call_openai_compatible(spec: ProviderSpec, settings: Settings, system: str, user: str) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=getattr(settings, spec.key_attr), base_url=spec.base_url, timeout=150, max_retries=1
    )
    kwargs: dict[str, Any] = {
        "model": getattr(settings, spec.model_attr),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.4,
    }
    if spec.supports_json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if spec.name == "zhipu":
        # GLM-4.5/4.7 "think" by default: slow and pointless for picking clips
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def _call_gemini(spec: ProviderSpec, settings: Settings, system: str, user: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=getattr(settings, spec.key_attr), http_options=types.HttpOptions(timeout=150_000)
    )
    resp = client.models.generate_content(
        model=getattr(settings, spec.model_attr),
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system, response_mime_type="application/json", temperature=0.4
        ),
    )
    return resp.text or ""


def _call(spec: ProviderSpec, settings: Settings, system: str, user: str) -> str:
    if spec.adapter == "gemini":
        return _call_gemini(spec, settings, system, user)
    return _call_openai_compatible(spec, settings, system, user)


def chat_json(
    system: str,
    user: str,
    *,
    provider: str | None = None,
    settings: Settings | None = None,
    rounds: int = 2,
    retry_wait: float = 15.0,
) -> tuple[Any, str]:
    """Return (parsed_json, provider_name). Tries each configured provider in order."""
    settings = settings or get_settings()
    chain = [PROVIDERS[provider]] if provider else configured_chain(settings)
    if provider:
        rounds = 1  # explicit single-provider test: fail fast
    if not chain:
        raise LLMError("No LLM provider configured. Add at least one API key to .env.")

    errors = []
    for attempt in range(rounds):
        if attempt:
            time.sleep(retry_wait)  # whole chain failed: likely a network blip, wait and retry
        for spec in chain:
            try:
                raw = _call(spec, settings, system, user)
                return parse_json(raw), spec.name
            except Exception as e:  # rate limit, auth, timeout, bad JSON -> next provider
                log.warning("LLM provider %s failed: %s", spec.name, e)
                errors.append(f"{spec.name}: {e}")
    raise LLMError("All LLM providers failed:\n" + "\n".join(errors))
