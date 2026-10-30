"""🔎 ہر مواد کا پورا SEO پیکیج — ہر پلیٹ فارم کے لیے الگ (مالک کی ہدایت 30 اکتوبر 2026: جو چیز بھی بنے، SEO ساتھ بنے،
تاکہ ہر اپلوڈ ایجنٹ (یوٹیوب، فیس بک، انسٹاگرام، ٹک ٹاک، لنکڈ اِن، X، سنیپ چیٹ، بلاگ) اسی سے اٹھائے)۔

package(kind, title, summary, points, links) → dict ؛ save(key, pkg) → state/seo/<key>.json
ایک سستی جیمنائی «متن» کال (آواز کا کوٹا نہیں لگتا)۔ ناکام ہو تو سادہ خودکار پیکیج — کام نہیں رکتا۔
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import ROOT, generate_json, write_json

DIR = ROOT / "state" / "seo"
BRAND = "فاروقی اے آئی نیوز"
BASE_TAGS = ["فاروقی اے آئی نیوز", "اے آئی", "مصنوعی ذہانت", "AI News Urdu", "Urdu Tech News", "Artificial Intelligence"]
KIND_UR = {"bulletin": "نیوز بلیٹن", "flash": "اے آئی فلیش (شارٹ)", "podcast": "اے آئی بیٹھک پوڈکاسٹ", "word": "آج کا اے آئی لفظ (شارٹ)"}

SYSTEM = """آپ «فاروقی اے آئی نیوز» (اردو اے آئی خبریں) کے سوشل میڈیا اور SEO ماہر ہیں۔ دیے گئے مواد کے لیے **ہر پلیٹ فارم کا الگ، پروفیشنل** پیکیج لکھیں —
ہر پلیٹ فارم کے اپنے انداز، لمبائی اور ہیش ٹیگ کے رواج کے مطابق۔ زبان: اردو رسم الخط (ٹیگ/ہیش ٹیگ اردو اور انگریزی ملا کر تاکہ دونوں تلاشوں میں آئے)۔
اصول: صرف دیے گئے مواد کے حقائق؛ کلک بیٹ، جھوٹا دعویٰ، سنسنی اور سرمایہ کاری کا مشورہ نہیں؛ اہم لفظ (keyword) عنوان کے شروع میں؛ ہیش ٹیگ متعلقہ اور مقبول۔
صرف JSON:
{"keywords": ["5 تا 8 اہم تلاشی الفاظ، اردو/انگریزی"],
 "youtube": {"title": "زیادہ سے زیادہ 90 حروف، keyword شروع میں", "description": "پہلی 2 سطریں سب سے اہم (تلاش میں دکھتی ہیں)، پھر خلاصہ 4 تا 6 سطریں، آخر میں سبسکرائب کی دعوت",
             "tags": ["15 تا 25 ٹیگ"], "hashtags": ["3 ہیش ٹیگ (# کے ساتھ)"], "pinned": "پن کمنٹ: ناظرین سے ایک سوال"},
 "facebook": "3 تا 6 سطریں، دلچسپ آغاز، آخر میں سوال + 3 تا 5 ہیش ٹیگ",
 "instagram": "کیپشن: پہلی سطر ہک، 3 تا 5 سطریں، «لنک بایو میں»، خالی سطر، 15 تا 20 ہیش ٹیگ",
 "tiktok": "1 تا 2 سطریں + 4 تا 6 ہیش ٹیگ (#fyp قسم کے عام نہیں، موضوع والے)",
 "linkedin": "پروفیشنل انداز، 4 تا 7 سطریں: یہ خبر کاروبار/روزگار/ٹیکنالوجی کے لیے کیوں اہم، آخر میں سوال + 3 ہیش ٹیگ",
 "x": "زیادہ سے زیادہ 240 حروف + 2 ہیش ٹیگ",
 "threads": "2 تا 4 سطریں، گفتگو والا انداز",
 "snapchat": "اسپاٹ لائٹ کیپشن، زیادہ سے زیادہ 150 حروف + 2 ہیش ٹیگ",
 "whatsapp": "چینل/اسٹیٹس کے لیے 2 تا 3 سطریں",
 "blog": {"title": "بلاگ پوسٹ کا SEO عنوان (60 حروف کے قریب)", "meta_description": "150 تا 160 حروف", "labels": ["3 تا 5 لیبل"], "slug": "english-url-slug"}}"""


def _fallback(kind: str, title: str, summary: str) -> dict:
    tags = BASE_TAGS + [KIND_UR.get(kind, "")]
    h = "#اے_آئی #فاروقی_اے_آئی_نیوز #AINews"
    short = f"{title}\n\n{summary}".strip()
    return {"keywords": tags[:6],
            "youtube": {"title": title[:90], "description": short, "tags": tags, "hashtags": h.split(), "pinned": "آپ کی اس بارے میں کیا رائے ہے؟"},
            "facebook": f"{short}\n\n{h}", "instagram": f"{title}\n\nلنک بایو میں 🔗\n\n{h}", "tiktok": f"{title} {h}",
            "linkedin": f"{short}\n\n{h}", "x": f"{title[:200]} #اے_آئی #AINews", "threads": short, "snapchat": title[:140],
            "whatsapp": short, "blog": {"title": title[:70], "meta_description": summary[:160], "labels": ["اے آئی", KIND_UR.get(kind, "خبریں")],
                                        "slug": re.sub(r"[^a-z0-9]+", "-", kind).strip("-")}}


def package(kind: str, title: str, summary: str = "", points: list[str] | None = None, links: list[str] | None = None,
            url: str = "") -> dict:
    user = (f"قسم: {KIND_UR.get(kind, kind)}\nعنوان: {title}\nخلاصہ: {summary}\n\nنکات:\n" +
            "\n".join(f"- {p}" for p in (points or [])[:25]) +
            (f"\n\nماخذ:\n" + "\n".join(links[:10]) if links else "") + (f"\n\nویڈیو کا لنک: {url}" if url else ""))
    try:
        p = generate_json(SYSTEM, user)
        if not isinstance(p.get("youtube"), dict):
            raise ValueError("youtube حصہ نہیں")
    except Exception as e:
        print("SEO پیکیج: سادہ نسخہ —", e)
        p = _fallback(kind, title, summary)
    yt = p["youtube"]
    yt["tags"] = list(dict.fromkeys([t for t in (yt.get("tags") or []) + BASE_TAGS if t]))
    return p


def save(key: str, pkg: dict) -> Path:
    DIR.mkdir(parents=True, exist_ok=True)
    f = DIR / f"{key}.json"
    write_json(f, pkg)
    return f


def social(pkg: dict) -> dict:
    """deliver() کے لیے: ٹیلیگرام پیکیج والے خانے"""
    return {k: pkg.get(k, "") for k in ("facebook", "instagram", "tiktok", "x", "linkedin", "snapchat", "threads", "whatsapp")} | \
           {"pinned": (pkg.get("youtube") or {}).get("pinned", "")}


def attach(kind: str, key: str, d: dict, sd: dict, points: list[str] | None = None, links: list[str] | None = None) -> dict:
    """ایک قدم میں: پیکیج بنائیں، یوٹیوب ٹیگ ملائیں، ٹیلیگرام کے سوشل خانے بھریں، state/seo/<key>.json میں محفوظ کریں"""
    pkg = package(kind, sd.get("youtube_title", ""), d.get("summary", ""), points, links)
    sd["tags"] = list(dict.fromkeys((sd.get("tags") or []) + pkg["youtube"].get("tags", [])))[:40]
    sd["seo"] = pkg
    d["social"] = {**social(pkg), **{k: v for k, v in (d.get("social") or {}).items() if v}}
    b = pkg.get("blog") or {}
    if b:
        d["social"]["blog"] = f"عنوان: {b.get('title', '')}\nتفصیل (meta): {b.get('meta_description', '')}\nلیبل: {', '.join(b.get('labels', []))}\nURL: {b.get('slug', '')}"
    save(key, pkg)
    return pkg
