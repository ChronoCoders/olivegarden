# Stage 1: Build
FROM python:3.10-slim AS builder

# Sistemdeki paket listesi güncellensin ve GDAL gibi C-kütüphaneleri yüklensin
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      gdal-bin libgdal-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Sadece requirements dosyasını kopyalayıp bağımlılıkları kur
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.10-slim

# Sistem bağımlılıkları yine yükleniyor (yalnızca runtime için)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      gdal-bin libgdal-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Sadece user-level pip dizinini PYTHONPATH'e ekleyin
ENV PATH=/root/.local/bin:$PATH

# Uygulama kodunu kopyala
COPY --from=builder /root/.local /root/.local
COPY . .

# Çalıştırma komutu
CMD ["gunicorn", "-c", "gunicorn.conf.py", "main:app"]
