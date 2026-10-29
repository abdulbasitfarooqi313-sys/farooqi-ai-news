import os, requests
k = os.environ.get("GEMINI_BACKUP_KEY", "").strip()
if not k:
    print("BK ❌ GEMINI_BACKUP_KEY نہیں ملی"); raise SystemExit(1)
r = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent",
                  params={"key": k}, timeout=120, json={"contents": [{"parts": [{"text": "Read the following Urdu text aloud:\n\nالسلام علیکم، فاروقی اے آئی نیوز میں خوش آمدید۔"}]}],
                  "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Kore"}}}}})
ok = r.ok and "inlineData" in r.text
fr = ((r.json().get("candidates") or [{}])[0].get("finishReason") if r.ok else "")
print("BK", "✅ آواز بنی — الگ کوٹا" if ok else f"❌ {r.status_code} finish={fr} " + r.text[:160].replace(chr(10), " "))
m = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent", params={"key": k}, timeout=60,
                  json={"contents": [{"parts": [{"text": "Reply OK"}]}]})
print("BK text", m.status_code, m.text[:100].replace(chr(10), " "))
