"""ہونٹوں کی حرکت آواز کے مطابق — MuseTalk (Tencent، MIT لائسنس، کاروباری استعمال کی اجازت)

ساکن تصویر + آواز → صرف چہرے والے حصے کی ویڈیو (patch)، جو studio.py اینکر کی تصویر پر رکھتا ہے۔
GPU کے بغیر (GitHub کا عام کمپیوٹر) چلتا ہے؛ ماڈل پہلی بار Hugging Face سے آتے ہیں اور پھر کیش میں رہتے ہیں۔

    python lipsync.py test        # نمونہ: مرد اینکر ایک جملہ بولتا ہے → ٹیلیگرام
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MT_DIR = Path(os.environ.get("MUSETALK_DIR", ROOT / ".musetalk"))
MT_REPO = "https://github.com/TMElyralab/MuseTalk.git"
MT_COMMIT = "0a89dec45a0192b824e3cf4daf96c239440c5ed8"
MODELS = MT_DIR / "models"
LS_FPS = 25

_M: dict = {}


def log(msg: str) -> None:
    print(f"[lipsync] {msg}", flush=True)


def ensure() -> None:
    """MuseTalk کوڈ اور ماڈل (اگر موجود نہ ہوں)"""
    if not (MT_DIR / "musetalk").exists():
        subprocess.run(["git", "clone", "-q", MT_REPO, str(MT_DIR)], check=True)
        subprocess.run(["git", "-C", str(MT_DIR), "checkout", "-q", MT_COMMIT], check=True)
    from huggingface_hub import hf_hub_download
    need = [("TMElyralab/MuseTalk", "musetalkV15/unet.pth", MODELS),
            ("TMElyralab/MuseTalk", "musetalkV15/musetalk.json", MODELS),
            ("stabilityai/sd-vae-ft-mse", "config.json", MODELS / "sd-vae"),
            ("stabilityai/sd-vae-ft-mse", "diffusion_pytorch_model.bin", MODELS / "sd-vae"),
            ("openai/whisper-tiny", "config.json", MODELS / "whisper"),
            ("openai/whisper-tiny", "pytorch_model.bin", MODELS / "whisper"),
            ("openai/whisper-tiny", "preprocessor_config.json", MODELS / "whisper")]
    for repo, name, dest in need:
        if not (dest / name).exists():
            log(f"downloading {repo}/{name}")
            hf_hub_download(repo, name, local_dir=str(dest))


def _load():
    if _M:
        return _M
    import torch
    ensure()
    sys.path.insert(0, str(MT_DIR))
    torch.set_num_threads(os.cpu_count() or 4)
    from transformers import WhisperModel
    from musetalk.models.unet import PositionalEncoding, UNet
    from musetalk.models.vae import VAE
    from musetalk.utils.audio_processor import AudioProcessor
    dev = torch.device("cpu")
    t = time.time()
    _M["vae"] = VAE(model_path=str(MODELS / "sd-vae"))
    _M["unet"] = UNet(unet_config=str(MODELS / "musetalkV15" / "musetalk.json"),
                      model_path=str(MODELS / "musetalkV15" / "unet.pth"), device=dev)
    _M["pe"] = PositionalEncoding(d_model=384).to(dev)
    _M["ap"] = AudioProcessor(feature_extractor_path=str(MODELS / "whisper"))
    _M["whisper"] = WhisperModel.from_pretrained(str(MODELS / "whisper")).to(dev).eval()
    _M["dev"] = dev
    log(f"models loaded in {time.time() - t:.0f}s")
    return _M


def available() -> bool:
    if os.environ.get("LIPSYNC", "1") != "1":
        return False
    try:
        import torch  # noqa: F401
        import diffusers  # noqa: F401
        _load()
        return True
    except Exception as e:
        log(f"not available: {e}")
        return False


def _mask(w: int, h: int):
    """منہ اور ٹھوڑی کا نرم ماسک (چہرے کے ڈبے کا نچلا حصہ) — آنکھیں اور ناک ویسے ہی رہیں"""
    import numpy as np
    yy, xx = np.mgrid[0:h, 0:w].astype("float32")
    cx, cy = w / 2, h * 0.74
    rx, ry = w * 0.36, h * 0.30
    d = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    m = np.clip((1.25 - d) / 0.45, 0, 1)
    m[yy < h * 0.47] *= np.clip((yy[yy < h * 0.47] - h * 0.40) / (h * 0.07), 0, 1)
    return m[..., None]


def animate(base, box: tuple[int, int, int, int], audio: Path, out: Path, pad: int = 24) -> tuple[Path, int, int]:
    """base: پوری اسکرین کی اینکر تصویر (PIL RGB)، box: چہرہ (x1, y1, x2, y2)
    واپس: patch ویڈیو، اور اسے رکھنے کی جگہ (x, y)"""
    import cv2
    import numpy as np
    import torch
    m = _load()
    vae, unet, pe, ap, whisper = m["vae"], m["unet"], m["pe"], m["ap"], m["whisper"]
    x1, y1, x2, y2 = box
    y2 += 10                                          # v1.5: ٹھوڑی کے نیچے تھوڑی جگہ
    frame = cv2.cvtColor(np.asarray(base), cv2.COLOR_RGB2BGR)
    crop = cv2.resize(frame[y1:y2, x1:x2], (256, 256), interpolation=cv2.INTER_LANCZOS4)
    wav16 = out.with_suffix(".16k.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", "16000", str(wav16)], check=True)
    t0 = time.time()
    with torch.no_grad():
        latent = vae.get_latents_for_unet(crop)
        feats, n = ap.get_audio_feature(str(wav16))
        chunks = ap.get_whisper_chunk(feats, m["dev"], torch.float32, whisper, n, fps=LS_FPS,
                                      audio_padding_length_left=2, audio_padding_length_right=2)
        # patch: چہرے کا ڈبہ + اردگرد تھوڑی جگہ (نرم کنارے)
        px1, py1 = max(0, x1 - pad), max(0, y1 - pad)
        px2, py2 = min(frame.shape[1], x2 + pad), min(frame.shape[0], y2 + pad)
        pw, ph = (px2 - px1) // 2 * 2, (py2 - py1) // 2 * 2
        px2, py2 = px1 + pw, py1 + ph
        still = frame[py1:py2, px1:px2].astype("float32")
        mk = _mask(x2 - x1, y2 - y1)
        enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                                "-s", f"{pw}x{ph}", "-r", str(LS_FPS), "-i", "-", "-c:v", "libx264",
                                "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", str(out)],
                               stdin=subprocess.PIPE)
        bs, ts = 16, torch.tensor([0])
        for i in range(0, len(chunks), bs):
            wb = chunks[i:i + bs]
            lat = latent.repeat(len(wb), 1, 1, 1)
            pred = unet.model(lat, ts, encoder_hidden_states=pe(wb)).sample
            for face in vae.decode_latents(pred):
                face = cv2.resize(face, (x2 - x1, y2 - y1), interpolation=cv2.INTER_LANCZOS4).astype("float32")
                img = still.copy()
                oy, ox = y1 - py1, x1 - px1
                reg = img[oy:oy + (y2 - y1), ox:ox + (x2 - x1)]
                img[oy:oy + (y2 - y1), ox:ox + (x2 - x1)] = reg * (1 - mk) + face * mk
                enc.stdin.write(np.clip(img, 0, 255).astype("uint8").tobytes())
        enc.stdin.close()
        enc.wait()
    log(f"{len(chunks)} frames in {time.time() - t0:.0f}s")
    return out, px1, py1


def test() -> None:
    """نمونہ ویڈیو: مرد اینکر کا ایک جملہ، ہونٹ آواز کے ساتھ → ٹیلیگرام"""
    import tempfile
    import studio
    import script
    text = ("السلام علیکم۔ فاروقی اے آئی نیوز میں خوش آمدید۔ آج مصنوعی ذہانت کی دنیا سے کئی اہم خبریں ہیں۔ "
            "اوپن اے آئی نے نیا ماڈل متعارف کرایا ہے، جبکہ گوگل نے اپنی تحقیق کے نتائج جاری کیے ہیں۔")
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        if studio._cut("m").exists() and studio._cut("f").exists():
            studio.build_set(tmp)
        base = studio._anchor_full("m")
        a = studio.speak(text, tmp / "v.mp3", 0)
        box = studio.face_box("m")
        patch, px, py = animate(base, box, a, tmp / "patch.mp4")
        base.save(tmp / "base.png")
        out = ROOT / "lipsync_test.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(LS_FPS), "-i", str(tmp / "base.png"),
                        "-i", str(patch), "-i", str(a), "-filter_complex",
                        f"[0:v][1:v]overlay={px}:{py}:eof_action=pass,format=yuv420p[v]", "-map", "[v]", "-map", "2:a",
                        "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "aac", str(out)], check=True)
        chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or str(script.load_history().get("chat_id", ""))
        script.send_video(out, f"🧪 ہونٹوں کا نمونہ (MuseTalk) — آواز: {', '.join(sorted(studio.VOICE_USED))}", chat)
        log("sent")


if __name__ == "__main__":
    if sys.argv[1:] == ["test"]:
        test()
