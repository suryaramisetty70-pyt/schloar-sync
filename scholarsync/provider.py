"""Bounded OpenAI-compatible text generation with redacted diagnostics."""
import os
from dataclasses import dataclass, field
import httpx


class ProviderError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


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
    last = None
    for provider in candidates:
        try:
            response = await client.post(provider.base + "/chat/completions",
                 headers={"Authorization": "Bearer " + provider.key},
                 json={"model": provider.model, "messages": [{"role":"system","content":system},{"role":"user","content":prompt}], "max_tokens":max_tokens})
            if response.is_error:
                raise classify(response)
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ProviderError("empty", "AI provider returned an empty answer.")
            return content.strip()
        except ProviderError as exc:
            last = exc
        except httpx.TimeoutException:
            last = ProviderError("timeout", "AI provider request timed out. Try a shorter question.")
        except httpx.HTTPError:
            last = ProviderError("connection", "Could not connect to the AI provider.")
        except (ValueError, KeyError, IndexError, TypeError):
            last = ProviderError("response", "AI provider returned an unexpected response.")
    raise last
