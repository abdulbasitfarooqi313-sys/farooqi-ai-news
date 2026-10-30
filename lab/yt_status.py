import os, sys, requests
sys.path.insert(0, ".")
from news import youtube as yt
tok = yt._token()
ids = "zcly-QYVNRo,SxyeAe7MZxg,BgEGtxhqne0,QBPSjzBz4sA"
j = requests.get("https://www.googleapis.com/youtube/v3/videos", params={"part": "status,snippet", "id": ids},
                 headers={"Authorization": f"Bearer {tok}"}, timeout=30).json()
for it in j.get("items", []):
    print("VID", it["id"], it["status"]["privacyStatus"], it["status"].get("publishAt"), it["snippet"]["title"][:50])
