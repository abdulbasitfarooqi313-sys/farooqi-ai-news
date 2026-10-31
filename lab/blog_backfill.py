"""ایک بار (4): شائع شدہ پوسٹس کی تصویر روشن (پوسٹ کے اندر ہی — تھیم بدلے بغیر)"""
import re, sys
sys.path.insert(0, ".")
import requests
from news import blog
from news.base import read_json
tok = blog._token(); bid = blog._blog_id(tok); h = {"Authorization": f"Bearer {tok}"}
F = "filter:brightness(1.12) contrast(1.15) saturate(1.3)"
for key, v in read_json(blog.STATE).get("posts", {}).items():
    g = requests.get(f"{blog.API}/blogs/{bid}/posts/{v['id']}", headers=h, timeout=30).json()
    c = g.get("content", "")
    if F in c:
        continue
    c2 = re.sub(r'(<img[^>]+style=")([^"]*)"', lambda m: m.group(1) + m.group(2).rstrip(";") + ";" + F + '"', c, count=1)
    r = requests.patch(f"{blog.API}/blogs/{bid}/posts/{v['id']}", headers=h, json={"title": g["title"], "content": c2, "labels": g.get("labels", [])}, timeout=60)
    print("BLOG bright", key, r.status_code)
