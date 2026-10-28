"""یوٹیوب اپلوڈ ایجنٹ — فاروقی اے آئی نیوز (@farooqiainews)

بلیٹن بنتے ہی ویڈیو یوٹیوب پر **Private** اپلوڈ ہوتی ہے (عنوان، تفصیل، ٹیگ، زمرہ، زبان، تھمب نیل، پلے لسٹ)۔
عوام کو تب ہی دکھتی ہے جب مالک ٹیلیگرام پر ✅ دبائے: تب مقررہ وقت (شام 5 بجے سعودی) پر خود پبلک ہونے کے لیے
شیڈول ہو جاتی ہے — وقت گزر چکا ہو تو فوراً پبلک۔ ❌ پر Private ہی رہتی ہے (کچھ ڈیلیٹ نہیں ہوتا)۔

چابیاں (صرف GitHub Secrets): YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN۔
نہ ہوں، یا YOUTUBE_UPLOAD=off ہو، تو کچھ نہیں ہوتا — بلیٹن پہلے کی طرح صرف ٹیلیگرام پر آتا ہے۔
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import requests

API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3"
PLAYLIST = "فاروقی اے آئی نیوز — روزانہ بلیٹن"
CATEGORY_SCI_TECH = "28"
KEYS = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")


class YTError(RuntimeError):
    pass


def enabled() -> bool:
    return os.environ.get("YOUTUBE_UPLOAD", "on") != "off" and all(os.environ.get(k, "").strip() for k in KEYS)


def _token() -> str:
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": os.environ["YOUTUBE_CLIENT_ID"].strip(),
        "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"].strip(),
        "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"].strip(),
        "grant_type": "refresh_token"})
    if not r.ok:
        raise YTError(f"یوٹیوب چابی: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _check(r: requests.Response, what: str) -> dict:
    if not r.ok:
        raise YTError(f"{what}: {r.status_code} {r.text[:300]}")
    return r.json() if r.content else {}


def _tags(tags: list[str]) -> list[str]:
    """یوٹیوب کی حد: کل تقریباً 500 حروف"""
    out, n = [], 0
    for t in tags:
        t = t.replace("<", "").replace(">", "").strip()
        w = len(t) + (2 if " " in t else 0) + 1
        if not t or n + w > 480:
            continue
        out.append(t)
        n += w
    return out


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def upload(video: Path, thumb: Path | None, title: str, desc: str, tags: list[str], playlist: bool = True) -> dict:
    """Private اپلوڈ → {"id", "url", "notes": [...]}۔ تھمب نیل/پلے لسٹ ناکام ہوں تو notes میں، اپلوڈ نہیں رکتا۔"""
    tok = _token()
    meta = {
        "snippet": {"title": title[:100], "description": desc[:4900], "tags": _tags(tags),
                    "categoryId": CATEGORY_SCI_TECH, "defaultLanguage": "ur", "defaultAudioLanguage": "ur"},
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "embeddable": True,
                   "containsSyntheticMedia": True},   # آواز اے آئی کی ہے — یوٹیوب کی پالیسی کے مطابق اعلان
    }
    size = video.stat().st_size
    r = requests.post(f"{UPLOAD}/videos", params={"uploadType": "resumable", "part": "snippet,status"}, timeout=60,
                      headers={**_h(tok), "Content-Type": "application/json; charset=UTF-8",
                               "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)}, json=meta)
    _check(r, "اپلوڈ شروع")
    loc = r.headers["Location"]
    vid = None
    for attempt in range(4):
        try:
            with open(video, "rb") as fh:
                u = requests.put(loc, data=fh, timeout=1800, headers={**_h(tok), "Content-Type": "video/mp4"})
            vid = _check(u, "اپلوڈ")["id"]
            break
        except (requests.RequestException, YTError) as e:
            if attempt == 3:
                raise YTError(f"اپلوڈ: {e}")
    notes = []
    if thumb and thumb.exists():
        t = requests.post(f"{UPLOAD}/thumbnails/set", params={"videoId": vid}, timeout=120,
                          headers={**_h(tok), "Content-Type": "image/jpeg"}, data=thumb.read_bytes())
        if not t.ok:
            notes.append("تھمب نیل نہیں لگا — چینل کی فون تصدیق (youtube.com/verify) کے بغیر یوٹیوب کسٹم تھمب نیل نہیں لگانے دیتا؛ "
                         "تب تک یوٹیوب ویڈیو کے اندر سے خود تصویر چنتا ہے")
    try:
        if not playlist:
            return {"id": vid, "url": f"https://youtu.be/{vid}", "notes": notes}
        pl = _playlist(tok)
        _check(requests.post(f"{API}/playlistItems", params={"part": "snippet"}, headers=_h(tok), timeout=30,
                             json={"snippet": {"playlistId": pl, "resourceId": {"kind": "youtube#video", "videoId": vid}}}),
               "پلے لسٹ")
    except YTError as e:
        notes.append(f"پلے لسٹ میں نہیں ڈالی گئی ({str(e)[:80]})")
    return {"id": vid, "url": f"https://youtu.be/{vid}", "notes": notes}


def _playlist(tok: str) -> str:
    page = None
    while True:
        j = _check(requests.get(f"{API}/playlists", headers=_h(tok), timeout=30,
                                params={"part": "snippet", "mine": "true", "maxResults": 50, **({"pageToken": page} if page else {})}),
                   "پلے لسٹیں")
        for it in j.get("items", []):
            if it["snippet"]["title"].strip() == PLAYLIST:
                return it["id"]
        page = j.get("nextPageToken")
        if not page:
            break
    j = _check(requests.post(f"{API}/playlists", params={"part": "snippet,status"}, headers=_h(tok), timeout=30, json={
        "snippet": {"title": PLAYLIST, "description": "مصنوعی ذہانت کی دنیا کی اہم خبریں، آسان اردو میں — ہر پیر، بدھ اور ہفتہ۔",
                    "defaultLanguage": "ur"},
        "status": {"privacyStatus": "public"}}), "نئی پلے لسٹ")
    return j["id"]


def release(vid: str, when: dt.datetime) -> str:
    """✅ کے بعد: وقت آنے میں 5 منٹ سے زیادہ باقی ہو تو شیڈول، ورنہ فوراً پبلک۔ واپسی: «scheduled» یا «public»"""
    tok = _token()
    cur = _check(requests.get(f"{API}/videos", params={"part": "status", "id": vid}, headers=_h(tok), timeout=30), "ویڈیو")
    if not cur.get("items"):
        raise YTError("یوٹیوب پر ویڈیو نہیں ملی (شاید ہٹا دی گئی)")
    st = cur["items"][0]["status"]
    keep = {k: st[k] for k in ("selfDeclaredMadeForKids", "embeddable", "license", "publicStatsViewable", "containsSyntheticMedia") if k in st}
    now = dt.datetime.now(dt.timezone.utc)
    if when - now > dt.timedelta(minutes=5):
        body, mode = {**keep, "privacyStatus": "private", "publishAt": _iso(when)}, "scheduled"
    else:
        body, mode = {**keep, "privacyStatus": "public"}, "public"
    _check(requests.put(f"{API}/videos", params={"part": "status"}, headers=_h(tok), timeout=30,
                        json={"id": vid, "status": body}), "پبلک/شیڈول")
    return mode
