"""فاروقی اے آئی نیوز — مشترک اوزار: فائلیں، ffmpeg، Gemini (متن/آواز سننا)، آواز کاٹنا، ٹیلیگرام، کروم۔
چابیاں صرف GitHub Secrets سے (ماحول): GEMINI_NEWS_KEY یا GEMINI_API_KEY · NEWS_BOT_TOKEN یا TELEGRAM_BOT_TOKEN · TELEGRAM_CHAT_ID"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
FALLBACKS = ["gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash"]


def gemini_key() -> str:
    return os.environ.get("GEMINI_NEWS_KEY") or os.environ["GEMINI_API_KEY"]


def bot_token() -> str:
    return os.environ.get("NEWS_BOT_TOKEN") or os.environ["TELEGRAM_BOT_TOKEN"]


def read_json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write_json(p: Path, d) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True, timeout=1800)


def _dur(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def _norm(src: Path, dst: Path, pad: float = 0.5) -> Path:
    _ff("-i", str(src), "-af", f"apad=pad_dur={pad}", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(dst))
    return dst


class TTSQuota(RuntimeError):
    """آواز (Gemini TTS) کا روزانہ کوٹہ ختم"""


# ---------------- Gemini (متن) ----------------

def _gemini(system: str, user: str, extra_parts: list | None = None, max_tokens: int = 8192) -> str:
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": (extra_parts or []) + [{"text": user}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": max_tokens}}
    last = None
    for model in [GEMINI_MODEL] + [m for m in FALLBACKS if m != GEMINI_MODEL]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(4):
            try:
                r = requests.post(url, json=body, headers={"x-goog-api-key": gemini_key()}, timeout=300)
            except requests.RequestException as e:
                print(f"   {model}: {e} — دوبارہ")
                time.sleep(20 * (attempt + 1))
                continue
            last = r
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(30 * (attempt + 1))
                continue
            if r.status_code == 404:
                break
            r.raise_for_status()
            cand = r.json()["candidates"][0]
            return "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    if last is not None:
        last.raise_for_status()
    raise RuntimeError("Gemini سے جواب نہیں ملا")


def generate(system: str, user: str) -> str:
    return _gemini(system, user)


def generate_with_audio(system: str, user: str, audio_bytes: bytes, mime: str = "audio/wav") -> str:
    return _gemini(system, user, extra_parts=[{"inline_data": {"mime_type": mime, "data": base64.b64encode(audio_bytes).decode()}}])


def parse_json(txt: str) -> dict:
    """AI کے جواب سے JSON — معمولی خرابیاں (آخری کوما، ٹیڑھے کوٹس، کوڈ بلاک) خود درست"""
    import json
    import re
    m = re.search(r"\{.*\}", txt or "", flags=re.S)
    if not m:
        raise ValueError("جواب میں JSON نہیں ملا")
    s = m.group(0)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    t = s.replace("“", '"').replace("”", '"').replace(" ", " ")
    t = re.sub(r",\s*([}\]])", r"\1", t)                 # آخری کوما
    t = re.sub(r'"\s*\n\s*"', '",\n"', t)                 # دو خانوں کے بیچ چھوٹا ہوا کوما
    t = re.sub(r'(["\]}])\s*\n(\s*")', r"\1,\n\2", t)
    t = re.sub(r",\s*,", ",", t)
    return json.loads(t)


def generate_json(system: str, user: str, tries: int = 3) -> dict:
    """JSON والا جواب — خراب ہو تو درستی کی ہدایت کے ساتھ دوبارہ (کل `tries` بار)"""
    last = None
    for i in range(tries):
        extra = "" if i == 0 else ("\n\nاہم: پچھلا جواب درست JSON نہیں تھا (" + str(last)[:120] +
                                   ")۔ صرف ایک درست JSON آبجیکٹ لوٹائیں — ہر خانے کے بعد کوما، متن کے اندر \" کی جگہ « » استعمال کریں۔")
        try:
            return parse_json(generate(system, user + extra))
        except ValueError as e:      # JSONDecodeError بھی ValueError ہے
            last = e
            print(f"JSON خراب (کوشش {i + 1}): {e}")
    raise ValueError(f"AI کا جواب {tries} بار بھی درست JSON نہ بن سکا: {last}")


# ---------------- آواز کو حصوں میں کاٹنا ----------------

def _silences(wav: Path) -> list[tuple[float, float]]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af", "silencedetect=noise=-32dB:d=0.28",
                        "-f", "null", "-"], capture_output=True, text=True, timeout=300)
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(st, en))


def _align(wav: Path, texts: list[str], total: float) -> list[float] | None:
    """Gemini آواز سن کر بتاتا ہے کہ ہر پیراگراف کس سیکنڈ پر شروع ہوتا ہے (آواز اور لکھائی برابر رکھنے کے لیے)"""
    try:
        small = wav.with_name(wav.stem + "_16k.wav")
        _ff("-i", str(wav), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(small))
        listing = "\n".join(f"{i + 1}) {t.strip()[:160]}" for i, t in enumerate(texts))
        sysm = ("You are an exact audio timing tool. You listen to an Urdu narration and report when each listed "
                "paragraph begins. Answer only JSON.")
        user = (f"This audio ({total:.1f} seconds) is a narrator reading these {len(texts)} paragraphs in this exact order:\n"
                f"{listing}\n\nFor each paragraph give the time in seconds (decimal, e.g. 12.4) at which the narrator "
                f"starts speaking its first word. Reply only as JSON: {{\"starts\": [{len(texts)} numbers]}}")
        txt = generate_with_audio(sysm, user, small.read_bytes())
        m = re.search(r"\{.*\}", txt, flags=re.S)
        st = [float(x) for x in json.loads(m.group(0))["starts"]]
        if len(st) != len(texts) or any(b <= a for a, b in zip(st, st[1:])) or st[-1] >= total:
            print(f"   ہم آہنگی کا جواب درست نہیں: {st}")
            return None
        print(f"   پیراگراف کے اوقات: {st}")
        return st
    except Exception as e:
        print(f"   ہم آہنگی نہ ہو سکی (اندازے سے کاٹیں گے): {e}")
        return None


def _ok_cuts(cuts: list[float], end: float, texts: list[str]) -> bool:
    """ہر ٹکڑے کی لمبائی اس کے متن کے تناسب سے معقول ہو — ورنہ آواز اور لکھائی آگے پیچھے ہو جاتی ہیں"""
    w = [len(t) + 12 for t in texts]
    b = [0.0] + cuts + [end]
    for i in range(len(texts)):
        exp = end * w[i] / sum(w)
        got = b[i + 1] - b[i]
        if exp > 1.5 and not (0.6 <= got / exp <= 1.65):
            print(f"   ٹکڑا {i + 1}: {got:.1f}s، متوقع {exp:.1f}s — ہم آہنگی مشکوک")
            return False
    return True


class SplitError(RuntimeError):
    pass


def _split(wav: Path, texts: list[str], tmp: Path, tag: str) -> list[Path]:
    """ایک لمبی آواز کو مناظر کے حساب سے کاٹیں۔ ترتیب: (۱) پیراگراف کے لمبے وقفے ٹھیک n-1 ملیں تو وہی
    (۲) Gemini سے ہر پیراگراف کا شروع کا وقت → قریب ترین وقفہ۔ ہر نتیجہ جانچا جاتا ہے؛ کوئی درست نہ ہو تو
    SplitError (پھر ہر منظر کی آواز الگ بنتی ہے — اندازے سے کاٹ کر غلط ہم آہنگی نہیں)"""
    if len(texts) == 1:
        return [wav]
    n = len(texts)
    total = _dur(wav)
    sil = _silences(wav)
    end = sil[-1][0] if sil and sil[-1][1] >= total - 0.05 else total      # آخر کی خاموشی نکال کر
    longp = [(a + b) / 2 for a, b in sil if b - a >= 0.7 and 0.5 < (a + b) / 2 < end - 0.5]
    if len(longp) == n - 1 and _ok_cuts(longp, end, texts):
        print("   ہم آہنگی: پیراگراف کے وقفوں سے")
        return _cut(wav, longp, total, n, tmp, tag)
    starts = _align(wav, texts, total) if True else None
    if starts:
        cuts, prev = [], 0.0
        for k in range(1, n):
            est = starts[k]
            near = [(a, b) for a, b in sil if abs(b - est) <= 1.5 and (a + b) / 2 > prev + 0.4]
            pick = (lambda ab: (ab[0] + ab[1]) / 2)(min(near, key=lambda ab: abs(ab[1] - est))) if near else max(0.0, est - 0.12)
            pick = max(pick, prev + 0.4)
            cuts.append(pick)
            prev = pick
        if _ok_cuts(cuts, end, texts):
            print("   ہم آہنگی: Gemini اوقات سے")
            return _cut(wav, cuts, total, n, tmp, tag)
    raise SplitError("آواز کو مناظر میں درست نہیں کاٹا جا سکا")


def _cut(wav: Path, cuts: list[float], total: float, n: int, tmp: Path, tag: str) -> list[Path]:
    bounds = [0.0] + cuts + [total]
    out = []
    for i in range(n):
        o = tmp / f"{tag}_{i}.wav"
        _ff("-i", str(wav), "-ss", f"{bounds[i]:.3f}", "-to", f"{bounds[i + 1]:.3f}", "-c:a", "pcm_s16le", str(o))
        out.append(o)
    return out



# ---------------- ٹیلیگرام ----------------

_REC: list | None = None


def tg_call(method: str, files=None, **params):
    url = f"https://api.telegram.org/bot{bot_token()}/{method}"
    if files:
        data = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in params.items()}
        r = requests.post(url, data=data, files=files, timeout=600)
    else:
        r = requests.post(url, json=params, timeout=60)
    body = r.json()
    if not body.get("ok") and body.get("error_code") == 429 and not files:
        time.sleep(min(int(body.get("parameters", {}).get("retry_after", 5)) + 1, 60))
        body = requests.post(url, json=params, timeout=60).json()
    if not body.get("ok"):
        raise RuntimeError(f"Telegram {method}: {body.get('description')}")
    res = body["result"]
    if _REC is not None and isinstance(res, dict) and res.get("message_id") and method.startswith("send"):
        _REC.append(res["message_id"])
    return res


def record_start() -> None:
    global _REC
    _REC = []


def record_stop() -> list:
    global _REC
    out, _REC = (_REC or []), None
    return out


def send_text(chat, text: str, html: bool = True, **kw) -> int:
    if html:
        kw.update(parse_mode="HTML", link_preview_options={"is_disabled": True})
    return tg_call("sendMessage", chat_id=chat, text=text, **kw)["message_id"]


def send_video(chat, path: Path, caption: str = "", buttons=None, width: int = 1920, height: int = 1080) -> int:
    extra = {"reply_markup": {"inline_keyboard": buttons}} if buttons else {}
    with open(path, "rb") as f:
        return tg_call("sendVideo", files={"video": (path.name, f, "video/mp4")}, chat_id=chat, caption=caption[:1000],
                       width=width, height=height, supports_streaming=True, **extra)["message_id"]


def send_photo(chat, path: Path, caption: str = "") -> int:
    with open(path, "rb") as f:
        return tg_call("sendPhoto", files={"photo": (path.name, f, "image/jpeg")}, chat_id=chat, caption=caption[:1000])["message_id"]


# ---------------- کروم ----------------

def _launch(pw):
    for kw in ({"channel": "chrome"}, {}, {"executable_path": "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"}):
        try:
            return pw.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"], **kw)
        except Exception:
            continue
    raise RuntimeError("کروم نہیں کھل سکا")


