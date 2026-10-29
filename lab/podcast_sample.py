"""«اے آئی بیٹھک» — 2 منٹ کا نمونہ: سارہ اور احمد کی گفتگو (جیمنائی، ایک ہی درخواست میں دو آوازیں)"""
import base64, json, re, subprocess, sys, wave
from pathlib import Path
import requests
from news.base import generate_json, gemini_key
from news import bulletin as B

items = B.fetch(max_age_h=24 * 7)
listing = "\n".join(f"[{i+1}] {it['title']} — {it['source']}: {it['summary'][:300]}" for i, it in enumerate(items[:40]))
SYS = """آپ اردو پوڈکاسٹ «اے آئی بیٹھک» (فاروقی اے آئی نیوز) کے اسکرپٹ رائٹر ہیں۔ میزبان: سارہ (خاتون، سوال اٹھاتی ہیں، عام ناظر کی نمائندہ) اور احمد (مرد، ٹیک کے ماہر، آسان مثالوں سے سمجھاتے ہیں)۔
دی گئی خبروں میں سے اس ہفتے کا سب سے دلچسپ ایک موضوع چنیں۔ گفتگو قدرتی، دوستانہ، بے تکلف مگر شائستہ اردو میں — چھوٹے جملے، ردِعمل («اچھا!»، «بالکل»، «یہ تو کمال ہے»)، ایک دوسرے کی بات آگے بڑھانا۔
سختی سے: صرف دی گئی خبروں کے حقائق؛ کوئی عدد، نام یا دعویٰ اپنی طرف سے نہیں۔ انگریزی نام اردو رسم الخط میں۔ کوئی بریکٹ، ایموجی یا ہدایت نہیں — صرف بولا جانے والا متن۔
یہ پہلے 2 منٹ ہیں: سارہ کا خوش آمدید، موضوع کا تعارف، 8 تا 12 باریاں، کل تقریباً 260 تا 300 الفاظ، آخر میں سارہ کا ایک سوال جس پر بات جاری رہے۔
صرف JSON: {"topic": "موضوع (اردو)", "lines": [{"s": "Sarah" یا "Ahmed", "t": "متن"}]}"""
d = generate_json(SYS, "اس ہفتے کی AI خبریں:\n" + listing)
lines = [l for l in d["lines"] if l.get("t", "").strip() and l.get("s") in ("Sarah", "Ahmed")]
conv = "\n".join(f"{l['s']}: {l['t'].strip()}" for l in lines)
prompt = ("TTS the following Urdu podcast conversation between Sarah and Ahmed. Natural, warm, friendly podcast tone, "
          "conversational pace:\n\n" + conv)
def tts(prompt):
  return requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent",
                  params={"key": gemini_key()}, timeout=300, json={
                      "contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"multiSpeakerVoiceConfig": {"speakerVoiceConfigs": [
                          {"speaker": "Sarah", "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}},
                          {"speaker": "Ahmed", "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Orus"}}}]}}}})
import time
for attempt, pr in enumerate(["TTS the following conversation between Sarah and Ahmed:\n" + conv, conv]):
    r = tts(pr)
    c = (r.json().get("candidates") or [{}])[0] if r.ok else {}
    if r.ok and c.get("content"):
        break
    print("TTS_TRY", attempt, r.status_code, json.dumps(c.get("finishReason")), r.text[:200].replace("\n", " "))
    time.sleep(10)
if not r.ok or not c.get("content"):
    print("TTS_FAIL", r.status_code, r.text[:300]); sys.exit(1)
part = c["content"]["parts"][0]["inlineData"]
rate = int(re.search(r"rate=(\d+)", part.get("mimeType", "rate=24000")).group(1))
with wave.open("pod.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(base64.b64decode(part["data"]))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "pod.wav", "-af", "loudnorm=I=-16:TP=-1.5", "-c:a", "aac", "-b:a", "128k",
                "podcast-namuna.m4a"], check=True)
Path("pod_script.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
print("TOPIC", d.get("topic"), "| lines", len(lines))
