import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_URL = "https://api.telegram.org/bot"


not_found_message = "Brak nowych terminów"
found_message = "Znaleziono nowe terminy:"
scan_start_message = "Uruchomiono skan nowych terminów w pętli."


def send_telegram_notification(notification_text: str) -> None:
    url = TELEGRAM_URL + TELEGRAM_BOT_TOKEN + "/sendMessage"
    params = {"chat_id": TELEGRAM_CHAT_ID, "text": notification_text}
    response = requests.post(url=url, params=params, timeout=10)
    response.raise_for_status()
    return


def prepare_telegram_notification(
    mode: str, data: list[tuple] | None = None, service_name: str = None
) -> str:
    if mode == "start":
        notification = scan_start_message
    if mode == "found":
        notification = f"{found_message}\n"
        for court in data:
            notification += f"{court[0]}:\n"
            for slot in court[1]:
                notification += f"{slot}\n"
            notification += "\n"

    return notification
