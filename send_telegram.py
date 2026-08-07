"""
send_telegram.py

Telegram bot polling ile 7/24 calismak yerine, sadece video hazir oldugunda
Telegram API'sine tek bir istek atip videoyu ve mesaji gonderir.
"""

import os
import requests

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip()
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"].strip()


def send_text(text: str):
    print(f"[telegram] mesaj gonderiliyor -> chat_id={TELEGRAM_CHAT_ID}")
    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=30,
    )
    print(f"[telegram] sendMessage cevap kodu: {resp.status_code}")
    print(f"[telegram] sendMessage cevap govdesi: {resp.text}")
    resp.raise_for_status()


def send_video(video_path, caption: str = ""):
    print(f"[telegram] video gonderiliyor -> chat_id={TELEGRAM_CHAT_ID}, dosya={video_path}")
    with open(video_path, "rb") as f:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
            files={"video": f},
            timeout=300,
        )
    print(f"[telegram] sendVideo cevap kodu: {resp.status_code}")
    print(f"[telegram] sendVideo cevap govdesi: {resp.text}")
    resp.raise_for_status()
