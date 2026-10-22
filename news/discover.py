"""یوٹیوب تلاش سے مقابل چینل خود ڈھونڈنا (مفت، بغیر چابی) — نتیجہ state/discover.json"""
import json
import re
import sys
from collections import defaultdict
from urllib.parse import quote

import requests

from .base import ROOT

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9,ur;q=0.8"}
NICHES = {
    "news": ["AI news Urdu", "AI news Hindi", "مصنوعی ذہانت خبریں", "AI news today", "AI tools Urdu", "ChatGPT Urdu"],
    "toolscape": ["AI tools tutorial", "best free AI tools", "how to use ChatGPT tutorial", "AI tools for productivity",
                  "Excel AI tutorial", "AI video editing tutorial"],
    "nawa": ["تفسیر قرآن اردو", "Quran tafseer Urdu", "Tafseer Usmani", "dars e quran urdu", "quran urdu tarjuma tafseer",
             "surah tafseer urdu"],
}


def _views(t: str) -> int:
    m = re.search(r"([\d.,]+)\s*([KMB]?)", t.replace(",", ""))
    if not m:
        return 0
    n = float(m.group(1))
    return int(n * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)])


def search(q: str) -> list:
    r = requests.get(f"https://www.youtube.com/results?search_query={quote(q)}&sp=EgIIBQ%3D%3D",  # اس سال
                     headers=UA, cookies={"CONSENT": "YES+1"}, timeout=30)
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", r.text, re.S)
    data = json.loads(m.group(1)) if m else {}
    out = []

    def walk(o):
        if isinstance(o, dict):
            v = o.get("videoRenderer")
            if v:
                try:
                    own = v["ownerText"]["runs"][0]
                    out.append({"channel": own["text"],
                                "id": own["navigationEndpoint"]["browseEndpoint"]["browseId"],
                                "handle": own["navigationEndpoint"]["browseEndpoint"].get("canonicalBaseUrl", ""),
                                "title": v["title"]["runs"][0]["text"],
                                "views": _views(v.get("viewCountText", {}).get("simpleText", "0"))})
                except Exception:
                    pass
            for x in o.values():
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(data)
    return out


def main():
    res = {}
    for niche, qs in NICHES.items():
        agg = defaultdict(lambda: {"hits": 0, "views": 0, "titles": []})
        for q in qs:
            try:
                for v in search(q):
                    a = agg[v["id"]]
                    a.update(channel=v["channel"], handle=v["handle"])
                    a["hits"] += 1
                    a["views"] += v["views"]
                    if len(a["titles"]) < 3:
                        a["titles"].append(f"{v['title']} ({v['views']:,})")
            except Exception as e:
                print(niche, q, e)
        top = sorted(agg.items(), key=lambda kv: -(kv[1]["views"] * (1 + kv[1]["hits"])))[:25]
        res[niche] = [{"id": k, **v} for k, v in top]
        print(niche, len(agg))
    (ROOT / "state" / "discover.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
