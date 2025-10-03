#!/usr/bin/env python3
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import ttest_ind, mannwhitneyu
from math import sqrt

plt.rcParams.update({
    "font.size": 13,
    "axes.titlesize": 16,
    "axes.labelsize": 13,
    "figure.titlesize": 16
})

def ensure_inflows_csv(base: Path):
    inflow_csv = base/"wallet2_inflows_by_day.csv"
    if inflow_csv.exists():
        return
    # Try to generate via inflow viz script
    viz = base/"plot_wallet2_inflows_viz.py"
    if viz.exists():
        import subprocess
        subprocess.run(["python", str(viz)], check=False)
    # After attempt, we just return; load step will error if still missing.

def load_data(base: Path):
    ensure_inflows_csv(base)
    inflow = pd.read_csv(base/"wallet2_inflows_by_day.csv", parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    price  = pd.read_csv(base/"kas-usd-max.csv")
    price["date"] = pd.to_datetime(price["snapped_at"].str.replace(" UTC",""), utc=True).dt.floor("D")
    price = price.rename(columns={"price":"kas_price_usd"})[["date","kas_price_usd"]].drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    price["ret_pct"] = price["kas_price_usd"].pct_change()*100.0
    df = inflow.merge(price, on="date", how="inner")
    df["ret_prev_pct"] = df["ret_pct"].shift(1)
    df["price_prev"] = df["kas_price_usd"].shift(1)
    df["usd_prev"] = df["inflow_kas"] * df["price_prev"]
    return df

def ci95_sem(x: np.ndarray):
    x = x[~np.isnan(x)]
    n = len(x)
    if n == 0:
        return np.nan, np.nan
    mean = x.mean()
    se = x.std(ddof=1)/sqrt(n) if n>1 else 0.0
    lo, hi = mean - 1.96*se, mean + 1.96*se
    return mean, (lo, hi)

def human_kas(x):
    if np.isnan(x): return "nan"
    if x >= 1e9: return f"{x/1e9:.2f}B KAS"
    if x >= 1e6: return f"{x/1e6:.2f}M KAS"
    if x >= 1e3: return f"{x/1e3:.2f}K KAS"
    return f"{x:.0f} KAS"

def human_usd(x):
    if np.isnan(x): return "nan"
    if x >= 1e9: return f"${x/1e9:.2f}B"
    if x >= 1e6: return f"${x/1e6:.2f}M"
    if x >= 1e3: return f"${x/1e3:.2f}K"
    return f"${x:.0f}"

def make_summary_table_png(base: Path, stats_rows, fname_png="buy_the_dip_summary_table.png", fname_csv="buy_the_dip_summary_table.csv"):
    # stats_rows: list of tuples (category, N, mean_kas, mean_usd, mean_prev_price)
    import matplotlib.pyplot as plt
    import pandas as pd
    df = pd.DataFrame(stats_rows, columns=["Category","N","Mean Inflow (KAS)","Mean Inflow (USD)","Mean Prev Price (USD)"])
    df.to_csv(base/fname_csv, index=False)
    fig, ax = plt.subplots(figsize=(8.5, 2.4))
    ax.axis("off")
    cell_text = []
    for _, r in df.iterrows():
        cell_text.append([
            r["Category"],
            int(r["N"]),
            f"{r['Mean Inflow (KAS)']:,.0f}",
            f"${r['Mean Inflow (USD)']:,.0f}",
            f"${r['Mean Prev Price (USD)']:,.4f}" if not np.isnan(r['Mean Prev Price (USD)']) else "nan"
        ])
    tbl = ax.table(cellText=cell_text,
                   colLabels=list(df.columns),
                   cellLoc="center", loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1.2, 1.2)
    out_path = base/fname_png
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved summary table PNG: {out_path}")
    print(f"Saved summary table CSV: {base/fname_csv}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", type=float, default=-1.0, help="Threshold (%%) for 'Drop' bin (ret_prev_pct <= drop)")
    ap.add_argument("--rise", type=float, default=+1.0, help="Threshold (%%) for 'Rise' bin (ret_prev_pct >= rise)")
    ap.add_argument("--bigdrop", type=float, default=None, help="Optional threshold (%%) for 'Big Drop' (ret_prev_pct <= bigdrop)")
    args = ap.parse_args()

    base = Path(__file__).resolve().parent
    df = load_data(base)

    # Categorize by prior-day move
    def cat(r):
        if pd.isna(r): return np.nan
        if args.bigdrop is not None and r <= args.bigdrop:
            return f"Big Drop (≤{args.bigdrop:.1f}%)"
        if r <= args.drop: return f"Drop (≤{args.drop:.1f}%)"
        if r >= args.rise: return f"Rise (≥{args.rise:.1f}%)"
        return f"Flat ({args.drop:.1f}%..{args.rise:.1f}%)"

    df["category"] = df["ret_prev_pct"].apply(cat)
    dfc = df.dropna(subset=["category"]).copy()

    cats = []
    if args.bigdrop is not None: cats.append(f"Big Drop (≤{args.bigdrop:.1f}%)")
    cats += [f"Drop (≤{args.drop:.1f}%)", f"Flat ({args.drop:.1f}%..{args.rise:.1f}%)", f"Rise (≥{args.rise:.1f}%)"]

    # Compute per-bin stats
    stats = []
    for c in cats:
        sel = dfc.loc[dfc["category"]==c]
        kas_vals = sel["inflow_kas"].to_numpy()
        usd_vals = sel["usd_prev"].to_numpy()
        mean_kas, (lo_kas, hi_kas) = ci95_sem(kas_vals)
        mean_usd, _ = ci95_sem(usd_vals)
        med_kas = np.median(kas_vals) if len(kas_vals) else np.nan
        mean_price = np.nanmean(sel["price_prev"].to_numpy()) if len(sel) else np.nan
        stats.append((c, len(sel), mean_kas, med_kas, lo_kas, hi_kas, mean_usd, mean_price))

    # Print stats
    print("Wallet #2 — Inflow after PRIOR-DAY price move categories")
    bd = "None" if args.bigdrop is None else f"≤{args.bigdrop:.1f}%"
    print(f"Thresholds: bigdrop={bd}, drop ≤ {args.drop:.1f}%, rise ≥ {args.rise:.1f}%")
    for c,n,mean_kas,med_kas,lo_kas,hi_kas,mean_usd,mean_price in stats:
        if np.isnan(mean_kas):
            print(f"  {c:<22} N={n:3d}  mean=nan  median=nan  95% CI=nan..nan  |  mean USD=nan  mean prev price=nan")
        else:
            print(f"  {c:<22} N={n:3d}  mean={mean_kas:,.0f}  median={med_kas:,.0f}  95% CI=[{lo_kas:,.0f}, {hi_kas:,.0f}] KAS"
                  f"  |  mean USD={mean_usd:,.0f}  at mean prev price=${mean_price:,.4f}")

    # Hypothesis tests
    drop_vals = dfc.loc[dfc["category"].str.startswith("Drop"), "inflow_kas"].to_numpy()
    rise_vals = dfc.loc[dfc["category"].str.startswith("Rise"), "inflow_kas"].to_numpy()
    if len(drop_vals)>=2 and len(rise_vals)>=2:
        t, p = ttest_ind(drop_vals, rise_vals, equal_var=False)
        try:
            u, p_u = mannwhitneyu(drop_vals, rise_vals, alternative="greater")
        except ValueError:
            u, p_u = (np.nan, np.nan)
        diff = np.nanmean(drop_vals) - np.nanmean(rise_vals)
        print("\nDrop vs Rise tests: (H1: Drop inflows > Rise inflows)")
        print(f"  Welch t-test: t={t:.3f}, p={p:.4f}, mean_diff={diff:,.0f} KAS")
        print(f"  Mann-Whitney U (one-sided): U={u:.0f}, p={p_u:.4f}")
    else:
        print("\nNot enough data in Drop/Rise bins to run tests.")

    if args.bigdrop is not None:
        bigdrop_vals = dfc.loc[dfc["category"].str.startswith("Big Drop"), "inflow_kas"].to_numpy()
        if len(bigdrop_vals)>=2 and len(rise_vals)>=2:
            t2, p2 = ttest_ind(bigdrop_vals, rise_vals, equal_var=False)
            try:
                u2, p2_u = mannwhitneyu(bigdrop_vals, rise_vals, alternative="greater")
            except ValueError:
                u2, p2_u = (np.nan, np.nan)
            diff2 = np.nanmean(bigdrop_vals) - np.nanmean(rise_vals)
            print("\nBig Drop vs Rise tests: (H1: Big Drop inflows > Rise inflows)")
            print(f"  Welch t-test: t={t2:.3f}, p={p2:.4f}, mean_diff={diff2:,.0f} KAS")
            print(f"  Mann-Whitney U (one-sided): U={u2:.0f}, p={p2_u:.4f}")

    # Data for chart
    means_kas = [s[2] for s in stats]
    los_kas   = [s[2]-s[4] if not np.isnan(s[2]) else 0.0 for s in stats]
    his_kas   = [s[5]-s[2] if not np.isnan(s[2]) else 0.0 for s in stats]
    means_usd = [s[6] for s in stats]

    # Plot: bars (KAS) with error bars, and secondary axis line (USD)
    fig, ax = plt.subplots(figsize=(10,6))
    x = np.arange(len(cats))
    bars = ax.bar(x, means_kas)
    ax.errorbar(x, means_kas, yerr=[los_kas, his_kas], fmt='none', capsize=6)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=0)
    ax.set_ylabel("Mean daily inflow (KAS)")
    ax.set_title("Wallet #2 — Inflows after PRIOR-DAY price moves")

    # Add exact mean labels inside bars + N
    for xi, bar, (c, n, mean_kas, *_rest) in zip(x, bars, stats):
        if not np.isnan(mean_kas):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height()*0.5,
                    f"{human_kas(mean_kas)}\n(N={n})",
                    ha="center", va="center")

    # Secondary axis for USD
    ax2 = ax.twinx()
    ax2.plot(x, means_usd, marker='o')
    ax2.set_ylabel("Mean daily inflow (USD, using prior-day price)")

    fig.tight_layout()
    out_png = base/"buy_the_dip_bar_with_usd.png"
    fig.savefig(out_png, dpi=160)
    print(f"\nSaved figure: {out_png}")

    # ---- Summary table (PNG + CSV) ----
    table_rows = [(c, n, mean_kas, mean_usd, mean_price) for (c,n,mean_kas,_med, _lo,_hi,mean_usd,mean_price) in stats]
    make_summary_table_png(base, table_rows)

if __name__ == "__main__":
    main()
