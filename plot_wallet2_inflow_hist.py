#!/usr/bin/env python3
"""
Plot 2D histograms (weekday x hour) of incoming transfers to Wallet #3.

Features:
1) Automatically loads *_involving.csv from current dir or flow_data_fullhistory/
2) Builds 2D histograms:
   - COUNT of incoming transfers by [weekday x hour]
   - AMOUNT (KAS) of incoming transfers by [weekday x hour]
3) Prints TOP-2 peak weekday/hour cells for both COUNT and AMOUNT with values.
4) Saves two PNGs:
   - wallet2_inflow_heatmap_count.png
   - wallet2_inflow_heatmap_amount.png
   Each heatmap is annotated with the TOP-2 peaks.
5) Draws a grid and adds a compact world-time overlay for UTC, NYC, London, Beijing.
"""

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

WALLET = "kaspa:qpz2vgvlxhmyhmt22h538pjzmvvd52nuut80y5zulgpvyerlskvvwm7n4uk5a"
WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# Fixed offsets for demo clarity (no DST handling here)
NYC_OFFSET = -4      # UTC-4
LONDON_OFFSET = 1    # UTC+1
BEIJING_OFFSET = 8   # UTC+8

def find_involving_csv(base_dir: Path) -> Path:
    # Prefer wallet-specific file if present
    for p in base_dir.glob("*_involving.csv"):
        if WALLET in p.name:
            return p
    # Then subdir flow_data_fullhistory
    fdir = base_dir / "flow_data_fullhistory"
    for p in fdir.glob("*_involving.csv"):
        if WALLET in p.name:
            return p
    # Fallback to first available *_involving.csv
    candidates = list(base_dir.glob("*_involving.csv")) + list(fdir.glob("*_involving.csv"))
    if candidates:
        return candidates[0]
    raise FileNotFoundError("Could not locate *_involving.csv for Wallet #3")

def compute_grids(df: pd.DataFrame):
    """
    Returns (count_grid, amount_grid)
    Shapes: (7 weekdays x 24 hours)
    """
    incoming = df[df["recipient"] == WALLET].copy()
    if incoming.empty:
        return np.zeros((7,24), dtype=int), np.zeros((7,24), dtype=float)

    incoming["timestamp"] = pd.to_datetime(incoming["timestamp"], utc=True)
    incoming["weekday"] = incoming["timestamp"].dt.weekday  # 0=Mon .. 6=Sun
    incoming["hour"] = incoming["timestamp"].dt.hour

    # Count grid
    count_grid = np.zeros((7,24), dtype=int)
    for wd, hr in incoming[["weekday", "hour"]].itertuples(index=False):
        count_grid[int(wd), int(hr)] += 1

    # Amount grid
    amount_grid = np.zeros((7,24), dtype=float)
    for wd, hr, amt in incoming[["weekday","hour","amount_kas"]].itertuples(index=False):
        amount_grid[int(wd), int(hr)] += float(amt)

    return count_grid, amount_grid

def top_k_cells(grid: np.ndarray, k: int = 2):
    """
    Return list of (weekday_idx, hour, value) for top-k cells by value.
    """
    flat_idx = np.argsort(grid, axis=None)[::-1]  # descending
    results = []
    seen = set()
    for idx in flat_idx:
        wd, hr = np.unravel_index(idx, grid.shape)
        val = float(grid[wd, hr])
        key = (int(wd), int(hr))
        if key not in seen:
            results.append((int(wd), int(hr), val))
            seen.add(key)
        if len(results) >= k:
            break
    return results

def annotate_peaks(ax, peaks, title_prefix: str):
    """
    Write up to 2 lines of annotation text in the upper-left of the given axes.
    """
    lines = [f"{title_prefix}"]
    for i, (wd, hr, val) in enumerate(peaks, 1):
        if "Count" in title_prefix:
            lines.append(f"#{i}: {WEEKDAYS[wd]} @ {hr:02d}:00 — {int(val)} tx")
        else:
            lines.append(f"#{i}: {WEEKDAYS[wd]} @ {hr:02d}:00 — {val:,.0f} KAS")
    text = "\n".join(lines)
    ax.text(0.02, 0.98, text, transform=ax.transAxes, va="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.7), fontsize=9)

def add_grid(ax):
    # Create grid lines between cells
    ax.set_xticks(np.arange(-0.5, 24, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 7, 1), minor=True)
    ax.grid(which="minor", linestyle="-", linewidth=0.5, alpha=0.8)
    # Keep major ticks at integer hours & weekdays
    ax.set_xticks(np.arange(0,24,1))
    ax.set_yticks(np.arange(0,7,1))
    ax.set_yticklabels(WEEKDAYS)

def add_world_time_overlay(ax):
    # Add a compact overlay using a secondary x-axis on top with labels at 3-hour intervals
    top_ax = ax.secondary_xaxis("top")
    ticks = np.arange(0, 24, 3)
    labels = []
    for h in ticks:
        nyc = (h + NYC_OFFSET) % 24
        lon = (h + LONDON_OFFSET) % 24
        bjs = (h + BEIJING_OFFSET) % 24
        # Stacked labels: UTC, NYC, LON, BJS
        labels.append(f"UTC {h:02d}\nNYC {nyc:02d}\nLON {lon:02d}\nBJS {bjs:02d}")
    top_ax.set_xticks(ticks)
    top_ax.set_xticklabels(labels)
    top_ax.tick_params(axis="x", labelsize=8, pad=6)

def plot_heatmap(grid: np.ndarray, title: str, cbar_label: str, out_path: Path, peaks):
    fig, ax = plt.subplots(figsize=(11,6))
    im = ax.imshow(grid, aspect="auto", origin="upper")
    ax.set_title(title)
    ax.set_xlabel("Hour (UTC)")
    ax.set_ylabel("Weekday")
    add_grid(ax)
    add_world_time_overlay(ax)
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label(cbar_label)
    annotate_peaks(ax, peaks, "Top-2 Peaks — " + ("Count" if cbar_label=="Count" else "Amount"))
    plt.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)

def main():
    base_dir = Path(__file__).resolve().parent
    inv_csv = find_involving_csv(base_dir)
    print(f"Using involving CSV: {inv_csv}")
    df = pd.read_csv(inv_csv, parse_dates=["timestamp"])

    count_grid, amount_grid = compute_grids(df)

    # Top-2 peaks
    peaks_count = top_k_cells(count_grid, k=2)
    peaks_amount = top_k_cells(amount_grid, k=2)

    print("Top-2 peak cells:")
    for i, (wd, hr, val) in enumerate(peaks_count, 1):
        print(f"  COUNT #{i} -> {WEEKDAYS[wd]} @ {hr:02d}:00  = {int(val)} transfers")
    for i, (wd, hr, val) in enumerate(peaks_amount, 1):
        print(f"  AMOUNT #{i} -> {WEEKDAYS[wd]} @ {hr:02d}:00  = {val:,.6f} KAS")

    # Plots with annotations, grid, and overlay
    out_count = base_dir / "wallet2_inflow_heatmap_count.png"
    out_amount = base_dir / "wallet2_inflow_heatmap_amount.png"
    plot_heatmap(count_grid, "Incoming Transfers — Count (Weekday x Hour, UTC)", "Count", out_count, peaks_count)
    plot_heatmap(amount_grid, "Incoming Transfers — Amount (KAS) (Weekday x Hour, UTC)", "KAS", out_amount, peaks_amount)

    print(f"Saved heatmaps:\n  {out_count}\n  {out_amount}")

if __name__ == "__main__":
    main()
