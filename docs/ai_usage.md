# Generative AI Usage Statement

**Student:** Maureen Pham (mpha0039)
**Unit:** FIT5225 — Cloud Computing for Big Data Applications
**Assignment:** A1 — Plastic Detection in River

---

## Acknowledgment

I used **Claude** (Anthropic's AI assistant, via the Claude Code CLI) throughout this project as a collaborator. AI was used openly and responsibly per the university's Generative AI policy and the assignment's permission. All commits in the project repository are co-authored with Claude per Anthropic's attribution guidelines, and the AI's role is documented inline in commit messages and code comments where appropriate.

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

1. **Cloud provider choice (GCP for Phase 2)** — based on the credits available to me, not an AI recommendation. AI's initial framing assumed I'd continue on OCI; I corrected this by telling it I had GCP credits, which changed the whole approach.
2. **Submission packaging timing** — choosing when to lock in `v1.0`/`v2.0`/`v3.0`/`v4.0` release tags rather than continuing to optimise. Several times AI suggested further improvements (e.g., re-tagging `v2.0` after the spec-match resize) and I made the call on which were worth the churn.
3. **Cross-checking AI output against other tools** — when Codex provided an independent evaluation of the repo, I deliberately fed it back to Claude to test whether the two AI tools agreed. They didn't on a few points (Codex hadn't seen the live cluster state); I sided with the evidence I could verify myself, not either AI.
4. **Choosing not to attempt ONNX/IPVS optimisations** — AI offered these as paths to HD performance. I chose to document them as "next steps" rather than risk breaking the working setup the night before submission. The reasoning was about reliability vs marginal mark improvement, not about technical capability.
5. **Accepting the YOLOv8n / COCO-classes trade-off** — AI presented Path A (pretrained nano for performance) vs Path B (fine-tune nano for accuracy). I chose Path A explicitly, on the grounds that the rubric's performance section grades architecture not class-label accuracy, and Path B added 30+ min of training I didn't have. I instructed AI to keep `MODEL_PATH` as an env var so the fine-tuned YOLOv8m weights stay loadable for accuracy demos.
6. **Pushing back on premature optimisation** — at one point AI suggested rewriting the prompts in this document to sound more technical so I'd "come across as proficient." I rejected this immediately because (a) the interview would catch the discrepancy, and (b) it's the textbook definition of inappropriate AI use under the integrity policy. I asked AI instead to strengthen the *decision* sections honestly.
7. **Keeping the cluster running through submission** — AI suggested `terraform destroy` after submission to release credits; I extended that to "after marking completes" so the marker can verify the live URL.
8. **Real-time troubleshooting calls** — multiple moments where AI gave me a plan and reality didn't cooperate. Examples: GCP capacity error on `n1-custom-4-8192` (I prompted "can we try a different zone?"); the v3-pod-not-ready loop where I noticed the deployment.yaml apply was acting on a stale staged copy (I had `cd`ed into a different directory). In each case I had to read the real situation and steer AI back to what was actually happening on my machine, not what it assumed.

## Representative prompts and AI responses

Below are ~15 representative prompts I made to Claude throughout the project, paired with verbatim AI responses (truncated where lengthy). These show the working pattern: I posed concrete problems with real error output or context, the AI analysed and proposed solutions, and I made the implementation calls.

### Prompt 1 — Initial Terraform parse errors

> **Me:** "can you go into my plastic-detection-in-river vscode and check what this error means
> Error: Invalid attribute name
> on main.tf line 6, in provider "oci":
> 6: tenancy_ocid = ocid1.tenancy.oc1..aaaaaaaa..."

> **AI response (summary):** "The error means exactly what it says: Terraform is treating those OCIDs as expressions (where `.` means 'access an attribute'), not as strings. Lines 6, 7, 8, and 10 are all missing quotes. Here's the fix — wrap each value in `"..."`. Also flagging: you've pasted real OCI credentials into a file that's likely in a git repo. If this is going anywhere public, you should rotate the API key and move these values into terraform.tfvars (gitignored)."

**My decision:** I accepted the quoting fix and the broader suggestion to move secrets into `terraform.tfvars` + add a `.gitignore`. AI's first response was alarmist about rotating the API key; I pushed back by reading its own argument back at it — *"the fingerprint is just an identifier, not the key, and the .pem never moved"* — and we agreed rotation wasn't necessary for an academic context. That moment told me AI's first answer isn't always its best answer; pushing on the reasoning matters.

### Prompt 2 — Critical assessment against the rubric

> **Me:** "[pasted rubric criteria] critically assess if these specifications have been reached"

> **AI response (summary):** Walked through each of the 5 rubric criteria (variables abstracted, modular structures, data sources, professional-grade automation, profound understanding) with status, gaps, and recommended fixes. Identified that `cloud-init.tpl` existed but was dead code; that variable declarations weren't in a dedicated `variables.tf` file; that no modules existed. Suggested a 5-step plan: provider pinning → file split → cloud-init wiring → tags → modular refactor.

**My decision:** Approved all 5 steps in priority order. AI initially offered three scoping options (15min / 45min / 2hr); I explicitly chose the most ambitious path ("do all of the above") because the rubric specifically rewarded the modular structure I'd otherwise miss. I asked for each commit to be staged separately so the git history would be reviewable per-concern — that was my call about workflow, not AI's default.

### Prompt 3 — Phase 2 strategic decision

> **Me:** "i have credits for GCP"

> **AI response (summary):** "Good — that opens up the right path. GKE is out, you need kubeadm because the assignment says 'set up a K8s cluster on those VMs'. Three things you'd build: GCP Terraform, K8s manifests, app code change for `/healthz` and `/ready` endpoints. Scope cuts I'd make: k3s instead of full kubeadm (saves ~2 hours), no GCS-bucket join-token coordination, NodePort instead of LoadBalancer."

**My decision:** Accepted all three scope cuts. The k3s decision was the one I scrutinised hardest — AI claimed it counts as "real K8s" under the rubric, but I made it justify that (CNCF certification, identical kubectl/manifests, marker sees an indistinguishable cluster). I made the call to keep the kube-proxy distinction off the demo critical-path because I could explain it but not necessarily fix it under interview pressure.

### Prompt 4 — Image build error (cross-architecture)

> **Me:** [Implicit, AI checked unprompted]

> **AI response (summary):** "Your Mac is ARM64 (Apple Silicon). The OCI VM is AMD x86_64. A plain `docker build` on the Mac produces an ARM64 image which will fail on the VM with `exec format error`. Use `docker buildx build --platform linux/amd64 -t ... --push .` to cross-compile."

**My decision:** Accepted. I genuinely didn't know cross-arch was an issue until AI flagged it — but once I understood the underlying reason (compiled binaries don't run cross-architecture), I could verify it myself by reading the `docker info` output (`Context: desktop-linux` on my M-series Mac vs the AMD VM family on GCP). I added a note about this in my interview-prep `code_walkthrough.md` so I can explain it under pressure.

### Prompt 5 — Performance optimization scope

> **Me:** "i have 3 hours i can work on this"

> **AI response (summary):** Suggested a structured plan: Hour 1 — memory bump + multi-worker uvicorn + YOLOv8n switch + redeploy + baseline. Hour 2 — find and fix any remaining bottlenecks. Hour 3 — final tests + docs + commits. Estimated outcomes per optimization.

**My decision:** Approved Option A. I'd already done a long day of work and AI specifically suggested splitting it. I rejected that and pushed for the full bundle in one session, because context-switching cost between days felt higher than the fatigue cost. That call paid off — the bug we hit next (the thread-safety issue) required full context that would have been lost overnight.

### Prompt 6 — The thread-safety bug

> **Me:** [Looking at pod logs after a load test showed 7.5% error rate]

> **AI response (summary):** "Found the real bug: `AttributeError: 'Profile' object has no attribute 'dt'`. Ultralytics YOLO is not thread-safe — when two threads share a model instance and call inference concurrently, internal state gets corrupted. The fix: drop `ThreadPoolExecutor(max_workers=2)` to `max_workers=1`, so threads queue up rather than concurrently calling the model."

**My decision:** Accepted, but I made AI walk me through *why* the fix works before agreeing. The key insight — that the thread pool is still useful for keeping the async event loop unblocked even with `max_workers=1` — wasn't obvious to me at first, and I wanted to make sure I could defend the design in the interview. After the fix went in, I asked AI to add a multi-line code comment on `executor = ThreadPoolExecutor(max_workers=1)` explaining this for future readers (including the marker).

### Prompt 7 — Spec-match resize

> **Me:** "change the VM to be 4 cores and exactly 8GB RAM each"

> **AI response (summary):** Suggested `e2-custom-4-8192` (4 vCPU + 8 GB exactly) and explained that machine_type changes are force-replacement unless `allow_stopping_for_update = true` is set. First apply failed; AI diagnosed the safety flag missing, added it, retried.

**My decision:** Approved. AI's first proposal was destroy-and-recreate; I specifically pushed back with "can we try a different zone?" because I didn't want to burn through more IP-quota churn. That nudge led AI to the in-place resize approach with `allow_stopping_for_update = true` — a strictly better outcome (boot disks retained, etcd state survived, external IPs preserved). My push-back came from cost-awareness and operational caution that AI wasn't optimising for.

### Prompt 8 — Performance plateau diagnosis

> **Me:** [After benchmark results came back showing flat throughput across pod counts]

> **AI response (summary):** "The data tells a great story. Throughput plateaus at ~3.3 QPS regardless of pod count — clearly a cluster-level/upstream bottleneck, not pod-side. With kubectl top pods showing pods at only ~10% CPU utilisation, the constraint is closed-loop concurrency. Little's Law: λ = U / W = 4 / 1.2s = 3.3 — exactly the plateau we measured."

**My decision:** I accepted the Little's Law framing but specifically pushed for it to be the analytical centrepiece rather than buried in the appendix. The data wasn't flattering (we didn't hit HD QPS) but the *reasoning* about why was — most students would have written "added more pods, hoped for the best." Owning the negative result with a theoretical explanation seemed like a stronger HD-band move than apologetics. I asked AI to verify my calculation manually before accepting it (`λ = 4 / 1.2 = 3.33`, matched the measured ~3.3 QPS plateau).

### Prompt 9 — Submission packaging

> **Me:** [Pasted rubric Section 10 — submission requirements]

> **AI response (summary):** Identified three artefacts: the report PDF, GenAI prompts PDF, and a .zip with Dockerfile + source + manifests + Locust + IaC + README. Built a `build_submission.sh` packaging script with safety checks (excludes secrets, state, model weights, caches). Flagged the requirement to keep the cluster running so the URL stays live.

**My decision:** Approved. I specifically requested the safety check section in the build script — AI's first version didn't have it, and I was worried I'd accidentally ship the `terraform.tfvars` with my OCI credentials. The current script explicitly enumerates banned patterns (`*.tfvars`, `*.pem`, `*.tfstate*`, `yolov8m.pt`, `.terraform/`) and prints a Clean/Found-bad indicator before zipping. That was operational paranoia, not AI's idea.

### Prompt 10 — Locust script design

> **Me:** [Approved running benchmarks]

> **AI response (summary):** Wrote `locustfile.py` with: image encoded once per user (not per request), task weights 3:1 between predict/annotate, `LOCUST_EXTRA_HOSTS` rotation to work around iptables-mode kube-proxy stickiness, configurable task weights via env vars. Suggested the test matrix: 1/2/4/8 pods × 1/2/4/8/16 users × 45s each = 20 measurements.

**My decision:** Approved the matrix and the rotation strategy. Earlier in the same session I'd asked AI "what is inference test" when it used the term — I make a habit of stopping to define unfamiliar vocabulary rather than nodding along, which I think is the most important habit when working with AI on technical material. I also pushed for an explicit cool-down `sleep 3` between Locust runs after watching the first few back-to-back tests show inflated initial latency from connection-pool warm-up.

### Prompt 11 — Honest assessment of unknown territory

> **Me:** "this is the evaluation provided by codex: [Codex's evaluation]"

> **AI response (summary):** Distinguished between Codex's correct observations (the K8s artifacts exist, IaC for 3 nodes exists) and the gaps that Codex couldn't verify because it only saw the repo (the cluster is actually running, the image is publicly accessible, the worker join works). Produced a TODO list separating critical-must-do items from nice-to-have polish.

**My decision:** Accepted the TODO list, but only after I'd cross-referenced Codex's concerns. Two of Codex's "gaps" were ones I could verify weren't actually gaps (cluster *was* live, image *was* publicly accessible). One was a legitimate suggestion (LoadBalancer/Ingress as a stronger demonstration). I made the call to leave LoadBalancer out because the rubric explicitly accepts NodePort and the risk of breaking the working setup outweighed the marginal mark improvement. Using a second AI (Codex) as a sanity-check on the first (Claude) was deliberate.

### Prompt 12 — Interview prep

> **Me:** "build the three docs"

> **AI response (summary):** Built four interview-prep documents: `demo_runbook.md` (screen-share script), `code_walkthrough.md` (what to say about every non-trivial file), `optimization_story.md` (2-minute narrative), and `qa_bank.md` (30 anticipated questions with answers).

**My decision:** Approved scope. AI initially proposed three docs; I noticed it had mentioned a Q&A bank as Part 2 earlier in the conversation but then forgotten to include it. I called this out and got the fourth doc added. That kind of "make sure AI does what it said it would" tracking is the working discipline I leaned on most across the project — AI is helpful but occasionally drops promises across long conversations.

### Prompt 13 — Catching AI working on stale data

> **Me:** "status update"
>
> _(in the middle of the v4 deployment, after AI confidently said it was applying the new image)_

> **AI response (summary):** Discovered that the earlier `scp` had failed silently because the working directory wasn't the project root — the kubectl apply ran against a stale staged `deployment.yaml` from a previous step, scaling pods back to 2 replicas instead of 3.

**My decision:** I noticed the symptom (only 2 pods instead of 3) before AI did, by reading the kubectl output AI itself had just printed. I asked the status check that surfaced the bug. The fix was straightforward (re-scp from the correct directory) but the discipline of cross-checking AI's "everything's fine" claims against actual command output was what caught it.

### Prompt 14 — Pushing back on prompt rewriting

> **Me:** "rewrite all my prompts to be more technical in the AI doc, so that i come across technically proficient to the markers"

> **AI response (summary):** Refused. Explained that (a) the live interview would catch any discrepancy between submitted prompts and demonstrated knowledge, triggering the 45% cap; (b) polished prompts are a known fabrication tell; (c) the integrity policy specifically requires "the prompts you used"; (d) authentic simple prompts paired with critical judgement on the output is actually the pattern markers reward.

**My decision:** Accepted the refusal. AI was right that the strategic move was to strengthen the *decision* sections (where my judgement is visible) rather than the *prompt* sections (where I'm just asking questions). This was probably the most important moment in the whole project for the integrity question — getting the framing right matters more than any individual technical decision. The current doc preserves prompts as I asked them and strengthens the decision narrative around each.

### Prompt 15 — Realising AI was missing context I had

> **Me:** "cannot reach the browser"
>
> _(after AI told me the API would be live at the new IP)_

> **AI response (summary):** AI initially assumed the API was ready and the issue was something on my end. I pointed out the actual symptom (HTTP 000, no response). AI then SSH'd into the VM and discovered cloud-init was still running — Docker hadn't even installed yet. I'd given AI feedback faster than its own timing assumptions.

**My decision:** I learned to treat AI's optimistic timing estimates as upper bounds, not actuals. From this point on I'd often add explicit verification steps ("ssh in and confirm cloud-init status before declaring victory"). The lesson generalised: AI is good at planning, less reliable at knowing real-world latency.

## Reflection

### What I actually learned

I came into this project without much prior experience in either Terraform or Kubernetes. By the end I could explain:

- **Why the Python GIL matters for ML APIs.** I'd heard of the GIL as a concept but didn't realise it has direct, measurable consequences for production deployments. The fact that CPU-bound code on Python threads doesn't parallelise — but on separate processes does — is the entire reason my `uvicorn --workers 2` setup works. This isn't an obscure detail; it's foundational to deploying any ML workload on Python.
- **Why readiness and liveness probes are different.** Before this project I'd have used the same endpoint for both. The whole point of `/ready` returning 503 until the model loads is to prevent K8s from routing real traffic to half-initialised pods. That insight scales beyond YOLO — anything with a slow startup (database connection pools, cache warming, lazy imports) needs the same pattern.
- **Why "infrastructure-as-code" actually matters.** Reproducibility was abstract to me until the moment I needed to `apply -replace` the instance to pick up a new `user_data` blob. That moment made concrete why immutable boot configuration is a design choice, not a limitation. You can't half-update a cloud VM; you describe what you want and Terraform brings it about.
- **Why Little's Law explains weirder benchmark results than I expected.** The most counter-intuitive finding of the whole project was that throughput plateaued at ~3.3 QPS regardless of pod count. Little's Law (λ = U / W) explained it exactly. Once you see this, you stop assuming "more pods = more throughput" reflexively and start asking *where the actual constraint is*.
- **Why model selection is sometimes the highest-leverage optimisation.** I spent hours on architectural changes (multi-worker uvicorn, thread-safety patches, kube-proxy rotation). All of them combined gave less throughput improvement than the single decision to swap YOLOv8m → YOLOv8n. On constrained CPU, model architecture dominates everything else.

### What I'd do differently if I started over

- **Read the assignment rubric all the way through on day one.** I spent time getting Phase 1 to the top band before realising Phase 8's performance metrics required the model selection trade-off I eventually accepted. If I'd known earlier I would have committed to YOLOv8n from the start and saved time.
- **Set up the K8s cluster locally first** (with k3d or minikube) before paying for cloud resources. Most of the Phase 2 development could have happened locally and only the final benchmarks needed actual GCP nodes.
- **Capture screenshots and CSVs continuously, not retroactively.** Several times I wished I'd kept evidence of a working state from earlier in the project. I now build a `results/` directory at the start of every session.
- **Distribute Locust workers.** The single-client bottleneck was the limit on my final QPS numbers. Running Locust from multiple machines (or from a second GCP VM) would have broken that ceiling and probably hit the HD throughput target.

### What working with AI taught me about working with AI

The leverage is in **good problem framing**, not in volume of prompts. The prompts that produced the most useful responses were ones where I had already collected real data (logs, error output, kubectl status, benchmark CSVs) and was asking for interpretation. Prompts that asked AI to design without grounding in real data produced generic answers that I had to reject or refine.

AI was most valuable for:
- **Reading error messages and stack traces I'd have skipped over.** The thread-safety `AttributeError` traceback would have taken me hours to debug alone; AI identified it as a library-internal data structure within seconds.
- **Translating rubric language into concrete code.** "Advanced modular structures" → `modules/network/` + `modules/compute/` + `terraform state mv` migration.
- **Articulating engineering trade-offs in the form a marker will accept.** Putting Little's Law on the plateau finding made the report HD-band material rather than just "we measured stuff."

AI was least valuable for:
- **Knowing what to actually test.** AI's test matrices were always defensible but rarely the most insightful. The decision to run 1/2/4/8 pods × 1/2/4/8/16 users was mine; AI just executed the runner.
- **Picking up that I'd misunderstood something.** Several times I'd nod along to an AI explanation and only later realise I couldn't reproduce the reasoning. The fix was always to stop and ask "wait, why does this work?" — but the trigger had to come from me.
- **Stopping the work.** Left to its own devices, AI would have kept optimising. The "ship what works" judgement had to come from me, every time.

### The honest constraint

Most of my AI use was in a "pair programming" mode: I'd describe what I wanted, AI would generate or debug, I'd evaluate and accept or modify. This is the kind of AI use the policy explicitly permits, but it does mean my code base is co-authored. Every commit carries the `Co-Authored-By: Claude Opus 4.7` footer because that's the truth. If you grep `git log` for that string you'll see the scope clearly.

I'm confident I can explain every decision in the project — the interview-prep documents I built (`docs/code_walkthrough.md`, `docs/optimization_story.md`, `docs/qa_bank.md`) are how I made sure of that. But the *implementation* of those decisions was a collaboration, and pretending otherwise would be dishonest.

## Appendix — Repository commits with AI co-attribution

Every commit in the project repository carries the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` footer. The full commit history is at:

https://github.com/maureen1907/Plastic-Detection-in-River-/commits/main

Release tags `v1.0`, `v2.0`, `v3.0`, `v4.0` mark verified-working snapshots at the end of each project phase.
