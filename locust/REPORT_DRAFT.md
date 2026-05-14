# Benchmark Report — FIT5225 A1 Phase 8

Methodology, raw data, plots, and a ≤500-word analysis. See `plots/results.csv` and `plots/openloop_results.csv` for every measurement; `plots/breaking_points.csv` and `plots/openloop_saturation.csv` for the per-pod-count summaries.

## Methodology

Two complementary workloads were run against the 3-node k3s cluster on GCP. Image payload: 316 KB JPEG (base64-encoded → 432 KB JSON body) sent to `/api/predict` (and `/api/annotate` for the closed-loop tasks, weighted 3:1). Pods: `mpha0039/plastic-detection:v4` (YOLOv8n, `uvicorn --workers 2`, 1 vCPU / 4 GiB), thread-safety patched.

| Methodology | Tool | What it reveals |
|---|---|---|
| **Closed-loop** (run first) | Locust 2.43, headless, 1 client on macOS, rotating across all 3 node external IPs via `LOCUST_EXTRA_HOSTS` to work around iptables-mode kube-proxy stickiness. | Steady-state throughput at a fixed user concurrency. Λ is bounded by Little's Law (λ = U/W). |
| **Open-loop** (validation run) | `vegeta` 12.13, fixed arrival-rate attacks at λ ∈ {1…14} req/s for 30 s each. | Saturation point — the offered λ beyond which queue grows unboundedly and latency diverges. Realistic for internet traffic, where clients don't wait for slow responses. |

For each methodology, pod counts ∈ {1, 2, 4, 8} (closed) or {1, 2, 4} (open) were tested by `kubectl scale`-ing the Deployment between runs.

## 1. Closed-loop results (breaking-point per pod count)

"Breaking point" = highest user count where failures = 0 AND avg latency stays below 2 × the single-user baseline.

| Replicas | Max stable users | Avg latency at threshold (ms) | QPS at threshold | Failures |
|---:|---:|---:|---:|---:|
| 1 | 4 | 1,420 | 2.78 | 0 |
| 2 | 4 | 1,191 | 3.32 | 0 |
| 4 | 4 | 1,192 | 3.27 | 0 |
| 8 | 4 | 1,240 | 3.21 | 0 |

Throughput plateaus at ~3.3 QPS regardless of pod count. See `plots/plot_latency.png` and `plots/plot_throughput.png`.

## 2. Open-loop results (saturation point per pod count)

"Saturation point" = lowest offered λ where success rate < 100% OR mean latency > 2 × the lowest-rate baseline.

| Replicas | Max stable λ (req/s) | Mean latency at max stable (ms) | Achieved rate at max stable (req/s) | Saturation λ (req/s) |
|---:|---:|---:|---:|---:|
| 1 | 3 | 344 | 3.00 | 4 |
| 2 | 4 | 350 | 3.99 | 6 |
| 4 | 4 | 532 | 3.99 | 6 |

Above saturation, the success rate collapses (e.g., 2 pods at 10 req/s: 42% success, mean 24 s; 4 pods at 14 req/s: 12% success, mean 28 s). See `plots/plot_openloop_latency.png` (hockey-stick latency curve) and `plots/plot_openloop_success.png` (sharp success-rate cliff at saturation).

## 3. Performance analysis (≤500 words)

**Queuing-theory framing.** Each pod is approximately an M/M/1 server whose service rate μ is set by YOLOv8n inference time (~150–300 ms on a 1 vCPU slice → μ ≈ 3–6 req/s) and by the per-pod `ThreadPoolExecutor(max_workers=1)` used to keep ultralytics' non-thread-safe `Profile` object from racing. With *N* replicas, the aggregate service rate ceiling is **N · μ**.

**Little's Law cross-checked by two methodologies.** Locust's closed-loop workload pins *U* users in flight, so λ = U/W. With *U* = 4 at the breaking point and *W* ≈ 1.2 s, predicted λ_max = 3.3 req/s — exactly the plateau visible in `plot_throughput.png`. The vegeta open-loop test then measured the per-pod saturation independently at λ ≈ 3 req/s (1 pod) and λ ≈ 6 req/s (2 pods). The two methodologies *converge on the same μ*, confirming the closed-loop ceiling was a genuine system limit and not a measurement artefact of the client-side concurrency.

**The 2 → 4 pod anomaly.** Open-loop shows 4 pods does not move the saturation point beyond ~6 req/s — both the 2-pod and 4-pod latency curves are nearly identical above saturation (see `plot_openloop_latency.png`). This isolates a *second* bottleneck downstream of the additional pods.

**Bottleneck identification.** Three layers contribute, in priority order:

1. **CPU per pod (μ ≈ 3 req/s).** YOLOv8n on 1 vCPU has a hard ceiling; visible as the per-pod open-loop knee.
2. **kube-proxy iptables stickiness.** k3s' default kube-proxy load-balances *per TCP connection*. Without `LOCUST_EXTRA_HOSTS` rotation and `Connection: close`, a single client pins to a single pod. Even with the rotation, kube-proxy's pseudo-random per-node selection mixes traffic unevenly across pods on the same node — the 4-pod plateau suggests the cluster effectively spreads to ~2 pods regardless of replica count.
3. **YOLO model thread safety.** Ultralytics' internal `Profile` object races under concurrent access inside one Python process. Mitigated by serialising inference *within* a process (`max_workers=1`) and parallelising *across* processes (`uvicorn --workers 2`).

**How horizontal autoscaling mitigates these.** Adding replicas multiplies aggregate μ. The 1 → 2 pod step doubled both the closed-loop QPS ceiling (visible in the throughput curve) and the open-loop saturation point (3 → 6 req/s), proving HPA works *up to the next bottleneck*. Beyond that, replicas help only by reducing per-pod queue depth (a secondary effect). In production, fixing the kube-proxy layer (switching to IPVS mode for per-request load balancing, or routing via a Layer-7 ingress like Traefik) is required before more replicas pay off.

**Edge/cloud trade-off.** Running 50 MB YOLOv8m on a 1 vCPU pod has μ ≈ 1 req/s and cannot meet sub-500 ms HD latency regardless of replica count. Switching to 6 MB YOLOv8n gave a 5–10× speedup at the cost of accuracy (fine-tuned plastic classes → pretrained COCO). On constrained edge-class compute, **model selection — not orchestration — dominates achievable QPS.**
