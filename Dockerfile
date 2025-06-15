### Dockerfile (use Python 3.12 to ensure prebuilt NumPy wheels)
# Use official slim Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy and install dependencies
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
