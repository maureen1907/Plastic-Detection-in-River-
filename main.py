from fastapi import FastAPI, APIRouter, HTTPException
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
import asyncio

from model import model
from service import run_inference, extract_detections, annotate_image
from utils import base64_to_image, image_to_base64

app = FastAPI()
router = APIRouter(prefix="/api")


@app.get("/")
async def root():
    return {
        "message": "wassup slayer. use /api/predict or /api/annotate"
    }


@app.get("/healthz")
async def healthz():
    # Liveness: the process is alive and serving HTTP.
    return {"status": "alive"}


@app.get("/ready")
async def ready():
    # Readiness: the YOLO model has been loaded into memory and is callable.
    # K8s uses this to gate traffic; pods stay out of the service rotation
    # until this returns 200.
    if model is None or not hasattr(model, "predict"):
        raise HTTPException(status_code=503, detail="model not loaded")
    return {"status": "ready", "model": "yolov8m"}

# Thread pool for running ML inference without blocking the event loop.
#
# IMPORTANT: max_workers=1 (not the FastAPI default of >1) because
# ultralytics YOLO model state is not thread-safe -- concurrent inference
# calls on the same model instance corrupt internal timing/profile objects
# and raise `AttributeError: 'Profile' object has no attribute 'dt'`.
#
# True parallelism is achieved at the *process* level via uvicorn --workers,
# where each worker has its own Python process and its own model instance.
# Each worker's thread pool serialises inference within that process,
# so workers can run inference truly in parallel without sharing state.
executor = ThreadPoolExecutor(max_workers=1)


class ImagePayload(BaseModel):
    uuid: str
    image: str  # base64 encoded image


def run_inference_sync(model, img):
    """Synchronous wrapper for inference to run in thread pool."""
    return model(img)[0]


@router.get("/")
async def api_root():
    return {
        "message": "good job! rmr u can use /api/predict or /api/annotate"
    }


@router.post("/predict")
async def predict(payload: ImagePayload):
    img = base64_to_image(payload.image)

    # Run inference in thread pool to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(executor, run_inference_sync, model, img)

    detections, boxes = extract_detections(results)
    speed = results.speed

    return {
        "uuid": payload.uuid,
        "count": len(detections),
        "detections": detections,
        "boxes": boxes,
        "speed_preprocess_ms": speed["preprocess"],
        "speed_inference_ms": speed["inference"],
        "speed_postprocess_ms": speed["postprocess"]
    }


@router.post("/annotate")
async def annotate(payload: ImagePayload):
    img = base64_to_image(payload.image)

    # Run inference in thread pool to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(executor, run_inference_sync, model, img)

    annotated_img = annotate_image(results)
    encoded_img = image_to_base64(annotated_img)
    detections, boxes = extract_detections(results)

    return {
        "uuid": payload.uuid,
        "image": encoded_img,
        "detections": detections,
        "boxes": boxes
    }


app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
