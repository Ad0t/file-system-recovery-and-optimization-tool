# File System Simulator

A Python-based file system simulator that models core OS-level file system components for educational and experimental purposes.

## Project Structure

```
file_system_tool/
├── src/
│   ├── core/
│   │   ├── disk.py                  # Simulated block-based disk storage
│   │   ├── inode.py                 # Inode and inode table management
│   │   ├── directory.py             # Hierarchical directory structure
│   │   ├── free_space.py            # Free space bitmap management
│   │   ├── file_allocation_table.py # FAT-style block chain tracking
│   │   └── journal.py               # Journaling for crash recovery
│   └── utils/
│       ├── constants.py             # System-wide configuration constants
│       └── helpers.py               # Utility functions
├── tests/                           # Unit tests for all core modules
├── data/                            # Data directory for simulation files
├── requirements.txt
└── README.md
```

## Components

| Module | Description |
|--------|-------------|
| **Disk** | Simulates block-based storage with read/write/clear operations |
| **Inode** | Manages file/directory metadata (permissions, timestamps, block pointers) |
| **Directory** | Hierarchical directory structure with entry management |
| **FreeSpaceManager** | Bitmap-based block allocation tracking using `bitarray` |
| **FileAllocationTable** | FAT-style linked block chain management |
| **Journal** | Operation logging for crash recovery with commit/rollback |

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
cd file_system_tool
pytest tests/ -v
```

## Running Tests

```bash
pytest tests/ -v
```

## License

This project is for educational purposes.
