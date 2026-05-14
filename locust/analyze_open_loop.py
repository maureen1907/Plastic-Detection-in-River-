"""
Read vegeta JSON outputs from open_loop_results/ and produce:

    plots/plot_openloop_latency.png    avg latency vs offered rate, per pod count
    plots/plot_openloop_success.png    success rate vs offered rate, per pod count
    plots/openloop_results.csv         tidy results table

The saturation knee on each curve is the open-loop equivalent of the closed-loop
breaking point, and should match Little's Law's μ prediction.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "open_loop_results"
PLOTS_DIR = ROOT / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

PATTERN = re.compile(r"pods(\d+)_rate(\d+)\.json$")


def load_all() -> pd.DataFrame:
    rows = []
    for path in sorted(RESULTS_DIR.glob("pods*_rate*.json")):
        m = PATTERN.search(path.name)
        if not m:
            continue
        pods, rate = int(m.group(1)), int(m.group(2))
        data = json.loads(path.read_text())
        # vegeta JSON keys (latencies in nanoseconds)
        latencies = data.get("latencies", {})
        rows.append({
            "pods": pods,
            "target_rate": rate,
            "achieved_rate": float(data.get("throughput", 0)),
            "requests": int(data.get("requests", 0)),
            "success_rate": float(data.get("success", 0)),  # 0..1
            "errors": data.get("errors", []) and len(data.get("errors", [])) or 0,
            "mean_ms": latencies.get("mean", 0) / 1e6,
            "p50_ms":  latencies.get("50th", 0) / 1e6,
            "p95_ms":  latencies.get("95th", 0) / 1e6,
            "p99_ms":  latencies.get("99th", 0) / 1e6,
            "max_ms":  latencies.get("max",  0) / 1e6,
        })
    return pd.DataFrame(rows).sort_values(["pods", "target_rate"]).reset_index(drop=True)


def find_saturation_point(group: pd.DataFrame) -> dict:
    """
    Saturation knee: lowest target_rate where (success_rate < 1.0) OR
    (mean_ms > 2× mean of lowest-rate run).
    """
    g = group.sort_values("target_rate").reset_index(drop=True)
    if g.empty:
        return {}
    baseline = g.iloc[0]["mean_ms"]
    knee = g[(g["success_rate"] < 1.0) | (g["mean_ms"] > 2 * baseline)]
    if knee.empty:
        # System never saturated within the tested range
        best = g.iloc[-1]
        return {
            "pods": int(best["pods"]),
            "saturation_rate": None,
            "max_stable_rate": int(best["target_rate"]),
            "mean_ms_at_max_stable": float(best["mean_ms"]),
            "achieved_at_max_stable": float(best["achieved_rate"]),
        }
    saturate = knee.iloc[0]
    stable = g[g["target_rate"] < saturate["target_rate"]]
    last_stable = stable.iloc[-1] if not stable.empty else g.iloc[0]
    return {
        "pods": int(saturate["pods"]),
        "saturation_rate": int(saturate["target_rate"]),
        "max_stable_rate": int(last_stable["target_rate"]),
        "mean_ms_at_max_stable": float(last_stable["mean_ms"]),
        "achieved_at_max_stable": float(last_stable["achieved_rate"]),
    }


def plot_latency(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    for pods, sub in df.groupby("pods"):
        sub = sub.sort_values("target_rate")
        ax.plot(sub["target_rate"], sub["mean_ms"], marker="o",
                label=f"{pods} pod{'s' if pods > 1 else ''}")
    ax.set_xlabel("Offered arrival rate λ (req/s)")
    ax.set_ylabel("Mean response time (ms)")
    ax.set_title("Open-loop: mean latency vs offered arrival rate")
    ax.axhline(500, color="red", linestyle="--", linewidth=1, label="500 ms")
    ax.grid(True, which="both", linestyle=":", alpha=0.5)
    ax.legend(title="Replicas")
    fig.tight_layout()
    out = PLOTS_DIR / "plot_openloop_latency.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def plot_success(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    for pods, sub in df.groupby("pods"):
        sub = sub.sort_values("target_rate")
        ax.plot(sub["target_rate"], sub["success_rate"] * 100, marker="s",
                label=f"{pods} pod{'s' if pods > 1 else ''}")
    ax.set_xlabel("Offered arrival rate λ (req/s)")
    ax.set_ylabel("Success rate (%)")
    ax.set_title("Open-loop: success rate vs offered arrival rate")
    ax.set_ylim(-5, 105)
    ax.grid(True, which="both", linestyle=":", alpha=0.5)
    ax.legend(title="Replicas")
    fig.tight_layout()
    out = PLOTS_DIR / "plot_openloop_success.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


def main() -> None:
    df = load_all()
    if df.empty:
        print(f"No JSON results in {RESULTS_DIR}.")
        return

    print("\n=== Open-loop measurements ===")
    print(df[["pods", "target_rate", "achieved_rate", "success_rate",
              "mean_ms", "p95_ms", "p99_ms"]].to_string(index=False))

    print("\n=== Saturation point per pod count ===")
    summary = pd.DataFrame([find_saturation_point(g) for _, g in df.groupby("pods")])
    print(summary.to_string(index=False))

    df.to_csv(PLOTS_DIR / "openloop_results.csv", index=False)
    summary.to_csv(PLOTS_DIR / "openloop_saturation.csv", index=False)
    print(f"\nwrote {PLOTS_DIR}/openloop_results.csv")
    print(f"wrote {PLOTS_DIR}/openloop_saturation.csv")

    plot_latency(df)
    plot_success(df)


if __name__ == "__main__":
    main()
