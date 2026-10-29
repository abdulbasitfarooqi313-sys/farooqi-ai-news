import json, requests
from news.base import gemini_key
U = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
def ms(text, m="gemini-2.5-flash-preview-tts"):
    return {"contents": [{"parts": [{"text": text}]}], "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"multiSpeakerVoiceConfig": {"speakerVoiceConfigs": [
        {"speaker": "Sarah", "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}},
        {"speaker": "Ahmed", "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Orus"}}}]}}}}
ss = {"contents": [{"parts": [{"text": "Read the following Urdu text aloud:\n\nالسلام علیکم، یہ ایک جانچ ہے۔"}]}],
      "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Kore"}}}}}
tests = [("single-urdu", "gemini-2.5-flash-preview-tts", ss),
         ("multi-urdu-short", "gemini-2.5-flash-preview-tts", ms("TTS the following conversation between Sarah and Ahmed:\nSarah: السلام علیکم احمد، آج ہم کس موضوع پر بات کریں گے؟\nAhmed: وعلیکم السلام سارہ، آج بات ہوگی مصنوعی ذہانت پر۔")),
         ("multi-english", "gemini-2.5-flash-preview-tts", ms("TTS the following conversation between Sarah and Ahmed:\nSarah: Hello Ahmed, what are we discussing today?\nAhmed: Hi Sarah, today we talk about AI.")),
         ("multi-urdu-pro", "gemini-2.5-pro-preview-tts", ms("TTS the following conversation between Sarah and Ahmed:\nSarah: السلام علیکم احمد، آج ہم کس موضوع پر بات کریں گے؟\nAhmed: وعلیکم السلام سارہ، آج بات ہوگی مصنوعی ذہانت پر۔"))]
for name, m, body in tests:
    r = requests.post(U.format(m=m), params={"key": gemini_key()}, json=body, timeout=180)
    c = (r.json().get("candidates") or [{}])[0] if r.ok else {}
    print("DIAG", name, r.status_code, "AUDIO" if c.get("content") else c.get("finishReason"), "" if r.ok else r.text[:150].replace("\n", " "))
