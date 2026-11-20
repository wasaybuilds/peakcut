"""YouTube Shorts upload via the official YouTube Data API v3 (free).

Setup: a Google Cloud OAuth "Desktop app" client JSON at backend/tokens/client_secret.json.
Connecting opens a Google sign-in page in the browser on this computer, once.
"""

import json
import logging
import threading
from pathlib import Path

from app.config import ROOT_DIR, get_settings

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",  # channel name for the settings page
]
TOKEN = ROOT_DIR / "backend" / "tokens" / "youtube_token.json"
GAMING_CATEGORY = "20"

_connect_lock = threading.Lock()
_connect_state = {"running": False, "error": None}


def client_secret_path() -> Path:
    p = Path(get_settings().youtube_client_secret_file)
    return p if p.is_absolute() else ROOT_DIR / p


def _creds():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not TOKEN.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return creds if creds.valid else None


def _service():
    from googleapiclient.discovery import build

    creds = _creds()
    if not creds:
        raise RuntimeError("YouTube isn't connected. Open Settings and click Connect YouTube.")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def status() -> dict:
    out = {
        "client_secret": client_secret_path().exists(),
        "connected": False,
        "channel": None,
        "connecting": _connect_state["running"],
        "error": _connect_state["error"],
    }
    if not TOKEN.exists():
        return out
    try:
        items = _service().channels().list(part="snippet", mine=True).execute().get("items", [])
        out["connected"] = True
        out["channel"] = items[0]["snippet"]["title"] if items else "(no channel on this account)"
    except Exception as e:  # expired/revoked token
        out["error"] = f"Reconnect needed: {e}"[:300]
    return out


def start_connect() -> None:
    """Open Google's sign-in page in the browser (runs in a background thread)."""
    if not client_secret_path().exists():
        raise RuntimeError(f"Put your OAuth client JSON at {client_secret_path()} first.")

    def run():
        from google_auth_oauthlib.flow import InstalledAppFlow

        with _connect_lock:
            _connect_state.update(running=True, error=None)
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path()), SCOPES)
                creds = flow.run_local_server(
                    port=0, open_browser=True, access_type="offline", prompt="consent", timeout_seconds=300
                )
                TOKEN.parent.mkdir(parents=True, exist_ok=True)
                TOKEN.write_text(creds.to_json(), encoding="utf-8")
            except Exception as e:
                log.warning("YouTube connect failed: %s", e)
                _connect_state["error"] = str(e)[:300]
            finally:
                _connect_state["running"] = False

    if not _connect_state["running"]:
        threading.Thread(target=run, daemon=True, name="youtube-oauth").start()


def disconnect() -> None:
    TOKEN.unlink(missing_ok=True)


def upload(path: Path, title: str, description: str, tags: list[str], privacy: str = "public", progress=None) -> str:
    """Upload a Short; returns its URL."""
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": [t.lstrip("#") for t in tags][:30],
            "categoryId": GAMING_CATEGORY,
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = _service().videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        st, response = req.next_chunk()
        if st and progress:
            progress(st.progress())
    vid = response["id"]
    log.info("uploaded to YouTube: %s (%s)", vid, json.dumps(response.get("status", {})))
    return f"https://www.youtube.com/shorts/{vid}"
