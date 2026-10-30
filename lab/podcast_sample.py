"""«اے آئی بیٹھک» — 2 منٹ کا نمونہ: سارہ اور احمد کی گفتگو (جیمنائی، ایک ہی درخواست میں دو آوازیں)"""
import base64, json, os, re, subprocess, sys, wave
from pathlib import Path
import requests
from news.base import generate_json, gemini_key
from news import bulletin as B

items = B.fetch(max_age_h=24 * 7)
listing = "\n".join(f"[{i+1}] {it['title']} — {it['source']}: {it['summary'][:300]}" for i, it in enumerate(items[:40]))
SYS = """آپ اردو پوڈکاسٹ «اے آئی بیٹھک» (فاروقی اے آئی نیوز) کے اسکرپٹ رائٹر ہیں۔ میزبان: سارہ (خاتون، سوال اٹھاتی ہیں، عام ناظر کی نمائندہ) اور احمد (مرد، ٹیک کے ماہر، آسان مثالوں سے سمجھاتے ہیں)۔
دی گئی خبروں میں سے اس ہفتے کا سب سے دلچسپ ایک موضوع چنیں۔ گفتگو قدرتی، دوستانہ، بے تکلف مگر شائستہ اردو میں — چھوٹے جملے، ردِعمل («اچھا!»، «بالکل»، «یہ تو کمال ہے»)، ایک دوسرے کی بات آگے بڑھانا۔
سختی سے: صرف دی گئی خبروں کے حقائق؛ کوئی عدد، نام یا دعویٰ اپنی طرف سے نہیں۔ انگریزی نام اردو رسم الخط میں۔ سرمایہ کاری کا کوئی مشورہ نہیں (کون سا شیئر یا کرپٹو خریدیں/بیچیں وغیرہ) — صرف خبر اور اس کا عام فہم مطلب۔ کوئی بریکٹ، ایموجی یا ہدایت نہیں — صرف بولا جانے والا متن۔
یہ پہلے 2 منٹ ہیں: سارہ کا خوش آمدید، موضوع کا تعارف، 8 تا 12 باریاں، کل تقریباً 260 تا 300 الفاظ، آخر میں سارہ کا ایک سوال جس پر بات جاری رہے۔
صرف JSON: {"topic": "موضوع (اردو)", "lines": [{"s": "Sarah" یا "Ahmed", "t": "متن"}]}"""
d = generate_json(SYS, "اس ہفتے کی AI خبریں:\n" + listing)
lines = [l for l in d["lines"] if l.get("t", "").strip() and l.get("s") in ("Sarah", "Ahmed")]
conv = "\n".join(f"{l['s']}: {l['t'].strip()}" for l in lines)
prompt = ("TTS the following Urdu podcast conversation between Sarah and Ahmed. Natural, warm, friendly podcast tone, "
          "conversational pace:\n\n" + conv)
def tts(prompt):
  return requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent",
                  params={"key": os.environ.get("GEMINI_BACKUP_KEY") or gemini_key()}, timeout=300, json={
                      "contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"multiSpeakerVoiceConfig": {"speakerVoiceConfigs": [
                          {"speaker": "Sarah", "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}},
                          {"speaker": "Ahmed", "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Orus"}}}]}}}})
import os, time, asyncio
if os.environ.get("POD_TTS") == "edge":                 # مائیکروسافٹ کی مفت اردو آوازیں (کوئی کوٹا نہیں) — مالک کی ہدایت پر نمونے کے لیے
    import edge_tts
    V = {"Sarah": "ur-PK-UzmaNeural", "Ahmed": "ur-PK-AsadNeural"}
    parts = []
    for i, l in enumerate(lines):
        mp3 = f"e{i:02d}.mp3"
        asyncio.run(edge_tts.Communicate(l["t"].strip(), V[l["s"]], rate="+0%").save(mp3))
        wav = f"e{i:02d}.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-af", "apad=pad_dur=0.3", "-ar", "24000", "-ac", "1", wav], check=True)
        parts.append(wav)
    Path("e.txt").write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "e.txt", "pod.wav"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "pod.wav", "-af", "loudnorm=I=-16:TP=-1.5", "-c:a", "aac", "-b:a", "128k",
                    "podcast-namuna.m4a"], check=True)
    Path("pod_script.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TOPIC", d.get("topic"), "| lines", len(lines), "| edge voices")
    sys.exit(0)
CH = int(os.environ.get("POD_CHUNK") or -(-len(lines) // 3))   # زیادہ سے زیادہ 3 درخواستیں
pcm, rate = b"", 24000
for n, k in enumerate(range(0, len(lines), CH)):
    if n:
        time.sleep(22)                                   # مفت حد: فی منٹ 3 درخواستیں
    part_txt = "\n".join(f"{l['s']}: {l['t'].strip()}" for l in lines[k:k + CH])
    c = {}
    for attempt in range(1):                             # کوئی دوبارہ کوشش نہیں — کوٹا بچانا
        r = tts("TTS the following conversation between Sarah and Ahmed:\n" + part_txt)
        c = (r.json().get("candidates") or [{}])[0] if r.ok else {}
        if r.ok and c.get("content"):
            break
        print("TTS_TRY", k, attempt, r.status_code, json.dumps(c.get("finishReason")), r.text[:150].replace("\n", " "))
        if r.status_code == 429:
            sys.exit(1)
        time.sleep(8)
    if not c.get("content"):
        print("TTS_FAIL chunk", k); sys.exit(1)
    p_ = c["content"]["parts"][0]["inlineData"]
    rate = int(re.search(r"rate=(\d+)", p_.get("mimeType", "rate=24000")).group(1))
    pcm += base64.b64decode(p_["data"]) + b"\x00\x00" * int(rate * 0.35)
print("TTS_CALLS ok, chunks", (len(lines) + CH - 1) // CH)
with wave.open("pod.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "pod.wav", "-af", "loudnorm=I=-16:TP=-1.5", "-c:a", "aac", "-b:a", "128k",
                "podcast-namuna.m4a"], check=True)
Path("pod_script.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
print("TOPIC", d.get("topic"), "| lines", len(lines))
