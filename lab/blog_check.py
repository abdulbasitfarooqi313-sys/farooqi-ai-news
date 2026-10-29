import re, requests
B = "https://farooqiainews.blogspot.com"
x = requests.get(f"{B}/p/about.html", headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
i = x.find("postbody")
print("BLOG idx", i, "len", len(x))
seg = re.sub(r"\s+", " ", x[i - 200:i + 900]) if i > 0 else re.sub(r"\s+", " ", x[x.find("<main"):x.find("<main") + 900])
for k in range(0, len(seg), 220):
    print("BLOG", seg[k:k + 220])
