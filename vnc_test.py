#!/usr/bin/env python3
"""
VNC Test Script - Verify that browser appears on VNC display
"""
import asyncio
import os
from playwright.async_api import async_playwright

# Set display for VNC
os.environ['DISPLAY'] = ':99'

async def test_vnc_browser():
    """Test browser visibility through VNC"""
    print("🖥️  Starting VNC Browser Test...")
    print("📺 VNC Access: Connect to 87.106.247.92:5900 (no password)")
    print("⏳ Opening browser on VNC display...")
    
    async with async_playwright() as p:
        # Launch browser in NON-headless mode for VNC visibility
        browser = await p.chromium.launch(
            headless=False,  # IMPORTANT: Must be False for VNC visibility
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security'
            ]
        )
        
        # Create context
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        
        # Create page
        page = await context.new_page()
        
        print("🌐 Navigating to Trafikverket...")
        await page.goto("https://fp.trafikverket.se/boka/#/")
        
        print("✅ Browser should now be visible on VNC!")
        print("🔍 You should see the Trafikverket booking page")
        print("⏰ Keeping browser open for 60 seconds...")
        
        # Keep browser open for inspection
        await asyncio.sleep(60)
        
        print("🔄 Cleaning up...")
        await browser.close()
        
    print("✅ VNC test completed!")

if __name__ == "__main__":
    asyncio.run(test_vnc_browser()) 