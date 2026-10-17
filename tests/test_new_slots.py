import copy
import unittest
from unittest.mock import mock_open, patch

import requests

import scaner


class NewSlotsTests(unittest.TestCase):
    def setUp(self):
        self.slot = {
            "start_time": "18:00:00",
            "duration": 90,
            "price": "270 PLN",
        }
        self.result = self.scan(self.slot)

    def scan(self, *slots):
        return {"Klub": {"2026-10-21": [("Padel 1 (Indoor)", list(slots))]}}

    def run_scans(self, scans, send_side_effect=None):
        with (
            patch("builtins.open", mock_open(read_data="{}")),
            patch("builtins.print"),
            patch("scaner.search_and_filter", side_effect=scans),
            patch(
                "scaner.time.sleep",
                side_effect=[None] * (len(scans) - 1) + [StopIteration],
            ),
            patch(
                "scaner.send_telegram_notification", side_effect=send_side_effect
            ) as send,
        ):
            with self.assertRaises(StopIteration):
                scaner.main()
        return send.call_args_list

    def test_first_scan_preserves_full_slot_data(self):
        original = copy.deepcopy(self.result)
        indexed = scaner.index_slots(self.result)
        key = ("Klub", "2026-10-21", "Padel 1 (Indoor)", "18:00:00", 90)

        self.assertEqual(indexed, {key: self.slot})
        self.assertEqual(scaner.find_new_slots({}, indexed), self.result)
        self.assertEqual(self.result, original)

    def test_only_new_slot_is_selected(self):
        new_slot = {**self.slot, "start_time": "19:00:00", "price": "300 PLN"}
        current = self.scan(self.slot, new_slot)

        new_slots = scaner.find_new_slots(
            scaner.index_slots(self.result), scaner.index_slots(current)
        )

        self.assertEqual(new_slots, self.scan(new_slot))

    def test_price_and_order_changes_are_not_new_terms(self):
        other = {**self.slot, "start_time": "19:00:00"}
        previous = self.scan(self.slot, other)
        current = self.scan(other, {**self.slot, "price": "300 PLN"})

        self.assertEqual(
            scaner.find_new_slots(
                scaner.index_slots(previous), scaner.index_slots(current)
            ),
            {},
        )

    def test_identity_includes_club_date_court_and_duration(self):
        current = copy.deepcopy(self.result)
        current["Inny klub"] = copy.deepcopy(self.result["Klub"])
        current["Klub"]["2026-10-22"] = [("Padel 1 (Indoor)", [self.slot])]
        current["Klub"]["2026-10-21"].extend([
            ("Padel 2 (Indoor)", [self.slot]),
            ("Padel 1 (Indoor)", [{**self.slot, "duration": 60}]),
        ])

        new_slots = scaner.find_new_slots(
            scaner.index_slots(self.result), scaner.index_slots(current)
        )

        self.assertEqual(len(scaner.index_slots(current)), 5)
        self.assertEqual(len(scaner.index_slots(new_slots)), 4)

    def test_repeated_scans_send_only_added_terms(self):
        new_slot = {**self.slot, "start_time": "19:00:00"}
        current = self.scan(self.slot, new_slot)
        calls = self.run_scans([self.result, self.result, current, current])

        self.assertEqual(len(calls), 2)
        text = calls[1].kwargs["notification_text"]
        self.assertIn("19:00:00", text)
        self.assertNotIn("18:00:00", text)

    def test_failed_notification_is_retried(self):
        calls = self.run_scans(
            [self.result, self.result, self.result],
            send_side_effect=[requests.exceptions.ConnectionError(), None],
        )

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], calls[1])

    def test_disappearing_and_returning_term_is_announced_again(self):
        calls = self.run_scans([
            self.result,
            {"Klub": {"2026-10-21": []}},
            self.result,
        ])

        self.assertEqual(len(calls), 2)

    def test_failed_scan_does_not_reset_previous_terms(self):
        initial = copy.deepcopy(self.result)
        initial["Klub"]["2026-10-22"] = [("Padel 1 (Indoor)", [self.slot])]
        # Brak 21.10 oznacza błąd pobrania; 22.10 pobrano bez wolnych terminów.
        partial = {"Klub": {"2026-10-22": []}}

        calls = self.run_scans([initial, partial, {}, initial])

        self.assertEqual(len(calls), 2)
        text = calls[1].kwargs["notification_text"]
        self.assertIn("2026-10-22", text)
        self.assertNotIn("2026-10-21", text)

    def test_search_distinguishes_empty_results_from_failed_requests(self):
        criteria = {
            "clubs": ["Klub"],
            "dates": ["2026-10-21", "2026-10-22"],
            "duration": 90,
            "start_time_range": ("17:00:00", "21:00:00"),
        }
        with (
            patch("builtins.print"),
            patch(
                "scaner.send_search_request",
                side_effect=[requests.exceptions.ConnectionError(), []],
            ),
        ):
            result = scaner.search_and_filter(
                search_critera=criteria,
                clubs_data={"Klub": {"tenant_id": "club-id", "resources": {}}},
            )

        self.assertEqual(result, {"Klub": {"2026-10-22": []}})


if __name__ == "__main__":
    unittest.main()
