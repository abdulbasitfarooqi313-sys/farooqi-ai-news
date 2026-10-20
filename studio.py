"""نیوز اسٹوڈیو ویڈیو — اردو خبرنامہ (1920×1080)

ہر خبر کی ایک سلائیڈ: اسٹوڈیو پس منظر، «تازہ ترین» پٹی، خبر نمبر، نستعلیق سرخی، خلاصہ، ماخذ،
اور نیچے چلتی ہوئی خبروں کی پٹی (ٹکر)۔ آواز: دو اردو نیوز اینکر، مرد اور خاتون باری باری (Gemini کی پیشہ ور آواز؛ متبادل Microsoft Edge)۔
سلائیڈیں ہیڈلیس کروم سے بنتی ہیں تاکہ اردو نستعلیق بالکل درست جڑے۔
"""
from __future__ import annotations

import asyncio
import base64
import html
import os
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
W, H, FPS = 1920, 1080, 30
MOCK = os.environ.get("MOCK") == "1"

# دو اینکر: مرد اور خاتون باری باری۔ پہلی پسند Gemini کی آواز (پیشہ ور نیوز اینکر کا لہجہ)،
# کوٹہ ختم ہو یا چابی نہ ہو تو Microsoft Edge کی اردو آواز۔
GEMINI_VOICES = [v.strip() for v in os.environ.get("NEWS_GEMINI_VOICES", "Charon,Kore").split(",") if v.strip()]
VOICES = [v.strip() for v in os.environ.get("NEWS_VOICES", "ur-PK-AsadNeural,ur-PK-UzmaNeural").split(",") if v.strip()]
TTS_MODELS = ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"]
STYLE = {
    0: "a seasoned male news anchor of a Pakistani national TV channel (PTV / Geo prime-time bulletin style): "
       "deep, authoritative, steady and formal; refined standard Urdu (Karachi/Lahore broadcast Urdu, not Hindi), "
       "correct Urdu sounds for ق خ غ ز ع; measured news-reading pace, slight emphasis on key words, "
       "clear pause at every full stop; serious but not dramatic, no smiling tone",
    1: "a seasoned female news anchor of a Pakistani national TV channel (PTV / Geo prime-time bulletin style): "
       "clear, composed, confident and formal; refined standard Urdu (broadcast Urdu, not Hindi), "
       "correct Urdu sounds for ق خ غ ز ع; measured news-reading pace, clear pause at every full stop; no theatrics",
}
_GEMINI_OFF = {"off": not os.environ.get("GEMINI_API_KEY")}
VOICE_USED: set = set()


def _ff(*args) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *map(str, args)], check=True, timeout=900)


def _dur(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def _gemini_tts(text: str, role: int, out: Path) -> Path | None:
    import json, re, wave
    import requests
    if _GEMINI_OFF["off"] or MOCK:
        return None
    voice = GEMINI_VOICES[role % len(GEMINI_VOICES)]
    prompt = (f"Voice style (do not read this line aloud): {STYLE[role % 2]}. Say nothing except the Urdu text "
              f"below, exactly once, word for word — no greeting or words of your own:\n\n{text}")
    if "tts" not in _GEMINI_OFF:
        try:
            from script import available_models
            _GEMINI_OFF["tts"] = list(dict.fromkeys(available_models(os.environ["GEMINI_API_KEY"], "tts") + TTS_MODELS))
        except Exception:
            _GEMINI_OFF["tts"] = TTS_MODELS
        print("Gemini آواز کے ماڈل:", ", ".join(_GEMINI_OFF["tts"]))
    for model in _GEMINI_OFF["tts"]:
        for attempt in range(3):
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                  headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout=180, json={
                                      "contents": [{"parts": [{"text": prompt}]}],
                                      "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                                          "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}})
            except requests.RequestException:
                time.sleep(10)
                continue
            if r.status_code == 429:
                if re.search(r"PerDay|per_day|per day|limit: 0", r.text, re.I):
                    print("Gemini آواز: آج کا مفت کوٹہ ختم — Edge کی آواز پر")
                    _GEMINI_OFF["off"] = True
                    return None
                m = re.search(r'"retryDelay":\s*"(\d+)', r.text)
                time.sleep(min(60, int(m.group(1)) + 2 if m else 30))
                continue
            if r.status_code in (500, 503):
                time.sleep(10)
                continue
            if not r.ok:
                print(f"Gemini آواز {model}: HTTP {r.status_code} {r.text[:200]}")
                break
            try:
                part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
            except (KeyError, IndexError, json.JSONDecodeError):
                break
            m = re.search(r"rate=(\d+)", part.get("mimeType", ""))
            raw = out.with_suffix(".wav")
            with wave.open(str(raw), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(int(m.group(1)) if m else 24000)
                w.writeframes(base64.b64decode(part["data"]))
            if raw.stat().st_size > 20000:
                VOICE_USED.add(f"Gemini {model} ({voice})")
                return raw
    print("Gemini آواز نہیں ملی — آج Edge کی آواز پر")
    _GEMINI_OFF["off"] = True
    return None


async def _speak(text: str, out: Path, voice: str) -> None:
    import edge_tts
    await edge_tts.Communicate(text, voice, rate="-2%").save(str(out))


def _fix_edge(text: str) -> str:
    """Edge کی آواز چند الفاظ غلط بولتی ہے — اعراب سے درست"""
    return (text.replace("السلام علیکم", "اَلسَّلامُ عَلَیکُم")
                .replace("اللہ حافظ", "اللّٰہ حافِظ"))


def speak(text: str, out: Path, role: int = 0) -> Path:
    g = _gemini_tts(text, role, out)
    if g:
        return g
    if MOCK:
        _ff("-f", "lavfi", "-i", f"sine=f=220:d={max(3, len(text.split()) / 2.4):.1f}", "-af", "volume=0.05", out)
        return out
    voice = VOICES[role % len(VOICES)]
    for i in range(5):
        try:
            asyncio.run(_speak(_fix_edge(text), out, voice))
            if out.exists() and out.stat().st_size > 2000:
                VOICE_USED.add(f"Edge {voice}")
                return out
        except Exception as e:
            print(f"آواز: دوبارہ کوشش {i + 1} ({e})")
        time.sleep(5 * (i + 1))
    raise RuntimeError("اردو آواز نہ بن سکی")


# ---------------- سلائیڈ (HTML) ----------------

def _font(name: str) -> str:
    return "data:font/woff2;base64," + base64.b64encode((FONTS / name).read_bytes()).decode()


CSS = """
@font-face{font-family:Nast;font-weight:400;src:url(@@n4@@)}
@font-face{font-family:Nast;font-weight:700;src:url(@@n7@@)}
@font-face{font-family:Naskh;font-weight:700;src:url(@@k7@@)}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1920px;height:1080px;overflow:hidden;background:#040a1c}
body{font-family:Nast,Naskh,serif;color:#fff;direction:rtl;position:relative}
.bg{position:absolute;inset:0;background:
 radial-gradient(900px 520px at 72% 38%,rgba(30,100,255,.42),transparent 70%),
 radial-gradient(700px 500px at 18% 60%,rgba(0,190,255,.16),transparent 70%),
 linear-gradient(165deg,#0b1a44 0%,#071030 50%,#030716 100%)}
.grid{position:absolute;inset:0;opacity:.09;background-image:
 linear-gradient(rgba(120,170,255,.7) 1px,transparent 1px),linear-gradient(90deg,rgba(120,170,255,.7) 1px,transparent 1px);
 background-size:64px 64px;mask-image:radial-gradient(ellipse at 60% 45%,#000 30%,transparent 75%)}
.wall{position:absolute;left:40px;right:40px;top:150px;height:600px;display:grid;grid-template-columns:repeat(4,1fr);
 grid-template-rows:repeat(2,1fr);gap:14px;opacity:.16;transform:perspective(1400px) rotateX(4deg)}
.wall div{border-radius:8px;background:linear-gradient(160deg,rgba(60,140,255,.9),rgba(10,40,120,.6));
 box-shadow:0 0 40px rgba(40,140,255,.5);border:1px solid rgba(160,210,255,.6)}
.wall div:nth-child(3n){background:linear-gradient(160deg,rgba(0,200,255,.8),rgba(10,40,120,.5))}
.floor{position:absolute;left:0;right:0;bottom:200px;height:180px;
 background:linear-gradient(180deg,transparent,rgba(30,90,220,.18));border-top:1px solid rgba(120,180,255,.18)}
.globe{position:absolute;left:-220px;top:90px;width:820px;height:820px;border-radius:50%;
 border:2px solid rgba(80,170,255,.18);box-shadow:inset 0 0 140px rgba(40,120,255,.18)}
.globe:before,.globe:after{content:"";position:absolute;inset:70px;border-radius:50%;border:1px solid rgba(80,170,255,.14)}
.globe:after{inset:200px}
/* اوپر کی پٹی */
.top{position:absolute;top:0;left:0;right:0;height:112px;display:flex;align-items:center;justify-content:space-between;
 padding:0 56px;background:linear-gradient(180deg,rgba(3,8,26,.95),rgba(3,8,26,.55));border-bottom:2px solid rgba(0,198,255,.35)}
.logo{display:flex;align-items:center;gap:20px}
.mark{width:92px;height:92px;border-radius:50%;box-shadow:0 0 22px rgba(0,170,255,.5)}
.brand{font-weight:700;font-size:44px;line-height:1.6}
.right{display:flex;align-items:center;gap:22px}
.date{font-size:34px;color:#cfe0ff;line-height:1.6}
.tag{font-family:Naskh;font-weight:700;font-size:26px;background:#e11d2e;padding:4px 18px;border-radius:6px;direction:ltr}
/* خبر */
.card{position:absolute;left:56px;top:170px;width:400px;height:560px;border-radius:26px;
 background:linear-gradient(160deg,rgba(255,255,255,.10),rgba(255,255,255,.03));border:1px solid rgba(140,190,255,.25);
 display:flex;flex-direction:column;align-items:center;justify-content:center;gap:26px;overflow:hidden}
.card img{position:absolute;width:520px;opacity:.10;filter:blur(1px)}
.card img.lg{position:relative;opacity:1;filter:none;width:200px;height:200px;border-radius:50%;box-shadow:0 0 40px rgba(0,170,255,.5)}
.card .of{font-size:34px;color:#cfe0ff;line-height:1.6}
.card .src{font-family:Naskh;font-weight:700;font-size:30px;background:rgba(0,198,255,.15);border:1px solid rgba(0,198,255,.5);
 padding:6px 22px;border-radius:30px;color:#bfefff;direction:ltr}
.panel{position:absolute;right:56px;left:780px;top:170px;height:560px;display:flex;flex-direction:column;justify-content:center}
.kicker{align-self:flex-start;font-weight:700;font-size:32px;color:#04102b;background:linear-gradient(90deg,#7fe3ff,#00c6ff);
 padding:0 22px;border-radius:6px;line-height:1.9;margin-bottom:14px}
.head{font-weight:700;font-size:@@hs@@px;line-height:2.0;text-shadow:0 6px 30px rgba(0,0,0,.6)}
.bar{width:200px;height:7px;background:linear-gradient(90deg,#3a5bff,#00c6ff);border-radius:4px;margin:14px 0 20px}
.body{font-size:@@bs@@px;line-height:1.95;color:#dce8ff}
.cmt{margin-top:18px;border-right:6px solid #ffc94d;background:rgba(255,201,77,.08);border-radius:10px;padding:6px 22px}
.cmt b{color:#ffc94d;font-size:30px}
.cmt span{font-size:@@cs@@px;line-height:1.9;color:#fff3d6}
/* نیچے: سرخی کی پٹی + ٹکر */
.l3{position:absolute;left:0;right:0;bottom:104px;height:96px;display:flex;align-items:stretch;
 background:linear-gradient(90deg,#0a3aa8,#1150d8 60%,#0d47c9);box-shadow:0 -6px 30px rgba(0,0,0,.45)}
.l3 .lab{background:#e11d2e;font-weight:700;font-size:36px;padding:0 30px;line-height:2.6;white-space:nowrap}
.l3 .txt{flex:1;font-weight:700;font-size:38px;line-height:2.45;padding:0 28px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.l3 .bug{width:96px;display:flex;align-items:center;justify-content:center;background:#071a55}
.l3 .bug img{width:78px;height:78px;border-radius:50%}
.lower{position:absolute;left:0;right:0;bottom:0;height:104px;background:#06102e;border-top:3px solid #00c6ff;display:flex;align-items:center}
.lower .t{background:#00c6ff;color:#04102b;font-weight:700;font-size:34px;height:100%;padding:0 30px;line-height:2.9;white-space:nowrap}
/* آغاز / اختتام */
.center{position:absolute;top:0;bottom:0;right:0;left:720px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding-bottom:90px}
.biglogo{width:300px;height:300px;border-radius:50%;margin-bottom:6px;box-shadow:0 0 70px rgba(0,170,255,.5)}
.big{font-weight:700;font-size:92px;line-height:1.8;text-shadow:0 10px 40px rgba(0,0,0,.6)}
.sub{font-size:48px;line-height:1.8;color:#bfe9ff}
"""


def _page(inner: str, hs: int = 72, bs: int = 44, cs: int = 34) -> str:
    css = CSS
    for k, v in {"n4": _font("noto-nastaliq-urdu-arabic-400-normal.woff2"),
                 "n7": _font("noto-nastaliq-urdu-arabic-700-normal.woff2"),
                 "k7": _font("noto-naskh-arabic-arabic-700-normal.woff2"), "hs": hs, "bs": bs, "cs": cs}.items():
        css = css.replace(f"@@{k}@@", str(v))
    return (f'<!doctype html><html lang="ur"><meta charset="utf-8"><style>{css}</style><body>'
            f'<div class="bg"></div><div class="wall">{"<div></div>" * 8}</div><div class="floor"></div>'
            f'<div class="grid"></div>{inner}</body></html>')


def _logo() -> str:
    f = ROOT / "assets" / "logo.png"
    return "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode() if f.exists() else ""


def _top(date: str) -> str:
    return (f'<div class="top"><div class="logo"><img class="mark" src="{_logo()}"><div class="brand">فاروقی اے آئی نیوز</div></div>'
            f'<div class="right"><div class="date">{html.escape(date)}</div><div class="tag">AI NEWS</div></div></div>')


def _lower() -> str:
    return '<div class="lower"><div class="t">تازہ ترین</div></div>'


def story_html(headline: str, body: str, source: str, date: str, comment: str = "") -> str:
    n = len(headline) + len(body) + len(comment)
    hs, bs, cs = (64, 38, 32) if n < 300 else (56, 34, 29) if n < 430 else (50, 31, 27)
    inner = (_top(date) +
             f'<div class="panel"><div class="kicker">تفصیلات · {html.escape(source)}</div><div class="head">{html.escape(headline)}</div>'
             f'<div class="bar"></div><div class="body">{html.escape(body)}</div>'
             + (f'<div class="cmt"><b>ہمارا تبصرہ: </b><span>{html.escape(comment)}</span></div>' if comment else "") + '</div>'
             f'<div class="l3"><div class="lab">اہم خبر</div><div class="txt">{html.escape(headline)}</div>'
             f'<div class="bug"><img src="{_logo()}"></div></div>' + _lower())
    return _page(inner, hs, bs, cs)


def headline_html(headline: str, date: str) -> str:
    """سرخیوں کا حصہ: پوری اسکرین پر ایک سرخی"""
    inner = (_top(date) + '<div class="center"><div class="kicker" style="align-self:center;font-size:40px">اہم سرخیاں</div>'
             f'<div class="big" style="font-size:76px;max-width:1100px">{html.escape(headline)}</div></div>'
             f'<div class="l3"><div class="lab">سرخیاں</div><div class="txt">{html.escape(headline)}</div>'
             f'<div class="bug"><img src="{_logo()}"></div></div>' + _lower())
    return _page(inner)


def title_html(big: str, sub: str, date: str) -> str:
    inner = (_top(date) + f'<div class="center"><img class="biglogo" src="{_logo()}"><div class="big">{html.escape(big)}</div>'
             f'<div class="sub">{html.escape(sub)}</div></div>' + _lower())
    return _page(inner)


def shoot(pages: list[str], outdir: Path, transparent: bool = False, height: int = H, tag: str = "slide") -> list[Path]:
    from playwright.sync_api import sync_playwright
    paths = []
    with sync_playwright() as pw:
        exe = "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").is_file() else None
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={"width": W, "height": height})
        for k, doc in enumerate(pages):
            f = outdir / f"{tag}{k}.html"
            f.write_text(doc, encoding="utf-8")
            pg.goto(f.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(300)
            p = outdir / f"{tag}{k}.png"
            pg.screenshot(path=str(p), omit_background=transparent)
            paths.append(p)
        br.close()
    return paths


# ---------------- ٹکر (نیچے چلتی پٹی) ----------------

def ticker_png(text: str, out: Path) -> Path:
    """لمبی افقی تصویر — ffmpeg اسے دائیں سے بائیں چلاتا ہے"""
    from playwright.sync_api import sync_playwright
    doc = _page("").replace("<body>", "<body style='width:auto;height:104px;background:#06102e'>")
    doc = doc.replace(doc[doc.index('<div class="bg">'):doc.index('</body>')],
                      f'<div id="t" style="display:inline-block;white-space:nowrap;font-size:40px;line-height:2.6;'
                      f'padding:0 60px;color:#fff">{html.escape(text)}</div>')
    with sync_playwright() as pw:
        exe = "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").is_file() else None
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page(viewport={"width": 1600, "height": 110})
        f = out.with_suffix(".html")
        f.write_text(doc, encoding="utf-8")
        pg.goto(f.as_uri())
        pg.evaluate("document.fonts.ready")
        w = int(pg.evaluate("document.getElementById('t').getBoundingClientRect().width")) + 10
        pg.set_viewport_size({"width": max(w, 1600), "height": 110})
        pg.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": w, "height": 110})
        br.close()
    return out


# ---------------- اینکر (اصل تصویریں) ----------------

PHOTOS = ROOT / "assets" / "anchors"
PS = H / 768                                   # 1408×768 تصویر → 1080 اونچائی
PX = (round(1408 * PS) - W) // 2               # دونوں طرف سے کٹنے والا حصہ
FACE = {"m": (850, 203), "f": (365, 272)}      # اصل تصویر میں منہ/چہرے کا مرکز
ANCHOR_X = 1290                                 # نئے اسٹوڈیو میں اینکر کا مرکز (دائیں طرف، بائیں طرف لوگو والی دیوار)
_SET: dict = {}                                 # اسٹوڈیو کی دیوار اور میز (render میں ایک بار بنتی ہیں)


def face_box(who: str) -> tuple[int, int, int, int]:
    """اسکرین پر چہرے کا ڈبہ (ہونٹوں کی AI حرکت کے لیے) — اصل تصویر میں (785..920, 112..252)"""
    ox, oy = FACE[who]
    cx = _sx(who)
    return (round(cx + (785 - ox) * PS), round(112 * PS), round(cx + (920 - ox) * PS), round(252 * PS))


_LS: dict = {}


def _lipsync_ok() -> bool:
    if "ok" not in _LS:
        try:
            import lipsync
            _LS["ok"] = lipsync.available()
        except Exception as e:
            print(f"lipsync: {e}")
            _LS["ok"] = False
    return _LS["ok"]


def _cut(who: str) -> Path:
    return PHOTOS / ("male_cut.png" if who == "m" else "female_cut.png")


def _sx(who: str) -> float:
    """اینکر کے چہرے کا اسکرین پر x"""
    return ANCHOR_X if (_cut(who).exists() and _SET) else FACE[who][0] * PS - PX
BOX = (50, 140, 700, 720)                      # تفصیل والی اسکرین پر اینکر کی کھڑکی: x, y, w, h


def _anchor_full(who: str, d: float = 0.0):
    """پوری اسکرین کی اینکر تصویر؛ مرد کے لیے d = منہ کتنا کھلا (پکسل)"""
    import numpy as np
    from PIL import Image
    if _cut(who).exists() and _SET:
        # نیا روشن اسٹوڈیو: دیوار → اینکر (الگ کی ہوئی تصویر) → میز
        im = _SET["wall"].copy()
        cut = Image.open(_cut(who)).convert("RGBA")
        cut = cut.resize((round(cut.width * PS), H), Image.LANCZOS)
        im.alpha_composite(cut, (round(ANCHOR_X - FACE[who][0] * PS), 0))
        im.alpha_composite(_SET["desk"])
        im = im.convert("RGB")
    else:
        im = Image.open(PHOTOS / ("male.jpg" if who == "m" else "female.jpg")).convert("RGB")
        im = im.resize((round(im.width * PS), H), Image.LANCZOS).crop((PX, 0, PX + W, H))
    if who != "m" or d <= 0:
        return im
    cx, my = _sx("m"), FACE["m"][1] * PS
    x0, x1, y0, y1 = int(cx - 70 * PS), int(cx + 70 * PS), int(my - 10 * PS), int(my + 70 * PS)
    a = np.asarray(im).astype(np.float32)
    sub = a[y0:y1, x0:x1]
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    wx = np.clip(1 - ((xx - cx) / (40 * PS)) ** 2, 0, 1)
    t = yy - my
    prof = np.where(t < 0, 0, np.where(t < 10 * PS, t / (10 * PS), np.clip(1 - (t - 10 * PS) / (45 * PS), 0, 1)))
    dy = d * PS * wx * prof
    sy = np.clip(yy - dy, 0, H - 1)
    iy = np.floor(sy).astype(int)
    f = (sy - iy)[..., None]
    xi = xx.astype(int)
    warped = a[iy, xi] * (1 - f) + a[np.clip(iy + 1, 0, H - 1), xi] * f
    gap = (wx * ((t >= 0) & (t < dy * 0.9)) * min(1.0, d / 6))[..., None]
    warped = warped * (1 - 0.55 * gap) + np.array([40, 15, 15], np.float32) * 0.55 * gap
    a = a.copy()
    a[y0:y1, x0:x1] = warped
    del sub
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


MOUTHS = (0.0, 3.0, 5.0)

SET_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1920px;height:1080px;overflow:hidden;background:transparent}
body{font-family:Nast,Naskh,serif;position:relative}
.wall{position:absolute;inset:0;background:linear-gradient(180deg,#f4f6fa 0%,#e7ebf2 62%,#d9dee8 100%)}
.panel{position:absolute;top:0;bottom:0;width:2px;background:rgba(120,135,160,.22)}
.arc1{position:absolute;left:-520px;top:-420px;width:1500px;height:1500px;border-radius:50%;
 border:120px solid #0b2a6f;opacity:.95}
.arc2{position:absolute;left:-420px;top:-320px;width:1300px;height:1300px;border-radius:50%;border:16px solid #00b4e6}
.arc3{position:absolute;left:-600px;top:-500px;width:1660px;height:1660px;border-radius:50%;border:6px solid #d4a73a}
.arc4{position:absolute;right:-380px;top:-260px;width:900px;height:900px;border-radius:50%;border:70px solid rgba(11,42,111,.10)}
.screen{position:absolute;left:150px;top:150px;width:700px;height:560px;border-radius:14px;overflow:hidden;
 background:radial-gradient(500px 360px at 50% 40%,#1b4fc4,#0a1f5c 70%,#06123a);border:10px solid #1c2433;
 box-shadow:0 30px 60px rgba(10,20,50,.35);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px}
.screen:before{content:"";position:absolute;inset:0;opacity:.16;background-image:
 linear-gradient(rgba(140,200,255,.8) 1px,transparent 1px),linear-gradient(90deg,rgba(140,200,255,.8) 1px,transparent 1px);background-size:40px 40px}
.screen img{width:300px;height:300px;border-radius:50%;box-shadow:0 0 50px rgba(0,190,255,.6);position:relative}
.screen .t{font-weight:700;font-size:58px;color:#fff;line-height:1.7;position:relative}
.screen .e{font-family:Naskh;font-weight:700;font-size:30px;letter-spacing:8px;color:#7fe3ff;position:relative;direction:ltr}
.light{position:absolute;left:0;right:0;top:0;height:70px;background:linear-gradient(180deg,rgba(255,255,255,.9),transparent)}
.floor{position:absolute;left:0;right:0;bottom:0;height:260px;background:linear-gradient(180deg,rgba(200,208,222,0),rgba(170,180,200,.55))}
.desk{position:absolute;left:640px;right:-40px;top:842px;height:260px;border-radius:40px 0 0 0;
 background:linear-gradient(180deg,#ffffff 0%,#f1f4f9 14%,#dfe5ee 15%,#ffffff 40%,#e9edf4 100%);
 box-shadow:0 -6px 24px rgba(20,40,80,.18)}
.desk:after{content:"";position:absolute;left:0;right:0;top:34px;height:10px;background:linear-gradient(90deg,#0b2a6f,#00b4e6,#d4a73a)}
"""


def build_set(tmp: Path) -> None:
    """روشن جدید نیوز اسٹوڈیو: دیوار (لوگو والی بڑی اسکرین) اور سفید میز"""
    from PIL import Image
    fonts = (f"@font-face{{font-family:Nast;font-weight:700;src:url({_font('noto-nastaliq-urdu-arabic-700-normal.woff2')})}}"
             f"@font-face{{font-family:Naskh;font-weight:700;src:url({_font('noto-naskh-arabic-arabic-700-normal.woff2')})}}")
    panels = "".join(f'<div class="panel" style="left:{x}px"></div>' for x in (980, 1240, 1500, 1760))
    wall = (f'<!doctype html><meta charset="utf-8"><style>{fonts}{SET_CSS}</style><body><div class="wall"></div>{panels}'
            f'<div class="arc4"></div><div class="arc3"></div><div class="arc1"></div><div class="arc2"></div><div class="light"></div>'
            f'<div class="screen"><img src="{_logo()}"><div class="t">فاروقی اے آئی نیوز</div><div class="e">AI NEWS</div></div>'
            f'<div class="floor"></div></body>')
    desk = f'<!doctype html><meta charset="utf-8"><style>{fonts}{SET_CSS}</style><body><div class="desk"></div></body>'
    a, b = shoot([wall], tmp, tag="setwall"), shoot([desk], tmp, transparent=True, tag="setdesk")
    _SET["wall"] = Image.open(a[0]).convert("RGBA")
    _SET["desk"] = Image.open(b[0]).convert("RGBA")


def brand_screen_html() -> str:
    """نیوز روم کی بڑی اسکرین پر اپنا برانڈ (تصویر کی اصل اسکرین اور سائن ڈھک جاتے ہیں)"""
    x, y, w, h = RP
    return _bare(f'<div class="rp" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
                 f'<div class="vis g" style="top:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px">'
                 f'<img src="{_logo()}" style="width:330px;height:330px;border-radius:50%;box-shadow:0 0 60px rgba(0,190,255,.6)">'
                 f'<div style="font-weight:700;font-size:64px;line-height:1.7">فاروقی اے آئی نیوز</div>'
                 f'<div style="font-size:38px;color:#bfe9ff;line-height:1.6">باوثوق · باخبر · سب سے آگے</div></div></div>'
                 f'<div style="position:absolute;left:1360px;top:8px;width:260px;height:118px;border-radius:10px;background:#1a1f2b;'
                 f'border:4px solid #2b3245;display:flex;align-items:center;justify-content:center">'
                 f'<div style="font-family:Naskh;font-weight:700;font-size:44px;color:#ff4d5e;text-shadow:0 0 18px rgba(255,60,80,.8);direction:ltr">AI NEWS</div></div>')


def anchor_states(tmp: Path) -> dict:
    out = {}
    from PIL import Image as _I
    screen = None
    if not (_cut("f").exists() and _SET):
        screen = _I.open(shoot([brand_screen_html()], tmp, transparent=True, tag="brand")[0]).convert("RGBA")
    for who in ("m", "f"):
        for mo, d in enumerate(MOUTHS if who == "m" else (0.0,)):
            f = tmp / f"anchor_{who}{mo}.png"
            im_ = _anchor_full(who, d)
            if who == "f" and screen is not None:
                im_ = im_.convert("RGBA")
                im_.alpha_composite(screen)
                im_ = im_.convert("RGB")
            im_.save(f)
            out[(who, mo)] = f
    return out


def _studio_bg(who: str) -> str:
    """تفصیل والی اسکرین کا پس منظر: اسی نیوز روم کی دھندلی تصویر"""
    from io import BytesIO
    from PIL import ImageFilter, ImageEnhance
    im = _anchor_full(who).filter(ImageFilter.GaussianBlur(18))
    im = ImageEnhance.Brightness(im).enhance(0.42)
    b = BytesIO()
    im.save(b, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


CSS += """
.studio{position:absolute;inset:0;background-size:cover}
.shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(2,8,30,.25),rgba(2,8,30,.78) 45%,rgba(2,8,30,.9))}
.abox{position:absolute;left:@@bx@@px;top:@@by@@px;width:@@bw@@px;height:@@bh@@px;border-radius:18px;
 border:3px solid rgba(0,198,255,.75);box-shadow:0 0 0 6px rgba(0,198,255,.12),0 20px 60px rgba(0,0,0,.6)}
.abox .nm{position:absolute;bottom:-3px;right:-3px;left:-3px;height:58px;background:linear-gradient(90deg,#0a3aa8,#1150d8);
 border-radius:0 0 18px 18px;font-weight:700;font-size:30px;line-height:1.9;text-align:center}
.glass{position:absolute;left:770px;right:44px;top:150px;height:690px;border-radius:22px;
 background:linear-gradient(160deg,rgba(255,255,255,.10),rgba(255,255,255,.04));border:1px solid rgba(160,210,255,.28);
 backdrop-filter:blur(4px)}
.panel{left:810px;right:84px;top:160px;height:670px}
.tagbox{position:absolute;top:34px;left:40px;display:flex;gap:12px;align-items:center;direction:ltr}
.tagbox .tag{font-size:26px}
.tagbox .date{background:rgba(3,8,26,.75);padding:0 18px;border-radius:6px;font-size:28px;line-height:1.7;direction:rtl}
.l3x{position:absolute;left:0;top:0;width:1920px;height:96px;display:flex;align-items:stretch;
 background:linear-gradient(90deg,#0a3aa8,#1150d8 60%,#0d47c9);box-shadow:0 -6px 30px rgba(0,0,0,.45)}
.l3x .lab{background:#e11d2e;font-weight:700;font-size:36px;padding:0 30px;line-height:2.6;white-space:nowrap}
.l3x .txt{flex:1;font-weight:700;font-size:38px;line-height:2.45;padding:0 28px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.l3x .bug{width:96px;display:flex;align-items:center;justify-content:center;background:#071a55}
.l3x .bug img{width:78px;height:78px;border-radius:50%}
"""


def _bare(inner: str, height: int = H, hs: int = 64, bs: int = 38, cs: int = 32) -> str:
    """شفاف صفحہ (اوورلے)"""
    css = CSS
    for k, v in {"n4": _font("noto-nastaliq-urdu-arabic-400-normal.woff2"),
                 "n7": _font("noto-nastaliq-urdu-arabic-700-normal.woff2"),
                 "k7": _font("noto-naskh-arabic-arabic-700-normal.woff2"), "hs": hs, "bs": bs, "cs": cs,
                 "bx": BOX[0], "by": BOX[1], "bw": BOX[2], "bh": BOX[3]}.items():
        css = css.replace(f"@@{k}@@", str(v))
    return (f'<!doctype html><html lang="ur"><meta charset="utf-8"><style>{css}'
            f'html,body{{background:transparent!important;height:{height}px}}</style><body>{inner}</body></html>')


def full_overlay(date: str) -> str:
    """پوری اسکرین اینکر شاٹ کے اوپر: تاریخ کا ٹیگ اور نیچے کی پٹی"""
    return _bare(f'<div class="tagbox"><div class="tag">AI NEWS</div><div class="date">{html.escape(date)}</div></div>'
                 + '<div class="l3"></div>' + _lower())


def l3_html(label: str, text: str) -> str:
    return _bare(f'<div class="l3x"><div class="lab">{html.escape(label)}</div><div class="txt">{html.escape(text)}</div>'
                 f'<div class="bug"><img src="{_logo()}"></div></div>', 96)


def detail_html(who: str, bg: str, headline: str, body: str, source: str, date: str, comment: str = "") -> str:
    n = len(headline) + len(body) + len(comment)
    hs, bs, cs = (58, 36, 31) if n < 300 else (52, 33, 28) if n < 430 else (46, 30, 26)
    name = "🎙️ ورچوئل رپورٹر · آڈیو رپورٹ" if who == "m" else "ورچوئل نیوز کاسٹر"
    inner = (f'<div class="studio" style="background-image:url({bg})"></div><div class="shade"></div>' + _top(date) +
             f'<div class="abox"><div class="nm">{name} · فاروقی اے آئی نیوز</div></div><div class="glass"></div>'
             f'<div class="panel"><div class="kicker">تفصیلات · {html.escape(source)}</div><div class="head">{html.escape(headline)}</div>'
             f'<div class="bar"></div><div class="body">{html.escape(body)}</div>'
             + (f'<div class="cmt"><span>{html.escape(comment)}</span></div>' if comment else "") + '</div>'
             + '<div class="l3"></div>' + _lower())
    return _bare(inner, H, hs, bs, cs).replace("background:transparent!important", "background:#040a1c!important")


BOX_L = (60, 150, 880, 690)                     # دو حصوں والی اسکرین: اینکر (بائیں) اور رپورٹر (دائیں)
BOX_R = (980, 150, 880, 690)

CSS += """
.sbox{position:absolute;border-radius:18px;border:3px solid rgba(0,198,255,.75);box-shadow:0 20px 60px rgba(0,0,0,.6)}
.sbox .nm{position:absolute;bottom:-3px;right:-3px;left:-3px;height:64px;background:linear-gradient(90deg,#0a3aa8,#1150d8);
 border-radius:0 0 18px 18px;font-weight:700;font-size:32px;line-height:2;text-align:center}
.sbox .live{position:absolute;top:16px;left:16px;z-index:2;background:#e11d2e;font-weight:700;font-size:26px;padding:0 16px;border-radius:6px;line-height:1.7}
.pin{position:absolute;z-index:2;right:18px;top:16px;background:rgba(3,8,26,.82);border:1px solid rgba(0,198,255,.6);border-radius:10px;
 padding:2px 16px;font-size:28px;line-height:1.8;display:flex;gap:10px;align-items:center}
.pin svg{width:26px;height:26px}
.mic{position:absolute;z-index:2;left:18px;top:16px;width:58px;height:58px;border-radius:50%;background:#e11d2e;display:flex;align-items:center;justify-content:center}
.mic svg{width:30px;height:30px}
"""
PIN_SVG = '<svg viewBox="0 0 24 24" fill="#ff4d5e"><path d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6a2.5 2.5 0 0 1 0 5.5z"/></svg>'
MIC_SVG = '<svg viewBox="0 0 24 24" fill="#fff"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.9V21h2v-3.1A7 7 0 0 0 19 11z"/></svg>'


def split_icons(city: str) -> str:
    """رپورٹر کی کھڑکی پر مائیک اور شہر کا نشان (تصویر کے اوپر، شفاف)"""
    x, y, w, h = BOX_R
    return _bare(f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
                 f'<div class="mic">{MIC_SVG}</div><div class="pin">{PIN_SVG}{html.escape(city)}</div></div>')


def split_html(bg: str, date: str, reporter: str, city: str) -> str:
    """اینکر اور رپورٹر آمنے سامنے (رپورٹر کی ساکن تصویر، مائیک، نام اور شہر)"""
    def box(b, inner):
        x, y, w, h = b
        return f'<div class="sbox" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">{inner}</div>'
    inner = (f'<div class="studio" style="background-image:url({bg})"></div><div class="shade" style="background:rgba(2,8,30,.72)"></div>'
             + _top(date)
             + box(BOX_L, '<div class="nm">ورچوئل نیوز کاسٹر · اسٹوڈیو</div>')
             + box(BOX_R, f'<div class="nm">ورچوئل رپورٹر: {html.escape(reporter)} · {html.escape(city)}</div>')
             + '<div class="l3"></div>' + _lower())
    return _bare(inner).replace("background:transparent!important", "background:#040a1c!important")


# ---------------- رپورٹر سے تفصیل: اینکر ڈیسک پر، دائیں طرف بڑی اسکرین پر رپورٹ ----------------

RP = (1080, 100, 835, 778)          # نیوز روم کی بڑی اسکرین کی جگہ: x, y, w, h
RP_INSET = (1101, 533, 222, 266)     # رپورٹر کی تصویر (اسکرین کے اندر کارڈ میں)
SHIFT_F = -360                       # خاتون اینکر کو بائیں طرف کھسکانا
_RP: dict = {}
_RP: dict = {}


def _map_svg(city: str, w: int = 470, h: int = 300) -> str:
    """سادہ نقشہ (اپنا بنایا ہوا، کسی کمپنی کا نہیں): سڑکیں، دریا اور شہر کا نشان"""
    import random
    r = random.Random(city)
    roads = "".join(f'<path d="M{r.randint(-40, w)} {r.randint(-20, h)} Q{r.randint(0, w)} {r.randint(0, h)} '
                    f'{r.randint(0, w + 40)} {r.randint(0, h + 20)}" stroke="#f6d38a" stroke-width="{r.choice((3, 4, 6))}" fill="none"/>'
                    for _ in range(9))
    minor = "".join(f'<path d="M{r.randint(0, w)} 0 L{r.randint(0, w)} {h}" stroke="#ffffff" stroke-width="2" opacity=".8"/>'
                    for _ in range(7))
    parks = "".join(f'<rect x="{r.randint(0, w - 60)}" y="{r.randint(0, h - 40)}" width="{r.randint(30, 70)}" height="{r.randint(20, 45)}" '
                    f'rx="8" fill="#cfe8c4"/>' for _ in range(4))
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="{w}" height="{h}" fill="#f2efe6"/>{parks}{minor}{roads}'
            f'<path d="M0 {h * .78} C{w * .3} {h * .62} {w * .55} {h * .95} {w} {h * .7}" stroke="#a9cdea" stroke-width="16" fill="none"/>'
            f'<circle cx="{w / 2}" cy="{h / 2 + 22}" r="26" fill="rgba(225,29,46,.18)"/>'
            f'<path transform="translate({w / 2 - 22},{h / 2 - 50}) scale(1.85)" d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6a2.5 2.5 0 0 1 0 5.5z" fill="#0b2a6f"/>'
            f'</svg>')


CSS += """
.rp{position:absolute;border-radius:16px;overflow:hidden;background:#06123a;border:4px solid #1c2c5a;
 box-shadow:0 0 0 2px rgba(0,198,255,.45),0 30px 70px rgba(0,0,0,.6)}
.rp .hd{height:96px;background:linear-gradient(90deg,#0a2a7a,#0d3fb0);display:flex;align-items:center;padding:0 26px;
 font-weight:700;font-size:40px;line-height:2.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-bottom:4px solid #00c6ff}
.rp .vis{position:absolute;left:0;right:0;top:100px;bottom:0;background-size:cover;background-position:center}
.rp .vis.g{background:radial-gradient(600px 300px at 50% 35%,#1f5be0,#0a1f5c 65%,#040c2a)}
.rp .vis .big{position:absolute;left:0;right:0;top:70px;text-align:center;font-weight:700;font-size:54px;line-height:1.8;color:#fff;
 text-shadow:0 6px 30px rgba(0,0,0,.7);padding:0 40px}
.rp .vis .src{position:absolute;left:0;right:0;top:250px;text-align:center}
.rp .vis .src span{font-family:Naskh;font-weight:700;font-size:30px;background:rgba(0,198,255,.18);border:1px solid rgba(0,198,255,.6);
 padding:4px 22px;border-radius:30px;color:#bfefff;direction:ltr}
.card2{position:absolute;left:14px;right:14px;bottom:14px;height:330px;border-radius:12px;background:#0a1c52;border:3px solid #e9eef8;
 overflow:hidden}
.card2 .t{position:absolute;right:0;left:226px;top:0;height:62px;background:#0b2a6f;font-weight:700;font-size:30px;line-height:2.1;padding:0 18px;
 white-space:nowrap;overflow:hidden}
.card2 .mp{position:absolute;right:8px;left:226px;top:66px;bottom:8px;border-radius:8px;overflow:hidden}
.card2 .nm{position:absolute;left:0;width:222px;bottom:0;height:58px;background:#e11d2e;font-weight:700;font-size:28px;line-height:2.1;text-align:center}
.card2 .on{position:absolute;left:10px;top:10px;z-index:3;background:rgba(3,8,26,.8);border:1px solid #00c6ff;border-radius:8px;
 font-size:24px;line-height:1.7;padding:0 12px}
"""


def report_html(headline: str, src: str, reporter: str, city: str, img: str = "", reporter_on: bool = False) -> str:
    """دائیں طرف کی بڑی اسکرین (شفاف صفحہ): عنوان، خبر کی تصویر، اندر رپورٹر کی تصویر + نقشہ"""
    x, y, w, h = RP
    vis = (f'<div class="vis" style="background-image:url({img})"></div>' if img else
           f'<div class="vis g"><div class="big">{html.escape(headline)}</div><div class="src"><span>{html.escape(src)}</span></div></div>')
    inner = (f'<div class="rp" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
             f'<div class="hd">خصوصی رپورٹ: {html.escape(headline)}</div>{vis}'
             f'<div class="card2"><div class="t">📍 {html.escape(city)} · ورچوئل رپورٹر {html.escape(reporter)}</div>'
             f'<div class="mp">{_map_svg(city)}</div>'
             + ('<div class="on">🎙️ بول رہے ہیں</div>' if reporter_on else "")
             + f'<div class="nm">ورچوئل رپورٹر</div></div></div>'
             + '<div class="l3"></div>' + _lower())
    return _bare(inner)


# ---- رپورٹ کا منظر (دوسرا نیوز روم: اینکر کھڑی، بڑی خمدار اسکرین پر رپورٹ) ----
SCENE = PHOTOS / "report_scene.jpg"
SC_CROP = (0, 24, 1280, 744)          # دائیں طرف کی عمودی پٹی کٹ جاتی ہے؛ ×1.5 = 1920×1080
RP2 = (1150, 190, 670, 450)           # بڑی اسکرین پر ہماری رپورٹ
RP2_REP = (1579, 205, 226, 272)       # اسکرین کے اندر رپورٹر کی تصویر

CSS += """
.r2{position:absolute;border-radius:14px;overflow:hidden;background:#06123a;border:3px solid rgba(190,230,255,.85);
 box-shadow:0 0 30px rgba(0,198,255,.45)}
.r2 .vis{position:absolute;inset:0;background-size:cover;background-position:center}
.r2 .vis.g{background:radial-gradient(500px 300px at 35% 40%,#1f5be0,#0a1f5c 65%,#040c2a)}
.r2 .vis .big{position:absolute;left:20px;right:250px;top:170px;text-align:center;font-weight:700;font-size:38px;line-height:1.8;
 text-shadow:0 6px 30px rgba(0,0,0,.7)}
.r2 .cap{position:absolute;left:0;right:0;bottom:0;height:72px;background:linear-gradient(90deg,#0a2a7a,#0d3fb0);border-top:3px solid #00c6ff;
 font-weight:700;font-size:30px;line-height:2.3;padding:0 22px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.r2 .map{position:absolute;left:12px;top:12px;width:230px;height:150px;border-radius:8px;overflow:hidden;border:2px solid #e9eef8}
.r2 .map .c{position:absolute;left:0;right:0;bottom:0;background:rgba(11,42,111,.92);font-weight:700;font-size:22px;line-height:1.7;text-align:center}
.r2 .nm{position:absolute;right:12px;top:284px;width:226px;height:44px;background:#e11d2e;font-weight:700;font-size:23px;line-height:1.9;text-align:center}
.r2 .on{position:absolute;right:12px;top:334px;width:226px;text-align:center;background:rgba(3,8,26,.85);border:1px solid #00c6ff;
 border-radius:8px;font-size:22px;line-height:1.7}
"""


def report2_html(headline: str, src: str, reporter: str, city: str, img: str = "", reporter_on: bool = False) -> str:
    """دوسرے نیوز روم کی بڑی اسکرین (شفاف صفحہ): خبر کی تصویر، نقشہ، رپورٹر، عنوان"""
    x, y, w, h = RP2
    vis = (f'<div class="vis" style="background-image:url({img})"></div>' if img else
           f'<div class="vis g"><div class="big">{html.escape(headline)}</div></div>')
    sign = ('<div style="position:absolute;left:404px;top:96px;width:214px;height:112px;border-radius:8px;background:#1a1f2b;'
            'border:3px solid #2b3245;display:flex;align-items:center;justify-content:center">'
            '<div style="font-family:Naskh;font-weight:700;font-size:32px;color:#ff4d5e;text-shadow:0 0 14px rgba(255,60,80,.8);direction:ltr">AI NEWS</div></div>')
    inner = (sign + f'<div class="r2" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">{vis}'
             f'<div class="map">{_map_svg(city, 230, 150)}<div class="c">📍 {html.escape(city)}</div></div>'
             f'<div class="nm">ورچوئل رپورٹر {html.escape(reporter)}</div>'
             + ('<div class="on">🎙️ بول رہے ہیں</div>' if reporter_on else "")
             + f'<div class="cap">خصوصی رپورٹ: {html.escape(headline)}</div></div>'
             + '<div class="l3"></div>' + _lower())
    return _bare(inner)


def report_canvas():
    from PIL import Image
    return Image.open(SCENE).convert("RGB").crop(SC_CROP).resize((W, H), Image.LANCZOS).convert("RGBA")


def story_image(prompt: str, out: Path) -> Path | None:
    """مین اسٹوری کی تصویر Gemini سے (اگر مفت کوٹہ ہو)؛ نہ بنے تو None — پھر گرافک"""
    import json as _j, requests
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key or MOCK or not prompt:
        return None
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                         headers={"x-goog-api-key": key}, timeout=30).json()
        models = [m["name"].split("/")[-1] for m in r.get("models", [])
                  if "image" in m["name"] and "generateContent" in m.get("supportedGenerationMethods", [])]
    except Exception:
        models = []
    for m in sorted(models, reverse=True)[:3]:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                              headers={"x-goog-api-key": key}, timeout=180, json={
                                  "contents": [{"parts": [{"text": prompt + ". Photorealistic editorial news image, 16:9, "
                                                           "no text, no logos, no real people's faces."}]}],
                                  "generationConfig": {"responseModalities": ["IMAGE"]}})
            if not r.ok:
                print(f"تصویر {m}: HTTP {r.status_code}")
                continue
            for part in r.json()["candidates"][0]["content"]["parts"]:
                if "inlineData" in part:
                    out.write_bytes(base64.b64decode(part["inlineData"]["data"]))
                    print(f"تصویر بن گئی: {m}")
                    return out
        except (requests.RequestException, KeyError, IndexError, _j.JSONDecodeError) as e:
            print(f"تصویر {m}: {e}")
    return None


def mouth_track(audio: Path, secs: float) -> list[int]:
    """آواز کی بلندی سے ہر فریم پر منہ: 0 بند، 1 تھوڑا، 2 کھلا"""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32)
    hop = 16000 // FPS
    n = int(secs * FPS)
    rms = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2)) if i * hop < len(x) else 0.0 for i in range(n)])
    hi = np.percentile(rms[rms > 0], 90) if (rms > 0).any() else 1.0
    lv = rms / max(hi, 1e-6)
    m = [2 if v > 0.55 else 1 if v > 0.2 else 0 for v in lv]
    return [m[i] if i % 2 == 0 or i == 0 else m[i - 1] for i in range(n)]


def _frames(seg: dict, states: dict, audio: Path, secs: float, tmp: Path, tag: str) -> Path:
    """ایک حصے کے فریم: اینکر (منہ کی حرکت) + اسکرین → concat فہرست"""
    from PIL import Image, ImageDraw
    who = seg["who"]
    n = int(secs * FPS)
    mouth = [0] * n                     # ہونٹ نہیں ہلتے: خاتون نقاب میں، مرد رپورٹر کی ساکن تصویر
    cache = {}

    def comp(page: int, mo: int) -> Path:
        key = (page, mo)
        if key in cache:
            return cache[key]
        anchor = Image.open(states[(who, mo)]).convert("RGBA")
        if seg["kind"] == "full":
            im = anchor
            im.alpha_composite(Image.open(seg["overlay"]).convert("RGBA"))
        elif seg["kind"] == "report":
            im = seg["canvas"].copy()
            im.alpha_composite(Image.open(seg["pages"][0]).convert("RGBA"))
            x, y, w, h = RP2_REP if SCENE.exists() else RP_INSET
            rp_f = PHOTOS / "reporter.jpg"
            if rp_f.exists():
                crop = Image.open(rp_f).convert("RGB").resize((w, h), Image.LANCZOS)
            else:
                rep = Image.open(states[("m", 0)]).convert("RGBA")
                cx = _sx("m")
                crop = rep.crop((int(cx - 110), 50, int(cx + 110), 50 + 265)).resize((w, h))
            im.paste(crop, (x, y))
        elif seg["kind"] == "split":
            im = Image.open(seg["pages"][0]).convert("RGBA")
            for w_, (x, y, w, h) in (("f", BOX_L), ("m", BOX_R)):
                an = Image.open(states[(w_, 0)]).convert("RGBA")
                cx = _sx(w_)
                crop = an.crop((int(cx - (w - 6) / 2), 30, int(cx + (w - 6) / 2), 30 + h - 67))
                mask = Image.new("L", crop.size, 0)
                ImageDraw.Draw(mask).rounded_rectangle((0, 0, crop.width - 1, crop.height + 20), 15, fill=255)
                im.paste(crop, (x + 3, y + 3), mask)
                if (seg["speaker"] == w_) is False:      # جو نہیں بول رہا وہ ہلکا مدھم
                    dim = Image.new("RGBA", (w - 6, h - 67), (0, 0, 0, 70))
                    im.alpha_composite(dim, (x + 3, y + 3))
            im.alpha_composite(Image.open(seg["icons"]).convert("RGBA"))
        else:
            im = Image.open(seg["pages"][page]).convert("RGBA")
            x, y, w, h = BOX
            cx = _sx(who)
            crop = anchor.crop((int(cx - (w - 6) / 2), 40, int(cx + (w - 6) / 2), 40 + h - 61))
            mask = Image.new("L", crop.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, crop.width - 1, crop.height + 20), 15, fill=255)
            im.paste(crop, (x + 3, y + 3), mask)
        f = tmp / f"{tag}_{page}_{mo}.png"
        im.convert("RGB").save(f)
        cache[key] = f
        return f

    bounds = seg.get("bounds") or [0.0]
    seq = []
    for i in range(n):
        t = i / FPS
        page = max(k for k, b in enumerate(bounds) if b <= t) if seg["kind"] == "detail" else 0
        seq.append(comp(page, mouth[i]))
    lines, i = [], 0
    while i < n:
        j = i
        while j < n and seq[j] == seq[i]:
            j += 1
        lines += [f"file '{seq[i].name}'", f"duration {(j - i) / FPS:.4f}"]
        i = j
    lines.append(f"file '{seq[-1].name}'")
    lst = tmp / f"{tag}.txt"
    lst.write_text("\n".join(lines) + "\n")
    return lst


def _split(text_parts: list[str], total: float) -> list[float]:
    """ایک آواز میں کئی سرخیاں: ہر حصے کا آغاز الفاظ کی لمبائی کے تناسب سے"""
    w = [max(1, len(x)) for x in text_parts]
    s, out = 0.0, []
    for x in w:
        out.append(total * s / sum(w))
        s += x
    return out



def make_card(tmp: Path, kind: str, date: str) -> Path:
    """انٹرو / آؤٹرو: حرکت کرتا لوگو + کورس کی آوازیں (کوئی ساز یا موسیقی نہیں) + اینکرز کی آواز میں چینل کا نام"""
    import ident
    fonts = (f"@font-face{{font-family:Nast;font-weight:400;src:url({_font('noto-nastaliq-urdu-arabic-400-normal.woff2')})}}"
             f"@font-face{{font-family:Nast;font-weight:700;src:url({_font('noto-nastaliq-urdu-arabic-700-normal.woff2')})}}"
             f"@font-face{{font-family:Naskh;font-weight:700;src:url({_font('noto-naskh-arabic-arabic-700-normal.woff2')})}}")
    if kind == "intro":
        dur, title, sub = 6.5, "فاروقی اے آئی نیوز", "باوثوق · باخبر · سب سے آگے"
        lines = [("فاروقی، اے آئی نیوز۔", 0, 1.2), ("باوثوق، باخبر، سب سے آگے!", 1, 3.3)]
        notes, vowel = (146.83, 220.0, 293.66, 369.99), "aa"
    else:
        dur, title, sub = 6.0, "فاروقی اے آئی نیوز", "ہر لمحہ، باخبر · سبسکرائب کریں"
        lines = [("فاروقی اے آئی نیوز۔ ہر لمحہ، باخبر!", 0, 1.4)]
        notes, vowel = (130.81, 196.0, 261.63, 329.63), "oo"
    bg, _, tx = ident.card_html(_logo(), fonts, title, sub, date if kind == "intro" else "")
    bgp = shoot([bg], tmp, tag=f"{kind}bg")[0]
    txp = shoot([tx], tmp, transparent=True, tag=f"{kind}tx")[0]
    sw = ident.sweep_png(tmp / f"{kind}_sweep.png")
    logo = ROOT / "assets" / "logo.png"
    ch = ident.save_wav(ident.choir(dur, notes, vowel), tmp / f"{kind}_choir.wav")
    ins, mix = ["-i", ch], ["[1:a]volume=0.9[c]"]
    for j, (txt, role, at) in enumerate(lines):
        v = speak(txt, tmp / f"{kind}_v{j}.mp3", role)
        ins += ["-i", v]
        ms = int(at * 1000)
        mix.append(f"[{2 + j}:a]aresample=44100,aformat=channel_layouts=stereo,volume=1.6,"
                   f"aecho=0.8:0.55:90|180|300:0.32|0.2|0.1,adelay={ms}|{ms}[v{j}]")
    lab = "".join(f"[v{j}]" for j in range(len(lines)))
    mix.append(f"[c]{lab}amix=inputs={1 + len(lines)}:normalize=0:duration=first,atrim=0:{dur},"
               f"afade=t=out:st={dur - 0.8}:d=0.8[a]")
    n = 2 + len(lines)
    fc = (f"[0:v]fps={FPS},format=rgba[b];"
          f"[{n}:v]format=rgba,scale=w='trunc(560*(0.55+0.45*min(1,t/1.3))/2)*2':h=-2:eval=frame,"
          f"fade=in:st=0.2:d=0.7:alpha=1[lg];"
          f"[b][lg]overlay=x='(W-w)/2':y='420-h/2'[b1];"
          f"[{n + 1}:v]format=rgba[sw];[b1][sw]overlay=x='-700+(t-1.1)*1700':y=0:enable='between(t,1.1,2.6)'[b2];"
          f"[{n + 2}:v]format=rgba,fade=in:st=1.5:d=0.7:alpha=1[tx];[b2][tx]overlay=0:0,"
          f"fade=in:st=0:d=0.4,format=yuv420p[v]")
    outp = tmp / f"{kind}.mp4"
    _ff("-loop", "1", "-framerate", FPS, "-t", f"{dur}", "-i", bgp, *ins,
        "-loop", "1", "-framerate", FPS, "-t", f"{dur}", "-i", logo,
        "-loop", "1", "-framerate", FPS, "-t", f"{dur}", "-i", sw,
        "-loop", "1", "-framerate", FPS, "-t", f"{dur}", "-i", txp,
        "-filter_complex", ";".join(mix) + ";" + fc, "-map", "[v]", "-map", "[a]", "-t", f"{dur}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-r", FPS,
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", outp)
    return outp


def render(out: dict, items: list[dict], date: str, dest: Path) -> Path:
    picks = [p for p in out.get("picks", [])[:5] if 1 <= int(p.get("n", 0)) <= len(items)]
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        intro = out.get("intro") or "السلام علیکم۔ فاروقی اے آئی نیوز میں خوش آمدید۔ آج کی تازہ ترین خبریں۔"
        first = intro.find("السلام علیکم")                     # سلام صرف ایک بار
        if first >= 0:
            intro = intro[:first + 12] + intro[first + 12:].replace("السلام علیکم", "").replace("۔۔", "۔")
        hl_say = [p.get("headline_say") or p["headline"] for p in picks]
        reporter = os.environ.get("NEWS_REPORTER", "عمر فاروق")

        def story_say(p, extra=""):
            base = p.get("say") or (f"{p['headline']}۔ {p['body']}" + (f" {p['comment']}" if p.get("comment") else ""))
            return base + (f" {extra}" if extra else "")
        # ترتیب: خاتون اینکر — سلام → سرخیاں → مین اسٹوری + تجزیہ → رپورٹر سے سوال و جواب → باقی خبریں → اختتام
        segs_def = [{"kind": "full", "who": "f", "say": intro, "l3": [("خوش آمدید", "فاروقی اے آئی نیوز · آج کی اہم خبریں")]},
                    {"kind": "full", "who": "f", "say": " ".join(hl_say), "parts": hl_say,
                     "l3": [("سرخیاں", p["headline"]) for p in picks]}]
        for k, p in enumerate(picks):
            src = items[int(p["n"]) - 1]["source"]
            main = k == 0 and p.get("qa")
            segs_def.append({"kind": "detail", "who": "f", "say": story_say(p, p.get("commentary", "") if main else ""),
                             "pick": p, "src": src, "chapter": p["headline"],
                             "note": (p.get("commentary") or p.get("comment", "")) if main else p.get("comment", ""),
                             "l3": [("مین اسٹوری" if main else "اہم خبر", p["headline"])]})
            if main:
                city = p.get("reporter_city") or "سان فرانسسکو"
                lab = ("رپورٹر سے رابطہ", f"ورچوئل رپورٹر {reporter} · {city}")
                intro_r = p.get("reporter_intro") or f"اس خبر کی مزید تفصیل کے لیے ہمارے ساتھ موجود ہیں نمائندہ {reporter}۔"
                segs_def.append({"kind": "report", "who": "f", "speaker": "f", "say": intro_r, "city": city, "l3": [lab],
                                 "headline": p["headline"], "src": src})
                for qa in p["qa"][:2]:
                    segs_def.append({"kind": "report", "who": "f", "speaker": "f", "say": qa["q"], "city": city, "l3": [lab],
                                     "headline": p["headline"], "src": src})
                    segs_def.append({"kind": "report", "who": "m", "speaker": "m", "say": qa["a"], "city": city, "l3": [lab],
                                     "headline": p["headline"], "src": src})
        segs_def.append({"kind": "full", "who": "f",
                         "say": out.get("outro") or "ناظرین و سامعین، یہ تھیں آج کی اہم خبریں۔ فاروقی اے آئی نیوز کو سبسکرائب کیجیے۔ اللہ حافظ۔",
                         "l3": [("شکریہ", "فاروقی اے آئی نیوز سبسکرائب کریں · ہر لمحہ، باخبر")]})

        if _cut("m").exists() and _cut("f").exists():
            build_set(tmp)
        states = anchor_states(tmp)
        overlay = shoot([full_overlay(date)], tmp, transparent=True, tag="ov")[0]
        bgs = {w: _studio_bg(w) for w in ("m", "f")}
        tick = ticker_png("   ●   ".join(p["headline"] for p in picks) + "   ●   ", tmp / "ticker.png")
        segs = []
        for k, sd in enumerate(segs_def):
            if sd.get("parts"):
                # ہر سرخی سے پہلے مختصر ووکل (کورس کی "آآ" — موسیقی نہیں)، پھر سرخی؛ آغاز کے وقت بالکل درست
                import ident
                sting = ident.save_wav(ident.choir(1.0, (220.0, 277.18, 329.63, 440.0), "aa", attack=0.12,
                                                   release=0.55, seed=k), tmp / f"sting{k}.wav")
                pieces, sd["starts"], t_ = [], [], 0.0
                for j, txt in enumerate(sd["parts"]):
                    v = speak(txt, tmp / f"v{k}_{j}.mp3", 0 if sd["who"] == "m" else 1)
                    sd["starts"].append(t_)
                    pieces += [sting, v]
                    t_ += _dur(sting) + _dur(v) + 0.35
                lst_a = tmp / f"hl{k}.txt"
                a = tmp / f"v{k}.wav"
                norm = []
                for j, f_ in enumerate(pieces):
                    g = tmp / f"n{k}_{j}.wav"
                    _ff("-i", f_, "-af", "aresample=44100,aformat=channel_layouts=stereo,apad=pad_dur=" +
                        ("0.35" if j % 2 else "0"), "-ar", "44100", "-ac", "2", g)
                    norm.append(g)
                lst_a.write_text("".join(f"file '{g.name}'\n" for g in norm))
                _ff("-f", "concat", "-safe", "0", "-i", lst_a, "-c:a", "pcm_s16le", a)
            else:
                a = speak(sd["say"], tmp / f"v{k}.mp3", 0 if sd["who"] == "m" else 1)
            d = _dur(a) + 0.7
            if sd["kind"] == "full":
                sd["overlay"] = overlay
            elif sd["kind"] == "report":
                if "canvas" not in _RP:
                    from PIL import Image
                    _RP["canvas"] = report_canvas() if SCENE.exists() else Image.open(states[("f", 0)]).convert("RGBA")
                    simg = story_image(out.get("thumbnail_prompt", ""), tmp / "story.png")
                    _RP["story_img"] = ("data:image/png;base64," + base64.b64encode(simg.read_bytes()).decode()) if simg else ""
                sd["canvas"] = _RP["canvas"]
                rh = report2_html if SCENE.exists() else report_html
                sd["pages"] = shoot([rh(sd["headline"], sd["src"], reporter, sd["city"], _RP["story_img"],
                                        sd["speaker"] == "m")], tmp, transparent=True, tag=f"d{k}_")
            elif sd["kind"] == "split":
                sd["pages"] = shoot([split_html(bgs["f"], date, reporter, sd["city"])], tmp, tag=f"d{k}_")
                sd["icons"] = shoot([split_icons(sd["city"])], tmp, transparent=True, tag=f"i{k}_")[0]
            else:
                p = sd["pick"]
                sd["pages"] = shoot([detail_html(sd["who"], bgs[sd["who"]], p["headline"], p["body"], sd["src"], date,
                                                 sd.get("note", ""))], tmp, tag=f"d{k}_")
            starts = sd.get("starts") or [0.0]
            l3s = shoot([l3_html(a_, b_) for a_, b_ in sd["l3"]], tmp, transparent=True, height=96, tag=f"l{k}_")
            # مرد اینکر: ہونٹ آواز کے مطابق (MuseTalk AI)؛ نہ چلے تو پرانا طریقہ
            patch_in, fc = [], f"[0:v]fps={FPS},split=3[z0][o0][o1];"
            if sd["who"] == "m" and os.environ.get("LIPSYNC") == "1" and _lipsync_ok():
                try:
                    import lipsync
                    from PIL import Image
                    pv, px, py = lipsync.animate(Image.open(states[("m", 0)]).convert("RGB"), face_box("m"), a,
                                                 tmp / f"patch{k}.mp4")
                    if sd["kind"] == "detail":
                        bx, by, bw, _ = BOX
                        px, py = px + bx + 3 - int(_sx("m") - (bw - 6) / 2), py + by + 3 - 40
                    sd["patch"] = pv
                    patch_in = ["-i", pv]
                    fc = (f"[0:v]fps={FPS}[b0];[b0][{3 + len(sd['l3'])}:v]overlay={px}:{py}:eof_action=pass,"
                          f"split=3[z0][o0][o1];")
                    VOICE_USED.add("lipsync: MuseTalk")
                except Exception as e:
                    print(f"lipsync ناکام ({e}) — پرانا طریقہ")
            lst = _frames(sd, states, a, d, tmp, f"k{k}")
            # ان پٹ: 0 فریم، 1 ٹکر، 2 آواز، 3.. سرخی کی پٹیاں، آخر میں ہونٹوں کی ویڈیو
            if sd["kind"] == "full":      # کیمرہ آہستہ آہستہ قریب (نیوز اسٹوڈیو کی طرح)
                fc += (f"[z0]crop={W}:{H - 200}:0:0,scale=w='trunc({W}*(1+0.045*t/{d:.2f})/2)*2':h=-2:eval=frame,"
                       f"crop={W}:{H - 200}:'(iw-{W})*{_sx(sd['who']) / W:.2f}':'(ih-{H - 200})*0.35',setsar=1[top];")
            else:
                fc += f"[z0]crop={W}:{H - 200}:0:0[top];"
            fc += (f"[o0]crop={W}:200:0:{H - 200}[bars];"
                   f"[o1]crop=240:104:{W - 240}:{H - 104}[lab];[1:v]format=rgba[tk];"
                   f"[bars][tk]overlay=x='mod(t*130+{k * 400}+w*0.55,w+{W - 240})-w':y=99:shortest=0[b2];"
                   f"[b2][lab]overlay={W - 240}:96[b3];[top][b3]vstack[v0]")
            last = "v0"
            ends = starts[1:] + [d + 1]
            for j, (s0, e0) in enumerate(zip(starts, ends)):
                s1 = s0 + 0.25
                fc += (f";[v{j}][{3 + j}:v]overlay=x='if(lt(t,{s1:.2f}+0.4),{W}*(1-(t-{s1:.2f})/0.4),0)':y={H - 200}:"
                       f"enable='between(t,{s1:.2f},{e0:.2f})'[v{j + 1}]")
                last = f"v{j + 1}"
            l3in = []
            for f_ in l3s:
                l3in += ["-loop", "1", "-framerate", FPS, "-t", f"{d:.2f}", "-i", f_]
            seg = tmp / f"s{k}.mp4"
            _ff("-f", "concat", "-safe", "0", "-i", lst,
                "-loop", "1", "-framerate", FPS, "-t", f"{d:.2f}", "-i", tick, "-i", a, *l3in, *patch_in,
                "-filter_complex", fc + ";[2:a]apad,atrim=0:" + f"{d:.2f}[a]",
                "-map", f"[{last}]", "-map", "[a]", "-t", f"{d:.2f}", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "23", "-pix_fmt", "yuv420p", "-r", FPS, "-c:a", "aac", "-b:a", "128k", "-ar", "44100", seg)
            segs.append(seg)
        # شروع میں انٹرو اور آخر میں آؤٹرو (کورس کی آوازیں، موسیقی نہیں)
        segs = [make_card(tmp, "intro", date)] + segs + [make_card(tmp, "outro", date)]
        segs_def = [{"kind": "full"}] + segs_def + [{"kind": "full"}]
        T = 0.5
        durs = [_dur(x) for x in segs]
        start = [sum(durs[:k]) - k * T for k in range(len(segs))]
        out["_chapters"] = ([(0, "آغاز اور آج کی سرخیاں")] +
                            [(start[i], sd_["chapter"]) for i, sd_ in enumerate(segs_def) if sd_.get("chapter")])
        out["_voice"] = ", ".join(sorted(VOICE_USED))
        args, vf, af = [], [], []
        for x in segs:
            args += ["-i", x]
        vlast, alast, off = "0:v", "0:a", 0.0
        for k in range(1, len(segs)):
            off += durs[k - 1] - T
            cur, prev = segs_def[k]["kind"], segs_def[k - 1]["kind"]
            kind = "fade" if cur == "full" or (cur in ("split", "report") and prev == cur) else "slideleft"
            vf.append(f"[{vlast}][{k}:v]xfade=transition={kind}:duration={T}:offset={off:.2f}[v{k}]")
            af.append(f"[{alast}][{k}:a]acrossfade=d={T}[a{k}]")
            vlast, alast = f"v{k}", f"a{k}"
        _ff(*args, "-filter_complex", ";".join(vf + af), "-map", f"[{vlast}]", "-map", f"[{alast}]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p", "-r", FPS,
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", dest)
        if dest.stat().st_size > 48 * 1024 * 1024:
            small = dest.with_name(dest.stem + "_720.mp4")
            _ff("-i", dest, "-vf", "scale=-2:720", "-c:v", "libx264", "-crf", "28", "-preset", "veryfast",
                "-c:a", "copy", "-movflags", "+faststart", small)
            small.replace(dest)
    return dest
