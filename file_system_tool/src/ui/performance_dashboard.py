"""
performance_dashboard.py - Real-time performance metrics dashboard.

Provides a PerformanceDashboard component that renders live metric
cards, arc gauges, time-series charts (via matplotlib), and alert
banners inside a Tkinter frame.  Metrics are refreshed periodically
from a ``PerformanceAnalyzer`` instance.

Dependencies:
    - tkinter (stdlib): Widget creation and layout.
    - matplotlib (optional but recommended): Embedded time-series charts.
    - PerformanceAnalyzer: Metrics collection and benchmark engine.

Usage::

    from src.ui.performance_dashboard import PerformanceDashboard

    dashboard = PerformanceDashboard(parent_frame, analyzer)
    # Periodic updates are started automatically.
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


# ====================================================================== #
#  Colour palette  (mirrors main_window.py for visual consistency)
# ====================================================================== #

_COLORS = {
    "bg_dark":        "#1a1a2e",
    "bg_panel":       "#16213e",
    "bg_card":        "#0f3460",
    "accent_primary": "#e94560",
    "accent_green":   "#00d2a0",
    "accent_yellow":  "#f5c542",
    "accent_blue":    "#4fc3f7",
    "accent_orange":  "#ff8c42",
    "text_primary":   "#e0e0e0",
    "text_secondary": "#a0a0b0",
    "text_header":    "#ffffff",
    "border":         "#2a2a4a",
    "success":        "#4caf50",
    "warning":        "#ff9800",
    "error":          "#f44336",
}

_FONT_HEADER  = ("Segoe UI", 14, "bold")
_FONT_SUBHEAD = ("Segoe UI", 11, "bold")
_FONT_BODY    = ("Segoe UI", 10)
_FONT_SMALL   = ("Segoe UI", 9)
_FONT_MONO    = ("Consolas", 10)
_FONT_METRIC  = ("Segoe UI", 20, "bold")
_FONT_METRIC_LABEL = ("Segoe UI", 9)

# Maximum data-points kept per chart series
_MAX_HISTORY_POINTS = 60


# ====================================================================== #
#  Threshold configuration
# ====================================================================== #

# (metric_key, lower_warn, lower_crit_or_upper_crit, invert?)
# For "higher is worse" metrics  → invert = False
# For "higher is better" metrics → invert = True
_THRESHOLDS: Dict[str, Dict[str, Any]] = {
    "disk_usage_percentage":    {"yellow": 70, "red": 90, "invert": False},
    "fragmentation_percentage": {"yellow": 30, "red": 50, "invert": False},
    "cache_hit_rate":           {"yellow": 70, "red": 50, "invert": True},
    "free_space_percentage":    {"yellow": 25, "red": 10, "invert": True},
    "read_throughput":          {"yellow": 30, "red": 10, "invert": True},
    "write_throughput":         {"yellow": 20, "red": 5,  "invert": True},
    "total_iops":               {"yellow": 300,"red": 100,"invert": True},
}


class PerformanceDashboard:
    """
    Live performance metrics dashboard for the File System Simulator.

    Embeds metric cards, arc gauges, matplotlib time-series charts,
    and coloured alert banners inside a parent ``ttk.Frame``.

    Attributes:
        parent_frame (ttk.Frame): Parent container.
        analyzer (PerformanceAnalyzer): Metrics & benchmark engine.
        metrics_labels (dict): Mapping of metric key → label widget.
        chart_canvas (tk.Canvas): Fallback canvas when matplotlib is
            unavailable.
        update_interval (int): Refresh interval in milliseconds.
        metrics_history (dict): Deques of recent metric values per key.
    """

    # ------------------------------------------------------------------ #
    #  Initialization
    # ------------------------------------------------------------------ #

    def __init__(self, parent_frame: ttk.Frame,
                 analyzer: PerformanceAnalyzer):
        """
        Initialize the performance dashboard.

        Creates the full layout (metric cards, gauges, charts, alert
        bar, action buttons), pre-populates widgets, and kicks off
        the periodic update loop.

        Args:
            parent_frame: Tkinter container to pack into.
            analyzer: PerformanceAnalyzer instance.
        """
        self.parent_frame = parent_frame
        self.analyzer = analyzer

        self.update_interval: int = 1000  # ms
        self.metrics_labels: Dict[str, tk.Label] = {}
        self.chart_canvas: Optional[tk.Canvas] = None
        self._after_id: Optional[str] = None

        # Recent metric history for time-series charts
        self.metrics_history: Dict[str, deque] = {
            "disk_usage_percentage":    deque(maxlen=_MAX_HISTORY_POINTS),
            "fragmentation_percentage": deque(maxlen=_MAX_HISTORY_POINTS),
            "cache_hit_rate":           deque(maxlen=_MAX_HISTORY_POINTS),
            "read_throughput":          deque(maxlen=_MAX_HISTORY_POINTS),
            "write_throughput":         deque(maxlen=_MAX_HISTORY_POINTS),
            "total_iops":              deque(maxlen=_MAX_HISTORY_POINTS),
            "free_space_percentage":    deque(maxlen=_MAX_HISTORY_POINTS),
        }

        # Gauge canvas widgets (populated in create_layout)
        self._gauge_canvases: Dict[str, tk.Canvas] = {}

        # matplotlib figure objects (populated if available)
        self._mpl_available = False
        self._fig = None
        self._axes: Dict[str, Any] = {}
        self._mpl_canvas_widget = None

        # ---- Build layout ----
        self.create_layout()

        # ---- Start periodic refresh ----
        self.parent_frame.after(300, self.update_metrics)

    # ------------------------------------------------------------------ #
    #  Layout
    # ------------------------------------------------------------------ #

    def create_layout(self) -> None:
        """
        Build the three-section dashboard layout:

        1. **Top** — Current metric cards.
        2. **Middle** — Arc gauges + time-series charts.
        3. **Bottom** — Quick stats, alerts, and action buttons.
        """
        # Make parent frame background consistent
        self.parent_frame.configure(style="TFrame")

        # ---- Top: Metric cards ----
        self.create_metrics_display()

        # ---- Middle: Gauges + Charts ----
        mid_frame = ttk.Frame(self.parent_frame)
        mid_frame.pack(fill="both", expand=True, padx=6, pady=(2, 0))

        gauge_lf = ttk.LabelFrame(mid_frame, text="  Gauges  ")
        gauge_lf.pack(side="left", fill="both", padx=(0, 4), pady=2)
        self._build_gauges(gauge_lf)

        chart_lf = ttk.LabelFrame(mid_frame, text="  Trends  ")
        chart_lf.pack(side="left", fill="both", expand=True, pady=2)
        self.create_charts(chart_lf)

        # ---- Bottom: Alerts + actions ----
        bot_frame = ttk.Frame(self.parent_frame)
        bot_frame.pack(fill="x", padx=6, pady=(4, 6))

        self._alert_label = tk.Label(
            bot_frame, text="", bg=_COLORS["bg_panel"],
            fg=_COLORS["text_primary"], font=_FONT_SMALL,
            anchor="w", padx=8, pady=4,
        )
        self._alert_label.pack(fill="x", pady=(0, 4))

        btn_bar = ttk.Frame(bot_frame)
        btn_bar.pack(fill="x")
        ttk.Button(btn_bar, text="⚡ Benchmark Now",
                   command=self.benchmark_now).pack(side="left", padx=2)
        ttk.Button(btn_bar, text="📄 Export Report",
                   command=self.export_metrics_report).pack(
            side="left", padx=2)
        ttk.Button(btn_bar, text="📊 Detailed View",
                   command=self.show_detailed_metrics).pack(
            side="left", padx=2)
        ttk.Button(btn_bar, text="↺ Reset Stats",
                   command=self.reset_statistics).pack(side="left", padx=2)

    # ------------------------------------------------------------------ #
    #  Metric cards
    # ------------------------------------------------------------------ #

    def create_metrics_display(self) -> None:
        """
        Create the top row of colour-coded metric cards.

        Metrics displayed:
        - Disk Usage (%)
        - Fragmentation (%)
        - Cache Hit Rate (%)
        - Read Throughput (MB/s)
        - Write Throughput (MB/s)
        - IOPS
        - Free Space (%)
        """
        cards_frame = ttk.Frame(self.parent_frame)
        cards_frame.pack(fill="x", padx=6, pady=(6, 2))

        metric_defs = [
            ("disk_usage_percentage",    "Disk Usage",      "%",    _COLORS["accent_primary"]),
            ("fragmentation_percentage", "Fragmentation",   "%",    _COLORS["accent_yellow"]),
            ("cache_hit_rate",           "Cache Hit Rate",  "%",    _COLORS["accent_blue"]),
            ("read_throughput",          "Read Throughput",  "MB/s", _COLORS["accent_green"]),
            ("write_throughput",         "Write Throughput", "MB/s", _COLORS["accent_orange"]),
            ("total_iops",              "IOPS",             "",     _COLORS["text_primary"]),
            ("free_space_percentage",    "Free Space",       "%",   _COLORS["success"]),
        ]

        for i, (key, label_text, unit, accent) in enumerate(metric_defs):
            card = tk.Frame(
                cards_frame, bg=_COLORS["bg_panel"],
                highlightbackground=_COLORS["border"],
                highlightthickness=1, padx=10, pady=6,
            )
            card.grid(row=0, column=i, padx=3, sticky="nsew")
            cards_frame.columnconfigure(i, weight=1)

            # Value label
            val_lbl = tk.Label(
                card, text="—", bg=_COLORS["bg_panel"],
                fg=accent, font=_FONT_METRIC,
            )
            val_lbl.pack()

            # Title label
            tk.Label(
                card, text=label_text, bg=_COLORS["bg_panel"],
                fg=_COLORS["text_secondary"], font=_FONT_METRIC_LABEL,
            ).pack()

            self.metrics_labels[key] = val_lbl
            # Stash unit for formatting
            val_lbl._unit = unit  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    #  Gauges
    # ------------------------------------------------------------------ #

    def _build_gauges(self, parent: ttk.Frame) -> None:
        """Create arc-gauge canvases for the three primary metrics."""
        gauge_keys = [
            ("disk_usage_percentage",    "Disk Usage"),
            ("fragmentation_percentage", "Fragmentation"),
            ("cache_hit_rate",           "Cache Hit"),
        ]
        for key, title in gauge_keys:
            gf = tk.Frame(parent, bg=_COLORS["bg_dark"])
            gf.pack(padx=6, pady=4)
            canvas = tk.Canvas(
                gf, width=120, height=90,
                bg=_COLORS["bg_dark"], highlightthickness=0,
            )
            canvas.pack()
            tk.Label(
                gf, text=title, bg=_COLORS["bg_dark"],
                fg=_COLORS["text_secondary"], font=_FONT_SMALL,
            ).pack()
            self._gauge_canvases[key] = canvas
            self._draw_gauge(canvas, 0.0, key)

    def create_gauge(self, parent: tk.Frame, label: str,
                     value: float, max_value: float) -> tk.Canvas:
        """
        Create a standalone circular-arc gauge widget.

        Args:
            parent: Container frame.
            label: Title shown below the arc.
            value: Current value (0 – max_value).
            max_value: Full-scale value.

        Returns:
            The tk.Canvas containing the gauge.
        """
        canvas = tk.Canvas(
            parent, width=120, height=90,
            bg=_COLORS["bg_dark"], highlightthickness=0,
        )
        canvas.pack(padx=4, pady=4)
        pct = (value / max_value * 100) if max_value else 0
        self._draw_gauge(canvas, pct, "disk_usage_percentage")
        tk.Label(
            parent, text=label, bg=_COLORS["bg_dark"],
            fg=_COLORS["text_secondary"], font=_FONT_SMALL,
        ).pack()
        return canvas

    def _draw_gauge(self, canvas: tk.Canvas, pct: float,
                    metric_key: str) -> None:
        """Render an arc gauge on *canvas* for *pct* (0-100)."""
        canvas.delete("all")
        w, h = 120, 90
        cx, cy, r = w // 2, h - 10, 45
        start_angle = 180  # leftmost point of the semicircle
        extent = 180       # full semicircle

        # Background arc (track)
        canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=start_angle, extent=extent,
            style="arc", width=10,
            outline=_COLORS["border"],
        )

        # Foreground arc (value)
        color = self._get_threshold_color(metric_key, pct)
        value_extent = max(0, min(extent, extent * pct / 100))
        canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=start_angle, extent=value_extent,
            style="arc", width=10,
            outline=color,
        )

        # Centre text
        canvas.create_text(
            cx, cy - 18, text=f"{pct:.0f}%",
            fill=color, font=("Segoe UI", 12, "bold"),
        )

    # ------------------------------------------------------------------ #
    #  Charts  (matplotlib if available, fallback canvas otherwise)
    # ------------------------------------------------------------------ #

    def create_charts(self, parent: ttk.Frame = None) -> None:
        """
        Create embedded time-series charts.

        If *matplotlib* is installed, three small axes are created
        (Disk Usage, Throughput, Cache Hit Rate) inside a single
        Figure embedded via ``FigureCanvasTkAgg``.

        Otherwise a plain ``tk.Canvas`` is used with simple line
        drawing.

        Args:
            parent: Container (defaults to parent_frame if None).
        """
        if parent is None:
            parent = self.parent_frame

        try:
            import matplotlib
            matplotlib.use("Agg")  # non-interactive backend first
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            self._mpl_available = True

            self._fig = Figure(figsize=(5.5, 3), dpi=80,
                               facecolor=_COLORS["bg_dark"])
            self._fig.subplots_adjust(
                hspace=0.55, left=0.12, right=0.95, top=0.92, bottom=0.10,
            )

            ax_disk = self._fig.add_subplot(3, 1, 1)
            ax_thru = self._fig.add_subplot(3, 1, 2)
            ax_cache = self._fig.add_subplot(3, 1, 3)

            self._axes = {
                "disk_usage_percentage": ax_disk,
                "throughput":            ax_thru,
                "cache_hit_rate":        ax_cache,
            }

            for ax, title in [
                (ax_disk,  "Disk Usage %"),
                (ax_thru,  "Throughput MB/s"),
                (ax_cache, "Cache Hit %"),
            ]:
                ax.set_facecolor(_COLORS["bg_panel"])
                ax.tick_params(colors=_COLORS["text_secondary"],
                               labelsize=7)
                ax.set_title(title, fontsize=8,
                             color=_COLORS["text_header"], pad=3)
                for spine in ax.spines.values():
                    spine.set_color(_COLORS["border"])

            self._mpl_canvas_widget = FigureCanvasTkAgg(self._fig, parent)
            self._mpl_canvas_widget.get_tk_widget().pack(
                fill="both", expand=True, padx=2, pady=2,
            )

        except ImportError:
            logger.info("matplotlib not available — using fallback canvas.")
            self._mpl_available = False
            self.chart_canvas = tk.Canvas(
                parent, bg=_COLORS["bg_panel"], highlightthickness=0,
            )
            self.chart_canvas.pack(fill="both", expand=True, padx=2, pady=2)

    # ------------------------------------------------------------------ #
    #  Periodic update
    # ------------------------------------------------------------------ #

    def update_metrics(self) -> None:
        """
        Fetch current metrics from the analyzer, update labels,
        append to history, redraw charts, and check alerts.

        Automatically reschedules itself after ``update_interval`` ms.
        """
        try:
            metrics = self.analyzer.collect_metrics()

            # Throughput & IOPS (from helper methods)
            throughput = self.analyzer.measure_throughput()
            iops = self.analyzer.calculate_iops()

            metrics["read_throughput"]  = throughput.get(
                "read_throughput_mbps", 0.0)
            metrics["write_throughput"] = throughput.get(
                "write_throughput_mbps", 0.0)
            metrics["total_iops"]       = iops.get("total_iops", 0.0)

            # Update label widgets
            for key, label in self.metrics_labels.items():
                val = metrics.get(key, 0.0)
                self._update_metric_label(key, val, getattr(label, "_unit", ""))

            # Push into history
            ts = time.time()
            for key in self.metrics_history:
                self.metrics_history[key].append(
                    (ts, metrics.get(key, 0.0))
                )

            # Redraw gauges
            for key, canvas in self._gauge_canvases.items():
                self._draw_gauge(canvas, metrics.get(key, 0.0), key)

            # Redraw charts
            self._refresh_charts()

            # Performance alerts
            self.add_performance_alerts(metrics)

        except Exception as exc:
            logger.error("Dashboard update error: %s", exc)

        # Schedule next tick
        self._after_id = self.parent_frame.after(
            self.update_interval, self.update_metrics,
        )

    # ------------------------------------------------------------------ #
    #  Label updates
    # ------------------------------------------------------------------ #

    def _update_metric_label(self, metric_name: str, value: Any,
                             unit: str = "") -> None:
        """
        Update a single metric label with a formatted, colour-coded value.

        Args:
            metric_name: Key into ``metrics_labels``.
            value: Raw numeric value.
            unit: Display unit string (e.g. ``'%'``, ``'MB/s'``).
        """
        label = self.metrics_labels.get(metric_name)
        if label is None:
            return

        text = self._format_metric_value(value, unit)
        color = self._get_threshold_color(metric_name, float(value))
        label.configure(text=text, fg=color)

    @staticmethod
    def _format_metric_value(value: float, unit: str) -> str:
        """
        Format a numeric metric value for display.

        Args:
            value: Numeric value.
            unit: Unit suffix.

        Returns:
            Formatted string such as ``'42.3%'`` or ``'1,250'``.
        """
        if unit == "%":
            return f"{value:.1f}%"
        elif unit in ("MB/s", "mb/s"):
            return f"{value:.1f} MB/s"
        elif isinstance(value, float) and value == int(value):
            return f"{int(value):,}{' ' + unit if unit else ''}"
        elif isinstance(value, float):
            return f"{value:,.1f}{' ' + unit if unit else ''}"
        return f"{value}{' ' + unit if unit else ''}"

    # ------------------------------------------------------------------ #
    #  Threshold colouring
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_threshold_color(metric_name: str, value: float) -> str:
        """
        Return a hex colour based on the metric's threshold rules.

        Args:
            metric_name: Key into ``_THRESHOLDS``.
            value: Current metric value.

        Returns:
            Hex colour string (green / yellow / red).
        """
        cfg = _THRESHOLDS.get(metric_name)
        if cfg is None:
            return _COLORS["text_primary"]

        yellow = cfg["yellow"]
        red = cfg["red"]
        invert = cfg["invert"]

        if invert:
            # Lower is worse  (e.g. cache hit rate, free space)
            if value <= red:
                return _COLORS["error"]
            elif value <= yellow:
                return _COLORS["warning"]
            return _COLORS["success"]
        else:
            # Higher is worse  (e.g. disk usage, fragmentation)
            if value >= red:
                return _COLORS["error"]
            elif value >= yellow:
                return _COLORS["warning"]
            return _COLORS["success"]

    def _color_code_value(self, metric_name: str, value: float) -> str:
        """Alias for ``_get_threshold_color``."""
        return self._get_threshold_color(metric_name, value)

    # ------------------------------------------------------------------ #
    #  Chart drawing
    # ------------------------------------------------------------------ #

    def _refresh_charts(self) -> None:
        """Redraw all time-series charts from current history."""
        if self._mpl_available:
            self._refresh_mpl_charts()
        else:
            self._refresh_fallback_charts()

    def _refresh_mpl_charts(self) -> None:
        """Redraw matplotlib-based charts."""
        if self._fig is None:
            return

        # Disk usage
        ax = self._axes.get("disk_usage_percentage")
        if ax is not None:
            data = list(self.metrics_history["disk_usage_percentage"])
            ax.clear()
            ax.set_facecolor(_COLORS["bg_panel"])
            ax.set_title("Disk Usage %", fontsize=8,
                         color=_COLORS["text_header"], pad=3)
            ax.tick_params(colors=_COLORS["text_secondary"], labelsize=7)
            if data:
                xs = list(range(len(data)))
                ys = [d[1] for d in data]
                ax.plot(xs, ys, color=_COLORS["accent_primary"],
                        linewidth=1.2)
                ax.set_ylim(0, 100)
            for spine in ax.spines.values():
                spine.set_color(_COLORS["border"])

        # Throughput (read + write)
        ax2 = self._axes.get("throughput")
        if ax2 is not None:
            rd = list(self.metrics_history["read_throughput"])
            wd = list(self.metrics_history["write_throughput"])
            ax2.clear()
            ax2.set_facecolor(_COLORS["bg_panel"])
            ax2.set_title("Throughput MB/s", fontsize=8,
                          color=_COLORS["text_header"], pad=3)
            ax2.tick_params(colors=_COLORS["text_secondary"], labelsize=7)
            if rd:
                xs = list(range(len(rd)))
                ax2.plot(xs, [d[1] for d in rd],
                         color=_COLORS["accent_green"], linewidth=1.2,
                         label="Read")
            if wd:
                xs = list(range(len(wd)))
                ax2.plot(xs, [d[1] for d in wd],
                         color=_COLORS["accent_orange"], linewidth=1.2,
                         label="Write")
            if rd or wd:
                ax2.legend(fontsize=6, facecolor=_COLORS["bg_panel"],
                           edgecolor=_COLORS["border"],
                           labelcolor=_COLORS["text_secondary"])
            for spine in ax2.spines.values():
                spine.set_color(_COLORS["border"])

        # Cache hit rate
        ax3 = self._axes.get("cache_hit_rate")
        if ax3 is not None:
            data = list(self.metrics_history["cache_hit_rate"])
            ax3.clear()
            ax3.set_facecolor(_COLORS["bg_panel"])
            ax3.set_title("Cache Hit %", fontsize=8,
                          color=_COLORS["text_header"], pad=3)
            ax3.tick_params(colors=_COLORS["text_secondary"], labelsize=7)
            if data:
                xs = list(range(len(data)))
                ys = [d[1] for d in data]
                ax3.plot(xs, ys, color=_COLORS["accent_blue"],
                         linewidth=1.2)
                ax3.set_ylim(0, 100)
            for spine in ax3.spines.values():
                spine.set_color(_COLORS["border"])

        try:
            self._mpl_canvas_widget.draw_idle()
        except Exception:
            pass  # canvas might not be visible yet

    def _refresh_fallback_charts(self) -> None:
        """Draw simple polyline charts on the fallback tk.Canvas."""
        if self.chart_canvas is None:
            return

        self.chart_canvas.delete("all")
        self.chart_canvas.update_idletasks()
        cw = max(self.chart_canvas.winfo_width(), 300)
        ch = max(self.chart_canvas.winfo_height(), 200)

        chart_defs = [
            ("disk_usage_percentage",    "Disk Usage %",  _COLORS["accent_primary"], 0),
            ("cache_hit_rate",           "Cache Hit %",   _COLORS["accent_blue"],    1),
            ("free_space_percentage",    "Free Space %",  _COLORS["accent_green"],   2),
        ]

        chart_h = ch // max(1, len(chart_defs))

        for key, title, color, idx in chart_defs:
            y_off = idx * chart_h
            data = list(self.metrics_history[key])

            # Title
            self.chart_canvas.create_text(
                6, y_off + 10, text=title, anchor="w",
                fill=_COLORS["text_secondary"], font=("Segoe UI", 8),
            )

            if len(data) < 2:
                continue

            max_v = max(d[1] for d in data) or 1
            min_v = min(d[1] for d in data)
            span = max_v - min_v if max_v != min_v else 1

            points = []
            px_per_pt = (cw - 20) / max(1, len(data) - 1)
            for i, (_ts, v) in enumerate(data):
                x = 10 + i * px_per_pt
                y = y_off + chart_h - 10 - ((v - min_v) / span) * (chart_h - 24)
                points.extend([x, y])

            if len(points) >= 4:
                self.chart_canvas.create_line(
                    *points, fill=color, width=1.5, smooth=True,
                )

    def _draw_chart(self, chart_name: str,
                    data: List[Tuple[float, float]]) -> None:
        """
        Draw a single time-series chart (matplotlib path).

        Args:
            chart_name: Key matching an axis in ``_axes``.
            data: List of ``(timestamp, value)`` tuples.
        """
        ax = self._axes.get(chart_name)
        if ax is None or not self._mpl_available:
            return

        ax.clear()
        ax.set_facecolor(_COLORS["bg_panel"])
        if data:
            xs = list(range(len(data)))
            ys = [d[1] for d in data]
            ax.plot(xs, ys, color=_COLORS["accent_blue"], linewidth=1.2)
        try:
            self._mpl_canvas_widget.draw_idle()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  Performance alerts
    # ------------------------------------------------------------------ #

    def add_performance_alerts(self, metrics: Optional[Dict] = None) -> None:
        """
        Check current metrics for critical conditions and display
        a coloured alert banner.

        Alert triggers:
        - Disk usage > 90%
        - Fragmentation > 60%
        - Cache hit rate < 50%

        Args:
            metrics: Pre-fetched metrics dict (fetched if None).
        """
        if metrics is None:
            metrics = self.analyzer.collect_metrics()

        alerts: List[str] = []

        disk = metrics.get("disk_usage_percentage", 0)
        if disk > 90:
            alerts.append(f"⚠ Disk usage critical: {disk:.1f}%")

        frag = metrics.get("fragmentation_percentage", 0)
        if frag > 60:
            alerts.append(f"⚠ High fragmentation: {frag:.1f}%")

        cache = metrics.get("cache_hit_rate", 100)
        if cache < 50:
            alerts.append(f"⚠ Low cache hit rate: {cache:.1f}%")

        if alerts:
            self._alert_label.configure(
                text="  |  ".join(alerts),
                bg=_COLORS["error"], fg="#ffffff",
            )
        else:
            self._alert_label.configure(
                text="✅  All systems operating normally",
                bg=_COLORS["bg_panel"], fg=_COLORS["accent_green"],
            )

    # ------------------------------------------------------------------ #
    #  Detailed metrics dialog
    # ------------------------------------------------------------------ #

    def show_detailed_metrics(self) -> None:
        """
        Open a top-level dialog with a comprehensive table of every
        available metric, historical statistics, and an export button.
        """
        metrics = self.analyzer.collect_metrics()
        throughput = self.analyzer.measure_throughput()
        iops = self.analyzer.calculate_iops()
        efficiency = self.analyzer.calculate_resource_efficiency()
        score = self.analyzer.calculate_performance_score()

        win = tk.Toplevel(self.parent_frame)
        win.title("Detailed Performance Metrics")
        win.geometry("600x520")
        win.configure(bg=_COLORS["bg_dark"])

        # Title
        tk.Label(
            win, text="  📊  Detailed Metrics",
            bg=_COLORS["bg_panel"], fg=_COLORS["text_header"],
            font=_FONT_HEADER, anchor="w",
        ).pack(fill="x", padx=0, pady=(0, 6))

        # Scrollable text area
        txt = tk.Text(
            win, wrap="word", bg=_COLORS["bg_panel"],
            fg=_COLORS["text_primary"], font=_FONT_MONO,
            relief="flat", insertbackground=_COLORS["text_primary"],
        )
        scroll = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True, padx=6, pady=4)

        lines = [
            "═══════════════════════════════════════",
            f"  Performance Score:  {score:.1f} / 100",
            "═══════════════════════════════════════",
            "",
            "── Core Metrics ──────────────────────",
        ]
        for k, v in metrics.items():
            if isinstance(v, float):
                lines.append(f"  {k:35s}  {v:.2f}")
            else:
                lines.append(f"  {k:35s}  {v}")

        lines.append("")
        lines.append("── Throughput ────────────────────────")
        for k, v in throughput.items():
            lines.append(f"  {k:35s}  {v:.2f} MB/s")

        lines.append("")
        lines.append("── IOPS ──────────────────────────────")
        for k, v in iops.items():
            lines.append(f"  {k:35s}  {v:.1f}")

        lines.append("")
        lines.append("── Resource Efficiency ───────────────")
        for k, v in efficiency.items():
            lines.append(f"  {k:35s}  {v:.1f}%")

        lines.append("")
        lines.append("── History Snapshots ─────────────────")
        lines.append(f"  Stored data points:  "
                     f"{len(self.analyzer.metrics_history)}")

        txt.insert("1.0", "\n".join(lines))
        txt.configure(state="disabled")

        # Bottom buttons
        bf = ttk.Frame(win)
        bf.pack(fill="x", padx=6, pady=6)
        ttk.Button(bf, text="Export JSON",
                   command=lambda: self._export_json(metrics, throughput,
                                                     iops, efficiency)
                   ).pack(side="left", padx=4)
        ttk.Button(bf, text="Close",
                   command=win.destroy).pack(side="right", padx=4)

    @staticmethod
    def _export_json(metrics, throughput, iops, efficiency) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        payload = {
            "metrics": metrics,
            "throughput": throughput,
            "iops": iops,
            "efficiency": efficiency,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        messagebox.showinfo("Export", f"Saved to:\n{path}")

    # ------------------------------------------------------------------ #
    #  Export / Benchmark / Reset
    # ------------------------------------------------------------------ #

    def export_metrics_report(self) -> None:
        """
        Export metrics to a user-chosen file (CSV or JSON).
        """
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[
                ("JSON", "*.json"),
                ("CSV", "*.csv"),
                ("Text", "*.txt"),
            ],
        )
        if not path:
            return

        if path.endswith(".csv") or path.endswith(".json"):
            fmt = "csv" if path.endswith(".csv") else "json"
            # Ensure current snapshot is in history
            self.analyzer.metrics_history.append(
                self.analyzer.collect_metrics())
            ok = self.analyzer.export_metrics(path, format=fmt)
            if ok:
                messagebox.showinfo("Export", f"Report saved to:\n{path}")
            else:
                messagebox.showerror("Export", "Failed to export report.")
        else:
            # Plain text report
            report = self.analyzer.generate_performance_report(
                output_format="text")
            with open(path, "w", encoding="utf-8") as f:
                f.write(report)
            messagebox.showinfo("Export", f"Report saved to:\n{path}")

    def benchmark_now(self) -> None:
        """
        Run an immediate benchmark suite and display results in a
        dialog.
        """
        # Show progress
        progress_win = tk.Toplevel(self.parent_frame)
        progress_win.title("Benchmarking…")
        progress_win.geometry("340x90")
        progress_win.configure(bg=_COLORS["bg_dark"])
        tk.Label(
            progress_win, text="⏳  Running benchmarks…",
            bg=_COLORS["bg_dark"], fg=_COLORS["text_primary"],
            font=_FONT_BODY,
        ).pack(pady=12)
        pb = ttk.Progressbar(progress_win, mode="indeterminate", length=260)
        pb.pack(pady=4)
        pb.start(15)
        progress_win.update()

        try:
            read_res = self.analyzer.benchmark_read_performance()
            write_res = self.analyzer.benchmark_write_performance()
            score = self.analyzer.calculate_performance_score()
        finally:
            progress_win.destroy()

        # Show results
        result_win = tk.Toplevel(self.parent_frame)
        result_win.title("Benchmark Results")
        result_win.geometry("500x400")
        result_win.configure(bg=_COLORS["bg_dark"])

        tk.Label(
            result_win, text="  🏆  Benchmark Results",
            bg=_COLORS["bg_panel"], fg=_COLORS["text_header"],
            font=_FONT_HEADER, anchor="w",
        ).pack(fill="x")

        txt = tk.Text(
            result_win, wrap="word", bg=_COLORS["bg_panel"],
            fg=_COLORS["text_primary"], font=_FONT_MONO,
            relief="flat",
        )
        txt.pack(fill="both", expand=True, padx=6, pady=6)

        lines = [
            f"Performance Score: {score:.1f} / 100",
            "",
            "── Read Performance ──────────────────",
        ]
        for size, val in read_res.get("sequential_read_mbps", {}).items():
            lines.append(f"  Sequential {size:>10,} B  →  {val:.1f} MB/s")
        for size, val in read_res.get("random_read_mbps", {}).items():
            lines.append(f"  Random     {size:>10,} B  →  {val:.1f} MB/s")

        lines.append("")
        lines.append("── Write Performance ─────────────────")
        for size, val in write_res.get("sequential_write_mbps", {}).items():
            lines.append(f"  Sequential {size:>10,} B  →  {val:.1f} MB/s")
        for size, val in write_res.get("random_write_mbps", {}).items():
            lines.append(f"  Random     {size:>10,} B  →  {val:.1f} MB/s")

        txt.insert("1.0", "\n".join(lines))
        txt.configure(state="disabled")

        ttk.Button(result_win, text="Close",
                   command=result_win.destroy).pack(pady=6)

    def reset_statistics(self) -> None:
        """
        Reset all metric history and counters after user confirmation.
        """
        if not messagebox.askyesno(
                "Reset Statistics",
                "Clear all stored metrics and history?\n"
                "This cannot be undone."):
            return

        # Clear local history
        for dq in self.metrics_history.values():
            dq.clear()

        # Clear analyzer history
        self.analyzer.metrics_history.clear()

        # Reset labels
        for label in self.metrics_labels.values():
            label.configure(text="—")

        # Redraw gauges
        for key, canvas in self._gauge_canvases.items():
            self._draw_gauge(canvas, 0.0, key)

        # Redraw charts
        self._refresh_charts()

        self._alert_label.configure(
            text="Statistics reset.", bg=_COLORS["bg_panel"],
            fg=_COLORS["accent_yellow"],
        )
        logger.info("Dashboard statistics reset.")

    # ------------------------------------------------------------------ #
    #  Cleanup
    # ------------------------------------------------------------------ #

    def stop(self) -> None:
        """Cancel the periodic update timer."""
        if self._after_id is not None:
            try:
                self.parent_frame.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
