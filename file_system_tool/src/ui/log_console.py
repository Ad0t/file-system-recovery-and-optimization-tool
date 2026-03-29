"""
log_console.py — Rich log console widget for the File System Simulator.

Provides a scrollable, colour-coded ``tk.Text``-based log panel with:

  • Colour-coded log levels (DEBUG / INFO / WARNING / ERROR / SUCCESS / SYSTEM)
  • Toolbar with Clear, Save, Filter drop-down, Search box, Auto-scroll toggle
  • Optional file-backed logging
  • Search with match highlighting
  • Level filtering
  • Export to TXT / HTML / JSON
  • Automatic line trimming (default 1000 lines)

Usage::

    from src.ui.log_console import LogConsole

    console = LogConsole(parent_frame, log_file="data/app.log")
    console.log_info("Application started.")
    console.log_error("Disk I/O failure on block 42.")
"""

import json
import logging
import os
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog
from typing import List, Optional

logger = logging.getLogger(__name__)

# =========================================================================== #
#  Palette (Catppuccin Mocha)
# =========================================================================== #

_PAL = {
    "bg":      "#1e1e2e",
    "surface": "#313244",
    "border":  "#45475a",
    "fg":      "#cdd6f4",
    "dim":     "#6c7086",
    "green":   "#a6e3a1",
    "yellow":  "#f9e2af",
    "red":     "#f38ba8",
    "blue":    "#89b4fa",
    "peach":   "#fab387",
    "mauve":   "#cba6f7",
    "teal":    "#94e2d5",
    "highlight_bg": "#45475a",
}


# =========================================================================== #
#  LogConsole
# =========================================================================== #

class LogConsole:
    """
    Embeddable log console panel with colour-coded levels, search,
    filtering, and file export.

    Attributes
    ----------
    parent_frame : ttk.Frame
        Container that hosts the console.
    log_text : tk.Text
        The read-only text widget that displays log entries.
    log_level : str
        Active display filter level — one of
        ``'ALL'``, ``'DEBUG'``, ``'INFO'``, ``'WARNING'``, ``'ERROR'``.
    max_lines : int
        Maximum visible lines before the oldest are trimmed.
    auto_scroll : bool
        Whether new entries automatically scroll the view to the bottom.
    log_file : str or None
        Path to an optional on-disk log file.  If set, every ``log()``
        call also appends to this file.
    """

    _VALID_LEVELS = ("ALL", "DEBUG", "INFO", "WARNING", "ERROR",
                     "SUCCESS", "SYSTEM")

    # --------------------------------------------------------------------- #
    #  Construction
    # --------------------------------------------------------------------- #

    def __init__(self, parent_frame: ttk.Frame,
                 log_file: Optional[str] = None,
                 *,
                 max_lines: int = 1000):
        """
        Build the log console inside *parent_frame*.

        Parameters
        ----------
        parent_frame : ttk.Frame
            Container widget.
        log_file : str, optional
            If given, log entries are also appended to this file.
        max_lines : int
            Maximum lines to retain (oldest are trimmed).
        """
        self.parent_frame = parent_frame
        self.log_file: Optional[str] = log_file
        self.max_lines: int = max_lines
        self.auto_scroll: bool = True
        self.log_level: str = "ALL"

        # Internal book-keeping
        self._all_entries: List[dict] = []   # full unfiltered history
        self._line_count: int = 0
        self._search_matches: List[str] = []

        # Build UI
        self.create_layout()
        self.configure_tags()

        # Ensure log-file directory exists
        if self.log_file:
            os.makedirs(os.path.dirname(self.log_file) or ".", exist_ok=True)

    # --------------------------------------------------------------------- #
    #  Layout
    # --------------------------------------------------------------------- #

    def create_layout(self):
        """Build controls (top) + text widget (main)."""

        outer = ttk.Frame(self.parent_frame)
        outer.pack(fill=tk.BOTH, expand=True)

        # ---- controls ---- #
        self._create_controls(outer)

        # ---- text widget + scrollbar ---- #
        text_frame = ttk.Frame(outer)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))

        self.log_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg=_PAL["surface"],
            fg=_PAL["fg"],
            insertbackground=_PAL["fg"],
            selectbackground=_PAL["blue"],
            selectforeground=_PAL["bg"],
            borderwidth=0,
            relief=tk.FLAT,
            state=tk.DISABLED,
            padx=6, pady=4,
        )

        v_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL,
                                  command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=v_scroll.set)

        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # --------------------------------------------------------------------- #
    #  Controls toolbar
    # --------------------------------------------------------------------- #

    def _create_controls(self, parent: ttk.Frame):
        """
        Build the toolbar with Clear, Save, Filter, Search,
        and Auto-scroll toggle.
        """
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X, padx=2, pady=2)

        # ---- Clear ---- #
        ttk.Button(bar, text="🗑 Clear", width=8,
                   command=self.clear_log).pack(side=tk.LEFT, padx=2)

        # ---- Save ---- #
        ttk.Button(bar, text="💾 Save", width=8,
                   command=self.save_log).pack(side=tk.LEFT, padx=2)

        # ---- Filter dropdown ---- #
        ttk.Label(bar, text="Filter:").pack(side=tk.LEFT, padx=(8, 2))
        self._filter_var = tk.StringVar(value="ALL")
        filter_cb = ttk.Combobox(bar, textvariable=self._filter_var,
                                  values=list(self._VALID_LEVELS),
                                  state="readonly", width=9)
        filter_cb.pack(side=tk.LEFT, padx=2)
        filter_cb.bind("<<ComboboxSelected>>",
                        lambda _e: self.filter_by_level(
                            self._filter_var.get()))

        # ---- Search box ---- #
        ttk.Label(bar, text="Search:").pack(side=tk.LEFT, padx=(8, 2))
        self._search_var = tk.StringVar()
        search_entry = ttk.Entry(bar, textvariable=self._search_var,
                                  width=16)
        search_entry.pack(side=tk.LEFT, padx=2)
        search_entry.bind("<Return>",
                           lambda _e: self.search_log(
                               self._search_var.get()))
        ttk.Button(bar, text="🔍", width=3,
                   command=lambda: self.search_log(
                       self._search_var.get())).pack(side=tk.LEFT)

        # ---- Auto-scroll checkbox ---- #
        self._autoscroll_var = tk.BooleanVar(value=True)
        chk = ttk.Checkbutton(bar, text="Auto-scroll",
                               variable=self._autoscroll_var,
                               command=lambda: self.set_auto_scroll(
                                   self._autoscroll_var.get()))
        chk.pack(side=tk.RIGHT, padx=4)

        # ---- line count label ---- #
        self._count_var = tk.StringVar(value="0 lines")
        ttk.Label(bar, textvariable=self._count_var).pack(
            side=tk.RIGHT, padx=6)

    # --------------------------------------------------------------------- #
    #  Tag configuration
    # --------------------------------------------------------------------- #

    def configure_tags(self):
        """Set up text tags for each log level."""
        tag_map = {
            "DEBUG":   _PAL["dim"],
            "INFO":    _PAL["fg"],
            "WARNING": _PAL["yellow"],
            "ERROR":   _PAL["red"],
            "SUCCESS": _PAL["green"],
            "SYSTEM":  _PAL["blue"],
            "search":  None,   # special highlight tag
        }
        for tag, colour in tag_map.items():
            if tag == "search":
                self.log_text.tag_configure(
                    tag,
                    background=_PAL["peach"],
                    foreground=_PAL["bg"],
                )
            else:
                self.log_text.tag_configure(tag, foreground=colour)

    # --------------------------------------------------------------------- #
    #  Core logging
    # --------------------------------------------------------------------- #

    def log(self, message: str, level: str = "INFO"):
        """
        Append a timestamped, colour-coded log entry.

        Parameters
        ----------
        message : str
            The log text.
        level : str
            One of ``'DEBUG'``, ``'INFO'``, ``'WARNING'``, ``'ERROR'``,
            ``'SUCCESS'``, ``'SYSTEM'``.
        """
        level = level.upper()
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] [{level:>7}] {message}\n"

        # Store in full history
        self._all_entries.append({
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "formatted": formatted,
        })

        # Only display if passes the current filter
        if self.log_level == "ALL" or level == self.log_level:
            self._append_line(formatted, level)

        # File logging
        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(formatted)
            except OSError:
                pass

    def _append_line(self, formatted: str, tag: str):
        """Insert a single formatted line into the text widget."""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, formatted, tag)
        self.log_text.configure(state=tk.DISABLED)

        self._line_count += 1
        self._count_var.set(f"{self._line_count} lines")

        if self.auto_scroll:
            self._scroll_to_bottom()

        self._trim_log()

    # --------------------------------------------------------------------- #
    #  Convenience shortcuts
    # --------------------------------------------------------------------- #

    def log_debug(self, message: str):
        """Log at DEBUG level."""
        self.log(message, "DEBUG")

    def log_info(self, message: str):
        """Log at INFO level."""
        self.log(message, "INFO")

    def log_warning(self, message: str):
        """Log at WARNING level."""
        self.log(message, "WARNING")

    def log_error(self, message: str):
        """Log at ERROR level."""
        self.log(message, "ERROR")

    def log_success(self, message: str):
        """Log at SUCCESS level."""
        self.log(message, "SUCCESS")

    # --------------------------------------------------------------------- #
    #  Clear
    # --------------------------------------------------------------------- #

    def clear_log(self):
        """Clear all log content after confirmation."""
        root_w = self.parent_frame.winfo_toplevel()
        if self._line_count > 0:
            if not messagebox.askyesno("Clear Log",
                                       f"Clear {self._line_count} log entries?",
                                       parent=root_w):
                return

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self._all_entries.clear()
        self._line_count = 0
        self._count_var.set("0 lines")

    # --------------------------------------------------------------------- #
    #  Save
    # --------------------------------------------------------------------- #

    def save_log(self):
        """Prompt for a destination and save the current log as plain text."""
        root_w = self.parent_frame.winfo_toplevel()
        path = filedialog.asksaveasfilename(
            title="Save Log",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"),
                       ("Log Files", "*.log"),
                       ("All Files", "*.*")],
            parent=root_w,
        )
        if not path:
            return

        try:
            content = self.log_text.get("1.0", tk.END)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Save Log", f"Log saved to:\n{path}",
                                parent=root_w)
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc), parent=root_w)

    # --------------------------------------------------------------------- #
    #  Filter
    # --------------------------------------------------------------------- #

    def filter_by_level(self, level: str):
        """
        Rebuild the text widget showing only entries matching *level*.

        Pass ``'ALL'`` to show everything.
        """
        level = level.upper()
        self.log_level = level
        self._filter_var.set(level)

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)

        count = 0
        for entry in self._all_entries:
            if level == "ALL" or entry["level"] == level:
                self.log_text.insert(tk.END,
                                      entry["formatted"],
                                      entry["level"])
                count += 1

        self.log_text.configure(state=tk.DISABLED)
        self._line_count = count
        self._count_var.set(f"{count} lines")

        if self.auto_scroll:
            self._scroll_to_bottom()

    # --------------------------------------------------------------------- #
    #  Search
    # --------------------------------------------------------------------- #

    def search_log(self, search_term: str) -> List[str]:
        """
        Search the log for *search_term*, highlight matches, and
        return a list of matching lines.

        Parameters
        ----------
        search_term : str
            Case-insensitive substring to search for.

        Returns
        -------
        list[str]
            Lines that contain the search term.
        """
        # Remove previous search highlights
        self.log_text.tag_remove("search", "1.0", tk.END)
        self._search_matches.clear()

        if not search_term:
            return []

        term_lower = search_term.lower()
        content = self.log_text.get("1.0", tk.END)
        match_count = 0

        # Walk through all lines
        lines = content.split("\n")
        for idx, line in enumerate(lines, start=1):
            if term_lower in line.lower():
                self._search_matches.append(line)
                # Highlight each occurrence within the line
                start = 0
                while True:
                    pos = line.lower().find(term_lower, start)
                    if pos == -1:
                        break
                    tag_start = f"{idx}.{pos}"
                    tag_end = f"{idx}.{pos + len(search_term)}"
                    self.log_text.tag_add("search", tag_start, tag_end)
                    match_count += 1
                    start = pos + 1

        # Scroll to first match
        if self._search_matches:
            first = self.log_text.tag_nextrange("search", "1.0")
            if first:
                self.log_text.see(first[0])

        # Update count label temporarily
        self._count_var.set(
            f"{match_count} match{'es' if match_count != 1 else ''}")

        return self._search_matches

    # --------------------------------------------------------------------- #
    #  Auto-scroll
    # --------------------------------------------------------------------- #

    def set_auto_scroll(self, enabled: bool):
        """Enable or disable automatic scrolling to new entries."""
        self.auto_scroll = enabled
        self._autoscroll_var.set(enabled)
        if enabled:
            self._scroll_to_bottom()

    # --------------------------------------------------------------------- #
    #  Trimming
    # --------------------------------------------------------------------- #

    def _trim_log(self):
        """Remove the oldest lines if the widget exceeds ``max_lines``."""
        self.log_text.configure(state=tk.NORMAL)
        while True:
            total = int(self.log_text.index("end-1c").split(".")[0])
            if total <= self.max_lines:
                break
            self.log_text.delete("1.0", "2.0")
            self._line_count = max(0, self._line_count - 1)
        self.log_text.configure(state=tk.DISABLED)

    # --------------------------------------------------------------------- #
    #  Scroll
    # --------------------------------------------------------------------- #

    def _scroll_to_bottom(self):
        """Scroll the text widget so the last line is visible."""
        self.log_text.see(tk.END)

    # --------------------------------------------------------------------- #
    #  Export
    # --------------------------------------------------------------------- #

    def export_log(self, filepath: str, format: str = "txt"):
        """
        Export the full log history to *filepath*.

        Parameters
        ----------
        filepath : str
            Destination file path.
        format : str
            ``'txt'``, ``'html'``, or ``'json'``.
        """
        try:
            if format == "json":
                payload = [
                    {"timestamp": e["timestamp"],
                     "level": e["level"],
                     "message": e["message"]}
                    for e in self._all_entries
                ]
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)

            elif format == "html":
                colour_map = {
                    "DEBUG":   _PAL["dim"],
                    "INFO":    _PAL["fg"],
                    "WARNING": _PAL["yellow"],
                    "ERROR":   _PAL["red"],
                    "SUCCESS": _PAL["green"],
                    "SYSTEM":  _PAL["blue"],
                }
                lines = [
                    "<!DOCTYPE html>",
                    "<html><head><meta charset='utf-8'>",
                    "<title>Log Export</title>",
                    "<style>",
                    f"  body {{ background:{_PAL['bg']}; "
                    f"color:{_PAL['fg']}; "
                    f"font-family:Consolas,monospace; font-size:12px; }}",
                    "  .entry { padding:1px 4px; }",
                    "</style></head><body>",
                ]
                for e in self._all_entries:
                    c = colour_map.get(e["level"], _PAL["fg"])
                    esc = (e["message"]
                           .replace("&", "&amp;")
                           .replace("<", "&lt;")
                           .replace(">", "&gt;"))
                    lines.append(
                        f"<div class='entry' style='color:{c}'>"
                        f"[{e['timestamp']}] [{e['level']:>7}] {esc}</div>")
                lines.append("</body></html>")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))

            else:  # txt
                with open(filepath, "w", encoding="utf-8") as f:
                    for e in self._all_entries:
                        f.write(e["formatted"])

            logger.info("Log exported to %s (%s)", filepath, format)
        except Exception as exc:
            logger.exception("Log export failed")
            root_w = self.parent_frame.winfo_toplevel()
            messagebox.showerror("Export Error", str(exc), parent=root_w)
