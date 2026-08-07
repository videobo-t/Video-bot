""
video_oluşturucu.py
-------------------
Bir konu metninden otomatik olarak kısa video üreten motor.

AkÄ±ÅŸ:
1. created_script() -> Groq API ile sahneye sahnelere bir senaryoya evirir (JSON)
2. generate_images() -> Her sahne iÃ§in Pollinations.ai ile gÃ¶rsel Ã¼retir
3. created_voiceover() -> edge-tts ile Türkçe seslendirme Üretir (sahne baŸına ayrı ses dosyaları)
4. assemble_video() -> FFmpeg ile görselleri (Ken Burns efektiyle) + sesi + altyazıyı birleştirerek
                          dikey (9:16) bir video olarak aktarılır.

Ortam değișkenleri (.env dosyalarına yazılır):
    GROQ_API_KEY -> https://console.groq.com adresinden Ã¼cretsiz alÄ±nÄ±r
    TTS_VOICE -> Örn: "tr-TR-AhmetNeural" veya "tr-TR-EmelNeural" (kadın)
""

os'u içe aktar
json'u içe aktar
uuid'yi içe aktar
ithalat alt süreci
metin kaydırmayı içe aktar
from pathlib import Path

ithalat istekleri

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"
PIPER_VOICE = os.environ.get("PIPER_VOICE", "tr_TR-dfki-medium")

BASE_DIR = Path(__file__).parent
TEMP_DIR = BASE_DIR / "temp"
ÇIKTI_DİZİNİ = TEMEL_DİZİN / "çıktı"
TEMP_DIR.mkdir(exist_ok=True)
ÇIKTI_DİZİNİ.mkdir(exist_ok=True)

VIDEO_W, VIDEO_H = 1080, 1920 # dikey format (Reels/TikTok/Shorts)


# --------------------------------------------------------------------------
# 1) SENARYO ÃœRETÄ°MÄ°
# --------------------------------------------------------------------------
def generate_script(topic: str, n_scenes: int = 6) -> list[dict]:
    ""
    Konu metnini alır, Groq API ile n_scenes adet sahneye bağlar.
    Onun sahnesi: {"anlatım": "...", "görüntü_isteği": "..."}
    ""
    GROQ_API_KEY değilse:
        Raise RuntimeError("GROQ_API_KEY tanÄ±mlÄ± deÄŸil (.env dosyalarÄ±nÄ± kontrol et)")

    sistem_istem = (
        "Sen kÄ±sa sosyal medya videoları (TikTok/Reels/Shorts) ĩ§in senarist olarak çalıyorsun. "
        "Sana verilen bakış açısı, izleyiciyi ilk 2'de yakalayan, akıcı ve meraklanı bir anlatan"
        "dönüştür. SADECE geçerli JSON dördür, başka hişaklama ekleme."
    )
    kullanıcı_istem = f"""
Konu: "{topic}"

Bu konunun tam olarak {n_scenes} sahneye çıkması. Onun sahnesi:
- "anlatım": Türkçe, doğal konuşma dilinde, seslendirilecek 1-2 cümlelik metin (max 25 kelime)
- "image_prompt": Bu sahneyi güzel olarak anlatıyor, Şükran Günü, detaylı bir AI güzel Üretim istemi'u
  (sinematik, yüksek kalite, Şıklandrma detaylarıişersin)

Sadece JSON formatını kullanabilirsiniz:
{{
  "başlık": "video baŸlÄ±ÄŸÄ±",
  "sahneler": [
    {{"anlatım": "...", "resim_istemesi": "..."}},
    ...
  ]
}}
""
    yanıt = istekler.post(
        "https://api.groq.com/openai/v1/chat/completions",
        başlıklar={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": GROQ_MODEL,
            "mesajlar": [
                {"rol": "sistem", "içerik": sistem_istem},
                {"rol": "kullanıcı", "içerik": kullanıcı_istem},
            ],
            "Sıcaklık": 0.8,
            "yanıt_biçimi": {"tür": "json_nesnesi"},
        },
        zaman aşımı=60,
    )
    yanıt.durum_yükselt()
    içerik = yanıt.json()["seçenekler"][0]["mesaj"]["içerik"]
    veri = json.yükle(içerik)
    veri döndür


# --------------------------------------------------------------------------
# 2) GÜRSEL ÜRETİMİ (Pollinations.ai - Ã¼cretsiz, key gereksiz)
# --------------------------------------------------------------------------
def generate_images(scenes: list[dict], job_id: str) -> list[Path]:
    resim_yolları = []
    for i, scene in enumerate(scenes):
        istem = sahne["image_prompt"]
        url = (
            f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}"
            f"?width={VIDEO_W}&height={VIDEO_H}&nologo=true&seed={uuid.uuid4().int % 100000}"
        )
        çıkış_yolu = TEMP_DIR / f"{job_id}_scene{i}.jpg"
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        resim_yolları.ekle(çıkış_yolu)
    resim yollarını döndür


# --------------------------------------------------------------------------
# 3) SESLENDİRME (Piper TTS - yerel/offline nöral ses, Ã¼cretsiz, şifresiz, MIT lisanslÄ±)
# --------------------------------------------------------------------------
def generate_voiceover(scenes: list[dict], job_id: str) -> list[Path]:
    ses_yolları = []
    for i, scene in enumerate(scenes):
        çıkış_yolu = TEMP_DIR / f"{job_id}_scene{i}.wav"
        alt işlem.çalıştır(
            ["piper", "--model", PIPER_VOICE, "--output_file", str(out_path)],
            giriş=sahne["anlatım"],
            metin=Doğru,
            kontrol et=Doğru,
            capture_output=True,
        )
        ses_yolları.ekle(çıkış_yolu)
    ses yollarını döndür


def _get_audio_duration(path: Path) -> float:
    sonuç = alt işlem.çalıştır(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    float(result.stdout.strip()) döndürün.


# --------------------------------------------------------------------------
# 4) VİDEO BİRLEŞTİRME (FFmpeg)
# --------------------------------------------------------------------------
def assemble_video(scenes: list[dict], image_paths: list[Path], audio_paths: list[Path],
                    job_id: str, title: str) -> Yol:
    ""
    Her sahnede: gÃ¶rseli hafif zoom (Ken Burns) efektiyle, sahnenin ses şiddeti kadar gÃ¶ster,
    altina o sahnenin seslendirmesini koy. Sonra hepsini tek videoda birleştirir.
    ""
    kırpma_yolları = []
    for i, (img, audio) in enumerate(zip(image_paths, audio_paths)):
        süre = _get_audio_duration(audio) + 0.3 # ufak pay
        clip_out = TEMP_DIR / f"{job_id}_clip{i}.mp4"

        # Ken Burns (yakınlaştırma) efekti + ses ekleme
        zoom_expr = f"zoompan=z='min(zoom+0.0008,1.15)':d={int(duration*25)}:s={VIDEO_W}x{VIDEO_H}:fps=25"
        alt işlem.çalıştır([
            "ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(audio),
            "-filter_complex", f"[0:v]{zoom_expr}[v]",
            "-map", "[v]", "-map", "1:a",
            "-t", str(süre), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(clip_out)
        ], check=True, capture_output=True)
        clip_paths.append(clip_out)

    # Tüm klipleri birleştirmek için birleştirilmiş liste
    birleştirme_dosyası = TEMP_DIR / f"{job_id}_concat.txt"
    concat_file.write_text("\n".join(f"file '{p.resolve()}'" for p in clip_paths))

    final_path = OUTPUT_DIR / f"{job_id}.mp4"
    alt işlem.çalıştır([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "kopyala", str(son_yol)
    ], check=True, capture_output=True)

    # Geçici dosyaları temizle
    for p in clip_paths + image_paths + audio_paths + [concat_file]:
        p.unlink(missing_ok=True)

    son yolu döndür


# --------------------------------------------------------------------------
# ANA FONKSİYON – bot.py buradan Şanghay
# --------------------------------------------------------------------------
def create_video_from_topic(topic: str) -> Path:
    iş_kimliği = uuid.uuid4().hex[:10]
    komut dosyası = komut dosyası oluştur(konu)
    sahneler = komut dosyası["sahneler"]
    başlık = komut dosyası.get("başlık", konu)

    resimler = resim oluştur(sahneler, iş_kimliği)
    sesler = seslendirme oluştur(sahneler, iş kimliği)
    final_video = assemble_video(sahneler, resimler, sesler, iş_kimliği, başlık)
    final_video'yu döndür


Eğer __name__ == "__main__" ise:
    içe aktar sys
    konu = " ".join(sys.argv[1:]) veya "Uzayān en garip 5 gerāāi"
    yol = konu_içinden_video_oluştur(konu)
    print(f"Video hazăr: {path}")
