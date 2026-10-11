"""Talking characters: make a photo's mouth move to the voiceover.

This runs on free GPU "Spaces" on Hugging Face (your Hugging Face PRO account gets
extra GPU time there). Tested in Oct 2026:
  - MoDA: fast (~15s per scene), human faces only (babies, people).
  - LongCat-Video-Avatar 1.5: slower (~90s per 5 seconds of talking) but also
    works for animals. It only makes 5 seconds at a time, so longer lines are
    split into pieces and joined back together.
The Spaces are tried in order; the first one that works is remembered.

Needs HF_TOKEN (a Hugging Face token) in .env / the Space secrets so the GPU time
is counted on your account. Without it, the shared anonymous quota is very small.
Set LIPSYNC_SPACES to a comma-separated list to choose other Spaces.
"""

import os
import shutil

from gradio_client import Client, handle_file

import video_builder

LONGCAT_MAX_SECONDS = 4.8  # LongCat cuts its videos at 5 seconds


def _longcat(client: Client, image: str, audio: str, api_name: str):
    return client.predict(
        handle_file(image), handle_file(audio),
        "A character is speaking expressively, looking at the camera.",
        "480p", 42, "Clean speech (fast)", "DBCache faster",
        api_name=api_name,
    )


def _moda(client: Client, image: str, audio: str, api_name: str):
    return client.predict(handle_file(image), handle_file(audio), "Happiness", 1.2, api_name=api_name)


# Space id -> (how to call it, its endpoint name). Fast human-only Space first.
KNOWN_SPACES = {
    "multimodalart/MoDA-fast-talking-head": (_moda, "/generate_motion"),
    "victor/LongCat-Video-Avatar-1.5": (_longcat, "/generate"),
    "meituan-longcat/LongCat-Video-Avatar-1.5-Demo": (_longcat, "/generate_avatar"),
}
DEFAULT_ORDER = list(KNOWN_SPACES)

_clients: dict[str, Client] = {}
_working: list[str] = []  # the Space that worked last time goes first


def spaces() -> list[str]:
    chosen = [s.strip() for s in os.getenv("LIPSYNC_SPACES", "").split(",") if s.strip() in KNOWN_SPACES]
    return list(dict.fromkeys([*_working, *(chosen or DEFAULT_ORDER)]))


def _client(space: str) -> Client:
    if space not in _clients:
        _clients[space] = Client(space, token=os.getenv("HF_TOKEN") or None, verbose=False)
    return _clients[space]


def _run(space: str, image_path: str, audio_path: str, out_path: str) -> str:
    call, api_name = KNOWN_SPACES[space]
    result = call(_client(space), image_path, audio_path, api_name)
    video = result.get("video") if isinstance(result, dict) else result
    if not video or not os.path.exists(video):
        raise RuntimeError("no video returned")
    shutil.copyfile(video, out_path)
    return out_path


def _run_in_pieces(space: str, image_path: str, audio_path: str, out_path: str, log) -> str:
    """LongCat makes at most 5 seconds: split the line, animate each piece, join them."""
    duration = video_builder.media_info(audio_path)[0]
    pieces = max(1, -(-duration // LONGCAT_MAX_SECONDS))  # round up
    if pieces == 1:
        return _run(space, image_path, audio_path, out_path)
    step = duration / pieces
    clips = []
    for n in range(int(pieces)):
        log(f"Animating part {n + 1} of {int(pieces)}…")
        part_audio = f"{out_path}.part{n}.wav"
        video_builder.run_ffmpeg(["-ss", f"{n * step:.3f}", "-t", f"{step:.3f}", "-i", audio_path, part_audio])
        clips.append(_run(space, image_path, part_audio, f"{out_path}.part{n}.mp4"))
    list_file = f"{out_path}.parts.txt"
    with open(list_file, "w", encoding="utf-8") as file:
        file.writelines(f"file '{os.path.abspath(c)}'\n" for c in clips)
    video_builder.run_ffmpeg(["-f", "concat", "-safe", "0", "-i", list_file, "-an",
                              "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", out_path])
    return out_path


def talking_clip(image_path: str, audio_path: str, out_path: str, log) -> str:
    """Create a video of the character in image_path saying audio_path. Raises if every Space fails."""
    errors = []
    for space in spaces():
        try:
            if KNOWN_SPACES[space][0] is _longcat:
                _run_in_pieces(space, image_path, audio_path, out_path, log)
            else:
                _run(space, image_path, audio_path, out_path)
            if space in _working:
                _working.remove(space)
            _working.insert(0, space)
            return out_path
        except Exception as error:  # noqa: BLE001 - try the next Space
            _clients.pop(space, None)
            errors.append(f"{space.split('/')[-1]}: {str(error)[:160]}")
            if "No face detected" in str(error):
                log("No human face found (an animal?), switching to the animal-friendly model…")
            else:
                log(f"Talking-face service {space.split('/')[-1]} didn't work, trying another…")
    raise RuntimeError("No talking-face service worked (" + " | ".join(errors) + ")")
