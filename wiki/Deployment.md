# Deployment Guide

Guide for deploying TerraformManager in production environments.

## Deployment Options

1. **Docker** - Single-container deployment
2. **Docker Compose** - Multi-container with volumes
3. **Kubernetes** - Scalable container orchestration
4. **Systemd** - Traditional Linux service
5. **Cloud Platforms** - AWS/Azure/GCP

---

## Docker Deployment

### Build Image

```bash
docker build -t terraform-manager:latest .
```

### Run Container

```bash
docker run -d \
  --name tfm \
  -p 8890:8890 \
  -e TFM_PORT=8890 \
  -e TFM_JWT_SECRET=your-secure-secret \
  -e TFM_COOKIE_SECURE=true \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/knowledge:/app/knowledge \
  -v $(pwd)/logs:/app/logs \
  terraform-manager:latest
```

### Environment Variables

See [Configuration Reference](Configuration) for all options. Minimum required:

```bash
-e TFM_JWT_SECRET=<secure-random-secret>
-e TFM_REFRESH_SECRET=<different-secure-secret>
-e TFM_COOKIE_SECURE=true
-e TFM_ALLOWED_ORIGINS=https://your-domain.com
```

### Health Check

```bash
docker run \
  --health-cmd="curl -f http://localhost:8890/health || exit 1" \
  --health-interval=30s \
  --health-timeout=3s \
  --health-retries=3 \
  # ... other options
```

---

## Docker Compose

### docker-compose.yml

```yaml
version: '3.8'

services:
  tfm:
    image: terraform-manager:latest
    build: .
    ports:
      - "8890:8890"
    environment:
      TFM_PORT: 8890
      TFM_JWT_SECRET: ${TFM_JWT_SECRET}
      TFM_REFRESH_SECRET: ${TFM_REFRESH_SECRET}
      TFM_COOKIE_SECURE: "true"
      TFM_COOKIE_DOMAIN: ${DOMAIN}
      TFM_ALLOWED_ORIGINS: https://${DOMAIN}
      TFM_LOG_LEVEL: INFO
    volumes:
      - ./data:/app/data
      - ./knowledge:/app/knowledge
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8890/health"]
      interval: 30s
      timeout: 3s
      retries: 3
```

### .env File

```bash
# Secrets (DO NOT COMMIT)
TFM_JWT_SECRET=your-secure-jwt-secret
TFM_REFRESH_SECRET=your-refresh-secret

# Domain
DOMAIN=tfm.example.com
```

### Deploy

```bash
docker compose up -d
```

### View Logs

```bash
docker compose logs -f tfm
```

### Update

```bash
docker compose pull
docker compose up -d
```

---

## Kubernetes Deployment

### Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: terraform-manager
```

### Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: tfm-secrets
  namespace: terraform-manager
type: Opaque
stringData:
  jwt-secret: your-secure-jwt-secret
  refresh-secret: your-refresh-secret
```

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tfm-config
  namespace: terraform-manager
data:
  TFM_PORT: "8890"
  TFM_LOG_LEVEL: "INFO"
  TFM_COOKIE_SECURE: "true"
  TFM_ALLOWED_ORIGINS: "https://tfm.example.com"
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: terraform-manager
  namespace: terraform-manager
spec:
  replicas: 2
  selector:
    matchLabels:
      app: terraform-manager
  template:
    metadata:
      labels:
        app: terraform-manager
    spec:
      containers:
      - name: tfm
        image: terraform-manager:latest
        ports:
        - containerPort: 8890
        env:
        - name: TFM_PORT
          valueFrom:
            configMapKeyRef:
              name: tfm-config
              key: TFM_PORT
        - name: TFM_JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: tfm-secrets
              key: jwt-secret
        - name: TFM_REFRESH_SECRET
          valueFrom:
            secretKeyRef:
              name: tfm-secrets
              key: refresh-secret
        envFrom:
        - configMapRef:
            name: tfm-config
        volumeMounts:
        - name: data
          mountPath: /app/data
        - name: knowledge
          mountPath: /app/knowledge
        livenessProbe:
          httpGet:
            path: /health
            port: 8890
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8890
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: tfm-data
      - name: knowledge
        persistentVolumeClaim:
          claimName: tfm-knowledge
```

### PersistentVolumeClaims

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: tfm-data
  namespace: terraform-manager
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: tfm-knowledge
  namespace: terraform-manager
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: terraform-manager
  namespace: terraform-manager
spec:
  selector:
    app: terraform-manager
  ports:
  - port: 80
    targetPort: 8890
  type: ClusterIP
```

### Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: terraform-manager
  namespace: terraform-manager
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - tfm.example.com
    secretName: tfm-tls
  rules:
  - host: tfm.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: terraform-manager
            port:
              number: 80
```

---

## Systemd Service

### Service File

`/etc/systemd/system/terraform-manager.service`:

```ini
[Unit]
Description=TerraformManager API
After=network.target

[Service]
Type=simple
User=tfm
Group=tfm
WorkingDirectory=/opt/terraform-manager
EnvironmentFile=/etc/terraform-manager/config.env
ExecStart=/opt/terraform-manager/.venv/bin/python -m api
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/var/log/terraform-manager/stdout.log
StandardError=append:/var/log/terraform-manager/stderr.log

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/terraform-manager/data /var/log/terraform-manager

[Install]
WantedBy=multi-user.target
```

### Environment File

`/etc/terraform-manager/config.env`:

```bash
TFM_PORT=8890
TFM_JWT_SECRET=your-secure-secret
TFM_REFRESH_SECRET=your-refresh-secret
TFM_COOKIE_SECURE=true
TFM_ALLOWED_ORIGINS=https://tfm.example.com
TFM_LOG_DIR=/var/log/terraform-manager
```

### Setup

```bash
# Create user
sudo useradd -r -s /bin/false tfm

# Create directories
sudo mkdir -p /opt/terraform-manager /var/log/terraform-manager
sudo chown tfm:tfm /opt/terraform-manager /var/log/terraform-manager

# Install application
sudo -u tfm git clone https://github.com/user/TerraformManager.git /opt/terraform-manager
cd /opt/terraform-manager
sudo -u tfm python -m venv .venv
sudo -u tfm .venv/bin/pip install -r requirements.txt

# Install service
sudo cp terraform-manager.service /etc/systemd/system/
sudo chmod 600 /etc/terraform-manager/config.env
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable terraform-manager
sudo systemctl start terraform-manager

# Check status
sudo systemctl status terraform-manager
```

---

## Reverse Proxy

### Nginx

```nginx
upstream tfm_backend {
    server localhost:8890;
}

server {
    listen 80;
    server_name tfm.example.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tfm.example.com;

    ssl_certificate /etc/letsencrypt/live/tfm.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tfm.example.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/tfm-access.log;
    error_log /var/log/nginx/tfm-error.log;

    location / {
        proxy_pass http://tfm_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### Caddy

```
tfm.example.com {
    reverse_proxy localhost:8890

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Frame-Options "SAMEORIGIN"
        X-Content-Type-Options "nosniff"
        X-XSS-Protection "1; mode=block"
    }

    log {
        output file /var/log/caddy/tfm.log
    }
}
```

---

## Production Checklist

### Security

- [ ] Change `TFM_JWT_SECRET` and `TFM_REFRESH_SECRET`
- [ ] Set `TFM_COOKIE_SECURE=true`
- [ ] Configure `TFM_ALLOWED_ORIGINS`
- [ ] Enable HTTPS/TLS
- [ ] Use `TFM_COOKIE_SAMESITE=strict`
- [ ] Set up firewall rules
- [ ] Configure `TFM_TRUSTED_HOSTS`

### Database

- [ ] Backup `data/app.db` regularly
- [ ] Consider PostgreSQL for multi-server
- [ ] Set appropriate file permissions
- [ ] Monitor database size

### Logging

- [ ] Configure log aggregation
- [ ] Set `TFM_LOG_LEVEL=INFO`
- [ ] Set up log rotation
- [ ] Monitor error rates

### Monitoring

- [ ] Set up health checks
- [ ] Monitor API response times
- [ ] Track authentication failures
- [ ] Alert on errors

### Backup

- [ ] Backup `data/` directory
- [ ] Backup `knowledge/` directory
- [ ] Backup environment configuration
- [ ] Test restore procedure

### Performance

- [ ] Configure resource limits
- [ ] Enable HTTP/2
- [ ] Use CDN for static assets
- [ ] Implement caching headers

---

## Scaling

### Horizontal Scaling

1. **Shared Database**: Migrate to PostgreSQL/MySQL
2. **Shared Storage**: Use NFS/S3 for `data/projects`
3. **Load Balancer**: Distribute traffic across instances
4. **Session Store**: Use Redis for sessions (future)

### Database Migration

```python
# config.py - Switch to PostgreSQL
DATABASE_URL = "postgresql://user:pass@host:5432/tfm"
```

### Shared Storage (S3)

```python
# Configure S3 backend for project files
PROJECTS_ROOT = "s3://bucket-name/projects"
```

---

## Monitoring & Observability

### Prometheus Metrics (Future)

```python
from prometheus_client import Counter, Histogram

scan_requests = Counter('tfm_scan_requests_total', 'Total scans')
scan_duration = Histogram('tfm_scan_duration_seconds', 'Scan duration')
```

### Health Check Endpoint

```bash
curl http://localhost:8890/health
```

### Log Aggregation

**Fluent Bit** → Elasticsearch:

```conf
[INPUT]
    Name tail
    Path /var/log/terraform-manager/*.log
    Parser json

[OUTPUT]
    Name es
    Host elasticsearch
    Port 9200
    Index tfm-logs
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs tfm

# Common issues:
# - Missing environment variables
# - Port already in use
# - Volume permission errors
```

### Permission Errors

```bash
# Fix volume permissions
chown -R 1000:1000 data/ knowledge/ logs/
```

### Database Locked

```bash
# SQLite lock (multi-container)
# Solution: Use PostgreSQL for multi-instance
```

---

## Next Steps

- [Configuration Reference](Configuration) - Environment variables
- [Architecture Overview](Architecture) - System design
- [Troubleshooting](Troubleshooting) - Common issues
- [Getting Started](Getting-Started) - Quick setup
