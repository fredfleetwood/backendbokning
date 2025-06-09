#!/usr/bin/env python3
"""
Test Script for VPS Automation Server Communication Flows

This script tests all three communication flows:
1. User Starts Booking (Flow 1)
2. Real-Time Status Updates (Flow 2) 
3. Booking Completion (Flow 3)
"""
import asyncio
import json
import time
import os
import sys
from datetime import datetime
from typing import Dict, Any
import httpx

# Test Configuration
VPS_URL = os.getenv("VPS_URL", "http://localhost:8080")
API_TOKEN = os.getenv("API_SECRET_TOKEN", "test-secret-token-12345")
WEBHOOK_URL = "https://webhook.site/your-webhook-id"  # Replace with your webhook.site URL

print(f"""
🧪 VPS Automation Server - Communication Flow Test
============================================

Testing all communication flows as specified:
- Flow 1: User Starts Booking
- Flow 2: Real-Time Status Updates  
- Flow 3: Booking Completion

Configuration:
- VPS URL: {VPS_URL}
- API Token: {API_TOKEN[:10]}...
- Webhook URL: {WEBHOOK_URL}

""")

class WebhookTester:
    """Test webhook functionality and communication flows"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.job_id = None
        
    async def test_flow_1_start_booking(self) -> Dict[str, Any]:
        """Flow 1: User Starts Booking"""
        
        print("🔄 Testing Flow 1: User Starts Booking")
        print("=" * 50)
        
        # Simulate Supabase Edge Function calling VPS server
        booking_request = {
            "user_id": f"test_user_{int(time.time())}",
            "license_type": "B",
            "exam_type": "Körprov", 
            "locations": ["Stockholm", "Uppsala"],
            "webhook_url": WEBHOOK_URL
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_TOKEN}"
        }
        
        try:
            print(f"📤 Sending booking request to: {VPS_URL}/api/v1/booking/start")
            print(f"📋 Request data: {json.dumps(booking_request, indent=2)}")
            
            response = await self.client.post(
                f"{VPS_URL}/api/v1/booking/start",
                json=booking_request,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                self.job_id = result.get("job_id")
                
                print(f"✅ Flow 1 Success!")
                print(f"   Status Code: {response.status_code}")
                print(f"   Job ID: {self.job_id}")
                print(f"   Status: {result.get('status')}")
                print(f"   Message: {result.get('message')}")
                print(f"   Webhook Configured: {result.get('webhook_configured')}")
                
                return {"success": True, "job_id": self.job_id, "response": result}
            else:
                print(f"❌ Flow 1 Failed!")
                print(f"   Status Code: {response.status_code}")
                print(f"   Error: {response.text}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ Flow 1 Exception: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_flow_2_status_updates(self, job_id: str) -> Dict[str, Any]:
        """Flow 2: Real-Time Status Updates"""
        
        print("\n🔄 Testing Flow 2: Real-Time Status Updates")
        print("=" * 50)
        
        headers = {
            "Authorization": f"Bearer {API_TOKEN}"
        }
        
        # Monitor job status for updates
        for i in range(12):  # Monitor for 60 seconds
            try:
                print(f"📊 Checking status (attempt {i+1}/12)...")
                
                response = await self.client.get(
                    f"{VPS_URL}/api/v1/booking/status/{job_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    status_data = response.json()
                    
                    print(f"   Job ID: {status_data.get('job_id')}")
                    print(f"   Status: {status_data.get('status')}")
                    print(f"   Message: {status_data.get('message')}")
                    print(f"   Is Active: {status_data.get('is_active')}")
                    print(f"   Timestamp: {status_data.get('timestamp')}")
                    
                    # Check if job completed
                    status = status_data.get('status')
                    if status in ['completed', 'failed', 'cancelled']:
                        print(f"✅ Flow 2 Success - Job completed with status: {status}")
                        return {"success": True, "final_status": status, "data": status_data}
                    
                else:
                    print(f"⚠️ Status check failed: {response.status_code}")
                
            except Exception as e:
                print(f"❌ Status check error: {str(e)}")
            
            await asyncio.sleep(5)  # Wait 5 seconds between checks
        
        print(f"⏰ Flow 2 Timeout - Job still running after 60 seconds")
        return {"success": False, "error": "timeout"}
    
    async def test_flow_3_qr_polling(self, job_id: str) -> Dict[str, Any]:
        """Flow 3: QR Code Polling (WebSocket alternative)"""
        
        print("\n🔄 Testing Flow 3: QR Code Polling")
        print("=" * 50)
        
        headers = {
            "Authorization": f"Bearer {API_TOKEN}"
        }
        
        # Poll for QR codes
        for i in range(6):  # Poll for 30 seconds
            try:
                print(f"📱 Checking for QR code (attempt {i+1}/6)...")
                
                response = await self.client.get(
                    f"{VPS_URL}/api/v1/booking/{job_id}/qr",
                    headers=headers
                )
                
                if response.status_code == 200:
                    qr_data = response.json()
                    
                    if "image_data" in qr_data:
                        print(f"✅ QR Code Found!")
                        print(f"   Type: {qr_data.get('type')}")
                        print(f"   Job ID: {qr_data.get('job_id')}")
                        print(f"   Timestamp: {qr_data.get('timestamp')}")
                        print(f"   Image Data: {qr_data.get('image_data')[:50]}...")
                        
                        return {"success": True, "qr_data": qr_data}
                    else:
                        print(f"   No QR code available yet: {qr_data.get('message')}")
                
            except Exception as e:
                print(f"❌ QR polling error: {str(e)}")
            
            await asyncio.sleep(5)  # Wait 5 seconds between polls
        
        print(f"⏰ Flow 3 Timeout - No QR code found after 30 seconds")
        return {"success": False, "error": "no_qr_found"}
    
    async def test_job_cancellation(self, job_id: str) -> Dict[str, Any]:
        """Test job cancellation"""
        
        print(f"\n🛑 Testing Job Cancellation")
        print("=" * 50)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_TOKEN}"
        }
        
        cancel_request = {
            "job_id": job_id
        }
        
        try:
            print(f"📤 Sending cancellation request for job: {job_id}")
            
            response = await self.client.post(
                f"{VPS_URL}/api/v1/booking/stop",
                json=cancel_request,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                
                print(f"✅ Cancellation Success!")
                print(f"   Success: {result.get('success')}")
                print(f"   Message: {result.get('message')}")
                print(f"   Timestamp: {result.get('timestamp')}")
                
                return {"success": True, "response": result}
            else:
                print(f"❌ Cancellation Failed: {response.status_code}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ Cancellation Exception: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_health_check(self) -> Dict[str, Any]:
        """Test health check endpoint"""
        
        print(f"\n❤️ Testing Health Check")
        print("=" * 50)
        
        try:
            # Basic health check
            response = await self.client.get(f"{VPS_URL}/health")
            
            if response.status_code == 200:
                health_data = response.json()
                
                print(f"✅ Basic Health Check Success!")
                print(f"   Status: {health_data.get('status')}")
                print(f"   Redis: {health_data.get('redis')}")
                print(f"   Active Jobs: {health_data.get('active_jobs')}")
                print(f"   WebSocket Connections: {health_data.get('websocket_connections')}")
                
                # Detailed health check
                response = await self.client.get(f"{VPS_URL}/health/detailed")
                
                if response.status_code == 200:
                    detailed_health = response.json()
                    
                    print(f"✅ Detailed Health Check Success!")
                    print(f"   System Status: {detailed_health.get('status')}")
                    print(f"   Memory Usage: {detailed_health.get('performance', {}).get('memory_usage')}%")
                    print(f"   CPU Usage: {detailed_health.get('performance', {}).get('cpu_usage')}%")
                    
                    return {"success": True, "health": health_data, "detailed": detailed_health}
                
            print(f"❌ Health Check Failed: {response.status_code}")
            return {"success": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ Health Check Exception: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


async def main():
    """Run all communication flow tests"""
    
    tester = WebhookTester()
    results = {}
    
    try:
        # Test Health Check First
        print("🏥 Pre-flight Health Check")
        health_result = await tester.test_health_check()
        results["health_check"] = health_result
        
        if not health_result.get("success"):
            print("\n❌ Health check failed - server may not be running!")
            print("Please ensure:")
            print("1. VPS server is running on the correct port")
            print("2. API token is correct")
            print("3. Redis is running and accessible")
            return results
        
        # Test Flow 1: Start Booking
        flow1_result = await tester.test_flow_1_start_booking()
        results["flow_1_start_booking"] = flow1_result
        
        if not flow1_result.get("success"):
            print("\n❌ Flow 1 failed - cannot continue with other tests")
            return results
        
        job_id = flow1_result.get("job_id")
        print(f"\n📋 Job ID for remaining tests: {job_id}")
        
        # Test Flow 2: Status Updates (run in parallel with QR polling)
        await asyncio.sleep(2)  # Give job time to start
        
        # Test Flow 3: QR Code Polling (parallel with status)
        flow2_task = asyncio.create_task(tester.test_flow_2_status_updates(job_id))
        flow3_task = asyncio.create_task(tester.test_flow_3_qr_polling(job_id))
        
        # Wait for both to complete
        flow2_result, flow3_result = await asyncio.gather(flow2_task, flow3_task)
        
        results["flow_2_status_updates"] = flow2_result
        results["flow_3_qr_polling"] = flow3_result
        
        # Test Job Cancellation (if job is still running)
        if job_id and flow2_result.get("final_status") not in ['completed', 'failed', 'cancelled']:
            await asyncio.sleep(1)
            cancel_result = await tester.test_job_cancellation(job_id)
            results["job_cancellation"] = cancel_result
        
        return results
        
    finally:
        await tester.close()


def print_summary(results: Dict[str, Any]):
    """Print test summary"""
    
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result.get("success"))
    
    for test_name, result in results.items():
        status = "✅ PASS" if result.get("success") else "❌ FAIL"
        error = f" - {result.get('error')}" if result.get("error") else ""
        print(f"{status} {test_name.replace('_', ' ').title()}{error}")
    
    print(f"\nResults: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 All tests passed! Communication flows are working correctly.")
        print("\nYour VPS automation server is ready for:")
        print("- Frontend integration with Lovable")
        print("- Supabase webhook communication") 
        print("- Real-time QR code streaming")
        print("- Status updates and monitoring")
    else:
        print("\n⚠️ Some tests failed. Check the errors above and:")
        print("1. Ensure the VPS server is running")
        print("2. Check API token configuration")
        print("3. Verify Redis is accessible")
        print("4. Review server logs for errors")


if __name__ == "__main__":
    print("Starting VPS Automation Server Communication Flow Tests...")
    
    try:
        results = asyncio.run(main())
        print_summary(results)
    except KeyboardInterrupt:
        print("\n\n🛑 Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test suite failed with error: {e}")
        sys.exit(1) 