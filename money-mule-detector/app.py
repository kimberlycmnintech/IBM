"""
app.py
Streamlit frontend for the Money Mule Detector.
Run with:  streamlit run app.py
"""

import pathlib
import time

import pandas as pd
import streamlit as st

from mule_detector.scoring import score_accounts
from mule_detector.detectors import fan_in_fan_out, rapid_passthrough

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Money Mule Detector",
    page_icon="🔍",
    layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔍 Mule Detector")
    st.markdown("---")

    st.subheader("Data source")
    default_csv = pathlib.Path(__file__).parent / "data" / "transactions.csv"
    uploaded = st.file_uploader("Upload a transactions CSV", type="csv")
    use_default = st.checkbox(
        "Use generated sample data",
        value=(not uploaded) and default_csv.exists(),
        disabled=bool(uploaded),
    )

    st.markdown("---")
    st.subheader("Detector settings")
    window_hours = st.slider("Fan-in window (hours)", 12, 168, 72, step=12)
    passthrough_hours = st.slider("Pass-through window (hours)", 6, 48, 24, step=6)

    st.markdown("---")
    st.subheader("Scoring weights")
    fan_in_threshold = st.number_input("Fan-in threshold (senders)", 1, 20, 5)
    fan_in_weight = st.number_input("Fan-in weight (pts / sender)", 0.1, 10.0, 1.0, step=0.1)
    pt_weight_high = st.number_input("Pass-through weight ≥ 90%", 0.0, 100.0, 40.0, step=5.0)
    pt_weight_mid = st.number_input("Pass-through weight ≥ 70%", 0.0, 100.0, 20.0, step=5.0)

    run_btn = st.button("▶  Run Detection", type="primary", use_container_width=True)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["timestamp"])

def load_uploaded(file) -> pd.DataFrame:
    return pd.read_csv(file, parse_dates=["timestamp"])

df: pd.DataFrame | None = None

if uploaded:
    df = load_uploaded(uploaded)
elif use_default and default_csv.exists():
    df = load_csv(str(default_csv))

# ── Main area ─────────────────────────────────────────────────────────────────
st.title("💸 Money Mule Account Detector")
st.caption("Detects fan-in/fan-out and rapid pass-through patterns in transaction data.")

if df is None:
    st.info(
        "No data loaded. Upload a CSV or enable **Use generated sample data** "
        "(run `python generate_mock_data.py` first).",
        icon="📂",
    )
    st.stop()

# ── Dataset summary ───────────────────────────────────────────────────────────
with st.expander("📊 Dataset overview", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total transactions", f"{len(df):,}")
    col2.metric("Unique accounts", df[["from_account", "to_account"]].stack().nunique())
    col3.metric(
        "Date range",
        f"{pd.to_datetime(df['timestamp']).min().strftime('%d %b')} – {pd.to_datetime(df['timestamp']).max().strftime('%d %b %Y')}",
    )
    col4.metric("Channels", df["channel"].nunique())
    st.dataframe(df, use_container_width=True, height=200)

# ── Run detection ─────────────────────────────────────────────────────────────
weights = {
    "fan_in_threshold": int(fan_in_threshold),
    "fan_in_weight": float(fan_in_weight),
    "window_hours": int(window_hours),
    "passthrough_weight_high": float(pt_weight_high),
    "passthrough_weight_mid": float(pt_weight_mid),
    "passthrough_hours": int(passthrough_hours),
}

if run_btn or "results" not in st.session_state:
    with st.spinner("Running detectors…"):
        t0 = time.perf_counter()
        results = score_accounts(df, weights=weights)
        elapsed = time.perf_counter() - t0
    st.session_state["results"] = results
    st.session_state["elapsed"] = elapsed
    st.session_state["weights"] = weights
    st.session_state["fi_raw"] = fan_in_fan_out(df, window_hours=int(window_hours))
    st.session_state["pt_raw"] = rapid_passthrough(df, passthrough_hours=int(passthrough_hours))

results = st.session_state["results"]
elapsed = st.session_state["elapsed"]
fi_raw = st.session_state["fi_raw"]
pt_raw = st.session_state["pt_raw"]

# ── KPI row ───────────────────────────────────────────────────────────────────
st.markdown("---")
k1, k2, k3, k4 = st.columns(4)
high_risk = [r for r in results if r["score"] >= 50]
med_risk  = [r for r in results if 20 <= r["score"] < 50]
k1.metric("🔴 High-risk accounts", len(high_risk))
k2.metric("🟡 Medium-risk accounts", len(med_risk))
k3.metric("✅ Total flagged", len(results))
k4.metric("⚡ Analysis time", f"{elapsed*1000:.0f} ms")

# ── Ranked results table ──────────────────────────────────────────────────────
st.markdown("### 🏆 Ranked Suspicious Accounts")

if not results:
    st.success("No suspicious accounts detected with current settings.")
else:
    results_df = pd.DataFrame(results)
    results_df.insert(0, "Rank", range(1, len(results_df) + 1))

    def _colour_row(row):
        if row["score"] >= 50:
            return ["background-color:#3d0000; color:#ff9a9a; font-weight:bold"] * len(row)
        elif row["score"] >= 20:
            return ["background-color:#2e2600; color:#f0c040; font-weight:bold"] * len(row)
        return [""] * len(row)

    styled = (
        results_df.style
        .apply(_colour_row, axis=1)
        .format({"score": "{:.1f}"})
        .hide(axis="index")
    )
    st.dataframe(styled, use_container_width=True, height=min(60 + 35 * len(results_df), 400))

# ── Detail drilldown ──────────────────────────────────────────────────────────
st.markdown("### 🔎 Account Drilldown")

all_flagged = [r["account"] for r in results]
if not all_flagged:
    st.info("No flagged accounts to inspect.")
else:
    chosen = st.selectbox("Select an account", all_flagged)
    row = next(r for r in results if r["account"] == chosen)

    dc1, dc2 = st.columns(2)

    with dc1:
        st.markdown("**Score breakdown**")
        fi = fi_raw.get(chosen)
        pt = pt_raw.get(chosen)
        breakdown = []
        if fi:
            excess = max(0, fi["max_unique_senders"] - int(fan_in_threshold))
            pts = excess * float(fan_in_weight)
            breakdown.append({
                "Signal": "Fan-in",
                "Value": f"{fi['max_unique_senders']} senders in {fi['window_hours']}h",
                "Points": f"+{pts:.1f}",
            })
        if pt:
            ratio = pt["passthrough_ratio"]
            pts = float(pt_weight_high) if ratio >= 0.9 else float(pt_weight_mid) if ratio >= 0.7 else 0.0
            breakdown.append({
                "Signal": "Pass-through",
                "Value": f"{ratio:.0%} forwarded in {pt['passthrough_hours']}h",
                "Points": f"+{pts:.1f}",
            })
        breakdown.append({"Signal": "TOTAL", "Value": "", "Points": f"{row['score']:.1f}"})
        st.dataframe(pd.DataFrame(breakdown), use_container_width=True, hide_index=True)

    with dc2:
        st.markdown("**Transaction history**")
        acct_txns = df[(df["from_account"] == chosen) | (df["to_account"] == chosen)].copy()
        acct_txns["direction"] = acct_txns.apply(
            lambda r: "OUT ↑" if r["from_account"] == chosen else "IN ↓", axis=1
        )
        acct_txns = acct_txns.sort_values("timestamp")[
            ["timestamp", "direction", "from_account", "to_account", "amount", "channel", "country"]
        ]
        st.dataframe(acct_txns, use_container_width=True, height=220, hide_index=True)

# ── Raw signal tables ─────────────────────────────────────────────────────────
with st.expander("🧪 Raw detector output", expanded=False):
    tab1, tab2 = st.tabs(["Fan-in / Fan-out", "Rapid Pass-through"])
    with tab1:
        fi_df = pd.DataFrame(
            [{"account": k, **v} for k, v in fi_raw.items()]
        ).sort_values("max_unique_senders", ascending=False)
        st.dataframe(fi_df, use_container_width=True, hide_index=True)
    with tab2:
        pt_df = pd.DataFrame(
            [{"account": k, **v} for k, v in pt_raw.items()]
        ).sort_values("passthrough_ratio", ascending=False)
        st.dataframe(pt_df, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("Money Mule Detector · built with pandas + streamlit · seed=42")
