"""Bounded OpenAI-compatible text generation with redacted diagnostics."""
import asyncio
import os
import time
from weakref import WeakKeyDictionary
from dataclasses import dataclass, field
import httpx
from .telemetry import event


class ProviderError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


_states = WeakKeyDictionary()


def _state():
    loop = asyncio.get_running_loop()
    if loop not in _states:
        _states[loop] = (asyncio.Lock(), {})
    return _states[loop]


def retry_delay(response, attempt):
    try:
        return max(2.0, float(response.headers.get("retry-after", "")))
    except (ValueError, TypeError):
        return 5.0 * (attempt + 1)


@dataclass(frozen=True)
class Provider:
    name: str
    base: str
    model: str
    key: str = field(repr=False)


def providers():
    result = []
    key, model = os.getenv("AI_API_KEY"), os.getenv("AI_MODEL")
    if key and model:
        base = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        result.append(Provider("Primary", base, model, key))
    key, model = os.getenv("GROQ_API_KEY"), os.getenv("GROQ_MODEL")
    if key and model:
        result.append(Provider("Groq", "https://api.groq.com/openai/v1", model, key))
    return result


def classify(response):
    status = response.status_code
    try:
        code = response.json().get("error", {}).get("code")
    except (ValueError, AttributeError):
        code = None
    if code in ("insufficient_quota", "billing_hard_limit_reached"):
        return ProviderError("quota", "AI provider has insufficient API credit or a billing limit. Add credit or configure a separate fallback provider.")
    if status == 401:
        return ProviderError("authentication", "AI provider rejected the API key. Replace it in Render.")
    if status == 403:
        return ProviderError("permission", "AI provider denied access to the configured model or project.")
    if status == 404:
        return ProviderError("model", "The configured AI model is unavailable. Check the model name and access.")
    if status == 429:
        return ProviderError("rate_limit", "AI provider is rate-limiting requests. Retry later or check API usage limits.")
    if status >= 500:
        return ProviderError("unavailable", "AI provider is temporarily unavailable.")
    return ProviderError("request", f"AI provider rejected the generation request (HTTP {status}). Check model configuration.")


async def generate(client, system, prompt, *, max_tokens=1000):
    candidates = providers()
    if not candidates:
        raise ProviderError("not_configured", "Configure a provider API key and model in Render.")
    lock, cooldowns = _state()
    last = ProviderError("rate_limit", "AI provider is cooling down. Retry in a moment.")
    deadline = time.monotonic() + 85
    # One request at a time across research, chat, and verification.
    async with lock:
        for attempt in range(3):
            if time.monotonic() >= deadline:
                break
            for provider in candidates:
                identity = (provider.name, provider.base, provider.model)
                if cooldowns.get(identity, 0) > time.monotonic():
                    continue
                payload = {"model":provider.model, "messages":[{"role":"system","content":system},{"role":"user","content":prompt}], "max_tokens":max_tokens}
                if provider.name == "Groq" and provider.model.startswith("openai/gpt-oss-"):
                    payload["reasoning_effort"] = "low"
                    payload["max_tokens"] = max(256, max_tokens)
                try:
                    response = await client.post(provider.base + "/chat/completions",
                         headers={"Authorization":"Bearer " + provider.key}, json=payload)
                    if response.is_error:
                        event("provider", "failed", provider=provider.name)
                        last = classify(response)
                        if last.code == "rate_limit":
                            cooldowns[identity] = time.monotonic() + retry_delay(response, attempt)
                        elif last.code in ("quota","authentication","permission","model"):
                            cooldowns[identity] = time.monotonic() + 300
                        elif last.code == "unavailable":
                            cooldowns[identity] = time.monotonic() + 5
                        else:
                            cooldowns[identity] = time.monotonic() + 300
                        continue
                    content = response.json()["choices"][0]["message"]["content"]
                    if not isinstance(content, str) or not content.strip():
                        last = ProviderError("empty", "AI provider returned an empty answer.")
                        cooldowns[identity] = time.monotonic() + 3
                        continue
                    if provider.name == "Groq":
                        cooldowns[identity] = time.monotonic() + 2.1
                    event("provider", "complete", provider=provider.name)
                    return content.strip()
                except httpx.TimeoutException:
                    last = ProviderError("timeout", "AI provider request timed out. Try a shorter question.")
                except httpx.HTTPError:
                    last = ProviderError("connection", "Could not connect to the AI provider.")
                except (ValueError, KeyError, IndexError, TypeError):
                    last = ProviderError("response", "AI provider returned an unexpected response.")
                cooldowns[identity] = time.monotonic() + 5
            if attempt == 2:
                break
            delay = min(max(0, cooldowns.get((p.name,p.base,p.model), 0)-time.monotonic()) for p in candidates)
            # Honor provider retry-after. Do not retry when the window exceeds our budget.
            if delay > 60 or time.monotonic()+delay >= deadline:
                break
            await asyncio.sleep(max(0.2, delay))
    raise last
