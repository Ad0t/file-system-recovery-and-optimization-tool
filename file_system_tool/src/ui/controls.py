"""
controls.py — Control panel component for the File System Simulator.

Provides organized sections for file operations, crash simulation,
recovery, optimization, and performance benchmarking using ttk widgets.

Usage::

    from src.ui.controls import Controls

    controls = Controls(parent_frame, fs_components, log_console)
    controls.set_callback('create_file', my_create_file_handler)
"""

import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Any, Callable, Dict, Optional


class Controls:
    """
    Control panel component for file system operations.

    Attributes
    ----------
    parent_frame : ttk.Frame
        Parent container.
    file_system_components : dict
        All FS components keyed by name.
    log_console : LogConsole
        Reference to the log console for logging operations.
    callback_handlers : dict
        Callbacks for operations, set by the main window.
    """

    def __init__(self, parent_frame: ttk.Frame, fs_components: dict, log_console: Any):
        """
        Initialize the control panel.

        Parameters
        ----------
        parent_frame : ttk.Frame
            The parent container.
        fs_components : dict
            Dictionary containing file system components.
        log_console : LogConsole
            Reference to the log console.
        """
        self.parent_frame = parent_frame
        self.file_system_components = fs_components
        self.log_console = log_console

        # Callbacks that can be set by the main window for UI updates
        self.callback_handlers: Dict[str, Callable] = {}

        # Scrollable container for all sections
        self._canvas = tk.Canvas(parent_frame, highlightthickness=0)
        self._scrollbar = ttk.Scrollbar(parent_frame, orient=tk.VERTICAL,
                                         command=self._canvas.yview)
        self._scroll_frame = ttk.Frame(self._canvas)

        self._scroll_frame.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")))

        self._canvas.create_window((0, 0), window=self._scroll_frame,
                                    anchor="nw")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Mouse wheel scrolling
        self._canvas.bind_all(
            "<MouseWheel>",
            lambda e: self._canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"),
            add="+")

        self.create_layout()

    # --------------------------------------------------------------------- #
    #  Layout
    # --------------------------------------------------------------------- #

    def create_layout(self):
        """Create all control sections."""
        self.create_file_operations_section()
        self.create_crash_simulation_section()
        self.create_recovery_section()
        self.create_optimization_section()
        self.create_performance_section()

    def create_file_operations_section(self):
        """Create controls for file system operations."""
        frame = ttk.LabelFrame(self._scroll_frame, text="  File Operations  ",
                                padding=10)
        frame.pack(fill=tk.X, pady=3, padx=2)

        ttk.Button(frame, text="📄 Create File",
                   command=self.on_create_file).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="📁 Create Directory",
                   command=self.on_create_directory).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="🗑  Delete Selected",
                   command=self.on_delete_item).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="👁 View File Content",
                   command=lambda: self._execute_callback("view_file")
                   ).pack(fill=tk.X, pady=2)

    def create_crash_simulation_section(self):
        """Create controls to inject crashes."""
        frame = ttk.LabelFrame(self._scroll_frame,
                                text="  Crash Simulation  ", padding=10)
        frame.pack(fill=tk.X, pady=3, padx=2)

        # Crash type
        ttk.Label(frame, text="Crash Type:").pack(anchor=tk.W)
        self.crash_type_var = tk.StringVar(value="Power Failure")
        ttk.Combobox(
            frame,
            textvariable=self.crash_type_var,
            values=["Power Failure", "Bit Corruption",
                    "Metadata Corruption", "Journal Corruption"],
            state="readonly"
        ).pack(fill=tk.X, pady=2)

        # Severity slider
        ttk.Label(frame, text="Severity:").pack(anchor=tk.W)
        self.severity_var = tk.DoubleVar(value=2.0)

        sev_frame = ttk.Frame(frame)
        sev_frame.pack(fill=tk.X, pady=2)
        ttk.Label(sev_frame, text="Low").pack(side=tk.LEFT)
        ttk.Scale(sev_frame, from_=1.0, to=3.0,
                  variable=self.severity_var,
                  orient=tk.HORIZONTAL).pack(
                      side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Label(sev_frame, text="High").pack(side=tk.RIGHT)

        ttk.Button(frame, text="⚠ Inject Crash",
                   command=self.on_inject_crash).pack(fill=tk.X, pady=5)
        ttk.Button(frame, text="🎲 Random Crash",
                   command=lambda: self._execute_callback("random_crash")
                   ).pack(fill=tk.X, pady=2)

    def create_recovery_section(self):
        """Create controls for system recovery."""
        frame = ttk.LabelFrame(self._scroll_frame,
                                text="  Recovery Operations  ", padding=10)
        frame.pack(fill=tk.X, pady=3, padx=2)

        ttk.Button(frame, text="🔍 Analyze Crash",
                   command=lambda: self._execute_callback("analyze_crash")
                   ).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="🔧 Recover from Journal",
                   command=self.on_recover_system).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="✅ Run FSCK",
                   command=self.on_run_fsck).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="🛠 Repair Metadata",
                   command=lambda: self._execute_callback("repair_metadata")
                   ).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="📦 Restore from Checkpoint",
                   command=lambda: self._execute_callback("restore_checkpoint")
                   ).pack(fill=tk.X, pady=2)

    def create_optimization_section(self):
        """Create controls for defragmentation and cache management."""
        frame = ttk.LabelFrame(self._scroll_frame,
                                text="  Optimization  ", padding=10)
        frame.pack(fill=tk.X, pady=3, padx=2)

        ttk.Button(frame, text="Defragment All",
                   command=self.on_defragment).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="Defragment Selected File",
                   command=lambda: self._execute_callback("defragment_selected")
                   ).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="Compact Free Space",
                   command=lambda: self._execute_callback("compact_free_space")
                   ).pack(fill=tk.X, pady=2)

        # Cache Strategy
        ttk.Label(frame, text="Cache Strategy:").pack(anchor=tk.W, pady=(5, 0))
        self.cache_strategy_var = tk.StringVar(value="LRU")
        ttk.Combobox(
            frame,
            textvariable=self.cache_strategy_var,
            values=["LRU", "LFU", "FIFO", "RANDOM"],
            state="readonly"
        ).pack(fill=tk.X, pady=2)

        # Cache Size
        ttk.Label(frame, text="Cache Size (Blocks):").pack(anchor=tk.W)
        self.cache_size_var = tk.IntVar(value=64)
        ttk.Scale(frame, from_=1, to=256,
                  variable=self.cache_size_var,
                  orient=tk.HORIZONTAL).pack(fill=tk.X, pady=2)

        # Cache Enable Toggle
        self.cache_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame, text="Enable/Disable Cache",
            variable=self.cache_enabled_var,
            command=lambda: self._execute_callback(
                "toggle_cache", self.cache_enabled_var.get())
        ).pack(anchor=tk.W, pady=2)

    def create_performance_section(self):
        """Create controls for monitoring performance."""
        frame = ttk.LabelFrame(self._scroll_frame,
                                text="  Performance  ", padding=10)
        frame.pack(fill=tk.X, pady=3, padx=2)

        ttk.Button(frame, text="▶ Run Benchmark",
                   command=self.on_benchmark).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="📄 Generate Report",
                   command=self.on_generate_report).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="📤 Export Metrics",
                   command=lambda: self._execute_callback("export_metrics")
                   ).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text="🧹 Clear Statistics",
                   command=lambda: self._execute_callback("clear_statistics")
                   ).pack(fill=tk.X, pady=2)

    # --------------------------------------------------------------------- #
    #  Callback management
    # --------------------------------------------------------------------- #

    def set_callback(self, operation: str, callback: Callable):
        """Set a callback for a specific operation."""
        self.callback_handlers[operation] = callback

    def _execute_callback(self, operation: str, *args, **kwargs):
        """Helper to safely invoke an operation callback."""
        callback = self.callback_handlers.get(operation)
        if callback:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self.log_console.log_error(
                    f"Error executing callback '{operation}': {e}")
                messagebox.showerror(
                    "Error", f"Failed to perform operation:\n{e}")

    # --------------------------------------------------------------------- #
    #  Operation handlers
    # --------------------------------------------------------------------- #

    def on_create_file(self):
        """Show dialog to get file parameters and create a file."""
        params = self._get_file_input_dialog()
        if not params:
            return

        try:
            name = params["name"]
            path = params["path"]
            size = params["size"]

            self.log_console.log_info(
                f"Creating file '{name}' at '{path}' with size {size} blocks…")

            if "create_file" in self.callback_handlers:
                self.callback_handlers["create_file"](path, name, size)
            else:
                self.log_console.log_warning(
                    "Create file callback not connected.")

            self._execute_callback("update_ui")

        except Exception as e:
            self.log_console.log_error(f"Failed to create file: {e}")
            messagebox.showerror("Error", f"Failed to create file: {e}")

    def on_create_directory(self):
        """Show dialog for directory name and create it."""
        params = self._get_directory_input_dialog()
        if not params:
            return

        try:
            name = params["name"]
            path = params["path"]

            self.log_console.log_info(
                f"Creating directory '{name}' at '{path}'…")

            if "create_directory" in self.callback_handlers:
                self.callback_handlers["create_directory"](path, name)
            else:
                self.log_console.log_warning(
                    "Create directory callback not connected.")

            self._execute_callback("update_ui")
        except Exception as e:
            self.log_console.log_error(f"Failed to create directory: {e}")
            messagebox.showerror("Error", f"Failed to create directory: {e}")

    def on_delete_item(self):
        """Delete the currently selected item after confirmation."""
        self.log_console.log_info("Requesting deletion of selected item.")

        if "get_selected_item" in self.callback_handlers:
            selected_path = self.callback_handlers["get_selected_item"]()
            if not selected_path:
                messagebox.showwarning(
                    "No Selection", "Please select an item to delete.")
                return

            if not messagebox.askyesno(
                    "Confirm Deletion",
                    f"Are you sure you want to delete '{selected_path}'?"):
                return

            try:
                if "delete_item" in self.callback_handlers:
                    self.callback_handlers["delete_item"](selected_path)
                self.log_console.log_info(f"Deleted item: {selected_path}")
                self._execute_callback("update_ui")
            except Exception as e:
                self.log_console.log_error(f"Failed to delete item: {e}")
                messagebox.showerror("Error", f"Failed to delete item: {e}")
        else:
            messagebox.showinfo(
                "Not Configured", "Selection tracking is not configured.")

    def on_inject_crash(self):
        """Inject a crash using the selected type and severity."""
        c_type = self.crash_type_var.get()
        c_sev = int(self.severity_var.get())
        severity_label = (["Low", "Medium", "High"][c_sev - 1]
                          if 1 <= c_sev <= 3 else "Unknown")

        self.log_console.log_warning(
            f"Injecting crash: {c_type} (Severity: {severity_label})")

        if "inject_crash" in self.callback_handlers:
            try:
                report = self.callback_handlers["inject_crash"](c_type, c_sev)
                if report:
                    self._show_crash_report_dialog(report)
            except Exception as e:
                self.log_console.log_error(f"Crash injection failed: {e}")
                messagebox.showerror("Crash Simulation Failed", str(e))
        else:
            dummy_report = {
                "type": c_type,
                "severity": severity_label,
                "affected_blocks": 5,
                "recoverable": True,
            }
            self._show_crash_report_dialog(dummy_report)

        self._execute_callback("update_ui")

    def on_recover_system(self):
        """Show progress dialog and run journal recovery in a thread."""
        dialog = self._show_progress_dialog(
            "Recovering System", "Running journal recovery…")

        def run_recovery():
            try:
                if "recover_system" in self.callback_handlers:
                    report = self.callback_handlers["recover_system"]()
                else:
                    self.log_console.log_info(
                        "Simulating recovery process…")
                    time.sleep(1)
                    report = {"success": True,
                              "recovered_transactions": 3,
                              "time_taken": 1.2}

                self.parent_frame.after(
                    0, self._finish_recovery, dialog, report)
            except Exception as e:
                self.log_console.log_error(f"Recovery failed: {e}")
                self.parent_frame.after(
                    0, lambda: messagebox.showerror(
                        "Recovery Error", str(e)))
                self.parent_frame.after(
                    0, lambda: self._close_progress_dialog(dialog))

        t = threading.Thread(target=run_recovery, daemon=True)
        t.start()

    def _finish_recovery(self, dialog, report):
        """Callback after recovery completes — close dialog, show report."""
        self._close_progress_dialog(dialog)
        self.log_console.log_success("System recovery complete.")
        self._show_recovery_report_dialog(report)
        self._execute_callback("update_ui")

    def on_run_fsck(self):
        """Run file-system consistency check."""
        self.log_console.log_info("Starting file system check (FSCK)…")

        if "run_fsck" in self.callback_handlers:
            try:
                results = self.callback_handlers["run_fsck"]()

                if results and results.get("errors_found", 0) > 0:
                    repair = messagebox.askyesno(
                        "FSCK Results",
                        f"Errors found ({results.get('errors_found')}) "
                        "during file system check. Attempt auto-repair?")
                    if repair and "repair_fsck" in self.callback_handlers:
                        self.callback_handlers["repair_fsck"]()
                        self.log_console.log_success(
                            "FSCK auto-repair completed.")
                else:
                    messagebox.showinfo(
                        "FSCK Results",
                        "File system check completed without errors.")
            except Exception as e:
                self.log_console.log_error(f"FSCK failed: {e}")
        else:
            messagebox.showinfo(
                "FSCK", "File system check initiated.")

        self._execute_callback("update_ui")

    def on_defragment(self):
        """Run defragmentation with a progress dialog."""
        dialog = self._show_progress_dialog(
            "Defragmenting", "Optimizing file system structures…")

        def run_defrag():
            try:
                if "defragment" in self.callback_handlers:
                    result = self.callback_handlers["defragment"]()
                    if isinstance(result, tuple) and len(result) == 2:
                        before, after = result
                        msg = (f"Defragmentation complete.\n"
                               f"Before: {before:.1f}% fragmentation.\n"
                               f"After: {after:.1f}% fragmentation.")
                    else:
                        msg = "Defragmentation complete."
                else:
                    time.sleep(1)
                    msg = "Defragmentation complete. (Simulated)"

                def on_done():
                    self._close_progress_dialog(dialog)
                    self.log_console.log_success(
                        "Defragmentation process complete.")
                    messagebox.showinfo("Defragmentation Results", msg)
                    self._execute_callback("update_ui")

                self.parent_frame.after(0, on_done)
            except Exception as e:
                self.log_console.log_error(f"Defragmentation failed: {e}")
                self.parent_frame.after(
                    0, lambda: self._close_progress_dialog(dialog))
                self.parent_frame.after(
                    0, lambda: messagebox.showerror("Error", str(e)))

        t = threading.Thread(target=run_defrag, daemon=True)
        t.start()

    def on_benchmark(self):
        """Launch benchmark and show results."""
        self.log_console.log_info("Starting benchmarking…")
        if "run_benchmark" in self.callback_handlers:
            self.callback_handlers["run_benchmark"]()
        else:
            messagebox.showinfo("Benchmark", "Benchmark process completed.")

    def on_generate_report(self):
        """Generate and save a performance report."""
        self.log_console.log_info("Generating performance report…")
        if "generate_report" in self.callback_handlers:
            self.callback_handlers["generate_report"]()
        else:
            self.log_console.log_info("Report generation not connected.")

    # --------------------------------------------------------------------- #
    #  Dialog helpers
    # --------------------------------------------------------------------- #

    def _show_progress_dialog(self, title: str,
                               message: str) -> tk.Toplevel:
        """Show a progress dialog with indeterminate progress bar."""
        dialog = tk.Toplevel(self.parent_frame)
        dialog.title(title)
        dialog.geometry("300x100")
        dialog.transient(self.parent_frame.winfo_toplevel())
        dialog.grab_set()
        dialog.eval(f'tk::PlaceWindow {str(dialog)} center')

        ttk.Label(dialog, text=message).pack(pady=(15, 5))
        progress = ttk.Progressbar(dialog, mode="indeterminate", length=200)
        progress.pack(pady=5)
        progress.start(10)

        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        return dialog

    def _close_progress_dialog(self, dialog: tk.Toplevel):
        """Close a progress dialog."""
        if dialog and dialog.winfo_exists():
            dialog.grab_release()
            dialog.destroy()

    def _get_file_input_dialog(self) -> Optional[Dict[str, Any]]:
        """Show dialog to gather file parameters (name, path, size)."""
        class _FileDialog(simpledialog.Dialog):
            def body(self_d, master):
                ttk.Label(master, text="File Name:").grid(
                    row=0, column=0, sticky=tk.W, pady=2)
                self_d.name_entry = ttk.Entry(master, width=24)
                self_d.name_entry.grid(row=0, column=1, pady=2)

                ttk.Label(master, text="Target Path:").grid(
                    row=1, column=0, sticky=tk.W, pady=2)
                self_d.path_entry = ttk.Entry(master, width=24)
                self_d.path_entry.insert(0, "/")
                self_d.path_entry.grid(row=1, column=1, pady=2)

                ttk.Label(master, text="Size (Blocks):").grid(
                    row=2, column=0, sticky=tk.W, pady=2)
                self_d.size_entry = ttk.Entry(master, width=24)
                self_d.size_entry.insert(0, "1")
                self_d.size_entry.grid(row=2, column=1, pady=2)
                return self_d.name_entry

            def apply(self_d):
                try:
                    size = int(self_d.size_entry.get())
                    if size <= 0:
                        raise ValueError()
                    self_d.result = {
                        "name": self_d.name_entry.get(),
                        "path": self_d.path_entry.get(),
                        "size": size,
                    }
                except ValueError:
                    messagebox.showerror(
                        "Invalid Input",
                        "Size must be a positive integer.")
                    self_d.result = None

        d = _FileDialog(self.parent_frame.winfo_toplevel(), "Create File")
        return d.result if hasattr(d, "result") else None

    def _get_directory_input_dialog(self) -> Optional[Dict[str, str]]:
        """Show dialog to gather directory parameters (name, path)."""
        class _DirDialog(simpledialog.Dialog):
            def body(self_d, master):
                ttk.Label(master, text="Directory Name:").grid(
                    row=0, column=0, sticky=tk.W, pady=2)
                self_d.name_entry = ttk.Entry(master, width=24)
                self_d.name_entry.grid(row=0, column=1, pady=2)

                ttk.Label(master, text="Target Path:").grid(
                    row=1, column=0, sticky=tk.W, pady=2)
                self_d.path_entry = ttk.Entry(master, width=24)
                self_d.path_entry.insert(0, "/")
                self_d.path_entry.grid(row=1, column=1, pady=2)
                return self_d.name_entry

            def apply(self_d):
                self_d.result = {
                    "name": self_d.name_entry.get(),
                    "path": self_d.path_entry.get(),
                }

        d = _DirDialog(self.parent_frame.winfo_toplevel(),
                       "Create Directory")
        return d.result if hasattr(d, "result") else None

    def _show_crash_report_dialog(self, crash_report: dict):
        """Display crash report in a dialog."""
        text = (
            f"Type: {crash_report.get('type', 'N/A')}\n"
            f"Severity: {crash_report.get('severity', 'N/A')}\n"
            f"Affected Blocks: {crash_report.get('affected_blocks', 0)}\n"
            f"Recoverable: "
            f"{'Yes' if crash_report.get('recoverable') else 'No'}"
        )
        messagebox.showinfo("Crash Report", text)

    def _show_recovery_report_dialog(self, recovery_report: dict):
        """Display recovery results in a dialog."""
        text = (
            f"Recovery Success: "
            f"{'Yes' if recovery_report.get('success') else 'No'}\n"
            f"Recovered Transactions: "
            f"{recovery_report.get('recovered_transactions', 0)}\n"
            f"Time Taken: "
            f"{recovery_report.get('time_taken', 0.0):.2f} seconds"
        )
        messagebox.showinfo("Recovery Report", text)
