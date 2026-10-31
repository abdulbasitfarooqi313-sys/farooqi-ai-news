"""ایک بار (2): مینو کے موضوعات بھرنا — پرانے 3 بلیٹن کی ہر خبر الگ پوسٹ (اصل تاریخ پر)، اور موجودہ پوسٹس نوٹو نستعلیق + موضوعاتی لیبل"""
import datetime as dt, json, sys
from pathlib import Path
sys.path.insert(0, ".")
import requests
from news import blog
from news.base import read_json, write_json

tok = blog._token(); bid = blog._blog_id(tok); h = {"Authorization": f"Bearer {tok}"}; API = blog.API
st = read_json(blog.STATE) if blog.STATE.exists() else {}
done = st.setdefault("stories", {})
import re
seen = []
def words(t): return set(w for w in re.findall(r"\w+", t) if len(w) > 2)
def dup(t): return any(len(words(t) & w) / max(1, len(words(t) | w)) > 0.4 for w in seen)

# 1) پرانے بلیٹن کی خبریں
for f in sorted(Path("lab/backfill").glob("script_*.json")):
    day = f.stem.split("_")[1]
    when = dt.datetime.fromisoformat(day + "T17:00:00+03:00")
    for i, x in enumerate(read_json(f).get("stories", [])):
        k = f"{day}-{i}"
        if k in done or dup(x["headline"]):
            print("BLOG skip (same story)", k); continue
        seen.append(words(x["headline"]))
        sp = blog.story_post(x)
        r = requests.post(f"{API}/blogs/{bid}/posts", params={"isDraft": "true"}, headers=h, timeout=60,
                          json={"kind": "blogger#post", "title": sp["title"], "labels": sp["labels"], "content": sp["html"]})
        if not r.ok:
            print("BLOG ❌", k, r.status_code, r.text[:150]); continue
        pid = r.json()["id"]
        pr = requests.post(f"{API}/blogs/{bid}/posts/{pid}/publish", headers=h, timeout=60,
                           params={"publishDate": when.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")})
        done[k] = pr.json().get("url", "") if pr.ok else f"draft {pid}"
        print("BLOG", k, sp["labels"], done[k])
write_json(blog.STATE, st)

# 2) موجودہ شائع پوسٹس: نستعلیق + لیبل
fl = read_json(Path("state/flash_last.json"))
extra = {"2026-10-29-f": ["اے آئی فلیش"] + blog.topics(" ".join(i["h"] + " " + i.get("country", "") for i in fl["items"]), [i.get("company") for i in fl["items"]]),
         "trailer": ["چینل کا تعارف"]}
for key, labs in extra.items():
    pid = st.get("posts", {}).get(key, {}).get("id")
    if not pid:
        continue
    g = requests.get(f"{API}/blogs/{bid}/posts/{pid}", headers=h, timeout=30).json()
    body = {"title": g["title"], "content": blog.wrap(g.get("content", "")), "labels": list(dict.fromkeys((g.get("labels") or []) + labs))}
    r = requests.patch(f"{API}/blogs/{bid}/posts/{pid}", headers=h, json=body, timeout=60)
    print("BLOG fix", key, r.status_code, body["labels"])
