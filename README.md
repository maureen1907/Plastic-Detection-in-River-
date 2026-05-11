# Plastic-Detection-in-River

Plastic pollution in marine environnement is a global threat. It threatens marine species health, human health, food security, costal tourism. More than 350 million tons of plastic are produced every year and it is estimated that more than 15 million tons end up in the world Ocean. The plastic then degrades over time into micro-plastic and both macro and microplastic have serious environmental impacts. Rivers are the very first source of plastic in Oceans. It is estimated that more than 80% of river plastic comes from only 1000 rivers. Organizations like the The Ocean Cleanup are investing resources to address the ocean plastic pollution at the root cause by cleaning rivers.

Inorder to tackle the above problem, this is a streamlit app that detects whether there is plastic in river or not using Deep Learning techniques like Object Detection and state-of-the-art Object Detection Models like "You only look once (YOLO)".

This app uses the YOLOv8m Pre-trained Object Detection model to train on the custom dataset. This dataset contains photos of rivers on which there may be waste. The waste items are annotated through bounding boxes, and are assigned to one of the 4 following categories: Plastic Bags, Plastic Bottles, Other Plastic Waste and No Plastic waste. Note that some photos may not contain any waste.

## Dataset

The dataset is included in the file ```convert_to_yolo.py``` which downloads the datasets and converts them into YOLO usable format. Alternatively, you can also download the dataset from [here](https://huggingface.co/datasets/Kili/plastic_in_river). The dataset is split into ***```train```*** and ***```validation```*** with ***3407*** and ***425*** images respectively

The downloaded dataset after conversion to YOLO Format is in the following structure:
```
datasets
├─ images
│  ├─ train
│  │  ├─ 0.png
│  │  ├─ 1.png
│  │  └─ ...
│  └─ validation
│     ├─ 0.png
│     ├─ 1.png
│     └─ ...
└─ labels
   ├─ train
   │  ├─ 0.txt
   │  ├─ 1.txt
   │  └─ ...
   └─ validation
      ├─ 0.txt
      ├─ 1.txt
      └─ ...
```

The text file for labels contains the data in the following format:
```
0 x_n y_n w_n h_n
1 x_n y_n w_n h_n
...
```

## Preview
![screenshot](/Screenshots/Example-screenshot.png)

---

## API Documentation

### Features

- **RESTful API** - FastAPI endpoints for prediction and annotation
- **Base64 Image Support** - Accepts base64-encoded images in JSON payloads
- **Async ML Inference** - Non-blocking inference using ThreadPoolExecutor
- **Docker Support** - Multi-stage Docker build for optimized deployment
- **Health Monitoring** - Built-in healthcheck for container orchestration

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root endpoint |
| `/api/` | GET | API info |
| `/api/predict` | POST | Detect plastic in image |
| `/api/annotate` | POST | Detect and return annotated image |

### Request Format

```json
{
  "uuid": "unique-id-123",
  "image": "base64_encoded_image_string"
}
```

### Response Format

#### /api/predict
```json
{
  "uuid": "unique-id-123",
  "count": 5,
  "detections": ["plastic", "plastic", "plastic", "plastic", "plastic"],
  "boxes": [
    {"x": 100, "y": 200, "width": 50, "height": 60, "probability": 0.95}
  ],
  "speed_preprocess_ms": 10,
  "speed_inference_ms": 150,
  "speed_postprocess_ms": 5
}
```

#### /api/annotate
```json
{
  "uuid": "unique-id-123",
  "image": "base64_encoded_annotated_image",
  "detections": ["plastic"],
  "boxes": [...]
}
```

## Local Development

### Setup

```bash
# Install dependencies
pip install -r requirements-cpu.txt

# Start API server
uvicorn main:app --host 0.0.0.0 --port 8000

# Test API
python test_api.py path/to/image.jpg
```

### Streamlit Frontend

```bash
streamlit run app.py
```

## Docker Deployment

### Using Docker

```bash
# Build
docker build -t plastic-detection-api .

# Run
docker run -p 8000:8000 plastic-detection-api
```

### Using Docker Compose

```bash
# Build and start
docker-compose up --build

# Start in background
docker-compose up -d

# Stop
docker-compose down
```

## Docker Optimizations

- **Multi-stage build** - Compiles dependencies in builder stage
- **CPU-only PyTorch** - Reduces image size by ~2-3GB
- **Layer caching** - Requirements copied before source code
- **Healthcheck** - Monitors container health

---

## Cloud Deployment (OCI + Terraform)

`oci-terraform/` provisions a complete deployment on Oracle Cloud Infrastructure: VCN, subnet, internet gateway, route table, security list, and an Ubuntu 22.04 compute instance. Cloud-init then pulls the Docker image from Docker Hub and starts the container automatically. No manual SSH or `docker run` required.

### Prerequisites

- OCI account with API key configured (Console → User Settings → API Keys)
- [Terraform](https://developer.hashicorp.com/terraform/install) ≥ 1.5
- Docker Hub account, with the image already built and pushed (see [Image publishing](#image-publishing) below)
- An SSH key pair (`ssh-keygen -t ed25519` if you don't have one)

### Quick start

```bash
cd oci-terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your OCI credentials and SSH key path

terraform init
terraform apply
```

After ~7 minutes, Terraform will output:

```
api_url            = "http://<public_ip>:8000"
instance_public_ip = "<public_ip>"
ssh_command        = "ssh -i ~/.ssh/id_ed25519 ubuntu@<public_ip>"
```

The API will be reachable at `api_url`. Interactive docs at `<api_url>/docs`.

### What gets created

| Resource | Purpose |
|----------|---------|
| VCN (10.0.0.0/16) | Virtual network |
| Subnet (10.0.1.0/24) | Public subnet for the instance |
| Internet gateway | Outbound internet access |
| Route table | Routes 0.0.0.0/0 via internet gateway |
| Security list | Inbound: SSH (22), API (8000), Streamlit (8501); egress: all |
| Compute instance | VM.Standard.E2.1.Micro (AMD Always Free), Ubuntu 22.04 |

All resources are tagged with `Project=plastic-detection`, `ManagedBy=terraform`.

### Image publishing

The compute instance pulls `${var.docker_image}` from Docker Hub on first boot. Before running `terraform apply`, build and push the image (the OCI VM is AMD x86_64, so cross-compile if you're on Apple Silicon):

```bash
# From the project root
docker buildx build --platform linux/amd64 \
  -t <dockerhub-username>/plastic-detection:latest \
  --push .
```

Update `docker_image` in `terraform.tfvars` to point at your image, then run `terraform apply`.

### Updating the running deployment

To push code changes:

1. Build and push a new image (same command as above; reuse `:latest` or use a new tag).
2. Force a re-bootstrap of the VM:
   ```bash
   terraform apply -replace=module.compute.oci_core_instance.plastic_detection_instance
   ```
   This destroys and recreates only the compute instance (~2 min). Cloud-init pulls the new image and starts the container.

### Teardown

```bash
terraform destroy
```

Removes all 6 resources in dependency order.

### Project structure

```
oci-terraform/
├── main.tf          # root composition: data sources, locals, module calls
├── versions.tf      # terraform/provider version pins, provider config
├── variables.tf     # input variable declarations (with validation)
├── outputs.tf       # output declarations
├── terraform.tfvars.example
└── modules/
    ├── network/     # VCN, subnet, IGW, route table, security list
    └── compute/     # instance + cloud-init bootstrap
```
