import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Server config
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:3000")
API_PORT = int(os.environ.get("API_PORT", "8000"))

# Gemini models
GEMINI_PRO_MODEL = "gemini-3.1-pro-preview"
GEMINI_FLASH_MODEL = "gemini-3-flash-preview"

# Model assignment per agent (legacy names kept for any direct references)
PLOT_NAVIGATOR_MODEL = GEMINI_PRO_MODEL
CHARACTER_SOUL_MODEL = GEMINI_PRO_MODEL
DRAFT_MASTER_MODEL = GEMINI_FLASH_MODEL
FINAL_AUDITOR_MODEL = GEMINI_FLASH_MODEL

# Novel defaults
DEFAULT_CHAPTERS = 3
DEFAULT_WORDS_PER_CHAPTER = 4500
DEFAULT_GENRE = "isekai"

# Retry config
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

# Output
OUTPUT_DIR = "output"

# Provider-specific connection details
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")

# Per-agent model config — read by build_adapter() at call time
AGENT_MODEL_CONFIG: dict = {
    "plot_navigator": {
        "provider": os.environ.get("PLOT_NAVIGATOR_PROVIDER", "gemini"),
        "model":    os.environ.get("PLOT_NAVIGATOR_MODEL", GEMINI_PRO_MODEL),
    },
    "character_soul": {
        "provider": os.environ.get("CHARACTER_SOUL_PROVIDER", "gemini"),
        "model":    os.environ.get("CHARACTER_SOUL_MODEL", GEMINI_PRO_MODEL),
    },
    "draft_master": {
        "provider": os.environ.get("DRAFT_MASTER_PROVIDER", "gemini"),
        "model":    os.environ.get("DRAFT_MASTER_MODEL", GEMINI_FLASH_MODEL),
    },
    "final_auditor": {
        "provider": os.environ.get("FINAL_AUDITOR_PROVIDER", "gemini"),
        "model":    os.environ.get("FINAL_AUDITOR_MODEL", GEMINI_FLASH_MODEL),
    },
    "summarizer": {
        "provider": os.environ.get("FINAL_AUDITOR_PROVIDER", "gemini"),
        "model":    os.environ.get("FINAL_AUDITOR_MODEL", GEMINI_FLASH_MODEL),
    },
}

# ── settings.json override ──────────────────────────────────────────────────

_SETTINGS_PATH = Path(__file__).parent / "settings.json"


def _load_settings_json() -> None:
    global OLLAMA_BASE_URL
    if not _SETTINGS_PATH.exists():
        return
    try:
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        for key, val in data.get("agents", {}).items():
            if key in AGENT_MODEL_CONFIG and isinstance(val, dict):
                AGENT_MODEL_CONFIG[key].update(val)
        if "ollama_base_url" in data:
            OLLAMA_BASE_URL = data["ollama_base_url"]
    except Exception as e:
        print(f"[config] Warning: failed to load settings.json: {e}")


_load_settings_json()


def reload_config() -> None:
    """Re-apply settings.json overrides at runtime (called by POST /settings)."""
    _load_settings_json()
