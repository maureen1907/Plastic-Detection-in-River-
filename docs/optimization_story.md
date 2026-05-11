# Optimization story — the narrative

A ~2-minute spoken story you can deliver if the interviewer asks "how did you optimise this?" or "walk me through the performance improvements." The numbers anchor it; the *reasoning* at each step is what gets marks.

## The arc in one sentence

> "I went from 0.45 QPS aggregate with 37% errors on the naive setup to 2.7 QPS per pod with 0% errors on the final setup. About 12× throughput, 9× latency, 37× error-rate improvement. Four bundled fixes got me there, and each one taught me something different about Python concurrency on constrained CPU."

## The four fixes, in order

### 1. Memory limit 2 GiB → 4 GiB

**The symptom:** Locust at 3 users on 2 pods showed 37% HTTP 500 errors. Pod status showed `OOMKilled`.

**The diagnosis:** YOLOv8m's model object is ~700 MB in memory once loaded. With `ThreadPoolExecutor(max_workers=2)` allowing concurrent inferences plus buffers, two simultaneous predictions could push the working set past the 2 GiB pod cap. The kernel's OOM killer terminated the container mid-request.

**The fix:** One YAML line — `memory: "4Gi"` in `deployment.yaml`. Cheapest possible improvement.

**The lesson:** Memory limits aren't just for safety; they're sized based on the working set of the workload. ML inference has spiky memory usage during the forward pass.

### 2. `uvicorn --workers 2`

**The symptom:** Even after the memory bump, throughput was bound at ~1 QPS per pod regardless of concurrency.

**The diagnosis:** YOLO inference is CPU-bound, and Python's GIL serialises bytecode execution within a single process. Threads in the same process can't actually run inference in parallel — they take turns under the GIL. The `ThreadPoolExecutor` keeps the async event loop unblocked but does nothing for actual throughput.

**The fix:** `uvicorn --workers 2` in the Dockerfile CMD. uvicorn forks N independent Python processes — each with its own GIL, its own model copy in memory. Now two requests can genuinely run inference in parallel.

**The lesson:** **For CPU-bound Python, the escape hatch is the process boundary, not the thread boundary.** The thread pool helps with async correctness; the process pool helps with throughput.

### 3. YOLOv8m → YOLOv8n

**The symptom:** With the multi-worker fix, throughput improved but per-request latency was still ~700–1500ms — well over the HD <500ms target.

**The diagnosis:** YOLOv8m has ~25M parameters. On 1 vCPU, a single inference takes ~700–1500ms. You can't be under 500ms latency if a single inference takes longer than 500ms — no architectural trick changes that.

**The fix:** Switch to YOLOv8n (nano). ~3M parameters, ~5–10× faster CPU inference. Made `MODEL_PATH` configurable so the fine-tuned YOLOv8m weights stay available for accuracy testing.

**The lesson:** On constrained compute, **model selection matters more than orchestration**. A small fast model + simple orchestration beats a large model + clever orchestration when CPU is the binding resource.

**The trade-off:** Pretrained YOLOv8n uses COCO class labels (`person`, `bottle`, etc.) — not the four plastic-specific classes the fine-tuned YOLOv8m has. Production would fine-tune YOLOv8n on the plastic dataset (10–30 min of additional training time) to keep both the speed and the accuracy.

### 4. `ThreadPoolExecutor(max_workers=1)` — the thread-safety fix

**The symptom:** Even with all of the above, at 8+ users the error rate climbed back to ~7.5%. Pod logs showed `AttributeError: 'Profile' object has no attribute 'dt'` with a Python traceback inside `ultralytics`.

**The diagnosis:** This was the most interesting bug. Ultralytics' YOLO model stores its inference timing in a `Profile` object that's shared across threads in a single Python process. Within a `model(img)` call, the Profile is reset and re-written. If two threads call `model(img)` simultaneously, one of them sees the Profile half-reset and crashes.

**The fix:** Drop `ThreadPoolExecutor(max_workers=2)` to `max_workers=1`. The thread pool becomes a one-slot queue — only one inference runs at a time per Python process. Combined with `uvicorn --workers 2`, the pod still does 2 concurrent inferences (one per process), but never two in the same process.

**The lesson:** Even mature ML libraries often aren't designed for shared-state concurrency. The right pattern for CPU-bound non-thread-safe work is **parallelism between processes, serialisation within processes** — exactly the inversion of what people new to async Python often try.

## The unexpected finding (the publication-quality bit)

After all four fixes, we ran the scaling benchmark — 4 pod counts × 5 user levels = 20 measurements. **Throughput plateaued at ~3.3 QPS regardless of pod count.** Adding pods past 2 gave nearly zero benefit. CPU usage on the pods sat at ~10%.

This is the textbook anti-pattern of horizontal scaling: optimising the wrong layer. The constraint wasn't pod compute; it was Little's Law applied to the closed-loop workload.

**Little's Law:** *U = λ · W*. With *U* (users) fixed at 4 in our breaking-point tests and *W* (response time) ≈ 1.2s under saturation, *λ* = *U* / *W* = 3.3 req/s. That's exactly the plateau we measured.

Adding pods reduces *W* slightly but doesn't increase *U*, so *λ* stays flat. To raise actual throughput you'd need:
- **More clients** (distributed Locust workers) to increase *U*, or
- **Faster pods** (ONNX runtime, better CPU) to decrease *W*

This finding is in the 470-word performance report. It's the analytical core that distinguishes the submission from "added more pods, hoped for the best."

## How to deliver this verbally

Don't recite all four fixes if you only have 60 seconds — pick the **two most interesting**:

1. **The GIL story (Fix 2)** — shows you understand Python concurrency at a deep level.
2. **The thread-safety bug (Fix 4)** — shows you can read traceback, identify a library bug, and reason about a correct fix.

Then close with the **Little's Law finding**: "the punchline is that even after all this, the cluster's actual throughput ceiling came from the closed-loop concurrency limit, not the pods. Adding pods past 2 gave us almost nothing — which Little's Law predicts exactly."

That's a 90-second story that demonstrates both engineering skill and analytical depth. That's what marks the difference between Distinction and HD on the explanation side.
