"""بلاگ کے لیے صاف، چوڑی تصویر (1280×720) — یوٹیوب کی دھندلی خودکار تصویر کی جگہ ہمارا اپنا تھمب نیل۔
کھڑی تصویر (شارٹ) ہو تو بیچ میں اصل تصویر اور دونوں طرف اسی کا دھندلا پس منظر۔ media/<کلید>.jpg (پبلک ریپو سے دکھتی ہے)"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

from .base import ROOT

MEDIA = ROOT / "media"
RAW = "https://raw.githubusercontent.com/abdulbasitfarooqi313-sys/farooqi-ai-news/main/media/"
W, H = 1280, 720


def wide(src: Path, key: str) -> str:
    im = Image.open(src).convert("RGB")
    if im.width / im.height < 1.5:                       # کھڑی/چوکور → دھندلا پس منظر + بیچ میں اصل
        bg = im.resize((W, int(im.height * W / im.width)), Image.LANCZOS)
        top = max(0, (bg.height - H) // 2)
        bg = bg.crop((0, top, W, top + H)).filter(ImageFilter.GaussianBlur(28))
        bg = ImageEnhance.Brightness(bg).enhance(0.55)
        fg = im.resize((int(im.width * H / im.height), H), Image.LANCZOS)
        bg.paste(fg, ((W - fg.width) // 2, 0))
        out = bg
    else:
        r = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * r + 0.5), int(im.height * r + 0.5)), Image.LANCZOS)
        l, t = (im.width - W) // 2, (im.height - H) // 2
        out = im.crop((l, t, l + W, t + H))
    MEDIA.mkdir(exist_ok=True)
    dst = MEDIA / f"{key}.jpg"
    out.save(dst, "JPEG", quality=88, optimize=True, progressive=True)
    return RAW + dst.name
