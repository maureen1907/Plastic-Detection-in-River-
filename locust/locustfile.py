"""
Locust load generation script for the plastic-detection API.

Simulates concurrent users that POST a base64-encoded image to /api/predict
and /api/annotate. The image is read and encoded once per user (in on_start),
not per request, so the test client is not CPU-bound itself.

Run against the K8s NodePort:
    locust -f locustfile.py --host http://<node-ip>:30080

Or headless for CI-style runs:
    locust -f locustfile.py --host http://<node-ip>:30080 \\
           --users 20 --spawn-rate 5 --run-time 2m --headless \\
           --csv results
"""

from __future__ import annotations

import base64
import os
import random
import uuid
from pathlib import Path

from locust import HttpUser, between, events, task


# Path to the test image, resolved relative to this file unless overridden.
# Defaults to a validation image from the training run.
DEFAULT_IMAGE = Path(__file__).resolve().parent.parent / "runs" / "detect" / "train" / "val_batch0_labels.jpg"
TEST_IMAGE_PATH = Path(os.environ.get("LOCUST_TEST_IMAGE", DEFAULT_IMAGE))

# Endpoint paths under test
PREDICT_PATH = "/api/predict"
ANNOTATE_PATH = "/api/annotate"

# Comma-separated list of additional node IPs (NodePort exposes the service
# on every node's external IP; spreading requests across all of them gives
# kube-proxy on each node a fair chance to route to different pods, working
# around iptables-mode kube-proxy's per-connection (rather than per-request)
# load balancing).
EXTRA_HOSTS = [
    h.strip().rstrip("/")
    for h in os.environ.get("LOCUST_EXTRA_HOSTS", "").split(",")
    if h.strip()
]


@events.init.add_listener
def _on_locust_init(environment, **_kwargs):
    """Verify the test image is readable before any user starts."""
    if not TEST_IMAGE_PATH.exists():
        raise FileNotFoundError(
            f"Test image not found: {TEST_IMAGE_PATH}\n"
            f"Set LOCUST_TEST_IMAGE to a valid path or place an image at the default location."
        )
    size_kb = TEST_IMAGE_PATH.stat().st_size // 1024
    print(f"[locust] Using test image: {TEST_IMAGE_PATH} ({size_kb} KB)")


class PlasticDetectionUser(HttpUser):
    """
    Each simulated user encodes the test image once, then loops:
    POST /api/predict  (weight 3 — primary endpoint, called more often)
    POST /api/annotate (weight 1 — heavier endpoint, called less often)

    `wait_time` simulates "think time" between requests. Set to 0 for max
    throughput testing; set to between(1, 3) to simulate realistic user pacing.
    """

    # No think time -- saturate the server. For realistic user behaviour use
    # `between(1, 3)` instead.
    wait_time = between(0, 0)

    def on_start(self) -> None:
        """Encode the test image once per simulated user."""
        with open(TEST_IMAGE_PATH, "rb") as fh:
            self.image_b64 = base64.b64encode(fh.read()).decode("ascii")

    def _payload(self) -> dict:
        """Build the JSON payload with a fresh UUID per request."""
        return {
            "uuid": str(uuid.uuid4()),
            "image": self.image_b64,
        }

    def _request(self, path: str, timeout: int):
        """Wrap self.client.post so we can rotate the target host per request
        when LOCUST_EXTRA_HOSTS is set. Each request opens a fresh connection
        to a randomly-chosen node IP, bypassing kube-proxy's per-connection
        stickiness and giving us true per-request load balancing across pods.
        """
        if EXTRA_HOSTS:
            host = random.choice(EXTRA_HOSTS)
            return self.client.post(
                f"{host}{path}",
                json=self._payload(),
                name=path,
                headers={"Connection": "close"},  # force fresh TCP -> fresh route
                catch_response=True,
                timeout=timeout,
            )
        return self.client.post(
            path,
            json=self._payload(),
            name=path,
            catch_response=True,
            timeout=timeout,
        )

    @task(int(os.environ.get("LOCUST_WEIGHT_PREDICT", "3")))
    def predict(self) -> None:
        """POST /api/predict — returns detection JSON (boxes, classes, speed)."""
        with self._request(PREDICT_PATH, timeout=30) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")
            else:
                body = resp.json()
                if "detections" not in body:
                    resp.failure(f"Missing 'detections' in response: {body}")

    @task(int(os.environ.get("LOCUST_WEIGHT_ANNOTATE", "1")))
    def annotate(self) -> None:
        """POST /api/annotate — returns annotated image + detection JSON."""
        with self._request(ANNOTATE_PATH, timeout=60) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")
