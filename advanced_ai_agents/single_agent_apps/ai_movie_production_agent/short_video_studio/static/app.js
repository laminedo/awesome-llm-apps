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
  voice_effect: "Normal",
  engine: "free",
  ...storage.get("prefs", {}),
};
let voices = {};

// Private Hugging Face Spaces give the page a "__sign" login token. Safari blocks the
// login cookie, so we also send the token with every request to stay logged in.
const signToken = new URLSearchParams(location.search).get("__sign");
function withSign(url) {
  if (!signToken || !url) return url;
  return `${url}${url.includes("?") ? "&" : "?"}__sign=${encodeURIComponent(signToken)}`;
}
let script = null;
let serverHasKey = false;
let serverKeyHint = "";
let talkingReady = true;
let characterPhoto = "";  // uploaded photo, shrunk, as a data: URL
let outputMaxAgeHours = 0;

// ---------- small helpers ----------

function toast(message, ms = 3200) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove("show"), ms);
}

function savePrefs() {
  const old = storage.get("prefs", {});
  storage.set("prefs", {
    format: state.format, duration: state.duration, veo_quality: state.veo_quality,
    voice_speed: state.voice_speed, voice_effect: state.voice_effect, engine: state.engine,
    character: $("#character").value,
    // keep the saved language/voice if the lists haven't loaded (e.g. server unreachable)
    style: $("#style").value, language: $("#language").value || old.language, voice: $("#voice").value || old.voice,
    subtitles: $("#subtitles").checked,
  });
}

function apiKey() { return storage.get("apiKey", ""); }

function keyHint(key) { return key.length > 12 ? `${key.slice(0, 4)}…${key.slice(-4)}` : key; }

async function api(path, body) {
  const headers = { "Content-Type": "application/json" };
  // Only send a browser key when you saved one; otherwise the server's key is used.
  if (apiKey() && path !== "/api/config") headers["X-Google-Api-Key"] = apiKey();
  const response = await fetch(withSign(path), {
    method: body ? "POST" : "GET",
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(", ") : data.detail;
    const error = new Error(detail || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return data;
}

function showFormError(message) {
  $("#formError").hidden = !message;
  $("#formError").textContent = message || "";
  if (message) $("#formError").scrollIntoView({ behavior: "smooth", block: "center" });
}

function updateKeyStatus() {
  const browserKey = apiKey();
  let text;
  if (browserKey && serverHasKey) {
    text = `Using the key saved in this browser (${keyHint(browserKey)}). It replaces the server key (${serverKeyHint}).`;
  } else if (browserKey) {
    text = `Using the key saved in this browser (${keyHint(browserKey)}).`;
  } else if (serverHasKey) {
    text = `Using the server key (${serverKeyHint}). Paste a key below only if you want to replace it.`;
  } else {
    text = "No key yet. Paste your Google API key below.";
  }
  $("#keyStatus").textContent = text;
  $("#clearKey").hidden = !(browserKey && serverHasKey);
  $("#keyError").hidden = true;
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
  if (state.engine === "talk") return Math.max(2, Math.min(6, Math.round(seconds / 8)));
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
    $("#talkOptions").hidden = value !== "talk";
    $("#talkTokenNote").hidden = talkingReady;
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

async function writeScript(makeVideoRightAway = false) {
  const idea = $("#idea").value.trim();
  if (idea.length < 3) { toast("Describe your idea first ✍️"); $("#idea").focus(); return; }
  if (state.engine === "talk" && !$("#character").value.trim() && !characterPhoto) {
    toast("Describe your character or upload a photo 🐱"); $("#character").focus(); return;
  }
  if (needKey()) return;
  showFormError("");

  const btn = makeVideoRightAway ? $("#quickBtn") : $("#writeBtn");
  btn.classList.add("loading");
  ["#writeBtn", "#quickBtn", "#rewriteBtn"].forEach((id) => { $(id).disabled = true; });
  try {
    script = await api("/api/script", {
      idea,
      style: $("#style").value,
      platform: state.format === "vertical" ? "Facebook Reels and YouTube Shorts (vertical 9:16)" : "YouTube (horizontal 16:9)",
      duration: Number(state.duration),
      language: $("#language").value,
      engine: state.engine,
      character: state.engine === "talk" ? $("#character").value.trim() : "",
    });
    renderScript();
    if (makeVideoRightAway) await makeVideo();
    else showView(2);
  } catch (error) {
    showFormError(error.message);
  } finally {
    btn.classList.remove("loading");
    ["#writeBtn", "#quickBtn", "#rewriteBtn"].forEach((id) => { $(id).disabled = false; });
  }
}

// Shrink an uploaded photo in the browser (max 1024px) so it uploads quickly.
function readPhoto(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, 1024 / Math.max(img.width, img.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(img.src);
      resolve(canvas.toDataURL("image/jpeg", 0.9));
    };
    img.onerror = () => reject(new Error("This file is not a picture we can read."));
    img.src = URL.createObjectURL(file);
  });
}

function setupCharacterPhoto() {
  const prefs = storage.get("prefs", {});
  if (prefs.character) $("#character").value = prefs.character;
  $("#character").addEventListener("change", savePrefs);
  $("#characterPhoto").addEventListener("change", async () => {
    const file = $("#characterPhoto").files[0];
    if (!file) return;
    try {
      characterPhoto = await readPhoto(file);
      $("#photoPreview").src = characterPhoto;
      $("#photoPreview").hidden = false;
      $("#removePhoto").hidden = false;
    } catch (error) {
      toast(error.message);
    }
  });
  $("#removePhoto").addEventListener("click", () => {
    characterPhoto = "";
    $("#characterPhoto").value = "";
    $("#photoPreview").hidden = true;
    $("#removePhoto").hidden = true;
  });
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
      <input type="text" class="headline-input" data-field="on_screen_text" maxlength="80" value="${escapeHtml(scene.on_screen_text)}" />
      <label class="label">Voiceover</label>
      <textarea rows="2" data-field="narration" maxlength="600">${escapeHtml(scene.narration)}</textarea>
      <label class="label">What we see</label>
      <textarea rows="2" data-field="visual_prompt" maxlength="1500">${escapeHtml(scene.visual_prompt)}</textarea>
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
      character: state.engine === "talk" ? $("#character").value.trim() : "",
      character_image: state.engine === "talk" ? characterPhoto : "",
      voice_effect: state.engine === "talk" ? state.voice_effect : "Normal",
    });
    pollJob(job_id);
  } catch (error) {
    showError(error.message);
  }
}

function pollJob(jobId) {
  clearTimeout(pollTimer);
  let failures = 0;
  const tick = async () => {
    try {
      const job = await api(`/api/jobs/${jobId}`);
      failures = 0;
      setProgress(job.progress, job.step);
      $("#logList").innerHTML = job.log.map((line) => `<li>${escapeHtml(line)}</li>`).join("");
      if (job.status === "done") return showResult(job);
      if (job.status === "error") return showError(job.error);
    } catch (error) {
      if (error.status === 404) {
        return showError("The app restarted and this video was lost. Click “Back to script” and create it again.");
      }
      failures += 1;  // the server may be busy for a moment - try again, but not forever
      if (failures >= 45) {
        return showError("Lost contact with the app for over a minute. Check it is still running, then try again.");
      }
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
  player.src = withSign(job.video_url);
  player.poster = withSign(job.thumbnail_url);
  $("#downloadBtn").href = withSign(job.video_url);
  $("#downloadBtn").setAttribute("download", job.filename);
  $("#finalCaption").textContent = `${script.caption}\n\n${script.hashtags.join(" ")}`;
  const warnings = job.warnings || [];
  $("#warnings").hidden = !warnings.length;
  $("#warnings").innerHTML = warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("");
  $("#expiryNote").hidden = !outputMaxAgeHours;
  $("#expiryNote").textContent = `Download it now: videos are deleted from the server after ${outputMaxAgeHours} hours.`;
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
  setupCharacterPhoto();

  // Buttons work straight away, even while the settings are still loading.
  $("#style").addEventListener("change", savePrefs);
  $("#voice").addEventListener("change", savePrefs);
  $("#subtitles").addEventListener("change", savePrefs);
  $$("#ideaExamples .chip").forEach((chip) =>
    chip.addEventListener("click", () => { $("#idea").value = chip.textContent; $("#idea").focus(); }));

  $("#writeBtn").addEventListener("click", () => writeScript(false));
  $("#quickBtn").addEventListener("click", () => writeScript(true));
  $("#rewriteBtn").addEventListener("click", () => { showView(1); writeScript(); });
  $("#backBtn").addEventListener("click", () => showView(1));
  $("#makeBtn").addEventListener("click", makeVideo);
  $("#retryBtn").addEventListener("click", () => showView(script ? 2 : 1));
  $("#newBtn").addEventListener("click", () => {
    $("#player").pause();
    script = null; $("#idea").value = ""; showFormError(""); updateVeoNote(); showView(1);
  });
  $("#copyCaption").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText($("#finalCaption").textContent); toast("Copied ✓"); }
    catch { toast("Couldn't copy - select the text and copy it manually"); }
  });

  $("#settingsBtn").addEventListener("click", () => {
    $("#apiKey").value = apiKey();
    updateKeyStatus();
    $("#settings").showModal();
  });
  $("#saveKey").addEventListener("click", (event) => {
    const key = $("#apiKey").value.trim();
    if (key && !/^[\x21-\x7E]+$/.test(key)) {
      event.preventDefault();  // keep the sheet open
      $("#keyError").hidden = false;
      $("#keyError").textContent = "This key contains a space or a special character. Copy it again with the copy button on the Google page.";
      return;
    }
    storage.set("apiKey", key);
    if (apiKey() || serverHasKey) $("#settingsBtn").classList.remove("attention");
    toast(apiKey() ? `Key ${keyHint(key)} saved in this browser` : "Using the server key");
    showFormError("");
  });
  $("#clearKey").addEventListener("click", () => {
    storage.set("apiKey", "");
    $("#apiKey").value = "";
    updateKeyStatus();
    toast("Using the server key");
  });

  try {
    const config = await api("/api/config");
    voices = config.voices;
    serverHasKey = config.server_has_key;
    serverKeyHint = config.server_key_hint || "";
    talkingReady = config.talking_ready !== false;
    $("#talkTokenNote").hidden = talkingReady;
    outputMaxAgeHours = config.output_max_age_hours || 0;
  } catch {
    toast("Can't reach the server. Is the app running?", 8000);
  }
  fillVoices(prefs);
  if (!serverHasKey && !apiKey()) $("#settingsBtn").classList.add("attention");
}

init();
