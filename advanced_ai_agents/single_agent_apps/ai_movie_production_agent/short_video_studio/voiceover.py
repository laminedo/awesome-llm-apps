"""Step 2 - The AI voiceover.

Voices are tried in this order, the first that works is used:
  1. Microsoft Edge neural voices (free, no key, the most natural).
  2. Google Translate's voice via gTTS (free, no key, simpler: one voice per language).
  3. Gemini text-to-speech (uses your Google API key; the free tier is tiny).
If all fail, the scene is simply silent so the video can still be made.
"""

import asyncio
import os
import threading
import time
import wave

import edge_tts
from google.genai import types
from gtts import gTTS

import google_client
import video_builder

# Backup voice models to try, newest first (set GEMINI_TTS_MODEL to force one).
TTS_MODELS = google_client.env_models("GEMINI_TTS_MODEL", [
    "gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts",
])

# Voices shown in the app, grouped by language. "id" is the Edge voice name.
VOICES = {
    "English": [
        {"id": "en-US-AndrewNeural", "name": "Andrew", "gender": "Male", "gemini": "Puck"},
        {"id": "en-US-AvaNeural", "name": "Ava", "gender": "Female", "gemini": "Kore"},
        {"id": "en-US-BrianNeural", "name": "Brian", "gender": "Male", "gemini": "Charon"},
        {"id": "en-US-EmmaNeural", "name": "Emma", "gender": "Female", "gemini": "Aoede"},
        {"id": "en-GB-RyanNeural", "name": "Ryan (UK)", "gender": "Male", "gemini": "Fenrir"},
        {"id": "en-GB-SoniaNeural", "name": "Sonia (UK)", "gender": "Female", "gemini": "Leda"},
    ],
    "French": [
        {"id": "fr-FR-HenriNeural", "name": "Henri", "gender": "Male", "gemini": "Puck"},
        {"id": "fr-FR-DeniseNeural", "name": "Denise", "gender": "Female", "gemini": "Kore"},
        {"id": "fr-FR-RemyMultilingualNeural", "name": "Rémy", "gender": "Male", "gemini": "Charon"},
        {"id": "fr-FR-VivienneMultilingualNeural", "name": "Vivienne", "gender": "Female", "gemini": "Aoede"},
    ],
    "Spanish": [
        {"id": "es-ES-AlvaroNeural", "name": "Álvaro", "gender": "Male", "gemini": "Puck"},
        {"id": "es-MX-DaliaNeural", "name": "Dalia", "gender": "Female", "gemini": "Kore"},
    ],
    "Portuguese": [
        {"id": "pt-BR-AntonioNeural", "name": "Antônio", "gender": "Male", "gemini": "Puck"},
        {"id": "pt-BR-FranciscaNeural", "name": "Francisca", "gender": "Female", "gemini": "Kore"},
    ],
    "Arabic": [
        {"id": "ar-SA-HamedNeural", "name": "Hamed", "gender": "Male", "gemini": "Puck"},
        {"id": "ar-EG-SalmaNeural", "name": "Salma", "gender": "Female", "gemini": "Kore"},
    ],
    "German": [
        {"id": "de-DE-ConradNeural", "name": "Conrad", "gender": "Male", "gemini": "Puck"},
        {"id": "de-DE-KatjaNeural", "name": "Katja", "gender": "Female", "gemini": "Kore"},
    ],
}


def _gemini_voice_for(edge_voice_id: str) -> str:
    for voices in VOICES.values():
        for voice in voices:
            if voice["id"] == edge_voice_id:
                return voice["gemini"]
    return "Kore"


# Microsoft sometimes refuses a computer ("403"), e.g. when it gets too many requests.
# After a refusal we skip it for a while and go straight to the backup voice.
EDGE_PAUSE_SECONDS = 15 * 60
_edge_paused_until = 0.0
_edge_lock = threading.Lock()


async def _edge_tts(text: str, voice: str, rate: str, out_path: str) -> None:
    await edge_tts.Communicate(text, voice, rate=rate).save(out_path)


def _edge(text: str, voice: str, rate: str, out_path: str) -> None:
    global _edge_paused_until
    if time.time() < _edge_paused_until:
        raise RuntimeError("Microsoft voice paused after a refusal")
    with _edge_lock:  # one request at a time, a second apart
        try:
            asyncio.run(_edge_tts(text, voice, rate, out_path))
        except Exception as error:
            if getattr(error, "status", None) == 403 or "403" in str(error):
                _edge_paused_until = time.time() + EDGE_PAUSE_SECONDS
            raise
        finally:
            time.sleep(1)
    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        raise RuntimeError("Microsoft voice returned no audio")


# Edge voice prefix -> (gTTS language, Google domain giving the right accent).
GTTS_ACCENTS = {
    "en-US": ("en", "com"), "en-GB": ("en", "co.uk"), "fr-FR": ("fr", "fr"),
    "es-ES": ("es", "es"), "es-MX": ("es", "com.mx"), "pt-BR": ("pt", "com.br"),
    "de-DE": ("de", "de"), "ar-SA": ("ar", "com"), "ar-EG": ("ar", "com"),
}
# gTTS talks a little slowly, so even "Normal" is sped up a bit.
GTTS_TEMPO = {"Slow": 0.95, "Normal": 1.12, "Fast": 1.25}


def _gtts(text: str, voice: str, speed: str, out_path: str) -> None:
    lang, tld = GTTS_ACCENTS.get(voice[:5], (voice[:2] or "en", "com"))
    raw_path = out_path + ".raw.mp3"
    gTTS(text, lang=lang, tld=tld).save(raw_path)
    video_builder.run_ffmpeg(["-i", raw_path, "-af", f"atempo={GTTS_TEMPO.get(speed, 1.12)}", out_path])
    os.remove(raw_path)


def _gemini_tts(text: str, voice: str, api_key: str, out_path: str) -> None:
    response = google_client.call_with_models(api_key, "tts", TTS_MODELS, lambda client, model: client.models.generate_content(
        model=model,
        contents=f"Say this in an energetic, engaging social-media voice: {text}",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    ))
    parts = (response.candidates or [None])[0]
    parts = parts.content.parts if parts and parts.content and parts.content.parts else []
    audio = next((p.inline_data for p in parts
                  if p.inline_data and (p.inline_data.mime_type or "").startswith("audio/")), None)
    if audio is None:
        raise RuntimeError("Gemini returned no audio")
    rate = 24000  # Gemini sends raw 16-bit mono PCM, e.g. "audio/L16;codec=pcm;rate=24000"
    for piece in (audio.mime_type or "").split(";"):
        if piece.strip().startswith("rate="):
            rate = int(piece.strip()[5:])
    with wave.open(out_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(audio.data)


def make_voiceover(text: str, voice: str, speed: str, api_key: str, out_base: str, log,
                   notes: set | None = None) -> str | None:
    """Create the voice file for one scene. Returns its path, or None for silence.

    Pass the same "notes" set for every scene of a video so each warning shows only once.
    """
    if not text.strip():
        return None  # nothing to say: a silent scene
    notes = set() if notes is None else notes
    rate = {"Slow": "-10%", "Normal": "+0%", "Fast": "+12%"}.get(speed, "+0%")

    mp3_path = out_base + ".mp3"
    try:
        _edge(text, voice, rate, mp3_path)
        return mp3_path
    except Exception as error:  # noqa: BLE001 - any failure -> try the backup voice
        log(f"Microsoft voice unavailable ({str(error)[:80] or type(error).__name__}), trying Google's free voice…")

    gtts_path = out_base + ".gtts.mp3"
    try:
        _gtts(text, voice, speed, gtts_path)
        if "gtts" not in notes:
            notes.add("gtts")
            log("⚠️ Microsoft's free voice was busy, so Google's free backup voice was used "
                "(simpler, one voice per language). Try again later for the voice you picked.")
        return gtts_path
    except Exception as error:  # noqa: BLE001
        log(f"Google's free voice unavailable ({type(error).__name__}), trying the Gemini voice…")

    wav_path = out_base + ".wav"
    try:
        _gemini_tts(text, _gemini_voice_for(voice), api_key, wav_path)
        return wav_path
    except Exception as error:  # noqa: BLE001
        log(f"⚠️ No voice could be recorded for: \"{text[:40]}…\" "
            f"({google_client.friendly_error(error)[:200]}). That scene is silent.")
        return None
