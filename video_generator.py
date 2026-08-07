"""
video_generator.py

Bir konu metninden otomatik olarak kisa video ureten motor.
(Bu dosyada encoding sorunlarindan kacinmak icin ozel Turkce
karakterler kullanilmamistir. Kod calismasini etkilemez.)
"""

import os
import json
import uuid
import subprocess
from pathlib import Path

import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"
PIPER_VOICE = os.environ.get("PIPER_VOICE", "tr_TR-dfki-medium")

BASE_DIR = Path(__file__).parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

VIDEO_W, VIDEO_H = 1080, 1920  # dikey format (Reels/TikTok/Shorts)


def generate_script(topic: str, n_scenes: int = 6) -> dict:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY tanimli degil")

    system_prompt = (
        "You are a scriptwriter for short social media videos (TikTok/Reels/Shorts). "
        "Turn the given topic into a flowing, curiosity-driving narration IN TURKISH "
        "LANGUAGE that hooks the viewer in the first 2 seconds. "
        "Respond ONLY with valid JSON, nothing else."
    )
    user_prompt = f"""
Topic: "{topic}"

Split this topic into exactly {n_scenes} scenes. For each scene provide:
- "narration": natural spoken TURKISH text, 1-2 sentences (max 25 words), written
  using proper Turkish spelling and Turkish letters since it will be read aloud
  by a Turkish text-to-speech voice.
- "image_prompt": an ENGLISH, detailed AI image generation prompt describing this
  scene visually (cinematic, high quality, lighting details).

Return ONLY JSON in this exact format:
{{
  "title": "video title",
  "scenes": [
    {{"narration": "...", "image_prompt": "..."}}
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


def generate_images(scenes: list, job_id: str) -> list:
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


def generate_voiceover(scenes: list, job_id: str) -> list:
    audio_paths = []
    for i, scene in enumerate(scenes):
        out_path = TEMP_DIR / f"{job_id}_scene{i}.wav"
        subprocess.run(
            ["piper", "--model", PIPER_VOICE, "--output_file", str(out_path)],
            input=scene["narration"],
            text=True,
            check=True,
            capture_output=True,
        )
        audio_paths.append(out_path)
    return audio_paths


def _get_audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def assemble_video(scenes: list, image_paths: list, audio_paths: list,
                    job_id: str, title: str) -> Path:
    clip_paths = []
    for i, (img, audio) in enumerate(zip(image_paths, audio_paths)):
        duration = _get_audio_duration(audio) + 0.3
        clip_out = TEMP_DIR / f"{job_id}_clip{i}.mp4"

        zoom_expr = f"zoompan=z='min(zoom+0.0008,1.15)':d={int(duration*25)}:s={VIDEO_W}x{VIDEO_H}:fps=25"
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(audio),
            "-filter_complex", f"[0:v]{zoom_expr}[v]",
            "-map", "[v]", "-map", "1:a",
            "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(clip_out)
        ], check=True, capture_output=True)
        clip_paths.append(clip_out)

    concat_file = TEMP_DIR / f"{job_id}_concat.txt"
    concat_file.write_text("\n".join(f"file '{p.resolve()}'" for p in clip_paths))

    final_path = OUTPUT_DIR / f"{job_id}.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy", str(final_path)
    ], check=True, capture_output=True)

    for p in clip_paths + image_paths + audio_paths + [concat_file]:
        p.unlink(missing_ok=True)

    return final_path


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
    topic = " ".join(sys.argv[1:]) or "Uzayin en garip 5 gercegi"
    path = create_video_from_topic(topic)
    print(f"Video hazir: {path}")
