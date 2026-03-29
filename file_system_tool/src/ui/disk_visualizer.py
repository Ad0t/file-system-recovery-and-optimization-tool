"""
disk_visualizer.py — Interactive canvas-based disk block visualiser.

Renders every block on the simulated disk as a coloured rectangle
inside a scrollable ``tk.Canvas``.  Supports:

  • Hover tooltips with block info
  • Click for detailed block dialog
  • File-block highlighting
  • Fragmentation heat-map mode
  • Zoom in / out
  • Animated allocation / deallocation
  • PNG export (via Pillow if available)

Usage::

    from src.ui.disk_visualizer import DiskVisualizer

    viz = DiskVisualizer(parent_frame, disk, fsm, fat)
    viz.draw_disk()
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

# Try to import Pillow for PNG export — graceful fallback
try:
    from PIL import Image, ImageDraw  # noqa: F401
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


# =========================================================================== #
#  DiskVisualizer
# =========================================================================== #

class DiskVisualizer:
    """
    Interactive canvas widget that draws every disk block as a coloured
    square and provides hover / click interactivity plus zoom and
    animation support.

    Attributes
    ----------
    parent_frame : ttk.Frame
        Container widget that hosts the canvas.
    disk : Disk
        The simulated disk whose blocks are visualised.
    fsm : FreeSpaceManager
        Free-space bitmap used to determine block state.
    fat : FileAllocationTable
        File-to-block / block-to-file mappings.
    canvas : tk.Canvas
        The Tkinter canvas that holds the drawing.
    block_size_pixels : int
        Side-length of each block square in pixels.
    blocks_per_row : int
        Number of blocks drawn per row.
    color_scheme : dict[str, str]
        Hex colours keyed by block-state name.
    tooltip : tk.Toplevel | None
        Floating tooltip window (created on demand).
    """

    # ---- sizing defaults ------------------------------------------------- #
    _DEFAULT_BLOCK_PX = 12
    _MIN_BLOCK_PX = 4
    _MAX_BLOCK_PX = 40
    _ZOOM_STEP = 2

    # ---- legend geometry ------------------------------------------------- #
    _LEGEND_PAD = 10
    _LEGEND_SWATCH = 14

    # --------------------------------------------------------------------- #
    #  Construction
    # --------------------------------------------------------------------- #

    def __init__(self, parent_frame: ttk.Frame,
                 disk: Disk,
                 fsm: FreeSpaceManager,
                 fat: FileAllocationTable,
                 *,
                 directory_tree=None):
        """
        Build the disk visualiser inside *parent_frame*.

        Parameters
        ----------
        parent_frame : ttk.Frame
            Container widget.
        disk : Disk
            The disk model.
        fsm : FreeSpaceManager
            Block bitmap.
        fat : FileAllocationTable
            Block ownership mappings.
        directory_tree : DirectoryTree, optional
            Used to resolve inode numbers to file paths.
        """
        self.parent_frame = parent_frame
        self.disk = disk
        self.fsm = fsm
        self.fat = fat
        self._dir_tree = directory_tree

        self.block_size_pixels: int = self._DEFAULT_BLOCK_PX
        self.blocks_per_row: int = 1  # recalculated in _calculate_layout

        # Persistent visual state
        self._highlighted_inode: Optional[int] = None
        self._heatmap_mode: bool = False
        self._anim_after_id: Optional[str] = None

        # ---- colour palette ---------------------------------------------- #
        self.color_scheme: Dict[str, str] = {
            "free":        "#a6e3a1",   # green  (Catppuccin green)
            "allocated":   "#f38ba8",   # red    (Catppuccin red)
            "system":      "#89b4fa",   # blue   (Catppuccin blue)
            "fragmented":  "#f9e2af",   # yellow (Catppuccin yellow)
            "highlight":   "#fab387",   # orange (Catppuccin peach)
            "outline":     "#45475a",   # border
            "canvas_bg":   "#1e1e2e",   # background
            "legend_bg":   "#313244",   # legend panel
            "legend_fg":   "#cdd6f4",   # legend text
        }

        # ---- toolbar ----------------------------------------------------- #
        toolbar = ttk.Frame(parent_frame)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=2, pady=(2, 0))

        ttk.Button(toolbar, text="🔍+", width=4,
                   command=self.zoom_in).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🔍−", width=4,
                   command=self.zoom_out).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🌡 Heatmap",
                   command=self.show_fragmentation_heatmap).pack(
                       side=tk.LEFT, padx=6)
        ttk.Button(toolbar, text="↺ Reset",
                   command=self._reset_view).pack(side=tk.LEFT, padx=2)

        self._stats_var = tk.StringVar(value="")
        ttk.Label(toolbar, textvariable=self._stats_var).pack(
            side=tk.RIGHT, padx=6)

        # ---- canvas + scrollbars ----------------------------------------- #
        canvas_frame = ttk.Frame(parent_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.canvas = tk.Canvas(canvas_frame,
                                bg=self.color_scheme["canvas_bg"],
                                highlightthickness=0)

        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL,
                                  command=self.canvas.yview)
        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL,
                                  command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v_scroll.set,
                               xscrollcommand=h_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        # ---- tooltip window ---------------------------------------------- #
        self.tooltip: Optional[tk.Toplevel] = None
        self._create_tooltip_window()

        # ---- bind events ------------------------------------------------- #
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Leave>", lambda _e: self._hide_tooltip())
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # ---- initial draw ------------------------------------------------ #
        # We schedule the first draw so the canvas has its real size.
        self.canvas.after(50, self.draw_disk)

    # --------------------------------------------------------------------- #
    #  Layout calculation
    # --------------------------------------------------------------------- #

    def _calculate_layout(self):
        """
        Recalculate ``blocks_per_row`` and ``total_rows`` based on
        the current canvas width and ``block_size_pixels``.
        """
        cw = self.canvas.winfo_width()
        if cw < 10:
            cw = 600  # sensible fallback before the canvas is mapped
        self.blocks_per_row = max(1, cw // self.block_size_pixels)
        self.total_rows = math.ceil(
            self.disk.total_blocks / self.blocks_per_row)

    # --------------------------------------------------------------------- #
    #  Main draw
    # --------------------------------------------------------------------- #

    def draw_disk(self):
        """
        Clear the canvas and redraw every block as a coloured rectangle,
        then append the legend and update the statistics label.
        """
        self.canvas.delete("all")
        self._calculate_layout()

        bp = self.block_size_pixels
        total = self.disk.total_blocks

        block_num = 0
        for row in range(self.total_rows):
            for col in range(self.blocks_per_row):
                if block_num >= total:
                    break

                x1 = col * bp
                y1 = row * bp
                x2 = x1 + bp
                y2 = y1 + bp

                colour = self._get_block_color(block_num)

                self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=colour,
                    outline=self.color_scheme["outline"],
                    tags=(f"block_{block_num}", "block"),
                )
                block_num += 1

        # Legend below the grid
        self.add_legend()

        # Scroll region
        self.canvas.configure(
            scrollregion=self.canvas.bbox("all") or (0, 0, 600, 400))

        # Stats in toolbar
        self._update_stats_label()

    # --------------------------------------------------------------------- #
    #  Refresh alias
    # --------------------------------------------------------------------- #

    def update_display(self):
        """Refresh the visualisation by redrawing the entire disk."""
        self.draw_disk()

    # --------------------------------------------------------------------- #
    #  Block colour
    # --------------------------------------------------------------------- #

    def _get_block_color(self, block_num: int) -> str:
        """
        Return the hex colour for *block_num* according to its state.

        Priority order:
        1. Highlighted file → orange
        2. Heat-map mode → gradient
        3. System block (block 0) → blue
        4. Allocated (owner in FAT) → file-hue or red
        5. Allocated bitmap but no FAT owner → yellow (fragmented / orphan)
        6. Free → green
        """
        cs = self.color_scheme

        # 1. Highlighted inode
        if self._highlighted_inode is not None:
            owner = self.fat.block_to_file.get(block_num)
            if owner == self._highlighted_inode:
                return cs["highlight"]

        # 2. Heat-map mode
        if self._heatmap_mode:
            return self._heatmap_color(block_num)

        # 3. System block (first block)
        if block_num == 0:
            return cs["system"]

        # 4–6. Normal mode
        owner = self.fat.block_to_file.get(block_num)
        if owner is not None:
            # Cycle through a palette per file inode
            file_colours = [
                "#89b4fa", "#a6e3a1", "#f9e2af",
                "#f38ba8", "#cba6f7", "#fab387",
                "#94e2d5", "#f2cdcd", "#74c7ec",
            ]
            return file_colours[owner % len(file_colours)]

        if self.fsm.bitmap[block_num] == 1:
            return cs["fragmented"]   # allocated but unowned — suspicious

        return cs["free"]

    # --------------------------------------------------------------------- #
    #  Heat-map helper
    # --------------------------------------------------------------------- #

    def _heatmap_color(self, block_num: int) -> str:
        """
        Return a heat-map gradient colour for *block_num*.

        Measures local fragmentation in a neighbourhood of ±8 blocks:
        more transitions → hotter (red), fewer → cooler (green).
        """
        radius = 8
        lo = max(0, block_num - radius)
        hi = min(self.disk.total_blocks - 1, block_num + radius)

        transitions = 0
        for i in range(lo, hi):
            if self.fsm.bitmap[i] != self.fsm.bitmap[i + 1]:
                transitions += 1

        span = hi - lo
        if span == 0:
            ratio = 0.0
        else:
            ratio = min(1.0, transitions / (span * 0.5))

        # Lerp green → yellow → red
        if ratio < 0.5:
            t = ratio * 2
            r = int(166 + (249 - 166) * t)
            g = int(227 + (226 - 227) * t)
            b = int(161 + (175 - 161) * t)
        else:
            t = (ratio - 0.5) * 2
            r = int(249 + (243 - 249) * t)
            g = int(226 + (139 - 226) * t)
            b = int(175 + (168 - 175) * t)

        return f"#{r:02x}{g:02x}{b:02x}"

    # --------------------------------------------------------------------- #
    #  Mouse hover
    # --------------------------------------------------------------------- #

    def on_mouse_move(self, event):
        """Show a tooltip with block info when hovering over the grid."""
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        block = self._get_block_at_position(cx, cy)
        if block is not None:
            self._show_tooltip(block, event.x_root, event.y_root)
        else:
            self._hide_tooltip()

    # --------------------------------------------------------------------- #
    #  Mouse click
    # --------------------------------------------------------------------- #

    def on_click(self, event):
        """Show a detailed dialog for the block under the cursor."""
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        block = self._get_block_at_position(cx, cy)
        if block is None:
            return

        owner = self.fat.block_to_file.get(block)
        is_free = self.fsm.bitmap[block] == 0

        lines = [
            f"Block number:   {block}",
            f"Status:         {'Free' if is_free else 'Allocated'}",
        ]

        if owner is not None:
            lines.append(f"Owner inode:    {owner}")

            # Resolve file name via directory tree
            fname = self._resolve_inode_name(owner)
            if fname:
                lines.append(f"File:           {fname}")

            blocks = self.fat.get_file_blocks(owner)
            if blocks:
                idx = blocks.index(block) if block in blocks else -1
                lines.append(
                    f"Position:       block {idx + 1} of {len(blocks)}"
                    f" in file")

            # Data preview
            try:
                raw = self.disk.read_block(block)
                preview = raw[:64].rstrip(b"\x00")
                if preview:
                    text = preview.decode("utf-8", errors="replace")
                    lines.append(f"\nData preview:\n{text}")
            except Exception:
                pass

        root_w = self.parent_frame.winfo_toplevel()
        messagebox.showinfo(f"Block {block}", "\n".join(lines),
                            parent=root_w)

    # --------------------------------------------------------------------- #
    #  Block-at-position
    # --------------------------------------------------------------------- #

    def _get_block_at_position(self, x: float, y: float) -> Optional[int]:
        """
        Return the block number at canvas coordinates *(x, y)*,
        or ``None`` if the point is outside the grid.
        """
        bp = self.block_size_pixels
        col = int(x) // bp
        row = int(y) // bp

        if col < 0 or col >= self.blocks_per_row:
            return None
        if row < 0 or row >= self.total_rows:
            return None

        block = row * self.blocks_per_row + col
        if block >= self.disk.total_blocks:
            return None
        return block

    # --------------------------------------------------------------------- #
    #  Tooltip
    # --------------------------------------------------------------------- #

    def _create_tooltip_window(self):
        """Create the floating tooltip ``Toplevel`` (hidden by default)."""
        self.tooltip = tk.Toplevel(self.parent_frame)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.withdraw()

        self._tip_label = tk.Label(
            self.tooltip, justify=tk.LEFT,
            background=self.color_scheme["legend_bg"],
            foreground=self.color_scheme["legend_fg"],
            relief=tk.SOLID, borderwidth=1,
            font=("Consolas", 9), padx=6, pady=4,
        )
        self._tip_label.pack()

    def _show_tooltip(self, block_num: int, x_root: int, y_root: int):
        """Display the tooltip near the cursor with block information."""
        owner = self.fat.block_to_file.get(block_num)
        is_free = self.fsm.bitmap[block_num] == 0

        parts = [f"Block {block_num}"]
        parts.append("Free" if is_free else "Allocated")

        if owner is not None:
            parts.append(f"Inode {owner}")
            fname = self._resolve_inode_name(owner)
            if fname:
                parts.append(fname)

        self._tip_label.configure(text="  |  ".join(parts))
        self.tooltip.wm_geometry(f"+{x_root + 16}+{y_root + 12}")
        self.tooltip.deiconify()
        self.tooltip.lift()

    def _hide_tooltip(self):
        """Hide the tooltip window."""
        if self.tooltip:
            self.tooltip.withdraw()

    # --------------------------------------------------------------------- #
    #  Highlighting
    # --------------------------------------------------------------------- #

    def highlight_file_blocks(self, inode_number: int):
        """
        Highlight every block belonging to *inode_number* in orange
        and redraw the canvas.
        """
        self._highlighted_inode = inode_number
        self._heatmap_mode = False
        self.draw_disk()

    def clear_highlights(self):
        """Remove file-block highlights and redraw normally."""
        self._highlighted_inode = None
        self.draw_disk()

    # --------------------------------------------------------------------- #
    #  Legend
    # --------------------------------------------------------------------- #

    def add_legend(self):
        """
        Draw a colour-keyed legend and statistics summary below
        the block grid on the canvas.
        """
        bp = self.block_size_pixels
        y_start = self.total_rows * bp + self._LEGEND_PAD + 4
        x = self._LEGEND_PAD
        sw = self._LEGEND_SWATCH
        cs = self.color_scheme
        fg = cs["legend_fg"]

        entries = [
            (cs["free"],       "Free"),
            (cs["allocated"],  "Allocated"),
            (cs["system"],     "System"),
            (cs["fragmented"], "Fragmented / Orphan"),
            (cs["highlight"],  "Highlighted"),
        ]

        for colour, label in entries:
            self.canvas.create_rectangle(
                x, y_start, x + sw, y_start + sw,
                fill=colour, outline=cs["outline"], tags="legend")
            self.canvas.create_text(
                x + sw + 6, y_start + sw // 2,
                text=label, anchor=tk.W, fill=fg,
                font=("Segoe UI", 8), tags="legend")
            x += sw + len(label) * 7 + 24

        # ---- stats line ----
        y_stats = y_start + sw + 10
        total = self.disk.total_blocks
        free_c = self.fsm.get_free_count()
        alloc_c = self.fsm.get_allocated_count()
        frag = self.fsm.get_fragmentation_percentage()

        stats_text = (
            f"Total: {total}   "
            f"Free: {free_c}   "
            f"Allocated: {alloc_c}   "
            f"Fragmentation: {frag:.1f}%"
        )
        self.canvas.create_text(
            self._LEGEND_PAD, y_stats,
            text=stats_text, anchor=tk.W, fill=fg,
            font=("Consolas", 9), tags="legend")

    # --------------------------------------------------------------------- #
    #  Zoom
    # --------------------------------------------------------------------- #

    def zoom_in(self):
        """Increase block square size and redraw."""
        if self.block_size_pixels < self._MAX_BLOCK_PX:
            self.block_size_pixels = min(
                self._MAX_BLOCK_PX,
                self.block_size_pixels + self._ZOOM_STEP)
            self.draw_disk()

    def zoom_out(self):
        """Decrease block square size and redraw."""
        if self.block_size_pixels > self._MIN_BLOCK_PX:
            self.block_size_pixels = max(
                self._MIN_BLOCK_PX,
                self.block_size_pixels - self._ZOOM_STEP)
            self.draw_disk()

    # --------------------------------------------------------------------- #
    #  Export
    # --------------------------------------------------------------------- #

    def export_visualization(self, filepath: str):
        """
        Export the current canvas contents to a PNG file.

        Requires Pillow (``pip install Pillow``).  If Pillow is not
        installed a warning dialog is shown instead.

        Parameters
        ----------
        filepath : str
            Destination file path (should end with ``.png``).
        """
        if not _HAS_PIL:
            messagebox.showwarning(
                "Export",
                "Pillow is required for PNG export.\n"
                "Install with:  pip install Pillow",
                parent=self.parent_frame.winfo_toplevel())
            return

        try:
            self._calculate_layout()
            bp = self.block_size_pixels
            img_w = self.blocks_per_row * bp
            img_h = self.total_rows * bp + 60  # extra for legend

            img = Image.new("RGB", (img_w, img_h),
                            color=self.color_scheme["canvas_bg"])
            draw = ImageDraw.Draw(img)

            block_num = 0
            for row in range(self.total_rows):
                for col in range(self.blocks_per_row):
                    if block_num >= self.disk.total_blocks:
                        break
                    x1 = col * bp
                    y1 = row * bp
                    colour = self._get_block_color(block_num)
                    draw.rectangle([x1, y1, x1 + bp - 1, y1 + bp - 1],
                                   fill=colour,
                                   outline=self.color_scheme["outline"])
                    block_num += 1

            img.save(filepath, "PNG")
            logger.info("Disk visualisation exported to %s", filepath)
            messagebox.showinfo(
                "Export", f"Visualisation saved to:\n{filepath}",
                parent=self.parent_frame.winfo_toplevel())
        except Exception as exc:
            logger.exception("Export failed")
            messagebox.showerror("Export Error", str(exc),
                                 parent=self.parent_frame.winfo_toplevel())

    # --------------------------------------------------------------------- #
    #  Fragmentation heat-map
    # --------------------------------------------------------------------- #

    def show_fragmentation_heatmap(self):
        """
        Toggle heat-map mode where block colour reflects local
        fragmentation intensity (green → yellow → red).
        """
        self._heatmap_mode = not self._heatmap_mode
        self._highlighted_inode = None
        self.draw_disk()

    # --------------------------------------------------------------------- #
    #  Animation
    # --------------------------------------------------------------------- #

    def animate_operation(self, blocks: List[int],
                          operation: str = "allocate"):
        """
        Animate an allocation or deallocation by flashing the
        specified blocks through a transition sequence.

        Parameters
        ----------
        blocks : list[int]
            Block numbers to animate.
        operation : str
            ``'allocate'`` or ``'deallocate'``.
        """
        if not blocks:
            return

        if operation == "allocate":
            colour_seq = [
                self.color_scheme["canvas_bg"],
                self.color_scheme["highlight"],
                "#ffffff",
                self.color_scheme["highlight"],
                self.color_scheme["allocated"],
            ]
        else:
            colour_seq = [
                self.color_scheme["allocated"],
                self.color_scheme["highlight"],
                "#ffffff",
                self.color_scheme["highlight"],
                self.color_scheme["free"],
            ]

        self._animate_step(blocks, colour_seq, 0)

    def _animate_step(self, blocks: List[int],
                      colour_seq: List[str], step: int):
        """Execute one animation frame and schedule the next."""
        if step >= len(colour_seq):
            self.draw_disk()  # final redraw in correct state
            return

        colour = colour_seq[step]
        bp = self.block_size_pixels

        for b in blocks:
            if b >= self.disk.total_blocks:
                continue
            row = b // self.blocks_per_row
            col = b % self.blocks_per_row
            x1 = col * bp
            y1 = row * bp

            tag = f"block_{b}"
            self.canvas.delete(tag)
            self.canvas.create_rectangle(
                x1, y1, x1 + bp, y1 + bp,
                fill=colour,
                outline=self.color_scheme["outline"],
                tags=(tag, "block"),
            )

        self._anim_after_id = self.canvas.after(
            120, self._animate_step, blocks, colour_seq, step + 1)

    # --------------------------------------------------------------------- #
    #  Canvas resize handler
    # --------------------------------------------------------------------- #

    def _on_canvas_resize(self, _event):
        """Redraw when the canvas is resized so the grid fills the width."""
        self.draw_disk()

    # --------------------------------------------------------------------- #
    #  Reset
    # --------------------------------------------------------------------- #

    def _reset_view(self):
        """Reset zoom, highlights, and heat-map to defaults."""
        self.block_size_pixels = self._DEFAULT_BLOCK_PX
        self._highlighted_inode = None
        self._heatmap_mode = False
        self.draw_disk()

    # --------------------------------------------------------------------- #
    #  Stats label
    # --------------------------------------------------------------------- #

    def _update_stats_label(self):
        """Update the toolbar statistics string."""
        total = self.disk.total_blocks
        free_c = self.fsm.get_free_count()
        frag = self.fsm.get_fragmentation_percentage()
        self._stats_var.set(
            f"Blocks: {total}   "
            f"Free: {free_c}   "
            f"Frag: {frag:.1f}%   "
            f"Zoom: {self.block_size_pixels}px")

    # --------------------------------------------------------------------- #
    #  Inode → filename resolver
    # --------------------------------------------------------------------- #

    def _resolve_inode_name(self, inode_number: int) -> Optional[str]:
        """Return the file path for *inode_number*, or ``None``."""
        if self._dir_tree is None:
            return None
        node = self._dir_tree.inode_map.get(inode_number)
        if node is None:
            return None
        return node.get_full_path()
