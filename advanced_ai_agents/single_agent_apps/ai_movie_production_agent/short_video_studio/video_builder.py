"""Step 4 - The video editor.

Puts everything together with FFmpeg (installed automatically with the
`imageio-ffmpeg` Python package, so you don't need to install anything else):
  picture/clip + voiceover + big headline + subtitles  ->  one MP4 per scene
  all scenes                                           ->  final MP4
"""

import glob
import os
import re
import subprocess
import textwrap

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, features

try:  # used to draw Arabic correctly when Pillow can't do it by itself (e.g. on a Mac)
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:  # pragma: no cover - optional
    arabic_reshaper = None

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FPS = 30

# Bold fonts to try (macOS, Windows, Linux). The first one found is used.
FONT_CANDIDATES = [
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/seguisb.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    *sorted(glob.glob("/usr/share/fonts/**/Inter-Bold.*", recursive=True)),
    *sorted(glob.glob("/usr/share/fonts/**/Inter*Variable.ttf", recursive=True)),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


# Fonts that contain Arabic letters (most fonts above don't, and would draw boxes).
ARABIC_FONTS = [
    "/System/Library/Fonts/SFArabic.ttf",
    "/System/Library/Fonts/GeezaPro.ttc",
    "/System/Library/Fonts/Supplemental/GeezaPro.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    *sorted(glob.glob("/usr/share/fonts/**/NotoSansArabic-Bold.ttf", recursive=True)),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]
_ARABIC = re.compile("[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_HAS_RAQM = features.check_feature("raqm")  # Pillow can shape Arabic by itself


def _font(size: int, text: str = "") -> ImageFont.FreeTypeFont:
    arabic = bool(_ARABIC.search(text))
    candidates = [*ARABIC_FONTS, *FONT_CANDIDATES] if arabic else FONT_CANDIDATES
    # Without Pillow's own Arabic support we pre-shape the text (see _wrap), so the
    # basic engine must draw it exactly as given.
    engine = ImageFont.Layout.BASIC if arabic and not _HAS_RAQM else None
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size, layout_engine=engine)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr.strip()[-800:]}")


def media_info(path: str) -> tuple[float, bool]:
    """Return (duration in seconds, has an audio track) for a media file."""
    result = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True)
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", result.stderr)
    duration = 0.0
    if match:
        hours, minutes, seconds = match.groups()
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return duration, "Audio:" in result.stderr


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and draw.textlength(f"{lines[-1]} {word}", font=font) <= max_width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    if _ARABIC.search(text) and not _HAS_RAQM and arabic_reshaper:
        # Join the letters and put them right-to-left, one line at a time.
        lines = [get_display(arabic_reshaper.reshape(line)) for line in lines]
    return lines


def headline_overlay(text: str, width: int, height: int, out_path: str) -> str:
    """Big bold headline near the top, with a soft shadow (transparent PNG)."""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _font(int(min(width, height) * 0.085), text)
    lines = _wrap(draw, text.strip(), font, int(width * 0.84))
    line_height = int(font.size * 1.18)
    y = int(height * (0.13 if height > width else 0.10))
    for line in lines:
        line_width = draw.textlength(line, font=font)
        x = (width - line_width) / 2
        for dx, dy in ((0, 4), (0, 6), (3, 5)):  # cheap soft shadow
            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 110))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_height
    image.save(out_path)
    return out_path


def subtitle_overlay(text: str, width: int, height: int, out_path: str) -> str:
    """Subtitle in a rounded, frosted-dark pill near the bottom (transparent PNG)."""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _font(int(min(width, height) * 0.052), text)
    lines = _wrap(draw, text.strip(), font, int(width * 0.78))
    line_height = int(font.size * 1.25)
    pad_x, pad_y = int(font.size * 0.8), int(font.size * 0.5)
    box_w = max(draw.textlength(line, font=font) for line in lines) + pad_x * 2
    box_h = line_height * len(lines) + pad_y * 2
    box_x = (width - box_w) / 2
    box_y = height * (0.70 if height > width else 0.76)
    draw.rounded_rectangle((box_x, box_y, box_x + box_w, box_y + box_h),
                           radius=int(font.size * 0.7), fill=(0, 0, 0, 150))
    y = box_y + pad_y
    for line in lines:
        draw.text(((width - draw.textlength(line, font=font)) / 2, y), line,
                  font=font, fill=(255, 255, 255, 255))
        y += line_height
    image.save(out_path)
    return out_path


def subtitle_chunks(narration: str, duration: float, words_per_chunk: int = 4):
    """Split narration into short chunks timed by their length (approximate lip-sync)."""
    words = narration.split()
    chunks = [" ".join(words[i:i + words_per_chunk]) for i in range(0, len(words), words_per_chunk)]
    total_chars = sum(len(chunk) for chunk in chunks) or 1
    start, timed = 0.0, []
    for chunk in chunks:
        length = duration * len(chunk) / total_chars
        timed.append((chunk, start, start + length))
        start += length
    return timed


def build_scene(
    *,
    index: int,
    visual_path: str,
    visual_is_video: bool,
    voice_path: str | None,
    headline: str,
    narration: str,
    show_subtitles: bool,
    width: int,
    height: int,
    work_dir: str,
    is_last: bool,
    talking: bool = False,
) -> str:
    """Render one scene to an MP4 and return its path.

    talking=True: the clip is a talking-character video whose mouth follows the
    voiceover, so it plays once (last frame held) and its own sound isn't mixed in.
    """
    if voice_path:
        voice_duration, _ = media_info(voice_path)
    else:
        voice_duration = max(2.0, len(narration.split()) / 2.5)
    duration = round(voice_duration + 0.45, 2)

    inputs: list[str] = []
    filters: list[str] = []

    # Input 0: the picture or the video clip.
    if visual_is_video and talking:
        inputs += ["-i", visual_path]
        filters.append(  # whole character on top of a blurred, darker copy (nothing gets cut off)
            f"[0:v]fps={FPS},tpad=stop_mode=clone:stop_duration={duration},split[c1][c2];"
            f"[c1]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
            f"boxblur=30:2,eq=brightness=-0.08[blur];"
            f"[c2]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
            f"[blur][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[bg]"
        )
    elif visual_is_video:
        inputs += ["-stream_loop", "-1", "-i", visual_path]
        filters.append(
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,fps={FPS}[bg]"
        )
    else:
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", str(duration), "-i", visual_path]
        # Slow "Ken Burns" zoom: in on even scenes, out on odd scenes.
        zoom = f"(1+0.12*t/{duration})" if index % 2 == 0 else f"(1.12-0.12*t/{duration})"
        zoomed_w, zoomed_h = f"trunc({width}*{zoom}/2)*2", f"trunc({height}*{zoom}/2)*2"
        filters.append(  # the crop offset follows the zoom so the picture stays centred
            f"[0:v]scale=w='{zoomed_w}':h='{zoomed_h}':eval=frame,"
            f"crop={width}:{height}:x='({zoomed_w}-{width})/2':y='({zoomed_h}-{height})/2',"
            f"setsar=1,fps={FPS}[bg]"
        )

    # Input 1: the voiceover (or silence).
    if voice_path:
        inputs += ["-i", voice_path]
    else:
        inputs += ["-f", "lavfi", "-t", str(duration), "-i", "anullsrc=r=44100:cl=stereo"]

    # Overlays: headline (fades in) + timed subtitle chunks.
    current, next_input = "bg", 2
    if headline.strip():
        png = headline_overlay(headline, width, height, os.path.join(work_dir, f"headline_{index}.png"))
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", str(duration), "-i", png]
        filters.append(f"[{next_input}:v]format=rgba,fade=t=in:st=0.1:d=0.35:alpha=1[h]")
        filters.append(f"[{current}][h]overlay=0:0:shortest=1[vh]")
        current, next_input = "vh", next_input + 1
    if show_subtitles and narration.strip():
        for n, (chunk, start, end) in enumerate(subtitle_chunks(narration, voice_duration)):
            png = subtitle_overlay(chunk, width, height, os.path.join(work_dir, f"sub_{index}_{n}.png"))
            inputs += ["-i", png]
            label = f"vs{n}"
            filters.append(
                f"[{current}][{next_input}:v]overlay=0:0:enable='between(t,{start:.2f},{end:.2f})'[{label}]"
            )
            current, next_input = label, next_input + 1

    if is_last:
        filters.append(f"[{current}]fade=t=out:st={max(0, duration - 0.5)}:d=0.5[vout]")
    else:
        filters.append(f"[{current}]null[vout]")

    # Audio: voice, plus the Veo clip's own sound quietly underneath (if it has any).
    voice_audio = "[1:a]aresample=44100,aformat=channel_layouts=stereo,apad"
    if visual_is_video and not talking and media_info(visual_path)[1]:
        filters.append(f"{voice_audio}[voice]")
        filters.append("[0:a]aresample=44100,aformat=channel_layouts=stereo,volume=0.22[sfx]")
        filters.append("[voice][sfx]amix=inputs=2:duration=first:normalize=0[aout]")
    else:
        filters.append(f"{voice_audio}[aout]")

    out_path = os.path.join(work_dir, f"scene_{index:02d}.mp4")
    run_ffmpeg([
        *inputs,
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", "[aout]",
        "-t", str(duration), "-r", str(FPS),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        out_path,
    ])
    return out_path


VOICE_EFFECTS = {  # pitch change, keeping the same speed
    "Baby": 1.35,
    "Chipmunk": 1.6,
    "Deep": 0.8,
}


def voice_effect(voice_path: str, effect: str, out_path: str) -> str:
    """Make a voice higher (baby / chipmunk) or deeper. Returns the new file path."""
    factor = VOICE_EFFECTS.get(effect)
    if not factor:
        return voice_path
    run_ffmpeg(["-i", voice_path, "-af",
                f"aresample=44100,asetrate={int(44100 * factor)},aresample=44100,atempo={1 / factor:.4f}",
                out_path])
    return out_path


def to_wav(path: str, out_path: str) -> str:
    """Convert audio to a 16 kHz mono WAV (what talking-face models expect)."""
    run_ffmpeg(["-i", path, "-ar", "16000", "-ac", "1", out_path])
    return out_path


def join_scenes(scene_paths: list[str], out_path: str, work_dir: str) -> str:
    """Glue all scene MP4s together into the final video."""
    list_file = os.path.join(work_dir, "scenes.txt")
    with open(list_file, "w", encoding="utf-8") as file:
        for path in scene_paths:
            escaped = os.path.abspath(path).replace("'", "'\\''")  # FFmpeg list quoting
            file.write(f"file '{escaped}'\n")
    run_ffmpeg([
        "-f", "concat", "-safe", "0", "-i", list_file,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        out_path,
    ])
    return out_path


def make_thumbnail(video_path: str, out_path: str) -> str:
    start = "1" if media_info(video_path)[0] > 1.5 else "0"
    run_ffmpeg(["-ss", start, "-i", video_path, "-frames:v", "1", "-q:v", "3", out_path])
    return out_path


def safe_filename(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", textwrap.shorten(text, 50, placeholder="")).strip("-")
    return slug.lower() or "video"
