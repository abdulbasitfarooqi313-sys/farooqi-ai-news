import re, requests
B = "https://farooqiainews.blogspot.com"
H = {"User-Agent": "Mozilla/5.0"}
def t(html): m = re.search(r"<title>(.*?)</title>", html, re.S); return (m.group(1).strip()[:60] if m else "-")
r = requests.get(B + "/", headers=H, timeout=30)
print("BLOG home", r.status_code, "| theme:", "ours" if "yt-cta" in r.text else "OTHER", "|", t(r.text))
for p in ["about", "contact", "privacy-policy", "terms", "disclaimer"]:
    x = requests.get(f"{B}/p/{p}.html", headers=H, timeout=30)
    print("BLOG", p, x.status_code, "|", t(x.text))
j = requests.get(B + "/feeds/pages/default?alt=json", headers=H, timeout=30)
try:
    for e in j.json()["feed"].get("entry", []):
        link = next(l["href"] for l in e["link"] if l["rel"] == "alternate")
        print("BLOG page", e["title"]["$t"], "->", link)
except Exception as ex:
    print("BLOG pages feed", j.status_code, ex)
