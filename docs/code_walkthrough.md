# Code walkthrough — what to say when asked

For each file: **what it does** (one sentence), **the design decision** (the "why"), and **what to point at** if the interviewer asks for specifics.

---

## `main.py` — FastAPI app

**What it does:** Defines the HTTP API. Three "informational" endpoints (`/`, `/healthz`, `/ready`) and two "work" endpoints (`/api/predict`, `/api/annotate`). Routes prediction requests through a thread pool so the async event loop doesn't block.

**Key design decisions:**

### `executor = ThreadPoolExecutor(max_workers=1)` (line ~22)

Probably the most-likely-to-be-questioned line in the project. Be ready for:

> "Why is max_workers=1? Doesn't that defeat the purpose of a thread pool?"

**Answer:** The thread pool serves two purposes — one we want, one we don't.

1. **Want:** keeping the FastAPI async event loop unblocked. `loop.run_in_executor()` hands the synchronous YOLO call to a thread so the event loop can keep accepting HTTP requests.
2. **Don't want:** running concurrent inference within the same Python process. Ultralytics' YOLO model stores its timing info in a shared `Profile` object. If two threads both call `model(img)` at the same time, one of them sees the other thread's half-reset `Profile` and crashes with `AttributeError: 'Profile' object has no attribute 'dt'`.

With `max_workers=1`, the thread pool becomes a one-slot queue. Inference is serialised within a process while the event loop stays free. **True parallelism comes from `uvicorn --workers 2`** (separate Python processes, each with its own model copy).

### `/healthz` vs `/ready` (lines ~28-37)

> "Why two endpoints? What's the difference?"

**Answer:** They map to Kubernetes' two probe types.

- **Liveness** (`/healthz`): "is the process alive?" If this fails, K8s **restarts** the pod. We return `{"status": "alive"}` unconditionally — the bare fact that the request was answered proves the process is running.
- **Readiness** (`/ready`): "is the pod ready for traffic?" If this fails, K8s **removes the pod from the Service rotation** (but keeps it running, hoping it recovers). We return 503 if `model` is None or doesn't have a `predict` method.

The HD rubric specifically asks for probes that gate traffic until the YOLO model is loaded. We achieve that without an async load state machine because `model.py` loads YOLO at *import time* — uvicorn doesn't bind its port until imports finish, so by the time anyone can reach `/ready` the model is already loaded.

### `run_inference_sync` + `run_in_executor` (lines ~30-32, ~47)

> "Walk me through how a prediction request flows through this code."

**Answer:**

1. `POST /api/predict` with `{"uuid": ..., "image": "base64..."}` arrives.
2. FastAPI parses it via the Pydantic `ImagePayload` model.
3. `base64_to_image()` decodes the bytes back into an in-memory image.
4. `loop.run_in_executor(executor, run_inference_sync, model, img)` hands the YOLO call to the thread pool — async/await yields control so the event loop can do other work.
5. The thread pool thread calls `model(img)[0]`, returning a YOLO `Results` object.
6. `extract_detections()` pulls out class labels + bounding boxes; `speed` is timing metadata YOLO provides.
7. The dict is serialised to JSON and returned.

---

## `model.py` — YOLO loader

**What it does:** Imports the YOLO model into a module-level `model` variable.

**Key design decisions:**

### `MODEL_PATH` env var (line ~26)

> "Why is this configurable?"

**Answer:** Two models in play:

- **YOLOv8n (pretrained, default):** ~6 MB, 5–10× faster CPU inference. Trained on the COCO dataset (80 generic classes). Used in the K8s deployment for performance.
- **YOLOv8m (fine-tuned, `runs/detect/train/weights/best.pt`):** ~50 MB, slower but trained on the plastic-detection dataset (4 plastic-specific classes). Used during development for accuracy.

The env var lets you swap between them without a code change — `MODEL_PATH=runs/detect/train/weights/best.pt` in the container would load the fine-tuned weights. This is the trade-off the rubric tests in the performance section: small fast model vs large accurate model on constrained CPU.

### The `torch.load` patch (lines ~17-22)

> "What's this monkey-patch doing?"

**Answer (honest):** PyTorch 2.6+ defaults `weights_only=True` for security (refuses to unpickle arbitrary objects). The fine-tuned `best.pt` was saved with older PyTorch and contains the `Profile` class instance, which `weights_only=True` rejects. The patch sets `weights_only=False` temporarily during the model load, then restores the original. **It's only relevant when loading the fine-tuned local checkpoint** — the pretrained YOLOv8n download doesn't need it.

If the interviewer pushes further: "I'd ideally re-save the checkpoint with `weights_only`-safe metadata, but that requires re-training time we didn't have."

---

## `service.py` and `utils.py` — helpers

`service.py`: `run_inference()`, `extract_detections()`, `annotate_image()`. Thin wrappers around YOLO's `Results` API.

`utils.py`: `base64_to_image()`, `image_to_base64()`. Converts between base64 strings (JSON-transportable) and in-memory `PIL.Image` objects.

Nothing tricky. If asked: "the conversion utilities exist because the JSON API spec calls for base64-encoded images, but YOLO needs a real image object."

---

## `Dockerfile`

**What it does:** Multi-stage build that produces a CPU-only PyTorch + ultralytics + FastAPI image, ~1.8 GB.

**Key design decisions:**

### Multi-stage build (lines 3-25 and 26-65)

> "Why two stages?"

**Answer:** The builder stage compiles Python wheels (some of which need gcc, libgl1, etc.). The final stage only copies the resulting `/opt/venv` and the runtime apt packages. This shrinks the image by a few hundred MB and reduces attack surface — no compiler in the final image.

### `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]`

> "Why --workers 2?"

**Answer:** The Python GIL serialises bytecode within a single Python process — including, mostly, YOLO inference. To get true parallelism, you need multiple Python processes. `uvicorn --workers 2` forks two independent worker processes (each with their own GIL, their own model copy in memory). Combined with the `ThreadPoolExecutor(max_workers=1)` inside each worker, the pod can run 2 concurrent inferences while being thread-safe within each process.

### `USER appuser`

> "Why a non-root user?"

**Answer:** Defence in depth. If the container is compromised, the attacker has the privileges of UID 1000 (`appuser`), not root. Standard container hardening practice.

---

## `k8s/deployment.yaml`

**What it does:** Tells K8s to run 2 replicas of the API container, with resource limits, probes, and explicit labels.

**Key design decisions:**

### Labels (lines 6-9, 18-20, 25-27)

> "Why three labels?"

**Answer:** Following the `app.kubernetes.io/*` recommended convention.
- `name: plastic-detection` — which app
- `component: api` — which subsystem (could later add `worker`, `frontend`, etc.)
- `version: v2` — which release of the image

The Service's `selector` matches `name + component` — version-agnostic so a rolling update doesn't break selection.

### Resource limits (lines 38-44)

> "Why request 500m / limit 1000m?"

**Answer:** Limit 1000m (1 vCPU) is the rubric's mandatory cap. Request 500m is the K8s scheduler's reservation — at scheduling time K8s guarantees the pod can have 500m, but it can burst up to 1000m if available. With 8 pods × 500m = 4 vCPU reserved and 12 vCPU on the cluster, we always fit.

Memory: requests 1 GiB, limits 4 GiB. The model itself is small (~6 MB) but YOLO's working buffers + 2 uvicorn workers + Python overhead can briefly spike. 4 GiB is generous to prevent OOMKilled events. (We bumped this from 2 GiB after seeing OOMs in the v2 image.)

### Probes (lines 50-67)

> "Walk me through these probe settings."

**Answer:**
- `livenessProbe`: hits `/healthz` every 30s. `initialDelaySeconds: 60` because cold-start (image pull + model import) can take ~50s. If liveness fails 3× in a row, kubelet kills and restarts the container.
- `readinessProbe`: hits `/ready` every 5s. `failureThreshold: 60` × `periodSeconds: 5` = 300s of grace at pod startup, which is more than enough for model load (~50–70s in practice). Until `/ready` returns 200, the pod is *not* in the Service rotation — so the first user request never lands on a pod that's still loading the model.

---

## `k8s/service.yaml`

**What it does:** Exposes the Deployment's pods on a fixed NodePort.

**Key design decisions:**

### `type: NodePort` (vs LoadBalancer or Ingress)

> "Why NodePort?"

**Answer:** Three reasons.
1. Rubric explicitly lists NodePort as accepted.
2. No cloud-managed component — everything is K8s-native and tracked in our manifests.
3. The Service is reachable on **every** node's external IP (kube-proxy on each node forwards to the right pod). This made it natural to demonstrate "the Service distributes traffic" by hitting all 3 node IPs and seeing the same response.

In production we'd use a LoadBalancer or Ingress for a stable external endpoint and managed health checks.

### `nodePort: 30080`

> "Why 30080?"

**Answer:** Arbitrary, but in the K8s default NodePort range (30000–32767). Pinning it explicitly makes the Locust scripts and demo URLs reproducible.

---

## `locust/locustfile.py`

**What it does:** Defines simulated users that hit `/api/predict` (weight 3) and `/api/annotate` (weight 1) with base64-encoded images.

**Key design decisions:**

### `on_start` encodes the image once (lines ~78-81)

> "Why isn't the image encoded per-request?"

**Answer:** To keep the client (Locust) from being CPU-bound itself. Base64 encoding a 316 KB image takes a few ms — small but non-negligible at 3 QPS × 6 users. Encoding once at user-start means every subsequent request is just a JSON template fill + HTTP send.

### `LOCUST_EXTRA_HOSTS` rotation (lines ~99-115)

> "What does this environment variable do?"

**Answer:** It works around iptables-mode kube-proxy's per-connection (rather than per-request) load balancing. By default, Locust reuses TCP connections, and all of a user's requests stick to the same pod. When `LOCUST_EXTRA_HOSTS` is set with multiple node IPs, each request picks a random node and sets `Connection: close` to force a fresh TCP — which lets kube-proxy on the chosen node route to a different pod.

We discovered this when `kubectl top pods` showed one pod at 277m CPU and the others at ~50m. After rotation, CPU was balanced 101m / 113m / 76m.

In production: switch kube-proxy to IPVS mode or use an HTTP-layer ingress so per-request routing works without the client-side hack.

### `wait_time = between(0, 0)`

> "Why no think time?"

**Answer:** This is a max-throughput stress test, not a user-simulation. Real users would have think times of seconds. Setting `wait_time` to zero means each user fires the next request the instant the previous response comes back — this is what makes Little's Law's `λ = U / W` exactly hold.

---

## `gcp-terraform/main.tf` + cloud-init templates

**What it does:** Provisions a custom GCP VPC, firewall rules, and 3 GCE instances with cloud-init scripts that install k3s.

**Key design decisions:**

### k3s vs kubeadm

> "Why k3s instead of full kubeadm?"

**Answer:** k3s is a CNCF-certified Kubernetes distribution — same kubectl, same manifests, identical API. The marker sees a real K8s cluster. The difference is bootstrap: k3s installs in one curl (`curl -sfL https://get.k3s.io | sh -`), bundles flannel (CNI) and etcd. kubeadm requires installing several components separately, then choosing and installing a CNI manually. For a 1-day assignment, k3s saves ~2 hours of bootstrap work and behaves identically at runtime.

### Shared k3s token via Terraform `random_string` (lines ~17-21 of main.tf)

> "How do workers know the master's token to join?"

**Answer:** Terraform generates a random 32-character string once (`random_string.k3s_token`). The same string is templated into both the master's cloud-init (which passes it as `K3S_TOKEN=` to the k3s server install) and the workers' cloud-init (which passes it as `K3S_TOKEN=` to the k3s agent install). No GCS bucket / no fetching from master after-the-fact — the secret is the same on both sides at instance creation.

### The worker `until` loop (cloud-init-worker.sh.tpl, lines ~9-13)

> "What does this loop do?"

**Answer:** Terraform creates the master and workers in parallel. The workers depend on the master *being created* (`depends_on`), but Terraform considers an instance "created" the moment the VM boots — not when its cloud-init finishes. So the master might still be installing k3s when the workers start trying to join.

The `until curl -k -sf https://${master_ip}:6443/ ... ; do sleep 5; done` loop on each worker blocks until the master's k3s API server is reachable. Only then does the worker run `curl get.k3s.io | sh - agent` to join. Without this loop, workers would race ahead and fail their join with "connection refused."

### `--disable traefik` (cloud-init-master.sh.tpl)

> "What's traefik and why disable it?"

**Answer:** k3s bundles Traefik as a default ingress controller. We're using NodePort, not Ingress, so Traefik is unused overhead — disabling it saves a control-plane pod's worth of resources and removes a potential point of confusion in `kubectl get pods -A`.

### `allow_stopping_for_update = true` (lines ~85, ~129)

> "What does this do?"

**Answer:** GCE refuses to change `machine_type` on a running instance. This flag tells Terraform "yes, you have permission to stop the VM, change its type, and restart it" — used when we resized from `e2-standard-4` to `e2-custom-4-8192` to match the rubric spec exactly.

---

## `oci-terraform/` — modular Terraform

The OCI Terraform is more elaborate than the GCP one because it's where the modular-structure rubric was tested. Key things to be able to explain:

- **`modules/network/`** — VCN, subnet, IGW, route table, security list. Has a `dynamic` block for ingress rules (`ingress_security_rules { ... }`), which generates one block per port in a list.
- **`modules/compute/`** — instance + cloud-init.tpl. Self-contained: the template lives inside the module folder.
- **State migration via `terraform state mv`** — we refactored from a flat `main.tf` into modules, which would normally cause Terraform to destroy/recreate everything. Used `state mv` to rewrite the state file pointing old addresses at new module-scoped ones. Result: zero infrastructure churn during the refactor.

---

## Files you probably won't be asked about (but should recognise)

- `convert_to_yolo.py` — converts the Hugging Face plastic dataset into YOLO's expected `images/labels` directory format. Run once before training.
- `train.py` — runs `model.train()` with the plastic dataset config (`plastic.yaml`). Already run; produced `best.pt`.
- `app.py` — Streamlit frontend for local browsing of model predictions. Not in the deployment path.
- `test_api.py` — local script for hitting the API with a sample image.

If asked: "those are local-development helpers, not part of the production deployment path."
