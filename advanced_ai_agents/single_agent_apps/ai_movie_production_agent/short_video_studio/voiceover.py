"""Step 2 - The AI voiceover.

Main voice engine: Microsoft Edge neural voices (free, no API key needed).
Backup: Gemini text-to-speech (uses your Google API key).
If both fail, the scene is simply silent so the video can still be made.
"""

import asyncio
import os
import wave

import edge_tts
from google.genai import types

import google_client

GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

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


async def _edge_tts(text: str, voice: str, rate: str, out_path: str) -> None:
    await edge_tts.Communicate(text, voice, rate=rate).save(out_path)


def _gemini_tts(text: str, voice: str, api_key: str, out_path: str) -> None:
    response = google_client.call(api_key, lambda client: client.models.generate_content(
        model=GEMINI_TTS_MODEL,
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
    pcm = response.candidates[0].content.parts[0].inline_data.data
    with wave.open(out_path, "wb") as wav:  # Gemini returns raw 24kHz 16-bit mono audio
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(pcm)


def make_voiceover(text: str, voice: str, speed: str, api_key: str, out_base: str, log) -> str | None:
    """Create the voice file for one scene. Returns its path, or None for silence."""
    rate = {"Slow": "-10%", "Normal": "+0%", "Fast": "+12%"}.get(speed, "+0%")

    mp3_path = out_base + ".mp3"
    try:
        asyncio.run(_edge_tts(text, voice, rate, mp3_path))
        if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
            return mp3_path
    except Exception as error:  # noqa: BLE001 - any failure -> try the backup voice
        log(f"Free voice unavailable ({type(error).__name__}), trying Gemini voice…")

    wav_path = out_base + ".wav"
    try:
        _gemini_tts(text, _gemini_voice_for(voice), api_key, wav_path)
        return wav_path
    except Exception as error:  # noqa: BLE001
        log(f"⚠️ No voice could be recorded for: \"{text[:40]}…\" ({type(error).__name__}). That scene is silent.")
        return None
