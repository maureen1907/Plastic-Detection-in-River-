# Benchmark Report — FIT5225 A1 Phase 8

Methodology, raw data, plots, and a ≤500-word analysis. See `plots/results.csv` for every (pods, users) measurement; `plots/breaking_points.csv` for the per-pod-count summary.

## Methodology

Locust (v2.43, headless, single client on macOS) ran a closed-loop workload against the 3-node k3s cluster on GCP. Each simulated user opens a fresh TCP connection per request and rotates uniformly across all 3 node external IPs (`LOCUST_EXTRA_HOSTS`) so kube-proxy on each node distributes to a different pod. Image payload: 316 KB JPEG (base64-encoded → 432 KB JSON body). Tasks weighted 3:1 (`/api/predict` : `/api/annotate`). For each pod count ∈ {1, 2, 4, 8}, ran 45 s at user counts ∈ {1, 2, 4, 8, 16}. Pods: `mpha0039/plastic-detection:v4` (YOLOv8n, `uvicorn --workers 2`, 1 vCPU / 4 GiB), thread-safety patched.

## 1. Results table (breaking-point per pod count)

"Breaking point" = highest user count where failures = 0 AND avg latency stays below 2 × the single-user baseline. (`analyze.py find_breaking_point()`)

| Replicas | Max stable users | Avg latency at threshold (ms) | QPS at threshold | Failures |
|---:|---:|---:|---:|---:|
| 1 | 4 | 1,420 | 2.78 | 0 |
| 2 | 4 | 1,191 | 3.32 | 0 |
| 4 | 4 | 1,192 | 3.27 | 0 |
| 8 | 4 | 1,240 | 3.21 | 0 |

## 2. Plots

- `plots/plot_latency.png` — average response time vs concurrent users, one curve per pod count, with the HD 500 ms target overlaid.
- `plots/plot_throughput.png` — sustained requests/sec vs concurrent users, same grouping.

## 3. Performance analysis (≤500 words)

**Queuing-theory framing.** Each pod is approximately an M/M/1 server whose service rate μ is set by YOLOv8n inference time (~150–300 ms on a 1 vCPU slice → μ ≈ 3–6 req/s) and by the per-pod `ThreadPoolExecutor(max_workers=1)` we use to keep ultralytics' non-thread-safe `Profile` object from racing. With *N* replicas in parallel, the aggregate service rate ceiling is **N · μ ≈ 3N–6N req/s**.

**Little's Law.** Locust generates a *closed-loop* workload: at any instant exactly *U* users are in the system (each issues a request, waits for the response, then immediately fires again). Little's Law gives

> *U* = λ · *W* → λ = *U* / *W*

So achievable throughput is upper-bounded by *U* / *W*. At *W* ≈ 1.2 s (our measured saturation latency), λ_max = 4 / 1.2 = 3.3 req/s — **exactly the plateau visible in `plot_throughput.png`** across every pod-count configuration. Adding replicas decreases *W* slightly (less queueing per pod) but does not raise *U*, so λ stays flat. Latency past the knee grows super-linearly because additional users join the queue rather than execute in parallel: *W* = service_time + queue_length / μ, and queue_length scales with *U − Nμ·service_time*.

**Bottleneck identification.** Three layers contributed, in priority order:

1. **Closed-loop concurrency (Locust client + WAN round-trip).** Our 1-client Locust generator from macOS Australia→GCP-Sydney has TCP-handshake-per-request (`Connection: close`) of ~50–100 ms RTT plus 432 KB upload over a residential link. This dominates *W* for low *U*. Pods sat at only ~10 % CPU utilisation across all 8-replica runs; the cluster was never compute-saturated.
2. **kube-proxy iptables stickiness.** k3s' default kube-proxy load-balances *per TCP connection*, not per request. Without `LOCUST_EXTRA_HOSTS` rotation, a single user pinned to a single pod and the cluster behaved as if it had 1 replica.
3. **YOLO model thread safety.** Even after the rotation hack, naïve `max_workers=2` inside a Python process raced on ultralytics' internal `Profile` object → `AttributeError`. We mitigated by serialising inference *within* a process and parallelising *across* processes (`uvicorn --workers 2`).

**How horizontal autoscaling mitigates these bottlenecks.** N replicas multiply aggregate μ, pushing the queueing knee (where λ → N·μ) to higher *U*. This only translates to higher measured QPS when requests can actually reach the new pods: an IPVS-mode kube-proxy or a Layer-7 ingress (Traefik, GCP L7 LB) is required so requests, not connections, are load-balanced. Without these, replicas only reduce queueing within each pod — a smaller secondary benefit.

**Edge/cloud trade-off.** Running 50 MB YOLOv8m on a 1 vCPU pod has a service rate of ~1 req/s and cannot meet sub-500 ms HD latency regardless of replica count or kube-proxy mode. Switching to 6 MB YOLOv8n gave a 5–10× speedup at the cost of accuracy (fine-tuned plastic classes → pretrained COCO). On constrained edge-class compute, model selection — not orchestration — dominates achievable QPS.
