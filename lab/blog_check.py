import re, requests
B = "https://farooqiainews.blogspot.com"
H = {"User-Agent": "Mozilla/5.0"}
for p in ["about", "contact", "privacy-policy", "terms", "disclaimer"]:
    x = requests.get(f"{B}/p/{p}.html", headers=H, timeout=30).text
    m = re.search(r"id='postbody'>(.*?)</div>\s*</article>", x, re.S) or re.search(r'id="postbody">(.*?)</div>', x, re.S)
    body = m.group(1) if m else ""
    esc = "&lt;div" in x or "&lt;p&gt;" in x or "&lt;h2" in x
    print("BLOG", p, "| body chars", len(body), "| escaped-html:", esc, "| h2:", body.count("<h2"), "| starts:", re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", body))[:70])
h = requests.get(B + "/", headers=H, timeout=30).text
for a in re.findall(r"<nav class='nav'>(.*?)</nav>", h, re.S)[:1]:
    for href, txt in re.findall(r"href='([^']+)'[^>]*>([^<]+)<", a):
        print("BLOG nav", txt, "->", href)
