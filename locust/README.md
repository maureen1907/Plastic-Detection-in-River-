# Locust load tests

Python load-generation script that hits `/api/predict` and `/api/annotate` on the deployed plastic-detection API.

## Setup

Install Locust into your existing venv (or a fresh one):

```bash
pip install locust
```

## Quick start (interactive web UI)

```bash
cd locust
locust -f locustfile.py --host http://<node-ip>:30080
```

Then open <http://localhost:8089> in a browser. Enter:
- **Number of users** (e.g. 10, 50, 100)
- **Spawn rate** (e.g. 5 users/sec)

Click **Start swarming**. Live charts show QPS, response times, failures.

## Headless run (for capturing report data)

```bash
locust -f locustfile.py \
  --host http://<node-ip>:30080 \
  --users 20 \
  --spawn-rate 5 \
  --run-time 2m \
  --headless \
  --csv results
```

Outputs `results_stats.csv`, `results_failures.csv`, `results_stats_history.csv` for analysis.

## Configuring the test image

By default the script uses `../runs/detect/train/val_batch0_labels.jpg`. Override via:

```bash
LOCUST_TEST_IMAGE=/path/to/your/test.jpg locust -f locustfile.py --host http://...
```

## What the script does

Each simulated user, on start, reads and base64-encodes the test image once. Then it loops:

| Task | Endpoint | Weight | Why |
|---|---|---|---|
| `predict` | `POST /api/predict` | 3 | Primary endpoint, called 3× as often |
| `annotate` | `POST /api/annotate` | 1 | Heavier (returns annotated image bytes) |

Wait time is set to **zero** by default — simulated users hammer the server as fast as their requests return. Change `wait_time` in `locustfile.py` to `between(1, 3)` for realistic-user pacing.

## Suggested test sequence for the report

| Phase | Users | Spawn rate | Duration | Purpose |
|---|---|---|---|---|
| Baseline (1 pod)   | 5   | 1/s | 60s | Measure single-pod capacity |
| Stress (1 pod)     | 50  | 5/s | 2m  | Find the saturation point |
| Scaled (2 pods)    | 50  | 5/s | 2m  | Show horizontal scaling helps |
| Scaled (3+ pods)   | 100 | 10/s | 2m | Highest sustained QPS |

Scale the deployment between phases:

```bash
ssh ubuntu@<master-ip> 'sudo kubectl scale deploy/plastic-detection-api -n plastic-detection --replicas=3'
```

## Metrics to report

- **Aggregate QPS** (sustained, not peak)
- **p50, p95, p99 latency** for `/api/predict`
- **Failure rate** (should be near 0%)
- **Per-pod QPS** = aggregate QPS / replica count
- The relationship between replica count and aggregate QPS (linear scaling = good)
