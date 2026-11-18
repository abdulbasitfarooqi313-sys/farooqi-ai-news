"""💬 ٹیلیگرام «فاروقی جیمنائی» بوٹ ↔ جیمنائی انجینئر (engine ریپو کا Issue)۔
مالک بوٹ میں لکھتا ہے → engine کے «گفتگو» Issue میں `@gemini …` کمنٹ → وہاں جیمنائی کام کرتا ہے اور جواب ٹیلیگرام پر بھیجتا ہے۔
✅ بٹن = Pull Request مرج، ❌ = بند۔ «نئی بات» یا /new = نیا Issue (نئی گفتگو)۔
پبلک ریپو: یہاں کوئی پیغام لاگ میں نہیں چھاپا جاتا؛ state میں چیٹ id کی جگہ صرف hash۔
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import requests

BOT = os.environ["GEMINI_BOT_TOKEN"]
GH = os.environ["GEMINI_CHAT_GH"]
ENGINE = "abdulbasitfarooqi313-sys/farooqi-ai-news-engine"
REPOS = {"engine": (ENGINE, "GEMINI_CHAT_GH"), "nawa": ("nawaefarooqi-bit/nawaefarooqi-agents", "NAWA_TOKEN"),
         "toolscape": ("hellotoolscape/ai-tube-factory", "TS_TOKEN"), "runner": ("abdulbasitfarooqi313-sys/farooqi-ai-news", "GITHUB_TOKEN")}
ST = Path("state/gemini_chat.json")
TG = f"https://api.telegram.org/bot{BOT}"


def h(x) -> str:
    return hashlib.sha256(str(x).encode()).hexdigest()[:16]


def tg(method: str, **kw):
    try:
        return requests.post(f"{TG}/{method}", json=kw, timeout=70).json().get("result")
    except Exception:
        return None


def gh(method: str, path: str, token: str | None = None, **kw):
    r = requests.request(method, f"https://api.github.com/repos/{path}", timeout=60, json=kw or None,
                         headers={"Authorization": f"Bearer {token or GH}", "Accept": "application/vnd.github+json"})
    return r


def new_issue(st: dict) -> int:
    r = gh("POST", f"{ENGINE}/issues", title=f"ٹیلیگرام گفتگو — {time.strftime('%Y-%m-%d %H:%M')}",
           body="یہ Issue ٹیلیگرام کے «فاروقی جیمنائی» بوٹ سے مالک کی گفتگو ہے۔ ہر کمنٹ مالک کا پیغام ہے۔")
    r.raise_for_status()
    st["issue"] = r.json()["number"]
    return st["issue"]


def on_message(st: dict, m: dict) -> None:
    chat = m["chat"]["id"]
    if not st.get("owner"):
        st["owner"] = h(chat)                    # پہلا پیغام بھیجنے والا = مالک
    if h(chat) != st["owner"]:
        return
    text = (m.get("text") or m.get("caption") or "").strip()
    files = []
    if m.get("photo"):
        files.append(m["photo"][-1]["file_id"])
    for k in ("voice", "audio", "document", "video"):
        if m.get(k):
            files.append(m[k]["file_id"])
    if text in ("/start", "السلام علیکم") and not files:
        tg("sendMessage", chat_id=chat, text="وعلیکم السلام 🌿 میں جیمنائی انجینئر ہوں۔ نظام کا جو کام ہو، اردو میں لکھیں (اسکرین شاٹ/آواز بھی بھیج سکتے ہیں)۔ نئی گفتگو کے لیے «نئی بات» لکھیں۔")
        return
    if text in ("/new", "نئی بات"):
        n = new_issue(st)
        tg("sendMessage", chat_id=chat, text=f"🆕 نئی گفتگو شروع (#{n})۔ اب اپنا کام لکھیں۔")
        return
    if not text and not files:
        return
    n = st.get("issue") or new_issue(st)
    if not text and files:
        text = "(تصویر/آواز دیکھیں)"
    body = f"@gemini {text}\n\n<!-- tg chat={chat} msg={m['message_id']} files={','.join(files)} -->"
    r = gh("POST", f"{ENGINE}/issues/{n}/comments", body=body)
    if r.status_code == 404 or r.status_code == 410:          # Issue بند/غائب → نیا
        n = new_issue(st)
        r = gh("POST", f"{ENGINE}/issues/{n}/comments", body=body)
    if r.ok:
        tg("sendMessage", chat_id=chat, reply_to_message_id=m["message_id"],
           text="⏳ جیمنائی کام کر رہا ہے… جواب 2–10 منٹ میں یہیں آئے گا۔")
    else:
        tg("sendMessage", chat_id=chat, text=f"⚠️ پیغام جیمنائی تک نہ پہنچ سکا (GitHub {r.status_code})۔ GEMINI_CHAT_GH ٹوکن کی اجازتیں دیکھیں۔")
        print("comment failed", r.status_code)


def on_callback(st: dict, cb: dict) -> None:
    chat = cb["message"]["chat"]["id"]
    if h(chat) != st.get("owner"):
        return
    parts = (cb.get("data") or "").split("|")
    if len(parts) != 4 or parts[0] != "gm":
        return
    _, act, key, num = parts
    repo, tokname = REPOS.get(key, (None, None))
    if not repo:
        return
    tok = os.environ.get(tokname, "")
    if act == "ok":
        r = gh("PUT", f"{repo}/pulls/{num}/merge", tok, merge_method="squash")
        msg = f"✅ {key}: تبدیلی نظام میں لگ گئی (#{num})" if r.ok else f"⚠️ {key}: مرج نہ ہو سکا ({r.status_code}) — {r.json().get('message', '')[:120]}"
    else:
        r = gh("PATCH", f"{repo}/pulls/{num}", tok, state="closed")
        msg = f"❌ {key}: تبدیلی رد کر دی (#{num})" if r.ok else f"⚠️ {key}: بند نہ ہو سکا ({r.status_code})"
    tg("answerCallbackQuery", callback_query_id=cb["id"])
    tg("sendMessage", chat_id=chat, text=msg)


def main(minutes: float) -> None:
    st = json.loads(ST.read_text()) if ST.exists() else {}
    end = time.time() + minutes * 60
    while time.time() < end:
        ups = tg("getUpdates", offset=st.get("offset", 0), timeout=50, allowed_updates=["message", "callback_query"]) or []
        for u in ups:
            st["offset"] = u["update_id"] + 1
            try:
                if "message" in u:
                    on_message(st, u["message"])
                elif "callback_query" in u:
                    on_callback(st, u["callback_query"])
            except Exception as e:
                print("error:", type(e).__name__)
            ST.parent.mkdir(exist_ok=True)
            ST.write_text(json.dumps(st))
        if not ups:
            time.sleep(1)


if __name__ == "__main__":
    main(float(os.environ.get("LOOP_MIN", "25")))
