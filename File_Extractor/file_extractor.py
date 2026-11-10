"""
Fast Track Project: read "columns of data" stored as plain text.

A text file can hold spreadsheet-like data using two keywords:

    COLUMN <Column Name>
    <Value 1>
    <Value 2>
    COLUMN <Next Column Name>
    <Value 1>
    END

* ``COLUMN`` (all uppercase) starts a column; the rest of that line is its name.
* Every following line is an entry of that column, until the next ``COLUMN``
  or the ``END`` keyword.
* ``END`` marks the end of the file; anything after it is ignored.
* Blank lines are ignored (they are only there to make the file readable).

The module provides the five functions from the brief:

    load_data_as_dict         file -> {"Names": ["Fred", ...], ...}
    load_data_as_list         file -> [("Names", ["Fred", ...]), ...]
    return_sublist            dict or list -> the entries of one column
    return_sublist_total      dict or list -> sum of a numeric column
    return_sublist_mean       dict or list -> mean of a numeric column

Run it as a script for a demonstration:  python fast_track_project.py [file]
Requires Python 3.10+ (uses ``X | Y`` type unions).
"""

import logging
import math
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Types and constants
# ---------------------------------------------------------------------------

ColumnDict = dict[str, list[str]]
ColumnList = list[tuple[str, list[str]]]
ColumnData = ColumnDict | ColumnList

END_KEYWORD: str = "END"

# "COLUMN" must be a whole word: either alone on the line or followed by
# whitespace and then the name. So "COLUMN Names" is a header, but a data
# value such as "COLUMNIST" or "COLUMNS are fun" is NOT.
_COLUMN_HEADER = re.compile(r"COLUMN(?:\s+(?P<name>.*))?")
_NEWLINE = re.compile(r"\r\n|\r|\n")        # Windows, Unix and old-Mac line endings

DEFAULT_SAMPLE_FILE: Path = Path(__file__).with_name("sample_data.txt")

logger = logging.getLogger(__name__)


class DataFormatError(ValueError):
    """Raised in ``strict`` mode when the file does not follow the COLUMN/END format."""


# ---------------------------------------------------------------------------
# Reading and parsing (one shared implementation for both loaders)
# ---------------------------------------------------------------------------

def _report_problem(message: str, strict: bool) -> None:
    """Raise DataFormatError in strict mode; otherwise log a warning and carry on."""
    if strict:
        raise DataFormatError(message)
    logger.warning(message)


def _read_lines(path: str | Path) -> list[str]:
    """
    Read a text file and return its lines.

    Handles a UTF-8 byte-order mark (BOM, added by some Windows editors) and any
    line-ending style. If the file is not valid UTF-8 it is read as Windows-1252
    instead, with a warning, rather than crashing.
    """
    raw_bytes: bytes = Path(path).read_bytes()
    try:
        text: str = raw_bytes.decode("utf-8-sig")       # "-sig" strips a leading BOM
    except UnicodeDecodeError:
        logger.warning("%s is not valid UTF-8; reading it as Windows-1252", path)
        text = raw_bytes.decode("cp1252", errors="replace")
    return _NEWLINE.split(text)


def _parse_columns(path: str | Path, strict: bool = False) -> ColumnList:
    """
    Parse the file into an ordered list of ``(column_name, entries)`` pairs.

    This is the single parser behind both public loaders, so they can never
    disagree about what the file means. Problems that the brief does not cover
    are handled the same way everywhere (see ``_report_problem``):

    * an entry that appears before any ``COLUMN`` line belongs to no column,
    * a ``COLUMN`` line with no name cannot be used as a key.

    In both cases the entry (or the nameless column's entries) is skipped.
    """
    columns: ColumnList = []
    current_entries: list[str] | None = None       # None = no usable column is open

    for line_number, raw_line in enumerate(_read_lines(path), start=1):
        line: str = raw_line.strip()

        if not line:                                # blank lines carry no data
            continue
        if line == END_KEYWORD:                     # end of the data; ignore the rest
            break

        header = _COLUMN_HEADER.fullmatch(line)
        if header is not None:
            column_name: str | None = header.group("name")
            if column_name is None:
                _report_problem(f"line {line_number}: COLUMN has no name; "
                                "its entries are ignored", strict)
                current_entries = None
            else:
                current_entries = []
                columns.append((column_name, current_entries))
        elif current_entries is None:
            _report_problem(f"line {line_number}: entry {line!r} is not under a "
                            "named COLUMN; ignored", strict)
        else:
            current_entries.append(line)

    return columns


def load_data_as_dict(path: str | Path, strict: bool = False) -> dict[str, list[str]]:
    """
    Load the data file as a dictionary of ``column name -> list of entries``.

    Args:
        path: Path to the text file.
        strict: If True, raise ``DataFormatError`` for format problems instead
            of logging a warning and skipping the offending lines.

    Returns:
        A dictionary whose keys are column names (in file order) and whose
        values are the entries of that column, as strings.

    Note:
        A dictionary cannot hold the same key twice, so if a column name is
        repeated its entries are merged, in file order, with a warning. (Use
        ``load_data_as_list`` to keep repeated columns separate.)

    Raises:
        OSError: If the file cannot be read.
        DataFormatError: Only when ``strict`` is True.
    """
    result: dict[str, list[str]] = {}
    for column_name, entries in _parse_columns(path, strict):
        if column_name in result:
            _report_problem(f"column {column_name!r} appears more than once; "
                            "entries merged", strict)
            result[column_name].extend(entries)
        else:
            result[column_name] = entries
    return result


def load_data_as_list(path: str | Path, strict: bool = False) -> list[tuple[str, list[str]]]:
    """
    Load the data file as a list of ``(column name, list of entries)`` tuples.

    Args:
        path: Path to the text file.
        strict: If True, raise ``DataFormatError`` for format problems instead
            of logging a warning and skipping the offending lines.

    Returns:
        One tuple per column, in file order. Unlike a dictionary, a list can
        represent a repeated column name faithfully, so repeats are kept.

    Raises:
        OSError: If the file cannot be read.
        DataFormatError: Only when ``strict`` is True.
    """
    return _parse_columns(path, strict)


# ---------------------------------------------------------------------------
# Looking things up
# ---------------------------------------------------------------------------

def _is_column_pair(item: object) -> bool:
    """True if ``item`` looks like a ``(column_name, entries)`` pair."""
    return isinstance(item, (tuple, list)) and len(item) == 2


def return_sublist(
    data: dict[str, list[str]] | list[tuple[str, list[str]]], col_name: str
) -> list[str] | None:
    """
    Return the entries of the column called ``col_name``.

    Works with the output of either ``load_data_as_dict`` or
    ``load_data_as_list``.

    Args:
        data: A dictionary of columns, or a list of ``(name, entries)`` tuples.
        col_name: The exact name of the column to find (case-sensitive).

    Returns:
        A copy of the column's entries, or ``None`` if ``data`` is not a
        dictionary or list, if ``col_name`` is not a string, if no column has
        that name, or if the column's entries are not a list. If a list
        contains the name more than once, the first match wins. Items in a
        list that are not ``(name, entries)`` pairs are skipped.

        A copy is returned so that changing the result cannot corrupt ``data``.
    """
    if not isinstance(col_name, str):
        return None

    entries: object = None
    if isinstance(data, dict):
        entries = data.get(col_name)
    elif isinstance(data, list):
        for item in data:
            if _is_column_pair(item) and item[0] == col_name:
                entries = item[1]
                break                               # first match wins
    else:
        return None

    # A bare string such as "123" is iterable, so without this check it would be
    # treated as the entries "1", "2", "3" and give a silently wrong total.
    if not isinstance(entries, (list, tuple)):
        return None
    return list(entries)


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def _to_finite_float(entry: object) -> float | None:
    """
    Convert one entry to a float, or return None if it is not a usable number.

    Python's ``float()`` also accepts "nan", "inf" and digit-grouped text like
    "1_000". Those are not real measurements and would silently poison a total
    or mean, so they are rejected here.
    """
    if isinstance(entry, str) and "_" in entry:
        return None
    try:
        number: float = float(entry)                # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _numeric_column(
    data: dict[str, list[str]] | list[tuple[str, list[str]]], col_name: str
) -> list[float] | None:
    """
    Fetch a column with ``return_sublist`` and convert every entry to a float.

    Returns None if the column is missing or if ANY entry is not a number.
    """
    entries: list[str] | None = return_sublist(data, col_name)
    if entries is None:
        return None

    numbers: list[float] = []
    for entry in entries:
        number: float | None = _to_finite_float(entry)
        if number is None:
            return None                             # one bad entry spoils the column
        numbers.append(number)
    return numbers


def _exact_sum(numbers: list[float]) -> float | None:
    """Sum without accumulating rounding error; None if the result overflows."""
    try:
        return math.fsum(numbers)                   # 10 x 0.1 -> 1.0, not 0.9999999999999999
    except OverflowError:
        return None


def return_sublist_total(
    data: dict[str, list[str]] | list[tuple[str, list[str]]], col_name: str
) -> float | None:
    """
    Return the sum of all entries in the column called ``col_name``.

    Args:
        data: A dictionary of columns, or a list of ``(name, entries)`` tuples.
        col_name: The exact name of the column to add up.

    Returns:
        The total as a float, or ``None`` if the column does not exist or any
        entry cannot be converted to a (finite) number. A column with no
        entries has a total of ``0.0``.
    """
    numbers: list[float] | None = _numeric_column(data, col_name)
    if numbers is None:
        return None
    return _exact_sum(numbers)


def return_sublist_mean(
    data: dict[str, list[str]] | list[tuple[str, list[str]]], col_name: str
) -> float | None:
    """
    Return the mean (average) of all entries in the column called ``col_name``.

    Args:
        data: A dictionary of columns, or a list of ``(name, entries)`` tuples.
        col_name: The exact name of the column to average.

    Returns:
        The mean as a float, or ``None`` if the column does not exist, any
        entry cannot be converted to a (finite) number, or the column is empty
        (a mean of nothing is undefined).
    """
    numbers: list[float] | None = _numeric_column(data, col_name)
    if not numbers:                                 # covers both None and []
        return None
    total: float | None = _exact_sum(numbers)
    return None if total is None else total / len(numbers)


# ---------------------------------------------------------------------------
# Demonstration
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """
    Demonstrate every function on a data file and return an exit code.

    Usage: ``python fast_track_project.py [path_to_data_file]``. With no
    argument it uses ``sample_data.txt`` next to this script, so it works no
    matter which folder you run it from. Returns 0 on success, 1 if the file
    could not be read.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    arguments: list[str] = sys.argv[1:] if argv is None else argv
    file_path: Path = Path(arguments[0]) if arguments else DEFAULT_SAMPLE_FILE

    try:
        data_as_dict: dict[str, list[str]] = load_data_as_dict(file_path)
        data_as_list: list[tuple[str, list[str]]] = load_data_as_list(file_path)
    except OSError as error:
        print(f"Could not read '{file_path}': {error}")
        return 1

    print(f"Fast Track Project demo on {file_path.name}")
    print(f"Loaded {len(data_as_dict)} columns "
          f"(dict and list agree: {data_as_dict == dict(data_as_list)})\n")

    print(f"{'Column':<15}{'Entries':>8}   Total / Mean")
    for column_name, entries in data_as_dict.items():
        total: float | None = return_sublist_total(data_as_dict, column_name)
        mean: float | None = return_sublist_mean(data_as_dict, column_name)
        summary: str = "not numeric" if total is None else f"{total:,.2f} / {mean}"
        print(f"{column_name:<15}{len(entries):>8}   {summary}")

    print("\nLookups:")
    print("  Names (from dict)      :", return_sublist(data_as_dict, "Names"))
    print("  Suppliers (from list)  :", return_sublist(data_as_list, "Suppliers"))
    print("  Unknown column         :", return_sublist(data_as_dict, "Unknown Column"))
    print("  Not a dict or list     :", return_sublist("Names", "Names"))
    print("  Total of a text column :", return_sublist_total(data_as_dict, "Names"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
