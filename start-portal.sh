#!/bin/bash
# Version: 0.1.0
# Start Minis Web Portal
# This script manages the HTTP server and API service

# Kill existing processes
pkill -f "web-portal-api.py" 2>/dev/null
# Keep the HTTP server on 8080 (it's the main file server)

# Start API on port 8765
nohup python3 /var/minis/shared/web-portal-api.py > /tmp/portal-api.log 2>&1 &
API_PID=$!
echo "Minis Portal API started (PID: $API_PID) on port 8765"

# Verify
sleep 2
if curl -sS http://localhost:8765/api/dashboard > /dev/null 2>&1; then
    echo "✅ API is running"
else
    echo "❌ API failed to start"
    cat /tmp/portal-api.log | head -10
fi