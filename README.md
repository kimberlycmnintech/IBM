# 💸 Money Mule Detector

A Python tool that analyses transaction CSVs to detect **money mule** accounts using two behavioural signals: **fan-in/fan-out** and **rapid pass-through**. Results are surfaced via a Rich terminal table and an interactive Streamlit dashboard.

---

## Features
<img width="638" height="331" alt="image" src="https://github.com/user-attachments/assets/637f285f-c18e-4d26-a13a-5c5be5794d4a" />
<img width="638" height="293" alt="image" src="https://github.com/user-attachments/assets/fd598bf8-5ad9-4e62-9396-9f2ba8aaca35" />



- **Fan-in / Fan-out detector** — flags accounts that receive funds from many unique senders within a configurable time window
- **Rapid pass-through detector** — flags accounts that forward a high fraction of received funds back out within a short time window
- **Weighted scoring engine** — combines both signals into a numeric risk score with human-readable reasons
- **Rich CLI table** — colour-coded ranked output (🔴 high / 🟡 medium risk) in the terminal
- **Streamlit dashboard** — interactive web UI with adjustable thresholds, drilldown per account, and raw detector output

---

## Project Structure

```
money-mule-detector/
├── pyproject.toml              # Package metadata & dependencies
├── generate_mock_data.py       # Generates reproducible sample data (seed=42)
├── detect.py                   # CLI entry point
├── app.py                      # Streamlit web UI
├── data/
│   └── transactions.csv        # Generated data (git-ignored)
├── src/
│   └── mule_detector/
│       ├── __init__.py
│       ├── detectors.py        # Pure detector functions
│       ├── scoring.py          # Weighted scoring + reason builder
│       └── report.py           # Rich terminal table renderer
└── tests/
    ├── test_detectors.py
    └── test_scoring.py
```

---

## Quick Start

### 1. Install dependencies

```bash
cd money-mule-detector
pip install -e ".[dev]"
```

### 2. Generate sample data

```bash
python generate_mock_data.py
```

This creates `data/transactions.csv` (~150 rows) with known mule personas (`ACC-M1`, `ACC-M2`) and a decoy (`ACC-LEGIT`), using a fixed random seed for reproducibility.

### 3. Run the CLI detector

```bash
python detect.py
# or with a custom CSV:
python detect.py --csv path/to/transactions.csv
```

Expected output: a ranked Rich table with `ACC-M1` and `ACC-M2` in the top 2 rows.

### 4. Launch the Streamlit dashboard

```bash
streamlit run app.py
```

---

## Detection Logic

### Fan-in / Fan-out

```python
fan_in_fan_out(df, window_hours=72)
```

Returns the maximum number of **unique senders** seen in any rolling `window_hours` window for each destination account. Accounts receiving from many distinct sources in a short window are flagged.

### Rapid Pass-through

```python
rapid_passthrough(df, passthrough_hours=24)
```

For each account with both inbound and outbound transactions, computes the fraction of total inbound amount that was forwarded out within `passthrough_hours` hours of arrival.

### Scoring

| Signal | Condition | Points |
|--------|-----------|--------|
| Fan-in | Each unique sender above threshold (default: 5) | +1.0 pts each |
| Pass-through | Ratio ≥ 90 % | +40.0 pts |
| Pass-through | Ratio ≥ 70 % | +20.0 pts |

Only accounts with `score > 0` appear in the output.

---

## Mock Data Personas

| Account | Pattern |
|---------|---------|
| `ACC-M1` | ≥ 10 unique senders in 48 h; forwards ≥ 90 % of inflow within 24 h |
| `ACC-M2` | ≥ 5 unique senders; amounts RM 800–2,500; forwards ≥ 90 % within 12 h |
| `ACC-LEGIT` | High inflow from many senders (merchant-like) but **no outbound** — score = 0 |

~20 normal accounts generate random noise transactions over a 14-day window.

---

## Running Tests

```bash
pytest tests/
```

Tests use in-memory DataFrames only — no CSV file required.

---

## Dependencies

| Package | Role |
|---------|------|
| `pandas >= 2.0` | DataFrame manipulation |
| `rich >= 13.0` | Terminal table rendering |
| `numpy >= 1.24` | Random data generation |
| `streamlit >= 1.35` | Interactive web dashboard |
| `pytest >= 7.0` | Test runner (dev only) |

---

## Configuration

All scoring thresholds and weights are overridable by passing a `weights` dict to `score_accounts`:

```python
from mule_detector.scoring import score_accounts

custom_weights = {
    "fan_in_threshold": 5,
    "fan_in_weight": 1.0,
    "window_hours": 72,
    "passthrough_weight_high": 40.0,
    "passthrough_weight_mid": 20.0,
    "passthrough_hours": 24,
}

results = score_accounts(df, weights=custom_weights)
```

---

## License

MIT
