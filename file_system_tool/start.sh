#!/bin/bash

echo "Starting File System Recovery Tool..."

# Start backend
echo "Starting backend server..."
python -m uvicorn backend.src.api.main:app --reload --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend
echo "Starting frontend server..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo "Application started!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for Ctrl+C
wait

# Cleanup
kill $BACKEND_PID $FRONTEND_PID
