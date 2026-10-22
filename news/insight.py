"""Competitor insight, hook bank and style guide — all free (official YouTube RSS feeds, no keys).

1. Competitor glimpse: latest videos (title + views) of the channels listed in channel.json "competitors".
2. Hook bank: every run adds those titles to data/hook_bank.json; the best performers are kept and fed
   to the writer as proven patterns (never copied word for word).
3. Style guide: style.md is read and given to the writer on every run.
"""
import datetime as dt
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from .base import ROOT

MOCK = False


def log(msg: str) -> None:
    print(f"[insight] {msg}", flush=True)


def load_channel() -> dict:
    try:
        return json.loads((ROOT / "news" / "competitors.json").read_text(encoding="utf-8"))
    except Exception:
        return {}

DATA = ROOT / "state"
BANK = DATA / "hook_bank.json"
IDS = DATA / "competitor_ids.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
NS = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/",
      "yt": "http://www.youtube.com/xml/schemas/2015"}


def _read(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _channel_id(handle: str, cache: dict) -> str:
    if handle.startswith("UC"):
        return handle
    if handle in cache:
        return cache[handle]
    r = requests.get(f"https://www.youtube.com/{handle if handle.startswith('@') else '@' + handle}",
                     headers=UA, cookies={"CONSENT": "YES+1"}, timeout=25)
    m = (re.search(r'"externalId":"(UC[\w-]{22})"', r.text) or re.search(r'"channelId":"(UC[\w-]{22})"', r.text)
         or re.search(r'channel_id=(UC[\w-]{22})', r.text))
    if not m:
        raise RuntimeError("channel id not found")
    cache[handle] = m.group(1)
    return cache[handle]


def competitor_videos(max_age_days: int = 30) -> list:
    """[{channel, title, views, date, url}] newest videos of the competitor channels."""
    handles = load_channel().get("competitors", [])
    if MOCK or not handles:
        return []
    cache = _read(IDS, {})
    out, cutoff = [], dt.datetime.utcnow() - dt.timedelta(days=max_age_days)
    for h in handles:
        try:
            cid = _channel_id(h, cache)
            r = requests.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}", headers=UA, timeout=25)
            r.raise_for_status()
            root = ET.fromstring(r.text)
            name = root.findtext("a:title", "", NS)
            n = 0
            for e in root.findall("a:entry", NS):
                date = dt.datetime.fromisoformat(e.findtext("a:published", "", NS)[:19])
                if date < cutoff:
                    continue
                st = e.find("m:group/m:community/m:statistics", NS)
                out.append({"channel": name, "title": e.findtext("a:title", "", NS),
                            "views": int(st.get("views", 0)) if st is not None else 0,
                            "date": f"{date:%Y-%m-%d}",
                            "url": f"https://youtu.be/{e.findtext('yt:videoId', '', NS)}"})
                n += 1
            log(f"insight: {n} recent videos from {name}")
        except Exception as e:  # one bad handle must never stop the video
            log(f"insight: skipped competitor {h} ({e})")
    DATA.mkdir(exist_ok=True)
    IDS.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    return out


def update_bank(videos: list, keep: int = 300) -> list:
    bank = {v["url"]: v for v in _read(BANK, [])}
    for v in videos:  # newer stats replace older ones
        bank[v["url"]] = v
    items = sorted(bank.values(), key=lambda v: -v.get("views", 0))[:keep]
    DATA.mkdir(exist_ok=True)
    BANK.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    return items


def style_guide() -> str:
    p = ROOT / "news" / "style.md"
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def brief(n_recent: int = 40, n_bank: int = 25) -> str:
    """Text block for the writer prompt."""
    recent = competitor_videos()
    bank = update_bank(recent)
    recent = sorted(recent, key=lambda v: -v["views"])[:n_recent]
    if not recent and not bank:
        return "(competitor data unavailable today — rely on the style guide)"
    fmt = lambda v: f"- [{v['channel']}] \"{v['title']}\" — {v['views']:,} views ({v['date']})"
    return ("COMPETITORS' LATEST VIDEOS (last 30 days, most viewed first):\n" + "\n".join(map(fmt, recent))
            + "\n\nHOOK BANK (best performing titles we have collected so far — learn the PATTERN, never copy):\n"
            + "\n".join(map(fmt, bank[:n_bank])))


VIRAL_RULES = """مقابل چینل اور ہک کے اصول:
- اوپر مقابل چینلوں کی تازہ ویڈیوز اور ان کے ویوز دیکھیں۔ جو خبر وہ پہلے دے چکے ہوں، اس میں وہ پہلو لائیں جو انہوں نے چھوڑا (عام آدمی پر اثر، پاکستان/ہندوستان کے لیے اہمیت، آگے کیا ہوگا)۔
- «youtube_title»، «thumb_text» اور آغاز کا پہلا جملہ مقابلین کے عنوانوں سے زیادہ مضبوط ہو: سب سے زیادہ دیکھے گئے عنوانوں کا انداز سیکھیں (واضح خبر، بڑا نام، تجسس)، مگر ان کے الفاظ نقل نہیں؛ کوئی جھوٹا یا سنسنی خیز دعویٰ نہیں جو بلیٹن میں نہ ہو۔
- «viral» ایمان داری سے بھریں: 0 تا 100 = اس بلیٹن کے مقابلین کی اوسط سے بہتر چلنے کا حقیقی امکان۔"""


if __name__ == "__main__":
    (ROOT / "state" / "insight_test.txt").write_text(brief(), encoding="utf-8")
