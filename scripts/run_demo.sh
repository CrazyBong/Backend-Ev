#!/bin/bash
echo "====================================="
echo "⚡ EVChargeFinder Hackathon Demo Mode ⚡"
echo "====================================="

echo "[1/2] Activating virtual environment..."
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "🚨 Error: Virtual environment not found at venv/! Please create and install dependencies first."
    exit 1
fi

echo "[2/2] Starting Backend with strictly 1 worker for WebSocket bridging..."
# WARNING: We use exactly 1 worker.
# If we used 4 workers (like in prod without Redis PubSub), the IoT webhook might 
# hit Worker 2 while the mobile app is connected to Worker 1, breaking realtime events!

uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
