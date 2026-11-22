"""TikTok via the official Content Posting API (free), in "upload to inbox" mode.

PeakCut uploads the clip to the creator's TikTok inbox; TikTok sends a notification in the app,
where the creator adds the caption and posts it (publicly if they like). This mode isn't limited
like Direct Post, which only allows private posts until TikTok audits the app, and TikTok doesn't
approve Direct Post for personal upload tools anyway. Limit: 5 pending inbox uploads per 24 hours.

Setup: a TikTok developer app with Login Kit (Desktop) and the Content Posting API, scopes
user.info.basic and video.upload, and the redirect URI http://127.0.0.1:<port>/callback/. The
client key and secret go in .env (TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET), never in the repo.
"""

import hashlib
import json
import logging
import secrets
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from app.config import ROOT_DIR, get_settings
from app.publish import oauth_local

log = logging.getLogger(__name__)

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
API = "https://open.tiktokapis.com/v2"
SCOPES = "user.info.basic,video.upload"
TOKEN = ROOT_DIR / "backend" / "tokens" / "tiktok.json"
CONNECT_TIMEOUT = 600
SINGLE_CHUNK_MAX = 60_000_000  # TikTok takes files up to 64 MB in one piece; stay under it
CHUNK = 10_000_000  # 5 to 64 MB per chunk; the last one absorbs the remainder

_connect_lock = threading.Lock()
_connect_state = {"running": False, "error": None, "auth_url": None}


def redirect_uri() -> str:
    return f"http://127.0.0.1:{get_settings().tiktok_redirect_port}/callback/"  # desktop: localhost or 127.0.0.1; the form only takes the IP


def configured() -> bool:
    s = get_settings()
    return bool(s.tiktok_client_key and s.tiktok_client_secret)


def _load() -> dict | None:
    if not TOKEN.exists():
        return None
    return json.loads(TOKEN.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(json.dumps(data), encoding="utf-8")


def _check(r: httpx.Response) -> dict:
    """TikTok answers {"data": ..., "error": {"code": "ok"}} on success; OAuth errors are flat."""
    try:
        data = r.json()
    except ValueError:
        r.raise_for_status()
        raise
    err = data.get("error")
    if isinstance(err, dict) and err.get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok: {err.get('message') or err.get('code')}"[:500])
    if isinstance(err, str) and err:  # token endpoint style
        raise RuntimeError(f"TikTok: {data.get('error_description') or err}"[:500])
    if r.status_code >= 400:
        raise RuntimeError(f"TikTok returned {r.status_code}: {r.text[:300]}")
    return data


def _store_tokens(tok: dict, extra: dict | None = None) -> dict:
    now = time.time()
    data = {
        **(extra or {}),
        "access_token": tok["access_token"],
        "refresh_token": tok["refresh_token"],
        "expires_at": now + int(tok.get("expires_in", 7200)),
        "refresh_expires_at": now + int(tok.get("refresh_expires_in", 180 * 86400)),
        "open_id": tok.get("open_id") or (extra or {}).get("open_id"),
        "scope": tok.get("scope", ""),
    }
    _save(data)
    return data


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]  # 43-128 chars of A-Z a-z 0-9 - _
    challenge = hashlib.sha256(verifier.encode()).hexdigest()  # TikTok documents hex, not base64url
    return verifier, challenge


def auth_url(state: str, challenge: str) -> str:
    return AUTH_URL + "?" + urlencode({
        "client_key": get_settings().tiktok_client_key, "scope": SCOPES, "response_type": "code",
        "redirect_uri": redirect_uri(), "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
    })  # fmt: skip


def _display_name(access_token: str) -> str | None:
    try:
        info = _check(httpx.get(f"{API}/user/info/", params={"fields": "open_id,display_name"},
                                headers={"Authorization": f"Bearer {access_token}"}, timeout=30))  # fmt: skip
        return (info.get("data") or {}).get("user", {}).get("display_name")
    except (RuntimeError, httpx.HTTPError) as e:
        log.warning("TikTok user info failed: %s", e)
        return None


def exchange(uri: str, state: str, verifier: str) -> dict:
    """Finish sign-in from the redirect URI TikTok sent the browser to."""
    q = parse_qs(urlparse(uri).query)
    if q.get("error"):
        raise RuntimeError(f"TikTok sign-in was not completed ({(q.get('error_description') or q['error'])[0]}).")
    if q.get("state", [""])[0] != state:
        raise RuntimeError("TikTok sign-in failed a security check (state mismatch). Try again.")
    s = get_settings()
    tok = _check(httpx.post(f"{API}/oauth/token/", data={
        "client_key": s.tiktok_client_key, "client_secret": s.tiktok_client_secret, "code": q["code"][0],
        "grant_type": "authorization_code", "redirect_uri": redirect_uri(), "code_verifier": verifier,
    }, timeout=30))  # fmt: skip
    if "video.upload" not in tok.get("scope", ""):
        raise RuntimeError("TikTok didn't grant video.upload. Add it to the app's scopes and connect again.")
    return _store_tokens(tok, {"display_name": _display_name(tok["access_token"])})


def start_connect() -> None:
    """Open TikTok's sign-in page; the redirect is caught on localhost in a background thread."""
    if not configured():
        raise RuntimeError("Add TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET to .env and restart PeakCut first.")
    if _connect_state["running"]:
        if _connect_state["auth_url"]:
            webbrowser.open(_connect_state["auth_url"], new=1)
        return
    try:
        server = oauth_local.make_server(get_settings().tiktok_redirect_port, host="127.0.0.1")
    except OSError as e:
        raise RuntimeError(f"Port {get_settings().tiktok_redirect_port} is busy, so TikTok can't redirect back: {e}") from e
    state, (verifier, challenge) = secrets.token_urlsafe(24), _pkce()
    url = auth_url(state, challenge)
    _connect_state.update(running=True, error=None, auth_url=url)

    def run():
        with _connect_lock:
            try:
                uri = oauth_local.wait_for_redirect(server, time.time() + CONNECT_TIMEOUT, "TikTok")
                exchange(uri, state, verifier)
            except Exception as e:
                log.warning("TikTok connect failed: %s", e)
                _connect_state["error"] = str(e)[:300]
            finally:
                server.server_close()
                _connect_state.update(running=False, auth_url=None)

    threading.Thread(target=run, daemon=True, name="tiktok-oauth").start()
    webbrowser.open(url, new=1)


def disconnect() -> None:
    TOKEN.unlink(missing_ok=True)


def _token() -> dict:
    data = _load()
    if not data:
        raise RuntimeError("TikTok isn't connected. Open Settings and click Connect TikTok.")
    if time.time() < data["expires_at"] - 300:
        return data
    if time.time() > data.get("refresh_expires_at", 0):
        raise RuntimeError("TikTok sign-in expired. Open Settings and connect TikTok again.")
    s = get_settings()
    tok = _check(httpx.post(f"{API}/oauth/token/", data={
        "client_key": s.tiktok_client_key, "client_secret": s.tiktok_client_secret,
        "grant_type": "refresh_token", "refresh_token": data["refresh_token"],
    }, timeout=30))  # fmt: skip
    return _store_tokens(tok, {"display_name": data.get("display_name"), "open_id": data.get("open_id")})  # rotated


def status() -> dict:
    data = _load()
    out = {"configured": configured(), "connected": False, "name": None,
           "connecting": _connect_state["running"], "error": _connect_state["error"],
           "redirect_uri": redirect_uri()}  # fmt: skip
    if not data:
        return out
    out["name"] = data.get("display_name")
    if time.time() > data.get("refresh_expires_at", 0):
        out["error"] = "Reconnect needed: the TikTok sign-in expired."
    else:
        out["connected"] = True
    return out


def chunks(size: int) -> tuple[int, int]:
    """(chunk_size, total_chunk_count) per TikTok's rules: whole file when small, else 10 MB pieces."""
    if size <= SINGLE_CHUNK_MAX:
        return size, 1
    return CHUNK, size // CHUNK


def send_to_inbox(path: Path, progress=None) -> str:
    """Upload a clip to the TikTok inbox; returns the publish_id once TikTok has delivered it."""
    tok = _token()["access_token"]
    auth = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}
    size = path.stat().st_size
    chunk_size, count = chunks(size)
    with httpx.Client(timeout=120) as client:
        init = _check(client.post(f"{API}/post/publish/inbox/video/init/", headers=auth, json={
            "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk_size,
                            "total_chunk_count": count},
        }))["data"]  # fmt: skip
        publish_id, upload_url = init["publish_id"], init["upload_url"]

        with open(path, "rb") as f:
            for i in range(count):
                first = i * chunk_size
                last = size - 1 if i == count - 1 else first + chunk_size - 1  # last chunk takes the rest
                body = f.read(last - first + 1)
                r = client.put(upload_url, content=body, timeout=600, headers={
                    "Content-Type": "video/mp4", "Content-Length": str(len(body)),
                    "Content-Range": f"bytes {first}-{last}/{size}",
                })  # fmt: skip
                if r.status_code not in (200, 201, 206):
                    raise RuntimeError(f"TikTok upload failed ({r.status_code}): {r.text[:300]}")
                if progress:
                    progress(0.1 + 0.5 * (i + 1) / count)

        for _ in range(60):  # up to ~5 min
            st = _check(client.post(f"{API}/post/publish/status/fetch/", headers=auth,
                                    json={"publish_id": publish_id}))["data"]  # fmt: skip
            code = st.get("status")
            if code in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
                return publish_id
            if code == "FAILED":
                raise RuntimeError(f"TikTok couldn't take the video: {st.get('fail_reason') or 'unknown reason'}")
            time.sleep(5)
    raise RuntimeError("TikTok is still processing the upload. Check your TikTok inbox in a few minutes.")
