import json
import logging
import re
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)
from google import genai
from google.genai import types

_client: genai.Client | None = None


def init_gemini(api_key: str):
    global _client
    _client = genai.Client(api_key=api_key)


def get_client() -> genai.Client:
    if _client is None:
        raise RuntimeError("Gemini client not initialized. Call init_gemini(api_key) first.")
    return _client


# ── Base adapter ────────────────────────────────────────────────────────────

class BaseAdapter(ABC):
    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 8192, json_mode: bool = False) -> str: ...

    def generate_stream(self, prompt: str, max_tokens: int = 8192):
        """Yield text chunks. Default falls back to generate() as one chunk."""
        yield self.generate(prompt, max_tokens=max_tokens)


# ── Gemini adapter ──────────────────────────────────────────────────────────

class GeminiAdapter(BaseAdapter):
    def __init__(self, model_name: str):
        self.model_name = model_name

    def generate(self, prompt: str, max_tokens: int = 8192, json_mode: bool = False) -> str:
        from config import MAX_RETRIES, RETRY_DELAY_SECONDS
        client = get_client()
        last_error = None

        config_kwargs = dict(max_output_tokens=max_tokens)
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
                return response.text
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    logger.warning(f"Gemini retry {attempt}/{MAX_RETRIES}: {e}")
                    time.sleep(RETRY_DELAY_SECONDS * attempt)

        raise RuntimeError(f"Gemini call failed after {MAX_RETRIES} attempts: {last_error}")

    def generate_stream(self, prompt: str, max_tokens: int = 8192):
        """Stream text chunks from Gemini. On failure, raises (no mid-stream retry)."""
        client = get_client()
        config_kwargs = dict(max_output_tokens=max_tokens)
        response = client.models.generate_content_stream(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text


# ── OpenAI-compatible adapter (OpenAI + Ollama) ─────────────────────────────

class OpenAIAdapter(BaseAdapter):
    def __init__(self, model_name: str, base_url: str, api_key: str):
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key

    def generate(self, prompt: str, max_tokens: int = 8192, json_mode: bool = False) -> str:
        from config import MAX_RETRIES, RETRY_DELAY_SECONDS
        import openai

        client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        last_error = None

        kwargs: dict = dict(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = client.chat.completions.create(**kwargs)
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    logger.warning(f"OpenAI retry {attempt}/{MAX_RETRIES}: {e}")
                    time.sleep(RETRY_DELAY_SECONDS * attempt)

        raise RuntimeError(f"OpenAI call failed after {MAX_RETRIES} attempts: {last_error}")

    def generate_stream(self, prompt: str, max_tokens: int = 8192):
        """Stream text chunks from OpenAI-compatible endpoint."""
        import openai
        client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        stream = client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# ── Factory ─────────────────────────────────────────────────────────────────

def get_adapter(provider: str, model: str, **kwargs) -> BaseAdapter:
    if provider == "gemini":
        return GeminiAdapter(model_name=model)
    elif provider in ("openai", "ollama"):
        base_url = kwargs.get("base_url", "https://api.openai.com/v1")
        api_key = kwargs.get("api_key", "")
        return OpenAIAdapter(model_name=model, base_url=base_url, api_key=api_key)
    raise ValueError(f"Unknown provider: {provider}")


def build_adapter(agent_key: str) -> BaseAdapter:
    """Build adapter from current config — reads config at call time (lazy init)."""
    import config
    cfg = config.AGENT_MODEL_CONFIG[agent_key]
    provider = cfg["provider"]
    model = cfg["model"]
    if provider == "gemini":
        return get_adapter(provider, model)
    elif provider == "ollama":
        return get_adapter(provider, model, base_url=config.OLLAMA_BASE_URL, api_key="ollama")
    elif provider == "openai":
        return get_adapter(provider, model, base_url="https://api.openai.com/v1", api_key=config.OPENAI_API_KEY)
    raise ValueError(f"Unknown provider: {provider}")


# ── JSON helpers ─────────────────────────────────────────────────────────────

def parse_json_response(response: str) -> dict:
    """Strip markdown code fence (handles trailing whitespace/newlines) and parse JSON."""
    text = response.strip()
    text = re.sub(r"^```[^\n]*\n", "", text)  # remove opening ```json or ```
    text = re.sub(r"\n```\s*$", "", text)      # remove closing ``` with any trailing whitespace
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in LLM response: {e}") from e
