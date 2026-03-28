"""
main_window.py - Main Tkinter GUI application for the File System Simulator.

Provides a comprehensive graphical interface for interacting with the
simulated file system, including:
  - Disk status and metrics dashboard
  - File operations (create, delete, list)
  - Crash injection and recovery
  - Defragmentation controls
  - Performance analysis and reporting
  - Disk layout visualization
  - Cache management
  - Journal/transaction viewing

Usage::

    from src.ui.main_window import MainWindow
    app = MainWindow()
    app.run()
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, Any
import sys
import os
import threading
import time
import logging

# Import all file system components
from src.core.disk import Disk
from src.core.free_space import FreeSpaceManager
from src.core.inode import Inode
from src.core.directory import DirectoryTree
from src.core.file_allocation_table import FileAllocationTable
from src.core.journal import Journal

from src.recovery.crash_simulator import CrashSimulator
from src.recovery.recovery_manager import RecoveryManager
from src.recovery.defragmenter import Defragmenter
from src.recovery.cache_manager import CacheManager
from src.recovery.performance_analyzer import PerformanceAnalyzer

from src.ui.disk_visualizer import DiskVisualizer
from src.ui.performance_dashboard import PerformanceDashboard
from src.ui.tree_view import TreeView

logger = logging.getLogger(__name__)


# ===================================================================== #
#  Color Palette & Style Constants
# ===================================================================== #

COLORS = {
    "bg_dark":         "#1a1a2e",
    "bg_panel":        "#16213e",
    "bg_card":         "#0f3460",
    "accent_primary":  "#e94560",
    "accent_green":    "#00d2a0",
    "accent_yellow":   "#f5c542",
    "accent_blue":     "#4fc3f7",
    "accent_orange":   "#ff8c42",
    "text_primary":    "#e0e0e0",
    "text_secondary":  "#a0a0b0",
    "text_header":     "#ffffff",
    "border":          "#2a2a4a",
    "success":         "#4caf50",
    "warning":         "#ff9800",
    "error":           "#f44336",
    "free_block":      "#2e7d32",
    "used_block":      "#1565c0",
    "corrupt_block":   "#c62828",
}

FONT_HEADER  = ("Segoe UI", 14, "bold")
FONT_SUBHEAD = ("Segoe UI", 11, "bold")
FONT_BODY    = ("Segoe UI", 10)
FONT_SMALL   = ("Segoe UI", 9)
FONT_MONO    = ("Consolas", 10)
FONT_MONO_SM = ("Consolas", 9)


# ===================================================================== #
#  MainWindow
# ===================================================================== #

class MainWindow:
    """
    Main application window for the File System Simulator GUI.

    Initializes all 10 core and recovery modules, provides tabbed
    panels for disk status, file operations, crash/recovery workflows,
    defragmentation, performance analytics, and cache management.
    """

    # ----------------------------------------------------------------- #
    #  Initialization
    # ----------------------------------------------------------------- #

    def __init__(self, total_blocks: int = 1024, block_size: int = 512):
        """
        Create the main window and initialize file system components.

        Args:
            total_blocks: Number of blocks for the simulated disk.
            block_size: Size of each block in bytes.
        """
        # ---- Tk root ----
        self.root = tk.Tk()
        self.root.title("🗄️ File System Recovery & Optimization Tool")
        self.root.geometry("1280x800")
        self.root.minsize(1024, 680)
        self.root.configure(bg=COLORS["bg_dark"])

        # ---- Initialize file system components ----
        self._init_file_system(total_blocks, block_size)

        # ---- Internal state ----
        self.inode_counter = 1  # auto-increment ID for new files

        # ---- Build the UI ----
        self._configure_styles()
        self._build_menu_bar()
        self._build_header()
        self._build_notebook()
        self._build_status_bar()

        # ---- Populate initial data ----
        self._refresh_dashboard()

    # ----------------------------------------------------------------- #
    #  File system bootstrap
    # ----------------------------------------------------------------- #

    def _init_file_system(self, total_blocks: int, block_size: int) -> None:
        """Create and wire up all core + recovery modules."""
        self.disk = Disk(total_blocks=total_blocks, block_size=block_size)
        self.fsm  = FreeSpaceManager(total_blocks=total_blocks)
        self.fat  = FileAllocationTable(allocation_method="indexed")
        self.journal = Journal()
        self.dir_tree = DirectoryTree()

        self.fs_components: Dict[str, Any] = {
            "disk":           self.disk,
            "fsm":            self.fsm,
            "fat":            self.fat,
            "journal":        self.journal,
            "directory_tree": self.dir_tree,
        }

        self.cache = CacheManager(self.fs_components, cache_size=100, strategy="ARC")
        self.fs_components["cache"] = self.cache

        self.defrag       = Defragmenter(self.fs_components)
        self.recovery_mgr = RecoveryManager(self.fs_components)
        self.analyzer     = PerformanceAnalyzer(self.fs_components)
        self.simulator    = CrashSimulator(random_seed=42)

        logger.info("All file system components initialized for GUI.")

    # ----------------------------------------------------------------- #
    #  Styling
    # ----------------------------------------------------------------- #

    def _configure_styles(self) -> None:
        """Apply a consistent dark-mode ttk theme."""
        style = ttk.Style(self.root)
        style.theme_use("clam")

        # General widget background
        style.configure(".", background=COLORS["bg_dark"],
                         foreground=COLORS["text_primary"],
                         font=FONT_BODY)

        # Notebook (tab bar)
        style.configure("TNotebook", background=COLORS["bg_dark"],
                         borderwidth=0)
        style.configure("TNotebook.Tab",
                         background=COLORS["bg_panel"],
                         foreground=COLORS["text_secondary"],
                         padding=[14, 6],
                         font=FONT_SUBHEAD)
        style.map("TNotebook.Tab",
                   background=[("selected", COLORS["bg_card"])],
                   foreground=[("selected", COLORS["accent_blue"])])

        # Frame
        style.configure("TFrame", background=COLORS["bg_dark"])
        style.configure("Card.TFrame", background=COLORS["bg_panel"],
                         relief="flat")

        # Label
        style.configure("TLabel", background=COLORS["bg_dark"],
                         foreground=COLORS["text_primary"],
                         font=FONT_BODY)
        style.configure("Header.TLabel",
                         background=COLORS["bg_dark"],
                         foreground=COLORS["text_header"],
                         font=FONT_HEADER)
        style.configure("Metric.TLabel",
                         background=COLORS["bg_panel"],
                         foreground=COLORS["accent_blue"],
                         font=("Segoe UI", 22, "bold"))
        style.configure("MetricLabel.TLabel",
                         background=COLORS["bg_panel"],
                         foreground=COLORS["text_secondary"],
                         font=FONT_SMALL)

        # Button
        style.configure("Accent.TButton",
                         background=COLORS["accent_primary"],
                         foreground="#ffffff",
                         font=FONT_BODY,
                         padding=[12, 6])
        style.map("Accent.TButton",
                   background=[("active", "#d63050")])

        style.configure("Green.TButton",
                         background=COLORS["accent_green"],
                         foreground="#000000",
                         font=FONT_BODY,
                         padding=[12, 6])
        style.map("Green.TButton",
                   background=[("active", "#00b889")])

        style.configure("Orange.TButton",
                         background=COLORS["accent_orange"],
                         foreground="#000000",
                         font=FONT_BODY,
                         padding=[12, 6])
        style.map("Orange.TButton",
                   background=[("active", "#e07830")])

        # Treeview (table)
        style.configure("Treeview",
                         background=COLORS["bg_panel"],
                         foreground=COLORS["text_primary"],
                         fieldbackground=COLORS["bg_panel"],
                         rowheight=26,
                         font=FONT_SMALL)
        style.configure("Treeview.Heading",
                         background=COLORS["bg_card"],
                         foreground=COLORS["accent_blue"],
                         font=FONT_SUBHEAD)
        style.map("Treeview",
                   background=[("selected", COLORS["bg_card"])],
                   foreground=[("selected", COLORS["text_header"])])

        # LabelFrame
        style.configure("TLabelframe",
                         background=COLORS["bg_dark"],
                         foreground=COLORS["accent_blue"],
                         font=FONT_SUBHEAD)
        style.configure("TLabelframe.Label",
                         background=COLORS["bg_dark"],
                         foreground=COLORS["accent_blue"],
                         font=FONT_SUBHEAD)

        # Progressbar
        style.configure("green.Horizontal.TProgressbar",
                         troughcolor=COLORS["bg_panel"],
                         background=COLORS["accent_green"])
        style.configure("red.Horizontal.TProgressbar",
                         troughcolor=COLORS["bg_panel"],
                         background=COLORS["accent_primary"])

    # ----------------------------------------------------------------- #
    #  Menu bar
    # ----------------------------------------------------------------- #

    def _build_menu_bar(self) -> None:
        menubar = tk.Menu(self.root, bg=COLORS["bg_panel"],
                          fg=COLORS["text_primary"],
                          activebackground=COLORS["bg_card"],
                          activeforeground=COLORS["text_header"])

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0,
                            bg=COLORS["bg_panel"],
                            fg=COLORS["text_primary"])
        file_menu.add_command(label="Save Disk State…",
                              command=self._action_save_disk)
        file_menu.add_command(label="Load Disk State…",
                              command=self._action_load_disk)
        file_menu.add_separator()
        file_menu.add_command(label="Export Performance Report…",
                              command=self._action_export_report)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0,
                             bg=COLORS["bg_panel"],
                             fg=COLORS["text_primary"])
        tools_menu.add_command(label="Format Disk",
                               command=self._action_format_disk)
        tools_menu.add_command(label="Run FSCK",
                               command=self._action_run_fsck)
        tools_menu.add_separator()
        tools_menu.add_command(label="Reset File System",
                               command=self._action_reset_fs)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0,
                            bg=COLORS["bg_panel"],
                            fg=COLORS["text_primary"])
        help_menu.add_command(label="About",
                              command=self._action_show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    # ----------------------------------------------------------------- #
    #  Header banner
    # ----------------------------------------------------------------- #

    def _build_header(self) -> None:
        header_frame = tk.Frame(self.root, bg=COLORS["bg_panel"],
                                height=52)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        title_lbl = tk.Label(
            header_frame,
            text="  🗄️  File System Recovery & Optimization Tool",
            bg=COLORS["bg_panel"],
            fg=COLORS["text_header"],
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        )
        title_lbl.pack(side="left", padx=10, fill="y")

        # Quick-refresh button in header
        refresh_btn = tk.Button(
            header_frame, text="⟳ Refresh",
            bg=COLORS["bg_card"], fg=COLORS["accent_blue"],
            font=FONT_BODY, relief="flat", cursor="hand2",
            command=self._refresh_dashboard,
        )
        refresh_btn.pack(side="right", padx=14, pady=8)

    # ----------------------------------------------------------------- #
    #  Tabbed notebook
    # ----------------------------------------------------------------- #

    def _build_notebook(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=(4, 0))

        # Tab 1 – Dashboard
        self.tab_dashboard = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_dashboard, text="  📊 Dashboard  ")
        self._build_dashboard_tab()

        # Tab 2 – File Operations
        self.tab_files = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_files, text="  📁 Files  ")
        self._build_files_tab()

        # Tab 3 – Tree View
        self.tab_tree = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_tree, text="  🌳 Tree View  ")
        self.tree_view = TreeView(self.tab_tree, self.dir_tree, fat=self.fat, fsm=self.fsm, disk=self.disk)

        # Tab 4 – Crash & Recovery
        self.tab_recovery = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_recovery, text="  💥 Crash & Recovery  ")
        self._build_recovery_tab()

        # Tab 5 – Defragmentation
        self.tab_defrag = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_defrag, text="  🛠️ Defragmentation  ")
        self._build_defrag_tab()

        # Tab 6 – Performance Dashboard
        self.tab_perf = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_perf, text="  📊 Perf Dashboard  ")
        self.perf_dashboard = PerformanceDashboard(self.tab_perf, self.analyzer)

        # Tab 7 – Block Visualizer
        self.tab_layout = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_layout, text="  🔳 Block Visualizer  ")
        self.disk_visualizer = DiskVisualizer(self.tab_layout, self.disk, self.fsm, self.fat)

        # Tab 8 – Journal
        self.tab_journal = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_journal, text="  📜 Journal  ")
        self._build_journal_tab()

    # ================================================================= #
    #  TAB 1 – Dashboard
    # ================================================================= #

    def _build_dashboard_tab(self) -> None:
        """Build the system-status dashboard with metric cards."""
        # --- Metric cards row ---
        cards_frame = ttk.Frame(self.tab_dashboard)
        cards_frame.pack(fill="x", padx=10, pady=10)

        # We store StringVars so we can update them later
        self.sv_disk_usage   = tk.StringVar(value="0.0%")
        self.sv_free_space   = tk.StringVar(value="100.0%")
        self.sv_frag         = tk.StringVar(value="0.0%")
        self.sv_cache_hit    = tk.StringVar(value="0.0%")
        self.sv_total_files  = tk.StringVar(value="0")
        self.sv_journal_txns = tk.StringVar(value="0")

        metrics = [
            ("Disk Usage",      self.sv_disk_usage,   COLORS["accent_primary"]),
            ("Free Space",      self.sv_free_space,    COLORS["accent_green"]),
            ("Fragmentation",   self.sv_frag,          COLORS["accent_yellow"]),
            ("Cache Hit Rate",  self.sv_cache_hit,     COLORS["accent_blue"]),
            ("Total Files",     self.sv_total_files,   COLORS["accent_orange"]),
            ("Journal Entries", self.sv_journal_txns,  COLORS["text_secondary"]),
        ]

        for i, (label_text, sv, color) in enumerate(metrics):
            card = tk.Frame(cards_frame, bg=COLORS["bg_panel"],
                            highlightbackground=COLORS["border"],
                            highlightthickness=1,
                            padx=14, pady=10)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            cards_frame.columnconfigure(i, weight=1)

            tk.Label(card, textvariable=sv,
                     bg=COLORS["bg_panel"], fg=color,
                     font=("Segoe UI", 20, "bold")).pack()
            tk.Label(card, text=label_text,
                     bg=COLORS["bg_panel"],
                     fg=COLORS["text_secondary"],
                     font=FONT_SMALL).pack()

        # --- Disk usage progress bar ---
        bar_frame = ttk.Frame(self.tab_dashboard)
        bar_frame.pack(fill="x", padx=16, pady=(0, 6))

        ttk.Label(bar_frame, text="Disk Capacity:").pack(side="left")
        self.pb_disk = ttk.Progressbar(bar_frame, length=400,
                                        style="green.Horizontal.TProgressbar")
        self.pb_disk.pack(side="left", padx=8, fill="x", expand=True)

        # --- Disk info text area ---
        info_frame = ttk.LabelFrame(self.tab_dashboard, text="  Disk Information  ")
        info_frame.pack(fill="both", expand=True, padx=10, pady=6)

        self.txt_disk_info = tk.Text(
            info_frame, height=14, wrap="word",
            bg=COLORS["bg_panel"], fg=COLORS["text_primary"],
            font=FONT_MONO, insertbackground=COLORS["text_primary"],
            relief="flat", state="disabled",
        )
        self.txt_disk_info.pack(fill="both", expand=True, padx=4, pady=4)

    # ================================================================= #
    #  TAB 2 – File Operations
    # ================================================================= #

    def _build_files_tab(self) -> None:
        """Create file, list files, view directory tree."""
        top = ttk.Frame(self.tab_files)
        top.pack(fill="x", padx=10, pady=10)

        # --- Create file controls ---
        create_lf = ttk.LabelFrame(top, text="  Create File  ")
        create_lf.pack(side="left", padx=(0, 10), fill="y")

        ttk.Label(create_lf, text="Blocks needed:").grid(
            row=0, column=0, padx=6, pady=4, sticky="w")
        self.sp_blocks = tk.Spinbox(
            create_lf, from_=1, to=50, width=8,
            bg=COLORS["bg_panel"], fg=COLORS["text_primary"],
            font=FONT_BODY, buttonbackground=COLORS["bg_card"])
        self.sp_blocks.grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(create_lf, text="Directory path:").grid(
            row=1, column=0, padx=6, pady=4, sticky="w")
        self.ent_file_dir = ttk.Entry(create_lf, width=22)
        self.ent_file_dir.insert(0, "/")
        self.ent_file_dir.grid(row=1, column=1, padx=6, pady=4)

        btn_create = ttk.Button(create_lf, text="Create File",
                                style="Green.TButton",
                                command=self._action_create_file)
        btn_create.grid(row=2, column=0, columnspan=2, pady=8, padx=6)

        # --- Directory tree view ---
        tree_lf = ttk.LabelFrame(top, text="  Directory Tree  ")
        tree_lf.pack(side="left", fill="both", expand=True)

        self.txt_dir_tree = tk.Text(
            tree_lf, height=8, wrap="none",
            bg=COLORS["bg_panel"], fg=COLORS["accent_green"],
            font=FONT_MONO, relief="flat", state="disabled",
        )
        self.txt_dir_tree.pack(fill="both", expand=True, padx=4, pady=4)

        btn_refresh_tree = ttk.Button(tree_lf, text="Refresh Tree",
                                       command=self._refresh_dir_tree)
        btn_refresh_tree.pack(pady=4)

        # --- File table ---
        table_lf = ttk.LabelFrame(self.tab_files, text="  Allocated Files  ")
        table_lf.pack(fill="both", expand=True, padx=10, pady=6)

        columns = ("inode", "blocks", "fragmented", "size_bytes")
        self.file_table = ttk.Treeview(table_lf, columns=columns,
                                        show="headings", height=10)
        self.file_table.heading("inode", text="Inode #")
        self.file_table.heading("blocks", text="Block List")
        self.file_table.heading("fragmented", text="Fragmented?")
        self.file_table.heading("size_bytes", text="Size (B)")
        self.file_table.column("inode", width=70, anchor="center")
        self.file_table.column("blocks", width=300)
        self.file_table.column("fragmented", width=100, anchor="center")
        self.file_table.column("size_bytes", width=100, anchor="center")
        self.file_table.pack(fill="both", expand=True, padx=4, pady=4)

        btn_bar = ttk.Frame(table_lf)
        btn_bar.pack(fill="x", padx=4, pady=4)
        ttk.Button(btn_bar, text="Refresh",
                    command=self._refresh_file_table).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Delete Selected",
                    style="Accent.TButton",
                    command=self._action_delete_file).pack(side="left", padx=4)

    # ================================================================= #
    #  TAB 3 – Crash & Recovery
    # ================================================================= #

    def _build_recovery_tab(self) -> None:
        """Crash injection controls and recovery pipeline."""
        top = ttk.Frame(self.tab_recovery)
        top.pack(fill="x", padx=10, pady=10)

        # --- Crash injection ---
        crash_lf = ttk.LabelFrame(top, text="  Inject Crash  ")
        crash_lf.pack(side="left", padx=(0, 10), fill="y")

        ttk.Label(crash_lf, text="Crash type:").grid(
            row=0, column=0, padx=6, pady=4, sticky="w")
        self.cmb_crash_type = ttk.Combobox(
            crash_lf, width=22, state="readonly",
            values=["Power Failure", "Bit Corruption",
                     "Sector Failure", "Metadata Corruption",
                     "Journal Corruption", "Random Crash"])
        self.cmb_crash_type.current(0)
        self.cmb_crash_type.grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(crash_lf, text="Affected blocks\n(comma-separated):").grid(
            row=1, column=0, padx=6, pady=4, sticky="w")
        self.ent_crash_blocks = ttk.Entry(crash_lf, width=24)
        self.ent_crash_blocks.insert(0, "11,12,13")
        self.ent_crash_blocks.grid(row=1, column=1, padx=6, pady=4)

        ttk.Button(crash_lf, text="💥 Inject Crash",
                    style="Accent.TButton",
                    command=self._action_inject_crash).grid(
            row=2, column=0, columnspan=2, padx=6, pady=8)

        # --- Recovery controls ---
        recover_lf = ttk.LabelFrame(top, text="  Recovery Actions  ")
        recover_lf.pack(side="left", fill="both", expand=True)

        ttk.Button(recover_lf, text="🔍 Analyze Crash",
                    command=self._action_analyze_crash).pack(
            fill="x", padx=10, pady=4)
        ttk.Button(recover_lf, text="🚑 Recover from Journal",
                    style="Green.TButton",
                    command=self._action_recover_journal).pack(
            fill="x", padx=10, pady=4)
        ttk.Button(recover_lf, text="🔧 Rebuild Allocation Table",
                    style="Orange.TButton",
                    command=self._action_rebuild_fat).pack(
            fill="x", padx=10, pady=4)
        ttk.Button(recover_lf, text="✅ Verify Consistency",
                    command=self._action_verify_consistency).pack(
            fill="x", padx=10, pady=4)

        # --- Log output ---
        log_lf = ttk.LabelFrame(self.tab_recovery,
                                 text="  Recovery Log  ")
        log_lf.pack(fill="both", expand=True, padx=10, pady=6)

        self.txt_recovery_log = tk.Text(
            log_lf, height=14, wrap="word",
            bg=COLORS["bg_panel"], fg=COLORS["text_primary"],
            font=FONT_MONO_SM, relief="flat",
            insertbackground=COLORS["text_primary"],
        )
        scroll_r = ttk.Scrollbar(log_lf, command=self.txt_recovery_log.yview)
        self.txt_recovery_log.configure(yscrollcommand=scroll_r.set)
        scroll_r.pack(side="right", fill="y")
        self.txt_recovery_log.pack(fill="both", expand=True, padx=4, pady=4)

    # ================================================================= #
    #  TAB 4 – Defragmentation
    # ================================================================= #

    def _build_defrag_tab(self) -> None:
        top = ttk.Frame(self.tab_defrag)
        top.pack(fill="x", padx=10, pady=10)

        # --- Controls ---
        ctrl_lf = ttk.LabelFrame(top, text="  Defragmentation Controls  ")
        ctrl_lf.pack(side="left", padx=(0, 10), fill="y")

        ttk.Label(ctrl_lf, text="Strategy:").grid(
            row=0, column=0, padx=6, pady=4, sticky="w")
        self.cmb_defrag_strategy = ttk.Combobox(
            ctrl_lf, width=22, state="readonly",
            values=["most_fragmented_first", "largest_first", "sequential"])
        self.cmb_defrag_strategy.current(0)
        self.cmb_defrag_strategy.grid(row=0, column=1, padx=6, pady=4)

        ttk.Button(ctrl_lf, text="📊 Analyze Fragmentation",
                    command=self._action_analyze_fragmentation).grid(
            row=1, column=0, columnspan=2, padx=6, pady=4, sticky="ew")
        ttk.Button(ctrl_lf, text="🛠️ Defragment All",
                    style="Green.TButton",
                    command=self._action_defragment_all).grid(
            row=2, column=0, columnspan=2, padx=6, pady=4, sticky="ew")
        ttk.Button(ctrl_lf, text="📦 Compact Free Space",
                    style="Orange.TButton",
                    command=self._action_compact_free_space).grid(
            row=3, column=0, columnspan=2, padx=6, pady=4, sticky="ew")

        # --- Results ---
        results_lf = ttk.LabelFrame(top, text="  Fragmentation Analysis  ")
        results_lf.pack(side="left", fill="both", expand=True)

        self.txt_defrag_results = tk.Text(
            results_lf, height=8, wrap="word",
            bg=COLORS["bg_panel"], fg=COLORS["text_primary"],
            font=FONT_MONO_SM, relief="flat", state="disabled",
        )
        self.txt_defrag_results.pack(fill="both", expand=True, padx=4, pady=4)

        # --- Defrag history table ---
        hist_lf = ttk.LabelFrame(self.tab_defrag,
                                  text="  Defragmentation History  ")
        hist_lf.pack(fill="both", expand=True, padx=10, pady=6)

        cols = ("op_id", "type", "inode", "blocks_moved", "time")
        self.defrag_table = ttk.Treeview(hist_lf, columns=cols,
                                          show="headings", height=8)
        for c, heading, w in [
            ("op_id", "Op #", 60), ("type", "Type", 120),
            ("inode", "Inode", 70), ("blocks_moved", "Blocks", 80),
            ("time", "Timestamp", 200),
        ]:
            self.defrag_table.heading(c, text=heading)
            self.defrag_table.column(c, width=w, anchor="center")
        self.defrag_table.pack(fill="both", expand=True, padx=4, pady=4)

    # ================================================================= #
    #  TAB 5 – Performance
    # ================================================================= #

    def _build_performance_tab(self) -> None:
        top = ttk.Frame(self.tab_perf)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Button(top, text="📈 Generate Report",
                    style="Green.TButton",
                    command=self._action_generate_report).pack(
            side="left", padx=4)
        ttk.Button(top, text="🔍 Analyze Bottlenecks",
                    command=self._action_analyze_bottlenecks).pack(
            side="left", padx=4)
        ttk.Button(top, text="⚡ Collect Metrics",
                    command=self._action_collect_metrics).pack(
            side="left", padx=4)
        ttk.Button(top, text="🏆 Performance Score",
                    style="Orange.TButton",
                    command=self._action_perf_score).pack(
            side="left", padx=4)

        report_lf = ttk.LabelFrame(self.tab_perf,
                                    text="  Performance Report  ")
        report_lf.pack(fill="both", expand=True, padx=10, pady=6)

        self.txt_perf_report = tk.Text(
            report_lf, wrap="word",
            bg=COLORS["bg_panel"], fg=COLORS["text_primary"],
            font=FONT_MONO, relief="flat", state="disabled",
        )
        scroll_p = ttk.Scrollbar(report_lf, command=self.txt_perf_report.yview)
        self.txt_perf_report.configure(yscrollcommand=scroll_p.set)
        scroll_p.pack(side="right", fill="y")
        self.txt_perf_report.pack(fill="both", expand=True, padx=4, pady=4)

    # ================================================================= #
    #  TAB 6 – Disk Layout Visualization
    # ================================================================= #

    def _build_layout_tab(self) -> None:
        ctrl = ttk.Frame(self.tab_layout)
        ctrl.pack(fill="x", padx=10, pady=10)

        ttk.Button(ctrl, text="Refresh Layout",
                    style="Green.TButton",
                    command=self._refresh_layout).pack(side="left", padx=4)

        ttk.Label(ctrl, text="Legend:").pack(side="left", padx=(20, 4))
        for label, color in [("Free", COLORS["free_block"]),
                              ("Used", COLORS["used_block"]),
                              ("Corrupt", COLORS["corrupt_block"])]:
            tk.Label(ctrl, text=f"  {label}  ", bg=color,
                     fg="#ffffff", font=FONT_SMALL).pack(side="left", padx=2)

        layout_lf = ttk.LabelFrame(self.tab_layout,
                                    text="  Block Map  ")
        layout_lf.pack(fill="both", expand=True, padx=10, pady=6)

        # Canvas for colored block grid
        self.layout_canvas = tk.Canvas(
            layout_lf, bg=COLORS["bg_panel"],
            highlightthickness=0,
        )
        self.layout_canvas.pack(fill="both", expand=True, padx=4, pady=4)

    # ================================================================= #
    #  TAB 7 – Journal
    # ================================================================= #

    def _build_journal_tab(self) -> None:
        ctrl = ttk.Frame(self.tab_journal)
        ctrl.pack(fill="x", padx=10, pady=10)

        ttk.Button(ctrl, text="Refresh Journal",
                    command=self._refresh_journal).pack(side="left", padx=4)
        ttk.Button(ctrl, text="Clear Committed",
                    style="Orange.TButton",
                    command=self._action_clear_journal).pack(
            side="left", padx=4)
        ttk.Button(ctrl, text="Checkpoint",
                    command=self._action_checkpoint_journal).pack(
            side="left", padx=4)

        cols = ("txn_id", "operation", "status", "timestamp")
        self.journal_table = ttk.Treeview(self.tab_journal, columns=cols,
                                           show="headings", height=16)
        self.journal_table.heading("txn_id", text="Transaction ID")
        self.journal_table.heading("operation", text="Operation")
        self.journal_table.heading("status", text="Status")
        self.journal_table.heading("timestamp", text="Timestamp")
        self.journal_table.column("txn_id", width=280)
        self.journal_table.column("operation", width=100, anchor="center")
        self.journal_table.column("status", width=110, anchor="center")
        self.journal_table.column("timestamp", width=200)
        self.journal_table.pack(fill="both", expand=True, padx=10, pady=6)

    # ----------------------------------------------------------------- #
    #  Status bar
    # ----------------------------------------------------------------- #

    def _build_status_bar(self) -> None:
        self.status_var = tk.StringVar(value="Ready.")
        status_bar = tk.Label(
            self.root, textvariable=self.status_var,
            bg=COLORS["bg_panel"], fg=COLORS["text_secondary"],
            font=FONT_SMALL, anchor="w", padx=10,
        )
        status_bar.pack(fill="x", side="bottom")

    def _set_status(self, msg: str) -> None:
        self.status_var.set(msg)
        self.root.update_idletasks()

    # ================================================================= #
    #  Data refresh helpers
    # ================================================================= #

    def _refresh_dashboard(self) -> None:
        """Refresh all dashboard metric cards and info text."""
        try:
            metrics = self.analyzer.collect_metrics()
            self.sv_disk_usage.set(f"{metrics['disk_usage_percentage']:.1f}%")
            self.sv_free_space.set(f"{metrics['free_space_percentage']:.1f}%")
            self.sv_frag.set(f"{metrics['fragmentation_percentage']:.1f}%")
            self.sv_cache_hit.set(f"{metrics['cache_hit_rate']:.1f}%")
            self.sv_total_files.set(str(len(self.fat.file_to_blocks)))
            self.sv_journal_txns.set(str(len(self.journal)))

            self.pb_disk["value"] = metrics["disk_usage_percentage"]

            # Disk info text
            info = self.disk.get_disk_info()
            lines = [
                f"Total Blocks:      {info['total_blocks']}",
                f"Block Size:        {info['block_size']} B",
                f"Total Capacity:    {info['total_capacity_mb']:.2f} MB",
                f"Blocks Used:       {info['blocks_used']}",
                f"Blocks Free:       {info['blocks_free']}",
                f"Total Reads:       {info['total_reads']}",
                f"Total Writes:      {info['total_writes']}",
                "",
                f"Allocation Strategy: {self.fsm.allocation_strategy}",
                f"FAT Method:        {self.fat.allocation_method}",
                f"Files Tracked:     {len(self.fat.file_to_blocks)}",
                f"Cache Strategy:    {self.cache.strategy}",
                f"Cache Size:        {len(self.cache.cache_data)}/{self.cache.cache_size}",
            ]
            self._set_text(self.txt_disk_info, "\n".join(lines))
            self._set_status("Dashboard refreshed.")
        except Exception as e:
            logger.error("Dashboard refresh error: %s", e)
            self._set_status(f"Error: {e}")

    def _refresh_file_table(self) -> None:
        """Reload the file-list treeview."""
        self.file_table.delete(*self.file_table.get_children())
        for inode_num, blocks in self.fat.file_to_blocks.items():
            frag = self.fat.is_fragmented(inode_num)
            size = len(blocks) * self.disk.block_size if isinstance(blocks, list) else 0
            self.file_table.insert("", "end", values=(
                inode_num,
                str(blocks),
                "Yes" if frag else "No",
                size,
            ))
        self._set_status(f"File table refreshed — {len(self.fat.file_to_blocks)} files.")

    def _refresh_dir_tree(self) -> None:
        """Reload the directory tree text view."""
        tree_str = self.dir_tree.get_tree_structure()
        self._set_text(self.txt_dir_tree, tree_str)

    def _refresh_layout(self) -> None:
        """Redraw the disk-block grid on the canvas."""
        self.layout_canvas.delete("all")
        canvas = self.layout_canvas
        canvas.update_idletasks()
        cw = max(canvas.winfo_width(), 400)
        ch = max(canvas.winfo_height(), 300)

        total = self.disk.total_blocks
        cols = max(1, cw // 10)
        block_w = cw / cols
        block_h = min(block_w, ch / max(1, (total // cols + 1)))

        for idx in range(total):
            r = idx // cols
            c = idx % cols
            x1 = c * block_w
            y1 = r * block_h
            x2 = x1 + block_w - 1
            y2 = y1 + block_h - 1

            # Determine color
            data = self.disk.blocks[idx]
            if data is not None and (b"CORRUPTED" in data or b"BAD_SECTOR" in data):
                color = COLORS["corrupt_block"]
            elif self.fsm.bitmap[idx]:
                color = COLORS["used_block"]
            else:
                color = COLORS["free_block"]

            canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")

        self._set_status("Disk layout refreshed.")

    def _refresh_journal(self) -> None:
        """Reload journal transaction table."""
        self.journal_table.delete(*self.journal_table.get_children())
        for entry in self.journal.entries:
            self.journal_table.insert("", "end", values=(
                entry.transaction_id,
                entry.operation,
                entry.status,
                entry.timestamp.isoformat() if hasattr(entry.timestamp, "isoformat") else str(entry.timestamp),
            ))
        self._set_status(f"Journal refreshed — {len(self.journal.entries)} entries.")

    def _refresh_defrag_history(self) -> None:
        """Reload defragmentation history table."""
        self.defrag_table.delete(*self.defrag_table.get_children())
        for op in self.defrag.defrag_history:
            self.defrag_table.insert("", "end", values=(
                op.get("operation_id", ""),
                op.get("type", ""),
                op.get("inode_number", ""),
                len(op.get("new_blocks", op.get("old_blocks", []))),
                str(op.get("timestamp", "")),
            ))

    # ================================================================= #
    #  Action handlers
    # ================================================================= #

    # --- File Operations --- #

    def _action_create_file(self) -> None:
        """Create a new simulated file with intentional fragmentation."""
        try:
            blocks_needed = int(self.sp_blocks.get())
        except ValueError:
            messagebox.showwarning("Invalid Input", "Blocks must be a positive integer.")
            return

        allocated = []
        candidate = 10
        while len(allocated) < blocks_needed and candidate < self.disk.total_blocks:
            if self.fsm.bitmap[candidate] == 0:
                self.fsm.bitmap[candidate] = 1
                allocated.append(candidate)
            candidate += 2  # intentional fragmentation

        if len(allocated) < blocks_needed:
            messagebox.showwarning("Allocation Failed",
                                   f"Could only allocate {len(allocated)}/{blocks_needed} blocks.")
            if not allocated:
                return

        inode_num = self.inode_counter
        self.inode_counter += 1

        self.fat.file_to_blocks[inode_num] = allocated
        for b in allocated:
            self.fat.block_to_file[b] = inode_num

        # Write through cache
        self.cache.put(allocated[0],
                       f"DATA_INODE_{inode_num}".encode("utf-8").ljust(
                           self.disk.block_size, b"\x00"))

        # Journal
        txn_id = self.journal.begin_transaction(
            "WRITE", {"inode": inode_num, "blocks": allocated})
        self.journal.commit_transaction(txn_id)

        self._refresh_dashboard()
        self._refresh_file_table()
        self._set_status(f"Created file (inode {inode_num}) with {len(allocated)} blocks.")

    def _action_delete_file(self) -> None:
        """Delete the selected file from the treeview."""
        selected = self.file_table.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Select a file row first.")
            return
        item = self.file_table.item(selected[0])
        inode_num = int(item["values"][0])

        blocks = self.fat.deallocate(inode_num)
        if blocks:
            self.fsm.deallocate_blocks(blocks)
            txn_id = self.journal.begin_transaction(
                "DELETE", {"inode": inode_num, "blocks": blocks})
            self.journal.commit_transaction(txn_id)

        self._refresh_dashboard()
        self._refresh_file_table()
        self._set_status(f"Deleted file inode {inode_num}.")

    # --- Crash & Recovery --- #

    def _action_inject_crash(self) -> None:
        crash_type = self.cmb_crash_type.get()
        blocks_str = self.ent_crash_blocks.get().strip()
        blocks = []
        if blocks_str:
            try:
                blocks = [int(b.strip()) for b in blocks_str.split(",") if b.strip()]
            except ValueError:
                messagebox.showwarning("Invalid Blocks", "Enter comma-separated integers.")
                return

        report = {}
        if crash_type == "Power Failure":
            report = self.simulator.inject_power_failure(self.disk, affected_blocks=blocks or None)
        elif crash_type == "Bit Corruption":
            report = self.simulator.inject_bit_corruption(self.disk, num_blocks=len(blocks) or 5)
        elif crash_type == "Sector Failure":
            report = self.simulator.inject_sector_failure(self.disk)
        elif crash_type == "Metadata Corruption":
            report = self.simulator.inject_metadata_corruption(self.dir_tree)
        elif crash_type == "Journal Corruption":
            report = self.simulator.inject_journal_corruption(self.journal)
        elif crash_type == "Random Crash":
            report = self.simulator.simulate_random_crash(self.fs_components)

        self._append_recovery_log(
            f"💥 CRASH INJECTED: {report.get('crash_type', crash_type)}\n"
            f"   Severity: {report.get('severity', 'N/A')}\n"
            f"   Description: {report.get('description', 'N/A')}\n"
            f"   Recoverable: {report.get('recoverable', 'N/A')}\n"
        )
        self._refresh_dashboard()
        self._set_status(f"Crash injected: {crash_type}")

    def _action_analyze_crash(self) -> None:
        analysis = self.recovery_mgr.analyze_crash()
        lines = [
            "🔍 CRASH ANALYSIS",
            f"   Corruption detected: {analysis['has_corruption']}",
            f"   Corrupted blocks: {analysis['corrupted_blocks']}",
            f"   Uncommitted txns: {len(analysis['uncommitted_transactions'])}",
            f"   Metadata issues: {analysis['inconsistent_metadata']}",
            f"   Recommended: {analysis['recommended_recovery_method']}",
        ]
        self._append_recovery_log("\n".join(lines) + "\n")
        self._set_status("Crash analysis complete.")

    def _action_recover_journal(self) -> None:
        """Full recovery pipeline: repair corrupted blocks → fixup FAT/FSM → FSCK."""
        start = time.time()

        # Step 1 – Scan disk and repair corrupted blocks
        corrupted_blocks = []
        for i in range(self.disk.total_blocks):
            data = self.disk.blocks[i]
            if isinstance(data, bytes) and (
                    b"CORRUPTED" in data or b"BAD_SECTOR" in data):
                corrupted_blocks.append(i)
                # Clear the corruption marker from disk
                self.disk.blocks[i] = None
                # Free in FSM
                if self.fsm.bitmap[i] == 1:
                    self.fsm.bitmap[i] = 0
                # Remove from FAT mappings
                owner = self.fat.block_to_file.pop(i, None)
                if owner is not None and owner in self.fat.file_to_blocks:
                    blocks = self.fat.file_to_blocks[owner]
                    if isinstance(blocks, list) and i in blocks:
                        blocks.remove(i)
                    # Remove empty file entries
                    if not self.fat.file_to_blocks[owner]:
                        del self.fat.file_to_blocks[owner]

        # Step 2 – Roll back any PENDING journal entries
        rolled_back = []
        for entry in self.journal.entries:
            status = getattr(entry, "status", None)
            if status in ("PENDING", "UNCOMMITTED"):
                entry.status = "ABORTED"
                rolled_back.append(getattr(entry, "transaction_id", "?"))

        # Step 3 – Auto-repair FSM ↔ FAT inconsistencies
        fsck = self.recovery_mgr.perform_fsck(auto_repair=True)

        # Step 4 – Verify final state
        verification = self.recovery_mgr.verify_consistency()
        elapsed = time.time() - start

        lines = [
            "🚑 RECOVERY PIPELINE COMPLETE",
            f"   Corrupted blocks repaired: {len(corrupted_blocks)} {corrupted_blocks}",
            f"   Transactions rolled back:  {len(rolled_back)}",
            f"   FSCK auto-repaired:        {fsck['auto_repaired']}",
            f"   Consistency:               {'✅ OK' if verification['is_consistent'] else '⚠ Issues remain'}",
            f"   Time:                      {elapsed:.4f}s",
        ]
        if not verification["is_consistent"]:
            for issue in verification.get("issues", []):
                lines.append(f"   ⚠ {issue}")
        self._append_recovery_log("\n".join(lines) + "\n")
        self._refresh_dashboard()
        self._set_status("Recovery pipeline complete.")

    def _action_rebuild_fat(self) -> None:
        """Non-destructive FAT rebuild: remove entries for corrupted/freed blocks."""
        repaired = 0
        removed_files = []

        for inode_num, blocks in list(self.fat.file_to_blocks.items()):
            if not isinstance(blocks, list):
                continue
            valid_blocks = []
            for b in blocks:
                data = self.disk.blocks[b] if b < self.disk.total_blocks else None
                is_corrupt = isinstance(data, bytes) and (
                    b"CORRUPTED" in data or b"BAD_SECTOR" in data)
                if is_corrupt or self.fsm.bitmap[b] == 0:
                    # Block is corrupt or freed — remove from FAT
                    self.fat.block_to_file.pop(b, None)
                    if is_corrupt:
                        self.disk.blocks[b] = None
                        self.fsm.bitmap[b] = 0
                    repaired += 1
                else:
                    valid_blocks.append(b)

            if valid_blocks:
                self.fat.file_to_blocks[inode_num] = valid_blocks
            else:
                del self.fat.file_to_blocks[inode_num]
                removed_files.append(inode_num)

        # Run FSCK to fix any remaining inconsistencies
        self.recovery_mgr.perform_fsck(auto_repair=True)

        self._append_recovery_log(
            f"🔧 Rebuild FAT: Repaired {repaired} block mappings, "
            f"removed {len(removed_files)} empty file(s).\n")
        self._refresh_dashboard()
        self._set_status(f"FAT rebuilt — {repaired} blocks repaired.")

    def _action_verify_consistency(self) -> None:
        result = self.recovery_mgr.verify_consistency()
        lines = [
            "✅ CONSISTENCY CHECK",
            f"   Consistent: {result['is_consistent']}",
        ]
        for issue in result.get("issues", []):
            lines.append(f"   ⚠ {issue}")
        self._append_recovery_log("\n".join(lines) + "\n")

    # --- Defragmentation --- #

    def _action_analyze_fragmentation(self) -> None:
        analysis = self.defrag.analyze_fragmentation()
        lines = [
            f"Total files:          {analysis['total_files']}",
            f"Fragmented files:     {analysis['fragmented_files']}",
            f"Fragmentation %:      {analysis['fragmentation_percentage']:.1f}%",
            f"Total gaps:           {analysis['total_gaps']}",
            f"Avg fragments/file:   {analysis['average_fragments_per_file']:.2f}",
            "",
            "Most fragmented files:",
        ]
        for f in analysis.get("most_fragmented_files", [])[:5]:
            lines.append(
                f"  Inode {f['inode_number']}: "
                f"score={f['fragmentation_score']:.1f}%, "
                f"blocks={f['total_blocks']}")
        self._set_text(self.txt_defrag_results, "\n".join(lines))
        self._set_status("Fragmentation analysis complete.")

    def _action_defragment_all(self) -> None:
        strategy = self.cmb_defrag_strategy.get()
        self._set_status("Defragmenting…")
        report = self.defrag.defragment_all(strategy=strategy)
        lines = [
            f"Strategy:               {report['strategy_used']}",
            f"Files processed:        {report['files_processed']}",
            f"Total blocks moved:     {report['total_blocks_moved']}",
            f"Time:                   {report['time_taken']:.4f}s",
            f"Initial frag %:         {report['initial_fragmentation_percentage']:.1f}%",
            f"Final frag %:           {report['final_fragmentation_percentage']:.1f}%",
        ]
        self._set_text(self.txt_defrag_results, "\n".join(lines))
        self._refresh_defrag_history()
        self._refresh_dashboard()
        self._set_status("Defragmentation complete.")

    def _action_compact_free_space(self) -> None:
        self._set_status("Compacting free space…")
        report = self.defrag.compact_free_space()
        lines = [
            f"Files moved:    {report['files_moved']}",
            f"Blocks moved:   {report['blocks_moved']}",
            f"Time:           {report['time_taken']:.4f}s",
        ]
        self._set_text(self.txt_defrag_results, "\n".join(lines))
        self._refresh_dashboard()
        self._set_status("Free space compaction complete.")

    # --- Performance --- #

    def _action_generate_report(self) -> None:
        report = self.analyzer.generate_performance_report(output_format="text")
        self._set_text(self.txt_perf_report, report)
        self._set_status("Performance report generated.")

    def _action_analyze_bottlenecks(self) -> None:
        result = self.analyzer.analyze_bottlenecks()
        lines = ["=== Bottleneck Analysis ===\n"]
        lines.append("Bottlenecks:")
        for b in result["bottlenecks"]:
            lines.append(f"  • {b}")
        lines.append("\nRecommendations:")
        for r in result["recommendations"]:
            lines.append(f"  ➜ {r}")
        self._set_text(self.txt_perf_report, "\n".join(lines))
        self._set_status("Bottleneck analysis complete.")

    def _action_collect_metrics(self) -> None:
        metrics = self.analyzer.collect_metrics()
        lines = ["=== Current Metrics ===\n"]
        for k, v in metrics.items():
            if isinstance(v, float):
                lines.append(f"  {k}: {v:.2f}")
            else:
                lines.append(f"  {k}: {v}")
        self._set_text(self.txt_perf_report, "\n".join(lines))
        self._set_status("Metrics collected.")

    def _action_perf_score(self) -> None:
        score = self.analyzer.calculate_performance_score()
        lines = [
            "=== Performance Score ===\n",
            f"  Overall Score: {score:.1f} / 100.0",
            "",
            "  Scoring breakdown:",
            "  • Fragmentation penalty (up to -30)",
            "  • Cache miss penalty   (up to -40)",
            "  • Low free space penalty",
        ]
        self._set_text(self.txt_perf_report, "\n".join(lines))
        self._set_status(f"Performance score: {score:.1f}")

    # --- Menu actions --- #

    def _action_save_disk(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".img",
            filetypes=[("Disk Image", "*.img"), ("All Files", "*.*")])
        if path:
            if self.disk.save_to_file(path):
                messagebox.showinfo("Saved", f"Disk state saved to:\n{path}")
            else:
                messagebox.showerror("Error", "Failed to save disk state.")

    def _action_load_disk(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Disk Image", "*.img"), ("All Files", "*.*")])
        if path:
            try:
                self.disk = Disk.load_from_file(path)
                self.fs_components["disk"] = self.disk
                self._refresh_dashboard()
                messagebox.showinfo("Loaded", f"Disk state loaded from:\n{path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load: {e}")

    def _action_export_report(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("JSON", "*.json")])
        if path:
            fmt = "json" if path.endswith(".json") else "text"
            report = self.analyzer.generate_performance_report(output_format=fmt)
            with open(path, "w", encoding="utf-8") as f:
                f.write(report)
            messagebox.showinfo("Exported", f"Report saved to:\n{path}")

    def _action_format_disk(self) -> None:
        if messagebox.askyesno("Confirm", "Format disk? This will erase all data."):
            self.disk.format_disk()
            self.fsm.bitmap.setall(0)
            self.fat.file_to_blocks.clear()
            self.fat.block_to_file.clear()
            self.fat.next_pointers.clear()
            self.journal.clear_journal(keep_uncommitted=False)
            self.inode_counter = 1
            self._refresh_dashboard()
            self._set_status("Disk formatted.")

    def _action_run_fsck(self) -> None:
        result = self.recovery_mgr.perform_fsck(auto_repair=False)
        lines = ["=== FSCK Results ===\n"]
        for key, val in result.items():
            lines.append(f"  {key}: {val}")
        messagebox.showinfo("FSCK", "\n".join(lines))

    def _action_reset_fs(self) -> None:
        if messagebox.askyesno("Confirm", "Reset the entire file system?"):
            self._init_file_system(self.disk.total_blocks, self.disk.block_size)
            self.inode_counter = 1
            self._refresh_dashboard()
            self._set_status("File system reset.")

    def _action_show_about(self) -> None:
        messagebox.showinfo(
            "About",
            "File System Recovery & Optimization Tool\n\n"
            "A comprehensive simulator for studying\n"
            "disk management, crash recovery,\n"
            "defragmentation, and caching strategies.\n\n"
            "Built with Python & Tkinter.",
        )

    # --- Journal actions --- #

    def _action_clear_journal(self) -> None:
        self.journal.clear_journal(keep_uncommitted=True)
        self._refresh_journal()
        self._set_status("Committed journal entries cleared.")

    def _action_checkpoint_journal(self) -> None:
        self.journal.checkpoint()
        self._refresh_journal()
        self._set_status("Journal checkpoint created.")

    # ================================================================= #
    #  UI utility helpers
    # ================================================================= #

    @staticmethod
    def _set_text(widget: tk.Text, text: str) -> None:
        """Replace the entire contents of a `tk.Text` widget."""
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _append_recovery_log(self, text: str) -> None:
        """Append timestamped text to the recovery log."""
        ts = time.strftime("%H:%M:%S")
        self.txt_recovery_log.insert("end", f"[{ts}] {text}\n")
        self.txt_recovery_log.see("end")

    # ----------------------------------------------------------------- #
    #  Lifecycle
    # ----------------------------------------------------------------- #

    def _on_close(self) -> None:
        try:
            if hasattr(self, 'perf_dashboard'):
                self.perf_dashboard.stop()
        except:
            pass
        self.root.destroy()

    def run(self) -> None:
        """Start the Tkinter event loop."""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()


# ===================================================================== #
#  Entry point
# ===================================================================== #

def main():
    """Launch the GUI application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
