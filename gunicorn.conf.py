# Gunicorn yapılandırma dosyası

# Sunucu socket
bind = "0.0.0.0:8000"

# Worker ayarları
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Timeout ayarları
timeout = 300
keepalive = 5
graceful_timeout = 30

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process ayarları
preload_app = True
daemon = False
pidfile = "/tmp/gunicorn.pid"
user = 1000
group = 1000
tmp_upload_dir = None

# SSL ayarları (gerekirse)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Worker restart ayarları
max_worker_memory = 2048  # MB
worker_tmp_dir = "/dev/shm"

def when_ready(server):
    server.log.info("Zeytin Ağacı Analiz Sistemi başlatılıyor...")

def worker_int(worker):
    worker.log.info("Worker interrupted")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    worker.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker aborted (pid: %s)", worker.pid)