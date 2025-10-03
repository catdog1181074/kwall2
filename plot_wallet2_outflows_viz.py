#!/usr/bin/env python3
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

WALLET = "kaspa:qpz2vgvlxhmyhmt22h538pjzmvvd52nuut80y5zulgpvyerlskvvwm7n4uk5a"

plt.rcParams.update({
    "font.size": 14,
    "axes.titlesize": 18,
    "axes.labelsize": 14,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "legend.fontsize": 12,
    "figure.titlesize": 18
})

def find_involving_csv(base_dir: Path) -> Path:
    for p in base_dir.glob("*_involving.csv"):
        if WALLET in p.name:
            return p
    fdir = base_dir / "flow_data_fullhistory"
    for p in fdir.glob("*_involving.csv"):
        if WALLET in p.name:
            return p
    cands = list(base_dir.glob("*_involving.csv")) + list(fdir.glob("*_involving.csv"))
    if cands:
        return cands[0]
    raise FileNotFoundError("Could not locate *_involving.csv for Wallet #2")

def load_labels(base_dir: Path):
    lbl = base_dir / "known_labels.csv"
    if not lbl.exists():
        return None
    df = pd.read_csv(lbl, dtype=str)
    # Normalize and dedupe to avoid exploding rows on merge
    df.columns = [c.strip() for c in df.columns]
    cols = {c.lower(): c for c in df.columns}
    addr_col = next((c for c in cols if c in ("address","addr","sender","kas_address","recipient")), None)
    label_col = next((c for c in cols if c in ("label","name","tag")), None)
    if addr_col is None or label_col is None:
        return None
    df = df.rename(columns={cols[addr_col]:"address", cols[label_col]:"label"})
    df["address"] = df["address"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()
    df = df.dropna(subset=["address"]).drop_duplicates(subset=["address"], keep="last")
    return df[["address","label"]]

def truncate_addr(a: str) -> str:
    if not isinstance(a, str): return a
    if len(a) <= 20: return a
    return a[:10] + "…" + a[-8:]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=3, help="Top-N destinations to plot")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    inv_csv = find_involving_csv(base_dir)
    print(f"Using involving CSV: {inv_csv}")
    df = pd.read_csv(inv_csv, parse_dates=["timestamp"])

    # Exclude self-transfers
    outflows = df[(df["sender"] == WALLET) & (df["recipient"] != WALLET)].copy()
    if outflows.empty:
        print("No outflows to other addresses found (after excluding self-transfers).")
        return
    outflows["date"] = outflows["timestamp"].dt.floor("D")

    # Aggregations
    by_dest = (
        outflows.groupby("recipient")
        .agg(
            tx_count=("tx_id","nunique"),
            total_kas=("amount_kas","sum"),
            first_seen=("timestamp","min"),
            last_seen=("timestamp","max"),
        )
        .sort_values("total_kas", ascending=False)
        .reset_index()
    )
    by_dest["first_seen"] = by_dest["first_seen"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    by_dest["last_seen"] = by_dest["last_seen"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    by_day = (
        outflows.groupby("date", as_index=False)["amount_kas"].sum()
        .rename(columns={"amount_kas":"outflow_kas"})
        .sort_values("date")
    )

    # Save CSVs
    out1 = base_dir / "wallet2_outflows_by_destination.csv"
    out2 = base_dir / "wallet2_outflows_by_day.csv"
    by_dest.to_csv(out1, index=False)
    by_day.to_csv(out2, index=False)
    print(f"Saved CSVs:\n  {out1}\n  {out2}")

    # Load labels and join
    labels_df = load_labels(base_dir)
    if labels_df is not None:
        by_dest = by_dest.merge(labels_df, left_on="recipient", right_on="address", how="left")
        by_dest["label"] = by_dest["label"].fillna("")
        by_dest = by_dest.drop(columns=["address"])
        print("Joined labels from known_labels.csv")
    else:
        by_dest["label"] = ""

    # Plot top-N destinations
    topN = by_dest.head(args.top).copy()
    topN = topN[::-1]  # reverse for horizontal bar chart
    disp = topN.apply(lambda r: (r["label"] if r["label"] else truncate_addr(r["recipient"])), axis=1)
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh(disp, topN["total_kas"])
    ax.set_title(f"Wallet #3 — Top {len(topN)} Outflow Destinations (KAS)")
    ax.set_xlabel("Total Outflow (KAS)")
    ax.set_ylabel("Destination (label or truncated address)")
    for i, v in enumerate(topN["total_kas"]):
        ax.text(v, i, f" {v:,.0f}", va="center")
    plt.tight_layout()
    out_png1 = base_dir / "wallet2_outflows_top_destinations.png"
    plt.savefig(out_png1, dpi=160)
    print(f"Saved plot: {out_png1}")

    # Plot outflows by day
    fig2, ax2 = plt.subplots(figsize=(12, 5))
    ax2.plot(by_day["date"], by_day["outflow_kas"], marker="o")
    ax2.set_title("Wallet #3 — Outflows by Day (KAS)")
    ax2.set_xlabel("Date (UTC)")
    ax2.set_ylabel("Outflow (KAS)")
    ax2.grid(True, alpha=0.3)
    plt.tight_layout()
    out_png2 = base_dir / "wallet2_outflows_by_day.png"
    plt.savefig(out_png2, dpi=160)
    print(f"Saved plot: {out_png2}")

if __name__ == "__main__":
    main()
