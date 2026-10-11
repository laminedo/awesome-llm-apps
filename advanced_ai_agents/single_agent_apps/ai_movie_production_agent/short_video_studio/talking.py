"""Step 3 (talking mode) - one character that talks to the camera.

1. Get the character picture: your uploaded photo, or an AI picture made from
   your description (front-facing portrait so the face can be animated).
2. For each scene, make the character's mouth move to that scene's voiceover
   (lipsync.py, on Hugging Face GPUs).
If the talking service fails, the scene uses the still picture with a slow zoom,
so the video is always made.
"""

import base64
import io
import os

from PIL import Image

import lipsync
import video_builder
import visuals

PORTRAIT = ("front-facing portrait, the face looks straight at the camera, centered, "
            "mouth closed, head and shoulders, soft studio light, simple background")


def character_picture(request, work_dir: str, log) -> str:
    """Save the uploaded photo, or create one from the description. Returns its path."""
    path = os.path.join(work_dir, "character.jpg")
    if request.character_image:
        data = request.character_image.split(",", 1)[-1]  # strip "data:image/...;base64,"
        image = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
        image.thumbnail((1024, 1024))  # smaller upload, faster GPU job
        image.save(path, quality=92)
        return path
    log("Creating your character…")
    raw = os.path.join(work_dir, "character_full.jpg")
    visuals.free_image(f"{request.character}, {PORTRAIT}", 576, 1024, 0, raw, log)
    Image.open(raw).save(path, quality=92)
    return path


def make_talking_clips(request, voice_paths, work_dir, width, height, step, log):
    """Return [(path, is_video)] for every scene."""
    total = len(request.scenes)
    step("Creating your character", 0.16)
    picture = character_picture(request, work_dir, log)
    # A copy shaped like the final video, used for scenes that can't talk.
    still = os.path.join(work_dir, "character_still.jpg")
    visuals.cover_resize(Image.open(picture), width, height).save(still, quality=92)

    results = []
    talking_works = True
    for i, voice in enumerate(voice_paths):
        step(f"Making your character talk ({i + 1} of {total}) — this uses a GPU, please wait",
             0.18 + 0.5 * i / total)
        if voice is None or not talking_works:
            results.append((still, False))
            continue
        try:
            wav = video_builder.to_wav(voice, os.path.join(work_dir, f"lipsync_{i}.wav"))
            clip = lipsync.talking_clip(picture, wav, os.path.join(work_dir, f"talk_{i}.mp4"), log)
            results.append((clip, True))
        except Exception as error:  # noqa: BLE001 - keep going with the still picture
            talking_works = False
            hint = "" if os.getenv("HF_TOKEN") else " Add HF_TOKEN (your Hugging Face token) to use your own GPU time."
            log(f"⚠️ The talking-face service failed, so the picture doesn't move its mouth "
                f"({str(error)[:200]}).{hint}")
            results.append((still, False))
    return results
