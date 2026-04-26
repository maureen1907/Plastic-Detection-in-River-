# service.py

def run_inference(model, img):
    return model(img)[0]


def extract_detections(results):
    boxes = []
    detections = []

    for box in results.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        w = x2 - x1
        h = y2 - y1
        conf = float(box.conf[0])
        cls = int(box.cls[0])
        label = results.names[cls]

        detections.append(label)
        boxes.append({
            "x": x1,
            "y": y1,
            "width": w,
            "height": h,
            "probability": conf
        })

    return detections, boxes


def annotate_image(results):
    return results.plot()