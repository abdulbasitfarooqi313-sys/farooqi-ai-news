"""یوٹیوب چابی کی جانچ — صرف چینل کا نام پڑھتا ہے، کچھ اپلوڈ نہیں کرتا۔ کوئی خفیہ قیمت لاگ میں نہیں چھپتی۔"""
import os
import sys

import requests

need = ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
missing = [k for k in need if not os.environ.get(k, "").strip()]
if missing:
    print("❌ Secret نہیں ملے:", ", ".join(missing))
    sys.exit(1)
for k in need:
    v = os.environ[k]
    if v != v.strip():
        print(f"⚠️ {k} کے شروع یا آخر میں خالی جگہ / نئی لائن ہے (کوڈ اسے ہٹا دیتا ہے)")

r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
    "client_id": os.environ["YOUTUBE_CLIENT_ID"].strip(),
    "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"].strip(),
    "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"].strip(),
    "grant_type": "refresh_token"})
if not r.ok:
    j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    print("❌ چابی سے رسائی نہیں ملی:", r.status_code, j.get("error"), "-", j.get("error_description"))
    sys.exit(1)
tok = r.json()
print("✅ چابی کام کر رہی ہے۔ اجازتیں:", tok.get("scope"))
c = requests.get("https://www.googleapis.com/youtube/v3/channels", timeout=30,
                 params={"part": "snippet,statistics", "mine": "true"},
                 headers={"Authorization": f"Bearer {tok['access_token']}"})
if not c.ok:
    print("❌ چینل نہیں پڑھا جا سکا:", c.status_code, c.text[:300])
    sys.exit(1)
items = c.json().get("items", [])
if not items:
    print("⚠️ اس اکاؤنٹ پر کوئی یوٹیوب چینل نہیں ملا")
    sys.exit(1)
for it in items:
    s = it["snippet"]
    print(f"📺 چینل: {s['title']}  |  {s.get('customUrl', '')}  |  id {it['id']}  |  ویڈیوز {it['statistics'].get('videoCount')}")
