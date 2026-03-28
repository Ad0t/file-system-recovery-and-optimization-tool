"""
run_gui.py — Entry point for the File System Recovery and Optimization Tool.

Run from the project root:

    python run_gui.py
"""

import logging
import sys
import os

# Ensure the project root is on sys.path so `from src.…` imports work.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

from src.ui.main_window import MainWindow

def main():
    # Launch the unified main window
    app = MainWindow(total_blocks=1024, block_size=512)
    
    # Optional: seed some initial data so the visualizers aren't empty
    _seed_initial_data(app)

    print("\n🚀  GUI is running.  Close the window to exit.\n")
    app.run()


def _seed_initial_data(app):
    """Create some sample files so the visualization is immediately useful."""
    from src.core.inode import Inode
    
    # Create directories
    app.dir_tree.create_directory("/projects")
    app.dir_tree.create_directory("/projects/src")
    app.dir_tree.create_directory("/tmp")

    # Create files
    files = [
        ("/projects/readme.txt", 1),
        ("/projects/src/main.py", 2),
        ("/projects/src/utils.py", 3),
        ("/tmp/cache.dat", 4),
    ]

    for filepath, inode_num in files:
        blocks = [10 + inode_num, 20 + inode_num]
        
        # Allocate blocks
        for b in blocks:
            app.fsm.bitmap[b] = 1
        
        # Add to FAT
        app.fat.file_to_blocks[inode_num] = blocks
        for b in blocks:
            app.fat.block_to_file[b] = inode_num
            
        # Add to Journal
        txn = app.journal.begin_transaction("WRITE", {"inode": inode_num, "blocks": blocks})
        app.journal.commit_transaction(txn)
        
        # Write to Cache/Disk
        app.cache.put(blocks[0], f"DATA_{inode_num}".encode("utf-8").ljust(512, b"\x00"))
        
        # Create Inode
        inode = Inode(inode_number=inode_num, file_type="file", size=len(blocks) * 512)
        app.dir_tree.create_file(filepath, inode)

    app.inode_counter = 5
    app._refresh_dashboard()

if __name__ == "__main__":
    main()
