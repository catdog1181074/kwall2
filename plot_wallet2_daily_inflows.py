#!/usr/bin/env python3
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

WALLET = "kaspa:qpz2vgvlxhmyhmt22h538pjzmvvd52nuut80y5zulgpvyerlskvvwm7n4uk5a"

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

def load_price(base_dir: Path) -> pd.DataFrame:
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
    df = pd.read_csv(parts_csv, parse_dates=["timestamp"])
    deltas = tx_delta_for_wallet(df, WALLET)

    inflow = deltas[deltas["delta_kas"] > 0].copy()
    daily_inflow = inflow.groupby("date", as_index=False)["delta_kas"].sum().rename(columns={"delta_kas": "daily_inflow_kas"})
    price = load_price(base_dir)
    merged = daily_inflow.merge(price, on="date", how="left").sort_values("date")

    fig, ax1 = plt.subplots(figsize=(11,5))
    ax1.bar(merged["date"], merged["daily_inflow_kas"])
    ax1.set_xlabel("Date (UTC)")
    ax1.set_ylabel("Daily inflow (KAS)")
    ax1.set_title("Wallet #2 — Daily Inflows (KAS) with Price Overlay")
    ax2 = ax1.twinx()
    ax2.plot(merged["date"], merged["kas_price_usd"], alpha=0.8)
    ax2.set_ylabel("Kaspa Price (USD)")
    plt.tight_layout()
    out_png = base_dir / "wallet2_daily_inflows.png"
    plt.savefig(out_png, dpi=160)
    print(f"Saved plot: {out_png}")

    tail = merged.tail(7)
    print("\nMost recent 7 days:")
    for _, row in tail.iterrows():
        price_str = "nan" if pd.isna(row['kas_price_usd']) else f"{row['kas_price_usd']:.6f}"
        print(f"{row['date'].date()}: inflow={row['daily_inflow_kas']:,.2f} KAS, price=${price_str}")

if __name__ == "__main__":
    main()
