import json
import pprint
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

from telegram_notification import (prepare_telegram_notification,
                                   send_telegram_notification)

SEARCH_URL = "https://playtomic.com/api/clubs/availability"


def convert_to_local_time(response: list[dict]) -> list[dict]:
    local_timezone = ZoneInfo("Europe/Warsaw")
    result = []

    for item in response:
        days = {}

        for slot in item["slots"]:
            utc_datetime = datetime.fromisoformat(
                f"{item['start_date']}T{slot['start_time']}"
            ).replace(tzinfo=timezone.utc)

            local_datetime = utc_datetime.astimezone(local_timezone)
            local_date = local_datetime.date().isoformat()

            if local_date not in days:
                days[local_date] = {
                    **item,
                    "start_date": local_date,
                    "slots": [],
                }

            days[local_date]["slots"].append(
                {
                    **slot,
                    "start_time": local_datetime.strftime("%H:%M:%S"),
                }
            )

        if not item["slots"]:
            result.append({**item, "slots": []})

        result.extend(days.values())

    return result


def search_for_slot(response: list[dict], courts_resources_list: list[tuple]):
    result = []
    for name, resource in courts_resources_list:
        if "Indoor" not in name:
            continue
        list_of_slots = []

        for item in response:
            if item["resource_id"] == resource:
                for slot in item["slots"]:
                    if (
                        slot["duration"] == 90
                        and "17:00:00" <= slot["start_time"] <= "21:00:00"
                    ):
                        list_of_slots.append(slot)

        if len(list_of_slots) > 0:
            result.append((name, list_of_slots))

    return result


def send_search_request(tenant_id: str, date: str) -> list[dict]:
    response = requests.get(
        url=SEARCH_URL,
        params={
            "tenant_id": tenant_id,
            "date": date,
            "sport_id": "PADEL",
        },
    )
    response.raise_for_status()
    return response.json()


def main():
    dates = ["2026-10-21"]

    with open("data/clubs.json", "r") as file:
        clubs = json.load(file)
    courts_resources_list = list(clubs[0]["resources"].items())
    tenant_id = clubs[0]["tenant_id"]
    notification = prepare_telegram_notification(mode="start")

    try:
        send_telegram_notification(notification_text=str(notification))
    except requests.exceptions.RequestException as e:
        print(f"Błąd podczas wysyłania powiadomienia: {type(e).__name__}")

    while True:
        try:
            search_response = send_search_request(tenant_id=tenant_id, date=dates[0])
        except requests.exceptions.RequestException as e:
            print(f"Błąd podczas pobierania listy terminów: {type(e).__name__}")
            continue

        search_response = convert_to_local_time(response=search_response)
        courts_resources_list = list(clubs[0]["resources"].items())
        result = search_for_slot(
            response=search_response, courts_resources_list=courts_resources_list
        )
        if len(result) > 0:
            notification = prepare_telegram_notification(mode="found", data=result)

            try:
                send_telegram_notification(notification_text=notification)
            except requests.exceptions.RequestException as e:
                print(f"Błąd podczas wysyłania powiadomienia: {type(e).__name__}")

        scan_time = datetime.now().strftime("%H:%M:%S")
        print(f"Skan zakończony, {scan_time}")
        time.sleep(120)


if __name__ == "__main__":
    main()
