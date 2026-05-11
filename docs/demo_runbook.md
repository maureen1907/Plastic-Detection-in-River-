# Demo runbook (20-minute live interview)

Step-by-step screen-share script. Rehearse this once end-to-end before the interview. Time estimates assume the cluster is healthy when you start — sanity check first thing in the morning.

## Pre-flight (do BEFORE you start sharing screen)

```bash
# 1. SSH works
ssh -i ~/.ssh/id_ed25519 ubuntu@35.197.187.242 'sudo kubectl get nodes'
# Expect: 3 nodes Ready

# 2. Pods are alive
ssh -i ~/.ssh/id_ed25519 ubuntu@35.197.187.242 'sudo kubectl get pods -n plastic-detection'
# Expect: all 1/1 Running

# 3. API responds
curl http://35.197.187.242:30080/ready
# Expect: {"status":"ready","model":"yolov8m"}  ← actually returns yolov8n now, just the label is hardcoded
```

If anything's broken: `terraform apply -auto-approve` from `gcp-terraform/` will rebuild. Allow ~10 min.

---

## Part 1 — Repository tour (~2 min)

Start in the project root. Show the marker the layout:

```bash
cd ~/Desktop/FIT5225/a1/Plastic-Detection-in-River
ls -F
```

Talk through the layout out loud:

> "The project has three deployment phases sitting side-by-side. `oci-terraform/` is the single-VM IaC deployment on Oracle Cloud — that's Phase 1, tagged v1.0. `gcp-terraform/` is the 3-node Kubernetes cluster on GCP — Phase 2 / v2.0. `k8s/` is the Kubernetes manifests applied to that cluster. `locust/` has the load-testing script, benchmark runner, and the final performance report. The FastAPI app code is at the root — `main.py`, `model.py`, `service.py`."

Show the git tags:

```bash
git tag -l
# v1.0, v2.0, v3.0, v4.0
git log --oneline -10
```

---

## Part 2 — Kubernetes cluster demo (~5 min)

```bash
# Switch to master IP variable so commands are clean
export MASTER=35.197.187.242
```

### Show the cluster topology

```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@$MASTER 'sudo kubectl get nodes -o wide'
```

Talk through:

> "Three nodes: one control-plane, two workers. Each is a GCP `e2-custom-4-8192` instance — exactly 4 vCPU and 8 GB RAM as the rubric specifies. They're running k3s, which is a CNCF-certified lightweight Kubernetes distribution — same `kubectl`, same manifests, much simpler bootstrap via a single curl in cloud-init."

### Show the workload

```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@$MASTER 'sudo kubectl get all -n plastic-detection'
```

Talk through:

> "The `plastic-detection` namespace contains a Deployment running two replicas of the plastic-detection API. The Service is a NodePort exposing port 30080 on every node. The Deployment uses `app.kubernetes.io/*` labels per the K8s standard convention — the Service selects pods by those same labels."

### Show the probes and limits

```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@$MASTER \
  'sudo kubectl describe deployment plastic-detection-api -n plastic-detection' \
  | grep -A 30 'Containers:'
```

Talk through:

> "Each pod is capped at 1 vCPU and 4 GiB memory. The 1 vCPU is the rubric requirement; the 4 GiB gives headroom for two uvicorn worker processes — that's the GIL-bypass strategy. The liveness probe hits `/healthz`, which is unconditional. The readiness probe hits `/ready`, which only returns 200 once the YOLO model is loaded into memory — that's the HD probe requirement, gating Service traffic until the pod is genuinely ready."

### Show traffic actually reaching pods

```bash
curl -s http://$MASTER:30080/ | jq .
curl -s http://$MASTER:30080/ready | jq .
```

Then a quick prediction to prove inference works:

```bash
# Locally
python3 -c "
import base64, json, urllib.request
with open('runs/detect/train/val_batch0_labels.jpg','rb') as f:
    img = base64.b64encode(f.read()).decode()
req = urllib.request.Request('http://35.197.187.242:30080/api/predict',
    data=json.dumps({'uuid':'demo','image':img}).encode(),
    headers={'Content-Type':'application/json'})
print(json.dumps(json.loads(urllib.request.urlopen(req, timeout=60).read()), indent=2)[:800])
"
```

---

## Part 3 — Live Locust demo (~5 min)

Open a fresh terminal for this so the marker sees the live charts.

```bash
cd locust
python3 -m locust -f locustfile.py --host http://35.197.187.242:30080
```

Then in browser: **http://localhost:8089**

Show the marker:

1. **Start a test** — 6 users, spawn rate 1/s. Click Start.
2. **The Statistics tab** — point out `/api/predict` and `/api/annotate` rows, the median/95% columns. Talk through how Locust is constantly base64-encoding images and POSTing them.
3. **The Charts tab** — point at the QPS line (~3 QPS sustained), the response time line (~1 sec median).
4. **The Failures tab** — point out the zero failures.

Then **stop the test** and switch to the saved plot:

```bash
open plots/plot_latency.png
open plots/plot_throughput.png
```

Talk through:

> "These are aggregated across 20 runs covering 4 pod counts and 5 user levels. The headline finding is the throughput plateau — adding pods past 2 gave almost zero benefit because we hit a closed-loop concurrency ceiling that Little's Law predicts almost exactly."

---

## Part 4 — Code walkthrough (~5 min)

The interviewer will probably ask "show me the source." Have these files open in tabs:

1. `main.py`
2. `model.py`
3. `k8s/deployment.yaml`
4. `gcp-terraform/main.tf`
5. `locust/locustfile.py`

For each, see `code_walkthrough.md` for talking points. Top-priority files (in order):

- **`main.py` lines 28-37** — the `/ready` endpoint. Why it exists, what it gates.
- **`main.py` lines 22-31** — `ThreadPoolExecutor(max_workers=1)`. Why 1, not 2. The thread-safety story.
- **`model.py`** — `MODEL_PATH` env var, the YOLOv8n choice.
- **`k8s/deployment.yaml` lines 35-50** — resource limits and probes.
- **`gcp-terraform/cloud-init-worker.sh.tpl`** — the `until` loop waiting for the master. Explain why.

---

## Part 5 — Optimization story (~3 min)

Have `docs/optimization_story.md` open. Walk through v2 → v3 → v4 with the numbers:

- v2 baseline: 0.45 QPS, 4,700ms, 37% errors
- v4 final: 2.7 QPS/pod, 530ms p50, 0% errors
- 12× QPS, 9× latency, 37× error rate improvement

Mention each fix and what it did. The thread-safety bug is the most interesting one — explain it last for the punchline.

---

## Closing (~30 sec)

If the interviewer asks "what would you do differently":

> "Three things. One — switch the inference layer to ONNX Runtime. ONNX releases the Python GIL inside its C++ kernel so a single Python process can do parallel inference, doubling per-pod throughput. Two — switch kube-proxy to IPVS mode for per-request load balancing instead of per-connection. Three — fine-tune YOLOv8n on the plastic dataset rather than using the pretrained COCO weights, so we keep the speed but recover the class accuracy."

---

## Cheat sheet — commands to memorise

| Need to show... | Run... |
|---|---|
| Nodes | `kubectl get nodes -o wide` |
| All workload state | `kubectl get all -n plastic-detection` |
| Pod details (probes, limits) | `kubectl describe deployment plastic-detection-api -n plastic-detection` |
| Pod logs | `kubectl logs -n plastic-detection <pod-name> --tail=50` |
| Scale up/down | `kubectl scale deploy/plastic-detection-api -n plastic-detection --replicas=N` |
| Terraform outputs | `cd gcp-terraform && terraform output` |
| Terraform-tracked state | `terraform state list` |

Always SSH to master first when running kubectl, because kubectl isn't installed on your Mac:
`ssh -i ~/.ssh/id_ed25519 ubuntu@35.197.187.242 'sudo kubectl ...'`

---

## If something goes wrong live

- **Pods Not Ready**: stay calm. "These were rolling — let me show you the working ones." Run `kubectl get pods` again.
- **kubectl times out**: the master node may have been preempted or restarted. Re-`terraform apply` while you talk through the IaC code.
- **Locust UI doesn't load**: make sure you didn't hit `--headless` — drop that flag.
- **API returns 500**: rare now, but if it happens, point to the logs (`kubectl logs ...`) and identify the error live. The thread-safety story made this very unlikely.

When in doubt: **slow down, narrate what you're doing, and don't pretend.** Saying "I'm not 100% sure why that happened but my hypothesis is X" is much better than bluffing.
