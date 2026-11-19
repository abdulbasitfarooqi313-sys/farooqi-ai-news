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
import urllib.error
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
    ("اے آئی نیوز — خودکار شارٹ", OWN, "clips.yml", "GH", "clips.yml", {"mode": "real"}),
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


REASONS = [  # (لاگ میں کیا ملا، اردو وجہ، دوبارہ کوشش سے ٹھیک ہونے کا امکان؟)
    (("exceeded your current quota", "RESOURCE_EXHAUSTED", " 429"), "جیمنائی کا آج کا کوٹا ختم", False),
    (("503", "UNAVAILABLE", "overloaded", "high demand"), "جیمنائی/گوگل اس وقت مصروف تھا", True),
    (("Read timed out", "ReadTimeout", "timed out", "TimeoutError"), "کسی سرور نے وقت پر جواب نہیں دیا", True),
    (("invalid_grant", "Token has been expired", "token expired", "Bad credentials", "OAuthException"), "کسی چابی کی میعاد ختم — نئی لگانی ہو گی", False),
    (("No space left on device",), "رنر کی ڈسک بھر گئی", True),
    (("quotaExceeded", "uploadLimitExceeded"), "یوٹیوب کا روزانہ کوٹا/اپلوڈ حد ختم", False),
    (("ConnectionError", "Connection reset", "Max retries exceeded", "502 Bad Gateway"), "نیٹ ورک کا عارضی مسئلہ", True),
]


class _NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def joblog(repo: str, job: int, tok: str) -> str:
    """لاگ کا لنک (302) خود کھولو — بلاب پر GitHub کی چابی نہ بھیجی جائے"""
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/jobs/{job}/logs",
                                 headers={"Authorization": f"Bearer {tok}", "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.build_opener(_NoRedir).open(req, timeout=40) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307) or not e.headers.get("Location"):
            raise
        with urllib.request.urlopen(e.headers["Location"], timeout=60) as r:
            return r.read().decode("utf-8", "replace")


def why(repo: str, run: dict, tok: str) -> tuple[str, str, bool]:
    """ناکام رن کے لاگ سے اردو وجہ: (وجہ، لاگ کا آخری حصہ، کوڈ کی خرابی؟)"""
    try:
        jobs = api(f"repos/{repo}/actions/runs/{run['id']}/jobs", tok).get("jobs", [])
        j = next((x for x in jobs if x.get("conclusion") in ("failure", "timed_out")), None)
        if not j:
            return "وجہ معلوم نہ ہو سکی", "", False
        if j.get("conclusion") == "timed_out":
            return "کام مقررہ وقت سے زیادہ چلا (ٹائم آؤٹ)", "", False
        if not j.get("runner_name"):                     # کام شروع ہی نہیں ہوا (19 نومبر: نوا کے نجی منٹ ختم)
            try:
                ann = " ".join(x.get("message", "") for x in api(j["check_run_url"].split("api.github.com/", 1)[1] + "/annotations", tok))
            except Exception:
                ann = ""
            if "spending limit" in ann or "payments" in ann or "minutes" in ann:
                return "نجی ریپو کے مفت GitHub منٹ اس مہینے ختم — کام متبادل (پبلک) رنر پر ہوتا ہے", "", False
            return "کام شروع ہی نہیں ہوا: " + (ann[:140] or "وجہ نامعلوم"), "", False
        log = joblog(repo, j["id"], tok)
    except Exception as e:
        return f"لاگ نہ پڑھ سکا ({type(e).__name__})", "", False
    lines = [l.split("Z ", 1)[-1] for l in log.splitlines()]
    tail = "\n".join(lines[-80:])
    for keys, text, _ in REASONS:
        if any(k in tail for k in keys):
            return text, tail, False
    err = [l for l in lines if l.strip() and ("Error" in l or "Exception" in l) and "##[error]Process completed" not in l]
    if any("Traceback" in l for l in lines):
        return "کوڈ کی خرابی: " + (err[-1].strip()[:140] if err else "Traceback"), tail, True
    return "وجہ واضح نہیں" + (f": {err[-1].strip()[:120]}" if err else ""), tail, False


def engineer(name: str, run: dict, reason: str, tail: str, st: dict) -> str:
    """کوڈ کی خرابی → جیمنائی انجینئر کو Issue (حل Pull Request بنے، ✅/❌ ٹیلیگرام پر)۔ دن میں زیادہ سے زیادہ 2۔"""
    tok = os.environ.get("ENGINEER_GH", "").strip()
    day = dt.datetime.now(RIYADH).strftime("%Y-%m-%d")
    q = st.setdefault("_engineer", {})
    if not tok or q.get(day, 0) >= 2:
        return ""
    body = (f"🔧 نگران نے خود بھیجا: «{name}» ناکام ہوا۔\n\nوجہ: {reason}\nرن: {run['html_url']}\n\n"
            f"لاگ کا آخری حصہ:\n```\n{tail[-6000:]}\n```\n\n"
            "براہِ کرم وجہ تلاش کریں اور کم سے کم تبدیلی سے ٹھیک کریں (AGENTS.md کے اصول)۔ صرف وہی بدلیں جو اس خرابی کے لیے ضروری ہو۔\n\n"
            "<!-- tg chat=OWNER msg=0 files= -->")
    try:
        i = api("repos/abdulbasitfarooqi313-sys/farooqi-ai-news-engine/issues", tok,
                {"title": f"خودکار: «{name}» کی خرابی", "body": body, "labels": ["gemini"]})
        q[day] = q.get(day, 0) + 1
        return i.get("html_url", "")
    except Exception as e:
        print("engineer issue:", type(e).__name__, getattr(e, "code", ""))
        return ""


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
        mine = (st.get(key) or {}).get("last")                  # ہماری اپنی دوبارہ کوشش (workflow_dispatch) کا وقت
        def ours(r: dict) -> bool:                             # ہاتھ سے چلائے نمونے/جانچ (19 نومبر: ٹیک نمونہ) نگرانی میں نہیں
            if r.get("event") != "workflow_dispatch":
                return True
            if not mine:
                return False
            c = dt.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
            return abs((c - dt.datetime.fromisoformat(mine)).total_seconds()) < 300
        done = [r for r in runs if r["status"] == "completed" and r["conclusion"] in ("success", "failure", "timed_out") and ours(r)]
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
                reason, tail, code = why(repo, last, TOK[tk])
                st[key] = s
                fix = engineer(name, last, reason, tail, st) if code and n == 0 else ""
                tell(f"⚠️ «{name}» ناکام ہوا۔\nوجہ: {reason}\n🔁 تقریباً {hhmm(due)} (سعودی) پر خود دوبارہ کوشش ہو گی ({n + 1}/{len(DELAYS)})"
                     + (" — مگر کوٹا ختم ہو تو شاید کل ہی چلے" if "کوٹا" in reason else "") + "۔ آپ کو کچھ نہیں کرنا۔"
                     + (f"\n🤖 کوڈ کی خرابی جیمنائی انجینئر کو دے دی — حل بنے گا تو «Farooqi Gemini» پر ✅/❌ آئے گا۔" if fix else ""))
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
