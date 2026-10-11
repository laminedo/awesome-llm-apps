"""One place to talk to Google AI with your API key.

- Google AI Studio gives out two kinds of keys: older "AIza..." keys and newer
  "AQ..." keys. Some AQ keys are refused by the normal Gemini address with
  "401 ACCESS_TOKEN_TYPE_UNSUPPORTED" but work through Vertex AI express mode,
  so we try both and remember which one works for your key.
- Google retires AI models over time, so for each job we try a short list of
  models and remember the first one that works.
- Busy/overloaded answers from Google are retried automatically, and every call
  has a time limit so the app never hangs forever.
"""

import os

from google import genai
from google.genai import types

# Each call waits at most 90s, and busy/overloaded answers are retried (3 tries in total).
HTTP_OPTIONS = types.HttpOptions(
    timeout=90_000,
    retry_options=types.HttpRetryOptions(
        attempts=3, initial_delay=2, http_status_codes=[408, 429, 500, 502, 503, 504]
    ),
)

KEY_HELP = (
    "Open aistudio.google.com/apikey, copy the key again with the copy button "
    "(the whole key) and paste it in ⚙️ Settings. If it still fails, create an "
    "'AIza…' key in Google Cloud (console.cloud.google.com → APIs & Services → "
    "Credentials) with the Generative Language API enabled."
)

_vertex_keys: set[str] = set()
_working_model: dict[str, str] = {}  # "script"/"tts" (+ backend) -> model that worked


def _code(error: Exception) -> int | None:
    return getattr(error, "code", None)


def _is_key_type_error(error: Exception) -> bool:
    return "ACCESS_TOKEN_TYPE_UNSUPPORTED" in str(error)


def _is_model_missing(error: Exception) -> bool:
    text = str(error)
    return _code(error) == 404 or "NOT_FOUND" in text or "no longer available" in text


def _client(api_key: str, vertex: bool) -> genai.Client:
    # vertexai is always set explicitly, so environment variables such as
    # GOOGLE_GENAI_USE_VERTEXAI can't silently switch the backend.
    return genai.Client(vertexai=vertex, api_key=api_key, http_options=HTTP_OPTIONS)


def make_client(api_key: str) -> genai.Client:
    return _client(api_key, api_key in _vertex_keys)


def call(api_key: str, action):
    """Run action(client); if Google refuses this AQ key, retry via Vertex AI express mode."""
    try:
        return action(make_client(api_key))
    except Exception as error:
        if api_key in _vertex_keys or not _is_key_type_error(error):
            raise
        try:
            result = action(_client(api_key, vertex=True))
        except Exception as vertex_error:  # noqa: BLE001 - both ways failed: explain clearly
            if _code(vertex_error) in (400, 401) or "API key not valid" in str(vertex_error):
                raise RuntimeError(
                    "Google refused this API key (401 ACCESS_TOKEN_TYPE_UNSUPPORTED), and the "
                    f"Vertex AI backup refused it too. {KEY_HELP}"
                ) from error
            raise RuntimeError(
                "Google's Gemini service refused this key (401 ACCESS_TOKEN_TYPE_UNSUPPORTED) and "
                f"the Vertex AI backup also failed: {vertex_error}"
            ) from error
        _vertex_keys.add(api_key)
        return result


def call_with_models(api_key: str, kind: str, candidates: list[str], action):
    """Run action(client, model), moving to the next model if Google says a model is gone.

    The first model that works is remembered, so later calls go straight to it.
    """
    models = [m for m in dict.fromkeys(candidates) if m]
    last_error: Exception | None = None

    def attempt(client):
        nonlocal last_error
        cache_key = f"{kind}:{'vertex' if client.vertexai else 'gemini'}"
        ordered = list(dict.fromkeys([_working_model.get(cache_key), *models]))
        for model in [m for m in ordered if m]:
            try:
                result = action(client, model)
            except Exception as error:  # noqa: BLE001
                if not _is_model_missing(error):
                    raise
                last_error = error
                continue
            _working_model[cache_key] = model
            return result
        raise RuntimeError(
            f"Google no longer offers the AI models this app tried ({', '.join(models)}). "
            f"Last answer: {last_error}"
        )

    return call(api_key, attempt)


def env_models(variable: str, defaults: list[str]) -> list[str]:
    """A model set in .env / Space settings goes first, then our defaults."""
    return [os.getenv(variable, "").strip(), *defaults]


def friendly_error(error: Exception, key_source: str = "", key_hint: str = "") -> str:
    """Turn a Google error into one clear sentence for the user."""
    text = str(error)
    code = _code(error)
    used = f" (using {key_source} {key_hint})" if key_source else ""
    if "ACCESS_TOKEN_TYPE_UNSUPPORTED" in text or "API_KEY_INVALID" in text or "API key not valid" in text:
        if text.startswith(("Google refused", "Google's Gemini")):
            return text + used
        return f"Google rejected the API key{used}. {KEY_HELP}"
    if code == 403 or "PERMISSION_DENIED" in text or "SERVICE_DISABLED" in text:
        return (f"Google says this key{used} isn't allowed to use Gemini. Make sure the "
                f"'Generative Language API' is enabled for the key's project. Details: {text[:300]}")
    if code == 429 or "RESOURCE_EXHAUSTED" in text:
        return f"Google's free limit was reached for now{used}. Wait a minute and try again. Details: {text[:200]}"
    if code in (500, 502, 503, 504) or "UNAVAILABLE" in text or "overloaded" in text:
        return "Google's AI is busy right now. Please try again in a minute."
    if "timed out" in text.lower() or "timeout" in type(error).__name__.lower():
        return "Google took too long to answer. Please try again."
    return text
