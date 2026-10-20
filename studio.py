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
FACE = {"m": (850, 203), "f": (705, 150)}      # اصل تصویر میں منہ/چہرے کا مرکز
BOX = (50, 140, 700, 720)                      # تفصیل والی اسکرین پر اینکر کی کھڑکی: x, y, w, h


def _anchor_full(who: str, d: float = 0.0):
    """پوری اسکرین کی اینکر تصویر؛ مرد کے لیے d = منہ کتنا کھلا (پکسل)"""
    import numpy as np
    from PIL import Image
    im = Image.open(PHOTOS / ("male.jpg" if who == "m" else "female.jpg")).convert("RGB")
    im = im.resize((round(im.width * PS), H), Image.LANCZOS).crop((PX, 0, PX + W, H))
    if who != "m" or d <= 0:
        return im
    cx, my = FACE["m"][0] * PS - PX, FACE["m"][1] * PS
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


def anchor_states(tmp: Path) -> dict:
    out = {}
    for who in ("m", "f"):
        for mo, d in enumerate(MOUTHS if who == "m" else (0.0,)):
            f = tmp / f"anchor_{who}{mo}.png"
            _anchor_full(who, d).save(f)
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
    name = "نیوز اینکر" if who == "m" else "نیوز اینکر"
    inner = (f'<div class="studio" style="background-image:url({bg})"></div><div class="shade"></div>' + _top(date) +
             f'<div class="abox"><div class="nm">{name} · فاروقی اے آئی نیوز</div></div><div class="glass"></div>'
             f'<div class="panel"><div class="kicker">تفصیلات · {html.escape(source)}</div><div class="head">{html.escape(headline)}</div>'
             f'<div class="bar"></div><div class="body">{html.escape(body)}</div>'
             + (f'<div class="cmt"><span>{html.escape(comment)}</span></div>' if comment else "") + '</div>'
             + '<div class="l3"></div>' + _lower())
    return _bare(inner, H, hs, bs, cs).replace("background:transparent!important", "background:#040a1c!important")


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
    mouth = mouth_track(audio, secs) if who == "m" else [0] * n
    cache = {}

    def comp(page: int, mo: int) -> Path:
        key = (page, mo)
        if key in cache:
            return cache[key]
        anchor = Image.open(states[(who, mo)]).convert("RGBA")
        if seg["kind"] == "full":
            im = anchor
            im.alpha_composite(Image.open(seg["overlay"]).convert("RGBA"))
        else:
            im = Image.open(seg["pages"][page]).convert("RGBA")
            x, y, w, h = BOX
            cx = FACE[who][0] * PS - PX
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



def render(out: dict, items: list[dict], date: str, dest: Path) -> Path:
    picks = [p for p in out.get("picks", [])[:6] if 1 <= int(p.get("n", 0)) <= len(items)]
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        intro = out.get("intro") or "السلام علیکم۔ فاروقی اے آئی نیوز میں خوش آمدید۔ آج کی تازہ ترین خبریں۔"
        first = intro.find("السلام علیکم")                     # سلام صرف ایک بار
        if first >= 0:
            intro = intro[:first + 12] + intro[first + 12:].replace("السلام علیکم", "").replace("۔۔", "۔")
        hl_say = [p.get("headline_say") or p["headline"] for p in picks] + ["اور اب، ان خبروں کی تفصیل۔"]
        # حصے: آغاز (مرد) → سرخیاں (خاتون) → ہر خبر کی تفصیل (باری باری) → اختتام (مرد)
        segs_def = [{"kind": "full", "who": "m", "say": intro, "l3": [("خوش آمدید", "فاروقی اے آئی نیوز · آج کی اہم خبریں")]},
                    {"kind": "full", "who": "f", "say": " ".join(hl_say), "parts": hl_say,
                     "l3": [("سرخیاں", p["headline"]) for p in picks] + [("تفصیلات", "اب ان خبروں کی تفصیل")]}]
        for k, p in enumerate(picks):
            src = items[int(p["n"]) - 1]["source"]
            who = "m" if k % 2 == 0 else "f"
            say = p.get("say") or (f"{p['headline']}۔ {p['body']}" + (f" {p['comment']}" if p.get("comment") else ""))
            segs_def.append({"kind": "detail", "who": who, "say": say, "pick": p, "src": src,
                             "l3": [("اہم خبر", p["headline"])]})
        segs_def.append({"kind": "full", "who": "m",
                         "say": out.get("outro") or "یہ تھیں آج کی اہم خبریں۔ مزید خبروں کے لیے چینل کو فالو کریں۔ اللہ حافظ۔",
                         "l3": [("شکریہ", "روزانہ اے آئی کی تازہ خبروں کے لیے چینل سبسکرائب کریں")]})

        states = anchor_states(tmp)
        overlay = shoot([full_overlay(date)], tmp, transparent=True, tag="ov")[0]
        bgs = {w: _studio_bg(w) for w in ("m", "f")}
        tick = ticker_png("   ●   ".join(p["headline"] for p in picks) + "   ●   ", tmp / "ticker.png")
        segs = []
        for k, sd in enumerate(segs_def):
            a = speak(sd["say"], tmp / f"v{k}.mp3", 0 if sd["who"] == "m" else 1)
            d = _dur(a) + 0.7
            if sd["kind"] == "full":
                sd["overlay"] = overlay
            else:
                p = sd["pick"]
                sd["pages"] = shoot([detail_html(sd["who"], bgs[sd["who"]], p["headline"], p["body"], sd["src"], date,
                                                 p.get("comment", ""))], tmp, tag=f"d{k}_")
            starts = _split(sd["parts"], d - 0.7) if sd.get("parts") else [0.0]
            l3s = shoot([l3_html(a_, b_) for a_, b_ in sd["l3"]], tmp, transparent=True, height=96, tag=f"l{k}_")
            lst = _frames(sd, states, a, d, tmp, f"k{k}")
            # ان پٹ: 0 فریم، 1 ٹکر، 2 آواز، 3.. سرخی کی پٹیاں
            fc = f"[0:v]fps={FPS},split=3[z0][o0][o1];"
            if sd["kind"] == "full":      # کیمرہ آہستہ آہستہ قریب (نیوز اسٹوڈیو کی طرح)
                fc += (f"[z0]crop={W}:{H - 200}:0:0,scale=w='trunc({W}*(1+0.045*t/{d:.2f})/2)*2':h=-2:eval=frame,"
                       f"crop={W}:{H - 200}:'(iw-{W})*{0.62 if sd['who'] == 'm' else 0.5}':'(ih-{H - 200})*0.35',setsar=1[top];")
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
                "-loop", "1", "-framerate", FPS, "-t", f"{d:.2f}", "-i", tick, "-i", a, *l3in,
                "-filter_complex", fc + ";[2:a]apad,atrim=0:" + f"{d:.2f}[a]",
                "-map", f"[{last}]", "-map", "[a]", "-t", f"{d:.2f}", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "23", "-pix_fmt", "yuv420p", "-r", FPS, "-c:a", "aac", "-b:a", "128k", "-ar", "44100", seg)
            segs.append(seg)
        T = 0.5
        durs = [_dur(x) for x in segs]
        start = [sum(durs[:k]) - k * T for k in range(len(segs))]
        out["_chapters"] = ([(0, "آغاز اور آج کی سرخیاں")] +
                            [(start[2 + i], p["headline"]) for i, p in enumerate(picks)])
        out["_voice"] = ", ".join(sorted(VOICE_USED))
        args, vf, af = [], [], []
        for x in segs:
            args += ["-i", x]
        vlast, alast, off = "0:v", "0:a", 0.0
        for k in range(1, len(segs)):
            off += durs[k - 1] - T
            kind = "fade" if segs_def[k]["kind"] == "full" else "slideleft"
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
