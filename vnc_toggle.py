#!/usr/bin/env python3
"""
VNC Monitoring Toggle - Enable/disable VNC monitoring for live job debugging
"""
import sys
import os
from pathlib import Path

def update_env_file(enable_vnc: bool):
    """Update .env file with VNC monitoring setting"""
    
    env_file = Path(".env")
    
    if not env_file.exists():
        print("❌ .env file not found!")
        print("Please run this script from the backend directory")
        return False
    
    # Read current .env file
    lines = []
    with open(env_file, 'r') as f:
        lines = f.readlines()
    
    # Update or add VNC monitoring setting
    vnc_line = f"VNC_MONITORING_ENABLED={'true' if enable_vnc else 'false'}\n"
    display_line = "VNC_DISPLAY=:99\n"
    
    # Check if settings already exist
    updated_vnc = False
    updated_display = False
    
    for i, line in enumerate(lines):
        if line.startswith('VNC_MONITORING_ENABLED='):
            lines[i] = vnc_line
            updated_vnc = True
        elif line.startswith('VNC_DISPLAY='):
            lines[i] = display_line
            updated_display = True
    
    # Add settings if they don't exist
    if not updated_vnc:
        lines.append(vnc_line)
    if not updated_display:
        lines.append(display_line)
    
    # Write back to file
    with open(env_file, 'w') as f:
        f.writelines(lines)
    
    return True

def show_status():
    """Show current VNC monitoring status"""
    
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found!")
        return
    
    vnc_enabled = False
    vnc_display = ":99"
    
    with open(env_file, 'r') as f:
        for line in f:
            if line.startswith('VNC_MONITORING_ENABLED='):
                vnc_enabled = line.strip().split('=')[1].lower() == 'true'
            elif line.startswith('VNC_DISPLAY='):
                vnc_display = line.strip().split('=')[1]
    
    print("\n🔍 Current VNC Monitoring Status:")
    print("=" * 40)
    status_emoji = "✅" if vnc_enabled else "❌"
    print(f"{status_emoji} VNC Monitoring: {'ENABLED' if vnc_enabled else 'DISABLED'}")
    if vnc_enabled:
        print(f"📺 VNC Display: {vnc_display}")
        print(f"🌐 Web VNC URL: http://87.106.247.92:8081/vnc.html")
        print(f"🔑 VNC Password: vnc123")
    print("=" * 40)

def main():
    """Main VNC toggle function"""
    
    print("🖥️  VNC Monitoring Toggle")
    print("=" * 40)
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "on" or command == "enable":
            print("🔄 Enabling VNC monitoring...")
            if update_env_file(True):
                print("✅ VNC monitoring ENABLED!")
                print("📺 All new frontend jobs will be visible on VNC")
                print("🌐 Connect to: http://87.106.247.92:8081/vnc.html")
                print("🔑 Password: vnc123")
                print("\n⚠️  NOTE: Restart the server for changes to take effect!")
            else:
                print("❌ Failed to enable VNC monitoring")
        
        elif command == "off" or command == "disable":
            print("🔄 Disabling VNC monitoring...")
            if update_env_file(False):
                print("✅ VNC monitoring DISABLED")
                print("🔒 Jobs will run in headless mode (production)")
                print("\n⚠️  NOTE: Restart the server for changes to take effect!")
            else:
                print("❌ Failed to disable VNC monitoring")
        
        elif command == "status":
            show_status()
        
        else:
            print(f"❌ Unknown command: {command}")
            print("Usage: python vnc_toggle.py [on|off|status]")
    
    else:
        # Interactive mode
        show_status()
        print("\n📋 What would you like to do?")
        print("1. Enable VNC monitoring")
        print("2. Disable VNC monitoring")
        print("3. Show status")
        print("4. Exit")
        
        choice = input("\n🔢 Enter choice (1-4): ").strip()
        
        if choice == "1":
            if update_env_file(True):
                print("\n✅ VNC monitoring ENABLED!")
                print("📺 All new frontend jobs will be visible on VNC")
                print("🌐 Connect to: http://87.106.247.92:8081/vnc.html")
                print("🔑 Password: vnc123")
                print("\n⚠️  NOTE: Restart the server for changes to take effect!")
        
        elif choice == "2":
            if update_env_file(False):
                print("\n✅ VNC monitoring DISABLED")
                print("🔒 Jobs will run in headless mode (production)")
                print("\n⚠️  NOTE: Restart the server for changes to take effect!")
        
        elif choice == "3":
            show_status()
        
        elif choice == "4":
            print("👋 Goodbye!")
        
        else:
            print("❌ Invalid choice")

if __name__ == "__main__":
    main() 