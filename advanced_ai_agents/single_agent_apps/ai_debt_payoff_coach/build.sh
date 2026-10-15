#!/usr/bin/env bash
# Wraps app.html (the page content) into a standalone index.html.
# Adds a strict Content Security Policy: only the app's own inline script (pinned by its hash) and the
# bundled Supabase library may run, and the page may only talk to Google Fonts, Supabase and the Gemini API.
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source ./supabase.config
[[ "$SUPABASE_URL" =~ ^https://[a-z0-9]{20}\.supabase\.co$ ]] || { echo "bad SUPABASE_URL" >&2; exit 1; }
[[ "$SUPABASE_KEY" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "bad SUPABASE_KEY" >&2; exit 1; }
SB_JS=vendor/supabase-js-2.45.4.js
HASH=$(python3 - <<'PY'
import re, hashlib, base64
src = open("app.html", encoding="utf-8").read()
assert len(re.findall(r"<script\b", src)) == 1, "expected exactly one <script> tag"
scripts = re.findall(r"<script>(.*?)</script>", src, re.S)
assert len(scripts) == 1, "the one <script> tag must be a plain inline <script>"
h = base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode()
print(h)
PY
)
SB_HOST=${SUPABASE_URL#https://}
CSP="default-src 'none'; script-src 'self' 'sha256-${HASH}'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src data: blob:; connect-src ${SUPABASE_URL} wss://${SB_HOST} https://generativelanguage.googleapis.com; base-uri 'none'; form-action 'none'; object-src 'none'"
{
  printf '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
  printf '<meta http-equiv="Content-Security-Policy" content="%s">\n' "$CSP"
  printf '<meta name="referrer" content="no-referrer">\n'
  printf '<meta name="supabase-url" content="%s">\n<meta name="supabase-key" content="%s">\n' "$SUPABASE_URL" "$SUPABASE_KEY"
  printf '<meta name="pdfjs-base" content="vendor/">\n'
  printf '<script src="%s"></script>\n' "$SB_JS"
  printf '</head>\n<body>\n'
  cat app.html
  printf '\n</body>\n</html>\n'
} > index.html
echo "Built index.html"
