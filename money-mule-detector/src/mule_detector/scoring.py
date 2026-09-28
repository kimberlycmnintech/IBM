"""
scoring.py
Combines detector outputs into a weighted score and human-readable reason per account.
"""

from __future__ import annotations

import pandas as pd

from mule_detector.detectors import fan_in_fan_out, rapid_passthrough

# Default weight configuration
DEFAULT_WEIGHTS: dict[str, float | int] = {
    "fan_in_threshold": 5,          # senders above this count towards score
    "fan_in_weight": 1.0,           # points per sender above threshold
    "window_hours": 72,             # rolling window for fan-in detector
    "passthrough_weight_high": 40.0,  # ratio >= 0.90
    "passthrough_weight_mid": 20.0,   # ratio >= 0.70
    "passthrough_hours": 24,          # window for pass-through detector
}


def score_accounts(
    df: pd.DataFrame,
    weights: dict | None = None,
) -> list[dict]:
    """
    Run both detectors on *df*, compute a weighted score for every account,
    and return a list of dicts sorted descending by score.

    Only accounts with score > 0 are included.

    Parameters
    ----------
    df : pd.DataFrame
        Transaction data with columns: txn_id, timestamp, from_account,
        to_account, amount, channel, country.
    weights : dict, optional
        Override any key in DEFAULT_WEIGHTS.

    Returns
    -------
    list of dicts::

        [
            {"account": "ACC-M1", "score": 45.0, "reasons": "Fan-in: ..."},
            ...
        ]
    """
    cfg = {**DEFAULT_WEIGHTS, **(weights or {})}

    fan_in_results = fan_in_fan_out(df, window_hours=int(cfg["window_hours"]))
    passthrough_results = rapid_passthrough(df, passthrough_hours=int(cfg["passthrough_hours"]))

    all_accounts = set(fan_in_results) | set(passthrough_results)
    scored: list[dict] = []

    for account in all_accounts:
        score = 0.0
        reason_parts: list[str] = []

        # ── Fan-in signal ────────────────────────────────────────────────────
        fi = fan_in_results.get(account)
        if fi is not None:
            senders = fi["max_unique_senders"]
            threshold = int(cfg["fan_in_threshold"])
            excess = max(0, senders - threshold)
            fi_pts = excess * float(cfg["fan_in_weight"])
            if fi_pts > 0:
                score += fi_pts
                reason_parts.append(
                    f"Fan-in: {senders} unique senders in {fi['window_hours']}h "
                    f"(+{fi_pts:.1f} pts)"
                )

        # ── Pass-through signal ──────────────────────────────────────────────
        pt = passthrough_results.get(account)
        if pt is not None:
            ratio = pt["passthrough_ratio"]
            if ratio >= 0.90:
                pt_pts = float(cfg["passthrough_weight_high"])
            elif ratio >= 0.70:
                pt_pts = float(cfg["passthrough_weight_mid"])
            else:
                pt_pts = 0.0

            if pt_pts > 0:
                score += pt_pts
                reason_parts.append(
                    f"Pass-through: {ratio:.0%} in {pt['passthrough_hours']}h "
                    f"(+{pt_pts:.1f} pts)"
                )

        if score > 0:
            scored.append(
                {
                    "account": account,
                    "score": score,
                    "reasons": "; ".join(reason_parts),
                }
            )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
