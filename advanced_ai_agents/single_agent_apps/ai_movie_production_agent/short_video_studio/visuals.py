"""Step 3 - The visuals for each scene.

Two engines (you pick with the switch in the app):
  - "free": an AI image per scene, animated later with a slow zoom. Pictures come
            from FLUX.1-schnell on Hugging Face's free GPUs (needs HF_TOKEN; fast and
            reliable), else from Pollinations.ai (no key, but often busy). If both
            fail, a smooth color gradient is used so the video always gets made.
  - "veo":  a real AI video clip per scene from Google Veo (paid, uses your
            Google API key).
"""

import os
import random
import threading
import time
import urllib.parse
import urllib.request

from google.genai import types
from gradio_client import Client

import google_client
from PIL import Image, ImageDraw, ImageFilter

# Veo models to try, newest first ("-preview" names are the Gemini API ones,
# "-001" names the Vertex AI ones). Set VEO_FAST_MODEL / VEO_MODEL to force one.
VEO_MODELS = {
    "fast": google_client.env_models("VEO_FAST_MODEL", [
        "veo-3.1-fast-generate-preview", "veo-3.1-fast-generate-001", "veo-3.0-fast-generate-001",
    ]),
    "best": google_client.env_models("VEO_MODEL", [
        "veo-3.1-generate-preview", "veo-3.1-generate-001", "veo-3.0-generate-001",
    ]),
}
VEO_RESOLUTION = os.getenv("VEO_RESOLUTION", "720p")

IMAGE_STYLE = "cinematic, ultra detailed, dramatic lighting, shallow depth of field, 4k"

# Pollinations lets anonymous users make about one picture every 15 seconds and
# answers "402"/"429" when asked too fast. A free key from enter.pollinations.ai
# (POLLINATIONS_TOKEN in .env) lifts that limit.
POLLINATIONS_TOKEN = os.getenv("POLLINATIONS_TOKEN", "").strip()
_MIN_GAP = 2 if POLLINATIONS_TOKEN else 16
_last_request = 0.0
_request_lock = threading.Lock()


def _wait_turn() -> None:
    """Space out picture requests so the free service doesn't refuse them."""
    global _last_request
    with _request_lock:
        wait = _last_request + _MIN_GAP - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_request = time.time()


# FLUX.1-schnell on Hugging Face's free "ZeroGPU" computers: ~5 seconds a picture.
# The GPU time is counted on the account of HF_TOKEN (free accounts get a small daily amount).
FLUX_SPACE = os.getenv("FLUX_SPACE", "black-forest-labs/FLUX.1-schnell")
FLUX_PAUSE_SECONDS = 10 * 60  # after a failure (e.g. daily GPU time used up), skip FLUX a while
_flux_client = None
_flux_paused_until = 0.0
_flux_lock = threading.Lock()


def _flux_image(prompt: str, req_w: int, req_h: int) -> str:
    """Make a picture with FLUX on Hugging Face. Returns the downloaded file path."""
    global _flux_client, _flux_paused_until
    token = os.getenv("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError("no HF_TOKEN")
    if time.time() < _flux_paused_until:
        raise RuntimeError("FLUX paused after an earlier failure")
    with _flux_lock:
        try:
            if _flux_client is None:
                _flux_client = Client(FLUX_SPACE, token=token, verbose=False)
            # Arguments: prompt, seed, randomize seed, width, height, steps.
            result = _flux_client.predict(prompt, 0, True, req_w, req_h, 4, api_name="/infer")
        except Exception:
            _flux_client = None
            _flux_paused_until = time.time() + FLUX_PAUSE_SECONDS
            raise
    image = result[0] if isinstance(result, (list, tuple)) else result
    if isinstance(image, dict):
        image = image.get("path")
    if not image or not os.path.exists(image):
        raise RuntimeError("FLUX returned no picture")
    return image

# Pleasant color pairs for the fallback gradients.
GRADIENTS = [
    ((10, 132, 255), (191, 90, 242)),
    ((255, 55, 95), (255, 159, 10)),
    ((48, 209, 88), (100, 210, 255)),
    ((94, 92, 230), (255, 55, 95)),
    ((255, 214, 10), (255, 69, 58)),
    ((100, 210, 255), (94, 92, 230)),
]


def cover_resize(image: Image.Image, width: int, height: int) -> Image.Image:
    """Resize + center-crop an image so it exactly fills width x height."""
    image = image.convert("RGB")
    scale = max(width / image.width, height / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def gradient_image(width: int, height: int, index: int) -> Image.Image:
    """A soft, colorful, Apple-wallpaper-like gradient (used as a fallback)."""
    start, end = GRADIENTS[index % len(GRADIENTS)]
    small = Image.new("RGB", (64, 64))
    pixels = small.load()
    for y in range(64):
        for x in range(64):
            t = (x + y) / 126
            pixels[x, y] = tuple(round(s + (e - s) * t) for s, e in zip(start, end))
    image = small.resize((width, height), Image.BICUBIC)

    # A few big blurred "light blobs" for depth.
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rng = random.Random(index)
    for _ in range(4):
        r = rng.randint(width // 4, width // 2)
        cx, cy = rng.randint(0, width), rng.randint(0, height)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 60))
    overlay = overlay.filter(ImageFilter.GaussianBlur(width // 8))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def free_image(prompt: str, width: int, height: int, index: int, out_path: str, log) -> str:
    """Make a free AI image for a scene: FLUX, then Pollinations, then a gradient."""
    full_prompt = f"{prompt}, {IMAGE_STYLE}"
    # Ask for a smaller image (faster), we upscale it afterwards.
    req_w, req_h = (768, 1344) if height > width else (1344, 768)
    url = (
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(full_prompt)
        + f"?width={req_w}&height={req_h}&nologo=true&seed={random.randint(1, 10**6)}"
    )
    headers = {"User-Agent": "ShortVideoStudio/1.0"}
    if POLLINATIONS_TOKEN:
        headers["Authorization"] = f"Bearer {POLLINATIONS_TOKEN}"
    try:
        cover_resize(Image.open(_flux_image(full_prompt, req_w, req_h)), width, height).save(out_path, quality=95)
        return out_path
    except Exception as error:  # noqa: BLE001 - use the next free picture service
        if os.getenv("HF_TOKEN", "").strip() and "paused" not in str(error):
            log(f"Hugging Face pictures unavailable ({str(error)[:120] or type(error).__name__}), "
                "using Pollinations…")

    raw_path = out_path + ".download"
    for attempt in range(3):
        try:
            _wait_turn()
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=120) as response, open(raw_path, "wb") as file:
                file.write(response.read())
            image = Image.open(raw_path)
            cover_resize(image, width, height).save(out_path, quality=95)
            os.remove(raw_path)
            return out_path
        except Exception as error:  # noqa: BLE001 - network hiccups / rate limits
            code = getattr(error, "code", "")
            log(f"Image service busy ({code or type(error).__name__}), attempt {attempt + 1}/3…")
            if attempt < 2:
                time.sleep(10 * (attempt + 1))

    log("⚠️ The free image service could not be reached, so one scene uses a color gradient.")
    gradient_image(width, height, index).save(out_path, quality=95)
    return out_path


def veo_clip(api_key: str, prompt: str, aspect_ratio: str, quality: str, out_path: str, log) -> str:
    """Generate one ~8 second AI video clip with Google Veo. Raises on failure."""
    config = types.GenerateVideosConfig(
        aspect_ratio=aspect_ratio,
        resolution=VEO_RESOLUTION,
        number_of_videos=1,
        negative_prompt="text, letters, subtitles, captions, watermark, logo",
        # Never auto-retry starting a clip: a retry could be billed as a second clip.
        http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
    )

    def start(client, model):
        operation = client.models.generate_videos(
            model=model, source=types.GenerateVideosSource(prompt=prompt), config=config,
        )
        return client, operation

    models = VEO_MODELS.get(quality, VEO_MODELS["fast"])
    client, operation = google_client.call_with_models(api_key, f"veo-{quality}", models, start)
    waited = 0
    while not operation.done:
        time.sleep(10)
        waited += 10
        if waited % 30 == 0:
            log(f"Veo is still filming… ({waited}s)")
        if waited > 15 * 60:
            raise TimeoutError("Veo took longer than 15 minutes")
        operation = client.operations.get(operation)

    if operation.error:
        raise RuntimeError(f"Veo error: {operation.error}")
    videos = operation.response.generated_videos if operation.response else None
    if not videos:
        raise RuntimeError("Veo returned no video (the prompt may have been blocked by safety filters)")

    if not client.vertexai:  # Vertex AI returns the video bytes directly
        client.files.download(file=videos[0].video)
    videos[0].video.save(out_path)
    return out_path
