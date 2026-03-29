"""
main_window.py — Main application window for the File System Recovery
& Optimization Tool.

Provides the Tkinter-based GUI with:
  • Three-panel layout (directory tree, disk visualisation, performance)
  • Bottom log console
  • Full menu bar with keyboard shortcuts
  • Integrated file-system component lifecycle

Usage::

    from src.ui.main_window import MainWindow
    app = MainWindow(total_blocks=1024, block_size=512)
    app.run()
"""

import logging
import os
import sys
import textwrap
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from typing import Dict, Any

# --------------------------------------------------------------------------- #
#  File-system core components
# --------------------------------------------------------------------------- #
from src.core.disk import Disk
from src.core.free_space import FreeSpaceManager
from src.core.inode import Inode
from src.core.directory import DirectoryTree
from src.core.file_allocation_table import FileAllocationTable
from src.core.journal import Journal

# --------------------------------------------------------------------------- #
#  Recovery / optimisation components
# --------------------------------------------------------------------------- #
from src.recovery.crash_simulator import CrashSimulator
from src.recovery.recovery_manager import RecoveryManager
from src.recovery.defragmenter import Defragmenter
from src.recovery.cache_manager import CacheManager
from src.recovery.performance_analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)


# =========================================================================== #
#  MainWindow
# =========================================================================== #

class MainWindow:
    """
    Root application window for the File System Recovery & Optimization Tool.

    Attributes
    ----------
    root : tk.Tk
        The top-level Tkinter window.
    file_system_components : dict
        All initialised file-system component instances, keyed by short name.
    current_disk_path : str
        Path to the currently loaded / saved disk image file.
    theme : str
        Active UI colour theme — ``'light'`` or ``'dark'``.
    window_width : int
        Window width in pixels (default 1400).
    window_height : int
        Window height in pixels (default 900).
    """

    # Default window geometry
    _DEFAULT_WIDTH = 1400
    _DEFAULT_HEIGHT = 900

    # --------------------------------------------------------------------- #
    #  Construction
    # --------------------------------------------------------------------- #

    def __init__(self, total_blocks: int = 1000, block_size: int = 4096):
        """
        Build and display the main application window.

        Parameters
        ----------
        total_blocks : int
            Number of blocks for the initial file system.
        block_size : int
            Size of each block in bytes.
        """
        self.window_width: int = self._DEFAULT_WIDTH
        self.window_height: int = self._DEFAULT_HEIGHT
        self.theme: str = "dark"
        self.current_disk_path: str = ""
        self._unsaved_changes: bool = False
        self.inode_counter: int = 1

        # File-system components — populated by _initialize_file_system
        self.file_system_components: Dict[str, Any] = {}

        # ---- Tk root ----
        self.root = tk.Tk()
        self.root.title("File System Recovery & Optimization Tool")
        self.root.geometry(f"{self.window_width}x{self.window_height}")
        self.root.minsize(900, 600)
        self._center_window()

        # Apply theme
        self._apply_theme()

        # Build UI skeleton
        self._create_menu_bar()
        self._initialize_file_system(total_blocks, block_size)
        self._create_main_layout()

        # Wire the close button to our handler
        self.root.protocol("WM_DELETE_WINDOW", self.exit_application)

        # Start a periodic UI refresh
        self._schedule_refresh()

        logger.info("MainWindow created (%d×%d)", self.window_width, self.window_height)

    # --------------------------------------------------------------------- #
    #  Window helpers
    # --------------------------------------------------------------------- #

    def _center_window(self):
        """Position the window at the centre of the screen."""
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - self.window_width) // 2)
        y = max(0, (sh - self.window_height) // 2)
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")

    def _apply_theme(self):
        """Configure ttk styles for the dark theme."""
        style = ttk.Style(self.root)
        style.theme_use("clam")

        bg = "#1e1e2e"
        fg = "#cdd6f4"
        accent = "#89b4fa"
        surface = "#313244"
        border = "#45475a"
        red = "#f38ba8"
        green = "#a6e3a1"
        yellow = "#f9e2af"

        self.root.configure(bg=bg)

        style.configure(".", background=bg, foreground=fg,
                         bordercolor=border, focuscolor=accent,
                         fieldbackground=surface)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=surface, foreground=fg,
                         padding=(8, 4))
        style.map("TButton",
                   background=[("active", accent)],
                   foreground=[("active", bg)])
        style.configure("TLabelframe", background=bg, foreground=accent)
        style.configure("TLabelframe.Label", background=bg, foreground=accent)
        style.configure("Treeview", background=surface, foreground=fg,
                         fieldbackground=surface, rowheight=22)
        style.configure("Treeview.Heading", background=border, foreground=fg)
        style.map("Treeview",
                   background=[("selected", accent)],
                   foreground=[("selected", bg)])
        style.configure("TNotebook", background=bg)
        style.configure("TNotebook.Tab", background=surface, foreground=fg,
                         padding=(12, 4))
        style.map("TNotebook.Tab",
                   background=[("selected", accent)],
                   foreground=[("selected", bg)])
        style.configure("Horizontal.TProgressbar",
                         troughcolor=surface, background=green)
        style.configure("TEntry", fieldbackground=surface, foreground=fg,
                         insertcolor=fg)

        # Store palette for manual widget colouring
        self._palette = dict(bg=bg, fg=fg, accent=accent, surface=surface,
                             border=border, red=red, green=green, yellow=yellow)

    # --------------------------------------------------------------------- #
    #  Menu bar
    # --------------------------------------------------------------------- #

    def _create_menu_bar(self):
        """Build the application menu bar with full keyboard shortcuts."""
        menubar = tk.Menu(self.root, tearoff=0,
                          bg=self._palette["surface"],
                          fg=self._palette["fg"],
                          activebackground=self._palette["accent"],
                          activeforeground=self._palette["bg"])

        menu_kw = dict(tearoff=0,
                       bg=self._palette["surface"],
                       fg=self._palette["fg"],
                       activebackground=self._palette["accent"],
                       activeforeground=self._palette["bg"])

        # ---- File ----
        file_menu = tk.Menu(menubar, **menu_kw)
        file_menu.add_command(label="New Disk…",     accelerator="Ctrl+N",
                              command=self.new_disk)
        file_menu.add_command(label="Open Disk…",    accelerator="Ctrl+O",
                              command=self.open_disk)
        file_menu.add_separator()
        file_menu.add_command(label="Save",           accelerator="Ctrl+S",
                              command=self.save_disk)
        file_menu.add_command(label="Save As…",      accelerator="Ctrl+Shift+S",
                              command=self.save_disk_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit",           accelerator="Alt+F4",
                              command=self.exit_application)
        menubar.add_cascade(label="File", menu=file_menu)

        # ---- Edit ----
        edit_menu = tk.Menu(menubar, **menu_kw)
        edit_menu.add_command(label="Preferences…", command=self._show_preferences)
        edit_menu.add_command(label="Configuration…", command=self._show_configuration)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # ---- Operations ----
        ops_menu = tk.Menu(menubar, **menu_kw)
        ops_menu.add_command(label="Create File…",      accelerator="Ctrl+F",
                             command=self._op_create_file)
        ops_menu.add_command(label="Create Directory…", accelerator="Ctrl+D",
                             command=self._op_create_directory)
        ops_menu.add_command(label="Delete…",            command=self._op_delete)
        ops_menu.add_separator()
        ops_menu.add_command(label="Defragment",         command=self._op_defragment)
        menubar.add_cascade(label="Operations", menu=ops_menu)

        # ---- Recovery ----
        rec_menu = tk.Menu(menubar, **menu_kw)
        rec_menu.add_command(label="Simulate Crash…",    command=self._rec_simulate_crash)
        rec_menu.add_command(label="Recover System",      command=self._rec_recover)
        rec_menu.add_command(label="Run FSCK",            command=self._rec_fsck)
        menubar.add_cascade(label="Recovery", menu=rec_menu)

        # ---- Tools ----
        tools_menu = tk.Menu(menubar, **menu_kw)
        tools_menu.add_command(label="Benchmark Performance", command=self._tool_benchmark)
        tools_menu.add_command(label="Clear Cache",           command=self._tool_clear_cache)
        tools_menu.add_command(label="Export Report…",       command=self._tool_export_report)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        # ---- Help ----
        help_menu = tk.Menu(menubar, **menu_kw)
        help_menu.add_command(label="Documentation", command=self._show_documentation)
        help_menu.add_command(label="About",          command=self._show_about_dialog)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

        # ---- Keyboard shortcuts ----
        self.root.bind_all("<Control-n>", lambda e: self.new_disk())
        self.root.bind_all("<Control-o>", lambda e: self.open_disk())
        self.root.bind_all("<Control-s>", lambda e: self.save_disk())
        self.root.bind_all("<Control-Shift-S>", lambda e: self.save_disk_as())
        self.root.bind_all("<Control-f>", lambda e: self._op_create_file())
        self.root.bind_all("<Control-d>", lambda e: self._op_create_directory())

    # --------------------------------------------------------------------- #
    #  File-system initialisation
    # --------------------------------------------------------------------- #

    def _initialize_file_system(self, total_blocks: int = 1000,
                                 block_size: int = 4096):
        """
        Create a fresh file system with the given parameters and store
        every component both in ``self.file_system_components`` and as
        convenience attributes on ``self``.
        """
        try:
            self.disk = Disk(total_blocks=total_blocks, block_size=block_size)
            self.fsm = FreeSpaceManager(total_blocks=total_blocks)
            self.dir_tree = DirectoryTree()
            self.fat = FileAllocationTable(allocation_method="indexed")
            self.journal = Journal(journal_file="data/journal.log")
            self.crash_sim = CrashSimulator()
            self.cache = CacheManager(disk=self.disk, cache_size=100)

            # Components dict used by RecoveryManager / Defragmenter / etc.
            self.file_system_components = {
                "disk": self.disk,
                "fsm": self.fsm,
                "directory_tree": self.dir_tree,
                "fat": self.fat,
                "journal": self.journal,
                "cache": self.cache,
            }

            self.recovery_mgr = RecoveryManager(self.file_system_components)
            self.defragmenter = Defragmenter(self.file_system_components)
            self.perf_analyzer = PerformanceAnalyzer(self.file_system_components)

            self.inode_counter = 1
            self._unsaved_changes = False

            logger.info("File system initialised: %d blocks × %d B",
                        total_blocks, block_size)
        except Exception as exc:
            logger.exception("Failed to initialise file system")
            messagebox.showerror("Initialisation Error", str(exc))

    # --------------------------------------------------------------------- #
    #  Main layout
    # --------------------------------------------------------------------- #

    def _create_main_layout(self):
        """Build the three-panel + bottom-log layout."""

        # ── Top-level vertical split: main area on top, log console on bottom ──
        self._main_frame = ttk.Frame(self.root)
        self._main_frame.pack(fill=tk.BOTH, expand=True)

        # ── Status bar (above the log) ──
        self._status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self._main_frame, textvariable=self._status_var,
                               anchor=tk.W, padding=(6, 2))
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # ── Log console ──
        log_frame = ttk.LabelFrame(self._main_frame, text="  Log Console  ",
                                   height=150)
        log_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=4, pady=(0, 2))
        log_frame.pack_propagate(False)

        self._log_text = tk.Text(log_frame, height=7, wrap=tk.WORD,
                                 bg=self._palette["surface"],
                                 fg=self._palette["fg"],
                                 insertbackground=self._palette["fg"],
                                 font=("Consolas", 9),
                                 borderwidth=0, relief=tk.FLAT)
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL,
                                    command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._log_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._log("Application started.")

        # ── Horizontal PanedWindow for 3-panel layout ──
        panes = ttk.PanedWindow(self._main_frame, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ---------- LEFT PANEL (Directory Tree & Controls) ----------
        left_panel = ttk.Frame(panes, width=350)
        panes.add(left_panel, weight=1)

        self._build_left_panel(left_panel)

        # ---------- CENTRE PANEL (Disk Visualisation) ----------
        centre_panel = ttk.Frame(panes, width=700)
        panes.add(centre_panel, weight=2)

        self._build_centre_panel(centre_panel)

        # ---------- RIGHT PANEL (Performance Dashboard) ----------
        right_panel = ttk.Frame(panes, width=350)
        panes.add(right_panel, weight=1)

        self._build_right_panel(right_panel)

    # ------------------------------------------------------------------ #
    #  LEFT panel — directory tree + quick controls
    # ------------------------------------------------------------------ #

    def _build_left_panel(self, parent: ttk.Frame):
        """Populate the left panel with a Treeview and action buttons."""

        # ---- Directory tree ----
        tree_frame = ttk.LabelFrame(parent, text="  Directory Tree  ")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self._dir_tree_view = ttk.Treeview(tree_frame, show="tree")
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                     command=self._dir_tree_view.yview)
        self._dir_tree_view.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._dir_tree_view.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # ---- Quick controls ----
        ctrl_frame = ttk.LabelFrame(parent, text="  Quick Controls  ")
        ctrl_frame.pack(fill=tk.X, padx=2, pady=2)

        btn_kw = dict(padding=(6, 3))
        ttk.Button(ctrl_frame, text="📁 New Directory", command=self._op_create_directory, **btn_kw).pack(fill=tk.X, padx=4, pady=1)
        ttk.Button(ctrl_frame, text="📄 New File",      command=self._op_create_file,      **btn_kw).pack(fill=tk.X, padx=4, pady=1)
        ttk.Button(ctrl_frame, text="🗑  Delete",        command=self._op_delete,            **btn_kw).pack(fill=tk.X, padx=4, pady=1)
        ttk.Button(ctrl_frame, text="🔄 Refresh",       command=self._update_all_panels,    **btn_kw).pack(fill=tk.X, padx=4, pady=(1, 4))

        # ---- Disk info ----
        info_frame = ttk.LabelFrame(parent, text="  Disk Info  ")
        info_frame.pack(fill=tk.X, padx=2, pady=2)

        self._disk_info_var = tk.StringVar(value="—")
        ttk.Label(info_frame, textvariable=self._disk_info_var,
                  wraplength=300, justify=tk.LEFT).pack(padx=4, pady=4)

    # ------------------------------------------------------------------ #
    #  CENTRE panel — disk visualisation (block grid)
    # ------------------------------------------------------------------ #

    def _build_centre_panel(self, parent: ttk.Frame):
        """Populate the centre panel with a canvas-based block grid."""

        vis_frame = ttk.LabelFrame(parent, text="  Disk Block Visualisation  ")
        vis_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self._disk_canvas = tk.Canvas(vis_frame,
                                      bg=self._palette["surface"],
                                      highlightthickness=0)
        self._disk_canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Fragmentation bar
        frag_frame = ttk.LabelFrame(parent, text="  Fragmentation  ")
        frag_frame.pack(fill=tk.X, padx=2, pady=2)

        self._frag_var = tk.DoubleVar(value=0.0)
        self._frag_bar = ttk.Progressbar(frag_frame, variable=self._frag_var,
                                          maximum=100,
                                          style="Horizontal.TProgressbar")
        self._frag_bar.pack(fill=tk.X, padx=8, pady=2)

        self._frag_label_var = tk.StringVar(value="Fragmentation: 0.0 %")
        ttk.Label(frag_frame, textvariable=self._frag_label_var).pack(pady=(0, 4))

    # ------------------------------------------------------------------ #
    #  RIGHT panel — performance dashboard
    # ------------------------------------------------------------------ #

    def _build_right_panel(self, parent: ttk.Frame):
        """Populate the right panel with performance metrics."""

        perf_frame = ttk.LabelFrame(parent, text="  Performance Dashboard  ")
        perf_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self._perf_text = tk.Text(perf_frame, wrap=tk.WORD,
                                   bg=self._palette["surface"],
                                   fg=self._palette["fg"],
                                   font=("Consolas", 9),
                                   borderwidth=0, relief=tk.FLAT,
                                   state=tk.DISABLED)
        perf_scroll = ttk.Scrollbar(perf_frame, orient=tk.VERTICAL,
                                     command=self._perf_text.yview)
        self._perf_text.configure(yscrollcommand=perf_scroll.set)
        perf_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._perf_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Actions
        action_frame = ttk.LabelFrame(parent, text="  Actions  ")
        action_frame.pack(fill=tk.X, padx=2, pady=2)

        ttk.Button(action_frame, text="▶ Benchmark",  command=self._tool_benchmark).pack(fill=tk.X, padx=4, pady=1)
        ttk.Button(action_frame, text="🧹 Clear Cache", command=self._tool_clear_cache).pack(fill=tk.X, padx=4, pady=1)
        ttk.Button(action_frame, text="⚠ Simulate Crash", command=self._rec_simulate_crash).pack(fill=tk.X, padx=4, pady=1)
        ttk.Button(action_frame, text="🔧 Recover",     command=self._rec_recover).pack(fill=tk.X, padx=4, pady=(1, 4))

        # Journal summary
        journal_frame = ttk.LabelFrame(parent, text="  Journal  ")
        journal_frame.pack(fill=tk.X, padx=2, pady=2)

        self._journal_var = tk.StringVar(value="—")
        ttk.Label(journal_frame, textvariable=self._journal_var,
                  wraplength=300, justify=tk.LEFT).pack(padx=4, pady=4)

    # --------------------------------------------------------------------- #
    #  Panel refresh helpers
    # --------------------------------------------------------------------- #

    def _update_all_panels(self):
        """Refresh every UI panel with current state."""
        self._refresh_directory_tree()
        self._refresh_disk_canvas()
        self._refresh_dashboard()
        self._refresh_disk_info()
        self._refresh_journal_info()

    def _refresh_dashboard(self):
        """Redraw the performance dashboard text widget."""
        try:
            metrics = self.perf_analyzer.collect_metrics()
            score = self.perf_analyzer.calculate_performance_score()
            cache_stats = self.cache.get_cache_stats()
            disk_info = self.disk.get_disk_info()

            lines = [
                f"=== Performance Score: {score:.1f} / 100 ===",
                "",
                f"Disk usage:      {metrics.get('disk_usage_percentage', 0):.1f} %",
                f"Free space:      {metrics.get('free_space_percentage', 100):.1f} %",
                f"Fragmentation:   {metrics.get('fragmentation_percentage', 0):.1f} %",
                "",
                f"Cache hit rate:  {cache_stats.get('hit_rate', 0):.1f} %",
                f"Cache size:      {cache_stats.get('cache_size', 0)}"
                f" / {cache_stats.get('max_cache_size', 0)}",
                f"Evictions:       {cache_stats.get('eviction_count', 0)}",
                "",
                f"Total reads:     {disk_info.get('total_reads', 0)}",
                f"Total writes:    {disk_info.get('total_writes', 0)}",
                f"Blocks used:     {disk_info.get('blocks_used', 0)}"
                f" / {disk_info.get('total_blocks', 0)}",
            ]
            text = "\n".join(lines)

            self._perf_text.configure(state=tk.NORMAL)
            self._perf_text.delete("1.0", tk.END)
            self._perf_text.insert(tk.END, text)
            self._perf_text.configure(state=tk.DISABLED)

            frag = metrics.get("fragmentation_percentage", 0)
            self._frag_var.set(frag)
            self._frag_label_var.set(f"Fragmentation: {frag:.1f} %")
        except Exception as exc:
            logger.debug("Dashboard refresh error: %s", exc)

    def _refresh_directory_tree(self):
        """Rebuild the Treeview from the DirectoryTree model."""
        tree = self._dir_tree_view
        tree.delete(*tree.get_children())

        def _insert(parent_id, node):
            label = node.name
            if node.is_directory:
                label += "/"
            iid = tree.insert(parent_id, tk.END, text=label, open=True)
            if node.is_directory:
                for child_name in sorted(node.children.keys()):
                    _insert(iid, node.children[child_name])

        _insert("", self.dir_tree.root)

    def _refresh_disk_canvas(self):
        """Draw a colour-coded block grid on the canvas."""
        canvas = self._disk_canvas
        canvas.delete("all")

        total = self.disk.total_blocks
        cw = canvas.winfo_width() or 680
        ch = canvas.winfo_height() or 400

        # Decide grid dimensions
        cols = max(1, cw // 8)
        rows = max(1, (total + cols - 1) // cols)
        cell_w = max(2, cw / cols)
        cell_h = max(2, ch / rows)

        p = self._palette
        for i in range(total):
            r = i // cols
            c = i % cols
            x1 = c * cell_w
            y1 = r * cell_h
            x2 = x1 + cell_w - 1
            y2 = y1 + cell_h - 1

            # Determine colour
            owner = self.fat.block_to_file.get(i)
            if owner is not None:
                # Pick a hue based on inode number
                hue_idx = owner % 6
                colours = [p["accent"], p["green"], p["yellow"],
                           p["red"], "#cba6f7", "#fab387"]
                colour = colours[hue_idx]
            elif self.fsm.bitmap[i] == 1:
                colour = p["yellow"]        # allocated but unowned
            else:
                colour = p["surface"]       # free

            canvas.create_rectangle(x1, y1, x2, y2,
                                    fill=colour, outline="")

    def _refresh_disk_info(self):
        """Update the disk-info label."""
        try:
            info = self.disk.get_disk_info()
            self._disk_info_var.set(
                f"Blocks: {info['blocks_used']} / {info['total_blocks']}  "
                f"({info['total_capacity_mb']:.1f} MB)\n"
                f"Block size: {info['block_size']} B\n"
                f"Reads: {info['total_reads']}   "
                f"Writes: {info['total_writes']}"
            )
        except Exception:
            pass

    def _refresh_journal_info(self):
        """Update the journal summary label."""
        try:
            stats = self.journal.get_statistics()
            self._journal_var.set(
                f"Entries: {stats['total_entries']}  "
                f"(P:{stats['pending_count']}  "
                f"C:{stats['committed_count']}  "
                f"A:{stats['aborted_count']})"
            )
        except Exception:
            pass

    def _schedule_refresh(self):
        """Schedule a periodic UI refresh (every 2 s)."""
        self._update_all_panels()
        self.root.after(2000, self._schedule_refresh)

    # --------------------------------------------------------------------- #
    #  Log helper
    # --------------------------------------------------------------------- #

    def _log(self, message: str):
        """Append a timestamped line to the log console."""
        ts = time.strftime("%H:%M:%S")
        self._log_text.insert(tk.END, f"[{ts}] {message}\n")
        self._log_text.see(tk.END)

    # --------------------------------------------------------------------- #
    #  File menu handlers
    # --------------------------------------------------------------------- #

    def new_disk(self):
        """Prompt for parameters and create a fresh file system."""
        try:
            blocks = simpledialog.askinteger(
                "New Disk", "Total blocks:", initialvalue=1000,
                minvalue=10, maxvalue=1_000_000, parent=self.root)
            if blocks is None:
                return
            bsize = simpledialog.askinteger(
                "New Disk", "Block size (bytes):", initialvalue=4096,
                minvalue=128, maxvalue=65536, parent=self.root)
            if bsize is None:
                return

            self._initialize_file_system(blocks, bsize)
            self._update_all_panels()
            self.current_disk_path = ""
            self._log(f"New disk created: {blocks} blocks × {bsize} B")
            self._status_var.set(f"New disk — {blocks} blocks")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def open_disk(self):
        """Load a disk image file and rebuild all components."""
        path = filedialog.askopenfilename(
            title="Open Disk Image",
            filetypes=[("Disk Images", "*.img *.bin *.dat"), ("All Files", "*.*")],
            parent=self.root)
        if not path:
            return
        try:
            self.disk = Disk.load_from_file(path)
            # Re-initialise dependent components with the loaded disk's geometry
            tb = self.disk.total_blocks
            self.fsm = FreeSpaceManager(total_blocks=tb)
            self.dir_tree = DirectoryTree()
            self.fat = FileAllocationTable(allocation_method="indexed")
            self.journal = Journal(journal_file="data/journal.log")
            self.crash_sim = CrashSimulator()
            self.cache = CacheManager(disk=self.disk, cache_size=100)
            self.file_system_components = {
                "disk": self.disk, "fsm": self.fsm,
                "directory_tree": self.dir_tree, "fat": self.fat,
                "journal": self.journal, "cache": self.cache,
            }
            self.recovery_mgr = RecoveryManager(self.file_system_components)
            self.defragmenter = Defragmenter(self.file_system_components)
            self.perf_analyzer = PerformanceAnalyzer(self.file_system_components)

            self.current_disk_path = path
            self._update_all_panels()
            self._log(f"Disk loaded from {path}")
            self._status_var.set(f"Loaded: {os.path.basename(path)}")
        except Exception as exc:
            logger.exception("Failed to open disk")
            messagebox.showerror("Open Error", str(exc))

    def save_disk(self):
        """Save the disk state; prompt for path if none is set."""
        if not self.current_disk_path:
            self.save_disk_as()
            return
        self._do_save(self.current_disk_path)

    def save_disk_as(self):
        """Prompt for a file path, then save the disk state."""
        path = filedialog.asksaveasfilename(
            title="Save Disk Image As",
            defaultextension=".img",
            filetypes=[("Disk Images", "*.img *.bin *.dat"), ("All Files", "*.*")],
            parent=self.root)
        if not path:
            return
        self.current_disk_path = path
        self._do_save(path)

    def _do_save(self, path: str):
        """Persist disk + journal to *path*."""
        try:
            self.disk.save_to_file(path)
            self.journal.save_journal()
            self._unsaved_changes = False
            self._log(f"Disk saved to {path}")
            self._status_var.set(f"Saved: {os.path.basename(path)}")
            messagebox.showinfo("Save", "Disk state saved successfully.",
                                parent=self.root)
        except Exception as exc:
            logger.exception("Failed to save disk")
            messagebox.showerror("Save Error", str(exc))

    def exit_application(self):
        """Prompt to save unsaved changes, then close."""
        if self._unsaved_changes:
            ans = messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have unsaved changes. Save before exiting?",
                parent=self.root)
            if ans is None:   # Cancel
                return
            if ans:           # Yes
                self.save_disk()
        self.perf_analyzer.stop_monitoring()
        self.root.destroy()

    # --------------------------------------------------------------------- #
    #  Edit menu handlers
    # --------------------------------------------------------------------- #

    def _show_preferences(self):
        messagebox.showinfo("Preferences",
                            "Preferences panel not yet implemented.",
                            parent=self.root)

    def _show_configuration(self):
        messagebox.showinfo("Configuration",
                            "Configuration panel not yet implemented.",
                            parent=self.root)

    # --------------------------------------------------------------------- #
    #  Operations menu handlers
    # --------------------------------------------------------------------- #

    def _op_create_file(self):
        """Create a new file in the directory tree."""
        try:
            path = simpledialog.askstring("Create File",
                                          "File path (e.g. /home/test.txt):",
                                          parent=self.root)
            if not path:
                return

            num_blocks = simpledialog.askinteger("Create File",
                                                  "Number of blocks:",
                                                  initialvalue=2,
                                                  minvalue=1, maxvalue=100,
                                                  parent=self.root)
            if num_blocks is None:
                return

            inode_num = self.inode_counter
            blocks = self.fsm.allocate_blocks(num_blocks, contiguous=False)
            if blocks is None:
                messagebox.showwarning("Allocation Failed",
                                       "Not enough free space.",
                                       parent=self.root)
                return

            self.fat.allocate(inode_num, blocks)
            inode = Inode(inode_number=inode_num, file_type="file",
                          size=num_blocks * self.disk.block_size)

            # Ensure parent directories exist
            parts = path.rsplit("/", 1)
            if len(parts) == 2 and parts[0]:
                self.dir_tree.create_directory(parts[0])

            if not self.dir_tree.create_file(path, inode):
                messagebox.showwarning("Create File",
                                       f"Could not create '{path}'.",
                                       parent=self.root)
                return

            # Write placeholder data
            for b in blocks:
                self.disk.write_block(b, f"DATA_{inode_num}".encode().ljust(
                    self.disk.block_size, b"\x00"))

            # Journal
            txn = self.journal.begin_transaction("CREATE",
                                                  {"path": path,
                                                   "inode": inode_num,
                                                   "blocks": blocks})
            self.journal.commit_transaction(txn)

            self.inode_counter += 1
            self._unsaved_changes = True
            self._update_all_panels()
            self._log(f"Created file: {path}  ({num_blocks} blocks)")
        except Exception as exc:
            logger.exception("Create file failed")
            messagebox.showerror("Error", str(exc), parent=self.root)

    def _op_create_directory(self):
        """Create a new directory."""
        try:
            path = simpledialog.askstring("Create Directory",
                                          "Directory path (e.g. /home/docs):",
                                          parent=self.root)
            if not path:
                return
            if self.dir_tree.create_directory(path):
                txn = self.journal.begin_transaction("MKDIR",
                                                      {"path": path})
                self.journal.commit_transaction(txn)
                self._unsaved_changes = True
                self._update_all_panels()
                self._log(f"Created directory: {path}")
            else:
                messagebox.showwarning("Create Directory",
                                       f"Could not create '{path}'.",
                                       parent=self.root)
        except Exception as exc:
            logger.exception("Create directory failed")
            messagebox.showerror("Error", str(exc), parent=self.root)

    def _op_delete(self):
        """Delete a file or directory."""
        try:
            path = simpledialog.askstring("Delete",
                                          "Path to delete:",
                                          parent=self.root)
            if not path:
                return
            node = self.dir_tree.resolve_path(path)
            if node is None:
                messagebox.showwarning("Delete", f"'{path}' not found.",
                                       parent=self.root)
                return

            # Free associated blocks if it's a file with an inode
            if node.inode is not None:
                freed = self.fat.deallocate(node.inode.inode_number)
                if freed:
                    self.fsm.deallocate_blocks(freed)

            self.dir_tree.delete(path, recursive=True)
            txn = self.journal.begin_transaction("DELETE", {"path": path})
            self.journal.commit_transaction(txn)

            self._unsaved_changes = True
            self._update_all_panels()
            self._log(f"Deleted: {path}")
        except Exception as exc:
            logger.exception("Delete failed")
            messagebox.showerror("Error", str(exc), parent=self.root)

    def _op_defragment(self):
        """Run full defragmentation."""
        try:
            self._log("Starting defragmentation…")
            report = self.defragmenter.defragment_all()
            self._unsaved_changes = True
            self._update_all_panels()

            summary = (
                f"Defragmentation complete.\n\n"
                f"Files processed: {report.get('files_processed', 0)}\n"
                f"Blocks moved:    {report.get('total_blocks_moved', 0)}\n"
                f"Time:            {report.get('time_taken', 0):.3f} s\n"
                f"Before:          {report.get('initial_fragmentation_percentage', 0):.1f} %\n"
                f"After:           {report.get('final_fragmentation_percentage', 0):.1f} %"
            )
            self._log("Defragmentation finished.")
            messagebox.showinfo("Defragmentation", summary, parent=self.root)
        except Exception as exc:
            logger.exception("Defragmentation failed")
            messagebox.showerror("Error", str(exc), parent=self.root)

    # --------------------------------------------------------------------- #
    #  Recovery menu handlers
    # --------------------------------------------------------------------- #

    def _rec_simulate_crash(self):
        """Inject a random crash into the file system."""
        try:
            report = self.crash_sim.simulate_random_crash(
                self.file_system_components)
            self._unsaved_changes = True
            self._update_all_panels()

            desc = report.get("description", "Unknown crash")
            sev = report.get("severity", "?")
            self._log(f"Crash injected! [{sev}] {desc}")
            messagebox.showwarning(
                "Crash Simulated",
                f"Type: {report.get('crash_type', '?')}\n"
                f"Severity: {sev}\n"
                f"Description: {desc}",
                parent=self.root)
        except Exception as exc:
            logger.exception("Crash simulation failed")
            messagebox.showerror("Error", str(exc), parent=self.root)

    def _rec_recover(self):
        """Attempt journal-based recovery."""
        try:
            self._log("Starting recovery…")
            report = self.recovery_mgr.recover_from_journal()
            self._update_all_panels()

            ok = report.get("success", False)
            tag = "✅" if ok else "❌"
            self._log(f"Recovery {tag}: "
                       f"{len(report.get('recovered_transactions', []))} redone, "
                       f"{len(report.get('rolled_back_transactions', []))} undone")
            messagebox.showinfo(
                "Recovery",
                f"Success: {ok}\n"
                f"Recovered: {len(report.get('recovered_transactions', []))}\n"
                f"Rolled back: {len(report.get('rolled_back_transactions', []))}\n"
                f"Errors: {len(report.get('errors', []))}\n"
                f"Time: {report.get('recovery_time', 0):.3f} s",
                parent=self.root)
        except Exception as exc:
            logger.exception("Recovery failed")
            messagebox.showerror("Error", str(exc), parent=self.root)

    def _rec_fsck(self):
        """Run file-system consistency check."""
        try:
            self._log("Running FSCK…")
            report = self.recovery_mgr.perform_fsck(auto_repair=True)
            self._update_all_panels()

            issues = []
            if report.get("blocks_marked_free_but_allocated"):
                issues.append(f"Free-but-allocated: "
                              f"{report['blocks_marked_free_but_allocated']}")
            if report.get("blocks_marked_allocated_but_free"):
                issues.append(f"Allocated-but-free: "
                              f"{report['blocks_marked_allocated_but_free']}")
            if report.get("orphaned_inodes"):
                issues.append(f"Orphaned inodes: {report['orphaned_inodes']}")

            status = "No issues found." if not issues else "\n".join(issues)
            self._log(f"FSCK complete. {'Clean' if not issues else 'Issues found'}")
            messagebox.showinfo("FSCK Results",
                                f"Auto-repaired: {report.get('auto_repaired')}\n\n"
                                f"{status}",
                                parent=self.root)
        except Exception as exc:
            logger.exception("FSCK failed")
            messagebox.showerror("Error", str(exc), parent=self.root)

    # --------------------------------------------------------------------- #
    #  Tools menu handlers
    # --------------------------------------------------------------------- #

    def _tool_benchmark(self):
        """Run read/write benchmarks and display results."""
        try:
            self._log("Running benchmarks…")
            read_r = self.perf_analyzer.benchmark_read_performance()
            write_r = self.perf_analyzer.benchmark_write_performance()
            self._update_all_panels()

            lines = ["=== Read Benchmark ==="]
            for sz, mbps in read_r.get("sequential_read_mbps", {}).items():
                lines.append(f"  {sz:>10} B  →  {mbps:.1f} MB/s (seq)")
            lines.append("\n=== Write Benchmark ===")
            for sz, mbps in write_r.get("sequential_write_mbps", {}).items():
                lines.append(f"  {sz:>10} B  →  {mbps:.1f} MB/s (seq)")

            self._log("Benchmarks complete.")
            messagebox.showinfo("Benchmark Results", "\n".join(lines),
                                parent=self.root)
        except Exception as exc:
            logger.exception("Benchmark failed")
            messagebox.showerror("Error", str(exc), parent=self.root)

    def _tool_clear_cache(self):
        """Flush and clear the block cache."""
        try:
            self.cache.flush_dirty_blocks()
            self.cache.clear_cache()
            self._update_all_panels()
            self._log("Cache cleared.")
            messagebox.showinfo("Cache", "Block cache has been cleared.",
                                parent=self.root)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self.root)

    def _tool_export_report(self):
        """Export a performance report to a text file."""
        path = filedialog.asksaveasfilename(
            title="Export Report",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            parent=self.root)
        if not path:
            return
        try:
            report = self.perf_analyzer.generate_performance_report("text")
            with open(path, "w", encoding="utf-8") as f:
                f.write(report)
            self._log(f"Report exported to {path}")
            messagebox.showinfo("Export", "Report saved.", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self.root)

    # --------------------------------------------------------------------- #
    #  Help menu
    # --------------------------------------------------------------------- #

    def _show_documentation(self):
        """Show a brief documentation dialog."""
        messagebox.showinfo(
            "Documentation",
            "File System Recovery & Optimization Tool\n\n"
            "Use the Operations menu to create files/directories,\n"
            "the Recovery menu to simulate & recover from crashes,\n"
            "and the Tools menu to benchmark performance.\n\n"
            "See README.md for full documentation.",
            parent=self.root)

    def _show_about_dialog(self):
        """Show the About dialog."""
        messagebox.showinfo(
            "About",
            "File System Recovery & Optimization Tool\n"
            "─────────────────────────────────────────\n"
            "Version 1.0\n\n"
            "A simulated block-based file system with:\n"
            "  • Disk, FAT, Inode, Directory Tree\n"
            "  • Journal-based crash recovery\n"
            "  • Defragmentation & caching\n"
            "  • Performance analysis\n\n"
            "Built with Python + Tkinter",
            parent=self.root)

    # --------------------------------------------------------------------- #
    #  Main event loop
    # --------------------------------------------------------------------- #

    def run(self):
        """Enter the Tkinter main event loop."""
        self.root.mainloop()
