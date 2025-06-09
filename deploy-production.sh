#!/bin/bash

# VPS Automation Server - Simplified Production Deployment Script
# This script deploys the simplified production system with only essential services

set -e  # Exit on any error

echo "🚀 Starting VPS Automation Server Simplified Deployment..."

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

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Creating from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your production settings before proceeding."
    echo "   Required settings: API_SECRET_TOKEN, etc."
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
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Health check: PASSED"
else
    echo "❌ Health check: FAILED"
fi

# Test API documentation
if curl -f http://localhost:8080/docs > /dev/null 2>&1; then
    echo "✅ API Documentation: PASSED"
else
    echo "❌ API Documentation: FAILED"
fi

# Step 6: Display deployment summary
echo ""
echo "🎉 Deployment Summary"
echo "===================="
echo ""
echo "🌐 Service Endpoints:"
echo "   Main API:           http://$DOMAIN:8080"
echo "   API Documentation:  http://$DOMAIN:8080/docs"
echo "   Health Monitoring:  http://$DOMAIN:8080/health/detailed"
echo ""
echo "🔧 Management:"
echo "   View logs:          docker-compose logs -f [service]"
echo "   Stop services:      docker-compose down"
echo "   Update deployment:  ./deploy-production.sh"
echo ""

# Step 7: Start a test booking job
echo "🧪 Testing automation with sample booking..."

# Test with authentication
API_TOKEN=$(grep API_SECRET_TOKEN .env | cut -d'=' -f2)

TEST_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "deployment_test",
    "license_type": "B",
    "exam_type": "Körprov",
    "locations": ["Stockholm"]
  }' \
  http://localhost:8080/api/v1/booking/start 2>/dev/null || echo '{"error": "test_failed"}')

if echo "$TEST_RESPONSE" | grep -q "job_id"; then
    JOB_ID=$(echo "$TEST_RESPONSE" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
    echo "✅ Test booking started: $JOB_ID"
    echo "   Monitor progress: curl -H 'Authorization: Bearer $API_TOKEN' http://localhost:8080/api/v1/booking/status/$JOB_ID"
else
    echo "⚠️  Test booking failed - check API token configuration"
fi

echo ""
echo "🎉 VPS Automation Server deployed successfully!"
echo ""
echo "📝 Next Steps:"
echo "   1. Configure your domain DNS to point to this server"
echo "   2. Configure firewall rules for ports 8080 and 5900 (VNC)"
echo "   3. Set up automated backups"
echo ""
echo "🔐 Security Reminders:"
echo "   - Change default passwords in .env file"
echo "   - Restrict access to sensitive endpoints"
echo "   - Regular security updates"
echo ""
echo "Happy automating! 🤖" 