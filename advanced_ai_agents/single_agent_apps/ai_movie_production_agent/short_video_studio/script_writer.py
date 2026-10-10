"""Step 1 - The AI script writer.

Turns a short idea into a scene-by-scene script for a vertical (or horizontal)
short video, using Google Gemini. Every scene has:
  - narration       -> what the AI voice says
  - on_screen_text  -> a short, punchy headline shown on the video
  - visual_prompt   -> a description used to create the picture / video clip
"""

import json
import os

from google import genai
from google.genai import types

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

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
    """How many scenes fit in the video. Veo clips are 8s long, so fewer scenes."""
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
- Each narration is spoken aloud: natural, conversational, at most {words_per_scene} words.
- on_screen_text: 2 to 6 punchy words that summarise the scene (no emojis, no hashtags).
- visual_prompt: ALWAYS in English, one vivid cinematic description of what we SEE
  (subject, setting, lighting, camera movement, mood). Never ask for text, letters,
  logos or subtitles inside the picture. Keep the same characters and look across scenes.
- caption: an engaging 1-2 sentence post caption.
- hashtags: 5 to 8 relevant hashtags, each starting with #.
"""

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SCRIPT_SCHEMA,
            temperature=0.9,
        ),
    )
    script = json.loads(response.text)
    script["hashtags"] = [
        tag if tag.startswith("#") else f"#{tag}" for tag in script.get("hashtags", [])
    ]
    return script
