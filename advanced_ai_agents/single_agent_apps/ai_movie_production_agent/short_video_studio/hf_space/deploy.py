"""Upload Short Video Studio to a private Hugging Face Space.

Run by the GitHub Action `.github/workflows/deploy-short-video-studio.yml`.
Needs the HF_TOKEN secret (a Hugging Face token with "write" access).
GOOGLE_API_KEY is optional: when set, it is saved as a hidden Space secret.
"""

import os
import sys
from pathlib import Path

from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi
from huggingface_hub.errors import HfHubHTTPError

SPACE_NAME = os.getenv("HF_SPACE_NAME", "short-video-studio")
APP_DIR = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"hf_space", "outputs", ".venv", "__pycache__"}
SKIP_FILES = {".env", ".gitignore", "install_mac.sh", "README.md"}

token = os.getenv("HF_TOKEN", "").strip()
if not token:
    print("::warning::HF_TOKEN secret is not set yet, so nothing was deployed.")
    sys.exit(0)

api = HfApi(token=token)
username = api.whoami()["name"]
repo_id = f"{username}/{SPACE_NAME}"

print(f"Deploying to https://huggingface.co/spaces/{repo_id} (private)")
try:
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", private=True, exist_ok=True)
except HfHubHTTPError as error:
    if error.response is not None and error.response.status_code == 402:
        print("::error::Hugging Face needs a PRO subscription to host this app "
              "(https://huggingface.co/pro). Subscribe, then re-run this deploy.")
        sys.exit(1)
    raise
api.update_repo_settings(repo_id, repo_type="space", private=True)  # always keep it private

google_key = os.getenv("GOOGLE_API_KEY", "").strip()
if google_key:
    api.add_space_secret(repo_id, "GOOGLE_API_KEY", google_key)
    print("Saved GOOGLE_API_KEY as a hidden Space secret.")

# Talking characters run on Hugging Face GPUs; this token counts the GPU time on your account.
gpu_token = os.getenv("HF_GPU_TOKEN", "").strip() or token
api.add_space_secret(repo_id, "HF_TOKEN", gpu_token)
print("Saved HF_TOKEN (for talking characters) as a hidden Space secret.")

# Stamp this deploy with a version the app shows in Settings (and we check below).
VERSION = os.getenv("GITHUB_SHA", "local")[:7]
(APP_DIR / "version.txt").write_text(VERSION, encoding="utf-8")

# Upload all app files + the Space README, and remove files that no longer exist.
local_files = {}
for path in APP_DIR.rglob("*"):
    relative = path.relative_to(APP_DIR)
    if path.is_file() and not (set(relative.parts) & SKIP_DIRS) and str(relative) not in SKIP_FILES:
        local_files[relative.as_posix()] = path
local_files["README.md"] = APP_DIR / "hf_space" / "README.md"

remote_files = set(api.list_repo_files(repo_id, repo_type="space"))
operations = [CommitOperationAdd(path_in_repo=name, path_or_fileobj=str(path))
              for name, path in sorted(local_files.items())]
operations += [CommitOperationDelete(path_in_repo=name)
               for name in sorted(remote_files - set(local_files) - {".gitattributes"})]

sha = os.getenv("GITHUB_SHA", "local")[:7]
info = api.create_commit(repo_id, operations, repo_type="space", commit_message=f"Deploy from GitHub {sha}")
new_revision = getattr(info, "oid", None)  # None when nothing changed
print("Files uploaded. Waiting for Hugging Face to build and start the app…")

# Follow the build so problems show up here in GitHub (up to 30 minutes).
import json  # noqa: E402
import time  # noqa: E402
import urllib.request  # noqa: E402


def print_logs(kind: str, seconds: int = 20) -> None:
    """Print the last lines of the Space's build or run log."""
    url = f"https://huggingface.co/api/spaces/{repo_id}/logs/{kind}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    lines, start = [], time.time()
    try:
        with urllib.request.urlopen(request, timeout=seconds) as response:
            for raw in response:
                if raw.startswith(b"data:"):
                    try:
                        lines.append(json.loads(raw[5:]).get("data", "").rstrip())
                    except ValueError:
                        pass
                if time.time() - start > seconds:
                    break
    except Exception as error:  # noqa: BLE001 - the log stream ends with a timeout
        lines.append(f"(log stream ended: {type(error).__name__})")
    print(f"----- last {kind} log lines -----")
    print("\n".join(lines[-60:]))


first = api.get_space_runtime(repo_id)
print(f"  New revision: {str(new_revision)[:7]}; Space runtime info: "
      f"{ {k: v for k, v in (first.raw or {}).items() if k in ('stage', 'sha', 'errorMessage')} }")
host = api.space_info(repo_id).host  # e.g. https://user-space.hf.space


def live_version() -> str:
    """Ask the running app which version it is (proves the new code is really live)."""
    try:
        request = urllib.request.Request(f"{host}/api/config", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read()).get("version", "")
    except Exception as error:  # noqa: BLE001
        return f"unreachable ({type(error).__name__})"


last_stage, last_live = None, None
for _ in range(180):
    runtime = api.get_space_runtime(repo_id)
    stage = str(getattr(runtime.stage, "value", runtime.stage))
    revision = (runtime.raw or {}).get("sha")
    if stage != last_stage:
        print(f"  Space status: {stage} (revision {str(revision)[:7]})")
        last_stage = stage
    up_to_date = new_revision is None or revision is None or revision == new_revision
    if stage == "RUNNING" and up_to_date:
        live = live_version()
        if live == VERSION:
            print(f"Done! The live app reports version {VERSION}. Open https://huggingface.co/spaces/{repo_id}")
            sys.exit(0)
        if live != last_live:
            print(f"  Live app answers version: {live} (waiting for {VERSION})")
            last_live = live
    if "ERROR" in stage:
        print(f"::error::The Space failed ({stage}): {(runtime.raw or {}).get('errorMessage', '')}")
        print_logs("build")
        print_logs("run")
        sys.exit(1)
    time.sleep(10)
print(f"::warning::Still not running the new version after 30 minutes. Check https://huggingface.co/spaces/{repo_id}")
print_logs("build")
