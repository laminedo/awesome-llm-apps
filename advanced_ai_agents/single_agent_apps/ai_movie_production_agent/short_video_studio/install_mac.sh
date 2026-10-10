#!/bin/bash
# One-command installer for Short Video Studio on macOS.
# Usage (paste in Terminal):
#   curl -fsSL https://raw.githubusercontent.com/laminedo/awesome-llm-apps/refs/heads/claude/hopeful-bohr-lm8k5a/advanced_ai_agents/single_agent_apps/ai_movie_production_agent/short_video_studio/install_mac.sh | bash
set -e

BRANCH="claude/hopeful-bohr-lm8k5a"
BASE="https://raw.githubusercontent.com/laminedo/awesome-llm-apps/refs/heads/$BRANCH/advanced_ai_agents/single_agent_apps/ai_movie_production_agent/short_video_studio"
FILES="app.py script_writer.py voiceover.py visuals.py video_builder.py requirements.txt .env.example README.md static/index.html static/style.css static/app.js"
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
say "Downloading Short Video Studio into $APP_DIR…"
mkdir -p "$APP_DIR/static"
for file in $FILES; do
  curl -fsSL -o "$APP_DIR/$file" "$BASE/$file"
done

# 3) Install the Python packages in a private environment.
say "Installing the app (1–2 minutes the first time)…"
cd "$APP_DIR"
[ -x .venv/bin/python ] || "$PY" -m venv .venv
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -r requirements.txt

# 4) Save the Google API key (asked only once).
if ! grep -q "^GOOGLE_API_KEY=..*" .env 2>/dev/null; then
  say "Paste your Google API key and press Enter (it stays hidden; press Enter to skip):"
  read -r -s KEY < /dev/tty || KEY=""
  echo
  if [ -n "$KEY" ]; then
    printf "GOOGLE_API_KEY=%s\n" "$KEY" > .env
    chmod 600 .env
    echo "Key saved in $APP_DIR/.env"
  else
    echo "Skipped. You can paste it later in the app (⚙️ icon, top right)."
  fi
fi

# 5) Create a double-click launcher on the Desktop.
cat > "$LAUNCHER" <<LAUNCH
#!/bin/bash
cd "$APP_DIR"
# Open the browser only once the app is really ready (the first start can be slow).
(for i in \$(seq 1 90); do curl -s -o /dev/null http://127.0.0.1:8000/ && break; sleep 1; done; open "http://127.0.0.1:8000") &
./.venv/bin/python app.py
LAUNCH
chmod +x "$LAUNCHER"

say "All done! ✅"
printf "Next time, just double-click \033[1m'Short Video Studio'\033[0m on your Desktop.\n"
printf "To stop the app, press Control + C in this window (or close it).\n"
say "Starting the app now — your browser will open when it is ready (up to a minute the first time)…"
exec "$LAUNCHER"
