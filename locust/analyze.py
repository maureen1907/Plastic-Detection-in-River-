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
    Per the FIT5225 A1 rubric, the breaking point is "the threshold at which
    response times degrade exponentially OR HTTP 500/503 errors begin to occur."

    Operationalised:
      * 'Exponential degradation' = latency growth ratio at successive
        Locust user-count doublings > 2 (super-linear growth: when input
        doubles, output more than doubles).
      * 'Errors occur' = failures > 0.

    Walks user levels low -> high; the first row that triggers either
    criterion is the breaking point. The row *before* it is the maximum
    stable point reported in the table.
    """
    g = group.sort_values("users").reset_index(drop=True)
    if g.empty:
        return {}

    breaking_idx = None
    for i in range(1, len(g)):
        prev_latency = g.iloc[i - 1]["avg_latency_ms"]
        cur = g.iloc[i]
        ratio = cur["avg_latency_ms"] / prev_latency if prev_latency else float("inf")
        # User counts double each step, so ratio > 2 means super-linear.
        if int(cur["failures"]) > 0 or ratio > 2.0:
            breaking_idx = i
            break

    if breaking_idx is None:
        # System never broke within the tested range; report the last row.
        last = g.iloc[-1]
        return {
            "pods": int(last["pods"]),
            "max_stable_users": int(last["users"]),
            "avg_latency_ms": float(last["avg_latency_ms"]),
            "qps": float(last["qps"]),
            "failures": int(last["failures"]),
            "breaking_user_count": None,
        }

    max_stable = g.iloc[breaking_idx - 1]
    breaking = g.iloc[breaking_idx]
    return {
        "pods": int(max_stable["pods"]),
        "max_stable_users": int(max_stable["users"]),
        "avg_latency_ms": float(max_stable["avg_latency_ms"]),
        "qps": float(max_stable["qps"]),
        "failures": int(max_stable["failures"]),
        "breaking_user_count": int(breaking["users"]),
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
    ax.axhline(500, color="red", linestyle="--", linewidth=1, label="500 ms")
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
