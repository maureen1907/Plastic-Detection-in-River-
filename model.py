"""
Model loader.

The deployed image uses YOLOv8n (nano), the smallest YOLOv8 variant
(~6 MB weights, ~5-10x faster CPU inference than the YOLOv8m variant used
during initial development). This is the deliberate performance-tuning
trade-off described in the report: trades a small amount of mAP for an
order-of-magnitude latency improvement, which is the only way to hit the
HD performance target (>10 QPS/pod, <500ms latency) on a 1 vCPU pod.

To use the fine-tuned YOLOv8m weights instead, set MODEL_PATH=runs/detect/train/weights/best.pt
"""

import os
from ultralytics import YOLO
import torch

# Patch torch.load to disable weights_only for loading any local checkpoint
_original_load = torch.load


def _patched_load(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _original_load(*args, **kwargs)


torch.load = _patched_load

# Default: YOLOv8n pretrained weights (auto-downloaded on first run).
# Override via env var to use the fine-tuned YOLOv8m or any other checkpoint.
MODEL_PATH = os.environ.get("MODEL_PATH", "yolov8n.pt")
model = YOLO(MODEL_PATH)

# Restore original torch.load
torch.load = _original_load
