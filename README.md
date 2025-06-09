# VPS Automation Server

Production-ready automation server for Swedish driving test booking with real-time QR code streaming and multi-browser support.

## 🚀 Features

- **Multi-User Concurrency**: Handle 10+ simultaneous booking jobs
- **Real-Time QR Streaming**: Capture and stream BankID QR codes to frontend
- **Multi-Browser Support**: Chromium, Firefox, WebKit with automatic fallback
- **Production Queue System**: Redis + Celery with job prioritization
- **Comprehensive Monitoring**: Health checks, metrics, and structured logging
- **Docker Deployment**: Production-ready containerization
- **Webhook Integration**: Real-time communication with Supabase backend

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │───▶│   FastAPI App    │───▶│   Celery Queue  │
│   (Next.js)     │    │   (API Server)   │    │   (Background)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         │                        ▼                        ▼
         │              ┌──────────────────┐    ┌─────────────────┐
         │              │   Redis Cache    │    │  Playwright     │
         │              │   (State/Queue)  │    │  (Browsers)     │
         │              └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Supabase      │◀───│   Webhooks       │◀───│   QR Capture    │
│   (Database)    │    │   (Notifications)│    │   (Streaming)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📋 Prerequisites

- **OS**: Ubuntu 22.04 LTS (recommended)
- **Memory**: 8GB RAM minimum, 16GB recommended
- **CPU**: 4+ cores recommended for concurrent jobs
- **Storage**: 50GB+ SSD for browser cache and logs
- **Network**: Stable internet connection
- **Domain**: For SSL/TLS certificate (production)

## 🛠️ Installation

### Option 1: Docker Deployment (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd vps-automation-server
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   nano .env
   ```

3. **Deploy with Docker Compose**
   ```bash
   # Basic deployment
   docker-compose up -d
   
   # Production with monitoring
   docker-compose --profile monitoring up -d
   
   # Full production with nginx
   docker-compose --profile production --profile monitoring up -d
   ```

### Option 2: Manual Installation

1. **System setup**
   ```bash
   chmod +x scripts/setup.sh
   sudo ./scripts/setup.sh
   ```

2. **Install dependencies**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Install browsers**
   ```bash
   playwright install-deps
   playwright install chromium firefox webkit
   ```

4. **Configure services**
   ```bash
   # Copy environment config
   cp .env.example .env
   
   # Start Redis
   sudo systemctl start redis-server
   
   # Start application
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   
   # Start workers (separate terminal)
   celery -A app.workers.celery_app worker --loglevel=info
   ```

## ⚙️ Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# Required Settings
API_SECRET_TOKEN=your-secret-api-token
SUPABASE_WEBHOOK_URL=https://your-project.supabase.co/rest/v1/webhook
SUPABASE_SECRET_KEY=your-supabase-secret
WEBHOOK_SECRET=your-webhook-secret

# Performance Tuning
MAX_CONCURRENT_JOBS=10
WORKER_CONCURRENCY=5
BROWSER_HEADLESS=true
MAX_BROWSER_INSTANCES=10

# Security
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
```

### Browser Configuration

The system supports multiple browsers with automatic fallback:

1. **Chromium** (Primary) - Best performance and compatibility
2. **Firefox** (Fallback) - Alternative for detection avoidance  
3. **WebKit** (Last resort) - Safari engine compatibility

## 📚 API Documentation

### Authentication

All API endpoints require Bearer token authentication:

```bash
curl -H "Authorization: Bearer your-api-token" \
     https://your-domain.com/api/v1/booking/start
```

### Core Endpoints

#### Start Booking Job
```http
POST /api/v1/booking/start
Content-Type: application/json
Authorization: Bearer <token>

{
  "user_id": "user-123",
  "license_type": "B",
  "exam_type": "Körprov",
  "locations": ["Stockholm", "Uppsala"],
  "date_ranges": [
    {"start": "2024-02-01", "end": "2024-02-15"}
  ],
  "webhook_url": "https://your-app.com/webhook",
  "auto_book": true,
  "priority": "normal"
}
```

#### Check Job Status
```http
GET /api/v1/booking/status/{job_id}
Authorization: Bearer <token>
```

#### Cancel Job
```http
POST /api/v1/booking/cancel/{job_id}
Content-Type: application/json
Authorization: Bearer <token>

{
  "reason": "User requested cancellation",
  "force": false
}
```

#### System Health
```http
GET /health/detailed
```

### Webhook Events

The system sends real-time updates via webhooks:

#### QR Code Update
```json
{
  "event_type": "qr_code_update",
  "job_id": "job_123",
  "user_id": "user_123",
  "timestamp": "2024-01-01T10:00:00Z",
  "data": {
    "qr_code_data": "data:image/png;base64,iVBORw0KGgo...",
    "retry_count": 1
  }
}
```

#### Status Update
```json
{
  "event_type": "status_update",
  "job_id": "job_123", 
  "user_id": "user_123",
  "timestamp": "2024-01-01T10:00:00Z",
  "data": {
    "status": "authenticating",
    "message": "Waiting for BankID authentication",
    "progress": 25.0
  }
}
```

#### Booking Completion
```json
{
  "event_type": "booking_completed",
  "job_id": "job_123",
  "user_id": "user_123", 
  "timestamp": "2024-01-01T10:30:00Z",
  "data": {
    "success": true,
    "booking_result": {
      "booking_id": "TV123456789",
      "confirmation_number": "ABC123XYZ",
      "exam_date": "2024-01-20",
      "exam_time": "10:30",
      "location": "Stockholm Bilprovning"
    }
  }
}
```

## 🔍 Monitoring

### Health Checks

- **Basic**: `GET /health` - Simple health status
- **Detailed**: `GET /health/detailed` - Comprehensive system metrics
- **Webhook**: `GET /webhooks/health` - Webhook system status

### Metrics (Prometheus)

Available at `http://localhost:9091` when monitoring is enabled:

- Job completion rates
- Browser resource usage
- Queue lengths and processing times
- Error rates by type
- System resource utilization

### Logging

Structured JSON logging with correlation IDs:

```json
{
  "timestamp": "2024-01-01T10:00:00Z",
  "level": "INFO",
  "logger": "app.automation.playwright_driver",
  "message": "Browser initialized successfully",
  "user_id": "user_123",
  "job_id": "job_123",
  "browser_type": "chromium"
}
```

### Flower Dashboard

Celery task monitoring at `http://localhost:5555`:
- Active/pending/failed tasks
- Worker status and performance
- Task routing and queues
- Real-time task execution

## 🚀 Deployment

### Production Checklist

- [ ] Configure SSL certificates
- [ ] Set strong secrets in `.env`
- [ ] Configure firewall rules
- [ ] Set up log rotation
- [ ] Configure backup procedures
- [ ] Set resource limits
- [ ] Configure monitoring alerts

### Docker Production

```bash
# Build and deploy
docker-compose --profile production --profile monitoring up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f web worker

# Scale workers
docker-compose up -d --scale worker=3
```

### Nginx Configuration

Example nginx configuration for SSL termination:

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.key;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🛡️ Security

### API Security
- Bearer token authentication
- Rate limiting (100 req/min by default)
- CORS protection
- Input validation and sanitization

### Infrastructure Security  
- Container security (no-new-privileges)
- Resource limits and isolation
- Webhook signature verification
- Secure defaults and hardening

### Browser Security
- Anti-detection measures
- User agent rotation
- Geolocation spoofing
- Cookie and session isolation

## 🐛 Troubleshooting

### Common Issues

**Browser fails to start**
```bash
# Check browser dependencies
playwright install-deps

# Verify shared memory
df -h /dev/shm

# Check container memory limits
docker stats
```

**Queue jobs stuck**
```bash
# Check Redis connection
redis-cli ping

# Restart workers
docker-compose restart worker

# Clear queue
celery -A app.workers.celery_app purge
```

**High memory usage**
```bash
# Check browser instances
curl localhost:8000/api/v1/status/browser-sessions

# Trigger cleanup
curl -X POST localhost:8000/api/v1/status/maintenance/cleanup
```

### Log Analysis

```bash
# Container logs
docker-compose logs -f web worker

# Application logs (if using file logging)
tail -f /app/logs/application.log | jq

# System metrics
docker stats --no-stream
```

## 📊 Performance Tuning

### Resource Allocation

**Memory**: 512MB per browser instance + 256MB base
**CPU**: 0.5 cores per concurrent job
**Storage**: 100MB per job for cache/screenshots

### Scaling Guidelines

- **10 concurrent users**: 2 worker containers, 8GB RAM
- **25 concurrent users**: 4 worker containers, 16GB RAM  
- **50 concurrent users**: 8 worker containers, 32GB RAM

### Optimization

```bash
# Increase worker concurrency
WORKER_CONCURRENCY=8

# Optimize browser resource usage
MAX_BROWSER_INSTANCES=15
BROWSER_MEMORY_LIMIT=256MB

# Tune Redis
maxmemory 2gb
maxmemory-policy allkeys-lru
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

[Add license information]

## 🆘 Support

For issues and questions:
- Check the troubleshooting section
- Review application logs
- Monitor system metrics
- Contact support team

---

**Built with**: FastAPI, Playwright, Celery, Redis, Docker 