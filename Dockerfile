FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgdal-dev \
    gdal-bin \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    ffmpeg \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first
COPY requirements.txt .

# Install dependencies in stages to reduce memory usage
RUN pip install --no-cache-dir --upgrade pip

# Install lighter dependencies first
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn==0.24.0 \
    gunicorn==21.2.0 \
    python-multipart==0.0.6 \
    aiofiles==23.2.1 \
    python-magic==0.4.27 \
    jinja2==3.1.2 \
    python-dotenv==1.0.0 \
    pydantic==2.9.0 \
    sqlalchemy==2.0.23 \
    passlib[bcrypt]==1.7.4 \
    python-jose[cryptography]==3.3.0 \
    psutil==5.9.6

# Install image processing libraries
RUN pip install --no-cache-dir \
    pillow==10.4.0 \
    opencv-python-headless==4.8.1.78 \
    numpy==1.26.4

# Install reporting libraries
RUN pip install --no-cache-dir \
    reportlab==4.0.7 \
    openpyxl==3.1.2

# Install PyTorch separately (biggest memory consumer)
# Use CPU-only version to reduce size
RUN pip install --no-cache-dir \
    torch==2.6.0+cpu \
    torchvision==0.21.0+cpu \
    torchaudio==2.6.0+cpu \
    -f https://download.pytorch.org/whl/torch_stable.html

# Install ultralytics last
RUN pip install --no-cache-dir ultralytics==8.1.0

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p data/analizler models static templates backups && \
    chmod -R 755 data models backups

# Download model if needed
RUN if [ ! -f models/yolov8n.pt ]; then \
    wget -q https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt -O models/yolov8n.pt; \
    fi

EXPOSE 8000

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--timeout", "300", "app.main:app"]