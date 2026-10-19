import contextlib
import copy
import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("converter", ROOT / "python coverter.py")
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


def stats_html(selected="last_15_days"):
    selected_attribute = " selected" if selected is not None else ""
    records = [{"name": "Ahri - Alluring", "set": "OGN", "type": "Unit",
                "play": 0.4, "win": 52.0}]
    return (
        '<select id="stats-range">'
        f'<option value="{selected}"{selected_attribute}>Range</option>'
        '</select><script>var DATA = ' + json.dumps(records) + ';</script>'
    )


def api_card(name="Ahri - Alluring", alternate_art=False, set_code="OGN"):
    return {
        "name": name,
        "set": {"set_id": set_code},
        "classification": {"type": "Unit"},
        "metadata": {"alternate_art": alternate_art},
    }


class CapturedFile(io.StringIO):
    def close(self):
        # Keep the contents readable after the converter closes its output.
        pass


class ConverterTests(unittest.TestCase):
    def build(self, cards, html=None):
        files = {}

        def capture_open(filename, *args, **kwargs):
            files[filename] = CapturedFile()
            return files[filename]

        with (
            patch.object(converter.Path, "read_text", return_value=html or stats_html()),
            patch.object(converter, "download_all_riftcodex_cards", return_value=copy.deepcopy(cards)),
            patch("builtins.open", side_effect=capture_open),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            converter.main()
        return files

    def test_printing_suffixes_share_base_key(self):
        expected = converter.normalize_name("Ahri - Alluring")
        for treatment in ("Alternate Art", "Overnumbered", "Signature", "Metal",
                          "Ultimate", "Launch Exclusive", "GG EZ", "Starter"):
            with self.subTest(treatment=treatment):
                self.assertEqual(
                    converter.normalize_name(f"Ahri - Alluring ({treatment})"), expected
                )
        self.assertEqual(
            converter.normalize_name("Ahri - Alluring (Alternate Art) (Signature)"), expected
        )

    def test_other_parenthetical_text_remains_distinct(self):
        self.assertNotEqual(
            converter.normalize_name("Example (Token)"), converter.normalize_name("Example")
        )
        self.assertEqual(converter.normalize_name("Kai’Sa, Survivör"), "kaisasurvivor")

    def test_base_printing_wins_in_either_order_and_keeps_stats(self):
        for treatment in ("Alternate Art", "Overnumbered", "Signature", "Metal",
                          "Ultimate", "Launch Exclusive", "GG EZ", "Starter"):
            for special_first in (True, False):
                with self.subTest(treatment=treatment, special_first=special_first):
                    cards = [api_card(f"Ahri - Alluring ({treatment})"), api_card()]
                    if not special_first:
                        cards.reverse()
                    files = self.build(cards)
                    output = json.loads(files[converter.OUTPUT_FILE].getvalue())
                    report = json.loads(files[converter.REPORT_FILE].getvalue())
                    self.assertEqual(output["card_count"], 1)
                    card = output["cards"][0]
                    self.assertEqual(card["name"], "Ahri - Alluring")
                    self.assertEqual(card["play_rate"], 0.4)
                    self.assertEqual(card["win_rate"], 52.0)
                    self.assertFalse(any(key.startswith("_") for key in card))
                    self.assertEqual(report["cards_with_stats"], 1)
                    self.assertEqual(report["riftdecks_records_failed_to_match"], 0)

    def test_only_special_printing_still_matches_base_stats(self):
        files = self.build([api_card("Ahri - Alluring (Alternate Art)", True)])
        output = json.loads(files[converter.OUTPUT_FILE].getvalue())
        self.assertEqual(output["cards"][0]["play_rate"], 0.4)

    def test_excluded_sets_and_missing_stats_are_preserved(self):
        files = self.build([api_card(set_code="RAD"), api_card("Unknown card")])
        output = json.loads(files[converter.OUTPUT_FILE].getvalue())
        self.assertEqual(output["card_count"], 1)
        self.assertIsNone(output["cards"][0]["play_rate"])
        self.assertIsNone(output["cards"][0]["win_rate"])

    def test_checked_in_stats_snapshot_is_accepted(self):
        with contextlib.redirect_stdout(io.StringIO()):
            lookup, excluded = converter.load_riftdecks_stats(ROOT / "latest_stats")
        self.assertEqual(len(lookup), 734)
        self.assertEqual(excluded, 0)

    def test_wrong_or_missing_range_fails_before_download_or_write(self):
        for html in (stats_html("all"), stats_html("last_week"), stats_html(None),
                     '<script>var DATA = [];</script>'):
            with (
                self.subTest(html=html),
                patch.object(converter.Path, "read_text", return_value=html),
                patch.object(converter, "download_all_riftcodex_cards") as download,
                patch("builtins.open") as output,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                with self.assertRaisesRegex(ValueError, "Expected Last 15 Days"):
                    converter.main()
                download.assert_not_called()
                output.assert_not_called()

    def test_range_parser_ignores_other_filters_and_accepts_html_attributes(self):
        html = (
            "<select id='other'><option value='all' selected>All</option></select>"
            "<select class='filter' id='stats-range'>"
            "<option selected='selected' value='last_15_days'>15 days</option></select>"
            "<script>var DATA = [];</script>"
        )
        with patch.object(converter.Path, "read_text", return_value=html):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(converter.load_riftdecks_stats("snapshot"), ({}, 0))

    def test_request_failures_exit_nonzero(self):
        for error in (converter.requests.ConnectionError("offline"),
                      converter.requests.Timeout("timed out"),
                      converter.requests.HTTPError("503 Service Unavailable")):
            with (
                self.subTest(error=error),
                patch.object(converter.requests, "get", side_effect=error),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(SystemExit) as raised:
                    converter.download_all_riftcodex_cards()
                self.assertEqual(raised.exception.code, 1)
                self.assertIs(raised.exception.__cause__, error)


if __name__ == "__main__":
    unittest.main()
