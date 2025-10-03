#!/usr/bin/env python3
"""
Plot Wallet #2 balance over time and overlay Kaspa USD price.
Also compute Pearson correlation (with p-value) between inflow amounts and price.

Assumptions:
- This script lives in the same directory as `kas-usd-max.csv`
- Wallet #2 CSVs are either in the same directory or in `flow_data_fullhistory/`
- Uses the *_all_participants.csv file to reconstruct balance (net delta per tx)
- Correlations computed with scipy.stats.pearsonr
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import pearsonr

plt.rc("font", size=18)
plt.rc("axes", titlesize=18, labelsize=18)
plt.rc("xtick", labelsize=18)
plt.rc("ytick", labelsize=18)
plt.rc("legend", fontsize=18)
plt.rc("figure", titlesize=24)

WALLET = "kaspa:qpz2vgvlxhmyhmt22h538pjzmvvd52nuut80y5zulgpvyerlskvvwm7n4uk5a"

def find_participants_csv(base_dir: Path) -> Path:
    # Check local dir first
    for p in base_dir.glob("*_all_participants.csv"):
        if WALLET in p.name:
            return p
    # Then subdir flow_data_fullhistory
    fdir = base_dir / "flow_data_fullhistory"
    for p in fdir.glob("*_all_participants.csv"):
        if WALLET in p.name:
            return p
    # Fallback to any *_all_participants.csv if wallet-specific not found
    candidates = list(base_dir.glob("*_all_participants.csv")) + list(fdir.glob("*_all_participants.csv"))
    if candidates:
        return candidates[0]
    raise FileNotFoundError("Could not locate *_all_participants.csv for Wallet #2")

def tx_delta_for_wallet(df: pd.DataFrame, wallet: str) -> pd.DataFrame:
    grp = df.groupby("tx_id")
    rows = []
    for tx, g in grp:
        ts = pd.to_datetime(g["timestamp"].iloc[0], utc=True)
        inflow = g.loc[g["recipient"] == wallet, "amount_kas"].sum()
        outflow = g.loc[g["sender"] == wallet, "amount_kas"].sum()
        delta = inflow - outflow
        if delta != 0:
            rows.append({"tx_id": tx, "timestamp": ts, "delta_kas": delta})
    out = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    out["date"] = out["timestamp"].dt.floor("D")
    return out

def load_price_csv(base_dir: Path) -> pd.DataFrame:
    price_csv = base_dir / "kas-usd-max.csv"
    if not price_csv.exists():
        raise FileNotFoundError("kas-usd-max.csv not found in script directory")
    price = pd.read_csv(price_csv)
    price["date"] = pd.to_datetime(price["snapped_at"].str.replace(" UTC",""), utc=True).dt.floor("D")
    price = price.rename(columns={"price": "kas_price_usd"})
    price = price[["date","kas_price_usd"]].sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    return price

def main():
    base_dir = Path(__file__).resolve().parent
    parts_csv = find_participants_csv(base_dir)
    print(f"Using participants CSV: {parts_csv}")
    parts = pd.read_csv(parts_csv, parse_dates=["timestamp"])
    deltas = tx_delta_for_wallet(parts, WALLET)
    deltas["cum_balance_kas"] = deltas["delta_kas"].cumsum()

    price = load_price_csv(base_dir)

    merged = pd.merge_asof(deltas.sort_values("date"), price.sort_values("date"), on="date")
    # --- Plot balance vs price (dual axis) ---
    plt.ion()
    fig, ax1 = plt.subplots(figsize=(20,10))
    ax1.plot(merged["date"], merged["cum_balance_kas"], color='g', linewidth=4)
    ax1.set_xlabel("Date (UTC)")
    ax1.set_ylabel("Balance (KAS)")
    ax2 = ax1.twinx()
    ax2.plot(merged["date"], merged["kas_price_usd"], alpha=0.7, color='b', linewidth=4)
    ax2.set_ylabel("Kaspa Price (USD)")
    plt.title("Wallet #3 Balance vs Kaspa USD Price")

    # --- Correlations (Pearson r and p-value) ---
    inflows = merged[merged["delta_kas"] > 0][["date","delta_kas","kas_price_usd"]].dropna().copy()
    # Per-transaction correlation
    if len(inflows) >= 3:
        r_tx, p_tx = pearsonr(inflows["delta_kas"], inflows["kas_price_usd"])
    else:
        r_tx, p_tx = (float("nan"), float("nan"))

    # Daily-summed inflows
    daily = inflows.groupby("date", as_index=False)["delta_kas"].sum().rename(columns={"delta_kas":"daily_inflow_kas"})
    daily = daily.merge(price, on="date", how="left").dropna()
    if len(daily) >= 3:
        r_day, p_day = pearsonr(daily["daily_inflow_kas"], daily["kas_price_usd"])
    else:
        r_day, p_day = (float("nan"), float("nan"))

    print("Pearson correlation (inflow vs price):")
    print(f"  Per-transaction: r={r_tx:.3f}, p={p_tx:.3g}")
    print(f"  Daily-summed:    r={r_day:.3f}, p={p_day:.3g}")

    # Add annotation with the daily result (more interpretable)
    ax1.text(
        0.02, 0.95,
        f"Pearson (daily inflow vs price): r={r_day:.3f}, p={p_day:.3g}",
        transform=ax1.transAxes,
        fontsize=14, va="top",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.6)
    )

    plt.tight_layout()
    out_png = base_dir / "wallet2_balance_vs_price.png"
    plt.savefig(out_png, dpi=640)
    print(f"Saved plot: {out_png}")

if __name__ == "__main__":
    main()
