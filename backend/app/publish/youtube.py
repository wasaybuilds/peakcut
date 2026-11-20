"""YouTube Shorts upload via the official YouTube Data API v3 (free).

Setup: a Google Cloud OAuth "Desktop app" client JSON at backend/tokens/client_secret.json.
Connecting opens a Google sign-in page in the browser on this computer, once.
"""

import json
import logging
import threading
import time
import webbrowser
import wsgiref.simple_server
import wsgiref.util
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.config import ROOT_DIR, get_settings

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",  # channel name for the settings page
]
TOKEN = ROOT_DIR / "backend" / "tokens" / "youtube_token.json"
GAMING_CATEGORY = "20"

CONNECT_TIMEOUT = 600  # seconds to finish signing in before the attempt is dropped

_connect_lock = threading.Lock()
_connect_state = {"running": False, "error": None, "auth_url": None}


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


class _QuietHandler(wsgiref.simple_server.WSGIRequestHandler):
    timeout = 10  # an idle connection (browser preconnect) can't hold the listener forever

    def log_message(self, *args):
        pass


def _wait_for_redirect(server, deadline: float) -> str:
    """Serve the local redirect until Google sends back a code or an error."""
    result: dict[str, str] = {}

    def app(environ, start_response):
        query = parse_qs(environ.get("QUERY_STRING", ""))
        if "code" in query or "error" in query:
            result["uri"] = wsgiref.util.request_uri(environ)
            body = b"PeakCut is connected to YouTube. You can close this tab."
            if "error" in query:
                body = b"Sign-in was cancelled. Go back to PeakCut and click Connect YouTube to try again."
        else:
            body = b"Waiting for Google sign-in."
        start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8")])
        return [body]

    server.set_app(app)
    server.timeout = 1
    while "uri" not in result:
        if time.time() > deadline:
            raise RuntimeError("Sign-in took too long. Click Connect YouTube to try again.")
        server.handle_request()
    return result["uri"]


def start_connect() -> None:
    """Open Google's sign-in page in the browser; the redirect is caught in a background thread.

    Clicking again while a sign-in is waiting reopens the same page, so a blocked or closed tab
    (for example "Access blocked" before you were added as a test user) can simply be retried.
    """
    if not client_secret_path().exists():
        raise RuntimeError(f"Put your OAuth client JSON at {client_secret_path()} first.")
    if _connect_state["running"]:
        if _connect_state["auth_url"]:
            webbrowser.open(_connect_state["auth_url"], new=1)
        return

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path()), SCOPES)
    server = wsgiref.simple_server.make_server("localhost", 0, lambda e, r: [], handler_class=_QuietHandler)
    flow.redirect_uri = f"http://localhost:{server.server_port}/"
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    _connect_state.update(running=True, error=None, auth_url=auth_url)

    def run():
        with _connect_lock:
            try:
                uri = _wait_for_redirect(server, time.time() + CONNECT_TIMEOUT)
                error = parse_qs(urlparse(uri).query).get("error")
                if error:
                    raise RuntimeError(f"Google sign-in was not completed ({error[0]}).")
                flow.fetch_token(authorization_response=uri.replace("http://", "https://", 1))  # oauthlib wants https
                TOKEN.parent.mkdir(parents=True, exist_ok=True)
                TOKEN.write_text(flow.credentials.to_json(), encoding="utf-8")
            except Exception as e:
                log.warning("YouTube connect failed: %s", e)
                _connect_state["error"] = str(e)[:300]
            finally:
                server.server_close()
                _connect_state.update(running=False, auth_url=None)

    threading.Thread(target=run, daemon=True, name="youtube-oauth").start()
    webbrowser.open(auth_url, new=1)


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
