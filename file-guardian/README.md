# File System Recovery and Optimization Tool (File Guardian)

A full-stack, highly interactive web application designed to simulate Operating System file-system mechanics. It visually demonstrates disk allocation, real-time file management, caching strategies, crash simulations, and recovery/defragmentation processes.

---

## 🏗️ Project Architecture & Technologies

- **Backend**: Python 3.10+, FastAPI, WebSockets (`backend/src/api`)
- **Core Logic**: Pure Python simulating Disk, FAT, Inodes, Journaling, & Crash Recovery
- **Frontend**: React 18, TypeScript, Tailwind CSS, Vite (`frontend/`)
- **State Management**: Zustand
- **Visualizations**: Recharts, Framer Motion

---

## 📂 Detailed File Structure

```text
file_system_tool/
├── requirements.txt            # Python dependencies
├── docker-compose.yml          # Container orchestration
├── start.bat / start.sh        # Quick-start scripts
├── cli.py / demo.py            # Command-line interface and testing scripts
│
├── backend/                    # Python FastAPI Backend
│   ├── src/
│   │   ├── api/                # REST API routes and WebSockets
│   │   ├── core/               # File System Core (Disk, FAT, Inode, Journal)
│   │   ├── recovery/           # Crash Simulation, CacheManager, Defragmenter
│   │   └── utils/              # Shared constants and config
│   │
│   └── tests/                  # Pytest unit & integration tests
│
└── frontend/                   # React TypeScript Frontend
    ├── package.json            # Node.js dependencies
    ├── vite.config.ts          # Vite build config
    ├── tailwind.config.ts      # Tailwind CSS theming
    ├── public/                 # Static assets
    └── src/
        ├── api/                # Axios/Fetch client and WebSocket hooks
        ├── components/         # ControlPanel, DiskMap, CacheVisualizer, etc.
        ├── hooks/              # Custom React hooks
        ├── store/              # Zustand global state (fileSystemStore)
        ├── types/              # TypeScript interfaces
        ├── App.tsx             # Main Layout and Router
        └── main.tsx            # React DOM Entry point
```

---

## 🚀 Installation & Setup Steps

Follow these instructions to get the simulator running locally on your own system.

### Option 1: Quick Start (Automated)

If you have Python and Node.js already installed, you can use the provided startup scripts to launch both the frontend and backend simultaneously.

**Windows:**
```powershell
# Double-click the file or run in terminal
.\start.bat
```

**Linux / Mac:**
```bash
chmod +x start.sh
./start.sh
```

### Option 2: Manual Setup (Recommended for Development)

Ensure you have **Python 3.10+** and **Node.js 18+** installed before proceeding.

**Step 1: Start the Backend (FastAPI)**
Open a terminal and navigate to the project root:
```bash
# Navigate to backend
cd backend

# (Optional but recommended) Create and activate a virtual environment
python -m venv venv
# On Windows: venv\Scripts\activate
# On Mac/Linux: source venv/bin/activate

# Install Python dependencies
pip install -r ../requirements.txt

# Start the FastAPI server on port 8000
python -m uvicorn src.api.main:app --reload
```

**Step 2: Start the Frontend (React/Vite)**
Open a **new** terminal window:
```bash
# Navigate to frontend
cd frontend

# Install Node modules
npm install

# Start the Vite development server
npm run dev
```

### Option 3: Docker (Containerized)
If you have Docker Desktop installed, you can spin up the entire stack without installing local dependencies.
```bash
docker-compose up --build
```

---

## 🌐 Accessing the Application

Once running, you can access the different components at:

- **Frontend Application**: [http://localhost:5173](http://localhost:5173) (Your main interactive UI)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **WebSocket Endpoint**: `ws://localhost:8000/ws`

---

## 🔧 Core Features

- **File/Directory Management**: Create files of varying sizes using Contiguous, Linked, or Indexed Allocation strategies.
- **Cache Algorithms**: Interactive read/write performance testing utilizing `LRU`, `LFU`, and `FIFO` queue strategies via the backend CacheManager.
- **Crash Simulators**: Inject random physical, structural, or transactional faults directly into the disk image.
- **File System Check (FSCK)**: Run automated recovery routines to detect orphaned blocks and broken chains.
- **Journal Replaying**: Test transaction undo/redo logging behavior.
- **Defragmentation**: Collapse fragmented blocks to improve simulated read/write speeds.
