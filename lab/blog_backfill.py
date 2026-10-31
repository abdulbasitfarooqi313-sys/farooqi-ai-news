"""ایک بار (3): فلیش پوسٹ کی تصویر — شارٹ کی maxres تصویر نہیں ہوتی، hqdefault لگائیں"""
import sys
sys.path.insert(0, ".")
import requests
from news import blog
from news.base import read_json
tok = blog._token(); bid = blog._blog_id(tok); h = {"Authorization": f"Bearer {tok}"}
st = read_json(blog.STATE)
pid = st["posts"]["2026-10-29-f"]["id"]
g = requests.get(f"{blog.API}/blogs/{bid}/posts/{pid}", headers=h, timeout=30).json()
c = g["content"].replace("/maxresdefault.jpg", "/hqdefault.jpg")
r = requests.patch(f"{blog.API}/blogs/{bid}/posts/{pid}", headers=h, json={"title": g["title"], "content": c, "labels": g.get("labels", [])}, timeout=60)
print("BLOG flash thumb", r.status_code)
