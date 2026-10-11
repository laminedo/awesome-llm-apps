## 🎬 Short Video Studio

An Apple-style web app that turns an idea into a **short video for Facebook Reels and YouTube Shorts**. It is built on the [AI Movie Production Agent](../), with the same idea of AI agents working as a film crew.

Type an idea, and the app:

1. ✍️ **Writes the script.** Gemini writes a hook, scenes, on-screen headlines, a post caption and hashtags. You can edit everything.
2. 🎙️ **Records an AI voiceover.** It uses free Microsoft Edge neural voices in six languages, with Gemini voices as a backup.
3. 🎥 **Makes the visuals.** A switch lets you pick:
   - **Free:** an AI image for each scene with a smooth "Ken Burns" zoom ($0).
   - **Veo AI Video:** real AI-filmed clips from Google Veo (paid by Google, per second of video).
   - **Talking character:** a photo or AI character whose mouth moves along with the voice (see below).
4. 🎞️ **Edits the video.** It adds big headlines and subtitles, then exports an MP4 in **9:16** (Reels/Shorts) or **16:9** (YouTube).

### 🗣️ Talking character mode
Upload a photo or describe a character (a baby, a cat, a grandpa…). The script is written in the character's own voice, and its mouth moves along with the voiceover. You can add a voice effect: **Baby**, **Chipmunk** or **Deep**.

- The mouth animation runs on free GPU Spaces on Hugging Face. **MoDA** is fast and handles human faces. **LongCat-Video-Avatar 1.5** is slower but also works for animals.
- It needs a Hugging Face token (`HF_TOKEN`) so the GPU time counts on your account; Hugging Face PRO gets more GPU time. The online version gets it automatically from the `HF_TOKEN` GitHub secret (or `HF_GPU_TOKEN`, if you set one). On a Mac, the installer asks for it.
- Animal videos use a lot of GPU time (about 1.5 minutes per 5 seconds of talking), so keep them at 15–30 seconds.
- If the talking service is busy or fails, the video still gets made with the still picture, and a warning is shown.
- Only use photos you have permission to use, and mark the videos as AI-generated when you post them.

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

Then open **http://127.0.0.1:8000** in your browser, click the ⚙️ icon (top right) and paste your Google API key.

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
| `video_builder.py` | The editor: zoom, headlines, subtitles, voice effects, final MP4 (FFmpeg) |
| `talking.py`, `lipsync.py` | Talking character mode: the character picture and the mouth animation on Hugging Face GPUs |
| `static/` | The Apple-style web page (HTML, CSS, JavaScript) |

### Troubleshooting
- **"API key not valid"**: paste the key again in ⚙️ Settings.
- **A scene is silent or shows a color gradient**: the free voice or image service was busy or unreachable. Try again. The app tells you on the result screen when this happens.
- **Which key is used?** Open ⚙️ Settings: it shows the start and end of the key in use. A key saved in the browser replaces the server key; click **Use the server key** to go back. Re-running the Mac installer lets you replace the saved key.
- **Retired AI models**: Google retires models over time. The app tries a list of current models and uses the first one that works. To force one, set `GEMINI_MODEL`, `GEMINI_TTS_MODEL`, `VEO_FAST_MODEL` or `VEO_MODEL` in `.env` ([model list](https://ai.google.dev/gemini-api/docs/models)).
- **Veo errors**: check that billing is on for your key.
