### Dockerfile (CPU-only)
# Use official slim Python base image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies (including PyTorch CPU wheels)
COPY requirements.txt .
RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

# Copy application source
COPY . .

# Expose port (adjust if needed)
EXPOSE 8000

# Default command to run the app via Gunicorn
CMD ["gunicorn", "main:app", "--config", "gunicorn.conf.py"]
