import streamlit as st
from PIL import Image
import requests
import base64
import uuid
import io

st.set_page_config(layout="wide", page_title="Plastic in River")
st.write("# Detect whether there is plastic in river or not")


def image_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


with st.sidebar:
    st.title("Plastic in River")
    uploaded_image = st.file_uploader("Upload an Image", type=["png", "jpg", "jpeg"])
    submitted = st.button("Predict")


if not submitted or not uploaded_image:
    st.stop()

try:
    image = Image.open(uploaded_image)

    encoded_img = image_to_base64(image)

    payload = {
        "uuid": str(uuid.uuid4()),
        "image": encoded_img
    }

    # --- Predict ---
    response = requests.post(
        "http://127.0.0.1:8000/api/predict",
        json=payload
    )
    result = response.json()

    st.subheader("Detections")
    st.write(f"Count: {result['count']}")
    st.write(result["detections"])

    # --- Annotate ---
    response_img = requests.post(
        "http://127.0.0.1:8000/api/annotate",
        json=payload
    )
    result_img = response_img.json()

    decoded_img = base64.b64decode(result_img["image"])
    img = Image.open(io.BytesIO(decoded_img))

    st.image(img, caption="Annotated Image")

except Exception as e:
    st.error(f"Error: {e}")