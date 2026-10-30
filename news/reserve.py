"""🌙 رات کا «بچت والا کام» (روز 9 بجے سعودی) — ریزرو (دوسری) جیمنائی چابی آج استعمال نہ ہوئی ہو تو اس کی بچت کام میں:
1) «آج کا اے آئی لفظ» شارٹ (1–2 درخواستیں)
2) جمعرات کی رات: کل کے «اے آئی بیٹھک» پوڈکاسٹ کی پیشگی آوازیں (باقی بچت سے) — جمعہ کو پہلی چابی پر بوجھ کم
کوٹا اگلی صبح 10–11 بجے نیا ہو جاتا ہے، اس لیے ریزرو کو نقصان نہیں۔ 2 درخواستیں ہمیشہ چھوڑ دی جاتی ہیں۔
python -m news.reserve        → آج کا کام
python -m news.reserve word   → صرف لفظ (❌ کے بعد دوبارہ)
"""
from __future__ import annotations

import datetime as dt
import os
import sys

from . import bulletin as B
from .base import read_json, write_json, send_text

LIMIT, KEEP = 10, 2


def left() -> int:
    return LIMIT - KEEP - B.backup_used()


def tick(only_word: bool = False) -> None:
    if not os.environ.get("GEMINI_BACKUP_KEY", "").strip():
        print("ریزرو چابی نہیں")
        return
    st = read_json(B.STATE) if B.STATE.exists() else {}
    redo = st.get("redo_w")
    print(f"ریزرو چابی: آج {B.backup_used()} استعمال، {max(0, left())} دستیاب")
    from . import word, podcast
    key = B._today() + "-w"
    if left() >= 2 and (redo or key not in st.get("days", {})):
        try:
            word.make(feedback=redo.get("feedback") if isinstance(redo, dict) else None)
        except Exception as e:
            print("لفظ نہیں بنا:", e)
            if redo:
                send_text(B.news_chat(), f"⚠️ «آج کا اے آئی لفظ» دوبارہ نہ بن سکا: {str(e)[:200]}", html=False)
    if only_word or redo:
        return
    if dt.datetime.now(B.TZ).weekday() == podcast.POD_DAY - 1 and left() >= 1:      # جمعرات کی رات
        try:
            podcast.prevoice(left())
        except Exception as e:
            print("پوڈکاسٹ کی پیشگی تیاری نہیں ہوئی:", e)
    print(f"آخر میں ریزرو: {B.backup_used()} استعمال")


if __name__ == "__main__":
    tick(only_word=len(sys.argv) > 1 and sys.argv[1] == "word")
