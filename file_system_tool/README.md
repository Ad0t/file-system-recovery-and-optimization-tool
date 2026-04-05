# File System Recovery and Optimization Tool (Web Version)

Full-stack web application for file system simulation, crash recovery, and performance optimization.

## Architecture

- **Backend**: Python + FastAPI + WebSockets
- **Frontend**: React + TypeScript + Tailwind CSS
- **Real-time Updates**: WebSocket communication

## Quick Start

### Option 1: Using Startup Scripts

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

**Windows:**
```bash
start.bat
```

### Option 2: Manual Setup

**Backend:**
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn src.api.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Option 3: Docker
```bash
docker-compose up
```

## Access

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws

## Features

- File and directory management
- Real-time disk visualization
- Crash simulation and recovery
- Performance monitoring with live charts
- Defragmentation
- Caching strategies
- Comprehensive logging

## Development

**Backend:**
- FastAPI for REST API
- WebSockets for real-time updates
- Modules 1 & 2 for file system logic

**Frontend:**
- React 18 with TypeScript
- Zustand for state management
- Recharts for visualizations
- Tailwind CSS for styling

## Testing

**Backend:**
```bash
cd backend
pytest tests/
```

**Frontend:**
```bash
cd frontend
npm run test
```

**API Testing:**
Visit http://localhost:8000/docs for interactive API testing.

## Deployment

**Build for production:**

Backend:
```bash
cd backend
pip install gunicorn
gunicorn src.api.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

Frontend:
```bash
cd frontend
npm run build
# Serve dist/ folder with any static server
```

## Project Structure

```
file_system_tool/
├── backend/           # Python backend
│   ├── src/
│   │   ├── core/     # Module 1
│   │   ├── recovery/ # Module 2
│   │   └── api/      # REST API
│   └── tests/
│
└── frontend/          # React frontend
    ├── src/
    │   ├── components/
    │   ├── api/
    │   └── store/
    └── public/
```
