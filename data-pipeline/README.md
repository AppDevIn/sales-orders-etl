# Sales Orders Batch ETL

A small Python + SQLite batch pipeline that loads all `orders_*.csv` files, rejects invalid rows, keeps the latest valid version of each order, and builds trusted reporting tables.

## Run

Requires Python 3 only; there are no third-party dependencies.

Unzip `data.zip` into a `data/` folder inside this directory, so that `data/customers.csv` and `data/orders_*.csv` exist. Then, from this directory:

```bash
python3 pipeline.py
```

The default input directory is `data/` (next to `pipeline.py`), and the output database is `sales.db`.
Both can be overridden:

```bash
python3 pipeline.py --input-dir /path/to/csvs --database /path/to/sales.db
```

## Output tables

- `fact_orders`: 270 clean orders, exactly one row per `order_id`
- `daily_revenue_by_region`: Completed orders (`orders`) and revenue by order date and region
- `rejected_orders`: 6 rejected source rows with their original values, source file, source row, and rejection reason

Total Completed revenue: **$312,130.38**

## Terminal output: run 1

```text
Database: /Users/jeya/Downloads/Data Engineer/data-pipeline/sales.db
fact_orders: 270
rejected_orders: 6
Completed revenue: $312,130.38
Rejected rows by file:
  orders_2025-12-01.csv: 0
  orders_2025-12-02.csv: 3
  orders_2025-12-03.csv: 3
Status changes (later file wins):
  100005: Pending -> Completed in orders_2025-12-02.csv
  100034: Pending -> Completed in orders_2025-12-02.csv
  100046: Pending -> Completed in orders_2025-12-02.csv
  100035: Pending -> Completed in orders_2025-12-02.csv
  100072: Pending -> Completed in orders_2025-12-02.csv
  100002: Pending -> Completed in orders_2025-12-03.csv
  100170: Pending -> Completed in orders_2025-12-03.csv
  100152: Pending -> Completed in orders_2025-12-03.csv
  100027: Pending -> Completed in orders_2025-12-03.csv
Checks passed:
  no duplicate order_id
  no dates outside December 2025
```

## Terminal output: run 2

The second run produced the same counts and revenue, confirming that rows were not doubled.

```text
Database: /Users/jeya/Downloads/Data Engineer/data-pipeline/sales.db
fact_orders: 270
rejected_orders: 6
Completed revenue: $312,130.38
Rejected rows by file:
  orders_2025-12-01.csv: 0
  orders_2025-12-02.csv: 3
  orders_2025-12-03.csv: 3
Status changes (later file wins):
  100005: Pending -> Completed in orders_2025-12-02.csv
  100034: Pending -> Completed in orders_2025-12-02.csv
  100046: Pending -> Completed in orders_2025-12-02.csv
  100035: Pending -> Completed in orders_2025-12-02.csv
  100072: Pending -> Completed in orders_2025-12-02.csv
  100002: Pending -> Completed in orders_2025-12-03.csv
  100170: Pending -> Completed in orders_2025-12-03.csv
  100152: Pending -> Completed in orders_2025-12-03.csv
  100027: Pending -> Completed in orders_2025-12-03.csv
Checks passed:
  no duplicate order_id
  no dates outside December 2025
```

## Rejected rows

### `orders_2025-12-01.csv`: 0

No rows were rejected.

### `orders_2025-12-02.csv`: 3

- CSV line 36: missing `order_id`
- CSV line 78: missing `order_id`
- CSV line 86, order `100176`: quantity is `-3`

### `orders_2025-12-03.csv`: 3

- CSV line 10, order `100273`: customer `C094` is not in `customers.csv`
- CSV line 25, order `100272`: quantity is `0`
- CSV line 99, order `100274`: customer `C099` is not in `customers.csv`

## Status changes

These orders appeared in a later file with a changed status. The later file's version won.

| Order ID | Change | Winning file |
|---|---|---|
| 100005 | Pending to Completed | orders_2025-12-02.csv |
| 100034 | Pending to Completed | orders_2025-12-02.csv |
| 100046 | Pending to Completed | orders_2025-12-02.csv |
| 100035 | Pending to Completed | orders_2025-12-02.csv |
| 100072 | Pending to Completed | orders_2025-12-02.csv |
| 100002 | Pending to Completed | orders_2025-12-03.csv |
| 100170 | Pending to Completed | orders_2025-12-03.csv |
| 100152 | Pending to Completed | orders_2025-12-03.csv |
| 100027 | Pending to Completed | orders_2025-12-03.csv |

## Data problems and handling

- **Invalid business rows:** Six rows failed the stated rules. They are retained in `rejected_orders` with a reason rather than silently discarded.
- **Duplicate order IDs:** There were exact duplicates within files and repeated orders across files. A dictionary keyed by `order_id` guarantees one final row per order. Files are processed by the date in their filename, so a later file replaces an earlier version. For duplicate rows within one file, the last occurrence wins; the supplied within-file duplicates are exact copies.
- **Status updates:** Nine orders changed from Pending to Completed. Their later versions are stored in `fact_orders`.
- **Mixed dates:** Both `YYYY-MM-DD` and `DD/MM/YYYY` are parsed explicitly and stored as ISO `YYYY-MM-DD`. The slash format is interpreted as day/month as specified.
- **Currency text:** Dollar signs and thousands separators are removed before converting revenue to a SQLite `REAL`. A database check confirmed all 270 `revenue` values are stored as numbers.
- **New files:** The pipeline discovers every valid `orders_YYYY-MM-DD.csv`; filenames are not hard-coded.
- **Unexpected schemas or unparseable dates/money:** The run fails with a clear error instead of loading misleading values.

## Design choices

- I used SQLite because it is included with Python and keeps the submission dependency-free.
- The pipeline performs a full refresh inside one SQLite transaction: it rebuilds all three output tables from the source files on every run. This makes daily re-runs idempotent and prevents doubled rows. If the run fails, the transaction rolls back instead of leaving partial tables.
- The primary key on `fact_orders.order_id` enforces the one-row-per-order rule in the database as well as in Python.
- Source filename and CSV line number are stored for traceability.
- Two automated checks run before commit:
  1. no duplicate `order_id` values in `fact_orders`;
  2. no order dates outside December 2025.

## Improvement with more time

For a larger production pipeline, I would add an ingestion audit table containing file checksums, load timestamps, raw/accepted/rejected counts, and run status. That would provide historical observability and allow unchanged files to be skipped safely instead of rebuilding from all source files.

## AI use

I used AI (Claude Code) to help profile the CSV files, draft the pipeline structure, and review the finished code. I did not accept its output without checking it. I independently queried the generated SQLite database to verify the six exact rejected rows, the 270-row fact count, the 12 aggregate rows, and that every `revenue` value had SQLite type `real`. I also ran the complete pipeline twice and compared the printed counts and revenue.

Two concrete checks on AI output:

1. I reconciled the counts by hand: the three files hold 93 + 95 + 105 = 293 data rows. 6 were rejected, 8 were exact duplicates within a file, and 9 were superseded by a later file, which leaves 293 - 6 - 8 - 9 = 270 rows in `fact_orders`. This matched the pipeline output.
2. A final AI code review found that `pipeline.py` imported modules that had been deleted during a late clean-up, so the README's run command would have failed with `ModuleNotFoundError`. I restored the modules, re-ran the pipeline and the tests, and corrected the README, which had also described the default input path incorrectly.

The code is split into `pipeline.py` (entry point), `ingest.py` (file discovery and validation), `parsing.py` (date and money normalisation), `models.py` (dataclasses) and `database.py` (SQLite tables and checks). Unit tests for the validation rules and the data-quality checks live in `test/` and run with `python3 -m pytest` from this directory.
