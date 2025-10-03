# Kaspa Wallet #2 — XXIMPOD Demo Pack

Reproducible scripts and slides from the **XXIMPOD (Decentralize Capitalism)** podcast segment on Kaspa on-chain forensics focusing on **“Wallet #2”** (#3 at time of podcast, now back to #2).

## Contents

- `Wall2_3.pdf` – slide deck with charts & conclusions  
- `trace_kaspa_fullhistory.py` – downloader for full tx history (Wallet #2)  
- `plot_wallet2_balance_vs_price.py` – balance vs KAS/USD price overlay  
- `plot_wallet2_daily_inflows.py` – daily inflows bar chart  
- `plot_wallet2_inflow_hist.py` – weekday × hour inflow heatmaps (UTC with NYC/LON/Beijing labels)  
- `plot_wallet2_inflows_viz.py` – inflow sources (per-address or grouped by label) + daily inflow CSV  
- `plot_wallet2_outflows_viz.py` – outflow destinations (excludes self-change)  
- `buy_the_dip_demo.py` – “buy the dip?” analysis (KAS bars + USD line, with stats)  
- `kas-usd-max.csv` – daily Kaspa price (from Coingecko; UTC)  
- `known_labels.csv` – optional address → label mappings for grouping

> Wallet #2 address used here:
> `kaspa:qpz2vgvlxhmyhmt22h538pjzmvvd52nuut80y5zulgpvyerlskvvwm7n4uk5a`

---

## Quick Start

### 1) Environment

- Python 3.10+ recommended  
- Install dependencies:
```bash
python -m venv .venv && source .venv/bin/activate
pip install pandas numpy matplotlib scipy
```

### 2) Get transactions

```bash
python trace_kaspa_fullhistory.py
```

- Outputs CSVs like:
  - `flow_data_fullhistory/*_involving.csv`
  - `flow_data_fullhistory/*_all_participants.csv`

> If you already have these from previous runs, you can skip this step.

### 3) Generate charts

Balance vs price:
```bash
python plot_wallet2_balance_vs_price.py
```

Daily inflows (bars):
```bash
python plot_wallet2_daily_inflows.py
```

Inflow heatmaps (weekday × hour, with UTC/NYC/LON/BJS labels):
```bash
python plot_wallet2_inflow_hist.py
```

Inflow sources (per-address or grouped):
```bash
# Per-address view (uses known_labels.csv for display names if present)
python plot_wallet2_inflows_viz.py

# Group by exchange-style labels (Gate.io / Bybit / KuCoin / MEXC / etc.)
python plot_wallet2_inflows_viz.py --group
```
This also writes:
- `wallet2_inflows_by_day.csv` (used by other scripts)
- `wallet2_inflows_by_source.csv` and/or `wallet2_inflows_by_group.csv`

Outflow destinations (excludes self change):
```bash
python plot_wallet2_outflows_viz.py
```

“Buy the dip?” figure + stats:
```bash
# default bins: Drop ≤ -1%, Flat (-1..+1%), Rise ≥ +1%
python buy_the_dip_demo.py

# add a 'Big Drop' bucket (e.g., ≤ -2%):
python buy_the_dip_demo.py --bigdrop -2.0

# customize thresholds:
python buy_the_dip_demo.py --drop -0.5 --rise 0.5 --bigdrop -2.0
```
Outputs:
- `buy_the_dip_bar_with_usd.png` (KAS mean bars + USD mean line)
- `buy_the_dip_summary_table.png` and `buy_the_dip_summary_table.csv`
- Console prints: means, 95% CIs, Welch t-test & Mann-Whitney (one-sided Drop>Rise)

---

## Files & Inputs

- **Transactions**: produced by `trace_kaspa_fullhistory.py` into `flow_data_fullhistory/`.  
  Scripts auto-discover the `*_involving.csv` and `*_all_participants.csv` for the wallet.
- **Price data**: `kas-usd-max.csv` (daily UTC, column `snapped_at`, `price`).  
- **Labels (optional)**: `known_labels.csv` with columns like:
  ```
  address,label
  kaspa:q...,Bybit
  kaspa:q...,GateIORecip7
  ```
  The inflow script dedupes by `address` and groups common patterns when `--group` is used:
  - Gate.io, Bybit, KuCoin, MEXC, Binance, OKX, CoinEx, Uphold (fallback: “Unlabeled”).

---

## Repro Tips

- **Self-change handling**: Outflow charts exclude transactions where sender=recipient (wallet sending to itself / change).  
- **Totals sanity-check**: `plot_wallet2_inflows_viz.py` prints inflow/outflow/net and reconstructs balance from participants CSV to match on-chain truth.  
- **Timezones**: All timestamps are treated as **UTC**; heatmaps display stacked hour labels for **UTC/NYC/LON/BJS** with fixed offsets (no DST).  
- **Stats caution**: The “buy the dip” tests are informative but not conclusive; sample sizes vary across bins.

---

## Typical Outputs

- `wallet2_balance_vs_price.png` – balance overlayed with KAS/USD  
- `wallet2_inflow_heatmap_amount.png` / `wallet2_inflow_heatmap_count.png`  
- `wallet2_inflows_top_sources.png` or `wallet2_inflows_top_groups.png`  
- `wallet2_outflows_top_destinations.png`  
- `wallet2_inflows_by_day.png`  
- `buy_the_dip_bar_with_usd.png`, `buy_the_dip_summary_table.png`

---

## Notes / Disclaimer

- Exchange/desk attributions are **heuristics** based on label patterns and upstream/downstream paths. Treat them as *best-effort inferences*, not definitive identity claims.  
- Use responsibly; nothing here is financial advice.

---

## Contact / Contributions

Issues and PRs welcome.  
If you’re interested in collaborating on Kaspa forensics or **computational neuroscience** track (distributed simulations, model search, ZK-verified results), send an email or DM.
