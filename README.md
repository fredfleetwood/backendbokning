# 🚗 Booking Automation Backend (VPS Server)

## 🎯 Overview

This is the VPS backend component of the booking automation system. It provides browser automation, QR code generation, and real-time status updates for driving test booking automation.

## 🏗️ Architecture

```
VPS Server (FastAPI + Playwright) → Trafikverket Website
         ↓                              ↓
   Browser Automation                BankID QR Codes
   Redis Cache                       Booking Forms  
   Webhook Callbacks                 Time Slots
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Redis Server  
- X11 Server (for browser automation)
- VNC Server (for remote viewing)

### Installation
```bash
# Clone repository
git clone https://github.com/fredfleetwood/backendbokning.git
cd backendbokning

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start Redis (if not running)
redis-server &

# Start VNC Server for browser automation
Xvnc :99 -geometry 1024x768 -depth 24 -rfbport 5999 -desktop "BookingAutomation" -alwaysshared &

# Start VNC Web Interface
websockify --web=/usr/share/novnc 8082 127.0.0.1:5999 &

# Start window manager
export DISPLAY=:99 && fluxbox > /dev/null 2>&1 &

# Start the server
uvicorn app.main_production:app --host 0.0.0.0 --port 8000
```

## 📡 API Endpoints

### Core Endpoints:
- `GET /health` - Health check
- `POST /api/v1/booking/start` - Start booking automation
- `GET /api/v1/booking/status/{job_id}` - Get job status
- **`GET /api/v1/booking/{job_id}/qr`** - **CRITICAL**: Get QR code

### Authentication:
All endpoints require: `Authorization: Bearer test-secret-token-12345`

### Example Usage:
```bash
# Start booking
curl -X POST http://87.106.247.92:8000/api/v1/booking/start \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-secret-token-12345" \
  -d '{
    "job_id": "job-123",
    "config": {
      "license_type": "B",
      "exam": "Körprov",
      "locations": ["Stockholm"],
      "webhook_url": "https://your-webhook.com/callback"
    }
  }'

# Get QR code (CRITICAL ENDPOINT)
curl http://87.106.247.92:8000/api/v1/booking/job-123/qr \
  -H "Authorization: Bearer test-secret-token-12345"
```

## 🔧 Service Management

### Port Configuration:
- **8000**: FastAPI Server
- **8082**: VNC Web Interface
- **5999**: VNC Server (RFB)
- **6379**: Redis Server

### Service Commands:
```bash
# Start all services
./start_services.sh  # If available

# Or manually:
cd backend && source venv/bin/activate
uvicorn app.main_production:app --host 0.0.0.0 --port 8000 &
Xvnc :99 -geometry 1024x768 -depth 24 -rfbport 5999 -desktop "BookingAutomation" -alwaysshared &
websockify --web=/usr/share/novnc 8082 127.0.0.1:5999 &
export DISPLAY=:99 && fluxbox > /dev/null 2>&1 &

# Check services
ps aux | grep -E "(uvicorn|Xvnc|redis)" | grep -v grep
curl http://87.106.247.92:8000/health
```

## 🔑 Critical QR System

> ⚠️ **WARNING**: The QR endpoint is critical for frontend BankID authentication. Never change without testing!

### QR Flow:
```
Browser Automation → QR Detection → Redis Storage → API Response
        ↓                ↓             ↓             ↓
   DOM Watching      image_data     Cache Layer   JSON Response
```

### QR Endpoint Details:
- **URL**: `/api/v1/booking/{job_id}/qr`
- **Method**: GET
- **Auth**: `Bearer test-secret-token-12345`
- **Response**: `{"job_id": "...", "image_data": "data:image/png;base64,...", "timestamp": "..."}`

### NEVER Change:
- QR endpoint URL structure
- Authentication token
- Response JSON field names
- Redis key patterns

## 🖥️ Browser Automation

### VNC Access:
- **Web Interface**: http://87.106.247.92:8082/vnc.html
- **Direct VNC**: 87.106.247.92:5999

### Browser Management:
```bash
# Check browser processes
ps aux | grep firefox

# Kill stuck browsers
pkill firefox

# Check display
export DISPLAY=:99 && echo $DISPLAY

# Restart VNC if needed
pkill Xvnc
Xvnc :99 -geometry 1024x768 -depth 24 -rfbport 5999 -desktop "BookingAutomation" -alwaysshared &
```

## 🗄️ Redis Cache

### Key Patterns:
- `job:{job_id}` - Job status and data
- `qr:{job_id}` - QR code data
- `session:{job_id}` - Browser session data

### Redis Commands:
```bash
# Check job data
redis-cli get "job:job-123"

# List all jobs
redis-cli keys "job:*"

# Clear job data
redis-cli del "job:job-123"

# Monitor Redis activity
redis-cli monitor
```

## 🔍 Monitoring & Debugging

### Health Checks:
```bash
# Service health
curl http://87.106.247.92:8000/health
curl http://87.106.247.92:8082/vnc.html
redis-cli ping

# Test QR endpoint
curl http://87.106.247.92:8000/api/v1/booking/test-job/qr \
  -H "Authorization: Bearer test-secret-token-12345"
```

### Log Analysis:
```bash
# Application logs
tail -f /tmp/booking-monitor/app.log

# QR-specific logs
grep -E "(QR|📱)" /tmp/booking-monitor/app.log

# Browser automation logs
tail -f /tmp/booking-monitor/browser.log

# Error tracking
tail -f /tmp/booking-monitor/errors.log
```

## 🚨 Common Issues & Solutions

### Browser Automation Fails:
```bash
# Check display
export DISPLAY=:99 && echo $DISPLAY

# Restart VNC
pkill Xvnc
Xvnc :99 -geometry 1024x768 -depth 24 -rfbport 5999 -desktop "BookingAutomation" -alwaysshared &

# Check browser processes
ps aux | grep firefox
```

### QR Codes Not Generated:
```bash
# Check Redis connection
redis-cli ping

# Test QR endpoint directly
curl http://87.106.247.92:8000/api/v1/booking/{active_job_id}/qr \
  -H "Authorization: Bearer test-secret-token-12345"

# Check browser automation logs
grep "QR" /tmp/booking-monitor/browser.log
```

### Port Conflicts:
```bash
# Check what's using ports
lsof -i :8000
lsof -i :8082
lsof -i :5999

# Kill processes on ports
fuser -k 8000/tcp
fuser -k 8082/tcp
fuser -k 5999/tcp
```

## 🔒 Security

### Authentication:
- All API endpoints require secret token
- Token: `test-secret-token-12345`
- No public endpoints exposed

### Network Security:
- VPS Server: 87.106.247.92
- Firewall allows ports: 8000, 8082, 5999
- Redis only accessible locally

## 📚 Related Documentation

- **Frontend Repository**: https://github.com/fredfleetwood/tid-snabbt-boka
- **QR System Rules**: See frontend repo `QR_SYSTEM_RULES.md`
- **Complete System Docs**: See frontend repo `README.md`

## 🛠️ Development

### Local Development:
```bash
# Development mode
uvicorn app.main_production:app --host 0.0.0.0 --port 8000 --reload

# Run tests
python -m pytest

# Code formatting
black .
flake8 .
```

### Deployment:
```bash
# Pull latest changes
git pull origin main

# Restart services
pkill -f uvicorn
source venv/bin/activate
uvicorn app.main_production:app --host 0.0.0.0 --port 8000 &
```

## ⚡ Emergency Recovery

### Full System Restart:
```bash
# Kill all services
pkill -f uvicorn
pkill -f Xvnc  
pkill -f websockify

# Start services
cd backend && source venv/bin/activate
Xvnc :99 -geometry 1024x768 -depth 24 -rfbport 5999 -desktop "BookingAutomation" -alwaysshared &
websockify --web=/usr/share/novnc 8082 127.0.0.1:5999 &
export DISPLAY=:99 && fluxbox > /dev/null 2>&1 &
uvicorn app.main_production:app --host 0.0.0.0 --port 8000 &
```

## 📞 Support

### Troubleshooting:
1. Check service status: `ps aux | grep -E "(uvicorn|Xvnc)"`
2. Test endpoints: `curl http://87.106.247.92:8000/health`
3. Check logs: `tail -f /tmp/booking-monitor/app.log`
4. Verify Redis: `redis-cli ping`

### Contact:
For critical QR system issues, coordinate with frontend team since QR display is handled by frontend fallback mechanisms.

---

**⚠️ CRITICAL: Never modify QR endpoint without coordinating with frontend team! See frontend repo QR_SYSTEM_RULES.md** 