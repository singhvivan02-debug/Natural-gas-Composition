"""
================================================================================
 NATURAL GAS DATA TRANSFORMATION AND COMPILATION SYSTEM
================================================================================
 Module       : charts.py
 Description  : This module encapsulates all data-visualization logic for
                the application, embedding Matplotlib figures directly
                inside Tkinter frames (via FigureCanvasTkAgg) so that the
                charts live natively inside the professional GUI rather
                than opening in separate pop-up windows.

                Two chart types are provided, matching the project
                requirements:

                    1. CompositionPieChart - a pie chart showing the
                       relative mole-percent share of every active gas
                       component, with an external legend and percentage
                       labels for clarity.

                    2. ComponentBarChart   - a horizontal bar chart
                       ranking every active component by mole percent,
                       which is easier to read than a pie chart when a
                       composition contains many trace components with
                       very small percentages.

                Each chart class also embeds a Matplotlib
                NavigationToolbar2Tk (pan/zoom/save-as-image) and exposes
                a save_figure() method used by the GUI's "Export Chart as
                Image" action.

                A shared THEME dictionary centralizes the color palette
                so that charts, tables and the rest of the GUI (gui.py)
                present a single, consistent professional visual identity.

 Author       : Semester Project
 Version      : 1.0.0
================================================================================
"""

import logging
from typing import List

import matplotlib
matplotlib.use("TkAgg")  # Ensure the Tk-compatible backend is selected before pyplot import

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from gas_data import GasComposition

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. SHARED VISUAL THEME
# ==============================================================================
# These colors are also referenced by gui.py so that the Tkinter widgets
# (backgrounds, headers, buttons) and the Matplotlib charts share one
# consistent, professional "engineering software" color identity.
THEME = {
    "bg_dark": "#0F2A3F",          # Deep navy - primary brand background
    "bg_panel": "#16374F",         # Slightly lighter navy - panel backgrounds
    "accent_teal": "#1F9D8C",      # Primary accent (buttons, highlights)
    "accent_light": "#8FD9CC",     # Secondary accent (hover, subtitles)
    "text_light": "#F2F6F7",       # Primary text on dark backgrounds
    "text_muted": "#B7C9D3",       # Secondary/muted text
    "grid_line": "#3A5568",        # Chart gridlines
    "chart_bg": "#FFFFFF",         # Chart plotting area background
    "warning": "#E0A32E",
    "danger": "#D14848",
    "success": "#2FA86B",
}

# A distinct, professional qualitative palette (15 colors) used to color
# each gas component consistently across BOTH the pie chart and the bar
# chart, so a component is always the same color no matter which chart
# the user is looking at.
COMPONENT_COLOR_PALETTE = [
    "#1F9D8C",  # teal        - Methane (typically the largest slice)
    "#2E86AB",  # blue
    "#F4A259",  # orange
    "#BC4B51",  # brick red
    "#8CB369",  # olive green
    "#5B5F97",  # indigo
    "#F4E285",  # gold
    "#B185A7",  # mauve
    "#3D5A80",  # slate blue
    "#EE6C4D",  # coral
    "#98C1D9",  # sky blue
    "#6D6875",  # muted plum
    "#7A9E7E",  # sage
    "#E4C1F9",  # lilac
    "#A0522D",  # sienna
]


def get_component_colors(names: List[str]) -> List[str]:
    """
    Returns a consistent color for each named component by hashing the
    component's fixed position in the palette list (cycling if there are
    more components than palette entries). Using the name's index in the
    reference library (rather than random assignment) guarantees the same
    component always renders in the same color across chart refreshes.
    """
    from gas_data import get_component_names
    reference_order = get_component_names()
    colors = []
    for name in names:
        if name in reference_order:
            idx = reference_order.index(name)
        else:
            idx = hash(name) % len(COMPONENT_COLOR_PALETTE)
        colors.append(COMPONENT_COLOR_PALETTE[idx % len(COMPONENT_COLOR_PALETTE)])
    return colors


def apply_professional_style():
    """
    Configures global Matplotlib rcParams once at import time so that
    every figure created by this module shares a clean, professional
    "engineering report" appearance (subtle grid, no top/right spines,
    consistent font).
    """
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
        "font.size": 9,
        "axes.edgecolor": THEME["grid_line"],
        "axes.labelcolor": "#33414D",
        "axes.grid": True,
        "grid.color": "#E3E9EC",
        "grid.linewidth": 0.7,
        "figure.facecolor": THEME["chart_bg"],
        "axes.facecolor": THEME["chart_bg"],
        "text.color": "#22303A",
        "xtick.color": "#33414D",
        "ytick.color": "#33414D",
    })


apply_professional_style()


# ==============================================================================
# 2. BASE CHART PANEL
# ==============================================================================
class _BaseChartPanel:
    """
    Shared plumbing for embedding a Matplotlib Figure inside a Tkinter
    frame, including the navigation toolbar and a save-to-file method.
    Both CompositionPieChart and ComponentBarChart inherit from this.
    """

    def __init__(self, parent, figsize=(6.4, 4.6), dpi=100, show_toolbar=True):
        self.parent = parent
        self.figure = Figure(figsize=figsize, dpi=dpi, facecolor=THEME["chart_bg"])
        self.axes = self.figure.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(side="top", fill="both", expand=True)

        self.toolbar = None
        if show_toolbar:
            toolbar_frame = None
            import tkinter as tk
            toolbar_frame = tk.Frame(parent, bg=THEME["chart_bg"])
            toolbar_frame.pack(side="bottom", fill="x")
            self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
            self.toolbar.update()

        self._draw_empty_state("No composition data to display.\n"
                                "Enter or import gas composition data to see this chart.")

    # ------------------------------------------------------------------ #
    def _draw_empty_state(self, message: str):
        """Clears the axes and displays a centered placeholder message."""
        self.axes.clear()
        self.axes.axis("off")
        self.axes.text(
            0.5, 0.5, message,
            ha="center", va="center",
            fontsize=10, color=THEME["text_muted"],
            wrap=True, transform=self.axes.transAxes,
        )
        self.canvas.draw_idle()

    # ------------------------------------------------------------------ #
    def save_figure(self, filepath: str, dpi: int = 300):
        """
        Saves the current figure to disk as a high-resolution PNG (or any
        format inferred from the file extension), used by the GUI's
        'Export Chart as Image' menu action.
        """
        try:
            self.figure.savefig(filepath, dpi=dpi, bbox_inches="tight",
                                 facecolor=self.figure.get_facecolor())
            logger.info("Chart saved to: %s", filepath)
            return True
        except Exception as exc:
            logger.error("Failed to save chart to '%s': %s", filepath, exc)
            return False

    # ------------------------------------------------------------------ #
    def clear(self):
        """Resets the chart back to its empty placeholder state."""
        self._draw_empty_state("No composition data to display.\n"
                                "Enter or import gas composition data to see this chart.")


# ==============================================================================
# 3. PIE CHART — GAS COMPOSITION BREAKDOWN
# ==============================================================================
class CompositionPieChart(_BaseChartPanel):
    """
    Renders the mole-percent composition of a GasComposition as a
    professional donut-style pie chart, with:
        - a wedge per active component, colored consistently via
          get_component_colors()
        - percentage labels shown directly on wedges above a configurable
          minimum size threshold (to avoid label clutter for trace gases)
        - an external legend listing every active component and its
          exact mole percent
    """

    MIN_LABEL_PERCENT = 3.0  # wedges smaller than this show no inline label

    def update_chart(self, composition: GasComposition, title: str = "Gas Composition (Mole %)"):
        active = sorted(composition.active_components(), key=lambda c: c.mole_percent, reverse=True)

        self.axes.clear()

        if not active:
            self._draw_empty_state("No active components (all mole percents are 0%).\n"
                                    "Enter composition data to generate the pie chart.")
            return

        self.axes.axis("on")
        labels = [c.name for c in active]
        sizes = [c.mole_percent for c in active]
        colors = get_component_colors(labels)

        def autopct_format(pct):
            return f"{pct:.1f}%" if pct >= self.MIN_LABEL_PERCENT else ""

        wedges, _texts, _autotexts = self.axes.pie(
            sizes,
            colors=colors,
            autopct=autopct_format,
            pctdistance=0.78,
            startangle=90,
            counterclock=False,
            wedgeprops={"width": 0.45, "edgecolor": THEME["chart_bg"], "linewidth": 1.5},
            textprops={"fontsize": 9, "fontweight": "bold", "color": "#1B2530"},
        )

        self.axes.set_title(title, fontsize=12, fontweight="bold", color="#1B2530", pad=14)

        legend_labels = [f"{c.name}  —  {c.mole_percent:.2f}%" for c in active]
        self.axes.legend(
            wedges, legend_labels,
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            fontsize=8,
            frameon=False,
            title="Components",
            title_fontsize=9,
        )

        self.axes.set_aspect("equal")
        self.figure.subplots_adjust(right=0.62)
        self.canvas.draw_idle()


# ==============================================================================
# 4. BAR CHART — COMPONENT RANKING
# ==============================================================================
class ComponentBarChart(_BaseChartPanel):
    """
    Renders a horizontal bar chart ranking each active component by mole
    percent (largest at top). A horizontal orientation is used because
    natural gas component names ("iso-Pentane", "Hydrogen Sulfide", etc.)
    are long and remain readable without rotation, unlike a vertical bar
    chart with crowded x-axis labels.
    """

    def update_chart(self, composition: GasComposition, title: str = "Component Mole Percent Ranking"):
        active = sorted(composition.active_components(), key=lambda c: c.mole_percent, reverse=True)

        self.axes.clear()

        if not active:
            self._draw_empty_state("No active components (all mole percents are 0%).\n"
                                    "Enter composition data to generate the bar chart.")
            return

        self.axes.axis("on")
        names = [c.name for c in active]
        values = [c.mole_percent for c in active]
        colors = get_component_colors(names)

        y_positions = list(range(len(names)))
        bars = self.axes.barh(y_positions, values, color=colors,
                               edgecolor="#FFFFFF", linewidth=0.6, height=0.65)

        self.axes.set_yticks(y_positions)
        self.axes.set_yticklabels(names, fontsize=9)
        self.axes.invert_yaxis()  # largest component at the top
        self.axes.set_xlabel("Mole Percent (%)", fontsize=9, fontweight="bold")
        self.axes.set_title(title, fontsize=12, fontweight="bold", color="#1B2530", pad=12)
        self.axes.grid(axis="x", linestyle="--", alpha=0.6)
        self.axes.grid(axis="y", visible=False)

        max_value = max(values) if values else 1.0
        for bar, value in zip(bars, values):
            self.axes.text(
                bar.get_width() + max_value * 0.015,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.2f}%",
                va="center", ha="left", fontsize=8, color="#1B2530", fontweight="bold",
            )

        self.axes.set_xlim(0, max_value * 1.18)
        self.figure.subplots_adjust(left=0.28, right=0.95, top=0.90, bottom=0.12)
        self.canvas.draw_idle()
