"""
video_generator.py
-------------------
Bir konu metninden otomatik olarak kısa video üreten motor.

Akış:
1. generate_script()   -> Groq API ile konuyu sahnelere bölünmüş bir senaryoya çevirir (JSON)
2. generate_images()   -> Her sahne için Pollinations.ai ile görsel üretir
3. generate_voiceover() -> edge-tts ile Türkçe seslendirme üretir (sahne başına ayrı ses dosyası)
4. assemble_video()    -> FFmpeg ile görselleri (Ken Burns efektiyle) + sesi + altyazıyı birleştirip
                          dikey (9:16) bir video olarak dışa aktarır.

Ortam değişkenleri (.env dosyasına yazılır):
    GROQ_API_KEY   -> https://console.groq.com adresinden ücretsiz alınır
    TTS_VOICE      -> Örn: "tr-TR-AhmetNeural" veya "tr-TR-EmelNeural" (kadın)
"""

import os
import json
import uuid
import asyncio
import subprocess
import textwrap
from pathlib import Path

import requests
import edge_tts

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"
TTS_VOICE = os.environ.get("TTS_VOICE", "tr-TR-EmelNeural")

BASE_DIR = Path(__file__).parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

VIDEO_W, VIDEO_H = 1080, 1920  # dikey format (Reels/TikTok/Shorts)


# --------------------------------------------------------------------------
# 1) SENARYO ÜRETİMİ
# --------------------------------------------------------------------------
def generate_script(topic: str, n_scenes: int = 6) -> list[dict]:
    """
    Konu metnini alır, Groq API ile n_scenes adet sahneye böler.
    Her sahne: {"narration": "...", "image_prompt": "..."}
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY tanımlı değil (.env dosyasını kontrol et)")

    system_prompt = (
        "Sen kısa sosyal medya videoları (TikTok/Reels/Shorts) için senarist olarak çalışıyorsun. "
        "Sana verilen konuyu, izleyiciyi ilk 2 saniyede yakalayan, akıcı ve meraklandırıcı bir anlatıma "
        "dönüştür. SADECE geçerli JSON döndür, başka hiçbir açıklama ekleme."
    )
    user_prompt = f"""
Konu: "{topic}"

Bu konuyu tam olarak {n_scenes} sahneye böl. Her sahne için:
- "narration": Türkçe, doğal konuşma dilinde, seslendirilecek 1-2 cümlelik metin (max 25 kelime)
- "image_prompt": Bu sahneyi görsel olarak anlatan, İNGİLİZCE, detaylı bir AI görsel üretim prompt'u
  (sinematik, yüksek kalite, ışıklandırma detayları içersin)

Sadece şu formatta JSON döndür:
{{
  "title": "video başlığı",
  "scenes": [
    {{"narration": "...", "image_prompt": "..."}},
    ...
  ]
}}
"""
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)
    return data


# --------------------------------------------------------------------------
# 2) GÖRSEL ÜRETİMİ (Pollinations.ai - ücretsiz, key gerekmez)
# --------------------------------------------------------------------------
def generate_images(scenes: list[dict], job_id: str) -> list[Path]:
    image_paths = []
    for i, scene in enumerate(scenes):
        prompt = scene["image_prompt"]
        url = (
            f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}"
            f"?width={VIDEO_W}&height={VIDEO_H}&nologo=true&seed={uuid.uuid4().int % 100000}"
        )
        out_path = TEMP_DIR / f"{job_id}_scene{i}.jpg"
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        image_paths.append(out_path)
    return image_paths


# --------------------------------------------------------------------------
# 3) SESLENDİRME (edge-tts - ücretsiz)
# --------------------------------------------------------------------------
async def _tts_single(text: str, out_path: Path):
    communicate = edge_tts.Communicate(text, TTS_VOICE)
    await communicate.save(str(out_path))


def generate_voiceover(scenes: list[dict], job_id: str) -> list[Path]:
    audio_paths = []
    for i, scene in enumerate(scenes):
        out_path = TEMP_DIR / f"{job_id}_scene{i}.mp3"
        asyncio.run(_tts_single(scene["narration"], out_path))
        audio_paths.append(out_path)
    return audio_paths


def _get_audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


# --------------------------------------------------------------------------
# 4) VİDEO BİRLEŞTİRME (FFmpeg)
# --------------------------------------------------------------------------
def assemble_video(scenes: list[dict], image_paths: list[Path], audio_paths: list[Path],
                    job_id: str, title: str) -> Path:
    """
    Her sahne için: görseli hafif zoom (Ken Burns) efektiyle, sahnenin ses süresi kadar göster,
    altına o sahnenin seslendirmesini koy. Sonra hepsini tek videoda birleştir.
    """
    clip_paths = []
    for i, (img, audio) in enumerate(zip(image_paths, audio_paths)):
        duration = _get_audio_duration(audio) + 0.3  # ufak pay
        clip_out = TEMP_DIR / f"{job_id}_clip{i}.mp4"

        # Ken Burns (yavaş zoom-in) efekti + ses ekleme
        zoom_expr = f"zoompan=z='min(zoom+0.0008,1.15)':d={int(duration*25)}:s={VIDEO_W}x{VIDEO_H}:fps=25"
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(audio),
            "-filter_complex", f"[0:v]{zoom_expr}[v]",
            "-map", "[v]", "-map", "1:a",
            "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(clip_out)
        ], check=True, capture_output=True)
        clip_paths.append(clip_out)

    # Tüm klipleri birleştirmek için concat listesi
    concat_file = TEMP_DIR / f"{job_id}_concat.txt"
    concat_file.write_text("\n".join(f"file '{p.resolve()}'" for p in clip_paths))

    final_path = OUTPUT_DIR / f"{job_id}.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy", str(final_path)
    ], check=True, capture_output=True)

    # Geçici dosyaları temizle
    for p in clip_paths + image_paths + audio_paths + [concat_file]:
        p.unlink(missing_ok=True)

    return final_path


# --------------------------------------------------------------------------
# ANA FONKSİYON — bot.py buradan çağırır
# --------------------------------------------------------------------------
def create_video_from_topic(topic: str) -> Path:
    job_id = uuid.uuid4().hex[:10]
    script = generate_script(topic)
    scenes = script["scenes"]
    title = script.get("title", topic)

    images = generate_images(scenes, job_id)
    audios = generate_voiceover(scenes, job_id)
    final_video = assemble_video(scenes, images, audios, job_id, title)
    return final_video


if __name__ == "__main__":
    import sys
    topic = " ".join(sys.argv[1:]) or "Uzayın en garip 5 gerçeği"
    path = create_video_from_topic(topic)
    print(f"Video hazır: {path}")
