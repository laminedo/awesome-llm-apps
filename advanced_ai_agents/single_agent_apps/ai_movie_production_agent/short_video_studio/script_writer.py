"""Step 1 - The AI script writer.

Turns a short idea into a scene-by-scene script for a vertical (or horizontal)
short video, using Google Gemini. Every scene has:
  - narration       -> what the AI voice says
  - on_screen_text  -> a short, punchy headline shown on the video
  - visual_prompt   -> a description used to create the picture / video clip
"""

import json
import os

from google.genai import types

import google_client

# Models to try, newest first. Google retires models over time (in Sept 2026 it
# closed gemini-2.5-flash to new users), so the first one that answers is used.
# Set GEMINI_MODEL in .env / Space settings to force a specific model.
SCRIPT_MODELS = google_client.env_models("GEMINI_MODEL", [
    "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash",
    "gemini-flash-latest", "gemini-2.5-flash",
])

# The exact JSON shape we want back from Gemini.
SCRIPT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "caption": {"type": "STRING"},
        "hashtags": {"type": "ARRAY", "items": {"type": "STRING"}},
        "scenes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "narration": {"type": "STRING"},
                    "on_screen_text": {"type": "STRING"},
                    "visual_prompt": {"type": "STRING"},
                },
                "required": ["narration", "on_screen_text", "visual_prompt"],
            },
        },
    },
    "required": ["title", "caption", "hashtags", "scenes"],
}


def scene_count(duration_seconds: int, engine: str) -> int:
    """How many scenes fit in the video. Veo clips are 8s long, so fewer scenes.

    Talking characters use longer lines and at most 6 scenes (each one is a GPU job).
    """
    if engine == "talk":
        return max(2, min(6, round(duration_seconds / 8)))
    seconds_per_scene = 7 if engine == "veo" else 5
    return max(3, min(10, round(duration_seconds / seconds_per_scene)))


def write_script(
    api_key: str,
    idea: str,
    style: str,
    platform: str,
    duration_seconds: int,
    language: str,
    engine: str,
    character: str = "",
) -> dict:
    """Ask Gemini for a complete short-video script and return it as a dict."""
    n_scenes = scene_count(duration_seconds, engine)
    words_per_scene = max(8, int(duration_seconds * 2.4 / n_scenes))  # ~2.4 spoken words per second

    prompt = f"""
You are an award-winning short-form video producer who makes viral videos for
Facebook Reels and YouTube Shorts. Write a script for this idea:

IDEA: {idea}
STYLE / TONE: {style}
PLATFORM: {platform}
TOTAL LENGTH: about {duration_seconds} seconds
LANGUAGE for narration, on-screen text, title, caption and hashtags: {language}

Rules:
- Exactly {n_scenes} scenes.
- Scene 1 must be a scroll-stopping HOOK (a bold question, surprising fact or promise).
- The last scene ends with a short call to action (follow, like, comment, share...).
- Each narration is spoken aloud: natural, conversational, at most {words_per_scene} words.{_talking_rules(engine, character)}
- on_screen_text: 2 to 6 punchy words that summarise the scene (no emojis, no hashtags).
- visual_prompt: ALWAYS in English, one vivid cinematic description of what we SEE
  (subject, setting, lighting, camera movement, mood). Never ask for text, letters,
  logos or subtitles inside the picture. Keep the same characters and look across scenes.
- caption: an engaging 1-2 sentence post caption.
- hashtags: 5 to 8 relevant hashtags, each starting with #.
"""

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=SCRIPT_SCHEMA,
        temperature=0.9,
    )
    script = None
    for _ in range(2):  # one retry if the answer comes back cut off / not valid JSON
        response = google_client.call_with_models(
            api_key, "script", SCRIPT_MODELS,
            lambda client, model: client.models.generate_content(model=model, contents=prompt, config=config),
        )
        script = _parse(response)
        if script:
            break
    if not script:
        raise RuntimeError("The AI's answer was incomplete. Please click the button again.")
    return script


def _talking_rules(engine: str, character: str) -> str:
    if engine != "talk":
        return ""
    who = character.strip() or "the character in the user's photo"
    return f"""
- TALKING CHARACTER VIDEO: the whole video is ONE character talking straight to the
  camera: {who}. Every narration is a first-person line SPOKEN BY THIS CHARACTER, in
  its own funny personality (e.g. a cat complaining about its human). Never describe
  the character from the outside and never switch speakers.
- visual_prompt: for every scene, repeat a short description of this same character."""


def _parse(response) -> dict | None:
    """Read Gemini's JSON answer safely. Returns None if it should be retried."""
    feedback = getattr(response, "prompt_feedback", None)
    if feedback and feedback.block_reason:
        raise RuntimeError(
            f"Google blocked this idea ({feedback.block_reason}). Try describing it differently."
        )
    candidate = (response.candidates or [None])[0]
    reason = str(getattr(candidate, "finish_reason", "") or "")
    if "SAFETY" in reason or "PROHIBITED" in reason:
        raise RuntimeError("Google's safety filter stopped this script. Try describing the idea differently.")
    try:
        script = json.loads(response.text or "")
    except (json.JSONDecodeError, TypeError):
        return None
    scenes = [
        {key: str(scene.get(key) or "") for key in ("narration", "on_screen_text", "visual_prompt")}
        for scene in (script.get("scenes") or []) if isinstance(scene, dict)
    ]
    if not scenes:
        return None
    return {
        "title": str(script.get("title") or "My short video"),
        "caption": str(script.get("caption") or ""),
        "hashtags": [tag if tag.startswith("#") else f"#{tag}"
                     for tag in (str(t).strip() for t in (script.get("hashtags") or [])) if tag],
        "scenes": scenes,
    }
