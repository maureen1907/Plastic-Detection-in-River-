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

    @task(3)
    def predict(self) -> None:
        """POST /api/predict — returns detection JSON (boxes, classes, speed)."""
        with self.client.post(
            PREDICT_PATH,
            json=self._payload(),
            name=PREDICT_PATH,
            catch_response=True,
            timeout=30,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")
            else:
                # Optional: validate the response shape
                body = resp.json()
                if "detections" not in body:
                    resp.failure(f"Missing 'detections' in response: {body}")

    @task(1)
    def annotate(self) -> None:
        """POST /api/annotate — returns annotated image + detection JSON."""
        with self.client.post(
            ANNOTATE_PATH,
            json=self._payload(),
            name=ANNOTATE_PATH,
            catch_response=True,
            timeout=60,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")
