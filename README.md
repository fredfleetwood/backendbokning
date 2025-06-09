# VPS Automation Server

**Production-Ready Swedish Driving Test Booking Automation with Real-Time Webhooks**

A comprehensive automation server for Swedish driving test booking with real-time browser automation, BankID integration, webhook notifications, and remote API control.

## 🚀 Features

- **Remote API Control**: Start booking jobs from any device via REST API
- **Real-Time Webhook System**: Live notifications to external services (Supabase, etc.)
- **Browser Automation**: Visual browser automation with VNC support
- **BankID QR Streaming**: Real-time QR code capture and delivery
- **WebSocket Support**: Live status updates and QR code streaming
- **Multi-Location Support**: Search across multiple test locations
- **Production Ready**: Docker deployment with Redis state management
- **Frontend Ready**: Designed for Lovable + Supabase integration

## 🏗️ Enhanced Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │───▶│   Supabase       │───▶│   VPS Server    │
│   (Lovable)     │    │   Edge Function  │    │   (Port 8080)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         ▲                        ▲                        │
         │                        │                        ▼
         │              ┌──────────────────┐    ┌─────────────────┐
         │              │   Webhook        │◀───│  Redis Storage  │
         │              │   Notifications  │    │  (State/Cache)  │
         │              └──────────────────┘    └─────────────────┘
         │                        │                        │
┌─────────────────┐               │                        ▼
│   Real-time     │◀──────────────┘              ┌──────────────────┐
│   Updates       │               │               └──────────────────┘
│   (WebSocket)   │               │                        │
└─────────────────┘               │                        │
         ▲                        │                        │
         │                        │                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   VNC Viewer    │◀───│   Browser Auto   │───▶│  Trafikverket   │
│   (Visual)      │    │   (Playwright)   │    │   (Website)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📡 Communication Flows

### **Flow 1: User Starts Booking**
```
User (Lovable) → Supabase Edge Function → VPS Server → Job Started
```

### **Flow 2: Real-Time Status Updates**
```
VPS Progress → Webhook to Supabase → Real-time to Frontend → User sees live updates
```

### **Flow 3: QR Code Streaming**
```
Browser QR Code → VPS Capture → Webhook + WebSocket → Frontend display
```

## 📋 Prerequisites

- **VPS**: Ubuntu 22.04+ with 4GB+ RAM
- **Ports**: 8080 (API), 5900 (VNC) open in firewall
- **Dependencies**: Docker & Docker Compose OR Python 3.12+

## 🛠️ Quick Start

### Option 1: Docker (Recommended)

```bash
git clone <your-repo-url>
cd vps-automation-server

# Start services
docker-compose up -d

# Check status
curl http://localhost:8080/health
```

### Option 2: Manual Setup

```bash
# Install dependencies
sudo apt update
sudo apt install python3.12 python3.12-venv redis-server xvfb x11vnc fluxbox

# Setup Python environment
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install browsers
playwright install-deps
playwright install chromium

# Start Redis
sudo systemctl start redis-server

# Start display services
Xvfb :99 -screen 0 1920x1080x24 &
DISPLAY=:99 fluxbox &
x11vnc -display :99 -nopw -forever -shared &

# Start server
source venv/bin/activate
export REDIS_URL="redis://localhost:6379/0"
export API_SECRET_TOKEN="your-secret-token"
export DISPLAY=":99"
python -m uvicorn app.main_production:app --host 0.0.0.0 --port 8080
```

## ⚙️ Configuration

### Environment Variables

Create `.env` file:

```bash
# Required
API_SECRET_TOKEN=your-secret-token-here
REDIS_URL=redis://localhost:6379/0

# Webhook Configuration (Optional)
WEBHOOK_SECRET=your-webhook-secret-key
SUPABASE_WEBHOOK_URL=https://your-project.supabase.co/functions/v1/booking-webhook

# Display & Browser
DISPLAY=:99
BROWSER_HEADLESS=false

# Application Settings
LOG_LEVEL=INFO
DEBUG=false
ENVIRONMENT=production
```

### VNC Access (Visual Browser)

Connect to see browser automation in real-time:
- **Server**: `your-vps-ip:5900`
- **Password**: None
- **Client**: VNC Viewer, TightVNC, or built-in screen sharing

## 📚 Enhanced API Usage

### Authentication

All requests require Bearer token:

```bash
export API_TOKEN="your-secret-token"
export VPS_URL="http://your-vps-ip:8080"
```

### Start Booking Job with Webhooks

```bash
curl -X POST "$VPS_URL/api/v1/booking/start" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_TOKEN" \
  -d '{
    "user_id": "your-user-id",
    "license_type": "B", 
    "exam_type": "Körprov",
    "locations": ["Stockholm", "Uppsala"],
    "webhook_url": "https://your-app.supabase.co/functions/v1/booking-webhook"
  }'
```

Response:
```json
{
  "job_id": "job_abc123",
  "status": "starting",
  "message": "Booking automation started",
  "webhook_configured": true,
  "websocket_url": "/ws/job_abc123",
  "qr_polling_url": "/api/v1/booking/job_abc123/qr"
}
```

### Real-Time WebSocket Connection

```javascript
// Frontend WebSocket connection
const ws = new WebSocket('ws://your-vps-ip:8080/ws/job_abc123');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'qr_update') {
    // Display QR code: data.image_data
    showQRCode(data.image_data);
  }
};
```

### QR Code Polling (HTTP Fallback)

```bash
curl -H "Authorization: Bearer $API_TOKEN" \
  "$VPS_URL/api/v1/booking/job_abc123/qr"
```

Response:
```json
{
  "type": "qr_update",
  "job_id": "job_abc123",
  "image_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "timestamp": "2024-01-01T10:07:30Z"
}
```

### Webhook Notifications

Your webhook endpoint will receive:

**Booking Started:**
```json
{
  "event_type": "booking_started",
  "job_id": "job_abc123",
  "user_id": "user_123",
  "timestamp": "2024-01-01T10:00:00Z",
  "data": {
    "config": {...},
    "estimated_duration": "60-180 seconds"
  }
}
```

**Status Updates:**
```json
{
  "event_type": "status_update",
  "job_id": "job_abc123",
  "user_id": "user_123",
  "data": {
    "status": "qr_waiting",
    "message": "Waiting for BankID authentication",
    "progress": 25
  }
}
```

**QR Code Updates:**
```json
{
  "event_type": "qr_code_update",
  "job_id": "job_abc123",
  "user_id": "user_123", 
  "data": {
    "qr_code_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
    "expires_in": 60
  }
}
```

**Booking Completed:**
```json
{
  "event_type": "booking_completed",
  "job_id": "job_abc123",
  "user_id": "user_123",
  "data": {
    "success": true,
    "booking_result": {
      "booking_id": "TV123456789",
      "exam_date": "2024-01-20",
      "exam_time": "10:30"
    }
  }
}
```

## 🧪 Testing Communication Flows

Run the comprehensive test suite:

```bash
source venv/bin/activate
export API_SECRET_TOKEN="your-token"
python test_webhook_flows.py
```

This tests all three communication flows:
- ✅ User starts booking 
- ✅ Real-time status updates
- ✅ QR code streaming

## 🔍 Enhanced Job Status Flow

1. **`starting`** - Initializing browser, webhook sent
2. **`navigating`** - Loading Trafikverket website
3. **`login`** - Clicking "Boka prov" button
4. **`bankid`** - Starting BankID authentication
5. **`qr_waiting`** - Displaying QR code, streaming to webhook
6. **`authenticated`** - BankID completed successfully
7. **`configuring`** - Selecting license and exam type
8. **`locations`** - Selecting test locations
9. **`searching`** - Looking for available slots
10. **`booking`** - Attempting to book found slot
11. **`completed`** - Job finished, final webhook sent

## 🖥️ Visual Monitoring

### VNC Connection

1. **Open VNC client** (VNC Viewer, etc.)
2. **Connect to**: `your-vps-ip:5900` 
3. **Watch browser automation** in real-time
4. **See BankID QR codes** and booking process

### Logs

```bash
# Docker logs
docker-compose logs -f web

# Manual logs  
tail -f /var/log/automation.log
```

## 🚀 Frontend Integration

### Supabase Edge Function

Create a Supabase Edge Function to receive webhooks:

```typescript
// supabase/functions/booking-webhook/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"

serve(async (req) => {
  const { event_type, job_id, user_id, data } = await req.json()
  
  // Update booking status in database
  const { error } = await supabase
    .from('bookings')
    .update({ 
      status: data.status,
      progress: data.progress,
      qr_code: data.qr_code_data 
    })
    .eq('job_id', job_id)
  
  // Broadcast real-time update to frontend
  await supabase.realtime.send({
    event: 'booking_update',
    payload: { job_id, ...data }
  })
  
  return new Response('OK')
})
```

### Lovable Frontend Integration

```javascript
// Start booking from frontend
const startBooking = async (bookingData) => {
  const response = await fetch('/api/start-booking', {
    method: 'POST',
    body: JSON.stringify({
      ...bookingData,
      webhook_url: 'https://your-project.supabase.co/functions/v1/booking-webhook'
    })
  })
  
  const { job_id } = await response.json()
  
  // Subscribe to real-time updates
  const channel = supabase
    .channel('booking_updates')
    .on('booking_update', (payload) => {
      if (payload.job_id === job_id) {
        updateBookingStatus(payload)
        if (payload.qr_code_data) {
          displayQRCode(payload.qr_code_data)
        }
      }
    })
    .subscribe()
}
```

## 🛡️ Security

### Webhook Security
- **HMAC Signatures**: All webhooks include security signatures
- **Secret Validation**: Configure `WEBHOOK_SECRET` for verification
- **Header Authentication**: Custom headers for webhook identification

### API Security
- **Bearer Token**: All endpoints require authentication
- **Rate Limiting**: Built-in request throttling
- **Input Validation**: All requests validated

## 🐛 Troubleshooting

### Test Communication Flows

```bash
# Run full test suite
python test_webhook_flows.py

# Test specific endpoint
curl -H "Authorization: Bearer $API_TOKEN" \
  "$VPS_URL/health/detailed"
```

### Common Issues

**Webhook Not Receiving Updates**
```bash
# Check webhook URL in job
curl -H "Authorization: Bearer $API_TOKEN" \
  "$VPS_URL/api/v1/booking/status/job_id"

# Test webhook endpoint
curl -X POST "your-webhook-url" \
  -H "Content-Type: application/json" \
  -d '{"test": "webhook"}'
```

**WebSocket Connection Failed**
```javascript
// Test WebSocket connection
const ws = new WebSocket('ws://your-vps-ip:8080/ws/test_job');
ws.onopen = () => console.log('✅ WebSocket connected');
ws.onerror = (error) => console.log('❌ WebSocket error:', error);
```

**QR Code Not Appearing**
```bash
# Check QR polling endpoint
curl -H "Authorization: Bearer $API_TOKEN" \
  "$VPS_URL/api/v1/booking/job_id/qr"
```

## 📊 Performance

### Resource Usage
- **Base**: ~500MB RAM, 1 CPU core
- **Per Job**: +200MB RAM per active booking
- **Browser**: ~100MB RAM per browser instance
- **WebSocket**: Minimal overhead per connection

### Scaling
- **Single Job**: 2GB RAM recommended
- **Multiple Jobs**: Add 500MB per concurrent job
- **VPS Size**: 4GB+ for production use
- **Concurrent Webhooks**: Up to 100/second

## 📝 Complete API Reference

### Core Endpoints

| Method | Endpoint | Description | Webhook Support |
|--------|----------|-------------|-----------------|
| GET | `/health` | Health check | ❌ |
| GET | `/health/detailed` | Detailed system status | ❌ |
| POST | `/api/v1/booking/start` | Start booking job | ✅ |
| GET | `/api/v1/booking/status/{job_id}` | Get job status | ❌ |
| GET | `/api/v1/booking/{job_id}/qr` | Get latest QR code | ❌ |
| POST | `/api/v1/booking/stop` | Stop job | ✅ |
| GET | `/api/v1/booking/status` | List all jobs | ❌ |
| WS | `/ws/{job_id}` | Real-time updates | ❌ |

### Webhook Events

- `booking_started` - Job initialization
- `status_update` - Progress updates
- `qr_code_update` - New QR code available
- `booking_completed` - Job finished (success/failure)

## 📄 License

MIT License - see LICENSE file

## 🆘 Support

1. **Run test suite** - `python test_webhook_flows.py`
2. **Check logs** for error messages
3. **Verify configuration** (.env file)
4. **Test webhooks** with webhook.site
5. **Check VNC** for visual debugging

---

**Built with**: FastAPI, Playwright, Redis, Docker, WebSockets, Webhooks

**Production-Ready. Real-Time. Frontend-Integrated.** 🚀 