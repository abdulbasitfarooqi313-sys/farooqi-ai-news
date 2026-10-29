import os, requests
k = os.environ.get("GEMINI_BACKUP_KEY", "").strip()
if not k:
    print("BK ❌ GEMINI_BACKUP_KEY نہیں ملی"); raise SystemExit(1)
r = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent",
                  params={"key": k}, timeout=120, json={"contents": [{"parts": [{"text": "Read the following Urdu text aloud:\n\nسلام"}]}],
                  "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Kore"}}}}})
ok = r.ok and "inlineData" in r.text
print("BK", "✅ آواز بنی — الگ کوٹا" if ok else f"❌ {r.status_code} {r.text[:160]}")
m = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent", params={"key": k}, timeout=60,
                  json={"contents": [{"parts": [{"text": "Reply OK"}]}]})
print("BK text", m.status_code)
