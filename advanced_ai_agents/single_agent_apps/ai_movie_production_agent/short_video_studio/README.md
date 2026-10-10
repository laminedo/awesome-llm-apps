## 🎬 Short Video Studio

An Apple-style web app that turns an idea into a **short video for Facebook Reels and YouTube Shorts**. It is built on the [AI Movie Production Agent](../), with the same idea of AI agents working as a film crew.

Type an idea, and the app:

1. ✍️ **Writes the script.** Gemini writes a hook, scenes, on-screen headlines, a post caption and hashtags. You can edit everything.
2. 🎙️ **Records an AI voiceover.** It uses free Microsoft Edge neural voices in six languages, with Gemini voices as a backup.
3. 🎥 **Makes the visuals.** A switch lets you pick:
   - **Free:** an AI image for each scene with a smooth "Ken Burns" zoom ($0).
   - **Veo AI Video:** real AI-filmed clips from Google Veo (paid by Google, per second of video).
4. 🎞️ **Edits the video.** It adds big headlines and subtitles, then exports an MP4 in **9:16** (Reels/Shorts) or **16:9** (YouTube).

### What you need
- **Python 3.10 or newer** ([download](https://www.python.org/downloads/)).
- A **Google API key**, free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey). The free tier is enough for scripts. Veo needs billing turned on in Google AI Studio.

You do **not** need to install FFmpeg. It comes with the `imageio-ffmpeg` package.

### Run it (copy and paste these one at a time)

```bash
# 1. Go into this folder
cd advanced_ai_agents/single_agent_apps/ai_movie_production_agent/short_video_studio

# 2. (Recommended) create a private Python environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install everything
pip install -r requirements.txt

# 4. Start the app
python app.py
```

Then open **http://localhost:8000** in your browser, click the ⚙️ icon (top right) and paste your Google API key.

> Tip: to avoid pasting the key each time, copy `.env.example` to `.env` and put the key there.

### Private web version (Hugging Face)
A GitHub Action (`.github/workflows/deploy-short-video-studio.yml`) uploads this folder to a **private** Hugging Face Space every time the code changes.
1. Create a Hugging Face **write** token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
2. In your GitHub repo, go to **Settings → Secrets and variables → Actions** and add the secrets `HF_TOKEN` (your Hugging Face token) and `GOOGLE_API_KEY` (your Google key).
3. Push a change. The app appears at `https://huggingface.co/spaces/<your-hf-username>/short-video-studio`.

Only you can open it while logged in to Hugging Face. Videos are deleted from the Space after 24 hours.

### How long does it take?
- **Free engine:** about 1–3 minutes per video.
- **Veo engine:** about 3–10 minutes, because Google films each clip.

Finished videos are saved in the `outputs/` folder.

### Files
| File | What it does |
| --- | --- |
| `app.py` | The web server and the video "job" that runs every step |
| `script_writer.py` | The AI script writer (Gemini) |
| `voiceover.py` | The AI voiceover (Edge voices, with Gemini as a backup) |
| `visuals.py` | Free AI images or Google Veo clips |
| `video_builder.py` | The editor: zoom, headlines, subtitles, final MP4 (FFmpeg) |
| `static/` | The Apple-style web page (HTML, CSS, JavaScript) |

### Troubleshooting
- **"API key not valid"**: paste the key again in ⚙️ Settings.
- **A scene is silent or shows a color gradient**: the free voice or image service was busy or unreachable. Try again. The app tells you on the result screen when this happens.
- **Veo errors**: check that billing is on for your key. If Google renames the models, update `VEO_MODEL` / `VEO_FAST_MODEL` in `.env` ([model list](https://ai.google.dev/gemini-api/docs/video)).
