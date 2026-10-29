import os, requests
r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
    "client_id": os.environ["YOUTUBE_CLIENT_ID"].strip(), "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"].strip(),
    "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"].strip(), "grant_type": "refresh_token"})
j = r.json()
print("TOK", r.status_code, j.get("error"), "|", j.get("error_description"))
