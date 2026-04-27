from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
import asyncio

from model import model
from service import run_inference, extract_detections, annotate_image
from utils import base64_to_image, image_to_base64

app = FastAPI()
router = APIRouter(prefix="/api")

# Thread pool for running ML inference without blocking the event loop
executor = ThreadPoolExecutor(max_workers=2)


class ImagePayload(BaseModel):
    uuid: str
    image: str  # base64 encoded image


@router.get("/")
async def root():
    return {
        "message": "Plastic Detection API. Use /api/predict or /api/annotate"
    }


def run_inference_sync(model, img):
    """Synchronous wrapper for inference to run in thread pool."""
    return model(img)[0]


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
