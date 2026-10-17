import json
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

from telegram_notification import (
    prepare_telegram_notification,
    send_telegram_notification,
)

SEARCH_URL = "https://playtomic.com/api/clubs/availability"
search_criteria = {
    "clubs": ["Rakiety PGE Narodowy", "Warsaw Padel Club"],
    "duration": 90,
    "start_time_range": ("17:00:00", "21:00:00"),
    "dates": ["2026-10-26", "2026-10-27", "2026-10-28"],
}


def send_search_request(tenant_id: str, date: str) -> list[dict]:
    response = requests.get(
        url=SEARCH_URL,
        params={
            "tenant_id": tenant_id,
            "date": date,
            "sport_id": "PADEL",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


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


def filter_slots(
    response: list[dict],
    courts_resources_list: dict[str, str],
    duration: int,
    start_time_range: tuple[str, str],
) -> list[tuple[str, list[dict]]]:
    result = []
    for name, resource in courts_resources_list.items():
        if "outdoor" in name.casefold():
            continue
        list_of_slots = []

        for item in response:
            if item["resource_id"] == resource:
                for slot in item["slots"]:
                    if (
                        slot["duration"] == duration
                        and start_time_range[0]
                        <= slot["start_time"]
                        <= start_time_range[1]
                    ):
                        list_of_slots.append(slot)

        if len(list_of_slots) > 0:
            result.append((name, list_of_slots))

    return result


def search_and_filter(
    search_critera: dict, clubs_data: dict
) -> dict[str, dict[str, list[tuple[str, list[dict]]]]]:
    slots_for_clubs = {}
    dates = search_critera["dates"]
    wanted_clubs = search_critera["clubs"]
    for club in wanted_clubs:
        desired_slots = {}
        for date in dates:
            try:
                response = send_search_request(
                    tenant_id=clubs_data[club]["tenant_id"], date=date
                )
            except requests.exceptions.RequestException as e:
                print(f"Błąd podczas pobierania listy terminów: {type(e).__name__}")
                continue

            filtered_slots = filter_slots(
                response=convert_to_local_time(response),
                courts_resources_list=clubs_data[club]["resources"],
                duration=search_critera["duration"],
                start_time_range=search_critera["start_time_range"],
            )
            desired_slots[date] = filtered_slots
        if desired_slots:
            slots_for_clubs[club] = desired_slots
    return slots_for_clubs


def index_slots(result: dict) -> dict[tuple, dict]:
    indexed_slots = {}

    for club, dates in result.items():
        for date, courts in dates.items():
            for court_name, slots in courts:
                for slot in slots:
                    key = (
                        club,
                        date,
                        court_name,
                        slot["start_time"],
                        slot["duration"],
                    )
                    indexed_slots[key] = slot

    return indexed_slots


def find_new_slots(previous_slots: dict, current_slots: dict) -> dict:
    new_keys = current_slots.keys() - previous_slots.keys()
    result = {}

    for key, slot in current_slots.items():
        if key not in new_keys:
            continue

        club, date, court_name, _, _ = key
        courts = result.setdefault(club, {}).setdefault(date, {})
        courts.setdefault(court_name, []).append(slot)

    return {
        club: {date: list(courts.items()) for date, courts in dates.items()}
        for club, dates in result.items()
    }


def update_slot_snapshot(
    previous_slots: dict, current_slots: dict, scan_result: dict
) -> dict:
    successful_scans = {
        (club, date)
        for club, dates in scan_result.items()
        for date in dates
    }
    snapshot = {
        key: slot
        for key, slot in previous_slots.items()
        if key[:2] not in successful_scans
    }
    snapshot.update(current_slots)
    return snapshot


def main():
    with open("data/clubs.json", "r") as file:
        clubs_data = json.load(file)

    previous_slots = {}

    while True:
        result = search_and_filter(
            search_critera=search_criteria, clubs_data=clubs_data
        )
        current_slots = index_slots(result)
        new_slots = find_new_slots(previous_slots, current_slots)

        try:
            if new_slots:
                notification = prepare_telegram_notification(
                    mode="found", data=new_slots
                )
                send_telegram_notification(notification_text=notification)
        except requests.exceptions.RequestException as e:
            print(f"Błąd podczas wysyłania powiadomienia: {type(e).__name__}")
        else:
            previous_slots = update_slot_snapshot(previous_slots, current_slots, result)

        scan_time = datetime.now().strftime("%H:%M:%S")
        print(f"Skan zakończony, {scan_time}")
        time.sleep(120)


if __name__ == "__main__":
    main()
