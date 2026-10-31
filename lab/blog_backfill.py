"""ایک بار (5): فلیش اور ٹریلر کی پوسٹ میں یوٹیوب کی دھندلی تصویر کی جگہ ہماری صاف تصویر (media/)"""
import re, sys
sys.path.insert(0, ".")
import requests
from news import blog, thumbs
from news.base import read_json
tok = blog._token(); bid = blog._blog_id(tok); h = {"Authorization": f"Bearer {tok}"}
posts = read_json(blog.STATE).get("posts", {})
for key in ("2026-10-29-f", "trailer"):
    pid = posts[key]["id"]
    g = requests.get(f"{blog.API}/blogs/{bid}/posts/{pid}", headers=h, timeout=30).json()
    c = re.sub(r'src="https://i\.ytimg\.com/vi/[^"]+"', f'src="{thumbs.RAW}{key}.jpg"', g["content"], count=1)
    r = requests.patch(f"{blog.API}/blogs/{bid}/posts/{pid}", headers=h, json={"title": g["title"], "content": c, "labels": g.get("labels", [])}, timeout=60)
    print("BLOG img", key, r.status_code, thumbs.RAW + key + ".jpg" in c)
