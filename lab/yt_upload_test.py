"""ایک بار کی جانچ: 6 سیکنڈ کی سادہ ویڈیو یوٹیوب پر PRIVATE اپلوڈ (کبھی پبلک نہیں ہوتی)، تھمب نیل اور پلے لسٹ کی جانچ۔"""
import subprocess
import sys
from pathlib import Path

from news import youtube as yt

v, t = Path("t.mp4"), Path("t.jpg")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x0a1544:s=1280x720:d=6",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", str(v)], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0xe2b84f:s=1280x720", "-frames:v", "1", str(t)], check=True)
if not yt.enabled():
    print("❌ چابیاں نہیں ملیں"); sys.exit(1)
tok = yt._token()
r = yt.upload(v, t, "TEST — private upload check (delete me)", "Private test of the Farooqi AI News uploader.", ["test"], playlist=False)
print("📃 پلے لسٹ:", yt._playlist(tok))
print(f"✅ Private اپلوڈ ہو گیا: {r['url']}")
for n in r["notes"]:
    print("⚠️", n)
import requests
j = requests.get(f"{yt.API}/videos", params={"part": "status,snippet", "id": r["id"]}, headers=yt._h(tok), timeout=30).json()
s = j["items"][0]
print("حیثیت:", s["status"]["privacyStatus"], "| زمرہ:", s["snippet"]["categoryId"], "| زبان:", s["snippet"].get("defaultAudioLanguage"),
      "| synthetic:", s["status"].get("containsSyntheticMedia"))
