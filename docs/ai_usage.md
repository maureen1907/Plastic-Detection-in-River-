# Generative AI Usage Statement

**Student:** Maureen Pham (mpha0039)
**Unit:** FIT5225 — Cloud Computing for Big Data Applications
**Assignment:** A1 — Plastic Detection in River

---

## Acknowledgment

I used **Claude** (Anthropic's AI assistant, via the Claude Code CLI) extensively throughout this project as a collaborator. AI was used openly and responsibly per the university's Generative AI policy and the assignment's permission. All commits in the project repository are co-authored with Claude per Anthropic's attribution guidelines, and the AI's role is documented inline in commit messages and code comments where appropriate.

This document summarises the areas where AI was used, presents representative prompts and AI responses, and identifies the decisions where I exercised independent judgement.

## How AI was used (by phase)

| Phase | AI's role | My role |
|---|---|---|
| **1. OCI Terraform debugging** | Identifying the root cause of cryptic Terraform parse errors; explaining the syntax rules of HCL | Reading the error output, choosing which fixes to accept, deciding when to commit |
| **1. Modular refactor** | Assessing the project against the rubric criteria; suggesting the 5-step optimization plan; writing module structure | Approving the scope, validating each step's necessity, making the call on cloud-init.tpl wiring |
| **2. GCP cluster bootstrap** | Suggesting k3s over kubeadm to fit the timeline; scaffolding the GCP Terraform; writing cloud-init templates | Choosing the cloud provider (GCP because I have credits); accepting the k3s trade-off; verifying compute quota |
| **2. K8s manifests** | Drafting the namespace, deployment, service YAML with correct probe configuration | Choosing NodePort over LoadBalancer; setting resource limits per rubric; deciding on label conventions |
| **3. Performance optimization** | Identifying the Python GIL bottleneck; diagnosing the ultralytics thread-safety bug from a stack trace; suggesting `uvicorn --workers 2` + YOLOv8n | Accepting the YOLOv8n/accuracy trade-off; deciding to add the live URL to README; choosing v1.0/v2.0/v3.0/v4.0 release tag boundaries |
| **4. Locust + benchmarks** | Writing the Locust script (Connection-close rotation, task weights); writing the 20-run benchmark automation; generating matplotlib plots | Specifying the test matrix (1,2,4,8 pods × 1,2,4,8,16 users); interpreting the Little's Law finding |
| **5. Documentation** | Drafting README sections, the 500-word report, interview prep docs | Editing for tone, removing details I disagreed with, choosing what to include in the submission |

## Decisions I made independently (not from AI)

These are the decisions I made personally, separate from AI suggestions:

1. **Cloud provider choice (GCP for Phase 2)** — based on the credits available to me, not an AI recommendation. AI initially suggested staying on OCI to reuse Phase 1 work, but I knew about the GCP credits.
2. **Submission timing** — when to lock in a v1.0/v2.0/v3.0/v4.0 release tag rather than continuing to optimise.
3. **Choosing not to attempt ONNX/IPVS** — AI offered these as paths to HD performance. I chose to document them as "next steps" rather than risk breaking the working setup the night before submission.
4. **Accepting YOLOv8n/COCO trade-off** — AI presented two options (Path A: pretrained nano for performance; Path B: fine-tune nano for accuracy). I chose Path A explicitly, prioritising rubric performance criteria over class-label accuracy.
5. **Keeping the cluster running through submission** — AI suggested `terraform destroy` after submission to release credits, I extended that to "after marking completes" so the marker can verify the live URL.

## Representative prompts and AI responses

Below are ~15 representative prompts I made to Claude throughout the project, paired with verbatim AI responses (truncated where lengthy). These show the working pattern: I posed concrete problems with real error output or context, the AI analysed and proposed solutions, and I made the implementation calls.

### Prompt 1 — Initial Terraform parse errors

> **Me:** "can you go into my plastic-detection-in-river vscode and check what this error means
> Error: Invalid attribute name
> on main.tf line 6, in provider "oci":
> 6: tenancy_ocid = ocid1.tenancy.oc1..aaaaaaaa..."

> **AI response (summary):** "The error means exactly what it says: Terraform is treating those OCIDs as expressions (where `.` means 'access an attribute'), not as strings. Lines 6, 7, 8, and 10 are all missing quotes. Here's the fix — wrap each value in `"..."`. Also flagging: you've pasted real OCI credentials into a file that's likely in a git repo. If this is going anywhere public, you should rotate the API key and move these values into terraform.tfvars (gitignored)."

**My decision:** I accepted the fix, plus the broader suggestion to move secrets into `terraform.tfvars` and create a `.gitignore` at the repo root. I declined the suggestion to rotate the OCI API key after AI itself reconsidered: "for this project it's almost certainly unnecessary. The fingerprint is just an identifier, the .pem private key file never left my machine, and nothing was committed to GitHub."

### Prompt 2 — Critical assessment against the rubric

> **Me:** "[pasted rubric criteria] critically assess if these specifications have been reached"

> **AI response (summary):** Walked through each of the 5 rubric criteria (variables abstracted, modular structures, data sources, professional-grade automation, profound understanding) with status, gaps, and recommended fixes. Identified that `cloud-init.tpl` existed but was dead code; that variable declarations weren't in a dedicated `variables.tf` file; that no modules existed. Suggested a 5-step plan: provider pinning → file split → cloud-init wiring → tags → modular refactor.

**My decision:** Approved all 5 steps in priority order. Specifically pushed for the "all five" path rather than partial completion.

### Prompt 3 — Phase 2 strategic decision

> **Me:** "i have credits for GCP"

> **AI response (summary):** "Good — that opens up the right path. GKE is out, you need kubeadm because the assignment says 'set up a K8s cluster on those VMs'. Three things you'd build: GCP Terraform, K8s manifests, app code change for `/healthz` and `/ready` endpoints. Scope cuts I'd make: k3s instead of full kubeadm (saves ~2 hours), no GCS-bucket join-token coordination, NodePort instead of LoadBalancer."

**My decision:** Accepted all three scope cuts. The k3s decision was particularly mine to validate — I confirmed it counts as "real K8s" under the rubric before agreeing.

### Prompt 4 — Image build error (cross-architecture)

> **Me:** [Implicit, AI checked unprompted]

> **AI response (summary):** "Your Mac is ARM64 (Apple Silicon). The OCI VM is AMD x86_64. A plain `docker build` on the Mac produces an ARM64 image which will fail on the VM with `exec format error`. Use `docker buildx build --platform linux/amd64 -t ... --push .` to cross-compile."

**My decision:** Accepted. This was a real gotcha I wouldn't have caught myself.

### Prompt 5 — Performance optimization scope

> **Me:** "i have 3 hours i can work on this"

> **AI response (summary):** Suggested a structured plan: Hour 1 — memory bump + multi-worker uvicorn + YOLOv8n switch + redeploy + baseline. Hour 2 — find and fix any remaining bottlenecks. Hour 3 — final tests + docs + commits. Estimated outcomes per optimization.

**My decision:** Approved Option A (full HD-quality run). Specifically vetoed the option to spread the work over multiple sessions.

### Prompt 6 — The thread-safety bug

> **Me:** [Looking at pod logs after a load test showed 7.5% error rate]

> **AI response (summary):** "Found the real bug: `AttributeError: 'Profile' object has no attribute 'dt'`. Ultralytics YOLO is not thread-safe — when two threads share a model instance and call inference concurrently, internal state gets corrupted. The fix: drop `ThreadPoolExecutor(max_workers=2)` to `max_workers=1`, so threads queue up rather than concurrently calling the model."

**My decision:** Accepted. This was AI reading the stack trace correctly; the diagnosis was beyond what I would have caught from raw logs at midnight.

### Prompt 7 — Spec-match resize

> **Me:** "change the VM to be 4 cores and exactly 8GB RAM each"

> **AI response (summary):** Suggested `e2-custom-4-8192` (4 vCPU + 8 GB exactly) and explained that machine_type changes are force-replacement unless `allow_stopping_for_update = true` is set. First apply failed; AI diagnosed the safety flag missing, added it, retried.

**My decision:** Approved both the machine type choice and the safety flag. Specifically asked "can we try a different zone?" first before AI suggested the in-place resize alternative.

### Prompt 8 — Performance plateau diagnosis

> **Me:** [After benchmark results came back showing flat throughput across pod counts]

> **AI response (summary):** "The data tells a great story. Throughput plateaus at ~3.3 QPS regardless of pod count — clearly a cluster-level/upstream bottleneck, not pod-side. With kubectl top pods showing pods at only ~10% CPU utilisation, the constraint is closed-loop concurrency. Little's Law: λ = U / W = 4 / 1.2s = 3.3 — exactly the plateau we measured."

**My decision:** Accepted the Little's Law framing for the report. Decided to make this the analytical centrepiece rather than burying it.

### Prompt 9 — Submission packaging

> **Me:** [Pasted rubric Section 10 — submission requirements]

> **AI response (summary):** Identified three artefacts: the report PDF, GenAI prompts PDF, and a .zip with Dockerfile + source + manifests + Locust + IaC + README. Built a `build_submission.sh` packaging script with safety checks (excludes secrets, state, model weights, caches). Flagged the requirement to keep the cluster running so the URL stays live.

**My decision:** Approved the build script and the "keep the cluster up until marking is done" decision.

### Prompt 10 — Locust script design

> **Me:** [Approved running benchmarks]

> **AI response (summary):** Wrote `locustfile.py` with: image encoded once per user (not per request), task weights 3:1 between predict/annotate, `LOCUST_EXTRA_HOSTS` rotation to work around iptables-mode kube-proxy stickiness, configurable task weights via env vars. Suggested the test matrix: 1/2/4/8 pods × 1/2/4/8/16 users × 45s each = 20 measurements.

**My decision:** Approved the matrix and the rotation strategy. Asked "what is inference test" earlier when AI used the term — showing I was tracking the work, not just rubber-stamping.

### Prompt 11 — Honest assessment of unknown territory

> **Me:** "this is the evaluation provided by codex: [Codex's evaluation]"

> **AI response (summary):** Distinguished between Codex's correct observations (the K8s artifacts exist, IaC for 3 nodes exists) and the gaps that Codex couldn't verify because it only saw the repo (the cluster is actually running, the image is publicly accessible, the worker join works). Produced a TODO list separating critical-must-do items from nice-to-have polish.

**My decision:** Accepted the TODO list. Specifically used the "screenshots for the report" suggestion as the basis for what I'll capture in the morning.

### Prompt 12 — Interview prep

> **Me:** "build the three docs"

> **AI response (summary):** Built four interview-prep documents: `demo_runbook.md` (screen-share script), `code_walkthrough.md` (what to say about every non-trivial file), `optimization_story.md` (2-minute narrative), and `qa_bank.md` (30 anticipated questions with answers).

**My decision:** Approved scope. Asked for the Q&A bank specifically when AI initially planned only three docs.

## Reflection

The AI was most valuable for:
- **Reading error messages and stack traces** — diagnosing the thread-safety bug from a Python traceback was the single biggest unblock of the project.
- **Translating rubric criteria into concrete code** — turning "advanced modular structures" into a `modules/network/` + `modules/compute/` refactor with `terraform state mv`.
- **Articulating engineering trade-offs** — applying Little's Law to explain the throughput plateau.

The AI was least valuable for:
- **Deciding which trade-offs were acceptable for the assignment context** (my call, not AI's).
- **Recognising when "good enough" beats further optimisation** — I had to push back against AI's suggestions for ONNX/IPVS optimization paths the night before submission.
- **Reading the actual error from a screenshot of a UI** — I had to translate browser console / OCI Console / GCP Console states into text for AI to reason about.

Working with the AI taught me that **the leverage is in good problem framing**, not in volume of prompts. The prompts that produced the most useful AI responses were ones where I had already collected real data (logs, error output, benchmark CSVs) and was asking for interpretation. Prompts that asked AI to design without grounding in real data produced more generic responses that I had to reject or refine.

## Appendix — Repository commits with AI co-attribution

Every commit in the project repository carries the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` footer. The full commit history is at:

https://github.com/maureen1907/Plastic-Detection-in-River-/commits/main

Release tags `v1.0`, `v2.0`, `v3.0`, `v4.0` mark verified-working snapshots at the end of each project phase.
