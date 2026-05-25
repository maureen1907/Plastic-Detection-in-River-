"""
End-to-end test for the deployed plastic-detection API.

Reads every image in ./test_image/, sends each one to both /api/predict
(detection JSON) and /api/annotate (detection JSON + annotated image),
and writes the results to ./test_result/:

    test_result/<basename>_predict.json    detection JSON
    test_result/<basename>_annotate.json   detection JSON + base64 image
    test_result/<basename>_annotated.jpg   decoded annotated image
    test_result/summary.txt                per-image success/failure summary

Run from the project root:
    python3 test_endpoints.py
or:
    HOST=http://other-cluster:30080 python3 test_endpoints.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HOST = os.environ.get("HOST", "http://35.197.187.242:30080").rstrip("/")
REQUEST_TIMEOUT = int(os.environ.get("TIMEOUT_SECONDS", "120"))
PROJECT_ROOT = Path(__file__).resolve().parent
TEST_IMAGE_DIR = PROJECT_ROOT / "test_image"
TEST_RESULT_DIR = PROJECT_ROOT / "test_result"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def post_json(path: str, payload: dict, timeout: int = REQUEST_TIMEOUT) -> tuple[int, dict | str]:
    """POST a JSON body and return (status_code, parsed_body_or_text)."""
    url = f"{HOST}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def process_image(image_path: Path) -> dict:
    """Run both endpoints on one image, write outputs, return status dict."""
    result = {"image": image_path.name, "predict": "skipped", "annotate": "skipped"}

    print(f"\n--- {image_path.name} ---")
    image_b64 = encode_image(image_path)
    payload = {"uuid": str(uuid.uuid4()), "image": image_b64}
    base = image_path.stem

    # /api/predict
    t0 = time.time()
    status, body = post_json("/api/predict", payload)
    dt = time.time() - t0
    if status == 200 and isinstance(body, dict):
        out_predict = TEST_RESULT_DIR / f"{base}_predict.json"
        out_predict.write_text(json.dumps(body, indent=2))
        count = body.get("count", "?")
        detections = body.get("detections", [])
        print(f"  /api/predict   HTTP 200 in {dt:.2f}s  count={count} detections={detections[:5]}")
        result["predict"] = f"OK count={count} in {dt:.2f}s"
    else:
        print(f"  /api/predict   HTTP {status} in {dt:.2f}s  -> {str(body)[:200]}")
        result["predict"] = f"FAIL {status}"

    # /api/annotate
    t0 = time.time()
    status, body = post_json("/api/annotate", payload)
    dt = time.time() - t0
    if status == 200 and isinstance(body, dict):
        # Save the JSON envelope (without re-pasting the image body)
        meta = {k: v for k, v in body.items() if k != "image"}
        out_annotate_json = TEST_RESULT_DIR / f"{base}_annotate.json"
        out_annotate_json.write_text(json.dumps(meta, indent=2))
        # Decode + save the annotated image
        if "image" in body:
            out_image = TEST_RESULT_DIR / f"{base}_annotated.jpg"
            out_image.write_bytes(base64.b64decode(body["image"]))
            print(f"  /api/annotate  HTTP 200 in {dt:.2f}s  -> {out_image.name} ({out_image.stat().st_size//1024} KB)")
            result["annotate"] = f"OK saved {out_image.name} in {dt:.2f}s"
        else:
            print(f"  /api/annotate  HTTP 200 but no 'image' field in response")
            result["annotate"] = "FAIL no-image-field"
    else:
        print(f"  /api/annotate  HTTP {status} in {dt:.2f}s  -> {str(body)[:200]}")
        result["annotate"] = f"FAIL {status}"

    return result


def main() -> int:
    if not TEST_IMAGE_DIR.exists():
        print(f"ERROR: {TEST_IMAGE_DIR} does not exist. Create it and drop test images in.")
        return 2

    TEST_RESULT_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(
        p for p in TEST_IMAGE_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )
    if not images:
        print(f"ERROR: no images found in {TEST_IMAGE_DIR}.")
        print(f"  Drop .jpg/.jpeg/.png/.bmp files in that folder and re-run.")
        return 2

    print(f"Host:        {HOST}")
    print(f"Test images: {len(images)} file(s) from {TEST_IMAGE_DIR}")
    print(f"Output:      {TEST_RESULT_DIR}")

    # Quick liveness check before hammering the cluster
    print("\nLiveness check...")
    status, body = post_json("/ready", {})  # ready is GET, but a quick check is fine
    # The /ready endpoint is GET; do a proper GET instead
    try:
        with urllib.request.urlopen(f"{HOST}/ready", timeout=10) as r:
            print(f"  GET /ready -> HTTP {r.status} ({r.read().decode().strip()})")
    except Exception as e:
        print(f"  WARNING: /ready not reachable: {e}")
        print(f"  Continuing anyway -- per-image errors will be reported.")

    results = [process_image(p) for p in images]

    # Write summary
    summary_lines = [
        f"plastic-detection API end-to-end test",
        f"Host: {HOST}",
        f"Images tested: {len(images)}",
        "",
        f"{'image':40} {'/api/predict':35} {'/api/annotate':35}",
        f"{'-'*40} {'-'*35} {'-'*35}",
    ]
    for r in results:
        summary_lines.append(f"{r['image']:40} {r['predict']:35} {r['annotate']:35}")

    summary_path = TEST_RESULT_DIR / "summary.txt"
    summary_path.write_text("\n".join(summary_lines) + "\n")
    print(f"\nSummary written to {summary_path}\n")
    print("\n".join(summary_lines[3:]))

    all_ok = all(r["predict"].startswith("OK") and r["annotate"].startswith("OK") for r in results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
