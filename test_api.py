import base64
import requests
import uuid
import sys

if len(sys.argv) < 2:
    print("Usage: python test_api.py <image_path>")
    sys.exit(1)

image_path = sys.argv[1]

# Read and encode image
with open(image_path, "rb") as f:
    encoded = base64.b64encode(f.read()).decode("utf-8")

payload = {
    "uuid": str(uuid.uuid4()),
    "image": encoded
}

print("Sending request...")
response = requests.post("http://localhost:8000/api/predict", json=payload)
print(f"Status: {response.status_code}")
print(response.json())