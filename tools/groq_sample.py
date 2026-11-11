"""🧪 Groq کا نمونہ (مالک، 11 نومبر 2026): آج کے بلیٹن کی 2 خبریں — وہی حقائق — Groq کے ماڈل سے دوبارہ لکھوا کر
جیمنائی والے متن کے ساتھ ٹیلیگرام پر، تاکہ مالک اردو کا معیار خود دیکھ لے۔ سسٹم میں کچھ نہیں بدلتا۔"""
import glob
import json
import os
import time
import urllib.parse
import urllib.request

KEY = os.environ.get("GROQ_API_KEY", "").strip()
WANT = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "llama-3.3-70b-versatile", "moonshotai/kimi-k2-instruct"]
SYSTEM = ("آپ «فاروقی اے آئی نیوز» کے اردو نیوز رائٹر ہیں۔ دی گئی خبر کے حقائق سے ٹی وی بلیٹن کا حصہ لکھیں: آسان، رواں، روزمرہ اردو "
          "(صرف اردو رسم الخط؛ کمپنی/پروڈکٹ کے نام اردو میں لکھیں، اعداد الفاظ میں)۔ کوئی نئی بات یا عدد اپنی طرف سے نہ گھڑیں۔ "
          'صرف JSON دیں: {"headline": "سرخی", "lead": "اینکر کے 2 جملے (تجسس والا آغاز)", "vo": "تفصیل، 3 جملے", '
          '"comment": "ناظرین، ... پاکستانی ناظر کے لیے اس کا مطلب، 1-2 جملے"}')


def tell(text: str) -> None:
    tok = (os.environ.get("NEWS_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    try:
        chat = str(json.load(open("state/news.json")).get("chat") or chat)
    except Exception:
        pass
    print(text, "\n")
    if tok and chat:
        urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                               data=urllib.parse.urlencode({"chat_id": chat, "text": text[:4000]}).encode()), timeout=30)


def groq(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request("https://api.groq.com/openai/v1/" + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                                          "User-Agent": "farooqi-ai-news/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def fmt(d: dict) -> str:
    return f"📰 {d.get('headline', '')}\n\n🎙 {d.get('lead', '')}\n\n📄 {d.get('vo', '')}\n\n💬 {d.get('comment', '')}"


def main() -> None:
    if not KEY:
        tell("🧪 Groq نمونہ: GROQ_API_KEY ابھی GitHub Secrets میں نہیں لگی — چابی لگا کر دوبارہ چلائیں۔")
        return
    try:
        have = {m["id"] for m in groq("models").get("data", [])}
    except Exception as e:
        tell(f"🧪 Groq نمونہ: چابی نہیں چلی ({type(e).__name__} {getattr(e, 'code', '')}) — چابی دوبارہ جانچیں۔")
        return
    models = [m for m in WANT if m in have][:2] or sorted(m for m in have if "whisper" not in m and "guard" not in m)[:1]
    f = sorted(glob.glob("state/script_*.json"), key=os.path.getmtime)[-1]
    stories = json.load(open(f))["stories"][:2]
    tell(f"🧪 Groq کا نمونہ — آج کے بلیٹن کی {len(stories)} خبریں، وہی حقائق۔ ہر خبر: پہلے جیمنائی کا متن، پھر Groq کا۔\nماڈل: {', '.join(models)}")
    for i, s in enumerate(stories, 1):
        tell(f"— خبر {i} · جیمنائی (موجودہ) —\n\n" + fmt(s))
        facts = json.dumps({"company": s.get("company"), "facts": [s.get("headline"), s.get("vo"), *s.get("points", [])]}, ensure_ascii=False)
        for m in models:
            t0 = time.time()
            try:
                r = groq("chat/completions", {"model": m, "temperature": 0.6, "response_format": {"type": "json_object"},
                                               "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": facts}]})
                d = json.loads(r["choices"][0]["message"]["content"])
                tell(f"— خبر {i} · Groq: {m} ({time.time() - t0:.0f} سیکنڈ) —\n\n" + fmt(d))
            except Exception as e:
                body = ""
                try:
                    body = e.read().decode()[:200]
                except Exception:
                    pass
                tell(f"— خبر {i} · Groq: {m} — نہیں چلا: {type(e).__name__} {getattr(e, 'code', '')} {body}")
            time.sleep(8)
    tell("🧪 نمونہ مکمل۔ اردو کا معیار دیکھ کر بتائیں: Groq کو متبادل کے طور پر لگاؤں یا نہیں۔")


if __name__ == "__main__":
    main()
