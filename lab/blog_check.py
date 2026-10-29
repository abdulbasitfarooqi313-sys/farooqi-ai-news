import re, requests
B = "https://farooqiainews.blogspot.com"
H = {"User-Agent": "Mozilla/5.0"}
for u in ["/", "/p/about.html"]:
    x = requests.get(B + u, headers=H, timeout=30).text
    i = x.find("<main>")
    j = x.find("</main>")
    seg = re.sub(r"\s+", " ", x[i:j])
    print("BLOG", u, "main-len", len(seg), "| single:", "class='single'" in x or 'class="single"' in x, "| cards:", x.count("class='card") + x.count('class="card'), "| empty:", "ابھی یہاں کوئی خبر نہیں" in x)
    print("BLOG", u, seg[:600])
