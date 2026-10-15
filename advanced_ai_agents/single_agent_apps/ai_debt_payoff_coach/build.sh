#!/usr/bin/env bash
# Wraps app.html (the page content) into a standalone index.html you can double-click to open.
# Adds a strict Content Security Policy: only the app's own inline script (pinned by its hash) may run,
# and the page may only talk to Google Fonts and the Gemini API.
set -euo pipefail
cd "$(dirname "$0")"
HASH=$(python3 - <<'PY'
import re, hashlib, base64
src = open("app.html", encoding="utf-8").read()
assert len(re.findall(r"<script\b", src)) == 1, "expected exactly one <script> tag"
scripts = re.findall(r"<script>(.*?)</script>", src, re.S)
assert len(scripts) == 1, "the one <script> tag must be a plain inline <script>"
print(base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode())
PY
)
CSP="default-src 'none'; script-src 'sha256-${HASH}'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src data: blob:; connect-src https://generativelanguage.googleapis.com; base-uri 'none'; form-action 'none'; object-src 'none'"
{
  printf '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
  printf '<meta http-equiv="Content-Security-Policy" content="%s">\n' "$CSP"
  printf '<meta name="referrer" content="no-referrer">\n</head>\n<body>\n'
  cat app.html
  printf '\n</body>\n</html>\n'
} > index.html
echo "Built index.html"
