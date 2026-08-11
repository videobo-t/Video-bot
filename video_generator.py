"""
video_generator.py

Bir konudan, kitap tadinda (giris - gelisme - sonuc), 7-8 dakikalik
sesli/gorsel bir hikaye videosu ureten motor.
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

# 7-8 dakikalik bir video icin yeterli sahne sayisi ve sahne basina soz uzunlugu
N_SCENES = 26
WORDS_PER_SCENE = 70


def generate_script(topic: str, n_scenes: int = N_SCENES) -> dict:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY tanimli degil")

    system_prompt = (
        "You are a professional Turkish storyteller/scriptwriter, writing a long-form "
        "narrated short-film script (like a book chapter read aloud), not a quick summary. "
        "The story must have real narrative depth: a clear introduction (giris) that sets "
        "the scene and introduces the main character and any supporting/side characters, "
        "a development (gelisme) with events, obstacles, emotional turns and (when natural) "
        "dialogue between characters, and a satisfying conclusion (sonuc) that resolves the "
        "story and lands its meaning. Respond ONLY with valid JSON, nothing else."
    )
    user_prompt = f"""
Topic: "{topic}"

Write this as a full narrated story in TURKISH, split into exactly {n_scenes} sequential
scenes, structured like book chapters:
- Scenes 1 to {max(1, round(n_scenes*0.2))}: GIRIS - introduce the setting, the main
  character, and any side characters. Establish the world and the initial situation.
- Scenes {round(n_scenes*0.2)+1} to {round(n_scenes*0.8)}: GELISME - the events unfold,
  obstacles/conflicts appear, characters interact (dialogue allowed inside narration,
  e.g. quoting what a character said), emotions and stakes build up.
- Scenes {round(n_scenes*0.8)+1} to {n_scenes}: SONUC - the story resolves, the emotional
  payoff lands, end with a clear closing line.

For each scene provide:
- "narration": natural spoken TURKISH text, written the way a narrator would read a book
  aloud. Roughly {WORDS_PER_SCENE} words per scene (can vary a little). Proper Turkish
  spelling and Turkish letters, since it will be read by a Turkish text-to-speech voice.
  Keep continuity with previous scenes (same character names, consistent story).
- "image_prompt": an ENGLISH, detailed cinematic AI image generation prompt describing
  this exact scene. IMPORTANT for visual consistency: every single image_prompt must
  repeat the SAME concrete physical description of the main character (and any visible
  side characters) - hair, clothing, age, build, style - word for word or nearly so,
  so the character looks the same across all scenes. Also keep a consistent overall art
  style (e.g. "cinematic realistic photography, warm lighting, 35mm film look") repeated
  in every image_prompt.

First decide on the character(s) and a fixed visual description for each before writing
scenes, then use that same description consistently in every image_prompt.

Return ONLY JSON in this exact format:
{{
  "title": "video title",
  "characters": [
    {{"name": "...", "visual_description": "..."}}
  ],
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
            "temperature": 0.85,
            "max_tokens": 8000,
            "response_format": {"type": "json_object"},
        },
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)
    return data


def _fetch_one_image(args):
    i, prompt, job_id = args
    url = (
        f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}"
        f"?width={VIDEO_W}&height={VIDEO_H}&nologo=true&model=flux"
        f"&seed={uuid.uuid4().int % 100000}"
    )
    out_path = TEMP_DIR / f"{job_id}_scene{i}.jpg"
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    out_path.write_bytes(r.content)
    return i, out_path


def generate_images(scenes: list, job_id: str) -> list:
    # Gorselleri sirayla degil, ayni anda (paralel) indirerek sureyi kisaltiyoruz
    from concurrent.futures import ThreadPoolExecutor

    tasks = [(i, scene["image_prompt"], job_id) for i, scene in enumerate(scenes)]
    results = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        for i, path in executor.map(_fetch_one_image, tasks):
            results[i] = path

    return [results[i] for i in range(len(scenes))]


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
    fps = 25
    zoom_target = 1.15
    for i, (img, audio) in enumerate(zip(image_paths, audio_paths)):
        duration = _get_audio_duration(audio) + 0.4
        clip_out = TEMP_DIR / f"{job_id}_clip{i}.mp4"

        frames = max(int(duration * fps), 1)
        increment = (zoom_target - 1.0) / frames
        zoom_expr = (
            f"zoompan=z='min(zoom+{increment:.6f},{zoom_target})':"
            f"d={frames}:s={VIDEO_W}x{VIDEO_H}:fps={fps}"
        )
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(audio),
            "-filter_complex", f"[0:v]{zoom_expr}[v]",
            "-map", "[v]", "-map", "1:a",
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-shortest", str(clip_out)
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
