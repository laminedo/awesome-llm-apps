"""One place to talk to Google AI with your API key.

Google AI Studio now gives out two kinds of keys: older "AIza..." keys and newer
"AQ..." keys. Some AQ keys are refused by the normal Gemini address with
"401 ACCESS_TOKEN_TYPE_UNSUPPORTED" but work through Vertex AI express mode,
so we try both and remember which one works for your key.
"""

from google import genai

KEY_HELP = (
    "Google rejected your API key (401 ACCESS_TOKEN_TYPE_UNSUPPORTED). "
    "Open aistudio.google.com/apikey, copy the key again with the copy button "
    "(the whole key), paste it in ⚙️ Settings and try again. If it still fails, "
    "click 'Create API key' → 'Create API key in new project' and use that key."
)

_vertex_keys: set[str] = set()


def _is_key_type_error(error: Exception) -> bool:
    return "ACCESS_TOKEN_TYPE_UNSUPPORTED" in str(error)


def make_client(api_key: str) -> genai.Client:
    if api_key in _vertex_keys:
        return genai.Client(vertexai=True, api_key=api_key)
    return genai.Client(api_key=api_key)


def is_vertex(api_key: str) -> bool:
    return api_key in _vertex_keys


def call(api_key: str, action):
    """Run action(client); if Google refuses the key type, retry via Vertex AI express mode."""
    try:
        return action(make_client(api_key))
    except Exception as error:
        if api_key in _vertex_keys or not _is_key_type_error(error):
            raise
        try:
            result = action(genai.Client(vertexai=True, api_key=api_key))
        except Exception as vertex_error:  # noqa: BLE001 - both ways failed: explain clearly
            raise RuntimeError(f"{KEY_HELP} (Backup method said: {vertex_error})") from error
        _vertex_keys.add(api_key)
        return result
