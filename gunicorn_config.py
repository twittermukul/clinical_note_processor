"""
Gunicorn configuration file for production deployment
"""

import multiprocessing

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes (reduced for memory efficiency with docling)
workers = 2  # Limited to 2 workers due to docling's memory requirements
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 300  # Increased timeout for PDF processing
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "medical_entity_extraction"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (uncomment and configure for HTTPS)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"
