"""
send_telegram.py
-----------------
Telegram bot polling ile 7/24 çalışmak yerine, sadece video hazır olduğunda
Telegram API'sine tek bir istek atıp videoyu ve mesajı gönderir.
Bu yüzden sürekli açık bir sunucuya ihtiyaç YOK — GitHub Actions üzerinde
birkaç dakikalığına çalışıp işini bitirip kapanabilir.
"""

import os
import requests

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def send_text(text: str):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=30,
    )


def send_video(video_path, caption: str = ""):
    with open(video_path, "rb") as f:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
            files={"video": f},
            timeout=300,
        )
