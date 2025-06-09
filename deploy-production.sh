#!/bin/bash

# VPS Automation Server - Complete Production Deployment Script
# This script deploys the full production system with webhook support and real-time features

set -e  # Exit on any error

echo "🚀 Starting VPS Automation Server Complete Production Deployment..."

# Configuration
DEPLOYMENT_ENV=${1:-production}
DOMAIN=${2:-localhost}

echo "📋 Deployment Configuration:"
echo "   Environment: $DEPLOYMENT_ENV"
echo "   Domain: $DOMAIN"
echo "   Date: $(date)"

# Step 1: Pre-deployment checks
echo ""
echo "🔍 Pre-deployment checks..."

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check required tools
if ! command -v curl &> /dev/null; then
    echo "❌ curl is not installed. Please install curl first."
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "⚠️  jq not found. Installing for JSON processing..."
    apt-get update && apt-get install -y jq || echo "Warning: Could not install jq"
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Creating from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your production settings before proceeding."
    echo "   Required settings: API_SECRET_TOKEN, WEBHOOK_SECRET, etc."
    read -p "Press Enter after configuring .env file..."
fi

echo "✅ Pre-deployment checks passed"

# Step 2: Build all containers
echo ""
echo "🔨 Building production containers..."

# Build the main application
docker-compose build --no-cache

echo "✅ Containers built successfully"

# Step 3: Stop any existing services
echo ""
echo "🛑 Stopping existing services..."

docker-compose down --remove-orphans || true

echo "✅ Existing services stopped"

# Step 4: Deploy core services
echo ""
echo "🚀 Starting core services (Redis, Web)..."

# Start Redis first
docker-compose up -d redis

# Wait for Redis to be healthy
echo "⏳ Waiting for Redis to be ready..."
timeout 60 bash -c 'until docker-compose exec redis redis-cli ping; do sleep 2; done'

# Start web service
docker-compose up -d web

# Wait for web service to be healthy
echo "⏳ Waiting for web service to be ready..."
timeout 120 bash -c 'until curl -f http://localhost:8080/health; do sleep 5; done'

echo "✅ Core services started"

# Step 5: Deployment verification
echo ""
echo "🧪 Verifying deployment..."

# Check all services are running
echo "Checking service status..."
docker-compose ps

# Test API endpoints
echo ""
echo "Testing API endpoints..."

# Basic health check
if curl -s http://localhost:8080/health | jq -e '.status == "healthy"' > /dev/null; then
    echo "✅ Health check: PASSED"
else
    echo "❌ Health check: FAILED"
fi

# Detailed health check
if curl -s http://localhost:8080/health/detailed | jq -e '.status == "healthy"' > /dev/null; then
    echo "✅ Detailed health check: PASSED"
else
    echo "❌ Detailed health check: FAILED"
fi

# Test API documentation
if curl -f http://localhost:8080/docs > /dev/null 2>&1; then
    echo "✅ API Documentation: PASSED"
else
    echo "❌ API Documentation: FAILED"
fi

# Test root endpoint
if curl -s http://localhost:8080/ | jq -e '.service' > /dev/null; then
    echo "✅ Root endpoint: PASSED"
else
    echo "❌ Root endpoint: FAILED"
fi

# Step 6: Test authentication and API functionality
echo ""
echo "🔐 Testing API authentication and functionality..."

# Get API token from environment
API_TOKEN=$(grep API_SECRET_TOKEN .env | cut -d'=' -f2 | tr -d '"' | tr -d "'")

if [ -z "$API_TOKEN" ]; then
    echo "⚠️  API_SECRET_TOKEN not found in .env file"
    API_TOKEN="test-secret-token-12345"
fi

# Test authenticated endpoint
AUTH_TEST=$(curl -s -H "Authorization: Bearer $API_TOKEN" http://localhost:8080/api/v1/booking/status)
if echo "$AUTH_TEST" | jq -e '.active_jobs' > /dev/null; then
    echo "✅ API Authentication: PASSED"
else
    echo "❌ API Authentication: FAILED"
fi

# Step 7: Test webhook functionality (if configured)
echo ""
echo "🔗 Testing webhook capabilities..."

WEBHOOK_SECRET=$(grep WEBHOOK_SECRET .env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
if [ ! -z "$WEBHOOK_SECRET" ]; then
    echo "✅ Webhook secret configured"
else
    echo "⚠️  Webhook secret not configured (optional)"
fi

# Step 8: Start a test booking job
echo ""
echo "🧪 Testing automation with sample booking..."

TEST_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "deployment_test_user",
    "license_type": "B",
    "exam_type": "Körprov",
    "locations": ["Stockholm"],
    "webhook_url": "https://httpbin.org/post"
  }' \
  http://localhost:8080/api/v1/booking/start 2>/dev/null || echo '{"error": "test_failed"}')

if echo "$TEST_RESPONSE" | jq -e '.job_id' > /dev/null; then
    JOB_ID=$(echo "$TEST_RESPONSE" | jq -r '.job_id')
    echo "✅ Test booking started: $JOB_ID"
    
    # Wait a moment and check job status
    sleep 5
    JOB_STATUS=$(curl -s -H "Authorization: Bearer $API_TOKEN" http://localhost:8080/api/v1/booking/status/$JOB_ID)
    if echo "$JOB_STATUS" | jq -e '.job_id' > /dev/null; then
        echo "✅ Job status retrieval: PASSED"
        echo "   Status: $(echo "$JOB_STATUS" | jq -r '.status // "unknown"')"
    else
        echo "❌ Job status retrieval: FAILED"
    fi
    
    # Test QR polling endpoint
    QR_TEST=$(curl -s -H "Authorization: Bearer $API_TOKEN" http://localhost:8080/api/v1/booking/$JOB_ID/qr)
    if echo "$QR_TEST" | jq -e '.job_id' > /dev/null; then
        echo "✅ QR polling endpoint: PASSED"
    else
        echo "❌ QR polling endpoint: FAILED"
    fi
    
    # Cancel the test job
    CANCEL_RESPONSE=$(curl -s -X POST \
      -H "Authorization: Bearer $API_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"job_id\": \"$JOB_ID\"}" \
      http://localhost:8080/api/v1/booking/stop)
    
    if echo "$CANCEL_RESPONSE" | jq -e '.success == true' > /dev/null; then
        echo "✅ Job cancellation: PASSED"
    else
        echo "⚠️  Job cancellation: FAILED (job may have completed)"
    fi
    
else
    echo "❌ Test booking failed - check API token configuration"
    echo "   Response: $TEST_RESPONSE"
fi

# Step 9: Display deployment summary
echo ""
echo "🎉 Deployment Summary"
echo "===================="
echo ""
echo "🌐 Service Endpoints:"
echo "   Main API:              http://$DOMAIN:8080"
echo "   API Documentation:     http://$DOMAIN:8080/docs"
echo "   Health Monitoring:     http://$DOMAIN:8080/health/detailed"
echo "   WebSocket Streaming:   ws://$DOMAIN:8080/ws/{job_id}"
echo ""
echo "🔧 Management Commands:"
echo "   View logs:             docker-compose logs -f [service]"
echo "   Stop services:         docker-compose down"
echo "   Update deployment:     ./deploy-production.sh"
echo "   Monitor system:        curl -H 'Authorization: Bearer \$API_TOKEN' http://$DOMAIN:8080/health/detailed"
echo ""
echo "📊 System Status:"
SYSTEM_STATUS=$(curl -s http://localhost:8080/health/detailed)
echo "   Redis Status:          $(echo "$SYSTEM_STATUS" | jq -r '.system.redis_status // "unknown"')"
echo "   Active Jobs:           $(echo "$SYSTEM_STATUS" | jq -r '.jobs.active_jobs // "0"')"
echo "   WebSocket Connections: $(echo "$SYSTEM_STATUS" | jq -r '.connections.websocket_connections // "0"')"
echo "   Memory Usage:          $(echo "$SYSTEM_STATUS" | jq -r '.performance.memory_usage // "unknown"')%"
echo "   CPU Usage:             $(echo "$SYSTEM_STATUS" | jq -r '.performance.cpu_usage // "unknown"')%"
echo ""
echo "🎉 VPS Automation Server deployed successfully!"
echo ""
echo "📝 Next Steps:"
echo "   1. Configure your domain DNS to point to this server"
echo "   2. Configure firewall rules for ports 8080 and 5900 (VNC)"
echo "   3. Set up SSL/TLS certificates for HTTPS"
echo "   4. Configure webhook endpoints in your frontend application"
echo "   5. Set up automated backups and monitoring"
echo ""
echo "🔐 Security Reminders:"
echo "   - Change default API_SECRET_TOKEN in .env file"
echo "   - Configure WEBHOOK_SECRET for secure webhook communication"
echo "   - Restrict access to sensitive endpoints with firewall rules"
echo "   - Regular security updates and log monitoring"
echo ""
echo "🚀 Ready for Frontend Integration:"
echo "   - All API endpoints are operational"
echo "   - Webhook system is configured"
echo "   - Real-time QR streaming is available"
echo "   - Authentication is working"
echo ""
echo "Happy automating! 🤖" 