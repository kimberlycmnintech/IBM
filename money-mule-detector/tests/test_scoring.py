"""
test_scoring.py
Integration tests verifying:
  1. ACC-M1 and ACC-M2 are ranked in the top 2 positions.
  2. ACC-LEGIT (decoy) does not appear in the scored results.

All DataFrames are built in-memory — no CSV file dependency.
"""

import pandas as pd
import pytest
from mule_detector.scoring import score_accounts


BASE = pd.Timestamp("2024-01-01 00:00:00")


def _ts(hours: float) -> pd.Timestamp:
    return BASE + pd.Timedelta(hours=hours)


def _row(txn_id, hours, frm, to, amount):
    return {
        "txn_id": txn_id,
        "timestamp": _ts(hours),
        "from_account": frm,
        "to_account": to,
        "amount": float(amount),
        "channel": "FPX",
        "country": "MY",
    }


def build_test_df() -> pd.DataFrame:
    rows = []

    # ── ACC-M1: 10 unique senders within 48h, 92% forwarded within 24h ───────
    m1_inflow = 0.0
    for i in range(10):
        amt = 1000.0
        rows.append(_row(f"M1-IN-{i}", i * 4, f"S1-{i:02d}", "ACC-M1", amt))
        m1_inflow += amt
    # outflow at t=37h (within 24h of last inbound at t=36h), 92% of total
    rows.append(_row("M1-OUT", 37, "ACC-M1", "EXT-X", m1_inflow * 0.92))

    # ── ACC-M2: 5 unique senders, amounts in [800,2500], 94% out within 12h ──
    m2_inflow = 0.0
    for i in range(5):
        amt = 1500.0
        rows.append(_row(f"M2-IN-{i}", 100 + i * 6, f"S2-{i:02d}", "ACC-M2", amt))
        m2_inflow += amt
    # outflow at t=126h (within 12h of last inbound at t=124h), 94%
    rows.append(_row("M2-OUT", 126, "ACC-M2", "EXT-Y", m2_inflow * 0.94))

    # ── ACC-LEGIT: 15 senders, zero outbound, spaced 30h apart so any 72h
    #    window contains at most 2 senders (well below fan-in threshold of 5)
    for i in range(15):
        rows.append(_row(f"LG-IN-{i}", i * 30, f"CUST-{i:02d}", "ACC-LEGIT", 500.0))

    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def scored():
    df = build_test_df()
    return score_accounts(df)


class TestMulesRankTopTwo:
    def test_top_two_are_mule_accounts(self, scored):
        top_two = {row["account"] for row in scored[:2]}
        assert top_two == {"ACC-M1", "ACC-M2"}, (
            f"Expected ACC-M1 and ACC-M2 in top 2, got: {[r['account'] for r in scored[:2]]}"
        )

    def test_both_mules_have_positive_score(self, scored):
        mule_scores = {row["account"]: row["score"] for row in scored if row["account"] in {"ACC-M1", "ACC-M2"}}
        assert mule_scores.get("ACC-M1", 0) > 0
        assert mule_scores.get("ACC-M2", 0) > 0

    def test_reasons_are_non_empty_for_mules(self, scored):
        mule_rows = [r for r in scored if r["account"] in {"ACC-M1", "ACC-M2"}]
        for row in mule_rows:
            assert row["reasons"].strip(), f"{row['account']} has empty reasons"


class TestDecoyNotFlagged:
    def test_legit_not_in_results(self, scored):
        flagged_accounts = {row["account"] for row in scored}
        assert "ACC-LEGIT" not in flagged_accounts, (
            f"ACC-LEGIT should not be flagged but appears with score "
            f"{next((r['score'] for r in scored if r['account'] == 'ACC-LEGIT'), 'N/A')}"
        )
