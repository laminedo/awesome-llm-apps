#!/bin/bash
# One-command installer for Short Video Studio on macOS.
# Usage (paste in Terminal):
#   curl -fsSL https://raw.githubusercontent.com/laminedo/awesome-llm-apps/refs/heads/claude/hopeful-bohr-lm8k5a/advanced_ai_agents/single_agent_apps/ai_movie_production_agent/short_video_studio/install_mac.sh | bash
set -e

BRANCH="claude/hopeful-bohr-lm8k5a"
BASE="https://raw.githubusercontent.com/laminedo/awesome-llm-apps/refs/heads/$BRANCH/advanced_ai_agents/single_agent_apps/ai_movie_production_agent/short_video_studio"
FILES="app.py google_client.py script_writer.py voiceover.py visuals.py video_builder.py requirements.txt .env.example README.md static/index.html static/style.css static/app.js"
APP_DIR="$HOME/ShortVideoStudio"
LAUNCHER="$HOME/Desktop/Short Video Studio.command"
PYTHON_PKG="https://www.python.org/ftp/python/3.13.1/python-3.13.1-macos11.pkg"

say() { printf "\n\033[1;34m▶ %s\033[0m\n" "$1"; }

# 1) Find Python 3.10+ (python.org or Homebrew). We skip Apple's built-in 3.9.
say "Looking for Python 3.10 or newer…"
PY=""
for candidate in /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [ -x "$candidate" ] && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$candidate"
  fi
done
if [ -z "$PY" ]; then
  say "Python is not installed yet. Opening the official Python installer for you…"
  curl -fsSL -o /tmp/python-installer.pkg "$PYTHON_PKG"
  open /tmp/python-installer.pkg
  printf "\n👉 Click through the Python installer (Continue → Agree → Install).\n"
  printf "👉 When it says 'The installation was successful', paste the same command in Terminal again.\n\n"
  exit 0
fi
echo "Using $("$PY" --version) at $PY"

# 2) Download the app files (re-running this updates them; your key is kept).
#    Files go to a temporary folder first, so a dropped connection can't break the app.
say "Downloading Short Video Studio into $APP_DIR…"
mkdir -p "$APP_DIR/static"
UPDATE_DIR="$APP_DIR/.update"
rm -rf "$UPDATE_DIR" && mkdir -p "$UPDATE_DIR/static"
for file in $FILES; do
  curl -fsSL -o "$UPDATE_DIR/$file" "$BASE/$file"
done
for file in $FILES; do
  mv -f "$UPDATE_DIR/$file" "$APP_DIR/$file"
done
rm -rf "$UPDATE_DIR"

# 3) Install / update the Python packages in a private environment.
say "Installing the app (1–2 minutes the first time)…"
cd "$APP_DIR"
if ! ./.venv/bin/python -c "import sys" 2>/dev/null; then  # missing or broken: (re)create it
  rm -rf .venv
  "$PY" -m venv .venv
fi
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet --upgrade -r requirements.txt

# 4) Save the Google API key. If one is saved already, you can keep it or replace it.
CURRENT=$(grep -E '^GOOGLE_API_KEY=' .env 2>/dev/null | head -1 | cut -d= -f2- || true)
if [ -n "$CURRENT" ]; then
  say "Your saved Google API key is ${CURRENT:0:4}…${CURRENT: -4}"
  echo "Paste a NEW key to replace it (it stays hidden), or just press Enter to keep it:"
else
  say "Paste your Google API key and press Enter (it stays hidden; press Enter to skip):"
fi
read -r -s KEY < /dev/tty || KEY=""
echo
# Remove spaces, line breaks and invisible paste codes that sometimes come with a copy.
KEY=$(printf '%s' "$KEY" | sed $'s/\x1b\\[20[01]~//g' | tr -d '[:space:]')
if [ -n "$KEY" ]; then
  { grep -v -E '^GOOGLE_API_KEY=' .env 2>/dev/null || true; printf "GOOGLE_API_KEY=%s\n" "$KEY"; } > .env.new
  mv -f .env.new .env
  chmod 600 .env
  echo "Key ${KEY:0:4}…${KEY: -4} saved in $APP_DIR/.env"
elif [ -n "$CURRENT" ]; then
  echo "Keeping your saved key."
else
  echo "Skipped. You can paste it later in the app (⚙️ icon, top right)."
fi

# 5) Create a double-click launcher on the Desktop.
cat > "$LAUNCHER" <<LAUNCH
#!/bin/bash
cd "$APP_DIR"
if curl -s -o /dev/null http://127.0.0.1:8000/; then
  echo "Short Video Studio is already running in another Terminal window. Opening it…"
  open "http://127.0.0.1:8000"
  exit 0
fi
# Open the browser only once the app is really ready (the first start can be slow).
(for i in \$(seq 1 90); do curl -s -o /dev/null http://127.0.0.1:8000/ && { open "http://127.0.0.1:8000"; exit 0; }; sleep 1; done) &
./.venv/bin/python app.py
LAUNCH
chmod +x "$LAUNCHER"

# 6) Stop an older copy that is still running, so the updated app is the one you use.
if curl -s http://127.0.0.1:8000/api/config 2>/dev/null | grep -q server_has_key; then
  say "Stopping the copy of Short Video Studio that is already running…"
  lsof -nP -iTCP:8000 -sTCP:LISTEN -t 2>/dev/null | xargs kill 2>/dev/null || true
  for i in $(seq 1 20); do curl -s -o /dev/null http://127.0.0.1:8000/ || break; sleep 0.5; done
fi

say "All done! ✅"
printf "Next time, just double-click \033[1m'Short Video Studio'\033[0m on your Desktop.\n"
printf "To stop the app, press Control + C in this window (or close it).\n"
say "Starting the app now — your browser will open when it is ready (up to a minute the first time)…"
exec "$LAUNCHER"
