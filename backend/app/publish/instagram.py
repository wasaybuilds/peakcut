"""Instagram Reels via the official Instagram API (free).

Setup: an Instagram Professional (Creator/Business) account + a Meta developer app. The token
generated in the app dashboard is pasted into Settings once. Two kinds work:

- IGAA... from "API setup with Instagram login" (older apps): talks to graph.instagram.com,
  lasts 60 days and is refreshed automatically here.
- EAA... from "API setup with Unified login" (newer apps, a system-user token that never
  expires): talks to graph.facebook.com and needs the Instagram account's ID, which is looked
  up from the token or pasted alongside it.

Publishing is the same for both: create a REELS container -> upload the file to rupload ->
wait -> publish.
"""

import json
import time
from pathlib import Path

import httpx

from app.config import ROOT_DIR, get_settings

IG_GRAPH = "https://graph.instagram.com"
FB_GRAPH = "https://graph.facebook.com"
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


def _graph(data: dict) -> str:
    return FB_GRAPH if data.get("api") == "facebook" else IG_GRAPH


def _facebook_account_ids(token: str) -> list[str]:
    """Instagram account IDs a Facebook-style (EAA) token can post to."""
    v, ids = _version(), []
    try:  # the token's own grants list the Instagram accounts it was issued for
        dbg = _check(httpx.get(f"{FB_GRAPH}/{v}/debug_token",
                               params={"input_token": token, "access_token": token}, timeout=30))  # fmt: skip
        info = dbg.get("data")
        for scope in (info if isinstance(info, dict) else {}).get("granular_scopes") or []:
            if scope.get("scope") in ("instagram_content_publish", "instagram_basic"):
                ids += [str(t) for t in scope.get("target_ids") or []]
    except RuntimeError:
        pass
    if not ids:  # Instagram accounts linked to Facebook Pages
        try:
            pages = _check(httpx.get(f"{FB_GRAPH}/{v}/me/accounts",
                                     params={"fields": "instagram_business_account", "access_token": token},
                                     timeout=30))  # fmt: skip
            ids = [str(p["instagram_business_account"]["id"]) for p in pages.get("data", [])
                   if p.get("instagram_business_account")]  # fmt: skip
        except RuntimeError:
            pass
    return list(dict.fromkeys(ids))


def connect(access_token: str, account_id: str | None = None) -> dict:
    """Validate a pasted token and remember the account."""
    token, v = access_token.strip(), _version()
    if token.startswith("EAA"):
        ids = [account_id.strip()] if account_id and account_id.strip() else _facebook_account_ids(token)
        if not ids:
            raise RuntimeError("Instagram: couldn't find an Instagram account for this token. Paste the account "
                               "ID too (the number under your username in the Meta app dashboard).")  # fmt: skip
        me = _check(httpx.get(f"{FB_GRAPH}/{v}/{ids[0]}",
                              params={"fields": "id,username", "access_token": token}, timeout=30))  # fmt: skip
        data = {"api": "facebook", "access_token": token, "user_id": str(me["id"]), "username": me.get("username"),
                "account_type": "BUSINESS", "refreshed_at": time.time()}  # fmt: skip
    else:
        me = _check(httpx.get(f"{IG_GRAPH}/{v}/me",
                              params={"fields": "user_id,username,account_type", "access_token": token},
                              timeout=30))  # fmt: skip
        data = {"api": "instagram", "access_token": token, "user_id": str(me["user_id"]),
                "username": me.get("username"), "account_type": me.get("account_type"), "refreshed_at": time.time()}  # fmt: skip
    _save(data)
    return data


def disconnect() -> None:
    TOKEN.unlink(missing_ok=True)


def _token() -> dict:
    data = _load()
    if not data:
        raise RuntimeError("Instagram isn't connected. Open Settings and paste your access token.")
    # Instagram-login tokens last 60 days and can refresh themselves; system-user tokens never expire.
    if data.get("api") != "facebook" and time.time() - data.get("refreshed_at", 0) > REFRESH_AFTER:
        try:
            r = _check(httpx.get(f"{IG_GRAPH}/refresh_access_token",
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


def publish(path: Path, caption: str, cover_at: float | None = None, progress=None) -> str:
    """Post a Reel; returns its URL.

    `cover_at` picks the cover frame (seconds into the clip). The API only takes a custom cover
    *image* from a public URL, which a local app doesn't have, so the frame is the cover; the
    text cover image is for posting from the Instagram app.
    """
    acct = _token()
    tok, uid, v, graph = acct["access_token"], acct["user_id"], _version(), _graph(acct)
    size = path.stat().st_size

    with httpx.Client(timeout=120) as client:
        # 1) container (resumable: we upload the bytes ourselves, no public URL needed)
        params = {
            "media_type": "REELS", "upload_type": "resumable", "caption": caption[:2200],
            "share_to_feed": "true", "access_token": tok,
        }  # fmt: skip
        if cover_at is not None:
            params["thumb_offset"] = str(int(cover_at * 1000))  # milliseconds
        c = _check(client.post(f"{graph}/{v}/{uid}/media", data=params))
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
            st = _check(client.get(f"{graph}/{v}/{container}",
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
        pub = _check(client.post(f"{graph}/{v}/{uid}/media_publish",
                                 data={"creation_id": container, "access_token": tok}))  # fmt: skip
        media = _check(client.get(f"{graph}/{v}/{pub['id']}", params={"fields": "permalink", "access_token": tok}))
    return media.get("permalink") or f"https://www.instagram.com/{acct.get('username', '')}"
