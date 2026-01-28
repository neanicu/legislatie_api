# Deployment Guide

This guide covers deployment options for the Romanian Legislative API Client.

## Table of Contents

1. [Docker Deployment](#docker-deployment)
2. [Virtual Environment Deployment](#virtual-environment-deployment)
3. [Cloud Deployment](#cloud-deployment)
   - [Heroku](#heroku)
   - [AWS Elastic Beanstalk](#aws-elastic-beanstalk)
   - [Google Cloud Run](#google-cloud-run)
4. [Environment Configuration](#environment-configuration)
5. [Monitoring & Logging](#monitoring--logging)
6. [Scaling Considerations](#scaling-considerations)

---

## Docker Deployment

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- Git

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/legislatie_api.git
cd legislatie_api

# Build and run with Docker Compose
docker compose up --build
```

The application will be available at `http://localhost:8501`.

### Production Deployment

For production, use the production profile:

```bash
# Build production image
docker build -t legislatie-api:latest .

# Run with environment variables
docker run -d \
  --name legislatie-api \
  -p 8501:8501 \
  -v legislatie-cache:/app/.legislatie_cache \
  -e LEGISLATIE_USE_PERSISTENT_CACHE=true \
  -e LEGISLATIE_LOG_LEVEL=INFO \
  legislatie-api:latest
```

### Docker Compose Profiles

The project includes multiple Docker Compose profiles:

- **Production**: `docker compose --profile production up`
- **Development**: `docker compose --profile development up`
- **Testing**: `docker compose --profile test up`
- **Monitoring**: `docker compose --profile monitoring up`

### Health Checks

The container includes a health check that validates all system components:

```bash
# Manual health check
docker exec legislatie-api python legislatie_client.py --health

# View container health status
docker inspect --format='{{.State.Health.Status}}' legislatie-api
```

---

## Virtual Environment Deployment

### Prerequisites
- Python 3.7+
- pip
- virtualenv (optional)

### Step-by-Step Deployment

```bash
# 1. Clone repository
git clone https://github.com/yourusername/legislatie_api.git
cd legislatie_api

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env
# Edit .env with your settings

# 6. Run the Streamlit app
streamlit run streamlit_app.py

# 7. Run as a service (using systemd)
# Create service file: /etc/systemd/system/legislatie-api.service
```

### Systemd Service File

Create `/etc/systemd/system/legislatie-api.service`:

```ini
[Unit]
Description=Romanian Legislative API Client
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/legislatie_api
Environment="PATH=/opt/legislatie_api/venv/bin"
ExecStart=/opt/legislatie_api/venv/bin/streamlit run streamlit_app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Nginx Reverse Proxy (Optional)

```nginx
server {
    listen 80;
    server_name legislatie.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Cloud Deployment

### Heroku

#### Prerequisites
- Heroku CLI
- Git

#### Deployment Steps

```bash
# 1. Login to Heroku
heroku login

# 2. Create Heroku app
heroku create legislatie-api

# 3. Set environment variables
heroku config:set LEGISLATIE_USE_PERSISTENT_CACHE=false
heroku config:set LEGISLATIE_LOG_LEVEL=INFO

# 4. Deploy
git push heroku main

# 5. Open application
heroku open
```

#### Procfile

Create `Procfile` in project root:

```procfile
web: streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true
```

#### Heroku-specific Considerations
- Use memory cache (persistent cache not available on ephemeral filesystem)
- Set appropriate timeout values for Heroku's 30-second limit
- Use Heroku Redis for caching if needed

### AWS Elastic Beanstalk

#### Prerequisites
- AWS CLI
- EB CLI

#### Deployment Steps

```bash
# 1. Initialize EB application
eb init -p python-3.9 legislatie-api

# 2. Create environment
eb create legislatie-api-env

# 3. Configure environment variables
eb setenv LEGISLATIE_USE_PERSISTENT_CACHE=true LEGISLATIE_LOG_LEVEL=INFO

# 4. Deploy
eb deploy

# 5. Open application
eb open
```

#### Configuration Files

Create `.ebextensions/01-streamlit.config`:

```yaml
option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: streamlit_app.py
    NumProcesses: 1
    NumThreads: 15
  aws:elasticbeanstalk:application:environment:
    PYTHONPATH: /var/app/current
```

### Google Cloud Run

#### Prerequisites
- Google Cloud SDK
- Docker

#### Deployment Steps

```bash
# 1. Build Docker image
gcloud builds submit --tag gcr.io/PROJECT-ID/legislatie-api

# 2. Deploy to Cloud Run
gcloud run deploy legislatie-api \
  --image gcr.io/PROJECT-ID/legislatie-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="LEGISLATIE_USE_PERSISTENT_CACHE=false"

# 3. Get deployment URL
gcloud run services describe legislatie-api --platform managed --region us-central1 --format='value(status.url)'
```

#### Cloud Run Considerations
- Use in-memory caching (no persistent storage)
- Set memory limit (512MB recommended)
- Configure concurrency appropriately

---

## Environment Configuration

### Required Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LEGISLATIE_WSDL_URL` | SOAP API WSDL URL | `https://legislatie.just.ro/apiws/FreeWebService.svc?wsdl` | No |
| `LEGISLATIE_SOAP_ENDPOINT` | SOAP endpoint | `https://legislatie.just.ro/apiws/FreeWebService.svc/SOAP` | No |
| `LEGISLATIE_BASE_URL` | Base URL for scraping | `https://legislatie.just.ro` | No |
| `LEGISLATIE_REQUEST_DELAY` | Delay between requests (seconds) | `1.0` | No |
| `LEGISLATIE_MAX_RETRIES` | Max retry attempts | `3` | No |
| `LEGISLATIE_CACHE_TTL` | Cache TTL (seconds) | `3600` | No |
| `LEGISLATIE_USE_PERSISTENT_CACHE` | Use disk cache | `false` | No |
| `LEGISLATIE_LOG_LEVEL` | Logging level | `INFO` | No |

### Production Configuration Example

```bash
# .env.production
LEGISLATIE_USE_PERSISTENT_CACHE=true
LEGISLATIE_CACHE_TTL=86400  # 24 hours
LEGISLATIE_LOG_LEVEL=WARNING
LEGISLATIE_REQUEST_DELAY=1.5  # Be polite to server
LEGISLATIE_MAX_RETRIES=5
```

### Security Considerations

1. **Never commit `.env` files** to version control
2. Use secret management services:
   - AWS: Secrets Manager
   - GCP: Secret Manager
   - Heroku: Config Vars
3. Rotate API keys and tokens regularly
4. Implement rate limiting for public deployments

---

## Monitoring & Logging

### Built-in Health Checks

The application includes comprehensive health monitoring:

```bash
# Run health check
python legislatie_client.py --health

# Output format:
{
  "overall": "healthy",
  "timestamp": "2024-01-01T12:00:00",
  "soap_api": {
    "status": "healthy",
    "details": "Token obtained successfully",
    "response_time": 1.23
  },
  "scraper": {
    "status": "healthy",
    "details": "Search completed successfully",
    "response_time": 2.45
  },
  "cache": {
    "status": "healthy",
    "details": "Cache operational",
    "response_time": 0.01
  }
}
```

### Logging Configuration

Logs are written to both console and file (`legislatie.log` by default).

```python
# Configure logging level
export LEGISLATIE_LOG_LEVEL=DEBUG

# Change log file location
export LEGISLATIE_LOG_FILE=/var/log/legislatie/api.log
```

### External Monitoring Services

- **Datadog**: Monitor application metrics
- **New Relic**: Performance monitoring
- **Sentry**: Error tracking
- **Prometheus + Grafana**: Self-hosted monitoring

### Alerting

Set up alerts for:
- SOAP API downtime (> 5 minutes)
- Scraper failure rate > 10%
- Cache hit rate < 50%
- Response time > 10 seconds

---

## Scaling Considerations

### Vertical Scaling

1. **Increase memory**: Cache more search results
2. **Increase CPU**: Handle more concurrent requests
3. **Use SSD storage**: Faster cache access

### Horizontal Scaling

1. **Load balancer**: Distribute traffic across multiple instances
2. **Shared cache**: Use Redis or Memcached instead of local cache
3. **Database**: Store results in PostgreSQL for persistence

### Caching Strategy

| Cache Level | TTL | Storage | Use Case |
|-------------|-----|---------|----------|
| Memory | 5 minutes | RAM | Hot searches |
| Disk | 24 hours | SSD | Common searches |
| Distributed | 7 days | Redis | Shared across instances |

### Performance Optimization

1. **Enable gzip compression** for HTML responses
2. **Implement request coalescing** for identical concurrent searches
3. **Use connection pooling** for HTTP requests
4. **Implement request queuing** during high load

### Cost Optimization

1. **Use spot instances** for non-critical deployments
2. **Implement cache warming** during off-peak hours
3. **Monitor and optimize** cache hit rate
4. **Use CDN** for static assets

---

## Troubleshooting

### Common Issues

#### 1. "Unable to connect to the remote server"
- **Cause**: SOAP API internal Solr error
- **Solution**: System automatically falls back to HTML scraping

#### 2. High memory usage
- **Cause**: Large cache accumulation
- **Solution**: Reduce `CACHE_TTL` or implement cache eviction

#### 3. Slow response times
- **Cause**: Network latency or server load
- **Solution**: Increase caching, implement CDN

#### 4. Character encoding issues
- **Cause**: UTF-8 configuration
- **Solution**: Ensure all components use UTF-8

### Debug Mode

Enable debug mode for detailed troubleshooting:

```bash
export LEGISLATIE_LOG_LEVEL=DEBUG
python legislatie_client.py --health
```

### Support

For additional support:
1. Check logs: `tail -f legislatie.log`
2. Run tests: `pytest tests/ -v`
3. Create issue on GitHub repository
4. Contact maintainers

---

## Updates & Maintenance

### Regular Maintenance Tasks

1. **Weekly**: Clear expired cache entries
2. **Monthly**: Update dependencies (`pip install -U -r requirements.txt`)
3. **Quarterly**: Review security settings
4. **Annually**: Archive old logs

### Backup Strategy

1. **Configuration**: Version control `.env.example`
2. **Cache**: Optional backup of cache directory
3. **Logs**: Rotate and archive logs monthly
4. **Database**: If using external storage, regular backups

### Upgrade Procedure

```bash
# 1. Backup current deployment
# 2. Pull latest changes
git pull origin main
# 3. Update dependencies
pip install -r requirements.txt --upgrade
# 4. Run tests
pytest tests/ -v
# 5. Restart service
systemctl restart legislatie-api
```

---

*Last updated: $(date)*