"""🎵 ٹک ٹاک (Content Posting API) — تینوں چینل: ainews (@farooqi.ainews)، nawa (@nawaefarooqi1)، toolscape (@toolscape1)۔
    python tools/tiktok.py link|exchange|whoami      (TIKTOK_ACCOUNT=ainews|nawa|toolscape)
    python tools/tiktok.py post <mp4> <caption>
    from tiktok import post; post(path, caption, acct) → {"status", "mode", "publish_id"}   (news/meta.py سے)
ٹوکن: state/tiktok_<acct>.enc (AES، کلید = client secret)۔ پبلک ریپو: کوئی ٹوکن/کوڈ لاگ میں نہیں۔
منظوری (audit) سے پہلے: ویڈیو Inbox ڈرافٹ میں (کیپشن ساتھ نہیں جا سکتا — ٹیلیگرام پر الگ بھیجا جاتا ہے)؛ منظوری کے بعد خود سیدھی پوسٹ + کیپشن۔
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import requests

KEY = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
REDIRECT = "https://abdulbasitfarooqi313-sys.github.io/farooqi-ai-news/callback.html"
SCOPES = "user.info.basic,video.upload,video.publish"
API = "https://open.tiktokapis.com/v2"
STATE = Path(os.environ.get("TIKTOK_STATE_DIR", "state"))


class TikTokError(RuntimeError):
    pass


def _st(acct: str) -> Path:
    return STATE / f"tiktok_{acct}.enc"


def ready(acct: str) -> bool:
    return bool(KEY and SECRET and _st(acct).exists())


def _crypt(data: bytes, dec: bool) -> bytes:
    env = {**os.environ, "TT_PASS": SECRET}
    args = ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-salt", "-pass", "env:TT_PASS"] + (["-d"] if dec else [])
    return subprocess.run(args, input=data, capture_output=True, check=True, env=env).stdout


def save(acct: str, tok: dict) -> None:
    tok["saved_at"] = int(time.time())
    _st(acct).parent.mkdir(exist_ok=True)
    _st(acct).write_bytes(_crypt(json.dumps(tok).encode(), False))


def load(acct: str) -> dict:
    return json.loads(_crypt(_st(acct).read_bytes(), True))


def _token_call(data: dict) -> dict:
    r = requests.post(f"{API}/oauth/token/", data={"client_key": KEY, "client_secret": SECRET, **data},
                      headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=60)
    j = r.json()
    if "access_token" not in j:
        raise TikTokError(f"ٹوکن نہیں ملا: {j.get('error')} — {str(j.get('error_description', ''))[:200]}")
    return j


def access(acct: str) -> str:
    t = load(acct)
    if time.time() - t.get("saved_at", 0) > int(t.get("expires_in", 86400)) - 600:
        t = _token_call({"grant_type": "refresh_token", "refresh_token": t["refresh_token"]})
        save(acct, t)
    return t["access_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}


def post(path: str | Path, caption: str, acct: str, public: bool = True) -> dict:
    tok = access(acct)
    H = _h(tok)
    ci = (requests.post(f"{API}/post/publish/creator_info/query/", headers=H, timeout=60).json().get("data") or {})
    opts = ci.get("privacy_level_options") or []
    priv = "PUBLIC_TO_EVERYONE" if public and "PUBLIC_TO_EVERYONE" in opts else (opts[-1] if opts else "SELF_ONLY")
    size = Path(path).stat().st_size
    src = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}
    body = {"post_info": {"title": caption[:2200], "privacy_level": priv, "disable_duet": False, "disable_comment": False,
                          "disable_stitch": False, "is_aigc": True}, "source_info": src}
    mode = "direct"
    j = requests.post(f"{API}/post/publish/video/init/", headers=H, json=body, timeout=60).json()
    if (j.get("error") or {}).get("code") == "unaudited_client_can_only_post_to_private_accounts":
        mode = "inbox"                                       # منظوری سے پہلے: Inbox ڈرافٹ
        j = requests.post(f"{API}/post/publish/inbox/video/init/", headers=H, json={"source_info": src}, timeout=60).json()
    d = j.get("data") or {}
    if not d.get("upload_url"):
        raise TikTokError(f"init ناکام: {(j.get('error') or {}).get('code')}")
    with open(path, "rb") as f:
        r = requests.put(d["upload_url"], data=f, timeout=900,
                         headers={"Content-Type": "video/mp4", "Content-Length": str(size), "Content-Range": f"bytes 0-{size - 1}/{size}"})
    if r.status_code not in (200, 201):
        raise TikTokError(f"اپلوڈ ناکام: {r.status_code}")
    st = ""
    for _ in range(60):
        time.sleep(10)
        s = requests.post(f"{API}/post/publish/status/fetch/", headers=H, json={"publish_id": d["publish_id"]}, timeout=60).json()
        st = (s.get("data") or {}).get("status", "")
        if st in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            break
        if st == "FAILED":
            raise TikTokError(f"ٹک ٹاک: {(s.get('data') or {}).get('fail_reason')}")
    return {"status": st, "mode": mode, "privacy": priv if mode == "direct" else "inbox", "publish_id": d["publish_id"]}


# ---------------------------------------------------------------- کمانڈ لائن (tiktok.yml)
def _cli() -> None:
    acct = os.environ.get("TIKTOK_ACCOUNT") or "ainews"
    cmd = sys.argv[1]
    if cmd == "link":
        if not KEY.lower().startswith(("sb", "aw")):
            sys.exit(f"⚠️ TIKTOK_CLIENT_KEY درست نہیں لگتی (لمبائی {len(KEY)})")
        q = {"client_key": KEY, "scope": SCOPES, "response_type": "code", "redirect_uri": REDIRECT, "state": f"farooqi-{acct}"}
        print("AUTH_URL_B64 " + base64.b64encode(("https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(q)).encode()).decode())
    elif cmd == "exchange":
        code = os.environ.get("TIKTOK_AUTH_CODE", "").strip()
        if not code:
            sys.exit("TIKTOK_AUTH_CODE خالی ہے")
        save(acct, _token_call({"grant_type": "authorization_code", "code": urllib.parse.unquote(code), "redirect_uri": REDIRECT}))
        print("✅ جڑ گیا:", acct)
    elif cmd == "whoami":
        ci = requests.post(f"{API}/post/publish/creator_info/query/", headers=_h(access(acct)), timeout=60).json().get("data") or {}
        print(f"ACCOUNT[{acct}] = @{ci.get('creator_username')} ({ci.get('creator_nickname')})")
    elif cmd == "post":
        print(post(sys.argv[2], sys.argv[3], acct, public=os.environ.get("TIKTOK_PUBLIC", "1") == "1"))


if __name__ == "__main__":
    try:
        _cli()
    except TikTokError as e:
        sys.exit(str(e))
