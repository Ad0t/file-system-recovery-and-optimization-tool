# 🛡️ File Guardian — File System Recovery & Optimization Simulator

A full-stack, highly interactive web application that simulates Operating System file-system mechanics. Visualize disk allocation in real time, manage files and directories, stress-test cache algorithms, inject crash faults, and run automated recovery and defragmentation — all through a modern browser-based UI.

---

## 🏗️ Architecture & Tech Stack

### Backend — Python / FastAPI
| Layer | Details |
|---|---|
| **Framework** | Python 3.10+, FastAPI, Uvicorn |
| **Core Engine** | Pure-Python simulation of Disk, FAT, Inodes, Free-Space Manager, and Journaling |
| **Recovery** | Crash Simulator, Recovery Manager, FSCK, Journal Replay |
| **Optimization** | Defragmenter, Cache Manager (LRU / LFU / FIFO), Performance Analyzer |
| **API** | REST + versioned routes under `/api/v1/` |

### Frontend — React / TypeScript / Vite
| Layer | Details |
|---|---|
| **Framework** | React 18, TypeScript, Vite 8 |
| **Styling** | Tailwind CSS, shadcn/ui (Radix UI primitives) |
| **State** | TanStack Query (server state), custom `useFileSystem` hook |
| **Visualizations** | Recharts (performance charts), Framer Motion (animations) |
| **Notifications** | Sonner (toast system) |

---

## 📂 Project Structure

```text
file-guardian/                      # Repository root
│
├── backend/                        # Python FastAPI backend
│   ├── requirements.txt            # Python dependencies
│   ├── api/                        # REST API layer
│   │   ├── main.py                 # FastAPI app entry point
│   │   ├── state.py                # Shared simulator state (singleton)
│   │   ├── routes/                 # Route modules
│   │   │   ├── files.py            # File & directory CRUD
│   │   │   ├── disk.py             # Block I/O & disk operations
│   │   │   ├── recovery.py         # Crash inject, FSCK, journal replay
│   │   │   ├── optimization.py     # Defragmentation & file placement
│   │   │   ├── metrics.py          # Cache & performance metrics
│   │   │   ├── state.py            # Simulator state snapshot
│   │   │   └── system.py           # System-level utilities
│   │   └── schemas/                # Pydantic request/response models
│   ├── core/                       # Core file system simulation
│   │   ├── disk.py                 # Raw block storage emulation
│   │   ├── file_allocation_table.py# FAT with Contiguous/Linked/Indexed alloc
│   │   ├── inode.py                # Inode table management
│   │   ├── journal.py              # Write-ahead journaling
│   │   ├── directory.py            # Directory tree operations
│   │   └── free_space.py           # Free space bitmap manager
│   ├── recovery/                   # Recovery & optimization engines
│   │   ├── crash_simulator.py      # Physical / Structural / Transactional faults
│   │   ├── recovery_manager.py     # FSCK, quarantine, journal-based recovery
│   │   ├── cache_manager.py        # LRU, LFU, FIFO cache algorithms
│   │   ├── defragmenter.py         # Block compaction & file relocation
│   │   └── performance_analyzer.py # I/O benchmarking & metrics
│   ├── utils/                      # Shared constants & configuration
│   └── data/                       # Persistent disk image storage
│
├── src/                            # React TypeScript frontend (Vite root)
│   ├── components/                 # UI components
│   │   ├── ControlPanel.tsx        # Main operation panel (create, delete, read)
│   │   ├── DiskMap.tsx             # Interactive block grid visualization
│   │   ├── CacheVisualizer.tsx     # Cache state & hit/miss display
│   │   ├── CachePanel.tsx          # Cache algorithm selector & controls
│   │   ├── BenchmarkPanel.tsx      # I/O benchmarking controls & results
│   │   ├── DirectoryTree.tsx       # File system tree view
│   │   ├── FsckPanel.tsx           # FSCK & recovery controls
│   │   ├── JournalLog.tsx          # Transaction journal log viewer
│   │   ├── StatsBar.tsx            # Live disk usage stats
│   │   └── ui/                     # shadcn/ui base components
│   ├── pages/
│   │   ├── Index.tsx               # Main simulator page (dashboard)
│   │   └── NotFound.tsx            # 404 page
│   ├── hooks/
│   │   ├── useFileSystem.ts        # Core hook — all API calls & WS events
│   │   ├── use-toast.ts            # Toast notification hook
│   │   └── use-mobile.tsx          # Responsive breakpoint hook
│   ├── lib/                        # Utility helpers
│   ├── App.tsx                     # Router & layout shell
│   ├── main.tsx                    # React DOM entry point
│   └── index.css                   # Global styles & Tailwind directives
│
├── public/                         # Static assets
├── index.html                      # Vite HTML template
├── vite.config.ts                  # Vite build configuration
├── tailwind.config.ts              # Tailwind CSS theme
├── tsconfig.json                   # TypeScript config
├── package.json                    # Node.js dependencies & scripts
└── .gitignore
```

---

## 🚀 Installation & Setup

> **Prerequisites:** Python 3.10+ and Node.js 18+ must be installed.

### Step 1 — Backend (FastAPI)

```powershell
# Navigate to the backend directory
cd backend

# (Recommended) Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Start the FastAPI server on port 8000
# Run from inside the backend/ directory
python -m uvicorn api.main:app --reload
```

### Step 2 — Frontend (React / Vite)

Open a **new** terminal and run from the **repository root**:

```powershell
# Install Node modules
npm install

# Start the Vite dev server
npm run dev
```

---

## 🌐 Accessing the Application

| Service | URL |
|---|---|
| **Frontend UI** | http://localhost:5173 |
| **Backend API** | http://localhost:8000 |
| **Swagger Docs** | http://localhost:8000/docs |
| **Health Check** | http://localhost:8000/health |

---

## ✨ Core Features

### 💾 File & Disk Management
- Create files of arbitrary sizes using **Contiguous**, **Linked**, or **Indexed** allocation strategies
- Interactive **DiskMap** — a live block-grid that highlights which blocks each file occupies, with hover tooltips and color coding by allocation type
- **Directory Tree** view for navigating the simulated file hierarchy
- Real-time **StatsBar** showing used/free blocks, fragmentation level, and total capacity

### 📦 Cache Algorithms
- Switch between **LRU** (Least Recently Used), **LFU** (Least Frequently Used), and **FIFO** cache eviction policies
- **CacheVisualizer** displays current cache slots, hit/miss ratio, and eviction history
- Trigger file reads from the UI to see policy behavior in action

### ⚡ I/O Benchmarking
- **BenchmarkPanel** runs configurable read/write batches against the simulated disk
- Captures throughput (ops/sec), latency, and cache hit rates per batch
- Results charted in real time with Recharts

### 💥 Crash Simulation
Four fault injection categories:
| Category | Examples |
|---|---|
| **Physical** | Bit-flips, bad-block failures |
| **Structural** | Broken FAT chains, corrupted inodes |
| **Transactional** | Incomplete writes, torn transactions |
| **Scenario** | Power-loss mid-write, sudden unmount |

### 🔧 Recovery & Repair
- **FSCK** — scans for orphaned blocks, broken chains, and inode inconsistencies; auto-repairs what it can
- **Journal Replay** — redo/undo committed and uncommitted transactions from the write-ahead log
- **Quarantine** — isolate irrecoverable blocks to prevent further corruption
- Full **recovery log** streamed to the UI in real time

### 🧩 Defragmentation
- Compact fragmented files by relocating scattered blocks to contiguous regions
- Before/after visualization on the DiskMap to illustrate improvement
- Configurable optimization strategy (first-fit, best-fit relocation)

---

## 🛠️ Development Scripts

### Frontend
```powershell
npm run dev          # Start Vite dev server with HMR
npm run build        # Production bundle
npm run test         # Run Vitest unit tests
npm run lint         # ESLint check
```

### Backend
```powershell
# From backend/ directory with venv active
python -m uvicorn api.main:app --reload        # Dev server
python -m pytest                               # Run test suite (if tests present)
```

---

## 📡 API Overview

All routes are prefixed with `/api/v1/`.

| Router | Prefix | Responsibility |
|---|---|---|
| `files_router` | `/api/v1/fs` | File & directory CRUD |
| `disk_router` | `/api/v1/disk` | Raw block operations |
| `recovery_router` | `/api/v1/recovery` | Crash injection, FSCK, journal |
| `optimization_router` | `/api/v1/optimization` | Defragmentation |
| `metrics_router` | `/api/v1/metrics` | Cache & performance stats |
| `state_router` | `/api/v1/state` | Full simulator state snapshot |
| `system_router` | `/api/v1/system` | System utilities |

Interactive API documentation is available at **http://localhost:8000/docs** (Swagger UI).
