# Text-File Column Extractor

> Reads spreadsheet-style data stored as plain text (`COLUMN` / `END` format) and turns it into Python data you can look up, total and average, with careful handling of the messy cases real files contain.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Dependencies](https://img.shields.io/badge/dependencies-none%20(stdlib%20only)-brightgreen) ![Tests](https://img.shields.io/badge/tests-66%20passing-brightgreen)

---

## Table of contents

1. [What this project does](#1-what-this-project-does)
2. [The data format](#2-the-data-format)
3. [Quick start](#3-quick-start)
4. [The five functions](#4-the-five-functions)
5. [Behaviour reference](#5-behaviour-reference)
6. [The sample dataset](#6-the-sample-dataset)
7. [How it works](#7-how-it-works)
8. [Testing](#8-testing)
9. [Project layout](#9-project-layout)
10. [Notes on the original brief](#10-notes-on-the-original-brief)
11. [Limitations](#11-limitations)

---

## 1. What this project does

Some systems export tables as simple text, with one value per line and keywords to mark where each column starts and where the file ends. This project:

1. **Parses** such a file into a Python dictionary (`column name → list of entries`) or a list of tuples (`(column name, list of entries)`).
2. **Looks up** any column by name, from either representation.
3. **Calculates** the **total** and the **mean** of a numeric column, and reports `None` when a column is missing or isn't entirely numeric.

It is a small library plus a command-line demonstration. It has no third-party dependencies.

---

## 2. The data format

```
COLUMN Names
Fred
John

COLUMN Credit
10
20
END
```

| Rule | Details |
|------|---------|
| **`COLUMN <name>`** | Starts a column. `COLUMN` is all uppercase and must be a whole word. Everything after it on that line (with surrounding spaces removed) is the column name, and names may contain spaces (`COLUMN Product Names`). |
| **Entries** | Every following line belongs to that column until the next `COLUMN` line or `END`. Entries are kept as **strings**, with surrounding whitespace removed. |
| **`END`** | Marks the end of the data. Anything after it is ignored. A file without `END` is still read to its last line. |
| **Blank lines** | Ignored. They are only there for readability. |
| **Line endings** | Windows (`\r\n`), Unix (`\n`) and old-Mac (`\r`) all work. |
| **Encoding** | UTF-8, with or without a byte-order mark. A file that isn't valid UTF-8 is read as Windows-1252 with a warning. |

Because `COLUMN` must be a whole word, a *value* such as `COLUMNIST` or `COLUMNS are fun` is correctly treated as data and not mistaken for a header.

### What the loaders produce

For the file above:

```python
# load_data_as_dict("data.txt")
{"Names": ["Fred", "John"], "Credit": ["10", "20"]}

# load_data_as_list("data.txt")
[("Names", ["Fred", "John"]), ("Credit", ["10", "20"])]
```

---

## 3. Quick start

**Requirements:** Python 3.10 or newer. No packages to install.

```bash
python file_extractor.py              # demo on the bundled sample_data.txt
python file_extractor.py my_data.txt  # demo on your own file
python -m unittest -v                     # run the test suite
```

The demo works from any folder: the default sample file is found relative to the script, not the current directory.

### Demo output

```
File Extractor Project demo on sample_data.txt
Loaded 10 columns (dict and list agree: True)

Column          Entries   Total / Mean
Names                20   not numeric
Addresses            20   not numeric
Credit               20   454.00 / 22.7
Product Names        20   not numeric
Suppliers            20   not numeric
Prices               20   454.00 / 22.7
Order Dates          20   not numeric
Quantities           20   254.00 / 12.7
Categories           20   not numeric
Regions              20   not numeric

Lookups:
  Names (from dict)      : ['Fred', 'John', 'Alice', 'Bob', ...]
  Suppliers (from list)  : ['SupplierA', 'SupplierB', 'SupplierC', ...]
  Unknown column         : None
  Not a dict or list     : None
  Total of a text column : None
```

(Lookup lists are shortened here.) If the file can't be read, the demo prints a message and exits with code `1`.

### Using it as a library

```python
from file_extractor import (
    load_data_as_dict, load_data_as_list,
    return_sublist, return_sublist_total, return_sublist_mean,
)

data = load_data_as_dict("sample_data.txt")

return_sublist(data, "Names")[:2]      # ['Fred', 'John']
return_sublist_total(data, "Credit")   # 454.0
return_sublist_mean(data, "Quantities")  # 12.7
return_sublist_total(data, "Names")    # None  (not numeric)
return_sublist(data, "Nope")           # None  (no such column)

# Every function accepts the list form too:
rows = load_data_as_list("sample_data.txt")
return_sublist(rows, "Suppliers")[:2]  # ['SupplierA', 'SupplierB']
```

---

## 4. The five functions

| Function | Input | Output |
|----------|-------|--------|
| `load_data_as_dict(path, strict=False)` | File path (`str` or `Path`) | `dict[str, list[str]]` |
| `load_data_as_list(path, strict=False)` | File path (`str` or `Path`) | `list[tuple[str, list[str]]]` |
| `return_sublist(data, col_name)` | A dict **or** list from the loaders, and a column name | `list[str] \| None` |
| `return_sublist_total(data, col_name)` | Same | `float \| None` |
| `return_sublist_mean(data, col_name)` | Same | `float \| None` |

### `return_sublist`

Returns the entries of the named column (as a copy), or `None` when:

- `data` is neither a dictionary nor a list;
- `col_name` is not a string;
- no column has that name. In a dictionary this means the name is not a key. In a list it means the name is not the first element of any tuple. Names are **case-sensitive** and must match exactly.

### `return_sublist_total` and `return_sublist_mean`

Both read the column through `return_sublist`, then convert **every** entry to a number:

- If the column is missing, or **any one** entry isn't a valid number, the result is `None`.
- Otherwise `return_sublist_total` returns the sum and `return_sublist_mean` returns the average.
- Sums are computed with `math.fsum`, so rounding error doesn't build up: ten entries of `0.1` total exactly `1.0`, not `0.9999999999999999`.

### Optional `strict` mode

By default, format problems that the format definition doesn't cover are **logged as warnings and skipped**. Pass `strict=True` to get a `DataFormatError` (a `ValueError`) instead:

```python
load_data_as_dict("messy.txt")               # warns and carries on
load_data_as_dict("messy.txt", strict=True)  # raises DataFormatError
```

Warnings use Python's `logging` module under the logger name `file_extractor`. The demo enables them; in your own code add `logging.basicConfig(level=logging.WARNING)` to see them.

---

## 5. Behaviour reference

### What counts as a number

Entries are converted with Python's `float()`, with two additions, because the following would give a meaningless total or mean:

| Entry | Result | Why |
|-------|--------|-----|
| `10`, `-5`, `+5`, `1.5`, `1e3`, ` 7 ` | ✅ number | Ordinary numeric text (surrounding spaces are fine) |
| `nan`, `inf`, `-inf`, `Infinity`, `1e999` | ❌ `None` | Not finite: one of these would turn the whole total into `nan` or `inf` |
| `1_000` | ❌ `None` | Python's `float()` accepts underscores; data files shouldn't |
| `2025-01-15`, `three`, empty string | ❌ `None` | Not numbers |
| a sum too large for a float | ❌ `None` | Overflow is reported as `None`, not an exception |

### Edge cases

| Situation | What happens |
|-----------|--------------|
| Column with **no entries** | Returned as `[]`; its **total** is `0.0` and its **mean** is `None` (an average of nothing is undefined) |
| **Repeated column name**, dictionary | The entries are **merged** in file order, with a warning (a dict can't hold a key twice). `strict=True` raises |
| **Repeated column name**, list | Both are **kept**, as the list can represent them. `return_sublist` returns the **first** match |
| Entry **before any `COLUMN`** line | Skipped with a warning (it belongs to no column). `strict=True` raises |
| `COLUMN` line with **no name** | The line and its entries are skipped with a warning. `strict=True` raises |
| List items that aren't `(name, entries)` pairs | Skipped by `return_sublist`, never a crash |
| A column "value" that isn't a list (e.g. the string `"123"`) | `return_sublist` returns `None`, so `"123"` is never summed digit by digit |
| Empty file | `{}` or `[]` |
| File does not exist | The loaders raise `FileNotFoundError` (the demo reports it cleanly and exits with `1`) |

`return_sublist` returns a **copy**, so changing the result can't alter the loaded data.

---

## 6. The sample dataset

`sample_data.txt` has **10 columns of 20 entries each** (200 values), using Windows line endings and a blank line between columns:

| Column | Contents | Numeric? | Total / Mean |
|--------|----------|----------|--------------|
| `Names` | Fred, John, Alice, … | No | `None` |
| `Addresses` | Pontypridd, Treforest, Cardiff, … | No | `None` |
| `Credit` | 10, 20, 15, 25, … | Yes | 454.0 / 22.7 |
| `Product Names` | Widget1, Widget2, Gadget1, … | No | `None` |
| `Suppliers` | SupplierA … SupplierT | No | `None` |
| `Prices` | 10, 20, 15, 25, … (same values as `Credit`) | Yes | 454.0 / 22.7 |
| `Order Dates` | 2025-01-15, 2025-02-20, … | No (dates) | `None` |
| `Quantities` | 5, 10, 8, 12, … | Yes | 254.0 / 12.7 |
| `Categories` | Electronics, Tools, Hardware, … | No | `None` |
| `Regions` | Wales, England, Scotland | No | `None` |

---

## 7. How it works

```
 file ──► _read_lines ──► _parse_columns ──┬─► load_data_as_list  (list of tuples)
          (decode, split)   (one shared     └─► load_data_as_dict  (merge repeats)
                             parser)
                                               │
              return_sublist ◄─────────────────┘   (find a column, defensively)
                    │
                    ▼
            _numeric_column ──► return_sublist_total / return_sublist_mean
            (every entry must          (math.fsum)
             be a finite number)
```

- **`_read_lines`** decodes the bytes (UTF-8 with an optional BOM, falling back to Windows-1252) and splits on any line-ending style.
- **`_parse_columns`** is the **single parser** behind both loaders, so the dictionary and the list can never disagree about what the file means. A short regular expression, `COLUMN(?:\s+(?P<name>.*))?` matched against the whole line, recognises headers as a whole word only.
- **`return_sublist`** validates its inputs (`data` type, `col_name` type, shape of each list item) before touching them.
- **`_numeric_column`** reuses `return_sublist` and converts each entry with `_to_finite_float`; one invalid entry makes the whole column `None`.
- **Total and mean** share that helper and differ only in the final step.

All public functions carry full type annotations and docstrings. `return_sublist_total` and `return_sublist_mean` are annotated `-> float | None`, which is what they return.

---

## 8. Testing

```bash
python -m unittest -v      # standard library only
```

The suite has **66 tests** in `test_file.py`:

| Group | What it covers |
|-------|----------------|
| Sample file | 10 columns in order; 20 entries each; exact first values; dict and list loaders agree; totals and means (454.0 / 22.7 / 254.0 / 12.7); text columns give `None` |
| Parsing | Three line-ending styles; no final newline; no `END`; text after `END`; blank lines and padding; UTF-8 BOM; non-ASCII text; Windows-1252 fallback; empty file; empty column; `str` and `Path` inputs; missing file |
| Header recognition | `COLUMNIST` / `COLUMNS are fun` / `COLUMN2` are data; case-sensitivity; extra spaces or tabs; symbols in names |
| Malformed input | Stray entries; nameless `COLUMN`; strict mode; repeated columns in dict (merged) and list (kept) |
| `return_sublist` | Dict and list; missing and case-mismatched names; non-dict/list input; non-string `col_name`; malformed list items; non-list values; first-match rule; returns a copy |
| Numbers | Integers, decimals, signs, scientific notation, padding; `nan`/`inf`/`1e999`; underscores; dates; empty column; exact summation; overflow; huge integers; `return_sublist` is really used |
| Typing and demo | `float \| None` annotations; every public function annotated and documented; demo exit codes and output; working-directory independence |

The same edge cases were also run against the original exam solution to confirm what each change fixes. On the real sample file the two versions give **identical** results.

---

## 9. Project layout

```
.
├── file_extractor.py        # the library + demo (main)
├── test_file.py   # 66 unit tests
├── sample_data.txt              # the 10-column sample dataset
└── README.md
```

---

## 10. Notes on the original brief

- The brief says "create **four (4)** functions" but describes **five** (`load_data_as_dict`, `load_data_as_list`, `return_sublist`, `return_sublist_total`, `return_sublist_mean`). All five are implemented, with the names and parameters the brief gives.
- The brief's placeholder for `return_sublist_total` and `return_sublist_mean` is annotated `-> list[str] | None`, which looks like a copy-paste from `return_sublist`: the text says they return a **sum** and a **mean**. They are annotated `-> float | None` here to match what they return.
- Where the brief says "convertible to a float", `nan` and `inf` technically convert. They are rejected here because they make every total and mean meaningless (see [section 5](#what-counts-as-a-number)).

---

## 11. Limitations

- The whole file is read into memory, which is fine for files of ordinary size but not designed for gigabyte-scale data.
- Entries stay as **strings**. Converting to numbers happens only inside `return_sublist_total` and `return_sublist_mean`, and values such as `1,000` or `$10` are not recognised as numbers.
- Column names are matched **exactly** and case-sensitively.
- Columns are independent lists, so they are not checked to have the same length (the sample's columns all have 20 entries, but the format doesn't require it).
- Requires Python 3.10+.
