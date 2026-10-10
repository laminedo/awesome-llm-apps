// Short Video Studio - front-end logic (plain JavaScript, no build step).

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const storage = {
  get(key, fallback = null) {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ }
  },
};

const state = {
  format: "vertical",
  duration: "30",
  veo_quality: "fast",
  voice_speed: "Normal",
  engine: "free",
  ...storage.get("prefs", {}),
};
let voices = {};
let script = null;
let serverHasKey = false;

// ---------- small helpers ----------

function toast(message, ms = 3200) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove("show"), ms);
}

function savePrefs() {
  storage.set("prefs", {
    format: state.format, duration: state.duration, veo_quality: state.veo_quality,
    voice_speed: state.voice_speed, engine: state.engine,
    style: $("#style").value, language: $("#language").value, voice: $("#voice").value,
    subtitles: $("#subtitles").checked,
  });
}

function apiKey() { return storage.get("apiKey", ""); }

async function api(path, body) {
  const response = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json", "X-Google-Api-Key": apiKey() },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(", ") : data.detail;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return data;
}

function showView(n) {
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view${n}`));
  $$("#navSteps span").forEach((s) => {
    const step = Number(s.dataset.step);
    s.classList.toggle("active", step === n);
    s.classList.toggle("done", step < n);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function needKey() {
  if (serverHasKey || apiKey()) return false;
  $("#settingsBtn").classList.add("attention");
  $("#settings").showModal();
  toast("Add your Google API key first");
  return true;
}

function sceneCount() {
  const seconds = Number(state.duration);
  return Math.max(3, Math.min(10, Math.round(seconds / (state.engine === "veo" ? 7 : 5))));
}

// ---------- step 1: idea & settings ----------

function setupSegmented() {
  $$(".segmented").forEach((group) => {
    const name = group.dataset.name;
    group.querySelectorAll("button").forEach((btn) => {
      btn.classList.toggle("selected", btn.dataset.value === String(state[name]));
      btn.addEventListener("click", () => {
        state[name] = btn.dataset.value;
        group.querySelectorAll("button").forEach((b) => b.classList.toggle("selected", b === btn));
        updateVeoNote();
        savePrefs();
      });
    });
  });
}

function setupEngine() {
  const select = (value) => {
    state.engine = value;
    $$("#engineSwitch .engine").forEach((b) => b.classList.toggle("selected", b.dataset.value === value));
    $("#veoOptions").hidden = value !== "veo";
    updateVeoNote();
  };
  $$("#engineSwitch .engine").forEach((btn) =>
    btn.addEventListener("click", () => { select(btn.dataset.value); savePrefs(); }));
  select(state.engine);
}

function updateVeoNote() {
  const clips = script ? script.scenes.length : sceneCount();
  $("#veoNote").innerHTML =
    `Google Veo will film <b>${clips} clips</b> (about 8 seconds each). Veo is billed by Google per second of video ` +
    `— check current prices on <a href="https://ai.google.dev/gemini-api/docs/pricing" target="_blank" rel="noopener">Google's pricing page</a>. ` +
    `Any clip that fails falls back to a free AI image.`;
}

function fillVoices(prefs) {
  const languages = Object.keys(voices);
  $("#language").innerHTML = languages.map((l) => `<option>${l}</option>`).join("");
  $("#language").value = prefs.language && voices[prefs.language] ? prefs.language : "English";
  const renderVoices = () => {
    const list = voices[$("#language").value] || [];
    $("#voice").innerHTML = list.map((v) => `<option value="${v.id}">${v.name} · ${v.gender}</option>`).join("");
  };
  renderVoices();
  if (prefs.voice && [...$("#voice").options].some((o) => o.value === prefs.voice)) $("#voice").value = prefs.voice;
  $("#language").addEventListener("change", () => { renderVoices(); savePrefs(); });
}

async function writeScript() {
  const idea = $("#idea").value.trim();
  if (idea.length < 3) { toast("Describe your idea first ✍️"); $("#idea").focus(); return; }
  if (needKey()) return;

  const btn = $("#writeBtn");
  btn.classList.add("loading"); btn.disabled = true;
  $("#rewriteBtn").disabled = true;
  try {
    script = await api("/api/script", {
      idea,
      style: $("#style").value,
      platform: state.format === "vertical" ? "Facebook Reels and YouTube Shorts (vertical 9:16)" : "YouTube (horizontal 16:9)",
      duration: Number(state.duration),
      language: $("#language").value,
      engine: state.engine,
    });
    renderScript();
    showView(2);
  } catch (error) {
    toast(error.message, 6000);
  } finally {
    btn.classList.remove("loading"); btn.disabled = false;
    $("#rewriteBtn").disabled = false;
  }
}

// ---------- step 2: script editor ----------

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function renderScript() {
  $("#scriptTitle").textContent = script.title;
  $("#caption").value = script.caption;
  $("#hashtags").value = (script.hashtags || []).join(" ");
  $("#scenes").innerHTML = script.scenes.map((scene, i) => `
    <div class="card scene" data-index="${i}">
      <div class="scene-head">
        <span class="scene-num"><b>${i + 1}</b>${i === 0 ? "Hook" : i === script.scenes.length - 1 ? "Call to action" : "Scene"}</span>
        ${script.scenes.length > 1 ? `<button class="scene-remove" data-remove="${i}">Remove</button>` : ""}
      </div>
      <label class="label">On-screen headline</label>
      <input type="text" class="headline-input" data-field="on_screen_text" value="${escapeHtml(scene.on_screen_text)}" />
      <label class="label">Voiceover</label>
      <textarea rows="2" data-field="narration">${escapeHtml(scene.narration)}</textarea>
      <label class="label">What we see</label>
      <textarea rows="2" data-field="visual_prompt">${escapeHtml(scene.visual_prompt)}</textarea>
    </div>`).join("");

  $$("#scenes [data-field]").forEach((input) => {
    input.addEventListener("input", () => {
      const index = Number(input.closest(".scene").dataset.index);
      script.scenes[index][input.dataset.field] = input.value;
    });
  });
  $$("#scenes [data-remove]").forEach((btn) => {
    btn.addEventListener("click", () => {
      script.scenes.splice(Number(btn.dataset.remove), 1);
      renderScript();
      updateVeoNote();
    });
  });
  updateVeoNote();
}

// ---------- step 3: make the video ----------

let pollTimer = null;

function setProgress(fraction, text) {
  const pct = Math.round(fraction * 100);
  $("#percent").textContent = `${pct}%`;
  $("#ringBar").style.strokeDashoffset = String(327 - 327 * fraction);
  if (text) $("#stepText").textContent = text;
}

async function makeVideo() {
  if (needKey()) return;
  script.title = $("#scriptTitle").textContent.trim() || "My short video";
  script.caption = $("#caption").value.trim();
  script.hashtags = $("#hashtags").value.split(/\s+/).filter(Boolean);
  const scenes = script.scenes.filter((s) => s.narration.trim() || s.visual_prompt.trim());
  if (!scenes.length) { toast("Your script has no scenes"); return; }
  if (state.engine === "veo" &&
      !confirm(`Veo AI Video is a paid Google service.\n\nThis will film ${scenes.length} clips. Continue?`)) return;

  $("#progressWrap").hidden = false;
  $("#result").hidden = true;
  $("#errorCard").hidden = true;
  $("#logList").innerHTML = "";
  setProgress(0, "Starting…");
  showView(3);

  try {
    const { job_id } = await api("/api/video", {
      title: script.title,
      scenes,
      format: state.format,
      engine: state.engine,
      veo_quality: state.veo_quality,
      voice: $("#voice").value,
      voice_speed: state.voice_speed,
      subtitles: $("#subtitles").checked,
    });
    pollJob(job_id);
  } catch (error) {
    showError(error.message);
  }
}

function pollJob(jobId) {
  clearTimeout(pollTimer);
  const tick = async () => {
    try {
      const job = await api(`/api/jobs/${jobId}`);
      setProgress(job.progress, job.step);
      $("#logList").innerHTML = job.log.map((line) => `<li>${escapeHtml(line)}</li>`).join("");
      if (job.status === "done") return showResult(job);
      if (job.status === "error") return showError(job.error);
    } catch (error) {
      // the server may be busy for a moment - just try again
    }
    pollTimer = setTimeout(tick, 2000);
  };
  tick();
}

function showResult(job) {
  setProgress(1, "Done");
  $("#progressWrap").hidden = true;
  $("#result").hidden = false;
  const wide = state.format === "horizontal";
  $("#device").classList.toggle("wide", wide);
  $(".result-grid").classList.toggle("wide", wide);
  const player = $("#player");
  player.src = job.video_url;
  player.poster = job.thumbnail_url;
  $("#downloadBtn").href = job.video_url;
  $("#downloadBtn").setAttribute("download", job.filename);
  $("#finalCaption").textContent = `${script.caption}\n\n${script.hashtags.join(" ")}`;
  const warnings = job.warnings || [];
  $("#warnings").hidden = !warnings.length;
  $("#warnings").innerHTML = warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("");
  toast(`Your ${job.duration}s video is ready 🎉`);
}

function showError(message) {
  $("#progressWrap").hidden = true;
  $("#errorCard").hidden = false;
  $("#errorText").textContent = message || "Unknown error";
}

// ---------- start ----------

async function init() {
  const prefs = storage.get("prefs", {});
  if (prefs.style) $("#style").value = prefs.style;
  if (typeof prefs.subtitles === "boolean") $("#subtitles").checked = prefs.subtitles;
  setupSegmented();
  setupEngine();

  try {
    const config = await api("/api/config");
    voices = config.voices;
    serverHasKey = config.server_has_key;
  } catch {
    toast("Can't reach the server. Is `python app.py` running?", 8000);
  }
  fillVoices(prefs);
  if (serverHasKey) $("#keyHint").insertAdjacentHTML("afterbegin", "<b>A key is already set in your .env file.</b> ");
  else if (!apiKey()) $("#settingsBtn").classList.add("attention");

  $("#style").addEventListener("change", savePrefs);
  $("#voice").addEventListener("change", savePrefs);
  $("#subtitles").addEventListener("change", savePrefs);
  $$("#ideaExamples .chip").forEach((chip) =>
    chip.addEventListener("click", () => { $("#idea").value = chip.textContent; $("#idea").focus(); }));

  $("#writeBtn").addEventListener("click", writeScript);
  $("#rewriteBtn").addEventListener("click", () => { showView(1); writeScript(); });
  $("#backBtn").addEventListener("click", () => showView(1));
  $("#makeBtn").addEventListener("click", makeVideo);
  $("#retryBtn").addEventListener("click", () => showView(2));
  $("#newBtn").addEventListener("click", () => { script = null; $("#idea").value = ""; showView(1); });
  $("#copyCaption").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText($("#finalCaption").textContent); toast("Copied ✓"); }
    catch { toast("Couldn't copy - select the text and copy it manually"); }
  });

  $("#settingsBtn").addEventListener("click", () => {
    $("#apiKey").value = apiKey();
    $("#settings").showModal();
  });
  $("#saveKey").addEventListener("click", () => {
    storage.set("apiKey", $("#apiKey").value.trim());
    if (apiKey()) $("#settingsBtn").classList.remove("attention");
    toast(apiKey() ? "Key saved in this browser" : "Key removed");
  });
}

init();
