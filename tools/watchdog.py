"""🔁 نگران (مالک، 11 نومبر 2026): کوئی ویڈیو/کام ناکام ہو تو خود دوبارہ چلاؤ — تینوں چینل۔

ہر 20 منٹ: ہر زیرِ نگرانی ورک فلو کا تازہ ترین مکمل رن دیکھو۔ ناکام ہو (اور کچھ چل نہ رہا ہو) تو
75 منٹ بعد پہلی، پھر اس کے ناکام ہونے کے 105 منٹ بعد دوسری کوشش۔ ہر قدم کی اطلاع ٹیلیگرام پر۔
ٹول اسکیپ / نوائے فاروقی کے نجی ریپو کی ناکامی پر یہاں کا متبادل ورک فلو (لامحدود منٹ) چلتا ہے۔
دوہری ویڈیو سے بچاؤ: ٹول اسکیپ کی آج کی ویڈیو اپلوڈ ہو چکی ہو تو دوبارہ نہیں بنتی۔ یہاں کوئی راز نہیں چھپتا۔
"""
import datetime as dt
import json
import os
import pathlib
import urllib.parse
import urllib.request

OWN = os.environ.get("GITHUB_REPOSITORY", "abdulbasitfarooqi313-sys/farooqi-ai-news")
TS, NAWA = "hellotoolscape/ai-tube-factory", "nawaefarooqi-bit/nawaefarooqi-agents"
DELAYS = [75, 105]                       # منٹ: ناکامی کے بعد پہلی کوشش، پھر اس کی ناکامی کے بعد دوسری
STALE_H = 10                             # اس سے پرانی ناکامی پر کچھ نہیں (اگلا مقررہ رن خود آئے گا)
STATE = pathlib.Path("state/watchdog.json")
RIYADH = dt.timezone(dt.timedelta(hours=3))

# نام · کہاں دیکھنا ہے (ریپو، فائل، چابی) · کیا چلانا ہے (ہمیشہ اسی پبلک ریپو میں: فائل، inputs)
WATCH = [
    ("اے آئی نیوز — بلیٹن", OWN, "bulletin.yml", "GH", "bulletin.yml", {}),
    ("اے آئی نیوز — فلیش شارٹ", OWN, "flash.yml", "GH", "flash.yml", {}),
    ("اے آئی نیوز — آج کا لفظ (رات)", OWN, "reserve.yml", "GH", "reserve.yml", {}),
    ("اے آئی نیوز — ٹیک دریافت", OWN, "tech.yml", "GH", "tech.yml", {"mode": "real"}),
    ("روزنامچہ فاروقی", OWN, "desk.yml", "GH", "desk.yml", {}),
    ("وائرل مقابل", OWN, "outliers.yml", "GH", "outliers.yml", {}),
    ("ہفتہ وار رپورٹ", OWN, "perf.yml", "GH", "perf.yml", {}),
    ("ٹول اسکیپ — ویڈیو", TS, "make-video.yml", "TS", "toolscape-video.yml", {"force": "true"}),
    ("ٹول اسکیپ — ویڈیو (متبادل رنر)", OWN, "toolscape-video.yml", "GH", "toolscape-video.yml", {"force": "true"}),
    ("نوائے فاروقی — سبق کی ویڈیو", NAWA, "lesson-video.yml", "NAWA", "nawa-lesson.yml", {"force": "true"}),
    ("نوائے فاروقی — سبق (متبادل رنر)", OWN, "nawa-lesson.yml", "GH", "nawa-lesson.yml", {"force": "true"}),
    # مالک (12 نومبر 2026): سیریز کے شارٹس اور لمبی ویڈیو — ناکامی پر دوبارہ کوشش لامحدود رنر پر
    ("نوائے فاروقی — سیریز شارٹس", NAWA, "media.yml", "NAWA", "nawa-video-fallback.yml", {"job": "media", "force": "true"}),
    ("نوائے فاروقی — لمبی ویڈیو", NAWA, "long-video.yml", "NAWA", "nawa-video-fallback.yml", {"job": "long", "force": "true"}),
    ("ٹول اسکیپ — منظوری اور پلے لسٹ", OWN, "toolscape-jobs.yml", "GH", "toolscape-jobs.yml", {"job": "approve"}),
]
TOK = {"GH": os.environ.get("GH_TOKEN", ""), "TS": os.environ.get("TS_TOKEN", ""), "NAWA": os.environ.get("NAWA_TOKEN", "")}


def api(path: str, tok: str, body: dict | None = None, raw: bool = False):
    req = urllib.request.Request("https://api.github.com/" + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {tok}", "X-GitHub-Api-Version": "2022-11-28",
                                          "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read()
    return data.decode() if raw else (json.loads(data) if data else {})


def tell(text: str) -> None:
    tok = (os.environ.get("NEWS_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    try:
        chat = str(json.loads(pathlib.Path("state/news.json").read_text()).get("chat") or chat)
    except Exception:
        pass
    print(text)
    if not (tok and chat):
        return
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            data=urllib.parse.urlencode({"chat_id": chat, "text": text, "disable_web_page_preview": "true"}).encode()), timeout=30)
    except Exception as e:
        print("telegram:", type(e).__name__)


def ts_made_today() -> bool:
    """ٹول اسکیپ کی آج کی ویڈیو پہلے ہی اپلوڈ ہو چکی؟ (تب ناکامی اپلوڈ کے بعد کی تھی — دوبارہ بنانا دوہرا ہوگا)"""
    try:
        y = json.loads(api(f"repos/{TS}/contents/state/youtube.json", TOK["TS"], raw=True))
        now = dt.datetime.now(dt.timezone.utc)
        days = {(now - dt.timedelta(days=d)).strftime("%Y-%m-%d") for d in (0, 1)}
        # ریکارڈ کی چابی یوٹیوب ID ہوتی ہے؛ تاریخ «vid» میں ہے (13 نومبر کی اصلاح — پہلے یہ جانچ کبھی میچ نہیں کرتی تھی)
        return any(str(v.get("vid", ""))[:10] in days for v in y.get("videos", {}).values() if isinstance(v, dict))
    except Exception as e:
        print("ts state:", type(e).__name__)
        return True                                  # معلوم نہ ہو سکے تو احتیاط: دوبارہ نہ بناؤ


def hhmm(t: dt.datetime) -> str:
    return t.astimezone(RIYADH).strftime("%I:%M %p").lstrip("0").replace("AM", "صبح").replace("PM", "شام/رات")


def main() -> None:
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    now = dt.datetime.now(dt.timezone.utc)
    for name, repo, wf, tk, target, inputs in WATCH:
        key = f"{repo}/{wf}"
        if not TOK[tk]:
            print(f"- {name}: چابی نہیں، چھوڑ دیا")
            continue
        try:
            runs = api(f"repos/{repo}/actions/workflows/{wf}/runs?per_page=8", TOK[tk]).get("workflow_runs", [])
            busy = any(r["status"] != "completed" for r in runs)
            if target != wf:                              # متبادل چل رہا ہو تو بھی انتظار
                busy = busy or any(r["status"] != "completed" for r in
                                   api(f"repos/{OWN}/actions/workflows/{target}/runs?per_page=4", TOK["GH"]).get("workflow_runs", []))
        except Exception as e:
            print(f"- {name}: دیکھ نہ سکا ({type(e).__name__} {getattr(e, 'code', '')})")
            continue
        done = [r for r in runs if r["status"] == "completed" and r["conclusion"] in ("success", "failure", "timed_out")]
        if not done or done[0]["conclusion"] == "success":
            if (st.pop(key, None) or {}).get("n", 0) > 0 and done:
                tell(f"✅ «{name}» دوبارہ کوشش پر ٹھیک چل گیا۔")
            continue
        last = done[0]
        ended = dt.datetime.fromisoformat(last["updated_at"].replace("Z", "+00:00"))
        if target != wf and (st.get(key) or {}).get("n", 0) > 0:      # نجی ریپو: کوشش متبادل رنر کو سونپ دی — آگے وہی دیکھا جاتا ہے
            continue
        age = (now - ended).total_seconds() / 60
        s = st.get(key) or {}
        if s.get("day") != ended.strftime("%Y-%m-%d") and s.get("run") != last["id"]:
            s = {"day": ended.strftime("%Y-%m-%d"), "n": 0}
        if age > STALE_H * 60 or busy:
            st[key] = s
            continue
        n = s.get("n", 0)
        if n >= len(DELAYS):
            if s.get("gave_up") != last["id"]:
                s["gave_up"] = last["id"]
                tell(f"⛔ «{name}» {len(DELAYS)} بار دوبارہ کوشش کے بعد بھی نہیں چلا — آج مزید کوشش نہیں۔ "
                     f"اگلا مقررہ وقت خود آئے گا۔ تفصیل: {last['html_url']}")
            st[key] = s
            continue
        due = ended + dt.timedelta(minutes=DELAYS[n])
        if now < due:
            if s.get("told") != last["id"]:
                s["told"] = last["id"]
                tell(f"⚠️ «{name}» ناکام ہوا۔ 🔁 تقریباً {hhmm(due)} (سعودی) پر خود دوبارہ کوشش ہو گی ({n + 1}/{len(DELAYS)}) — آپ کو کچھ نہیں کرنا۔")
            st[key] = s
            continue
        if repo == TS or target == "toolscape-video.yml":
            if ts_made_today():
                s.update(n=len(DELAYS), gave_up=last["id"])
                st[key] = s
                print(f"- {name}: آج کی ویڈیو پہلے سے اپلوڈ ہے — دوبارہ نہیں")
                continue
        try:
            api(f"repos/{OWN}/actions/workflows/{target}/dispatches", TOK["GH"], {"ref": "main", "inputs": inputs})
            s.update(n=n + 1, run=last["id"], last=now.isoformat())
            tell(f"🔁 «{name}» — دوبارہ کوشش شروع ({n + 1}/{len(DELAYS)})۔ نتیجہ خود بتاؤں گا۔")
        except Exception as e:
            print(f"- {name}: چلا نہ سکا ({type(e).__name__} {getattr(e, 'code', '')})")
        st[key] = s
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
