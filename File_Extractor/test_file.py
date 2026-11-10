"""
Tests for file_extractor.py.

Run with either:
    python -m unittest -v
    pytest

Uses only the standard library. Temporary files are created and cleaned up
automatically, and tests that need the real sample use ``sample_data.txt``.
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from typing import get_type_hints

import file_extractor as ftp

SAMPLE_FILE: Path = Path(__file__).with_name("sample_data.txt")

SAMPLE_COLUMNS: list[str] = [
    "Names", "Addresses", "Credit", "Product Names", "Suppliers",
    "Prices", "Order Dates", "Quantities", "Categories", "Regions",
]


class TempFileTestCase(unittest.TestCase):
    """Base class giving each test a scratch folder and a ``write`` helper."""

    def setUp(self) -> None:
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self.folder: Path = Path(self._folder.name)

    def write(self, text: str | bytes, name: str = "data.txt") -> Path:
        """Write ``text`` exactly as given (no newline translation) and return the path."""
        path: Path = self.folder / name
        path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        return path


# ---------------------------------------------------------------------------
# The real sample file
# ---------------------------------------------------------------------------

class SampleFileTests(unittest.TestCase):
    """Behaviour on the sample_data.txt supplied with the brief."""

    def test_dict_has_ten_columns_in_file_order(self) -> None:
        data = ftp.load_data_as_dict(SAMPLE_FILE)
        self.assertEqual(list(data), SAMPLE_COLUMNS)

    def test_every_column_has_twenty_entries(self) -> None:
        data = ftp.load_data_as_dict(SAMPLE_FILE)
        self.assertTrue(all(len(entries) == 20 for entries in data.values()))

    def test_first_entries_match_the_brief_examples(self) -> None:
        data = ftp.load_data_as_dict(SAMPLE_FILE)
        self.assertEqual(data["Names"][:2], ["Fred", "John"])
        self.assertEqual(data["Addresses"][:2], ["Pontypridd", "Treforest"])
        self.assertEqual(data["Credit"][:2], ["10", "20"])
        self.assertEqual(data["Product Names"][:2], ["Widget1", "Widget2"])

    def test_no_blank_or_keyword_lines_leak_into_entries(self) -> None:
        data = ftp.load_data_as_dict(SAMPLE_FILE)
        for entries in data.values():
            self.assertNotIn("", entries)
            self.assertNotIn("END", entries)
            self.assertFalse(any(e.startswith("COLUMN") for e in entries))

    def test_list_is_a_list_of_name_entries_tuples(self) -> None:
        data = ftp.load_data_as_list(SAMPLE_FILE)
        self.assertIsInstance(data, list)
        self.assertTrue(all(isinstance(item, tuple) and len(item) == 2 for item in data))
        self.assertEqual([name for name, _ in data], SAMPLE_COLUMNS)

    def test_dict_and_list_loaders_agree(self) -> None:
        self.assertEqual(ftp.load_data_as_dict(SAMPLE_FILE),
                         dict(ftp.load_data_as_list(SAMPLE_FILE)))

    def test_totals_and_means(self) -> None:
        for data in (ftp.load_data_as_dict(SAMPLE_FILE), ftp.load_data_as_list(SAMPLE_FILE)):
            self.assertEqual(ftp.return_sublist_total(data, "Credit"), 454.0)
            self.assertEqual(ftp.return_sublist_mean(data, "Credit"), 22.7)
            self.assertEqual(ftp.return_sublist_total(data, "Prices"), 454.0)
            self.assertEqual(ftp.return_sublist_total(data, "Quantities"), 254.0)
            self.assertEqual(ftp.return_sublist_mean(data, "Quantities"), 12.7)

    def test_text_columns_have_no_total_or_mean(self) -> None:
        data = ftp.load_data_as_dict(SAMPLE_FILE)
        for name in ("Names", "Addresses", "Order Dates", "Regions"):
            self.assertIsNone(ftp.return_sublist_total(data, name), name)
            self.assertIsNone(ftp.return_sublist_mean(data, name), name)


# ---------------------------------------------------------------------------
# Parsing rules
# ---------------------------------------------------------------------------

class ParsingTests(TempFileTestCase):
    """How the COLUMN / END format is interpreted."""

    def test_windows_unix_and_old_mac_line_endings(self) -> None:
        for newline in ("\r\n", "\n", "\r"):
            text = newline.join(["COLUMN A", "1", "2", "COLUMN B", "3", "END"])
            self.assertEqual(ftp.load_data_as_dict(self.write(text)),
                             {"A": ["1", "2"], "B": ["3"]}, repr(newline))

    def test_missing_final_newline_and_missing_end_are_fine(self) -> None:
        self.assertEqual(ftp.load_data_as_dict(self.write("COLUMN A\n1\n2")), {"A": ["1", "2"]})

    def test_nothing_after_end_is_read(self) -> None:
        text = "COLUMN A\n1\nEND\nCOLUMN B\n2\n"
        self.assertEqual(ftp.load_data_as_dict(self.write(text)), {"A": ["1"]})

    def test_end_in_the_middle_of_a_column_stops_reading(self) -> None:
        self.assertEqual(ftp.load_data_as_dict(self.write("COLUMN A\n1\nEND\n2\n")), {"A": ["1"]})

    def test_blank_lines_and_surrounding_spaces_are_ignored(self) -> None:
        text = "\n\nCOLUMN A\n\n  1  \n\t2\t\n\n   \nCOLUMN B\n3\nEND"
        self.assertEqual(ftp.load_data_as_dict(self.write(text)), {"A": ["1", "2"], "B": ["3"]})

    def test_utf8_bom_does_not_hide_the_first_column(self) -> None:
        path = self.write(b"\xef\xbb\xbfCOLUMN A\n1\n2\nEND")
        self.assertEqual(ftp.load_data_as_dict(path), {"A": ["1", "2"]})
        self.assertEqual(ftp.load_data_as_list(path), [("A", ["1", "2"])])

    def test_non_ascii_text_round_trips(self) -> None:
        self.assertEqual(ftp.load_data_as_dict(self.write("COLUMN Name\nZoë\nJosé\nEND")),
                         {"Name": ["Zoë", "José"]})

    def test_windows_1252_file_falls_back_instead_of_crashing(self) -> None:
        path = self.write("COLUMN Name\nJosé\nEND".encode("cp1252"))
        with self.assertLogs(ftp.logger, level="WARNING"):
            self.assertEqual(ftp.load_data_as_dict(path), {"Name": ["José"]})

    def test_empty_file_gives_empty_results(self) -> None:
        path = self.write("")
        self.assertEqual(ftp.load_data_as_dict(path), {})
        self.assertEqual(ftp.load_data_as_list(path), [])

    def test_column_with_no_entries_is_kept_and_empty(self) -> None:
        self.assertEqual(ftp.load_data_as_dict(self.write("COLUMN A\nCOLUMN B\n1\nEND")),
                         {"A": [], "B": ["1"]})

    def test_path_can_be_str_or_pathlib(self) -> None:
        path = self.write("COLUMN A\n1\nEND")
        self.assertEqual(ftp.load_data_as_dict(str(path)), ftp.load_data_as_dict(path))

    def test_missing_file_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            ftp.load_data_as_dict(self.folder / "nope.txt")
        with self.assertRaises(FileNotFoundError):
            ftp.load_data_as_list(self.folder / "nope.txt")


class HeaderRecognitionTests(TempFileTestCase):
    """COLUMN is a keyword only when it is a whole word."""

    def test_values_that_merely_start_with_column_are_data(self) -> None:
        text = "COLUMN Words\nCOLUMNIST\nCOLUMNS are fun\nCOLUMN2\nEND"
        self.assertEqual(ftp.load_data_as_dict(self.write(text)),
                         {"Words": ["COLUMNIST", "COLUMNS are fun", "COLUMN2"]})

    def test_keyword_is_case_sensitive(self) -> None:
        text = "COLUMN A\ncolumn b\nColumn C\nEND"
        self.assertEqual(ftp.load_data_as_dict(self.write(text)), {"A": ["column b", "Column C"]})

    def test_extra_spaces_or_tabs_after_keyword_are_not_part_of_the_name(self) -> None:
        text = "COLUMN   Spaced\n1\nCOLUMN\tTabbed\n2\nEND"
        self.assertEqual(ftp.load_data_as_dict(self.write(text)), {"Spaced": ["1"], "Tabbed": ["2"]})

    def test_names_may_contain_spaces_and_symbols(self) -> None:
        text = "COLUMN Product Names (2025) - v2\nx\nEND"
        self.assertEqual(ftp.load_data_as_dict(self.write(text)), {"Product Names (2025) - v2": ["x"]})


class MalformedInputTests(TempFileTestCase):
    """Cases the brief does not define: lenient by default, strict on request."""

    def test_entries_before_the_first_column_are_skipped_with_a_warning(self) -> None:
        path = self.write("stray\nCOLUMN A\n1\nEND")
        with self.assertLogs(ftp.logger, level="WARNING") as logs:
            self.assertEqual(ftp.load_data_as_dict(path), {"A": ["1"]})
        self.assertIn("line 1", logs.output[0])
        with self.assertLogs(ftp.logger, level="WARNING"):
            self.assertEqual(ftp.load_data_as_list(path), [("A", ["1"])])

    def test_dict_and_list_treat_stray_entries_identically(self) -> None:
        path = self.write("stray\nCOLUMN A\n1\nEND")
        with self.assertLogs(ftp.logger, level="WARNING"):
            as_dict = ftp.load_data_as_dict(path)
            as_list = ftp.load_data_as_list(path)
        self.assertEqual(as_dict, dict(as_list))

    def test_nameless_column_is_skipped_with_its_entries(self) -> None:
        path = self.write("COLUMN A\n1\nCOLUMN\n2\n3\nCOLUMN B\n4\nEND")
        with self.assertLogs(ftp.logger, level="WARNING"):
            self.assertEqual(ftp.load_data_as_dict(path), {"A": ["1"], "B": ["4"]})

    def test_strict_mode_raises_for_stray_entries_and_nameless_columns(self) -> None:
        with self.assertRaises(ftp.DataFormatError):
            ftp.load_data_as_dict(self.write("stray\nCOLUMN A\nEND"), strict=True)
        with self.assertRaises(ftp.DataFormatError):
            ftp.load_data_as_list(self.write("COLUMN\n1\nEND", "b.txt"), strict=True)

    def test_data_format_error_is_a_value_error(self) -> None:
        self.assertTrue(issubclass(ftp.DataFormatError, ValueError))

    def test_repeated_column_is_merged_in_a_dict_with_a_warning(self) -> None:
        path = self.write("COLUMN A\n1\n2\nCOLUMN A\n3\nEND")
        with self.assertLogs(ftp.logger, level="WARNING"):
            self.assertEqual(ftp.load_data_as_dict(path), {"A": ["1", "2", "3"]})

    def test_repeated_column_is_kept_apart_in_a_list(self) -> None:
        path = self.write("COLUMN A\n1\n2\nCOLUMN A\n3\nEND")
        self.assertEqual(ftp.load_data_as_list(path), [("A", ["1", "2"]), ("A", ["3"])])

    def test_strict_mode_rejects_a_repeated_column_in_a_dict(self) -> None:
        with self.assertRaises(ftp.DataFormatError):
            ftp.load_data_as_dict(self.write("COLUMN A\n1\nCOLUMN A\n2\nEND"), strict=True)


# ---------------------------------------------------------------------------
# return_sublist
# ---------------------------------------------------------------------------

class ReturnSublistTests(unittest.TestCase):
    """The rules from the brief, plus defensive behaviour."""

    DICT_DATA = {"Names": ["Fred", "John"], "Credit": ["10", "20"]}
    LIST_DATA = [("Names", ["Fred", "John"]), ("Credit", ["10", "20"])]

    def test_finds_a_column_in_a_dict_and_in_a_list(self) -> None:
        self.assertEqual(ftp.return_sublist(self.DICT_DATA, "Names"), ["Fred", "John"])
        self.assertEqual(ftp.return_sublist(self.LIST_DATA, "Credit"), ["10", "20"])

    def test_missing_column_gives_none(self) -> None:
        self.assertIsNone(ftp.return_sublist(self.DICT_DATA, "Nope"))
        self.assertIsNone(ftp.return_sublist(self.LIST_DATA, "Nope"))

    def test_name_must_match_exactly(self) -> None:
        self.assertIsNone(ftp.return_sublist(self.DICT_DATA, "names"))
        self.assertIsNone(ftp.return_sublist(self.DICT_DATA, "Names "))

    def test_data_that_is_not_a_dict_or_list_gives_none(self) -> None:
        for bad in (None, "Names", 42, 3.5, ("Names", ["a"]), {"Names"}, b"Names", object()):
            self.assertIsNone(ftp.return_sublist(bad, "Names"), repr(bad))  # type: ignore[arg-type]

    def test_a_col_name_that_is_not_a_string_gives_none_instead_of_crashing(self) -> None:
        for bad in (["Names"], {"Names"}, None, 5, ("Names",)):
            self.assertIsNone(ftp.return_sublist(self.DICT_DATA, bad), repr(bad))  # type: ignore[arg-type]
            self.assertIsNone(ftp.return_sublist(self.LIST_DATA, bad), repr(bad))  # type: ignore[arg-type]

    def test_empty_containers(self) -> None:
        self.assertIsNone(ftp.return_sublist({}, "A"))
        self.assertIsNone(ftp.return_sublist([], "A"))

    def test_a_column_with_no_entries_returns_an_empty_list_not_none(self) -> None:
        self.assertEqual(ftp.return_sublist({"A": []}, "A"), [])

    def test_malformed_list_items_are_skipped_not_fatal(self) -> None:
        messy = [1, "AB", ("A", ["x"], "extra"), None, ("Good", ["ok"])]
        self.assertEqual(ftp.return_sublist(messy, "Good"), ["ok"])
        self.assertIsNone(ftp.return_sublist(messy, "A"))      # "AB" must not unpack into "A", "B"

    def test_a_non_list_value_is_not_treated_as_entries(self) -> None:
        self.assertIsNone(ftp.return_sublist({"A": "123"}, "A"))
        self.assertIsNone(ftp.return_sublist({"A": None}, "A"))
        self.assertIsNone(ftp.return_sublist([("A", "123")], "A"))

    def test_first_match_wins_when_a_list_repeats_a_name(self) -> None:
        data = [("A", ["1"]), ("A", ["2"])]
        self.assertEqual(ftp.return_sublist(data, "A"), ["1"])

    def test_result_is_a_copy_so_callers_cannot_corrupt_the_data(self) -> None:
        data = {"A": ["1", "2"]}
        ftp.return_sublist(data, "A").append("INTRUDER")       # type: ignore[union-attr]
        self.assertEqual(data["A"], ["1", "2"])


# ---------------------------------------------------------------------------
# return_sublist_total / return_sublist_mean
# ---------------------------------------------------------------------------

class NumericTests(unittest.TestCase):
    """Sums and means: what counts as a number, and exactness."""

    @staticmethod
    def column(*entries: str) -> dict[str, list[str]]:
        return {"C": list(entries)}

    def check(self, entries: list[str], total: float | None, mean: float | None) -> None:
        """Assert total and mean for both container types."""
        for data in ({"C": entries}, [("C", entries)]):
            self.assertEqual(ftp.return_sublist_total(data, "C"), total, entries)
            self.assertEqual(ftp.return_sublist_mean(data, "C"), mean, entries)

    def test_integers_and_decimals(self) -> None:
        self.check(["10", "20"], 30.0, 15.0)
        self.check(["1.5", "2.5"], 4.0, 2.0)

    def test_negative_signed_and_scientific_notation(self) -> None:
        self.check(["-5", "+5", "1e2"], 100.0, 100.0 / 3)

    def test_surrounding_spaces_are_tolerated(self) -> None:
        self.check([" 7 ", "3"], 10.0, 5.0)

    def test_total_returns_a_float(self) -> None:
        self.assertIsInstance(ftp.return_sublist_total(self.column("1"), "C"), float)

    def test_one_bad_entry_makes_the_whole_column_none(self) -> None:
        self.check(["1", "2", "three"], None, None)
        self.check(["1", "", "3"], None, None)

    def test_dates_are_not_numbers(self) -> None:
        self.check(["2025-01-15"], None, None)

    def test_nan_and_infinity_are_rejected(self) -> None:
        for bad in ("nan", "NaN", "inf", "-inf", "Infinity", "1e999"):
            self.check(["1", bad], None, None)

    def test_underscore_digit_groups_are_rejected(self) -> None:
        self.check(["1_000", "2"], None, None)

    def test_missing_column_gives_none(self) -> None:
        self.assertIsNone(ftp.return_sublist_total({"C": ["1"]}, "Other"))
        self.assertIsNone(ftp.return_sublist_mean([("C", ["1"])], "Other"))

    def test_data_that_is_not_a_dict_or_list_gives_none(self) -> None:
        for bad in (None, "C", 7, ("C", ["1"])):
            self.assertIsNone(ftp.return_sublist_total(bad, "C"), repr(bad))  # type: ignore[arg-type]
            self.assertIsNone(ftp.return_sublist_mean(bad, "C"), repr(bad))   # type: ignore[arg-type]

    def test_a_string_value_is_not_summed_digit_by_digit(self) -> None:
        self.assertIsNone(ftp.return_sublist_total({"C": "123"}, "C"))

    def test_non_string_entries_that_are_not_numbers_do_not_crash(self) -> None:
        self.check([None, "1"], None, None)                     # type: ignore[list-item]
        self.check([[1], "1"], None, None)                      # type: ignore[list-item]

    def test_empty_column_has_total_zero_but_no_mean(self) -> None:
        self.check([], 0.0, None)

    def test_summation_is_exact(self) -> None:
        self.check(["0.1"] * 10, 1.0, 0.1)                      # naive += gives 0.9999999999999999

    def test_overflow_gives_none_instead_of_crashing(self) -> None:
        self.check(["1e308", "1e308"], None, None)

    def test_huge_integers_do_not_crash(self) -> None:
        self.check([str(10 ** 400)], None, None)                # float() overflows -> not usable

    def test_totals_use_return_sublist(self) -> None:
        """The brief says to read entries via return_sublist; a patched one must be honoured."""
        original = ftp.return_sublist
        try:
            ftp.return_sublist = lambda data, col_name: ["2", "4"]      # type: ignore[assignment]
            self.assertEqual(ftp.return_sublist_total({}, "anything"), 6.0)
            self.assertEqual(ftp.return_sublist_mean({}, "anything"), 3.0)
        finally:
            ftp.return_sublist = original


# ---------------------------------------------------------------------------
# Typing and the demo
# ---------------------------------------------------------------------------

class TypingTests(unittest.TestCase):
    """The brief awards marks for type annotations, so check them."""

    def test_total_and_mean_are_annotated_as_float_or_none(self) -> None:
        for function in (ftp.return_sublist_total, ftp.return_sublist_mean):
            self.assertEqual(get_type_hints(function)["return"], float | None)

    def test_return_sublist_is_annotated_as_list_of_str_or_none(self) -> None:
        self.assertEqual(get_type_hints(ftp.return_sublist)["return"], list[str] | None)

    def test_every_public_function_is_fully_annotated_and_documented(self) -> None:
        for function in (ftp.load_data_as_dict, ftp.load_data_as_list, ftp.return_sublist,
                         ftp.return_sublist_total, ftp.return_sublist_mean, ftp.main):
            hints = get_type_hints(function)
            self.assertIn("return", hints, function.__name__)
            self.assertTrue(function.__doc__ and len(function.__doc__.strip()) > 40, function.__name__)


class MainTests(TempFileTestCase):
    """The demonstration entry point."""

    def test_main_succeeds_on_the_sample(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as shown:
            self.assertEqual(ftp.main([str(SAMPLE_FILE)]), 0)
        self.assertIn("Credit", shown.getvalue())
        self.assertIn("454.00", shown.getvalue())

    def test_main_reports_a_missing_file_with_exit_code_1(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as shown:
            self.assertEqual(ftp.main([str(self.folder / "missing.txt")]), 1)
        self.assertIn("Could not read", shown.getvalue())

    def test_default_sample_path_does_not_depend_on_the_working_directory(self) -> None:
        self.assertTrue(ftp.DEFAULT_SAMPLE_FILE.is_absolute())
        self.assertTrue(ftp.DEFAULT_SAMPLE_FILE.exists())


if __name__ == "__main__":
    unittest.main()
