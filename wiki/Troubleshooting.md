# Troubleshooting Guide

Common issues and solutions for TerraformManager.

## Installation Issues

### Python Version Mismatch

**Problem**: `SyntaxError` or incompatibility errors

**Solution**:
```bash
python --version  # Should be 3.11+

# Use pyenv to install correct version
pyenv install 3.11.0
pyenv local 3.11.0
```

### Dependency Installation Fails

**Problem**: `pip install -r requirements.txt` fails

**Solutions**:
1. Upgrade pip:
   ```bash
   pip install --upgrade pip
   ```

2. Use virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. System dependencies missing:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install python3-dev build-essential

   # macOS
   xcode-select --install
   ```

---

## Server Issues

### Port Already in Use

**Problem**: `Address already in use: 8890`

**Solutions**:
1. Change port:
   ```bash
   export TFM_PORT=9000
   python -m api
   ```

2. Kill existing process:
   ```bash
   lsof -ti:8890 | xargs kill -9
   ```

### API Won't Start

**Problem**: API crashes on startup

**Diagnostic**:
```bash
# Check logs
export TFM_LOG_LEVEL=DEBUG
python -m api

# Common causes:
# - Missing environment variables
# - Database corruption
# - Port conflict
```

**Solutions**:
1. Reset database (DEV ONLY):
   ```bash
   rm data/app.db
   python -m api  # Recreates DB
   ```

2. Check environment:
   ```bash
   python -c "from backend.config import settings; print(settings)"
   ```

### Frontend Won't Connect to API

**Problem**: CORS errors or connection refused

**Solutions**:
1. Verify API is running:
   ```bash
   curl http://localhost:8890/health
   ```

2. Check `VITE_API_BASE`:
   ```bash
   # frontend/.env
   VITE_API_BASE=http://localhost:8890
   ```

3. Configure CORS:
   ```bash
   export TFM_ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
   ```

---

## Authentication Issues

### Login Fails

**Problem**: 401 Unauthorized or invalid credentials

**Diagnostic**:
```bash
# Test login
curl -X POST http://localhost:8890/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=test"
```

**Solutions**:
1. Verify user exists in database:
   ```bash
   sqlite3 data/app.db "SELECT email FROM users;"
   ```

2. Register new user:
   ```bash
   curl -X POST http://localhost:8890/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"test123"}'
   ```

3. Check password:
   - Minimum length requirements
   - Special character requirements

### Token Expired

**Problem**: 401 errors after initial login

**Solutions**:
1. Refresh token automatically (client-side)
2. Increase token lifetime:
   ```bash
   export TFM_ACCESS_TOKEN_MINUTES=60
   ```

3. Re-login:
   ```bash
   python -m backend.cli auth login --email you@example.com
   ```

### Cookie Not Set

**Problem**: Refresh token cookie missing

**Solutions**:
1. Development (HTTP):
   ```bash
   export TFM_COOKIE_SECURE=false
   ```

2. Production (HTTPS required):
   ```bash
   export TFM_COOKIE_SECURE=true
   # Ensure using HTTPS
   ```

3. Check browser console for cookie errors

---

## Scanning Issues

### No Terraform Files Found

**Problem**: `No .tf files found in path`

**Solutions**:
1. Verify path:
   ```bash
   ls -la path/to/terraform/*.tf
   ```

2. Use correct path:
   ```bash
   python -m backend.cli scan --path ./terraform
   ```

### HCL Parse Error

**Problem**: `Failed to parse Terraform file`

**Diagnostic**:
```bash
# Test with terraform
terraform fmt -check
terraform validate
```

**Solutions**:
1. Fix syntax errors in `.tf` files
2. Check for invalid HCL
3. Validate with Terraform CLI

### Terraform Validate Fails

**Problem**: `terraform validate` errors

**Solutions**:
1. Install Terraform CLI:
   ```bash
   # Check if installed
   terraform version

   # Install if missing
   brew install terraform  # macOS
   ```

2. Initialize Terraform:
   ```bash
   cd path/to/terraform
   terraform init
   ```

3. Skip validation:
   ```bash
   # Don't use --terraform-validate flag
   python -m backend.cli scan --path .
   ```

---

## Generator Issues

### Template Rendering Error

**Problem**: Jinja2 syntax errors

**Diagnostic**:
```bash
# Check template
cat backend/generators/template.tf.j2

# Test rendering
python -c "
from backend.generators.registry import render_generator
print(render_generator('aws/s3-secure-bucket', {'bucket_name': 'test'}))
"
```

**Solutions**:
1. Fix Jinja2 syntax
2. Verify all variables are provided
3. Check generator model schema

### Validation Fails

**Problem**: Generated code fails `terraform fmt`

**Solutions**:
1. Override validation:
   ```bash
   python -m backend.cli project generator \
     --slug aws/s3 \
     --payload data.json \
     --force-save
   ```

2. Fix template formatting
3. Run terraform fmt on template

---

## Database Issues

### Database Locked

**Problem**: `database is locked`

**Causes**:
- Multiple processes accessing SQLite
- Long-running transaction
- File system issues

**Solutions**:
1. Use PostgreSQL for multi-instance:
   ```bash
   # Replace SQLite with PostgreSQL
   export DATABASE_URL="postgresql://user:pass@host/db"
   ```

2. Stop other processes:
   ```bash
   ps aux | grep python
   kill <pid>
   ```

3. Remove lock file (if safe):
   ```bash
   rm data/app.db-journal
   ```

### Database Corrupted

**Problem**: Database integrity errors

**Solutions**:
1. Backup first:
   ```bash
   cp data/app.db data/app.db.backup
   ```

2. Try repair:
   ```bash
   sqlite3 data/app.db "PRAGMA integrity_check;"
   ```

3. Restore from backup or recreate (DEV):
   ```bash
   rm data/app.db
   python -m api  # Recreates schema
   ```

---

## Performance Issues

### Slow Scans

**Problem**: Scans taking too long

**Solutions**:
1. Disable optional features:
   ```bash
   # Skip cost analysis
   python -m backend.cli scan --path . --out report.json
   # (don't use --cost flag)
   ```

2. Reduce file count:
   ```bash
   # Scan specific subdirectory
   python -m backend.cli scan --path ./terraform/aws
   ```

3. Check disk I/O:
   ```bash
   iostat -x 1
   ```

### High Memory Usage

**Problem**: Process using too much RAM

**Solutions**:
1. Scan smaller batches
2. Increase system memory
3. Check for memory leaks:
   ```bash
   # Monitor memory
   ps aux | grep python
   ```

---

## Docker Issues

### Container Exits Immediately

**Problem**: Container starts then stops

**Diagnostic**:
```bash
docker logs tfm
```

**Solutions**:
1. Check environment variables:
   ```bash
   docker run --rm -e TFM_JWT_SECRET=test terraform-manager env
   ```

2. Verify image build:
   ```bash
   docker build -t terraform-manager:debug .
   docker run -it terraform-manager:debug /bin/bash
   ```

3. Check entrypoint:
   ```bash
   docker inspect terraform-manager:latest
   ```

### Volume Permission Errors

**Problem**: Permission denied errors

**Solutions**:
1. Fix permissions:
   ```bash
   chown -R 1000:1000 data/ knowledge/ logs/
   ```

2. Run as specific user:
   ```bash
   docker run --user 1000:1000 ...
   ```

---

## Network Issues

### CORS Errors

**Problem**: Browser blocks requests

**Diagnostic**:
```javascript
// Browser console
// Error: CORS policy: No 'Access-Control-Allow-Origin' header
```

**Solutions**:
```bash
# Add frontend origin
export TFM_ALLOWED_ORIGINS="http://localhost:5173,https://your-domain.com"

# Restart API
python -m api
```

### Proxy Issues

**Problem**: Requests fail behind proxy

**Solutions**:
1. Configure proxy environment:
   ```bash
   export HTTP_PROXY=http://proxy:8080
   export HTTPS_PROXY=http://proxy:8080
   export NO_PROXY=localhost,127.0.0.1
   ```

2. Update nginx/caddy config

---

## CLI Issues

### Command Not Found

**Problem**: `python -m backend.cli` fails

**Solutions**:
1. Activate virtual environment:
   ```bash
   source .venv/bin/activate
   ```

2. Verify installation:
   ```bash
   pip list | grep terraform
   ```

3. Reinstall:
   ```bash
   pip install -r requirements.txt
   ```

### Auth File Not Found

**Problem**: CLI can't find `tm_auth.json`

**Solutions**:
1. Login first:
   ```bash
   python -m backend.cli auth login --email you@example.com
   ```

2. Specify file location:
   ```bash
   export TM_AUTH_FILE=/path/to/auth.json
   ```

---

## Knowledge Base Issues

### Search Returns No Results

**Problem**: Knowledge search not finding docs

**Solutions**:
1. Reindex knowledge base:
   ```bash
   python -m backend.cli reindex
   ```

2. Check knowledge directory:
   ```bash
   ls -la knowledge/*.md
   ```

3. Verify TF-IDF index:
   ```bash
   python -c "
   from backend.rag import warm_index
   warm_index()
   print('Index rebuilt')
   "
   ```

### Sync Fails

**Problem**: GitHub sync errors

**Solutions**:
1. Verify repo URL:
   ```bash
   git clone <repo-url>
   ```

2. Check network:
   ```bash
   curl -I https://github.com
   ```

3. Provide access token (private repos):
   ```bash
   # Include token in URL
   https://token@github.com/user/repo
   ```

---

## Getting More Help

### Enable Debug Logging

```bash
export TFM_LOG_LEVEL=DEBUG
export TFM_SQL_ECHO=1
python -m api
```

### Check System Info

```bash
# Python version
python --version

# Installed packages
pip list

# System info
uname -a

# Disk space
df -h

# Memory
free -h
```

### Collect Logs

```bash
# API logs
cat logs/terraform-manager.log

# Service manager logs
cat logs/api-service.log

# Docker logs
docker logs tfm > docker.log 2>&1
```

### Report Issues

When reporting bugs, include:
1. TerraformManager version
2. Python version
3. Operating system
4. Error messages and stack traces
5. Steps to reproduce
6. Relevant logs (DEBUG level)

**GitHub Issues**: https://github.com/ilyafedotov-ops/TerraformManager/issues

---

## Next Steps

- [Configuration Reference](Configuration) - Environment variables
- [Getting Started](Getting-Started) - Setup guide
- [Development Guide](Development) - Contributing
- [Deployment Guide](Deployment) - Production deployment
