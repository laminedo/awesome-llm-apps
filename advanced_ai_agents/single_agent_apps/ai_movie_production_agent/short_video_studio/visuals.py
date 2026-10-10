"""Step 3 - The visuals for each scene.

Two engines (you pick with the switch in the app):
  - "free": an AI image per scene from Pollinations.ai (free, no key), animated
            later with a slow zoom. If the image service is busy, a smooth color
            gradient is used instead so the video always gets made.
  - "veo":  a real AI video clip per scene from Google Veo (paid, uses your
            Google API key).
"""

import os
import random
import time
import urllib.parse
import urllib.request

from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFilter

VEO_MODELS = {
    "fast": os.getenv("VEO_FAST_MODEL", "veo-3.1-fast-generate-preview"),
    "best": os.getenv("VEO_MODEL", "veo-3.1-generate-preview"),
}
VEO_RESOLUTION = os.getenv("VEO_RESOLUTION", "720p")

IMAGE_STYLE = "cinematic, ultra detailed, dramatic lighting, shallow depth of field, 4k"

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
    """Download a free AI image for a scene (falls back to a gradient)."""
    full_prompt = f"{prompt}, {IMAGE_STYLE}"
    # Ask for a smaller image (faster), we upscale it afterwards.
    req_w, req_h = (768, 1344) if height > width else (1344, 768)
    url = (
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(full_prompt)
        + f"?width={req_w}&height={req_h}&nologo=true&model=flux&seed={random.randint(1, 10**6)}"
    )
    raw_path = out_path + ".download"
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ShortVideoStudio/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, open(raw_path, "wb") as file:
                file.write(response.read())
            image = Image.open(raw_path)
            cover_resize(image, width, height).save(out_path, quality=95)
            os.remove(raw_path)
            return out_path
        except Exception as error:  # noqa: BLE001 - network hiccups / rate limits
            log(f"Image service busy ({type(error).__name__}), attempt {attempt + 1}/3…")
            if attempt < 2:
                time.sleep(8 * (attempt + 1))

    log("⚠️ The free image service could not be reached, so one scene uses a color gradient.")
    gradient_image(width, height, index).save(out_path, quality=95)
    return out_path


def veo_clip(api_key: str, prompt: str, aspect_ratio: str, quality: str, out_path: str, log) -> str:
    """Generate one ~8 second AI video clip with Google Veo. Raises on failure."""
    client = genai.Client(api_key=api_key)
    operation = client.models.generate_videos(
        model=VEO_MODELS.get(quality, VEO_MODELS["fast"]),
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio,
            resolution=VEO_RESOLUTION,
            number_of_videos=1,
            negative_prompt="text, letters, subtitles, captions, watermark, logo",
        ),
    )
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

    client.files.download(file=videos[0].video)
    videos[0].video.save(out_path)
    return out_path
