import os
from datetime import date
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
WEEKDAYS_PL = (
    "poniedziałek",
    "wtorek",
    "środa",
    "czwartek",
    "piątek",
    "sobota",
    "niedziela",
)


def send_telegram_notification(notification_text: str) -> None:
    url = TELEGRAM_URL + TELEGRAM_BOT_TOKEN + "/sendMessage"
    params = {"chat_id": TELEGRAM_CHAT_ID, "text": notification_text}
    response = requests.post(url=url, params=params, timeout=10)
    response.raise_for_status()
    return


def prepare_telegram_notification(
    mode: str,
    data: dict[str, dict[str, list[tuple[str, list[dict]]]]] | None = None,
) -> str:
    if mode == "start":
        notification = scan_start_message
    if mode == "found":
        notification = f"{found_message}\n"
        for club, days in data.items():
            notification += f"\nKlub: {club}:\n"
            for day, courts in days.items():
                weekday = WEEKDAYS_PL[date.fromisoformat(day).weekday()]
                notification += f"\n{day} ({weekday}):\n"
                for court_name, court_slots in courts:
                    notification += f" Kort: {court_name}\n"
                    for slot in court_slots:
                        notification += (
                            f"    {slot['start_time']}, {slot['duration']}min\n"
                        )
    return notification
