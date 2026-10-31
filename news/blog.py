"""📝 بلاگ پر خودکار اشاعت — farooqiainews.blogspot.com

ہر ویڈیو (بلیٹن، فلیش، پوڈکاسٹ، لفظ) بنتے ہی اس کی مکمل تحریری پوسٹ تیار ہو کر `state/blog_queue/<کلید>.json` میں رکھی جاتی ہے؛
ٹیلیگرام پر ✅ دبتے ہی Blogger پر اسی وقت کے لیے شیڈول ہو جاتی ہے جب ویڈیو یوٹیوب پر پبلک ہو گی۔ ❌ پر کچھ شائع نہیں۔
لیبل بلاگ کے مینو سے ملتے ہیں (بلیٹن، اے آئی فلیش، اے آئی بیٹھک، آج کا اے آئی لفظ، کمپنیاں، ٹولز، پاکستان)۔

چابیاں: YOUTUBE_CLIENT_ID/SECRET (وہی کلائنٹ ai-news-web) + BLOGGER_REFRESH_TOKEN (بلاگ کے مالک اکاؤنٹ — نوائے فاروقی — سے، اسکوپ blogger)۔
python -m news.blog check
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys

import requests

from .base import ROOT, read_json, write_json

API = "https://www.googleapis.com/blogger/v3"
BLOG_URL = os.environ.get("BLOG_URL", "https://farooqiainews.blogspot.com/")
QUEUE = ROOT / "state" / "blog_queue"
STATE = ROOT / "state" / "blog.json"
TZ = dt.timezone(dt.timedelta(hours=3))
KIND_LABEL = {"bulletin": "بلیٹن", "flash": "اے آئی فلیش", "podcast": "اے آئی بیٹھک", "word": "آج کا اے آئی لفظ"}
E = html.escape


def enabled() -> bool:
    return bool(os.environ.get("BLOGGER_REFRESH_TOKEN", "").strip())


def _token() -> str:
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": os.environ["YOUTUBE_CLIENT_ID"].strip(), "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"].strip(),
        "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"].strip(), "grant_type": "refresh_token"})
    if not r.ok:
        raise RuntimeError(f"بلاگ کی چابی: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


def _blog_id(tok: str) -> str:
    st = read_json(STATE) if STATE.exists() else {}
    if st.get("blog_id"):
        return st["blog_id"]
    r = requests.get(f"{API}/blogs/byurl", params={"url": BLOG_URL}, headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"بلاگ نہیں ملا: {r.status_code} {r.text[:200]}")
    st["blog_id"] = r.json()["id"]
    write_json(STATE, st)
    return st["blog_id"]


def _labels(kind: str, sd: dict) -> list[str]:
    seo_l = ((sd.get("seo") or {}).get("blog") or {}).get("labels") or []
    return list(dict.fromkeys([KIND_LABEL.get(kind, "خبریں")] + [l for l in seo_l if l and len(l) < 30]))[:6]


def _video_block(title: str) -> str:
    # یوٹیوب آئی ڈی ✅ کے وقت معلوم ہوتی ہے — یہاں نشان، publish() میں بدلا جاتا ہے
    return ('<div style="text-align:center"><img alt="' + E(title) + '" src="https://i.ytimg.com/vi/__YT__/maxresdefault.jpg" '
            'style="width:100%;border-radius:14px"/></div>\n<h2>ویڈیو دیکھیں</h2>\n'
            '<iframe src="https://www.youtube.com/embed/__YT__" title="' + E(title) + '" allowfullscreen="" loading="lazy"></iframe>')


def _src(name: str, link: str) -> str:
    return f'<p class="src">ماخذ: <a href="{E(link)}" rel="nofollow noopener" target="_blank">{E(name or "لنک")}</a></p>' if link else ""


def prepare(kind: str, key: str, d: dict, sd: dict) -> None:
    """ویڈیو بنتے ہی پوسٹ کا مسودہ — صرف ریکارڈ، ابھی کچھ شائع نہیں"""
    seo = sd.get("seo") or {}
    b = seo.get("blog") or {}
    title = b.get("title") or sd.get("youtube_title", "").replace("#shorts", "").strip()
    parts = []
    if b.get("meta_description"):
        parts.append(f"<p><b>{E(b['meta_description'])}</b></p>")
    parts.append(_video_block(title))
    if kind == "bulletin":
        parts.append("<h2>آج کی اہم خبریں</h2><ol>" + "".join(f"<li>{E(s['headline'])}</li>" for s in d.get("stories", [])) + "</ol>")
        for s in d.get("stories", []):
            parts.append(f"<h2>{E(s['headline'])}</h2><p>{E(s.get('lead', ''))}</p><p>{E(s.get('vo', ''))}</p>"
                         + ("<ul>" + "".join(f"<li>{E(p)}</li>" for p in s.get("points", [])) + "</ul>" if s.get("points") else "")
                         + (f"<blockquote>{E(s['comment'])}</blockquote>" if s.get("comment") else "")
                         + _src(s.get("source", ""), s.get("link", "")))
    elif kind == "flash":
        parts.append("<h2>آج کی اے آئی سرخیاں</h2><ol>" + "".join(
            f"<li>{E(it['h'])}" + (f" <small>({E(it.get('country', ''))})</small>" if it.get("country") else "")
            + (f' — <a href="{E(it["link"])}" rel="nofollow noopener" target="_blank">{E(it.get("source_ur") or it.get("source") or "ماخذ")}</a>' if it.get("link") else "")
            + "</li>" for it in d.get("items", [])) + "</ol>")
    elif kind == "podcast":
        if d.get("summary"):
            parts.append(f"<p>{E(d['summary'])}</p>")
        parts.append("<h2>گفتگو کا مکمل متن</h2>" + "".join(
            f"<p><b>{'سارہ' if l['s'] == 'Sarah' else 'احمد'}:</b> {E(l['t'])}</p>" for l in d.get("lines", [])))
        parts.append("".join(_src(x.get("source", ""), x.get("link", "")) for x in d.get("sources", [])))
        parts.append("<p><small>یہ گفتگو معلوماتی ہے، سرمایہ کاری کا مشورہ نہیں۔</small></p>")
    elif kind == "word":
        parts.append(f"<h2>{E(d['term'])} کیا ہے؟</h2><p><b>مطلب:</b> {E(d['meaning'])}</p><p><b>مثال:</b> {E(d['example'])}</p><p>{E(d['script'])}</p>")
    parts.append('<p>مزید ویڈیوز کے لیے <a href="https://www.youtube.com/@farooqiainews?sub_confirmation=1" target="_blank" rel="noopener">'
                 'فاروقی اے آئی نیوز کو یوٹیوب پر سبسکرائب کریں</a>۔</p>')
    QUEUE.mkdir(parents=True, exist_ok=True)
    write_json(QUEUE / f"{key}.json", {"kind": kind, "title": title, "labels": _labels(kind, sd), "html": "\n".join(parts)})


def publish(key: str, yt_id: str, when: dt.datetime) -> str:
    """✅ پر: مسودہ Blogger پر — ویڈیو کے پبلک ہونے کے وقت کے لیے شیڈول (وقت گزر چکا ہو تو ابھی)"""
    q = QUEUE / f"{key}.json"
    if not q.exists():
        return ""
    st = read_json(STATE) if STATE.exists() else {}
    if key in st.get("posts", {}):
        return st["posts"][key]["url"]
    p = read_json(q)
    tok = _token()
    bid = _blog_id(tok)
    h = {"Authorization": f"Bearer {tok}"}
    body = {"kind": "blogger#post", "title": p["title"], "labels": p["labels"], "content": p["html"].replace("__YT__", yt_id)}
    r = requests.post(f"{API}/blogs/{bid}/posts", params={"isDraft": "true"}, headers=h, json=body, timeout=60)
    if not r.ok:
        raise RuntimeError(f"بلاگ: {r.status_code} {r.text[:200]}")
    pid = r.json()["id"]
    params = {}
    if when > dt.datetime.now(TZ) + dt.timedelta(minutes=5):
        params["publishDate"] = when.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    r = requests.post(f"{API}/blogs/{bid}/posts/{pid}/publish", params=params, headers=h, timeout=60)
    if not r.ok:
        raise RuntimeError(f"بلاگ اشاعت: {r.status_code} {r.text[:200]}")
    url = r.json().get("url", "")
    st = read_json(STATE) if STATE.exists() else {}
    st.setdefault("posts", {})[key] = {"id": pid, "url": url, "at": when.isoformat()}
    write_json(STATE, st)
    q.unlink(missing_ok=True)
    return url


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        print("BLOG id", _blog_id(_token()), BLOG_URL)
