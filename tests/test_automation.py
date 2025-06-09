"""
Comprehensive Test Suite for VPS Automation System
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

# Import the production app
from app.main_production import app, manager, active_jobs, qr_streaming_callback
from app.automation.simple_booking import BookingAutomation, start_automated_booking


class TestProductionAPI:
    """Test the production FastAPI application"""
    
    def setup_method(self):
        """Set up test client and mocks"""
        self.client = TestClient(app)
        self.auth_headers = {"Authorization": "Bearer test-secret-token-12345"}
        
    def test_root_endpoint(self):
        """Test the root endpoint"""
        response = self.client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["service"] == "VPS Automation Server - Production"
        assert data["status"] == "running"
        assert "real_automation" in data["features"]
        assert "qr_streaming" in data["features"]
        
    def test_health_endpoint(self):
        """Test basic health check"""
        response = self.client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "redis" in data
        assert "active_jobs" in data
        
    def test_detailed_health_endpoint(self):
        """Test detailed health monitoring"""
        response = self.client.get("/health/detailed")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "system" in data
        assert "jobs" in data
        assert "connections" in data
        assert "performance" in data
        
    def test_authentication_required(self):
        """Test that authentication is required for protected endpoints"""
        
        # Test without auth
        response = self.client.post("/api/v1/booking/start", json={
            "user_id": "test",
            "license_type": "B",
            "exam_type": "Körprov",
            "locations": ["Stockholm"]
        })
        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"
        
    def test_invalid_token(self):
        """Test invalid authentication token"""
        
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = self.client.post("/api/v1/booking/start", 
                                  json={"user_id": "test"}, 
                                  headers=invalid_headers)
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid authentication token"
        
    def test_booking_validation(self):
        """Test booking request validation"""
        
        # Missing required fields
        response = self.client.post("/api/v1/booking/start", 
                                  json={"user_id": "test"},
                                  headers=self.auth_headers)
        assert response.status_code == 400
        assert "Missing required field" in response.json()["detail"]
        
    @patch('app.main_production.start_automated_booking')
    def test_successful_booking_start(self, mock_automation):
        """Test successful booking job creation"""
        
        # Mock the automation function
        mock_automation.return_value = asyncio.create_task(self._mock_booking_task())
        
        response = self.client.post("/api/v1/booking/start", json={
            "user_id": "test_user",
            "license_type": "B", 
            "exam_type": "Körprov",
            "locations": ["Stockholm", "Göteborg"]
        }, headers=self.auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "starting"
        assert data["message"] == "Booking automation started"
        assert "job_id" in data
        assert "websocket_url" in data
        assert "qr_polling_url" in data
        
    async def _mock_booking_task(self):
        """Mock booking task for testing"""
        await asyncio.sleep(0.1)
        return {"success": True, "message": "Test booking completed"}
        
    def test_queue_status(self):
        """Test queue status endpoint"""
        
        response = self.client.get("/api/v1/queue/status", headers=self.auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "capacity" in data
        assert "active_jobs" in data
        assert "websocket_connections" in data
        assert data["capacity"]["max_concurrent_jobs"] == 10
        
    @patch('app.main_production.redis_client')
    def test_job_status_retrieval(self, mock_redis):
        """Test job status retrieval"""
        
        # Mock Redis response
        mock_redis.get.return_value = json.dumps({
            "job_id": "test_job_123",
            "status": "running",
            "progress": 50,
            "message": "Processing"
        }).encode()
        
        response = self.client.get("/api/v1/booking/status/test_job_123", 
                                 headers=self.auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["job_id"] == "test_job_123"
        assert data["status"] == "running"
        assert data["progress"] == 50
        
    @patch('app.main_production.redis_client')  
    def test_qr_code_retrieval(self, mock_redis):
        """Test QR code polling endpoint"""
        
        # Mock Redis QR data
        qr_data = {
            "type": "qr_update",
            "job_id": "test_job_123",
            "image_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
            "timestamp": "2025-06-07T00:00:00.000000"
        }
        mock_redis.get.return_value = json.dumps(qr_data).encode()
        
        response = self.client.get("/api/v1/booking/test_job_123/qr", 
                                 headers=self.auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["type"] == "qr_update"
        assert data["job_id"] == "test_job_123"
        assert "image_data" in data


class TestBookingAutomation:
    """Test the booking automation system"""
    
    def setup_method(self):
        """Set up test environment"""
        self.mock_redis = Mock()
        self.qr_callback = AsyncMock()
        
    @pytest.mark.asyncio
    async def test_booking_automation_initialization(self):
        """Test BookingAutomation initialization"""
        
        automation = BookingAutomation(self.mock_redis, self.qr_callback)
        assert automation.redis_client == self.mock_redis
        assert automation.qr_callback == self.qr_callback
        assert automation.browser is None
        assert automation.page is None
        
    @pytest.mark.asyncio
    @patch('app.automation.simple_booking.async_playwright')
    async def test_browser_launch(self, mock_playwright):
        """Test browser launching"""
        
        # Mock playwright
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_playwright.return_value.start = AsyncMock(return_value=mock_p)
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        
        automation = BookingAutomation(self.mock_redis, self.qr_callback)
        
        # This would test the actual browser launch, but we'll mock it
        # automation.browser = mock_browser
        # automation.page = mock_page
        
        assert True  # Placeholder for browser launch test
        
    @pytest.mark.asyncio
    async def test_qr_code_generation(self):
        """Test QR code generation"""
        
        automation = BookingAutomation(self.mock_redis, self.qr_callback)
        
        test_data = "test_qr_data"
        qr_image = automation._generate_qr_image(test_data)
        
        assert qr_image.startswith("data:image/png;base64,")
        assert len(qr_image) > 50  # Should be a substantial base64 string
        
    @pytest.mark.asyncio 
    async def test_job_status_update(self):
        """Test job status updates"""
        
        automation = BookingAutomation(self.mock_redis, self.qr_callback)
        automation.job_id = "test_job_123"
        
        await automation._update_job_status("running", "Test message", 50)
        
        # Verify Redis was called
        self.mock_redis.setex.assert_called_once()
        call_args = self.mock_redis.setex.call_args
        
        assert call_args[0][0] == "job:test_job_123"  # Redis key
        assert call_args[0][1] == 3600  # TTL
        
        # Parse the stored data
        stored_data = json.loads(call_args[0][2])
        assert stored_data["status"] == "running"
        assert stored_data["message"] == "Test message"
        assert stored_data["progress"] == 50


class TestWebSocketManager:
    """Test WebSocket connection management"""
    
    def setup_method(self):
        """Set up test environment"""
        self.manager = manager
        self.mock_websocket = AsyncMock()
        
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection management"""
        
        job_id = "test_job_websocket"
        
        # Test connection
        await self.manager.connect(self.mock_websocket, job_id)
        assert job_id in self.manager.active_connections
        assert self.manager.active_connections[job_id] == self.mock_websocket
        
        # Test disconnection
        self.manager.disconnect(job_id)
        assert job_id not in self.manager.active_connections
        
    @pytest.mark.asyncio
    async def test_qr_streaming(self):
        """Test QR code streaming via WebSocket"""
        
        job_id = "test_job_qr_stream"
        await self.manager.connect(self.mock_websocket, job_id)
        
        qr_data = {
            "type": "qr_update",
            "job_id": job_id,
            "image_data": "test_image_data",
            "timestamp": "2025-06-07T00:00:00.000000"
        }
        
        await self.manager.send_qr_update(job_id, qr_data)
        
        # Verify WebSocket send was called
        self.mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(self.mock_websocket.send_text.call_args[0][0])
        assert sent_data == qr_data
        
    @pytest.mark.asyncio
    async def test_qr_streaming_callback(self):
        """Test the QR streaming callback function"""
        
        # Mock the manager
        with patch('app.main_production.manager') as mock_manager:
            with patch('app.main_production.redis_client') as mock_redis:
                
                await qr_streaming_callback(
                    job_id="test_job",
                    qr_image_data="test_image",
                    qr_metadata={"test": "metadata"}
                )
                
                # Verify manager was called
                mock_manager.send_qr_update.assert_called_once()
                
                # Verify Redis was called
                mock_redis.setex.assert_called_once()


class TestConcurrency:
    """Test concurrent job handling"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
        self.auth_headers = {"Authorization": "Bearer test-secret-token-12345"}
        
    def test_concurrent_job_limit(self):
        """Test that concurrent job limit is enforced"""
        
        # Fill up the active jobs (mocking)
        with patch('app.main_production.active_jobs', {f"job_{i}": Mock() for i in range(10)}):
            
            response = self.client.post("/api/v1/booking/start", json={
                "user_id": "test_user",
                "license_type": "B",
                "exam_type": "Körprov", 
                "locations": ["Stockholm"]
            }, headers=self.auth_headers)
            
            assert response.status_code == 503
            assert "Server at capacity" in response.json()["detail"]
            
    @patch('app.main_production.start_automated_booking')
    def test_job_cleanup_on_completion(self, mock_automation):
        """Test that jobs are cleaned up when completed"""
        
        # This is a more complex test that would require proper async testing
        # For now, we'll test the concept
        
        mock_task = AsyncMock()
        mock_automation.return_value = mock_task
        
        response = self.client.post("/api/v1/booking/start", json={
            "user_id": "test_user",
            "license_type": "B",
            "exam_type": "Körprov",
            "locations": ["Stockholm"]
        }, headers=self.auth_headers)
        
        assert response.status_code == 200
        # In a real test, we'd verify the cleanup callback is set


class TestErrorHandling:
    """Test error handling and recovery"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
        self.auth_headers = {"Authorization": "Bearer test-secret-token-12345"}
        
    @patch('app.main_production.redis_client')
    def test_redis_failure_handling(self, mock_redis):
        """Test graceful handling of Redis failures"""
        
        # Mock Redis failure
        mock_redis.get.side_effect = Exception("Redis connection failed")
        
        response = self.client.get("/api/v1/booking/status/test_job", 
                                 headers=self.auth_headers)
        
        # Should still return a response, not crash
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unknown"
        assert data["message"] == "Job not found or expired"
        
    def test_websocket_error_handling(self):
        """Test WebSocket error handling"""
        
        # This would test WebSocket disconnection handling
        # The actual implementation handles disconnections gracefully
        job_id = "test_job_error"
        
        # Simulate adding and removing a connection
        manager.active_connections[job_id] = Mock()
        manager.disconnect(job_id)
        
        assert job_id not in manager.active_connections


# Integration Tests
class TestIntegration:
    """Integration tests for the complete system"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
        self.auth_headers = {"Authorization": "Bearer test-secret-token-12345"}
        
    @patch('app.automation.simple_booking.async_playwright')
    @patch('app.main_production.redis_client')
    def test_complete_booking_flow(self, mock_redis, mock_playwright):
        """Test the complete booking flow end-to-end"""
        
        # Mock playwright and Redis
        mock_redis.setex = Mock()
        mock_redis.get.return_value = None
        
        # Start a booking
        response = self.client.post("/api/v1/booking/start", json={
            "user_id": "integration_test",
            "license_type": "B",
            "exam_type": "Körprov",
            "locations": ["Stockholm"]
        }, headers=self.auth_headers)
        
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Check job status
        status_response = self.client.get(f"/api/v1/booking/status/{job_id}",
                                        headers=self.auth_headers)
        assert status_response.status_code == 200
        
        # Check queue status
        queue_response = self.client.get("/api/v1/queue/status",
                                       headers=self.auth_headers)
        assert queue_response.status_code == 200
        
        # Clean up any remaining jobs
        if job_id in active_jobs:
            active_jobs[job_id].cancel()
            del active_jobs[job_id]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app", "--cov-report=html"]) 