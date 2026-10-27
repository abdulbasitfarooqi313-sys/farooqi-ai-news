#!/usr/bin/env bash
# مرد اینکر کی لپ سنگ کا تجربہ (Wav2Lip، مفت، CPU پر)
set -euo pipefail
OUT=out; mkdir -p $OUT w
get() { f=$1; shift; for u in "$@"; do echo "try $u"; curl -fsSL --retry 2 -o "$f" "$u" && [ $(stat -c%s "$f") -gt 1000000 ] && return 0; done; return 1; }
get w/wav2lip_gan.pth \
  https://huggingface.co/Nekochu/Wav2Lip/resolve/main/wav2lip_gan.pth \
  https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints/wav2lip_gan.pth \
  https://huggingface.co/numz/wav2lip_studio/resolve/main/Wav2lip/wav2lip_gan.pth \
  || { curl -s "https://huggingface.co/api/models?search=wav2lip&limit=30" | head -c 4000; exit 1; }
get Wav2Lip/face_detection/detection/sfd/s3fd.pth \
  https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth \
  https://huggingface.co/camenduru/Wav2Lip/resolve/main/face_detection/detection/sfd/s3fd.pth \
  https://huggingface.co/Nekochu/Wav2Lip/resolve/main/s3fd.pth

TEXT="${TEXT:-السلام علیکم، فاروقی اے آئی نیوز میں خوش آمدید۔ آج کی سب سے بڑی خبر یہ ہے کہ مصنوعی ذہانت کے نئے ماڈل اب اردو زبان کو پہلے سے کہیں بہتر سمجھنے لگے ہیں۔}"
edge-tts --voice ur-PK-AsadNeural --text "$TEXT" --write-media $OUT/say.mp3
ffmpeg -y -loglevel error -i $OUT/say.mp3 -ar 16000 -ac 1 $OUT/say.wav
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 $OUT/say.wav)

# آگے پیچھے چلا کر لمبا اور ہموار پس منظر
ffmpeg -y -loglevel error -i lab/ref.mp4 -filter_complex "[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1[v]" -map "[v]" -an -r 24 $OUT/pp.mp4
# صرف دائیں آدھا حصہ (مرد اینکر) تاکہ چہرہ پہچاننے والا خاتون کو نہ پکڑے
ffmpeg -y -loglevel error -i $OUT/pp.mp4 -vf "crop=512:592:512:0" $OUT/right.mp4

mkdir -p Wav2Lip/temp
( cd Wav2Lip && python inference.py --checkpoint_path ../w/wav2lip_gan.pth --face ../$OUT/right.mp4 \
    --audio ../$OUT/say.wav --outfile ../$OUT/right_sync.mp4 --pads 0 15 0 0 --resize_factor 1 )

ffmpeg -y -loglevel error -stream_loop -1 -i $OUT/pp.mp4 -i $OUT/right_sync.mp4 \
  -filter_complex "[0:v][1:v]overlay=512:0:shortest=1[v]" -map "[v]" -map 1:a -t "$DUR" \
  -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac $OUT/lipsync-test.mp4
ls -la $OUT
