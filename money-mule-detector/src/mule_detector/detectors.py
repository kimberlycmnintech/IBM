"""
detectors.py
Pure detector functions — DataFrame in, dict out. No file I/O, no global state.
"""

from __future__ import annotations

from collections import deque

import pandas as pd


def fan_in_fan_out(
    df: pd.DataFrame,
    window_hours: int = 72,
) -> dict[str, dict]:
    """
    For every account that appears as *to_account*, find the maximum number of
    unique *from_account* values seen inside any rolling *window_hours* window.

    Returns
    -------
    dict keyed by account id::

        {
            "ACC-M1": {"max_unique_senders": 10, "window_hours": 72},
            ...
        }
    """
    data = df.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], format="mixed")
    window_td = pd.Timedelta(hours=window_hours)
    result: dict[str, dict] = {}

    for account, group in data.groupby("to_account"):
        group = group.sort_values("timestamp")
        timestamps = group["timestamp"].tolist()
        senders = group["from_account"].tolist()

        # Two-pointer sliding window
        left = 0
        window_senders: deque[str] = deque()
        sender_counts: dict[str, int] = {}
        max_unique = 0

        for right in range(len(timestamps)):
            s = senders[right]
            window_senders.append(s)
            sender_counts[s] = sender_counts.get(s, 0) + 1

            # Evict entries outside the window
            while timestamps[right] - timestamps[left] > window_td:
                evict = senders[left]
                sender_counts[evict] -= 1
                if sender_counts[evict] == 0:
                    del sender_counts[evict]
                window_senders.popleft()
                left += 1

            max_unique = max(max_unique, len(sender_counts))

        result[account] = {
            "max_unique_senders": max_unique,
            "window_hours": window_hours,
        }

    return result


def rapid_passthrough(
    df: pd.DataFrame,
    passthrough_hours: int = 24,
) -> dict[str, dict]:
    """
    For every account that has *both* inbound and outbound transactions, compute
    the fraction of total inbound amount that left within *passthrough_hours*
    hours of each inbound arrival.

    Matching is greedy and chronological: each outbound transaction can only be
    matched once.

    Returns
    -------
    dict keyed by account id::

        {
            "ACC-M1": {"passthrough_ratio": 0.92, "passthrough_hours": 24},
            ...
        }
    """
    data = df.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], format="mixed")
    window_td = pd.Timedelta(hours=passthrough_hours)
    result: dict[str, dict] = {}

    # Pre-index inflows and outflows
    inflows_by_acct = data.groupby("to_account")
    outflows_by_acct = data.groupby("from_account")

    inflow_accounts = set(data["to_account"].unique())
    outflow_accounts = set(data["from_account"].unique())
    candidates = inflow_accounts & outflow_accounts

    for account in candidates:
        inflows = (
            inflows_by_acct.get_group(account)
            .sort_values("timestamp")[["timestamp", "amount"]]
            .reset_index(drop=True)
        )
        outflows = (
            outflows_by_acct.get_group(account)
            .sort_values("timestamp")[["timestamp", "amount"]]
            .reset_index(drop=True)
        )

        total_inflow = inflows["amount"].sum()
        if total_inflow == 0:
            continue

        # Greedy chronological matching
        remaining_outflows = outflows["amount"].tolist()
        out_ts = outflows["timestamp"].tolist()
        used = [False] * len(remaining_outflows)

        matched_sum = 0.0
        for _, inrow in inflows.iterrows():
            window_end = inrow["timestamp"] + window_td
            for j, ots in enumerate(out_ts):
                if not used[j] and inrow["timestamp"] <= ots <= window_end:
                    matched_sum += remaining_outflows[j]
                    used[j] = True

        passthrough_ratio = min(matched_sum / total_inflow, 1.0)
        result[account] = {
            "passthrough_ratio": passthrough_ratio,
            "passthrough_hours": passthrough_hours,
        }

    return result
