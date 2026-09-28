"""
test_detectors.py
Unit tests for pure detector functions using in-memory DataFrames.
"""

import pandas as pd
import pytest
from mule_detector.detectors import fan_in_fan_out, rapid_passthrough


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ts(hours_offset: float) -> pd.Timestamp:
    return pd.Timestamp("2024-01-01 00:00:00") + pd.Timedelta(hours=hours_offset)


def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


# ── fan_in_fan_out ────────────────────────────────────────────────────────────

class TestFanInFanOut:
    def test_three_senders_within_window(self):
        df = _make_df([
            {"txn_id": "T1", "timestamp": _ts(0),  "from_account": "S1", "to_account": "ACCT", "amount": 100, "channel": "FPX", "country": "MY"},
            {"txn_id": "T2", "timestamp": _ts(10), "from_account": "S2", "to_account": "ACCT", "amount": 200, "channel": "FPX", "country": "MY"},
            {"txn_id": "T3", "timestamp": _ts(20), "from_account": "S3", "to_account": "ACCT", "amount": 300, "channel": "FPX", "country": "MY"},
        ])
        result = fan_in_fan_out(df, window_hours=72)
        assert result["ACCT"]["max_unique_senders"] == 3

    def test_sender_outside_window_not_counted(self):
        # S1 at t=0, S2 at t=80h — only one in any 72h window
        df = _make_df([
            {"txn_id": "T1", "timestamp": _ts(0),  "from_account": "S1", "to_account": "ACCT", "amount": 100, "channel": "FPX", "country": "MY"},
            {"txn_id": "T2", "timestamp": _ts(80), "from_account": "S2", "to_account": "ACCT", "amount": 200, "channel": "FPX", "country": "MY"},
        ])
        result = fan_in_fan_out(df, window_hours=72)
        assert result["ACCT"]["max_unique_senders"] == 1

    def test_duplicate_sender_counts_as_one(self):
        df = _make_df([
            {"txn_id": "T1", "timestamp": _ts(0),  "from_account": "S1", "to_account": "ACCT", "amount": 100, "channel": "FPX", "country": "MY"},
            {"txn_id": "T2", "timestamp": _ts(5),  "from_account": "S1", "to_account": "ACCT", "amount": 150, "channel": "FPX", "country": "MY"},
        ])
        result = fan_in_fan_out(df, window_hours=72)
        assert result["ACCT"]["max_unique_senders"] == 1

    def test_window_hours_stored_in_result(self):
        df = _make_df([
            {"txn_id": "T1", "timestamp": _ts(0), "from_account": "S1", "to_account": "ACCT", "amount": 100, "channel": "FPX", "country": "MY"},
        ])
        result = fan_in_fan_out(df, window_hours=48)
        assert result["ACCT"]["window_hours"] == 48


# ── rapid_passthrough ─────────────────────────────────────────────────────────

class TestRapidPassthrough:
    def test_full_passthrough_within_window(self):
        # 1000 in, 1000 out within 24h → ratio = 1.0
        df = _make_df([
            {"txn_id": "T1", "timestamp": _ts(0),  "from_account": "EXT", "to_account": "ACCT", "amount": 1000, "channel": "FPX", "country": "MY"},
            {"txn_id": "T2", "timestamp": _ts(12), "from_account": "ACCT", "to_account": "EXT2", "amount": 1000, "channel": "FPX", "country": "MY"},
        ])
        result = rapid_passthrough(df, passthrough_hours=24)
        assert abs(result["ACCT"]["passthrough_ratio"] - 1.0) < 1e-9

    def test_partial_passthrough(self):
        # 1000 in, 500 out within 24h → ratio = 0.5
        df = _make_df([
            {"txn_id": "T1", "timestamp": _ts(0),  "from_account": "EXT",  "to_account": "ACCT", "amount": 1000, "channel": "FPX", "country": "MY"},
            {"txn_id": "T2", "timestamp": _ts(10), "from_account": "ACCT", "to_account": "EXT2", "amount": 500,  "channel": "FPX", "country": "MY"},
        ])
        result = rapid_passthrough(df, passthrough_hours=24)
        assert abs(result["ACCT"]["passthrough_ratio"] - 0.5) < 1e-9

    def test_outflow_outside_window_not_counted(self):
        # outflow at t=30h, window=24h → ratio = 0 → account absent from result
        df = _make_df([
            {"txn_id": "T1", "timestamp": _ts(0),  "from_account": "EXT",  "to_account": "ACCT", "amount": 1000, "channel": "FPX", "country": "MY"},
            {"txn_id": "T2", "timestamp": _ts(30), "from_account": "ACCT", "to_account": "EXT2", "amount": 1000, "channel": "FPX", "country": "MY"},
        ])
        result = rapid_passthrough(df, passthrough_hours=24)
        # account exists (has both in/out) but ratio should be 0
        assert result.get("ACCT", {}).get("passthrough_ratio", 0.0) == 0.0

    def test_no_outflow_account_excluded(self):
        # account only receives — should not appear in result
        df = _make_df([
            {"txn_id": "T1", "timestamp": _ts(0), "from_account": "EXT", "to_account": "ACCT", "amount": 500, "channel": "FPX", "country": "MY"},
        ])
        result = rapid_passthrough(df)
        assert "ACCT" not in result

    def test_passthrough_hours_stored_in_result(self):
        df = _make_df([
            {"txn_id": "T1", "timestamp": _ts(0),  "from_account": "EXT",  "to_account": "ACCT", "amount": 100, "channel": "FPX", "country": "MY"},
            {"txn_id": "T2", "timestamp": _ts(5),  "from_account": "ACCT", "to_account": "EXT2", "amount": 100, "channel": "FPX", "country": "MY"},
        ])
        result = rapid_passthrough(df, passthrough_hours=12)
        assert result["ACCT"]["passthrough_hours"] == 12
