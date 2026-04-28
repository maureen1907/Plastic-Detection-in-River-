from ultralytics import YOLO
import torch

# Patch torch.load to disable weights_only for loading the checkpoint
_original_load = torch.load

def _patched_load(*args, **kwargs):
    kwargs.setdefault('weights_only', False)
    return _original_load(*args, **kwargs)

torch.load = _patched_load

model = YOLO('runs/detect/train/weights/best.pt')

# Restore original torch.load
torch.load = _original_load
