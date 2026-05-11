# Q&A bank — rapid-fire interview prep

~30 questions the interviewer might ask, grouped by topic. Answer each one out loud in your own words before reading the answer below. The point is to internalise the *reasoning*, not memorise the wording.

---

## A. Application code

### 1. "What does `/ready` do that `/healthz` doesn't?"

`/healthz` returns 200 unconditionally — it's the liveness probe, so K8s knows the process is alive and shouldn't be restarted. `/ready` returns 200 only when the YOLO model is loaded and callable, returns 503 otherwise. K8s uses readiness to decide whether to send Service traffic — pods stay out of the rotation until `/ready` succeeds. Without it, the first request after a pod starts would hit a half-initialised process.

### 2. "Why max_workers=1 in the ThreadPoolExecutor?"

Ultralytics' YOLO model isn't thread-safe — its internal `Profile` object gets corrupted under concurrent access in the same Python process, raising `AttributeError`. Max_workers=1 serialises inference within a process. Real parallelism comes from `uvicorn --workers 2` (separate processes, each with its own model).

### 3. "Why does the thread pool exist at all if max_workers=1?"

To keep the async event loop unblocked. FastAPI is `async`, but YOLO inference is synchronous and CPU-bound. Without `loop.run_in_executor`, the inference call would block the entire event loop and reject other incoming requests. The thread pool lets uvicorn keep accepting connections during a prediction.

### 4. "Walk me through what happens between `POST /api/predict` and the response."

1. FastAPI parses the JSON body into a Pydantic `ImagePayload` model.
2. `base64_to_image()` decodes the base64 string into a PIL Image.
3. `loop.run_in_executor(executor, run_inference_sync, model, img)` hands the model call to the thread pool. The async route yields, freeing the event loop.
4. The thread pool runs `model(img)[0]`, returning a YOLO `Results` object.
5. `extract_detections()` pulls class labels + bounding boxes from `Results.boxes`.
6. The dict (uuid, count, detections, boxes, speed) gets serialised to JSON and returned.

### 5. "What's the difference between Python threads and processes for this workload?"

YOLO inference is CPU-bound. The Python GIL means only one thread per process runs bytecode at a time, so threads can't actually parallelise this work. Processes each have their own GIL — they truly run in parallel on multi-core CPUs. The cost is N copies of the model in memory (one per process).

---

## B. Model & ML

### 6. "Why YOLOv8n instead of your fine-tuned YOLOv8m?"

Performance. YOLOv8m has ~25M parameters and takes ~700–1500ms per inference on 1 vCPU. The HD rubric needs <500ms latency — impossible with that model. YOLOv8n has ~3M parameters, runs in ~150–300ms. The trade-off is that pretrained YOLOv8n uses COCO classes (`person`, `bottle`, etc.) rather than the plastic-specific classes. The fine-tuned model is still in the repo at `runs/detect/train/weights/best.pt` and can be loaded via the `MODEL_PATH` env var.

### 7. "What would you do if you needed both speed AND the plastic classes?"

Fine-tune YOLOv8n on the same plastic dataset I trained YOLOv8m on. Same data, smaller architecture, ~10–30 minutes of training time. That'd give the nano-model speed with plastic-specific class labels. I didn't do this for the assignment due to time constraints and because the rubric's performance section grades the architecture, not the model accuracy.

### 8. "What's the `torch.load` patch in `model.py` for?"

PyTorch 2.6+ defaults `weights_only=True` when loading checkpoints, as a security measure — it refuses to unpickle arbitrary Python objects. The fine-tuned `best.pt` was saved with an older PyTorch and contains custom objects (`Profile` class instances) that `weights_only=True` rejects. The patch temporarily disables that check during the load. It's only needed when loading the local fine-tuned checkpoint — the auto-downloaded pretrained YOLOv8n doesn't need it.

---

## C. Kubernetes

### 9. "Why a Namespace?"

Three reasons: it isolates the app's labels and policies from `kube-system` and other workloads; it lets `kubectl get all -n plastic-detection` show only my stuff; and it's the rubric's "appropriate namespace management" criterion. A real cluster might have dev/staging/prod namespaces side-by-side.

### 10. "What's the difference between requests and limits?"

`requests` is what the K8s scheduler reserves at scheduling time — it guarantees the pod will get at least this much. `limits` is the hard ceiling — the pod can burst up to this if the node has capacity, but never above. Memory limit hits are OOMKill; CPU limit hits are throttling. I have requests at 500m CPU / 1 GiB and limits at 1000m / 4 GiB — that means K8s reserves half a CPU per pod for scheduling but allows up to 1 full vCPU under load.

### 11. "Why is the master not running pods in some of your outputs?"

In standard kubeadm, the control-plane node is tainted with `node-role.kubernetes.io/control-plane:NoSchedule`, so user workloads aren't scheduled there. k3s doesn't apply that taint by default, but the scheduler still prefers worker nodes for new pods. In some of my benchmarks I saw pods on the master too — k3s is happy to use the master as a worker.

### 12. "Walk me through the readiness probe settings."

`initialDelaySeconds: 10` — wait 10s after the container starts before the first probe (model load is in progress).
`periodSeconds: 5` — probe every 5s after that.
`failureThreshold: 60` — allow up to 60 consecutive failures before marking the pod NotReady. 60 × 5s = 300s of grace, more than enough for cold-start model load.
`successThreshold: 1` — one successful probe is enough to mark ready.

Effectively: pods get up to 5 minutes to load the model, then must respond 200 within 5s of each subsequent probe to stay in rotation.

### 13. "What's the Service doing exactly?"

It's a NodePort Service. The selector matches the Deployment's pod labels (`app.kubernetes.io/name + component`). For every node in the cluster, kube-proxy installs iptables rules so that traffic arriving at port 30080 gets DNAT'd to one of the pod IPs (which live on a flannel overlay network). From the outside, you can hit any node's external IP on :30080 and reach a pod — even if that node has no pods on it (kube-proxy on that node forwards to a pod on a different node).

---

## D. Terraform / IaC

### 14. "Why k3s and not full kubeadm?"

k3s is a CNCF-certified Kubernetes distro — same kubectl, same manifests, same API. The marker sees a real K8s cluster. The difference is bootstrap: k3s is one curl per node and bundles flannel CNI + etcd. kubeadm needs several separate components installed and a CNI chosen and installed manually. For a 1-day assignment, k3s saved ~2 hours of setup with no runtime difference for the marker.

### 15. "How do workers find the master to join?"

A shared token. Terraform generates a `random_string` once, then templates it into both the master's cloud-init (where it's set as `K3S_TOKEN=` for the server install) and the workers' cloud-init (where it's set as `K3S_TOKEN=` for the agent install with `K3S_URL=https://<master-ip>:6443`). No coordination needed — the secret is identical on both sides at provisioning time.

### 16. "What does the `until` loop in `cloud-init-worker.sh.tpl` do?"

Terraform creates all 3 instances roughly in parallel. The workers `depends_on` the master resource, but Terraform considers an instance "created" the moment the VM boots — not when its cloud-init finishes. So the master might still be installing k3s when the workers start trying to join. The `until` loop on each worker keeps curling the master's API server (`https://<master-ip>:6443`) until it responds, then runs the join. Without it, workers would race ahead and fail with "connection refused."

### 17. "What's a Terraform module?"

A reusable bundle of `.tf` files in its own directory. Has its own `variables.tf`, `outputs.tf`, optionally `versions.tf`. Called from a parent project via a `module {}` block that wires the parent's values into the module's inputs. The point is reusability — my `modules/network/` could be dropped into another OCI project that needs a VCN + subnet without copy-paste.

### 18. "How did you migrate from a flat main.tf to modules without destroying everything?"

`terraform state mv`. When you refactor a resource into a module, its address changes from e.g. `oci_core_vcn.foo` to `module.network.oci_core_vcn.foo`. Without telling Terraform about this, it'd see "the old one is gone, the new one is new" and destroy+recreate everything. `state mv` rewrites the state file in place — points the new address at the existing physical resource. The OCI provider doesn't support the declarative `moved {}` block, so I used the imperative `state mv` instead.

### 19. "What does `allow_stopping_for_update = true` mean?"

It's a GCE-specific Terraform argument. GCE forbids changing `machine_type` on a running instance. This flag tells Terraform "you have my permission to stop the instance, apply the type change, and restart it." Used when I resized from `e2-standard-4` (4 vCPU + 16 GB) to `e2-custom-4-8192` (4 vCPU + 8 GB exact, matching the rubric) without destroying the VMs.

---

## E. Locust and load testing

### 20. "Walk me through `locustfile.py`."

Each `PlasticDetectionUser` simulates one client. On start, it reads the test image and base64-encodes it once. Then it loops: pick `/api/predict` (weight 3) or `/api/annotate` (weight 1), build a JSON payload with a fresh UUID, POST it, validate the response. `wait_time = between(0, 0)` means no think time — the user fires the next request as soon as the previous response comes back.

### 21. "What does `LOCUST_EXTRA_HOSTS` do?"

It rotates which node IP each request goes to. With Locust's default HTTP connection reuse, every request from a user goes to the same node, and kube-proxy on that node routes to the same pod for the connection's lifetime. Adding multiple node IPs and forcing `Connection: close` per request means each request gets a fresh TCP, lands on a (random) node, and kube-proxy gets a fresh chance to route to a different pod. It's a client-side workaround for iptables-mode kube-proxy's per-connection load-balancing.

### 22. "Why a closed-loop workload?"

It's what Locust does by default. Each simulated user is a sequential loop: request → wait for response → request → ... So there are exactly *N* requests in flight at any time, where *N* is the user count. This makes Little's Law hold exactly: λ = U / W. An open-loop workload (request every X seconds regardless of response time) would simulate a different kind of traffic.

### 23. "What's the breaking point and how did you find it?"

For each pod count, I ran Locust at user counts 1, 2, 4, 8, 16 for 45s each. The "breaking point" heuristic: highest user count where (a) zero failures AND (b) avg response time < 2× the single-user baseline. For all four pod configs (1, 2, 4, 8) the breaking point was 4 users — saturation hit at the same concurrency regardless of replicas, which is the key analytical finding.

---

## F. Performance analysis

### 24. "State Little's Law and apply it to your data."

Little's Law: L = λW, where L is the average number of items in the system, λ is the arrival rate, and W is the average time in the system. For my closed-loop workload, L = U (user count, fixed). So λ = U / W. With U = 4 at the breaking point and W ≈ 1.2s saturation latency, λ_max = 3.3 req/s — exactly the plateau visible in `plot_throughput.png` for every pod count. Adding pods reduces W slightly (less queueing) but doesn't change U, so λ stays flat.

### 25. "What's the bottleneck if not pod CPU?"

A few layers, in priority order:
- **Client-side concurrency**: a single Locust process from my Mac, with `Connection: close` forcing a fresh TCP handshake per request over a high-latency WAN to GCP Sydney. Each round-trip is ~50–100ms of network alone.
- **kube-proxy iptables stickiness**: per-connection load balancing, not per-request.
- **Pod CPU** in theory, but in practice pods sat at ~10% utilisation across all 8-replica runs — they were never compute-saturated.

The fix to actually raise throughput would be more independent clients (distributed Locust workers), not more pods.

### 26. "How does horizontal pod autoscaling 'mitigate the bottleneck' in the rubric's words?"

Each additional pod multiplies aggregate service rate μ. With N replicas, the cluster's throughput ceiling λ_max = N · μ_per_pod. This pushes the queueing knee (where requests start backing up) to higher user counts — but only if requests can actually reach the new pods. Per-connection load balancing pins traffic to one pod regardless of replica count; per-request load balancing (IPVS mode, Traefik, or GCP L7 LB) is needed to actually exploit the additional capacity.

### 27. "What would you do differently?"

Three things. First, switch the inference layer to ONNX Runtime — its C++ kernel releases the GIL so a single Python process can do parallel inference, doubling per-pod throughput. Second, run kube-proxy in IPVS mode (a k3s install option) for per-request load balancing without the client-side hack. Third, run distributed Locust from multiple machines to break the single-client concurrency ceiling and actually saturate the cluster.

---

## G. Project context / soft questions

### 28. "How did you find the thread-safety bug?"

I was investigating why error rates climbed back up to ~7.5% at moderate load after the v3 image improvements. Ran `kubectl logs` on each pod during a load test and grepped for `error|exception|traceback`. The first match was the Python `AttributeError: 'Profile' object has no attribute 'dt'` traceback. That's a library-internal data structure, so I knew it wasn't my code — it was concurrent threads racing on ultralytics' internal timing object. Setting max_workers=1 in the thread pool serialised access and the errors disappeared.

### 29. "What's the trade-off of running ML on edge/cloud constrained compute?"

It's fundamentally an accuracy-vs-cost trade-off, and orchestration cleverness alone can't erase it. Running my fine-tuned YOLOv8m on 1 vCPU has a hard service-rate ceiling of ~1 req/s, regardless of how the rest of the stack is engineered — the workload doesn't fit the available compute. The trade-off I accepted was switching to YOLOv8n (5–10× faster, smaller accuracy) to make the model match the constrained compute. The alternative would be GPU-class node pools, multiplying cost ~50× for an academic workload.

### 30. "What were the hardest decisions on this project?"

Two: (1) Whether to attempt HD performance on YOLOv8m or accept the speed/accuracy trade-off of YOLOv8n. The rubric tests performance, not accuracy in that section, so YOLOv8n was right — but the project lost the fine-tuning work as a result. (2) Whether to scale-up the K8s cluster spec (4 vCPU per pod with 1 vCPU limit means lots of wasted capacity) versus actually optimising the inference path. The rubric's 1 vCPU limit is a hard constraint, so the only honest path is optimising within it — which is why ONNX Runtime is the obvious next step.
