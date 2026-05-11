"""
Aggregate the per-run Locust CSVs into a results table and two plots:

    plot_latency.png   - avg response time vs concurrent users, one curve per pod count
    plot_throughput.png - requests/sec vs concurrent users, one curve per pod count
    results.csv         - tidy table for the report (pods, users, qps, avg_latency, failures)

Usage:  python3 analyze.py
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parent / "results"
OUTPUT_DIR = Path(__file__).resolve().parent / "plots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PATTERN = re.compile(r"pods(\d+)_users(\d+)_stats\.csv$")


def load_all() -> pd.DataFrame:
    rows = []
    for path in sorted(RESULTS_DIR.glob("pods*_users*_stats.csv")):
        m = PATTERN.search(path.name)
        if not m:
            continue
        pods, users = int(m.group(1)), int(m.group(2))
        df = pd.read_csv(path)
        agg = df[df["Name"] == "Aggregated"].iloc[0]
        rows.append({
            "pods": pods,
            "users": users,
            "requests": int(agg["Request Count"]),
            "failures": int(agg["Failure Count"]),
            "qps": float(agg["Requests/s"]),
            "avg_latency_ms": float(agg["Average Response Time"]),
            "p50_ms": float(agg["50%"]),
            "p95_ms": float(agg["95%"]),
            "p99_ms": float(agg["99%"]),
        })
    return pd.DataFrame(rows).sort_values(["pods", "users"]).reset_index(drop=True)


def find_breaking_point(group: pd.DataFrame) -> dict:
    """
    Heuristic 'breaking point' per pod-count group:
      * Walk user levels low->high.
      * Last row where (failures == 0) AND (avg_latency_ms < 2 * smallest_avg_latency).
    Returns dict with users, avg_latency, qps at that point.
    """
    g = group.sort_values("users").reset_index(drop=True)
    if g.empty:
        return {}
    baseline_latency = g.iloc[0]["avg_latency_ms"]
    stable = g[(g["failures"] == 0) & (g["avg_latency_ms"] < 2 * baseline_latency)]
    if stable.empty:
        # No stable point at all -> take the lowest-latency row regardless
        best = g.sort_values("avg_latency_ms").iloc[0]
    else:
        best = stable.iloc[-1]
    return {
        "pods": int(best["pods"]),
        "max_stable_users": int(best["users"]),
        "avg_latency_ms": float(best["avg_latency_ms"]),
        "qps": float(best["qps"]),
        "failures": int(best["failures"]),
    }


def plot_latency(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    for pods, sub in df.groupby("pods"):
        sub = sub.sort_values("users")
        ax.plot(
            sub["users"], sub["avg_latency_ms"],
            marker="o", label=f"{pods} pod{'s' if pods > 1 else ''}",
        )
    ax.set_xlabel("Concurrent users (Locust)")
    ax.set_ylabel("Average response time (ms)")
    ax.set_title("Latency vs concurrency, by pod count")
    ax.set_xscale("log", base=2)
    ax.set_xticks(sorted(df["users"].unique()))
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.axhline(500, color="red", linestyle="--", linewidth=1, label="HD target (500 ms)")
    ax.grid(True, which="both", linestyle=":", alpha=0.5)
    ax.legend(title="Replicas")
    fig.tight_layout()
    out = OUTPUT_DIR / "plot_latency.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def plot_throughput(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    for pods, sub in df.groupby("pods"):
        sub = sub.sort_values("users")
        ax.plot(
            sub["users"], sub["qps"],
            marker="s", label=f"{pods} pod{'s' if pods > 1 else ''}",
        )
    ax.set_xlabel("Concurrent users (Locust)")
    ax.set_ylabel("Throughput (requests / s)")
    ax.set_title("Throughput vs concurrency, by pod count")
    ax.set_xscale("log", base=2)
    ax.set_xticks(sorted(df["users"].unique()))
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.grid(True, which="both", linestyle=":", alpha=0.5)
    ax.legend(title="Replicas")
    fig.tight_layout()
    out = OUTPUT_DIR / "plot_throughput.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def main() -> None:
    df = load_all()
    if df.empty:
        print(f"No CSVs found in {RESULTS_DIR}. Run benchmark.sh first.")
        return

    print("\n=== Raw measurements ===")
    print(df.to_string(index=False))

    print("\n=== Breaking-point per pod count ===")
    summary_rows = [find_breaking_point(g) for _, g in df.groupby("pods")]
    summary = pd.DataFrame(summary_rows)
    print(summary.to_string(index=False))

    df.to_csv(OUTPUT_DIR / "results.csv", index=False)
    summary.to_csv(OUTPUT_DIR / "breaking_points.csv", index=False)
    print(f"\nwrote {OUTPUT_DIR}/results.csv")
    print(f"wrote {OUTPUT_DIR}/breaking_points.csv")

    plot_latency(df)
    plot_throughput(df)


if __name__ == "__main__":
    main()
