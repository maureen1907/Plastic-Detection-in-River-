from fastapi import FastAPI, APIRouter, UploadFile, File, Form
from PIL import Image
import io

from model import model
from service import run_inference, extract_detections, annotate_image
from utils import image_to_base64

app = FastAPI()
router = APIRouter(prefix="/api")

@router.get("/")
async def root():
    return {
        "message": "Plastic Detection API. Use /api/predict or /api/annotate"
    }


@router.post("/predict")
async def predict(
    uuid: str = Form(...),
    file: UploadFile = File(...)
):
    image_bytes = await file.read()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    results = run_inference(model, img)
    detections, boxes = extract_detections(results)

    speed = results.speed

    return {
        "uuid": uuid,
        "count": len(detections),
        "detections": detections,
        "boxes": boxes,
        "speed_preprocess_ms": speed["preprocess"],
        "speed_inference_ms": speed["inference"],
        "speed_postprocess_ms": speed["postprocess"]
    }

@router.post("/annotate")
async def annotate(
    uuid: str = Form(...),
    file: UploadFile = File(...)
):
    image_bytes = await file.read()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    results = run_inference(model, img)
    annotated_img = annotate_image(results)

    encoded_img = image_to_base64(annotated_img)
    detections, boxes = extract_detections(results)

    return {
        "uuid": uuid,
        "image": encoded_img,
        "detections": detections,
        "boxes": boxes
    }


app.include_router(router)