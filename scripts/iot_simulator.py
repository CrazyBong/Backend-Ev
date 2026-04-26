import sys
import os
import json
import httpx
import argparse
from datetime import datetime

# Default configuration
DEFAULT_BASE_URL = "http://localhost:8000"
IOT_API_KEY = os.environ.get("IOT_API_KEY", "dummy-fallback-key")

def send_heartbeat(slot_id: str, status: str, draw_kw: float, base_url: str):
    url = f"{base_url}/v1/iot/heartbeat"
    headers = {
        "X-IoT-Key": IOT_API_KEY, 
        "Content-Type": "application/json"
    }
    payload = {
        "slot_id": slot_id,
        "status": status,
        "current_draw_kw": draw_kw
    }
    
    print(f"[{datetime.now().time()}] Sending heartbeat to {url}...")
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! Slot: {data.get('slot_id')} -> Status: {data.get('new_status')}")
        else:
            print(f"❌ Failed ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"🚨 Connection error: {e}")

def get_status_label(cmd: str):
    if cmd == "start":
        return "CHARGING"
    elif cmd == "stop":
        return "AVAILABLE"
    elif cmd == "fault":
        return "FAULTED"
    return cmd.upper()

def interactive_mode(base_url: str):
    print("====================================")
    print("🔌 EV Hackathon IoT Simulator 🔌")
    print("====================================")
    print("Target backend:", base_url)
    print("Commands:")
    print("  start <slot_id>  - Simulates car plugged in (7.2kW)")
    print("  stop  <slot_id>  - Simulates car unplugged (0.0kW)")
    print("  fault <slot_id>  - Simulates hardware fault")
    print("  exit             - Quit simulator")
    print("------------------------------------")
    
    while True:
        try:
            user_input = input("iot> ").strip().split()
            if not user_input:
                continue
                
            cmd = user_input[0].lower()
            if cmd == "exit" or cmd == "quit":
                break
                
            if len(user_input) < 2:
                print("Usage: <command> <slot_id> (e.g. start 123e4567-e89b-12d3... )")
                continue
                
            slot_id = user_input[1]
            status = get_status_label(cmd)
            
            draw_kw = 7.2 if status == "CHARGING" else 0.0
            
            send_heartbeat(slot_id, status, draw_kw, base_url)
            
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IoT Hardware Simulator for EV Backend")
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help="Base URL of the backend (e.g. http://192.168.1.5:8000)")
    parser.add_argument("--slot", help="Slot ID (UUID) to update instantly")
    parser.add_argument("--status", choices=["start", "stop", "fault"], help="Change to broadcast")
    
    args = parser.parse_args()
    
    if args.slot and args.status:
        status = get_status_label(args.status)
        draw = 7.2 if status == "CHARGING" else 0.0
        send_heartbeat(args.slot, status, draw, args.url)
    else:
        interactive_mode(args.url)
