import os, requests
k = os.environ.get("PIXABAY_API_KEY", "").strip()
if not k:
    print("PIX ❌ PIXABAY_API_KEY نہیں ملی"); raise SystemExit(1)
r = requests.get("https://pixabay.com/api/", params={"key": k, "q": "artificial intelligence", "orientation": "vertical", "per_page": 5}, timeout=30)
print("PIX", "✅ چابی کام کر رہی ہے — تصاویر:" if r.ok else "❌", r.json().get("totalHits") if r.ok else f"{r.status_code} {r.text[:120]}")
# 01:56:26
