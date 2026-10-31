"""ایک بار (6): شائع/شیڈول پوسٹس میں یوٹیوب iframe کی جگہ div (Blogger اب ہماری صاف تصویر کو پوسٹ کی تصویر بنائے گا)"""
import re, sys
sys.path.insert(0, ".")
import requests
from news import blog
from news.base import read_json
tok = blog._token(); bid = blog._blog_id(tok); h = {"Authorization": f"Bearer {tok}"}
RX = re.compile(r'<iframe[^>]+youtube\.com/embed/([\w-]+)[^>]*>\s*</iframe>')
for key, v in read_json(blog.STATE).get("posts", {}).items():
    g = requests.get(f"{blog.API}/blogs/{bid}/posts/{v['id']}", headers=h, timeout=30).json()
    c = g.get("content", "")
    c2 = RX.sub(lambda m: f'<div class="yt-embed" data-yt="{m.group(1)}" style="text-align:center;margin:10px 0"><a href="https://youtu.be/{m.group(1)}" target="_blank" rel="noopener">▶ ویڈیو یوٹیوب پر دیکھیں</a></div>', c)
    if c2 != c:
        r = requests.patch(f"{blog.API}/blogs/{bid}/posts/{v['id']}", headers=h, json={"title": g["title"], "content": c2, "labels": g.get("labels", [])}, timeout=60)
        print("BLOG embed", key, r.status_code)
