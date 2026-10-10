"""Short Video Studio - the web server.

Run it with:   python app.py
Then open:     http://localhost:8000
"""

import os
import shutil
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

load_dotenv()  # read GOOGLE_API_KEY etc. from a .env file if you made one

try:  # use up-to-date security certificates (fixes HTTPS errors with Python from python.org on Mac)
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

import uvicorn  # noqa: E402
from fastapi import FastAPI, Header, HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import video_builder  # noqa: E402
import visuals  # noqa: E402
from script_writer import write_script  # noqa: E402
from voiceover import VOICES, make_voiceover  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(HERE, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

FORMATS = {
    "vertical": {"size": (1080, 1920), "aspect": "9:16"},  # Reels / Shorts
    "horizontal": {"size": (1920, 1080), "aspect": "16:9"},  # classic YouTube
}

app = FastAPI(title="Short Video Studio")


# ---------- request models ----------

class ScriptRequest(BaseModel):
    idea: str = Field(min_length=3, max_length=2000)
    style: str = "Inspiring"
    platform: str = "YouTube Shorts"
    duration: int = Field(default=30, ge=10, le=90)
    language: str = "English"
    engine: str = "free"


class Scene(BaseModel):
    narration: str
    on_screen_text: str = ""
    visual_prompt: str


class VideoRequest(BaseModel):
    title: str = "My short video"
    scenes: list[Scene] = Field(min_length=1, max_length=12)
    format: str = "vertical"
    engine: str = "free"  # "free" or "veo"
    veo_quality: str = "fast"  # "fast" or "best"
    voice: str = "en-US-AndrewNeural"
    voice_speed: str = "Normal"
    subtitles: bool = True


def resolve_key(header_key: str | None) -> str:
    key = (header_key or "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        raise HTTPException(400, "Please add your Google API key in Settings (top right).")
    return key


# ---------- background video jobs ----------

JOBS: dict[str, dict] = {}


def run_job(job_id: str, request: VideoRequest, api_key: str) -> None:
    job = JOBS[job_id]
    work_dir = os.path.join(OUTPUT_DIR, job_id, "work")
    os.makedirs(work_dir, exist_ok=True)
    width, height = FORMATS[request.format]["size"]
    aspect = FORMATS[request.format]["aspect"]
    scenes = request.scenes
    total = len(scenes)

    def log(message: str) -> None:
        job["log"].append(message)
        if message.startswith("⚠️"):
            job["warnings"].append(message)

    def step(message: str, progress: float) -> None:
        job["step"], job["progress"] = message, round(progress, 3)
        log(message)

    try:
        # 1) Voiceovers
        voice_paths = []
        for i, scene in enumerate(scenes):
            step(f"Recording voiceover {i + 1} of {total}", 0.02 + 0.13 * i / total)
            voice_paths.append(make_voiceover(
                scene.narration, request.voice, request.voice_speed, api_key,
                os.path.join(work_dir, f"voice_{i}"), log,
            ))

        # 2) Visuals
        visual_paths: list[tuple[str, bool]] = [("", False)] * total
        if request.engine == "veo":
            step(f"Filming {total} AI clips with Google Veo (this takes a few minutes)", 0.15)
            done_count = 0
            lock = threading.Lock()

            def film(i: int):
                nonlocal done_count
                path = os.path.join(work_dir, f"clip_{i}.mp4")
                try:
                    visuals.veo_clip(api_key, scenes[i].visual_prompt, aspect,
                                     request.veo_quality, path, log)
                    result = (path, True)
                except Exception as error:  # noqa: BLE001 - keep going with a free picture
                    log(f"⚠️ Scene {i + 1}: Veo failed ({error}). A free AI image was used instead.")
                    image = os.path.join(work_dir, f"image_{i}.jpg")
                    result = (visuals.free_image(scenes[i].visual_prompt, width, height, i, image, log), False)
                with lock:
                    done_count += 1
                    step(f"Filmed {done_count} of {total} clips", 0.15 + 0.55 * done_count / total)
                return i, result

            with ThreadPoolExecutor(max_workers=int(os.getenv("VEO_PARALLEL", "2"))) as pool:
                for i, result in pool.map(film, range(total)):
                    visual_paths[i] = result
        else:
            for i, scene in enumerate(scenes):
                step(f"Creating AI image {i + 1} of {total}", 0.15 + 0.45 * i / total)
                image = os.path.join(work_dir, f"image_{i}.jpg")
                visual_paths[i] = (visuals.free_image(scene.visual_prompt, width, height, i, image, log), False)

        # 3) Edit each scene
        scene_files = []
        for i, scene in enumerate(scenes):
            step(f"Editing scene {i + 1} of {total}", 0.70 + 0.25 * i / total)
            path, is_video = visual_paths[i]
            scene_files.append(video_builder.build_scene(
                index=i, visual_path=path, visual_is_video=is_video, voice_path=voice_paths[i],
                headline=scene.on_screen_text, narration=scene.narration,
                show_subtitles=request.subtitles, width=width, height=height,
                work_dir=work_dir, is_last=i == total - 1,
            ))

        # 4) Final export
        step("Exporting your video", 0.96)
        name = f"{video_builder.safe_filename(request.title)}-{request.format}.mp4"
        final_path = os.path.join(OUTPUT_DIR, job_id, name)
        video_builder.join_scenes(scene_files, final_path, work_dir)
        video_builder.make_thumbnail(final_path, os.path.join(OUTPUT_DIR, job_id, "thumbnail.jpg"))
        if os.getenv("KEEP_WORK_FILES", "").lower() not in ("1", "true", "yes"):
            shutil.rmtree(work_dir, ignore_errors=True)

        job.update(
            status="done", progress=1.0, step="Your video is ready",
            video_url=f"/outputs/{job_id}/{name}", thumbnail_url=f"/outputs/{job_id}/thumbnail.jpg",
            duration=round(video_builder.media_info(final_path)[0], 1), filename=name,
        )
    except Exception as error:  # noqa: BLE001 - report any problem to the user
        traceback.print_exc()
        job.update(status="error", step="Something went wrong", error=str(error))


# ---------- API routes ----------

@app.get("/api/config")
def config():
    return {"server_has_key": bool(os.getenv("GOOGLE_API_KEY")), "voices": VOICES}


@app.post("/api/script")
def create_script(request: ScriptRequest, x_google_api_key: str | None = Header(default=None)):
    api_key = resolve_key(x_google_api_key)
    try:
        return write_script(api_key, request.idea, request.style, request.platform,
                            request.duration, request.language, request.engine)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(502, f"The script writer had a problem: {error}") from error


@app.post("/api/video")
def create_video(request: VideoRequest, x_google_api_key: str | None = Header(default=None)):
    if request.format not in FORMATS:
        raise HTTPException(400, "Unknown format")
    api_key = resolve_key(x_google_api_key)
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"id": job_id, "status": "running", "progress": 0.0, "step": "Starting",
                    "log": [], "warnings": [], "created": time.time()}
    threading.Thread(target=run_job, args=(job_id, request, api_key), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")


@app.get("/")
def home():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"\n  🎬 Short Video Studio is running →  http://localhost:{port}\n")
    uvicorn.run(app, host="127.0.0.1", port=port)
