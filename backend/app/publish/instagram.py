"""Instagram Reels via the official Instagram API with Instagram Login (free).

Setup: an Instagram Professional (Creator/Business) account + a Meta developer app.
The access token generated in the app dashboard is pasted into Settings once; it lasts
60 days and is refreshed automatically here, so it effectively never expires while in use.

Publishing = create a REELS container -> upload the file to rupload -> wait -> publish.
"""

import json
import time
from pathlib import Path

import httpx

from app.config import ROOT_DIR, get_settings

GRAPH = "https://graph.instagram.com"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload"
TOKEN = ROOT_DIR / "backend" / "tokens" / "instagram.json"
REFRESH_AFTER = 7 * 24 * 3600


def _version() -> str:
    return get_settings().instagram_graph_version


def _load() -> dict | None:
    if not TOKEN.exists():
        return None
    return json.loads(TOKEN.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(json.dumps(data), encoding="utf-8")


def _check(r: httpx.Response) -> dict:
    try:
        data = r.json()
    except ValueError:
        r.raise_for_status()
        raise
    if r.status_code >= 400 or "error" in data:
        err = data.get("error", {})
        msg = err.get("error_user_msg") or err.get("message") or r.text
        raise RuntimeError(f"Instagram: {msg}"[:500])
    return data


def connect(access_token: str) -> dict:
    """Validate a pasted token and remember the account."""
    token = access_token.strip()
    me = _check(httpx.get(f"{GRAPH}/{_version()}/me",
                          params={"fields": "user_id,username,account_type", "access_token": token}, timeout=30))  # fmt: skip
    data = {"access_token": token, "user_id": str(me["user_id"]), "username": me.get("username"),
            "account_type": me.get("account_type"), "refreshed_at": time.time()}  # fmt: skip
    _save(data)
    return data


def disconnect() -> None:
    TOKEN.unlink(missing_ok=True)


def _token() -> dict:
    data = _load()
    if not data:
        raise RuntimeError("Instagram isn't connected. Open Settings and paste your access token.")
    if time.time() - data.get("refreshed_at", 0) > REFRESH_AFTER:
        try:
            r = _check(httpx.get(f"{GRAPH}/refresh_access_token",
                                 params={"grant_type": "ig_refresh_token", "access_token": data["access_token"]},
                                 timeout=30))  # fmt: skip
            data.update(access_token=r["access_token"], refreshed_at=time.time())
            _save(data)
        except RuntimeError:
            pass  # still valid for a while; try again next time
    return data


def status() -> dict:
    data = _load()
    if not data:
        return {"connected": False, "username": None, "error": None}
    try:
        _token()
        return {"connected": True, "username": data.get("username"), "account_type": data.get("account_type"),
                "error": None}  # fmt: skip
    except RuntimeError as e:
        return {"connected": False, "username": data.get("username"), "error": str(e)}


def publish(path: Path, caption: str, progress=None) -> str:
    """Post a Reel; returns its URL."""
    acct = _token()
    tok, uid, v = acct["access_token"], acct["user_id"], _version()
    size = path.stat().st_size

    with httpx.Client(timeout=120) as client:
        # 1) container (resumable: we upload the bytes ourselves, no public URL needed)
        c = _check(client.post(f"{GRAPH}/{v}/{uid}/media", data={
            "media_type": "REELS", "upload_type": "resumable", "caption": caption[:2200],
            "share_to_feed": "true", "access_token": tok,
        }))  # fmt: skip
        container = c["id"]

        # 2) upload the video file
        with open(path, "rb") as f:
            up = client.post(f"{RUPLOAD}/{v}/{container}", content=f.read(), timeout=600, headers={
                "Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size),
            })  # fmt: skip
        _check(up)
        if progress:
            progress(0.6)

        # 3) wait for Instagram to process it
        for _ in range(90):  # up to ~7.5 min
            st = _check(client.get(f"{GRAPH}/{v}/{container}",
                                   params={"fields": "status_code,status", "access_token": tok}))  # fmt: skip
            code = st.get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Instagram couldn't process the video: {st.get('status') or code}")
            time.sleep(5)
        else:
            raise RuntimeError("Instagram is still processing the video; try again later.")
        if progress:
            progress(0.9)

        # 4) publish
        pub = _check(client.post(f"{GRAPH}/{v}/{uid}/media_publish",
                                 data={"creation_id": container, "access_token": tok}))  # fmt: skip
        media = _check(client.get(f"{GRAPH}/{v}/{pub['id']}", params={"fields": "permalink", "access_token": tok}))
    return media.get("permalink") or f"https://www.instagram.com/{acct.get('username', '')}"
