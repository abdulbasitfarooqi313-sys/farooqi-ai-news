"""ہفتہ وار «50 بڑی خبریں» — تیز رفتار سرخیوں کا راؤنڈ اپ (ہر جمعہ)۔

صرف سرخیاں، ایک کے بعد ایک (ہر ایک تقریباً 5–6 سیکنڈ؛ کل ~5 منٹ)۔ اسکرین: «۱ / ۵۰»، بڑی سرخی، کمپنی کا لوگو۔
ہر 10 خبروں کے بعد مختصر دھن + «خبریں ۱۱ تا ۲۰» والا کارڈ۔ آواز: جیمنائی (میزبان والی)، 10 سرخیاں ایک ہی
درخواست میں — یوں کل ~5–7 درخواستیں (مفت حد 10 روزانہ؛ جمعہ کو بلیٹن نہیں، اس لیے کوٹا اسی کا)۔
باقی سب بلیٹن جیسا: ٹیلیگرام ✅/❌ + یوٹیوب Private اپلوڈ → ✅ پر شام 5 بجے پبلک۔

python -m news.roundup          → اس جمعہ کا راؤنڈ اپ (اگر ابھی نہیں بنا)
python -m news.roundup force    → دوبارہ بنائیں
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys
import tempfile
from pathlib import Path

from . import bulletin as B
from . import explainer as X
from .base import generate_json, read_json, write_json, send_text, _split, SplitError

ROUNDUP_DAY = 4            # جمعہ
N = 50
GN = "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q="
FEEDS = B.FEEDS + [GN + q for q in (
    "%22artificial+intelligence%22+when:7d", "OpenAI+OR+ChatGPT+when:7d", "Google+Gemini+OR+DeepMind+when:7d",
    "Anthropic+OR+Claude+AI+when:7d", "Nvidia+AI+chips+when:7d", "AI+regulation+OR+AI+law+when:7d",
    "AI+startup+funding+when:7d", "Meta+AI+OR+Microsoft+Copilot+when:7d", "AI+robot+OR+humanoid+when:7d",
    "AI+healthcare+OR+AI+education+when:7d")]

SYSTEM = """آپ «فاروقی اے آئی نیوز» کے سینئر اردو نیوز پروڈیوسر ہیں۔ ہفتہ وار پروگرام «ہفتے کی پچاس بڑی خبریں» — تیز رفتار سرخیاں (ریپڈ فائر)۔
سختی سے: صرف دی گئی خبروں کے حقائق؛ کوئی عدد، نام یا دعویٰ اپنی طرف سے نہیں۔ ایک ہی واقعے کی دو سرخیاں نہیں — مختلف خبریں، مختلف کمپنیاں اور موضوعات۔
سب سے اہم پہلے۔ زبان سادہ، ٹی وی خبروں والی؛ انگریزی نام اردو رسم الخط میں (OpenAI = اوپن اے آئی، Anthropic = انتھروپک، Google = گوگل، Nvidia = این ویڈیا، Meta = میٹا، Microsoft = مائیکروسافٹ)۔
بولا جانے والا متن: کوئی بریکٹ، ایموجی، ہیش ٹیگ، نمبر شمار یا انگریزی حروف نہیں۔ سنسنی اور سیاسی رائے نہیں۔

صرف JSON:
{"opening": "آغاز، 20 تا 30 الفاظ: «السلام علیکم! فاروقی اے آئی نیوز کے ہفتہ وار پروگرام میں خوش آمدید…» — آخر میں پچاس خبروں کی طرف",
 "closing": "اختتامی جملہ، 12 تا 20 الفاظ (الوداع یا سبسکرائب نہیں — وہ آؤٹرو میں ہے)",
 "headlines": [ زیادہ سے زیادہ 50: {"h": "بولی جانے والی سرخی، 7 تا 13 الفاظ، مکمل خبر والا جملہ",
                "company": "مرکزی کمپنی کا انگریزی نام (نہ ہو تو خالی)", "domain": "سرکاری ڈومین، مثلاً openai.com (یقین نہ ہو تو خالی)",
                "n": "فہرست میں اس خبر کا نمبر (عدد)"} ],
 "thumb_text": "تھمب نیل: 3 تا 5 الفاظ (مثلاً «ہفتے کی 50 بڑی خبریں»)",
 "youtube_title": "یوٹیوب عنوان (زیادہ سے زیادہ 90 حروف) — «اے آئی کی 50 بڑی خبریں» + ہفتے کی سب سے بڑی خبر کا اشارہ",
 "summary": "یوٹیوب تفصیل کا پہلا پیراگراف، 2 تا 3 جملے",
 "tags": ["15 تا 20 ٹیگ اردو اور انگریزی ملا کر"],
 "social": {"facebook": "3 تا 5 سطریں + 4 ہیش ٹیگ", "instagram": "کیپشن + 12 ہیش ٹیگ", "tiktok": "1 تا 2 سطریں + 5 ہیش ٹیگ",
            "x": "زیادہ سے زیادہ 230 حروف + 2 ہیش ٹیگ", "whatsapp": "2 تا 3 سطریں", "pinned": "پن کمنٹ: ناظرین سے ایک سوال"}}"""


def _key() -> str:
    return B._today() + "-r"


def script(items: list[dict], feedback: str | None = None) -> dict:
    listing = "\n".join(f"[{i + 1}] {it['title']} — {it['source']} · {it['when'][:10]}" for i, it in enumerate(items[:220]))
    user = f"آج کی تاریخ: {B.urdu_date()}\n\nپچھلے سات دن کی AI خبریں:\n\n{listing}"
    if feedback:
        user += f"\n\nمالک کی ہدایت (اس کا خاص خیال رکھیں): {feedback}"
    d = generate_json(SYSTEM, user)
    seen, hs = set(), []
    for h in d.get("headlines", []):
        t = (h.get("h") or "").strip()
        k = re.sub(r"\W+", "", t)[:40]
        if t and k not in seen:
            seen.add(k)
            try:
                it = items[int(str(h.get("n", "")).strip()) - 1]
                h["source"], h["link"] = it["source"], it["link"]
            except (ValueError, IndexError):
                pass
            hs.append(h)
    d["headlines"] = hs[:N]
    if len(d["headlines"]) < 25:
        raise RuntimeError(f"راؤنڈ اپ کے لیے کافی سرخیاں نہیں ({len(d['headlines'])})")
    d["opening"] = d.get("opening") or "السلام علیکم! فاروقی اے آئی نیوز کے ہفتہ وار پروگرام میں خوش آمدید۔ آئیے دیکھتے ہیں ہفتے کی بڑی خبریں۔"
    d["closing"] = d.get("closing") or "یہ تھیں اس ہفتے مصنوعی ذہانت کی دنیا کی بڑی خبریں۔"
    # بلیٹن کے مددگار (تھمب نیل، SEO) کے لیے
    d["stories"] = [{"headline": h["h"], "topic": "ai", "source": h.get("source", ""), "link": h.get("link", "")} for h in d["headlines"]]
    return d


def voices(d: dict, tmp: Path) -> tuple[Path, list[Path], Path]:
    """آغاز، ہر سرخی، اختتام — 10 سرخیاں ایک آواز میں، پھر خاموشیوں سے کاٹ کر"""
    hs = [h["h"].strip() for h in d["headlines"]]
    blocks = [hs[i:i + 10] for i in range(0, len(hs), 10)]
    texts = [d["opening"].strip()] + ["\n\n".join(b) for b in blocks] + [d["closing"].strip()]
    wavs = B._speak(texts, B.ANCHOR_VOICE, tmp, "rnd")
    per: list[Path] = []
    for j, (b, w) in enumerate(zip(blocks, wavs[1:-1])):
        try:
            parts = _split(w, b, tmp, f"rb{j}")
        except SplitError:
            from .base import _silences, _cut
            total = B._dur(w)
            sil = [(a + c) / 2 for a, c in _silences(w)]
            wts = [len(x) + 12 for x in b]
            cuts, acc = [], 0
            for x in wts[:-1]:
                acc += x
                est = total * acc / sum(wts)
                near = min(sil, key=lambda c: abs(c - est)) if sil else est
                cuts.append(near if abs(near - est) < 2.0 else est)
            parts = _cut(w, cuts, total, len(b), tmp, f"rb{j}")
        per += parts
    return wavs[0], per, wavs[-1]


def build(d: dict, tmp: Path) -> tuple[Path, dict]:
    op, per, cl = voices(d, tmp)
    op, cl = B._trim(op, tmp / "opT.wav"), B._trim(cl, tmp / "clT.wav")
    per = [B._trim(p, tmp / f"hT{i}.wav") for i, p in enumerate(per)]
    tune, sting = tmp / "tune.wav", tmp / "sting.wav"
    logo_mp3 = B.A / "headlines_logo.mp3"
    B._ff("-i", str(logo_mp3), "-af", "volume=0.85", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(tune))
    B._ff("-i", str(logo_mp3), "-t", "1.6", "-af", "volume=0.8,afade=t=out:st=1.05:d=0.55,apad=pad_dur=0.1", "-t", "1.7",
          "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(sting))
    parts, t = [], 0.0
    tl = {"utt": [], "cards": [], "bridges": []}

    def add(p: Path, kind: str = "", text: str = ""):
        nonlocal t
        du = B._dur(p)
        parts.append(p)
        if text:
            tl["utt"].append({"t0": round(t, 2), "t1": round(t + du, 2), "kind": kind, "text": text})
        t0, t = t, t + du
        return t0, t

    def gap(sec: float, tag: str):
        return add(B._sil(sec, tmp / f"rg_{tag}.wav"))

    gap(0.5, "s")
    add(op, "anchor", d["opening"])
    gap(0.3, "o")
    u0, u1 = add(tune)
    tl["tune"] = [round(u0, 2), round(u1, 2)]
    n = len(per)
    for i, p in enumerate(per):
        if i and i % 10 == 0:
            gap(0.3, f"b{i}")
            b0, b1 = add(sting)
            tl["bridges"].append({"t0": round(b0, 2), "t1": round(b1, 2), "i": i})
        gap(0.35, f"h{i}")
        a0, a1 = add(p, "head", d["headlines"][i]["h"])
        tl["cards"].append({"t0": round(a0 - 0.35, 2), "t1": round(a1, 2), "i": i})
    gap(0.6, "c")
    c0, c1 = add(cl, "anchor", d["closing"])
    tl["close"] = round(c0 - 0.6, 2)
    gap(1.0, "e")
    lst = tmp / "rbody.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    voice = tmp / "rvoice.wav"
    B._ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c:a", "pcm_s16le", str(voice))
    tl["dur"] = round(B._dur(voice), 2)
    mixed = tmp / "raudio.wav"
    B._ff("-i", str(voice), "-stream_loop", "-1", "-i", str(B.A / "bed.m4a"), "-filter_complex",
          f"[1]volume=0.05,afade=t=in:d=1.5,afade=t=out:st={tl['dur'] - 1.5:.2f}:d=1.5[b];"
          "[0][b]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5[a]",
          "-map", "[a]", "-t", f"{tl['dur']:.2f}", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(mixed))
    tl["n"] = n
    return mixed, tl


def _u(n: int) -> str:
    return str(n).translate(B.UD)


def plan(d: dict, tl: dict, date: str) -> tuple[list, list, list]:
    n = tl["n"]
    sc = [{"t0": 0, "kind": "title", "kicker": "فاروقی اے آئی نیوز · ہفتہ وار",
           "h": f"ہفتے کی {_u(n)} بڑی اے آئی خبریں", "date": date},
          {"t0": tl["tune"][0], "kind": "bridge", "h": f"{_u(n)} خبریں · ریپڈ فائر"}]
    for b in tl["bridges"]:
        sc.append({"t0": b["t0"], "kind": "bridge", "h": f"خبریں {_u(b['i'] + 1)} تا {_u(min(n, b['i'] + 10))}"})
    for c in tl["cards"]:
        h = d["headlines"][c["i"]]
        sc.append({"t0": c["t0"], "kind": "headline", "num": f"{_u(c['i'] + 1)} / {_u(n)}", "h": h["h"],
                   "logo": h.get("_logo"), "co": h.get("company") or ""})
    sc.append({"t0": tl["close"], "kind": "bridge", "h": "فاروقی اے آئی نیوز"})
    sc.sort(key=lambda x: x["t0"])
    for a, b in zip(sc, sc[1:]):
        a["t1"] = b["t0"]
    sc[-1]["t1"] = tl["dur"] + 0.1
    caps = [c for u in tl["utt"] if u["kind"] == "anchor" for c in X._chunks(u["text"], u["t0"], u["t1"])]
    ranges = [(0, tl["dur"], X.br.GENERIC)]              # صرف عنوان والے منظر میں نظر آتی ہے
    return sc, caps, ranges


def seo(d: dict, tl: dict, intro_dur: float) -> dict:
    ch = ["0:00 انٹرو"] + [f"{B._ts(intro_dur + c['t0'])} خبریں {_u(c['i'] + 1)}–{_u(min(tl['n'], c['i'] + 10))}"
                          for c in tl["cards"] if c["i"] % 10 == 0]
    src = "\n".join(f"• {h.get('source', '')}: {h.get('link', '')}" for h in d["headlines"][:25] if h.get("link"))
    desc = (f"{d.get('summary', '')}\n\n📰 ہفتے کی {_u(tl['n'])} بڑی اے آئی خبریں — {B.urdu_date()}\n"
            + "\n".join(f"{i + 1}. {h['h']}" for i, h in enumerate(d["headlines"]))
            + "\n\n⏱️ ابواب:\n" + "\n".join(ch) + (f"\n\n🔗 ماخذ (منتخب):\n{src}" if src else "")
            + "\n\n🎵 Music: “Headlines News Logo” by moodmode (Pixabay)\n🎬 Footage: Pexels"
            + "\n\nفاروقی اے آئی نیوز — مصنوعی ذہانت کی دنیا، آسان اردو میں۔ ہر جمعہ: ہفتے کی پچاس بڑی خبریں۔\n"
            "سبسکرائب کریں، لائک کریں اور بیل آئیکن دبائیں۔\n\n"
            "#فاروقی_اے_آئی_نیوز #مصنوعی_ذہانت #اے_آئی #AINews #WeeklyRoundup #UrduNews #TechNews")
    tags = list(dict.fromkeys((d.get("tags") or []) + ["فاروقی اے آئی نیوز", "Farooqi AI News", "AI News Urdu", "ہفتہ وار خبریں",
                                                        "AI weekly roundup", "مصنوعی ذہانت", "Tech News Urdu"]))
    title = d.get("youtube_title") or f"ہفتے کی {_u(tl['n'])} بڑی اے آئی خبریں"
    if "فاروقی" not in title:
        title = f"{title} | فاروقی اے آئی نیوز"
    return {"youtube_title": title[:100], "youtube_description": desc[:4900], "tags": tags}


def make(feedback: str | None = None) -> None:
    if not B.news_chat():
        raise RuntimeError("ٹیلیگرام چیٹ معلوم نہیں")
    items = B.fetch(max_age_h=24 * 7, feeds=FEEDS, per_feed=40)
    if len(items) < 40:
        raise RuntimeError(f"ہفتے کی کافی خبریں نہیں ملیں ({len(items)})")
    sf = B.ROOT / "state" / f"roundup_{B._today()}.json"
    if sf.exists() and not feedback:
        d = read_json(sf)
    else:
        d = script(items, feedback)
        write_json(sf, d)
    for old in (B.ROOT / "state").glob("roundup_*.json"):
        if old != sf:
            old.unlink()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for i, h in enumerate(d["headlines"]):
            h["_logo"] = B._logo(h.get("domain") or "", tmp, i)
        audio, tl = build(d, tmp)
        print(f"راؤنڈ اپ: {tl['n']} سرخیاں، {tl['dur']:.0f}s")
        sc, caps, ranges = plan(d, tl, B.urdu_date(latin=True))
        body = X.render_scenes(sc, caps, ranges, tl["dur"], audio, tmp / "rbody.mp4", tmp, B._launch, B.FONT,
                               B._b64(B.A / "logo_round.png", "image/png"))
        out = B.ROOT / "out_roundup.mp4"
        B.assemble(body, out)
        B.ANCHOR_ON = False                               # تھمب نیل: خالی اسٹوڈیو (میزبان کی تصویر نہیں)
        thumb = B.thumbnail(d, tmp / "rthumb.jpg", tmp)
        sd = seo(d, tl, B._dur(B.A / "intro.mp4"))
        key = _key()
        vmid, mids = B.deliver(out, thumb, sd, d, key=key, label=f"ہفتہ وار راؤنڈ اپ — {_u(tl['n'])} سرخیاں")
        ytinfo = B._yt_upload(out, thumb, sd)
        import shutil
        shutil.copy(out, B.ROOT / "roundup.mp4")
    st = read_json(B.STATE) if B.STATE.exists() else {}
    st.setdefault("days", {})[key] = {"status": "pending", "vmid": vmid, "mids": mids, "kind": "roundup", **ytinfo}
    st.pop("redo_r", None)
    st["days"] = dict(sorted(st["days"].items())[-40:])
    write_json(B.STATE, st)
    out.unlink(missing_ok=True)
    print("✅ راؤنڈ اپ بھیج دیا")


def tick(force: bool = False) -> None:
    st = read_json(B.STATE) if B.STATE.exists() else {}
    redo = st.get("redo_r")
    if not force and not redo and dt.datetime.now(B.TZ).weekday() != ROUNDUP_DAY:
        print("آج راؤنڈ اپ کا دن نہیں (جمعہ)")
        return
    if not force and not redo and _key() in st.get("days", {}):
        print("اس جمعہ کا راؤنڈ اپ بن چکا")
        return
    make(feedback=(redo or {}).get("feedback") if isinstance(redo, dict) else None)


if __name__ == "__main__":
    try:
        tick(force=len(sys.argv) > 1 and sys.argv[1] == "force")
    except Exception as e:
        import traceback
        (B.ROOT / "state" / "news_error.txt").write_text(traceback.format_exc()[-3000:] + "\n\n" + "\n".join(B.LOG[-12:]), encoding="utf-8")
        try:
            send_text(B.news_chat(), f"⚠️ ہفتہ وار راؤنڈ اپ ابھی نہ بن سکا: {str(e)[:250]}\nاگلے مقررہ وقت پر خود دوبارہ کوشش ہوگی۔", html=False)
        except Exception:
            pass
        raise
