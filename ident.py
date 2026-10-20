"""انٹرو اور آؤٹرو: نیوز چینل کا شناختی حصہ — موسیقی کے بغیر، صرف انسانی آوازیں (vocals)

آواز: کورس (کئی گلوکاروں کی "اووو / آآآ" جیسی گنگناہٹ — کوئی ساز نہیں) + اینکرز کی آواز میں چینل کا نام، گونج کے ساتھ۔
تصویر: نیلا پس منظر، لوگو آہستہ سے بڑا ہو کر نمایاں، روشنی کی چمک گزرتی ہے، نام نمودار۔
"""
from __future__ import annotations

import html
import wave
from pathlib import Path

import numpy as np

SR = 44100

# حرفِ علت کے فارمینٹ (Hz, bandwidth)
VOWELS = {"oo": [(320, 80), (800, 100), (2300, 140)],
          "aa": [(760, 90), (1180, 110), (2700, 160)]}


def _resonate(x: np.ndarray, f: float, bw: float) -> np.ndarray:
    from scipy.signal import lfilter
    r = np.exp(-np.pi * bw / SR)
    th = 2 * np.pi * f / SR
    return lfilter([1 - r], [1, -2 * r * np.cos(th), r * r], x)


def _voice(f0: float, n: int, vowel: str, rnd: np.random.Generator) -> np.ndarray:
    """ایک گلوکار: ہلکی لرزش (vibrato) والی آواز، حلق کی گونج (فارمینٹ) سے گزری ہوئی"""
    t = np.arange(n) / SR
    vib = 1 + 0.006 * np.sin(2 * np.pi * rnd.uniform(4.6, 5.8) * t + rnd.uniform(0, 6.28))
    drift = 1 + 0.002 * np.sin(2 * np.pi * rnd.uniform(0.15, 0.4) * t)
    f = f0 * rnd.uniform(0.995, 1.005) * vib * drift
    ph = 2 * np.pi * np.cumsum(f) / SR
    src = np.zeros(n)
    for k in range(1, int(4200 / f0)):
        src += np.sin(k * ph) / k ** 1.2
    src += 0.02 * rnd.standard_normal(n)          # سانس کی ہلکی آواز
    out = sum(_resonate(src, F, B) * g for (F, B), g in zip(VOWELS[vowel], (1.0, 0.55, 0.25)))
    return out


def choir(seconds: float, notes=(146.83, 220.0, 293.66, 369.99), vowel: str = "oo",
          attack: float = 1.6, release: float = 1.8, seed: int = 7) -> np.ndarray:
    n = int(seconds * SR)
    rnd = np.random.default_rng(seed)
    mix = np.zeros(n)
    for f0 in notes:
        for _ in range(4):                          # ہر سُر پر چار آوازیں — کورس
            mix += _voice(f0, n, vowel, rnd)
    t = np.arange(n) / SR
    env = np.clip(t / attack, 0, 1) ** 1.5 * np.clip((seconds - t) / release, 0, 1)
    mix *= env
    return mix / (np.abs(mix).max() + 1e-9) * 0.5


def save_wav(x: np.ndarray, path: Path) -> Path:
    y = (np.clip(x, -1, 1) * 32767).astype("<i2")
    st = np.stack([y, y], 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())
    return path


# ---------------- تصویر ----------------

def card_html(logo: str, fonts: str, title: str, sub: str, date: str = "") -> tuple[str, str, str]:
    """تین تہیں: پس منظر، لوگو، متن (ffmpeg انہیں حرکت دیتا ہے)"""
    base = (f'<!doctype html><meta charset="utf-8"><style>{fonts}'
            '*{margin:0;padding:0;box-sizing:border-box}html,body{width:1920px;height:1080px;overflow:hidden;background:transparent}'
            'body{font-family:Nast,Naskh,serif;color:#fff;direction:rtl}</style><body>')
    bg = (base + '<div style="position:absolute;inset:0;background:radial-gradient(1100px 700px at 50% 42%,#1f5be0,#0a1f5c 62%,#040c2a)"></div>'
          '<div style="position:absolute;inset:0;opacity:.13;background-image:linear-gradient(rgba(140,200,255,.9) 1px,transparent 1px),'
          'linear-gradient(90deg,rgba(140,200,255,.9) 1px,transparent 1px);background-size:64px 64px;'
          'mask-image:radial-gradient(ellipse at 50% 45%,#000 25%,transparent 72%)"></div>'
          '<div style="position:absolute;left:50%;top:44%;width:1500px;height:1500px;margin:-750px 0 0 -750px;border-radius:50%;'
          'border:3px solid rgba(0,198,255,.35)"></div>'
          '<div style="position:absolute;left:50%;top:44%;width:1100px;height:1100px;margin:-550px 0 0 -550px;border-radius:50%;'
          'border:2px solid rgba(212,167,58,.45)"></div>'
          '<div style="position:absolute;left:0;right:0;bottom:0;height:14px;background:linear-gradient(90deg,#0b2a6f,#00b4e6,#d4a73a)"></div></body>')
    lg = (base + f'<img src="{logo}" style="position:absolute;left:660px;top:120px;width:600px;height:600px;border-radius:50%;'
          'box-shadow:0 0 90px rgba(0,190,255,.65)"></body>')
    tx = (base + '<div style="position:absolute;left:0;right:0;top:735px;text-align:center">'
          f'<div style="font-weight:700;font-size:96px;line-height:1.7;text-shadow:0 8px 40px rgba(0,0,0,.6)">{html.escape(title)}</div>'
          f'<div style="font-size:46px;line-height:1.6;color:#bfe9ff">{html.escape(sub)}'
          + (f' · {html.escape(date)}' if date else "") + '</div></div></body>')
    return bg, lg, tx


def sweep_png(path: Path) -> Path:
    """روشنی کی ترچھی پٹی (لوگو پر سے گزرتی چمک)"""
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new("RGBA", (700, 1080), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(260, 0), (420, 0), (300, 1080), (140, 1080)], fill=(255, 255, 255, 70))
    im.filter(ImageFilter.GaussianBlur(30)).save(path)
    return path
