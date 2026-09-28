# Money Mule Detector — Build Plan

## Overview

Build a Python CLI tool that reads a transaction CSV, runs two behavioural detectors
(fan-in/fan-out and rapid pass-through), scores each account with weighted points and
human-readable reasons, then prints a ranked Rich table. The project is a proper
installable package (`pip install -e .`) with pytest tests that use only in-memory
DataFrames.

**Scope:** five files of production code + two test files + one mock-data generator.  
**Non-goals:** no database, no REST API, no streaming input, no real data.

---

## Package Layout

```
money-mule-detector/
├── pyproject.toml
├── generate_mock_data.py
├── data/
│   └── transactions.csv          (git-ignored, generated)
├── src/
│   └── mule_detector/
│       ├── __init__.py
│       ├── detectors.py
│       ├── scoring.py
│       └── report.py
├── detect.py
└── tests/
    ├── __init__.py
    ├── test_detectors.py
    └── test_scoring.py
```

---

## Sub-Tasks

---

### Sub-Task 1 — Project scaffold (pyproject.toml + __init__.py)

**Intent**  
Create the installable package skeleton so all subsequent files can be imported
consistently and dependencies are declared in one place.

**Expected Outcomes**
- `pip install -e .` succeeds with no errors.
- `import mule_detector` works from any directory after install.
- `pandas`, `rich`, and `pytest` are declared as dependencies.

**Todo List**
1. Create `pyproject.toml` with `[project]` metadata, `dependencies` listing
   `pandas`, `rich`, and `pytest`, and a `[project.scripts]` entry pointing
   `detect = "detect:main"` (or keep detect.py as a plain script — either is fine).
2. Create `src/mule_detector/__init__.py` (empty is fine).
3. Create `tests/__init__.py` (empty).
4. Create `data/` directory; add `data/transactions.csv` to `.gitignore`.

**Relevant Context**  
- Build backend: `hatchling` or `setuptools` (either works; prefer `hatchling` for
  minimal config).  
- `src/` layout requires `[tool.setuptools.packages.find] where = ["src"]` or the
  hatchling equivalent.

**Status** `[ ] pending`

---

### Sub-Task 2 — generate_mock_data.py

**Intent**  
Produce a reproducible, realistic CSV that contains known mule patterns and a decoy,
so the detectors can be validated deterministically.

**Expected Outcomes**
- Running `python generate_mock_data.py` creates `data/transactions.csv` with ~150 rows.
- Schema: `txn_id, timestamp, from_account, to_account, amount, channel, country`.
- `timestamp` is a proper ISO-8601 datetime string parseable by `pd.to_datetime`.
- Three named personas are always present:

  | Account | Pattern |
  |---------|---------|
  | ACC-M1  | Receives from ≥ 10 distinct senders within any 2-day window; forwards ≥ 90 % of inflow out within 24 h |
  | ACC-M2  | Receives from ≥ 5 distinct senders; amounts RM 800–2 500; forwards out within 12 h |
  | ACC-LEGIT | High inflow from many senders (looks like a merchant) but does NOT forward funds out |

- ~20 normal accounts generate noise transactions with random amounts, random
  timestamps spread over 14 days, low fan-in, and no forwarding pattern.
- Fixed seed (`random.seed(42)`, `numpy.random.seed(42)`) guarantees identical output
  on every run.

**Todo List**
1. Import `random`, `numpy`, `pandas`, `pathlib`.
2. Define helper `make_txn(txn_id, ts, frm, to, amount, channel, country)` returning a dict.
3. Build normal noise: 20 accounts × ~5 transactions each, random timestamps over 14 days.
4. Build ACC-M1 pattern:
   - 10 inbound transactions from 10 unique senders, all within a 48-hour window
     (e.g. day 3 of the 14-day range).
   - Outbound transactions summing to ≥ 90 % of total inbound, all timestamped within
     24 h of the last inbound.
5. Build ACC-M2 pattern:
   - 5 inbound transactions from 5 unique senders, amounts in [800, 2500].
   - Outbound transactions timestamped within 12 h of each inbound, summing to ≥ 90 %.
6. Build ACC-LEGIT pattern:
   - 15 inbound transactions from distinct senders (merchant-like fan-in).
   - Zero outbound transactions.
7. Concatenate all rows, shuffle with fixed seed, reset index, write to `data/transactions.csv`.

**Relevant Context**  
- Channel values: `["FPX", "DuitNow", "IBG", "cash"]`  
- Country values: `["MY", "SG", "ID"]` (mostly MY for noise, mix for mules)
- Amount for noise: uniform RM 50–5 000

**Status** `[ ] pending`

---

### Sub-Task 3 — detectors.py (pure detector functions)

**Intent**  
Implement the two behavioural signals as pure functions: DataFrame in, dict out.
Pure functions make unit-testing trivial and keep the scoring layer decoupled.

**Expected Outcomes**
- `fan_in_fan_out(df: pd.DataFrame, window_hours: int = 72) -> dict[str, dict]`  
  Returns, for every account that appears as `to_account`, the maximum number of
  unique `from_account` values seen in any rolling `window_hours` window.  
  Shape of each value: `{"max_unique_senders": int, "window_hours": int}`.
- `rapid_passthrough(df: pd.DataFrame, passthrough_hours: int = 24) -> dict[str, dict]`  
  For every account that has both inbound and outbound transactions, computes the
  fraction of total inbound amount that left within `passthrough_hours` hours of
  arrival (per-inbound matching).  
  Shape of each value: `{"passthrough_ratio": float, "passthrough_hours": int}`.
- Both functions treat `timestamp` as `pd.Timestamp`; they call `pd.to_datetime`
  internally if needed so callers can pass raw string columns.
- No side effects, no file I/O, no global state.

**Todo List**
1. Create `src/mule_detector/detectors.py`.
2. Implement `fan_in_fan_out`:
   - Group by `to_account`.
   - Sort each group by `timestamp`.
   - Use a sliding-window approach (two-pointer or `pd.Grouper`) to find max unique
     senders in any `window_hours`-wide window.
   - Return dict keyed by account id.
3. Implement `rapid_passthrough`:
   - For each account A, collect all rows where `to_account == A` (inflows) and all
     rows where `from_account == A` (outflows).
   - For each inflow, sum outflows whose timestamp falls within
     `[inflow.timestamp, inflow.timestamp + passthrough_hours]`.
   - `passthrough_ratio = min(matched_outflow_sum / total_inflow, 1.0)`.
   - Only include accounts that have at least one outflow.
4. Add module-level docstrings and argument docstrings.

**Relevant Context**  
- The sliding-window for fan-in can be implemented with `collections.deque` and a
  sorted timestamp list per account — no need for a heavy time-series library.
- Edge case: an outflow can only be "matched" once (it cannot cancel two separate inflows).
  For simplicity, match greedily in chronological order.

**Status** `[ ] pending`

---

### Sub-Task 4 — scoring.py (weighted scoring + reason builder)

**Intent**  
Combine the two detector outputs into a single numeric score per account and produce
a human-readable reason string explaining which signals fired.

**Expected Outcomes**
- `score_accounts(df: pd.DataFrame, weights: dict | None = None) -> list[dict]`  
  Returns a list of dicts sorted descending by score:
  ```
  [{"account": str, "score": float, "reasons": str}, ...]
  ```
- Default weights (overridable via `weights` param):
  ```
  fan_in_weight     = 1.0  per unique sender above threshold (threshold = 5)
  passthrough_weight = 40.0 if passthrough_ratio >= 0.9 else
                       20.0 if passthrough_ratio >= 0.7 else 0
  ```
- Reason string example:
  `"Fan-in: 10 unique senders in 72h (+10.0 pts); Pass-through: 92% in 24h (+40.0 pts)"`
- Only accounts with score > 0 appear in the output list.

**Todo List**
1. Create `src/mule_detector/scoring.py`.
2. Import and call `fan_in_fan_out` and `rapid_passthrough` from `detectors`.
3. Union the account keys from both detector results.
4. For each account, compute fan-in points and passthrough points using default or
   provided weights.
5. Build reason string from whichever signals fired (skip signals with 0 points).
6. Sort by score descending, filter score > 0, return list of dicts.

**Relevant Context**  
- Threshold of 5 unique senders means fan-in points = `max(0, senders - 5) * fan_in_weight`.
- The `weights` dict keys: `"fan_in_weight"`, `"passthrough_weight_high"`,
  `"passthrough_weight_mid"`, `"fan_in_threshold"`, `"passthrough_hours"`,
  `"window_hours"`.

**Status** `[ ] pending`

---

### Sub-Task 5 — report.py + detect.py (Rich table + CLI entry point)

**Intent**  
Surface the scoring results as a formatted Rich table in the terminal, and wire
everything together in a single runnable script.

**Expected Outcomes**
- `render_table(results: list[dict]) -> None` prints a Rich `Table` with columns:
  `Rank`, `Account`, `Score`, `Reasons`. High-score rows highlighted in red,
  mid-score in yellow, rest in default colour.
- `detect.py` (at repo root):
  1. Accepts an optional `--csv` CLI argument (default: `data/transactions.csv`).
  2. Loads the CSV with `pd.read_csv`, parses `timestamp`.
  3. Calls `score_accounts`.
  4. Calls `render_table`.
  5. Exits with code 0 on success, 1 if the CSV is not found.
- Running `python detect.py` produces a ranked table in the terminal.

**Todo List**
1. Create `src/mule_detector/report.py` with `render_table`.
2. Define colour thresholds: score ≥ 50 → red, score ≥ 20 → yellow.
3. Create `detect.py` at repo root with `argparse` for `--csv`.
4. In `detect.py`, import `mule_detector.scoring` and `mule_detector.report`.
5. Handle `FileNotFoundError` with a clear error message and `sys.exit(1)`.

**Relevant Context**  
- Rich table: `rich.table.Table`, `rich.console.Console`.
- Use `rich.text.Text` with `style="bold red"` / `"bold yellow"` for coloured rows.

**Status** `[ ] pending`

---

### Sub-Task 6 — Tests (pytest)

**Intent**  
Verify the two key acceptance criteria with fast, isolated, in-memory tests —
no CSV file required.

**Expected Outcomes**
- `tests/test_detectors.py`: unit tests for `fan_in_fan_out` and `rapid_passthrough`
  with hand-crafted minimal DataFrames confirming correct numeric outputs.
- `tests/test_scoring.py`:
  - `test_mules_rank_top_two`: build a DataFrame that mirrors the M1/M2/LEGIT personas
    at minimum fidelity, call `score_accounts`, assert ACC-M1 and ACC-M2 are in the
    top 2 positions (order between them is not enforced).
  - `test_decoy_not_flagged`: assert ACC-LEGIT does not appear in the scored results
    (score == 0 or absent from the returned list).
- All tests pass with `pytest tests/`.

**Todo List**
1. Create `tests/test_detectors.py`:
   - Test `fan_in_fan_out` with 3 senders in a 72 h window → expect `max_unique_senders == 3`.
   - Test `rapid_passthrough` with a known inflow/outflow pair → expect correct ratio.
2. Create `tests/test_scoring.py`:
   - Build minimal DataFrames for M1 (10 senders, 90 % passthrough), M2 (5 senders,
     90 % passthrough), and LEGIT (15 senders, 0 % passthrough).
   - Assert top-2 accounts are `{"ACC-M1", "ACC-M2"}`.
   - Assert `ACC-LEGIT` not in scored accounts.

**Relevant Context**  
- Use `pd.DataFrame` with explicit `timestamp` columns as `pd.Timestamp` objects
  to avoid any CSV parsing dependency.
- Keep fixtures as module-level functions or `pytest.fixture` — whichever is simpler.

**Status** `[ ] pending`

---

## Dependency Summary

| Package | Role |
|---------|------|
| `pandas` | DataFrame manipulation in all modules |
| `rich`   | Terminal table rendering in `report.py` |
| `pytest` | Test runner |
| `numpy`  | Random data generation in `generate_mock_data.py` only |

`numpy` is a transitive dependency of `pandas` and does not need to be declared
separately unless a minimum version is required.

---

## Acceptance Criteria (Definition of Done)

1. `pip install -e .` installs cleanly.
2. `python generate_mock_data.py` produces `data/transactions.csv` with ~150 rows.
3. `python detect.py` prints a Rich table with ACC-M1 and ACC-M2 in the top 2 rows.
4. ACC-LEGIT does not appear in the top results (score = 0).
5. `pytest tests/` passes with 0 failures.
6. All detector functions are pure (no file I/O, no global state).
