"""
disk_visualizer.py - Interactive disk block visualization component.

Provides a DiskVisualizer class that renders a colored grid of disk
blocks on a ``tk.Canvas``.  Each block is colour-coded by state (free,
allocated, system, fragmented).  Supports tooltips on hover, click
details, zoom in/out, file-block highlighting, fragmentation heatmap,
animated allocation/deallocation, and PNG export.

Dependencies:
    - tkinter (stdlib): Canvas drawing and widget creation.
    - PIL (optional): Export the visualization as a PNG image.
    - Disk, FreeSpaceManager, FileAllocationTable: Core FS modules.

Usage::

    from src.ui.disk_visualizer import DiskVisualizer

    visualizer = DiskVisualizer(parent_frame, disk, fsm, fat)
    visualizer.update_display()
"""

import logging
import math
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Optional

from src.core.disk import Disk
from src.core.free_space import FreeSpaceManager
from src.core.file_allocation_table import FileAllocationTable

logger = logging.getLogger(__name__)


# ====================================================================== #
#  Constants
# ====================================================================== #

# Default pixel size for each block square
_DEFAULT_BLOCK_SIZE_PX = 14

# Minimum / maximum zoom limits (pixels per block)
_MIN_BLOCK_SIZE_PX = 4
_MAX_BLOCK_SIZE_PX = 40

# Animation step duration in milliseconds
_ANIM_STEP_MS = 60
_ANIM_TOTAL_STEPS = 10

# Legend / stats panel height
_LEGEND_HEIGHT = 70

# Tooltip styling
_TOOLTIP_BG = "#2a2a4a"
_TOOLTIP_FG = "#e0e0e0"
_TOOLTIP_FONT = ("Consolas", 9)


class DiskVisualizer:
    """
    Interactive disk block visualization drawn on a ``tk.Canvas``.

    Renders a grid of colored rectangles — one per disk block — inside
    a scrollable canvas.  Supports hover tooltips, click detail dialogs,
    zoom, file-highlight overlays, fragmentation heatmaps, and animated
    block operations.

    Attributes:
        parent_frame (ttk.Frame): Parent container.
        disk (Disk): Reference to the simulated disk.
        fsm (FreeSpaceManager): Reference to the free space manager.
        fat (FileAllocationTable): Reference to the file allocation table.
        canvas (tk.Canvas): Canvas widget used for drawing.
        block_size_pixels (int): Side length of each block square (px).
        blocks_per_row (int): Number of blocks drawn per row.
        color_scheme (dict): Maps block state names to hex colours.
        tooltip (tk.Label): Floating tooltip label for hover info.
    """

    # ------------------------------------------------------------------ #
    #  Initialization
    # ------------------------------------------------------------------ #

    def __init__(self, parent_frame: ttk.Frame, disk: Disk,
                 fsm: FreeSpaceManager, fat: FileAllocationTable):
        """
        Initialize the disk visualizer.

        Creates the canvas with scrollbars, sets up the colour scheme,
        binds mouse events, and performs the initial draw.

        Args:
            parent_frame (ttk.Frame): Tkinter container to pack into.
            disk (Disk): Disk instance to visualize.
            fsm (FreeSpaceManager): Free space manager instance.
            fat (FileAllocationTable): File allocation table instance.
        """
        self.parent_frame = parent_frame
        self.disk = disk
        self.fsm = fsm
        self.fat = fat

        # Layout parameters
        self.block_size_pixels: int = _DEFAULT_BLOCK_SIZE_PX
        self.blocks_per_row: int = 32  # recalculated in _calculate_layout

        # Highlighted inode (for file-block highlighting)
        self._highlighted_inode: Optional[int] = None

        # Animation state
        self._anim_after_id: Optional[str] = None

        # Color scheme
        self.color_scheme: Dict[str, str] = {
            "free":        "#90EE90",   # light green
            "allocated":   "#F08080",   # light coral
            "system":      "#ADD8E6",   # light blue
            "fragmented":  "#FFFF99",   # yellow
            "highlight":   "#FFA500",   # orange  (file highlight)
            "corrupt":     "#FF4444",   # red
            "outline":     "#555555",
        }

        # ---- Build widgets ----
        self._build_toolbar()
        self._build_canvas()
        self._create_tooltip_window()

        # ---- Mouse bindings ----
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Leave>", lambda _e: self._hide_tooltip())
        self.canvas.bind("<Button-1>", self.on_click)

        # ---- Recalculate on resize ----
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # ---- Initial draw ----
        self.parent_frame.after(100, self.draw_disk)

    # ------------------------------------------------------------------ #
    #  Widget construction helpers
    # ------------------------------------------------------------------ #

    def _build_toolbar(self) -> None:
        """Create a toolbar with zoom and heatmap controls."""
        toolbar = ttk.Frame(self.parent_frame)
        toolbar.pack(fill="x", padx=4, pady=(4, 0))

        ttk.Button(toolbar, text="🔍+ Zoom In",
                   command=self.zoom_in).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🔍− Zoom Out",
                   command=self.zoom_out).pack(side="left", padx=2)

        ttk.Separator(toolbar, orient="vertical").pack(
            side="left", fill="y", padx=6, pady=2)

        ttk.Button(toolbar, text="🌡️ Heatmap",
                   command=self.show_fragmentation_heatmap).pack(
            side="left", padx=2)
        ttk.Button(toolbar, text="↺ Normal View",
                   command=self.update_display).pack(
            side="left", padx=2)

        ttk.Separator(toolbar, orient="vertical").pack(
            side="left", fill="y", padx=6, pady=2)

        ttk.Button(toolbar, text="💾 Export PNG",
                   command=self._action_export).pack(side="left", padx=2)

    def _build_canvas(self) -> None:
        """Create the canvas with vertical and horizontal scrollbars."""
        wrapper = ttk.Frame(self.parent_frame)
        wrapper.pack(fill="both", expand=True, padx=4, pady=4)

        self.canvas = tk.Canvas(
            wrapper, bg="#1a1a2e", highlightthickness=0,
        )

        v_scroll = ttk.Scrollbar(wrapper, orient="vertical",
                                 command=self.canvas.yview)
        h_scroll = ttk.Scrollbar(wrapper, orient="horizontal",
                                 command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v_scroll.set,
                              xscrollcommand=h_scroll.set)

        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

    def _create_tooltip_window(self) -> None:
        """Create the floating tooltip label (hidden initially)."""
        self.tooltip = tk.Label(
            self.canvas, text="", bg=_TOOLTIP_BG, fg=_TOOLTIP_FG,
            font=_TOOLTIP_FONT, padx=6, pady=3, relief="solid",
            borderwidth=1, justify="left",
        )
        # The tooltip is placed via canvas window — not packed.

    # ------------------------------------------------------------------ #
    #  Layout helpers
    # ------------------------------------------------------------------ #

    def _calculate_layout(self) -> None:
        """
        Recalculate ``blocks_per_row`` based on the current canvas width
        and ``block_size_pixels``.
        """
        self.canvas.update_idletasks()
        canvas_width = max(self.canvas.winfo_width(), 200)
        self.blocks_per_row = max(1, canvas_width // self.block_size_pixels)

    @property
    def total_rows(self) -> int:
        """Total number of rows needed to display all blocks."""
        return math.ceil(self.disk.total_blocks / max(1, self.blocks_per_row))

    # ------------------------------------------------------------------ #
    #  Drawing
    # ------------------------------------------------------------------ #

    def draw_disk(self) -> None:
        """
        Clear the canvas and redraw the full block grid, legend, and
        statistics.
        """
        self.canvas.delete("all")
        self._calculate_layout()

        bs = self.block_size_pixels
        total = self.disk.total_blocks

        block_num = 0
        for row in range(self.total_rows):
            for col in range(self.blocks_per_row):
                if block_num >= total:
                    break

                x = col * bs
                y = row * bs

                color = self._get_block_color(block_num)

                self.canvas.create_rectangle(
                    x, y,
                    x + bs, y + bs,
                    fill=color,
                    outline=self.color_scheme["outline"],
                    tags=f"block_{block_num}",
                )
                block_num += 1

        # Update scroll region to encompass the grid + legend
        grid_height = self.total_rows * bs
        total_height = grid_height + _LEGEND_HEIGHT + 10
        total_width = self.blocks_per_row * bs
        self.canvas.configure(
            scrollregion=(0, 0, total_width, total_height)
        )

        self.add_legend()

    def update_display(self) -> None:
        """Refresh the visualization by redrawing the disk grid."""
        self._highlighted_inode = None
        self.draw_disk()

    # ------------------------------------------------------------------ #
    #  Block color logic
    # ------------------------------------------------------------------ #

    def _get_block_color(self, block_num: int) -> str:
        """
        Determine the display colour for a specific block.

        Priority order:
        1. Highlighted inode  → orange
        2. Corrupt data       → red
        3. System block (< 2) → light blue
        4. Allocated & fragmented → yellow
        5. Allocated          → coral
        6. Free               → green

        Args:
            block_num: Zero-based block index.

        Returns:
            Hex colour string.
        """
        # 1) File-highlight overlay
        if self._highlighted_inode is not None:
            blocks = self.fat.file_to_blocks.get(self._highlighted_inode, [])
            if block_num in blocks:
                return self.color_scheme["highlight"]

        # 2) Corruption check
        data = self.disk.blocks[block_num]
        if isinstance(data, bytes) and (
                b"CORRUPTED" in data or b"BAD_SECTOR" in data):
            return self.color_scheme["corrupt"]

        # 3) System block (first 2 blocks reserved)
        if block_num < 2:
            return self.color_scheme["system"]

        # 4/5) Allocated
        is_allocated = self.fsm.bitmap[block_num] == 1
        if is_allocated:
            owner = self.fat.block_to_file.get(block_num)
            if owner is not None and self.fat.is_fragmented(owner):
                return self.color_scheme["fragmented"]
            return self.color_scheme["allocated"]

        # 6) Free
        return self.color_scheme["free"]

    # ------------------------------------------------------------------ #
    #  Mouse events
    # ------------------------------------------------------------------ #

    def on_mouse_move(self, event: tk.Event) -> None:
        """
        Handle mouse hover — show a tooltip with block info if the cursor
        is over a block.
        """
        block_num = self._get_block_at_position(
            self.canvas.canvasx(event.x),
            self.canvas.canvasy(event.y),
        )
        if block_num is None:
            self._hide_tooltip()
            return
        self._show_tooltip(block_num, event.x, event.y)

    def on_click(self, event: tk.Event) -> None:
        """
        Handle click — open a detail dialog for the block under the
        cursor.
        """
        block_num = self._get_block_at_position(
            self.canvas.canvasx(event.x),
            self.canvas.canvasy(event.y),
        )
        if block_num is None:
            return

        # Gather information
        status = "Allocated" if self.fsm.bitmap[block_num] == 1 else "Free"
        owner = self.fat.block_to_file.get(block_num)
        owner_str = f"Inode #{owner}" if owner is not None else "None"

        data = self.disk.blocks[block_num]
        if data is not None:
            preview = data[:64].decode("utf-8", errors="replace")
            data_len = len(data)
        else:
            preview = "<empty>"
            data_len = 0

        # Build detail text
        detail = (
            f"Block #{block_num}\n"
            f"{'─' * 30}\n"
            f"Status:        {status}\n"
            f"Owner:         {owner_str}\n"
            f"Data size:     {data_len} bytes\n"
            f"Data preview:  {preview}\n"
        )

        # If allocated, check fragmentation
        if owner is not None:
            frag = self.fat.is_fragmented(owner)
            blocks = self.fat.file_to_blocks.get(owner, [])
            detail += (
                f"\n{'─' * 30}\n"
                f"File blocks:   {blocks}\n"
                f"Fragmented:    {'Yes' if frag else 'No'}\n"
            )

        messagebox.showinfo(f"Block #{block_num} Details", detail)

    # ------------------------------------------------------------------ #
    #  Position helpers
    # ------------------------------------------------------------------ #

    def _get_block_at_position(self, x: float, y: float) -> Optional[int]:
        """
        Calculate the block number from canvas coordinates.

        Args:
            x: Horizontal canvas coordinate (float from canvasx).
            y: Vertical canvas coordinate (float from canvasy).

        Returns:
            The block number or ``None`` if the position is outside
            the grid.
        """
        bs = self.block_size_pixels
        col = int(x) // bs
        row = int(y) // bs

        if col < 0 or col >= self.blocks_per_row:
            return None
        if row < 0 or row >= self.total_rows:
            return None

        block_num = row * self.blocks_per_row + col
        if block_num >= self.disk.total_blocks:
            return None
        return block_num

    # ------------------------------------------------------------------ #
    #  Tooltip
    # ------------------------------------------------------------------ #

    def _show_tooltip(self, block_num: int, x: int, y: int) -> None:
        """
        Display a tooltip near the cursor with block information.

        Args:
            block_num: Block index.
            x: Widget-relative x coordinate.
            y: Widget-relative y coordinate.
        """
        status = "Allocated" if self.fsm.bitmap[block_num] == 1 else "Free"
        owner = self.fat.block_to_file.get(block_num)
        owner_str = f"Inode #{owner}" if owner is not None else "—"

        text = (
            f"Block #{block_num}\n"
            f"Status: {status}\n"
            f"Owner:  {owner_str}"
        )

        self.tooltip.configure(text=text)

        # Place tooltip slightly offset from cursor (using canvas window)
        cx = self.canvas.canvasx(x) + 14
        cy = self.canvas.canvasy(y) + 14
        self.canvas.delete("tooltip_win")
        self.canvas.create_window(
            cx, cy, window=self.tooltip, anchor="nw", tags="tooltip_win"
        )

    def _hide_tooltip(self) -> None:
        """Hide the tooltip."""
        self.canvas.delete("tooltip_win")

    # ------------------------------------------------------------------ #
    #  File-block highlighting
    # ------------------------------------------------------------------ #

    def highlight_file_blocks(self, inode_number: int) -> None:
        """
        Highlight blocks belonging to a specific file with orange
        to visually show file fragmentation.

        Args:
            inode_number: The inode whose blocks should be highlighted.
        """
        self._highlighted_inode = inode_number
        self.draw_disk()

    def clear_highlights(self) -> None:
        """Remove all file-block highlights and return to normal view."""
        self._highlighted_inode = None
        self.draw_disk()

    # ------------------------------------------------------------------ #
    #  Legend and statistics
    # ------------------------------------------------------------------ #

    def add_legend(self) -> None:
        """
        Draw a legend and statistics summary below the block grid.
        """
        bs = self.block_size_pixels
        y_start = self.total_rows * bs + 10

        # ---- Color legend squares ----
        legend_items = [
            ("Free",       self.color_scheme["free"]),
            ("Allocated",  self.color_scheme["allocated"]),
            ("System",     self.color_scheme["system"]),
            ("Fragmented", self.color_scheme["fragmented"]),
            ("Corrupt",    self.color_scheme["corrupt"]),
            ("Highlight",  self.color_scheme["highlight"]),
        ]

        x = 10
        for label, color in legend_items:
            self.canvas.create_rectangle(
                x, y_start, x + 14, y_start + 14,
                fill=color, outline="#888",
            )
            self.canvas.create_text(
                x + 18, y_start + 7, text=label,
                fill="#e0e0e0", font=("Segoe UI", 8), anchor="w",
            )
            x += len(label) * 7 + 36

        # ---- Statistics ----
        total = self.disk.total_blocks
        free = self.fsm.get_free_count()
        allocated = self.fsm.get_allocated_count()
        frag_pct = self.fsm.get_fragmentation_percentage()

        stats_text = (
            f"Total: {total}  |  "
            f"Free: {free}  |  "
            f"Allocated: {allocated}  |  "
            f"Fragmentation: {frag_pct:.1f}%"
        )
        self.canvas.create_text(
            10, y_start + 28, text=stats_text,
            fill="#a0a0b0", font=("Segoe UI", 9), anchor="w",
        )

    # ------------------------------------------------------------------ #
    #  Zoom
    # ------------------------------------------------------------------ #

    def zoom_in(self) -> None:
        """Increase block size and redraw with larger blocks."""
        if self.block_size_pixels < _MAX_BLOCK_SIZE_PX:
            self.block_size_pixels = min(
                self.block_size_pixels + 4, _MAX_BLOCK_SIZE_PX
            )
            self.draw_disk()

    def zoom_out(self) -> None:
        """Decrease block size and redraw with smaller blocks."""
        if self.block_size_pixels > _MIN_BLOCK_SIZE_PX:
            self.block_size_pixels = max(
                self.block_size_pixels - 4, _MIN_BLOCK_SIZE_PX
            )
            self.draw_disk()

    # ------------------------------------------------------------------ #
    #  Export
    # ------------------------------------------------------------------ #

    def export_visualization(self, filepath: str) -> None:
        """
        Export the current canvas visualization as a PNG image.

        Uses Pillow (PIL) to capture the canvas contents.  If Pillow
        is not installed, saves as a PostScript file instead.

        Args:
            filepath: Destination file path (should end in ``.png``).
        """
        try:
            # Generate PostScript from canvas
            ps_path = filepath.replace(".png", ".ps")
            self.canvas.postscript(file=ps_path, colormode="color")

            try:
                from PIL import Image
                img = Image.open(ps_path)
                img.save(filepath, "PNG")
                import os
                os.remove(ps_path)
                logger.info("Exported visualization as PNG to %s", filepath)
            except ImportError:
                logger.warning(
                    "Pillow not installed — saved as PostScript: %s", ps_path
                )
                messagebox.showinfo(
                    "Export",
                    f"Pillow not installed.\n"
                    f"Saved as PostScript:\n{ps_path}"
                )
                return

            messagebox.showinfo("Export", f"Saved to:\n{filepath}")

        except Exception as exc:
            logger.error("Export failed: %s", exc)
            messagebox.showerror("Export Error", str(exc))

    def _action_export(self) -> None:
        """Prompt the user for a file path and export."""
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")],
        )
        if path:
            self.export_visualization(path)

    # ------------------------------------------------------------------ #
    #  Fragmentation heatmap
    # ------------------------------------------------------------------ #

    def show_fragmentation_heatmap(self) -> None:
        """
        Show an alternative visualization using a colour gradient
        based on local fragmentation density.

        - **Green**: Area is contiguous (low fragmentation).
        - **Yellow**: Moderate fragmentation.
        - **Red**: Highly fragmented area.

        The "heat" for each block is computed as the ratio of
        state-transitions in its local neighbourhood (±``window``
        blocks).
        """
        self.canvas.delete("all")
        self._calculate_layout()

        bs = self.block_size_pixels
        total = self.disk.total_blocks
        window = 8  # neighbourhood half-width

        block_num = 0
        for row in range(self.total_rows):
            for col in range(self.blocks_per_row):
                if block_num >= total:
                    break

                x = col * bs
                y = row * bs

                # Calculate local fragmentation heat
                heat = self._local_fragmentation(block_num, window)
                color = self._heat_to_color(heat)

                self.canvas.create_rectangle(
                    x, y, x + bs, y + bs,
                    fill=color,
                    outline=self.color_scheme["outline"],
                    tags=f"block_{block_num}",
                )
                block_num += 1

        # Legend
        grid_height = self.total_rows * bs
        y_top = grid_height + 10
        self.canvas.create_text(
            10, y_top, text="Heatmap:  ",
            fill="#e0e0e0", font=("Segoe UI", 9, "bold"), anchor="w",
        )

        # Gradient bar
        bar_x = 80
        bar_width = 200
        for i in range(bar_width):
            h = i / bar_width
            c = self._heat_to_color(h)
            self.canvas.create_line(
                bar_x + i, y_top - 4, bar_x + i, y_top + 10, fill=c,
            )
        self.canvas.create_text(
            bar_x - 4, y_top + 3, text="Low", fill="#90EE90",
            font=("Segoe UI", 8), anchor="e",
        )
        self.canvas.create_text(
            bar_x + bar_width + 4, y_top + 3, text="High", fill="#FF4444",
            font=("Segoe UI", 8), anchor="w",
        )

        # Update scroll region
        total_height = grid_height + _LEGEND_HEIGHT + 10
        total_width = self.blocks_per_row * bs
        self.canvas.configure(
            scrollregion=(0, 0, total_width, total_height)
        )

    def _local_fragmentation(self, block_num: int, window: int) -> float:
        """
        Compute a 0.0–1.0 fragmentation score for the neighbourhood
        around ``block_num``.

        Args:
            block_num: Centre block.
            window: Half-width of the neighbourhood.

        Returns:
            float between 0.0 (contiguous) and 1.0 (highly fragmented).
        """
        lo = max(0, block_num - window)
        hi = min(self.disk.total_blocks - 1, block_num + window)
        if hi <= lo:
            return 0.0

        transitions = 0
        for i in range(lo, hi):
            if self.fsm.bitmap[i] != self.fsm.bitmap[i + 1]:
                transitions += 1

        span = hi - lo
        return min(1.0, transitions / max(1, span))

    @staticmethod
    def _heat_to_color(heat: float) -> str:
        """
        Map a heat value (0.0–1.0) to a colour on a green→yellow→red
        gradient.

        Args:
            heat: Normalised fragmentation intensity.

        Returns:
            Hex colour string.
        """
        # Green (0.0) → Yellow (0.5) → Red (1.0)
        heat = max(0.0, min(1.0, heat))
        if heat < 0.5:
            r = int(255 * (heat * 2))
            g = 255
        else:
            r = 255
            g = int(255 * (1 - (heat - 0.5) * 2))
        b = 0
        return f"#{r:02x}{g:02x}{b:02x}"

    # ------------------------------------------------------------------ #
    #  Animated operations
    # ------------------------------------------------------------------ #

    def animate_operation(self, blocks: List[int],
                          operation: str = "allocate") -> None:
        """
        Animate block allocation or deallocation by smoothly
        transitioning colours over several frames.

        Args:
            blocks: Block numbers to animate.
            operation: ``'allocate'`` to transition free→allocated, or
                ``'deallocate'`` for allocated→free.
        """
        if not blocks:
            return

        if operation == "allocate":
            start_color = self.color_scheme["free"]
            end_color = self.color_scheme["allocated"]
        else:
            start_color = self.color_scheme["allocated"]
            end_color = self.color_scheme["free"]

        # Parse start/end RGB
        sr, sg, sb = self._hex_to_rgb(start_color)
        er, eg, eb = self._hex_to_rgb(end_color)

        self._animate_step(blocks, sr, sg, sb, er, eg, eb, step=0)

    def _animate_step(self, blocks: List[int],
                      sr: int, sg: int, sb: int,
                      er: int, eg: int, eb: int,
                      step: int) -> None:
        """Perform one animation frame and schedule the next."""
        if step > _ANIM_TOTAL_STEPS:
            # Final redraw to ensure clean state
            self.draw_disk()
            return

        t = step / _ANIM_TOTAL_STEPS
        r = int(sr + (er - sr) * t)
        g = int(sg + (eg - sg) * t)
        b = int(sb + (eb - sb) * t)
        color = f"#{r:02x}{g:02x}{b:02x}"

        for bn in blocks:
            tag = f"block_{bn}"
            self.canvas.itemconfigure(tag, fill=color)

        self._anim_after_id = self.canvas.after(
            _ANIM_STEP_MS,
            self._animate_step, blocks,
            sr, sg, sb, er, eg, eb, step + 1,
        )

    @staticmethod
    def _hex_to_rgb(hex_color: str):
        """Convert ``'#RRGGBB'`` to ``(R, G, B)`` ints."""
        hex_color = hex_color.lstrip("#")
        return (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )

    # ------------------------------------------------------------------ #
    #  Resize handler
    # ------------------------------------------------------------------ #

    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Redraw when the canvas is resized."""
        # Use after_cancel + after to debounce rapid resizes
        if hasattr(self, "_resize_after_id"):
            self.canvas.after_cancel(self._resize_after_id)
        self._resize_after_id = self.canvas.after(200, self.draw_disk)
