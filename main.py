
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
from model import model
from utils import base64_to_image, image_to_base64
from service import run_inference, extract_detections, annotate_image

app = FastAPI()

class PredictRequest(BaseModel):
    uuid: str
    image: str

router = APIRouter(prefix="/api")

@app.get("/")
async def root():
    return {"message": "Welcome to the Plastic Detection API. Use /api/predict to get predictions and /api/annotate to get annotated images."}

@router.post("/predict")
async def predict(req: PredictRequest):
    img = base64_to_image(req.image)

    results = run_inference(model, img)
    detections, boxes = extract_detections(results)

    speed = results.speed

    return {
        "uuid": req.uuid,
        "count": len(detections),
        "detections": detections,
        "boxes": boxes,
        "speed_preprocess_ms": speed["preprocess"],
        "speed_inference_ms": speed["inference"],
        "speed_postprocess_ms": speed["postprocess"]
    }


@router.post("/annotate")
async def annotate(req: PredictRequest):
    img = base64_to_image(req.image)

    results = run_inference(model, img)
    annotated_img = annotate_image(results)

    encoded_img = image_to_base64(annotated_img)

    return {
        "uuid": req.uuid,
        "image": encoded_img,
        "detections": [...],
        "boxes": [...],
        "image": "base64..."
    }



app.include_router(router)