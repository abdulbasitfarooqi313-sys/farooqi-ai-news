"""🎵 ٹک ٹاک (Content Posting API) — farooqi.ainews وغیرہ پر شارٹس بھیجنا۔
    python tools/tiktok.py link                 → اجازت کا لنک (لاگ میں؛ اس میں کوئی راز نہیں)
    python tools/tiktok.py exchange             → TIKTOK_AUTH_CODE سے ٹوکن، state/tiktok_<acct>.enc میں خفیہ (AES، کلید = client secret)
    python tools/tiktok.py post <mp4> <title>   → ویڈیو بھیجنا (منظوری سے پہلے صرف SELF_ONLY)
پبلک ریپو: کوئی ٹوکن/کوڈ لاگ میں نہیں چھپتا۔
"""
from __future__ import annotations

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
ACCT = os.environ.get("TIKTOK_ACCOUNT", "ainews")
REDIRECT = "https://abdulbasitfarooqi313-sys.github.io/farooqi-ai-news/callback.html"
SCOPES = "user.info.basic,video.upload,video.publish"
API = "https://open.tiktokapis.com/v2"
ST = Path(f"state/tiktok_{ACCT}.enc")


def _crypt(data: bytes, dec: bool) -> bytes:
    os.environ["TT_PASS"] = SECRET
    args = ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-salt", "-pass", "env:TT_PASS"] + (["-d"] if dec else [])
    return subprocess.run(args, input=data, capture_output=True, check=True).stdout


def save(tok: dict) -> None:
    tok["saved_at"] = int(time.time())
    ST.parent.mkdir(exist_ok=True)
    ST.write_bytes(_crypt(json.dumps(tok).encode(), False))


def load() -> dict:
    return json.loads(_crypt(ST.read_bytes(), True))


def _token_call(data: dict) -> dict:
    r = requests.post(f"{API}/oauth/token/", data={"client_key": KEY, "client_secret": SECRET, **data},
                      headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=60)
    j = r.json()
    if "access_token" not in j:
        sys.exit(f"ٹوکن نہیں ملا: {j.get('error')} — {j.get('error_description', '')[:200]}")
    return j


def access() -> str:
    t = load()
    if time.time() - t.get("saved_at", 0) > int(t.get("expires_in", 86400)) - 600:
        t = _token_call({"grant_type": "refresh_token", "refresh_token": t["refresh_token"]})
        save(t)
    return t["access_token"]


def link() -> None:
    if not KEY.lower().startswith(("sb", "aw")):         # غلطی سے secret ڈالا گیا ہو تو لاگ میں نہ جائے
        sys.exit(f"⚠️ TIKTOK_CLIENT_KEY درست نہیں لگتی (لمبائی {len(KEY)}) — sbaw… والی Client key ڈالیں")
    q = {"client_key": KEY, "scope": SCOPES, "response_type": "code", "redirect_uri": REDIRECT, "state": f"farooqi-{ACCT}"}
    import base64          # client_key عوامی ہے (اجازت کے لنک میں ہوتا ہے)؛ GitHub اسے *** کر دیتا ہے، اس لیے base64
    print("AUTH_URL_B64 " + base64.b64encode(("https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(q)).encode()).decode())


def exchange() -> None:
    code = os.environ.get("TIKTOK_AUTH_CODE", "").strip()
    if not code:
        sys.exit("TIKTOK_AUTH_CODE خالی ہے")
    t = _token_call({"grant_type": "authorization_code", "code": urllib.parse.unquote(code), "redirect_uri": REDIRECT})
    save(t)
    u = requests.get(f"{API}/user/info/", params={"fields": "display_name,username"},
                     headers={"Authorization": f"Bearer {t['access_token']}"}, timeout=60).json()
    print("✅ جڑ گیا:", (u.get("data", {}).get("user") or {}).get("display_name", "?"), "| scopes:", t.get("scope"))


def post(path: str, title: str) -> None:
    tok = access()
    H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}
    ci = requests.post(f"{API}/post/publish/creator_info/query/", headers=H, timeout=60).json()
    opts = (ci.get("data") or {}).get("privacy_level_options") or []
    print("privacy options:", opts, "| creator:", (ci.get("data") or {}).get("creator_nickname"))
    priv = "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in opts and os.environ.get("TIKTOK_PUBLIC") == "1" else "SELF_ONLY"
    size = Path(path).stat().st_size
    body = {"post_info": {"title": title[:2200], "privacy_level": priv, "disable_duet": False, "disable_comment": False,
                          "disable_stitch": False, "is_aigc": True},
            "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}}
    j = requests.post(f"{API}/post/publish/video/init/", headers=H, json=body, timeout=60).json()
    if (j.get("error") or {}).get("code") == "unaudited_client_can_only_post_to_private_accounts":
        # منظوری سے پہلے: ویڈیو ٹک ٹاک کے Inbox میں ڈرافٹ کے طور پر (مالک ایپ میں خود پوسٹ کرے)
        print("→ ابھی منظوری نہیں: Inbox ڈرافٹ (video.upload)")
        j = requests.post(f"{API}/post/publish/inbox/video/init/", headers=H, json={"source_info": body["source_info"]}, timeout=60).json()
        priv = "INBOX_DRAFT"
    d = j.get("data") or {}
    if not d.get("upload_url"):
        sys.exit(f"init ناکام: {j.get('error')}")
    with open(path, "rb") as f:
        r = requests.put(d["upload_url"], data=f, timeout=600,
                         headers={"Content-Type": "video/mp4", "Content-Length": str(size), "Content-Range": f"bytes 0-{size - 1}/{size}"})
    print("upload:", r.status_code)
    for _ in range(40):
        time.sleep(10)
        s = requests.post(f"{API}/post/publish/status/fetch/", headers=H, json={"publish_id": d["publish_id"]}, timeout=60).json()
        st = (s.get("data") or {}).get("status")
        print("status:", st, (s.get("data") or {}).get("fail_reason") or "")
        if st in ("PUBLISH_COMPLETE", "FAILED", "SEND_TO_USER_INBOX"):
            break
    print("privacy:", priv)


def whoami() -> None:
    ci = requests.post(f"{API}/post/publish/creator_info/query/", headers={"Authorization": f"Bearer {access()}",
                       "Content-Type": "application/json; charset=UTF-8"}, timeout=60).json().get("data") or {}
    print(f"ACCOUNT[{ACCT}] = @{ci.get('creator_username')} ({ci.get('creator_nickname')})")


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"link": link, "exchange": exchange, "whoami": whoami}.get(cmd, lambda: post(sys.argv[2], sys.argv[3]))()
