"""
generate_mock_data.py
Writes data/transactions.csv with ~150 reproducible transactions.
Fixed seeds: random.seed(42), numpy.random.seed(42).
"""

import random
import pathlib
import pandas as pd
import numpy as np

random.seed(42)
np.random.seed(42)

CHANNELS = ["FPX", "DuitNow", "IBG", "cash"]
COUNTRIES = ["MY", "SG", "ID"]
BASE_TS = pd.Timestamp("2024-01-01 08:00:00")
_txn_counter = 0


def _next_id() -> str:
    global _txn_counter
    _txn_counter += 1
    return f"TXN-{_txn_counter:04d}"


def make_txn(ts, frm, to, amount, channel=None, country="MY") -> dict:
    return {
        "txn_id": _next_id(),
        "timestamp": ts.isoformat(),
        "from_account": frm,
        "to_account": to,
        "amount": round(float(amount), 2),
        "channel": channel or random.choice(CHANNELS),
        "country": country,
    }


rows = []

# ── Noise: 20 normal accounts, ~5 txns each ─────────────────────────────────
normal_accounts = [f"ACC-N{i:02d}" for i in range(1, 21)]
for acct in normal_accounts:
    n_txns = random.randint(4, 6)
    for _ in range(n_txns):
        offset_hours = random.uniform(0, 14 * 24)
        ts = BASE_TS + pd.Timedelta(hours=offset_hours)
        sender = random.choice([a for a in normal_accounts if a != acct])
        amount = random.uniform(50, 5000)
        rows.append(make_txn(ts, sender, acct, amount))

# ── ACC-M1: 10 senders within 48 h, 90 %+ forwarded out within 24 h ─────────
M1 = "ACC-M1"
m1_senders = [f"ACC-S1-{i:02d}" for i in range(1, 11)]
m1_inflow_start = BASE_TS + pd.Timedelta(days=3)
m1_inflow = 0.0
m1_last_inbound = m1_inflow_start

for i, sender in enumerate(m1_senders):
    ts = m1_inflow_start + pd.Timedelta(hours=i * 4)   # spread over 36 h < 48 h
    amount = random.uniform(500, 3000)
    rows.append(make_txn(ts, sender, M1, amount, country=random.choice(COUNTRIES)))
    m1_inflow += amount
    m1_last_inbound = ts

# Forward 92 % out within 24 h of last inbound
m1_forward_amount = m1_inflow * 0.92
m1_out_ts = m1_last_inbound + pd.Timedelta(hours=random.uniform(1, 20))
recipient = random.choice(normal_accounts)
rows.append(make_txn(m1_out_ts, M1, recipient, m1_forward_amount, country="SG"))

# ── ACC-M2: 5 senders, RM 800–2500, forwarded out within 12 h ───────────────
M2 = "ACC-M2"
m2_senders = [f"ACC-S2-{i:02d}" for i in range(1, 6)]
m2_inflow_start = BASE_TS + pd.Timedelta(days=7)
m2_inflow = 0.0
m2_last_inbound = m2_inflow_start

for i, sender in enumerate(m2_senders):
    ts = m2_inflow_start + pd.Timedelta(hours=i * 6)
    amount = random.uniform(800, 2500)
    rows.append(make_txn(ts, sender, M2, amount, country=random.choice(COUNTRIES)))
    m2_inflow += amount
    m2_last_inbound = ts

# Forward 94 % out within 12 h of last inbound
m2_forward_amount = m2_inflow * 0.94
m2_out_ts = m2_last_inbound + pd.Timedelta(hours=random.uniform(0.5, 10))
recipient2 = random.choice(normal_accounts)
rows.append(make_txn(m2_out_ts, M2, recipient2, m2_forward_amount, country="ID"))

# ── ACC-LEGIT: 15 senders (merchant), zero outbound ─────────────────────────
LEGIT = "ACC-LEGIT"
legit_senders = [f"ACC-C{i:02d}" for i in range(1, 16)]
for i, sender in enumerate(legit_senders):
    ts = BASE_TS + pd.Timedelta(hours=i * 30)   # 30h spacing -> max 2 per 72h window
    amount = random.uniform(100, 4000)
    rows.append(make_txn(ts, sender, LEGIT, amount, channel="FPX", country="MY"))

# ── Shuffle & write ──────────────────────────────────────────────────────────
df = pd.DataFrame(rows)
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

out_path = pathlib.Path(__file__).parent / "data" / "transactions.csv"
out_path.parent.mkdir(exist_ok=True)
df.to_csv(out_path, index=False)

print(f"Written {len(df)} transactions -> {out_path}")
