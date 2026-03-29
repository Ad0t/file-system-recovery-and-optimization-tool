"""
performance_dashboard.py — Real-time performance dashboard widget.

Displays live file-system metrics, mini time-series charts drawn on
``tk.Canvas``, arc gauges, and colour-coded performance alerts inside
a ``ttk.Frame``.

Matplotlib is attempted for richer charts; if unavailable the module
falls back to pure ``tk.Canvas`` line charts.

Usage::

    from src.ui.performance_dashboard import PerformanceDashboard

    dash = PerformanceDashboard(parent_frame, analyzer)
    dash.update_metrics()   # or let the auto-refresh run
"""

import json
import logging
import math
import time
import tkinter as tk
from collections import deque
from tkinter import ttk, messagebox, filedialog
from typing import Any, Dict, List, Optional, Tuple

from src.recovery.performance_analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)

# Try to import matplotlib with TkAgg backend — graceful fallback
_HAS_MPL = False
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    _HAS_MPL = True
except ImportError:
    pass


# =========================================================================== #
#  Colour constants (Catppuccin Mocha)
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
}


# =========================================================================== #
#  PerformanceDashboard
# =========================================================================== #

class PerformanceDashboard:
    """
    Real-time performance dashboard panel.

    Attributes
    ----------
    parent_frame : ttk.Frame
        Container hosting the dashboard widgets.
    analyzer : PerformanceAnalyzer
        Source of all performance data.
    metrics_labels : dict[str, ttk.Label]
        Label widgets keyed by metric name.
    chart_canvas : tk.Canvas
        Canvas used for pure-Tk mini charts (fallback when matplotlib
        is not installed).
    update_interval : int
        Auto-refresh interval in milliseconds (default 1000).
    metrics_history : dict[str, deque]
        Rolling window of recent metric samples for charting.
    """

    _HISTORY_LENGTH = 60        # keep 60 data points (≈ 1 minute)
    _GAUGE_SIZE      = 100      # diameter of each arc gauge

    # ---- threshold tables ------------------------------------------------ #
    _THRESHOLDS: Dict[str, List[Tuple[float, str]]] = {
        # (upper_bound, colour) — evaluated in order; first match wins
        "disk_usage":     [(60, "green"), (85, "yellow"), (101, "red")],
        "fragmentation":  [(30, "green"), (50, "yellow"), (101, "red")],
        "cache_hit_rate": [(50, "red"),   (75, "yellow"), (101, "green")],
        "free_space":     [(10, "red"),   (30, "yellow"), (101, "green")],
    }

    # --------------------------------------------------------------------- #
    #  Construction
    # --------------------------------------------------------------------- #

    def __init__(self, parent_frame: ttk.Frame,
                 analyzer: PerformanceAnalyzer,
                 *,
                 update_interval: int = 1000,
                 cache_manager=None,
                 disk=None):
        self.parent_frame = parent_frame
        self.analyzer = analyzer
        self.update_interval = update_interval

        # Optional direct references for extra stats
        self._cache = cache_manager
        self._disk = disk

        self.metrics_labels: Dict[str, ttk.Label] = {}
        self.chart_canvas: Optional[tk.Canvas] = None
        self._mpl_canvases: Dict[str, Any] = {}

        # Rolling history
        self.metrics_history: Dict[str, deque] = {
            "disk_usage":    deque(maxlen=self._HISTORY_LENGTH),
            "fragmentation": deque(maxlen=self._HISTORY_LENGTH),
            "cache_hit_rate": deque(maxlen=self._HISTORY_LENGTH),
            "read_tp":       deque(maxlen=self._HISTORY_LENGTH),
            "write_tp":      deque(maxlen=self._HISTORY_LENGTH),
        }

        # Alert state
        self._active_alerts: List[str] = []

        self.create_layout()

        # Kick off the first refresh
        self._schedule_update()

    # --------------------------------------------------------------------- #
    #  Layout
    # --------------------------------------------------------------------- #

    def create_layout(self):
        """Build the three-section vertical layout (metrics → charts → quick stats)."""

        # Make the parent scrollable
        outer = ttk.Frame(self.parent_frame)
        outer.pack(fill=tk.BOTH, expand=True)

        # ---- top: metric cards ---- #
        self.create_metrics_display(outer)

        # ---- middle: mini charts ---- #
        self.create_charts(outer)

        # ---- bottom: gauges + alerts ---- #
        bottom = ttk.Frame(outer)
        bottom.pack(fill=tk.X, padx=2, pady=2)

        self._create_gauges(bottom)
        self.add_performance_alerts(bottom)

        # ---- buttons ---- #
        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill=tk.X, padx=4, pady=(0, 4))

        ttk.Button(btn_frame, text="▶ Benchmark",
                   command=self.benchmark_now).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="📄 Export",
                   command=self.export_metrics_report).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="📋 Details",
                   command=self.show_detailed_metrics).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="↺ Reset",
                   command=self.reset_statistics).pack(side=tk.LEFT, padx=2)

    # --------------------------------------------------------------------- #
    #  Metrics display (top section)
    # --------------------------------------------------------------------- #

    def create_metrics_display(self, parent: ttk.Frame):
        """Build colour-coded metric labels."""
        frame = ttk.LabelFrame(parent, text="  Current Metrics  ",
                                padding=6)
        frame.pack(fill=tk.X, padx=2, pady=2)

        metric_defs = [
            ("disk_usage",     "Disk Usage",       "%"),
            ("fragmentation",  "Fragmentation",    "%"),
            ("cache_hit_rate", "Cache Hit Rate",    "%"),
            ("read_tp",        "Read Throughput",   "MB/s"),
            ("write_tp",       "Write Throughput",  "MB/s"),
            ("iops",           "IOPS",              ""),
            ("free_space",     "Free Space",        ""),
        ]

        for key, label, unit in metric_defs:
            row = ttk.Frame(frame)
            row.pack(fill=tk.X, pady=1)

            ttk.Label(row, text=f"{label}:",
                      font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

            val_lbl = tk.Label(row, text="—",
                               font=("Consolas", 13, "bold"),
                               bg=_PAL["bg"], fg=_PAL["green"],
                               anchor=tk.E)
            val_lbl.pack(side=tk.RIGHT)
            self.metrics_labels[key] = val_lbl

    # --------------------------------------------------------------------- #
    #  Charts (middle section)
    # --------------------------------------------------------------------- #

    def create_charts(self, parent: ttk.Frame):
        """Create mini time-series charts — matplotlib if available, else Canvas."""
        frame = ttk.LabelFrame(parent, text="  Trends  ", padding=4)
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        if _HAS_MPL:
            self._create_mpl_charts(frame)
        else:
            self._create_canvas_charts(frame)

    # ---- matplotlib path ------------------------------------------------ #

    def _create_mpl_charts(self, parent: ttk.Frame):
        """Create three matplotlib mini charts embedded in Tkinter."""
        chart_defs = [
            ("disk_usage",    "Disk Usage %",    _PAL["blue"]),
            ("cache_hit_rate", "Cache Hit %",    _PAL["green"]),
            ("read_tp",       "Read MB/s",       _PAL["peach"]),
        ]

        row_frame = ttk.Frame(parent)
        row_frame.pack(fill=tk.BOTH, expand=True)

        for idx, (key, title, colour) in enumerate(chart_defs):
            fig = Figure(figsize=(2.6, 1.5), dpi=80)
            fig.patch.set_facecolor(_PAL["surface"])
            ax = fig.add_subplot(111)
            ax.set_facecolor(_PAL["surface"])
            ax.set_title(title, fontsize=8, color=_PAL["fg"], pad=4)
            ax.tick_params(colors=_PAL["dim"], labelsize=6)
            for spine in ax.spines.values():
                spine.set_color(_PAL["border"])
            ax.plot([], [], color=colour, linewidth=1.5)

            canvas = FigureCanvasTkAgg(fig, master=row_frame)
            widget = canvas.get_tk_widget()
            widget.grid(row=0, column=idx, padx=2, pady=2, sticky="nsew")
            row_frame.grid_columnconfigure(idx, weight=1)

            self._mpl_canvases[key] = (fig, ax, canvas, colour)

        row_frame.grid_rowconfigure(0, weight=1)

    def _update_mpl_chart(self, key: str):
        """Redraw a single matplotlib chart with current history."""
        if key not in self._mpl_canvases:
            return
        fig, ax, canvas, colour = self._mpl_canvases[key]
        data = list(self.metrics_history.get(key, []))
        ax.clear()
        ax.set_facecolor(_PAL["surface"])

        titles = {
            "disk_usage": "Disk Usage %",
            "cache_hit_rate": "Cache Hit %",
            "read_tp": "Read MB/s",
        }
        ax.set_title(titles.get(key, key), fontsize=8,
                      color=_PAL["fg"], pad=4)
        ax.tick_params(colors=_PAL["dim"], labelsize=6)
        for spine in ax.spines.values():
            spine.set_color(_PAL["border"])

        if data:
            ax.plot(range(len(data)), data, color=colour, linewidth=1.5)
            ax.fill_between(range(len(data)), data,
                            alpha=0.15, color=colour)
        ax.set_xlim(0, max(self._HISTORY_LENGTH, len(data)))
        try:
            canvas.draw_idle()
        except Exception:
            pass

    # ---- pure-Canvas fallback ------------------------------------------- #

    def _create_canvas_charts(self, parent: ttk.Frame):
        """Fallback: create a single canvas for line charts."""
        self.chart_canvas = tk.Canvas(parent, height=160,
                                       bg=_PAL["surface"],
                                       highlightthickness=0)
        self.chart_canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

    def _draw_canvas_charts(self):
        """Redraw all lines on the fallback canvas."""
        c = self.chart_canvas
        if c is None:
            return
        c.delete("all")
        cw = c.winfo_width() or 400
        ch = c.winfo_height() or 140

        chart_defs = [
            ("disk_usage",     _PAL["blue"],  "Disk %"),
            ("cache_hit_rate", _PAL["green"], "Cache %"),
            ("read_tp",        _PAL["peach"], "Read MB/s"),
        ]

        legend_x = 6
        for key, colour, label in chart_defs:
            data = list(self.metrics_history.get(key, []))
            if not data:
                continue

            maxv = max(max(data), 1)
            n = len(data)
            step = cw / max(n, 1)
            pad = 16

            points = []
            for i, v in enumerate(data):
                x = i * step
                y = ch - pad - (v / maxv) * (ch - 2 * pad)
                points.append(x)
                points.append(y)

            if len(points) >= 4:
                c.create_line(*points, fill=colour, width=2, smooth=True)

            # Legend swatch
            c.create_rectangle(legend_x, 4, legend_x + 10, 14,
                               fill=colour, outline="")
            c.create_text(legend_x + 14, 9, text=label, anchor=tk.W,
                          fill=_PAL["fg"], font=("Segoe UI", 7))
            legend_x += len(label) * 6 + 30

    # --------------------------------------------------------------------- #
    #  Gauges
    # --------------------------------------------------------------------- #

    def _create_gauges(self, parent: ttk.Frame):
        """Draw three arc-gauge canvases for headline metrics."""
        gauge_frame = ttk.LabelFrame(parent, text="  Gauges  ", padding=4)
        gauge_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self._gauge_canvases: Dict[str, tk.Canvas] = {}
        self._gauge_data: Dict[str, float] = {}

        for key, label in [("perf_score", "Score"),
                            ("disk_usage", "Disk %"),
                            ("cache_hit", "Cache %")]:
            cv = tk.Canvas(gauge_frame,
                           width=self._GAUGE_SIZE,
                           height=self._GAUGE_SIZE + 18,
                           bg=_PAL["bg"], highlightthickness=0)
            cv.pack(side=tk.LEFT, padx=6, pady=2)
            self._gauge_canvases[key] = cv
            self._gauge_data[key] = 0.0

    def create_gauge(self, parent_canvas: tk.Canvas,
                      label: str, value: float, max_value: float):
        """Draw one circular arc gauge on *parent_canvas*."""
        cv = parent_canvas
        cv.delete("all")
        sz = self._GAUGE_SIZE
        pad = 8
        cx, cy = sz // 2, sz // 2
        r = (sz - 2 * pad) // 2

        # Background arc (270°)
        cv.create_arc(pad, pad, sz - pad, sz - pad,
                      start=135, extent=270,
                      style=tk.ARC, outline=_PAL["border"], width=8)

        # Value arc
        ratio = min(value / max(max_value, 1), 1.0)
        extent = ratio * 270

        colour = self._get_gauge_colour(ratio)
        cv.create_arc(pad, pad, sz - pad, sz - pad,
                      start=135, extent=extent,
                      style=tk.ARC, outline=colour, width=8)

        # Centre text
        display = f"{value:.0f}" if value == int(value) else f"{value:.1f}"
        cv.create_text(cx, cy - 2, text=display,
                       font=("Consolas", 14, "bold"),
                       fill=_PAL["fg"])

        # Label below
        cv.create_text(cx, sz + 6, text=label,
                       font=("Segoe UI", 8), fill=_PAL["dim"])

    @staticmethod
    def _get_gauge_colour(ratio: float) -> str:
        """Return green/yellow/red based on a 0-1 ratio."""
        if ratio < 0.5:
            return _PAL["green"]
        elif ratio < 0.8:
            return _PAL["yellow"]
        return _PAL["red"]

    def _update_gauges(self, metrics: Dict[str, Any]):
        """Redraw all gauge arcs with fresh metrics."""
        score = self.analyzer.calculate_performance_score()
        disk_u = metrics.get("disk_usage_percentage", 0)
        cache_h = metrics.get("cache_hit_rate", 0)

        if "perf_score" in self._gauge_canvases:
            self.create_gauge(self._gauge_canvases["perf_score"],
                              "Score", score, 100)
        if "disk_usage" in self._gauge_canvases:
            self.create_gauge(self._gauge_canvases["disk_usage"],
                              "Disk %", disk_u, 100)
        if "cache_hit" in self._gauge_canvases:
            self.create_gauge(self._gauge_canvases["cache_hit"],
                              "Cache %", cache_h, 100)

    # --------------------------------------------------------------------- #
    #  Alerts
    # --------------------------------------------------------------------- #

    def add_performance_alerts(self, parent: ttk.Frame = None):
        """Create the alert panel and populate initial state."""
        target = parent or self.parent_frame
        alert_frame = ttk.LabelFrame(target, text="  Alerts  ", padding=4)
        alert_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self._alert_text = tk.Text(alert_frame, height=4, wrap=tk.WORD,
                                    bg=_PAL["surface"], fg=_PAL["fg"],
                                    font=("Consolas", 9),
                                    borderwidth=0, relief=tk.FLAT,
                                    state=tk.DISABLED)
        self._alert_text.pack(fill=tk.BOTH, expand=True)

    def _refresh_alerts(self, metrics: Dict[str, Any]):
        """Check thresholds and refresh the alert text widget."""
        alerts: List[str] = []
        disk_u = metrics.get("disk_usage_percentage", 0)
        frag   = metrics.get("fragmentation_percentage", 0)
        cache  = metrics.get("cache_hit_rate", 0)

        if disk_u > 90:
            alerts.append(f"🔴 Disk usage critical: {disk_u:.1f}%")
        elif disk_u > 75:
            alerts.append(f"🟡 Disk usage high: {disk_u:.1f}%")

        if frag > 60:
            alerts.append(f"🔴 Fragmentation severe: {frag:.1f}%")
        elif frag > 30:
            alerts.append(f"🟡 Fragmentation elevated: {frag:.1f}%")

        if cache < 50:
            alerts.append(f"🔴 Cache hit rate low: {cache:.1f}%")
        elif cache < 75:
            alerts.append(f"🟡 Cache hit rate moderate: {cache:.1f}%")

        if not alerts:
            alerts.append("✅ All systems normal")

        self._active_alerts = alerts
        self._alert_text.configure(state=tk.NORMAL)
        self._alert_text.delete("1.0", tk.END)
        self._alert_text.insert(tk.END, "\n".join(alerts))
        self._alert_text.configure(state=tk.DISABLED)

    # --------------------------------------------------------------------- #
    #  Periodic update
    # --------------------------------------------------------------------- #

    def update_metrics(self):
        """
        Fetch current metrics, update labels / charts / gauges / alerts,
        and schedule the next tick.
        """
        try:
            metrics = self.analyzer.collect_metrics()
            iops = self.analyzer.calculate_iops()
            throughput = self.analyzer.measure_throughput()

            # ---- labels ---- #
            du = metrics.get("disk_usage_percentage", 0)
            fg = metrics.get("fragmentation_percentage", 0)
            ch = metrics.get("cache_hit_rate", 0)
            rt = throughput.get("read_throughput_mbps", 0)
            wt = throughput.get("write_throughput_mbps", 0)
            ti = iops.get("total_iops", 0)
            fs = metrics.get("free_space_percentage", 0)

            self._update_metric_label("disk_usage", du, "%")
            self._update_metric_label("fragmentation", fg, "%")
            self._update_metric_label("cache_hit_rate", ch, "%")
            self._update_metric_label("read_tp", rt, "MB/s")
            self._update_metric_label("write_tp", wt, "MB/s")
            self._update_metric_label("iops", ti, "")
            self._update_metric_label("free_space",
                                       self._format_metric_value(fs, "percentage"),
                                       "")

            # ---- history ---- #
            self.metrics_history["disk_usage"].append(du)
            self.metrics_history["fragmentation"].append(fg)
            self.metrics_history["cache_hit_rate"].append(ch)
            self.metrics_history["read_tp"].append(rt)
            self.metrics_history["write_tp"].append(wt)

            # ---- charts ---- #
            if _HAS_MPL:
                for key in ("disk_usage", "cache_hit_rate", "read_tp"):
                    self._update_mpl_chart(key)
            else:
                self._draw_canvas_charts()

            # ---- gauges ---- #
            self._update_gauges(metrics)

            # ---- alerts ---- #
            self._refresh_alerts(metrics)

        except Exception as exc:
            logger.debug("Dashboard update error: %s", exc)

    def _schedule_update(self):
        """Schedule the next update_metrics() call."""
        self.update_metrics()
        self.parent_frame.after(self.update_interval, self._schedule_update)

    # --------------------------------------------------------------------- #
    #  Label helpers
    # --------------------------------------------------------------------- #

    def _update_metric_label(self, metric_name: str,
                              value: Any, unit: str = ""):
        """Update a specific metric label with colour coding."""
        lbl = self.metrics_labels.get(metric_name)
        if lbl is None:
            return
        text = self._format_metric_value(value, unit)
        colour = self._color_code_value(metric_name, float(value)
                                        if not isinstance(value, str) else 0)
        lbl.configure(text=text, fg=colour)

    def _color_code_value(self, metric_name: str, value: float) -> str:
        """Return the hex colour for *value* based on metric thresholds."""
        return self._get_threshold_color(metric_name, value)

    def _get_threshold_color(self, metric_name: str,
                              value: float) -> str:
        """Look up the threshold table and return the matching palette colour."""
        thresholds = self._THRESHOLDS.get(metric_name)
        if thresholds is None:
            return _PAL["fg"]
        for bound, col_name in thresholds:
            if value < bound:
                return _PAL.get(col_name, _PAL["fg"])
        return _PAL["fg"]

    # --------------------------------------------------------------------- #
    #  Formatting helpers
    # --------------------------------------------------------------------- #

    @staticmethod
    def _format_metric_value(value: Any, metric_type: str) -> str:
        """
        Format *value* for display.

        *metric_type* examples: ``'%'``, ``'MB/s'``, ``'percentage'``,
        ``''`` (unitless integer).
        """
        if isinstance(value, str):
            return value
        if metric_type in ("%", "percentage"):
            return f"{value:.1f} %"
        elif metric_type == "MB/s":
            return f"{value:.1f} MB/s"
        elif metric_type == "":
            if isinstance(value, float) and value == int(value):
                return f"{int(value)}"
            return f"{value:.1f}" if isinstance(value, float) else str(value)
        return str(value)

    # --------------------------------------------------------------------- #
    #  Chart draw helper (for show_detailed_metrics)
    # --------------------------------------------------------------------- #

    def _draw_chart(self, chart_name: str,
                    data: List[Tuple[float, float]]):
        """
        Draw a time-series chart (used by detailed-metrics dialog).

        Parameters
        ----------
        chart_name : str
            Title for the chart.
        data : list[tuple[float, float]]
            ``(timestamp, value)`` pairs.
        """
        if not _HAS_MPL or not data:
            return

        win = tk.Toplevel(self.parent_frame)
        win.title(chart_name)
        win.geometry("500x350")

        fig = Figure(figsize=(5, 3.2), dpi=96)
        fig.patch.set_facecolor(_PAL["surface"])
        ax = fig.add_subplot(111)
        ax.set_facecolor(_PAL["surface"])
        ax.set_title(chart_name, color=_PAL["fg"], fontsize=10)
        ax.tick_params(colors=_PAL["dim"], labelsize=7)
        for spine in ax.spines.values():
            spine.set_color(_PAL["border"])

        xs = [d[0] for d in data]
        ys = [d[1] for d in data]
        ax.plot(xs, ys, color=_PAL["blue"], linewidth=1.5)
        ax.fill_between(xs, ys, alpha=0.12, color=_PAL["blue"])

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # --------------------------------------------------------------------- #
    #  Detailed metrics dialog
    # --------------------------------------------------------------------- #

    def show_detailed_metrics(self):
        """Show a comprehensive metrics dialog with historical data."""
        root_w = self.parent_frame.winfo_toplevel()
        metrics = self.analyzer.collect_metrics()
        analysis = self.analyzer.analyze_bottlenecks()
        recs = self.analyzer.recommend_optimizations()

        lines = [
            "═══════════ Detailed Metrics ═══════════",
            "",
            f"Timestamp:         {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Disk Usage:        {metrics.get('disk_usage_percentage', 0):.1f} %",
            f"Free Space:        {metrics.get('free_space_percentage', 100):.1f} %",
            f"Fragmentation:     {metrics.get('fragmentation_percentage', 0):.1f} %",
            f"Cache Hit Rate:    {metrics.get('cache_hit_rate', 0):.1f} %",
            f"Total Operations:  {metrics.get('total_operations', 0)}",
            "",
            "═══════════ Bottlenecks ═══════════",
        ]
        for b in analysis.get("bottlenecks", []):
            lines.append(f"  ▸ {b}")
        lines.append("")
        lines.append("═══════════ Recommendations ═══════════")
        for r in recs:
            lines.append(
                f"  [{r.get('priority', '?')}] {r.get('description', '')}")
        lines.append("")

        # History summary
        for key in ("disk_usage", "cache_hit_rate"):
            hist = list(self.metrics_history.get(key, []))
            if hist:
                lines.append(
                    f"{key}: min={min(hist):.1f}  "
                    f"max={max(hist):.1f}  "
                    f"avg={sum(hist)/len(hist):.1f}  "
                    f"samples={len(hist)}")

        messagebox.showinfo("Detailed Metrics",
                            "\n".join(lines), parent=root_w)

    # --------------------------------------------------------------------- #
    #  Benchmark now
    # --------------------------------------------------------------------- #

    def benchmark_now(self):
        """Run read + write benchmarks and display a summary."""
        root_w = self.parent_frame.winfo_toplevel()
        try:
            read_r = self.analyzer.benchmark_read_performance()
            write_r = self.analyzer.benchmark_write_performance()
            self.update_metrics()

            lines = ["═══ Read Benchmark ═══"]
            for sz, mbps in read_r.get("sequential_read_mbps", {}).items():
                lines.append(
                    f"  {self._human_size(sz):>10}  →  "
                    f"{mbps:.1f} MB/s (seq)")
            lines.append("")
            lines.append("═══ Write Benchmark ═══")
            for sz, mbps in write_r.get("sequential_write_mbps", {}).items():
                lines.append(
                    f"  {self._human_size(sz):>10}  →  "
                    f"{mbps:.1f} MB/s (seq)")

            messagebox.showinfo("Benchmark Results",
                                "\n".join(lines), parent=root_w)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=root_w)

    # --------------------------------------------------------------------- #
    #  Export
    # --------------------------------------------------------------------- #

    def export_metrics_report(self):
        """Export current metrics + history to CSV or JSON."""
        root_w = self.parent_frame.winfo_toplevel()
        path = filedialog.asksaveasfilename(
            title="Export Metrics Report",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV", "*.csv"),
                       ("Text", "*.txt"), ("All", "*.*")],
            parent=root_w)
        if not path:
            return

        try:
            metrics = self.analyzer.collect_metrics()
            history = {k: list(v) for k, v in self.metrics_history.items()}

            if path.endswith(".json"):
                payload = {"current": metrics, "history": history,
                           "alerts": self._active_alerts}
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, default=str)
            elif path.endswith(".csv"):
                self.analyzer.export_metrics(path, format="csv")
            else:
                report = self.analyzer.generate_performance_report("text")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(report)

            messagebox.showinfo("Export", f"Report saved to:\n{path}",
                                parent=root_w)
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc), parent=root_w)

    # --------------------------------------------------------------------- #
    #  Reset
    # --------------------------------------------------------------------- #

    def reset_statistics(self):
        """Clear history and counters after user confirmation."""
        root_w = self.parent_frame.winfo_toplevel()
        if not messagebox.askyesno("Reset Statistics",
                                   "Clear all metric history and counters?",
                                   parent=root_w):
            return

        for dq in self.metrics_history.values():
            dq.clear()

        self.analyzer.metrics_history.clear()
        self._active_alerts.clear()
        self.update_metrics()
        messagebox.showinfo("Reset", "Statistics have been reset.",
                            parent=root_w)

    # --------------------------------------------------------------------- #
    #  Utility
    # --------------------------------------------------------------------- #

    @staticmethod
    def _human_size(n: int) -> str:
        """Format a byte count as a compact human string."""
        if n < 1024:
            return f"{n} B"
        elif n < 1024 ** 2:
            return f"{n / 1024:.0f} KB"
        elif n < 1024 ** 3:
            return f"{n / 1024**2:.1f} MB"
        return f"{n / 1024**3:.1f} GB"
