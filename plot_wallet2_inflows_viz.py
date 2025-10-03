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

def find_participants_csv(base_dir: Path) -> Path:
    for p in base_dir.glob("*_all_participants.csv"):
        if WALLET in p.name:
            return p
    fdir = base_dir / "flow_data_fullhistory"
    for p in fdir.glob("*_all_participants.csv"):
        if WALLET in p.name:
            return p
    cands = list(base_dir.glob("*_all_participants.csv")) + list(fdir.glob("*_all_participants.csv"))
    if cands:
        return cands[0]
    raise FileNotFoundError("Could not locate *_all_participants.csv for Wallet #2")

def tx_deltas(parts_df: pd.DataFrame) -> pd.DataFrame:
    grp = parts_df.groupby("tx_id")
    rows = []
    for tx, g in grp:
        ts = pd.to_datetime(g["timestamp"].iloc[0], utc=True)
        inflow = g.loc[g["recipient"] == WALLET, "amount_kas"].sum()
        outflow = g.loc[g["sender"] == WALLET, "amount_kas"].sum()
        delta = inflow - outflow
        rows.append({"tx_id": tx, "timestamp": ts, "delta_kas": delta})
    out = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    out["date"] = out["timestamp"].dt.floor("D")
    return out

def load_labels(base_dir: Path):
    lbl = base_dir / "known_labels.csv"
    if not lbl.exists():
        return None
    df = pd.read_csv(lbl)
    cols = {c.lower(): c for c in df.columns}
    addr_col = next((c for c in cols if c in ("address","addr","sender","kas_address")), None)
    label_col = next((c for c in cols if c in ("label","name","tag")), None)
    if addr_col is None or label_col is None:
        return None
    df = df.rename(columns={cols[addr_col]:"address", cols[label_col]:"label"})
    return df[["address","label"]]

def load_price(base_dir: Path) -> pd.DataFrame:
    price_csv = base_dir / "kas-usd-max.csv"
    if not price_csv.exists():
        return None
    price = pd.read_csv(price_csv)
    price["date"] = pd.to_datetime(price["snapped_at"].str.replace(" UTC",""), utc=True).dt.floor("D")
    price = price.rename(columns={"price": "kas_price_usd"})
    price = price[["date","kas_price_usd"]].sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    return price

def truncate_addr(a: str) -> str:
    if not isinstance(a, str): return a
    if len(a) <= 20: return a
    return a[:10] + "…" + a[-8:]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=12, help="Top-N sources to plot")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    inv_csv = find_involving_csv(base_dir)
    print(f"Using involving CSV: {inv_csv}")
    df = pd.read_csv(inv_csv, parse_dates=["timestamp"])

    # Inflows and outflows (exclude self on both sides)
    inflows = df[(df["recipient"] == WALLET) & (df["sender"] != WALLET)].copy()
    outflows_to_others = df[(df["sender"] == WALLET) & (df["recipient"] != WALLET)].copy()

    if inflows.empty:
        print("No inflows from other addresses found.")
        return

    inflows["date"] = inflows["timestamp"].dt.floor("D")
    outflows_to_others["date"] = outflows_to_others["timestamp"].dt.floor("D")

    # Aggregations: by source
    by_src = (
        inflows.groupby("sender")
        .agg(
            tx_count=("tx_id","nunique"),
            total_kas=("amount_kas","sum"),
            first_seen=("timestamp","min"),
            last_seen=("timestamp","max"),
        )
        .sort_values("total_kas", ascending=False)
        .reset_index()
    )
    by_src["first_seen"] = by_src["first_seen"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    by_src["last_seen"] = by_src["last_seen"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    by_day = (
        inflows.groupby("date", as_index=False)["amount_kas"].sum()
        .rename(columns={"amount_kas":"inflow_kas"})
        .sort_values("date")
    )

    # Save CSVs
    out1 = base_dir / "wallet2_inflows_by_source.csv"
    out2 = base_dir / "wallet2_inflows_by_day.csv"
    by_src.to_csv(out1, index=False)
    by_day.to_csv(out2, index=False)
    print(f"Saved CSVs:\n  {out1}\n  {out2}")

    # Consistency checks
    total_in = inflows["amount_kas"].sum()
    total_out = outflows_to_others["amount_kas"].sum()
    parts_csv = find_participants_csv(base_dir)
    parts = pd.read_csv(parts_csv, parse_dates=["timestamp"])
    deltas = tx_deltas(parts)
    reconstructed_balance = deltas["delta_kas"].sum()
    print(f"\nTotals: inflow={total_in:,.6f} KAS, outflow_to_others={total_out:,.6f} KAS, net={total_in - total_out:,.6f} KAS")
    print(f"Reconstructed balance from participants CSV: {reconstructed_balance:,.6f} KAS")

    # Load labels and join
    labels_df = load_labels(base_dir)
    if labels_df is not None:
        by_src = by_src.merge(labels_df, left_on="sender", right_on="address", how="left")
        by_src["label"] = by_src["label"].fillna("")
        by_src = by_src.drop(columns=["address"])
        print("Joined labels from known_labels.csv")
    else:
        by_src["label"] = ""

    # Plot top-N sources with % share annotations
    topN = by_src.head(args.top).copy()
    topN = topN[::-1]  # reverse for horizontal chart
    disp = topN.apply(lambda r: (r["label"] if r["label"] else truncate_addr(r["sender"])), axis=1)
    shares = topN["total_kas"] / total_in * 100.0

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh(disp, topN["total_kas"])
    ax.set_title(f"Wallet #2 — Top {len(topN)} Inflow Sources (KAS)")
    ax.set_xlabel("Total Inflow (KAS)")
    ax.set_ylabel("Source (label or truncated address)")
    for i, (v, s) in enumerate(zip(topN["total_kas"], shares)):
        ax.text(v, i, f" {v:,.0f}  ({s:.1f}%)", va="center")
    plt.tight_layout()
    out_png1 = base_dir / "wallet2_inflows_top_sources.png"
    plt.savefig(out_png1, dpi=160)
    print(f"Saved plot: {out_png1}")

    # Plot inflows by day with price overlay (secondary axis)
    price = None
    try:
        price = load_price(base_dir)
    except Exception as e:
        price = None
    fig2, ax2 = plt.subplots(figsize=(12, 5))
    ax2.plot(by_day["date"], by_day["inflow_kas"], marker="o")
    ax2.set_title("Wallet #2 — Inflows by Day (KAS) with Price Overlay")
    ax2.set_xlabel("Date (UTC)")
    ax2.set_ylabel("Inflow (KAS)")
    ax2.grid(True, alpha=0.3)
    if price is not None and not price.empty:
        merged = pd.merge_asof(by_day.sort_values("date"), price.sort_values("date"), on="date")
        ax3 = ax2.twinx()
        ax3.plot(merged["date"], merged["kas_price_usd"], alpha=0.8)
        ax3.set_ylabel("Kaspa Price (USD)")
    plt.tight_layout()
    out_png2 = base_dir / "wallet2_inflows_by_day.png"
    plt.savefig(out_png2, dpi=160)
    print(f"Saved plot: {out_png2}")

if __name__ == "__main__":
    main()
