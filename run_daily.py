"""
run_daily.py
------------
GitHub Actions tarafından çalıştırılan ana script.

İki modda çalışır:
1) Manuel tetikleme: Sen GitHub'da "Run workflow" butonuna basıp bir konu yazarsın
   -> TOPIC ortam değişkeni gelir -> sadece o konudan 1 video üretilir
2) Günlük otomatik tetikleme (zamanlanmış): TOPIC boş gelir
   -> topics.txt dosyasındaki tüm satırlar (konular) sırayla işlenir
"""

import os
import sys
from pathlib import Path

from video_generator import create_video_from_topic
from send_telegram import send_text, send_video

TOPICS_FILE = Path(__file__).parent / "topics.txt"


def process_topic(topic: str):
    topic = topic.strip()
    if not topic:
        return
    try:
        send_text(f"🎬 \"{topic}\" için video hazırlanıyor...")
        video_path = create_video_from_topic(topic)
        send_video(video_path, caption=f"✅ {topic}")
        video_path.unlink(missing_ok=True)
    except Exception as e:
        send_text(f"❌ \"{topic}\" üretilirken hata oluştu: {e}")
        raise


def main():
    manual_topic = os.environ.get("TOPIC", "").strip()

    if manual_topic:
        process_topic(manual_topic)
        return

    if not TOPICS_FILE.exists():
        print("topics.txt bulunamadı, işlenecek konu yok.")
        return

    topics = [line.strip() for line in TOPICS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not topics:
        print("topics.txt boş, işlenecek konu yok.")
        return

    for topic in topics:
        process_topic(topic)


if __name__ == "__main__":
    main()
