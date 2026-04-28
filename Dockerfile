# Use stable slim Python image
FROM python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies (for OpenCV / YOLO)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements-cpu.txt .

# Upgrade pip + install dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements-cpu.txt

# Copy application code
COPY main.py .
COPY model.py .
COPY service.py .
COPY utils.py .
COPY app.py .

# Ensure model directory exists, then copy weights
RUN mkdir -p runs/detect/train/weights
COPY runs/detect/train/weights/best.pt runs/detect/train/weights/

# Expose API port
EXPOSE 8000

# Run FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]