"""
================================================================================
 NATURAL GAS DATA TRANSFORMATION AND COMPILATION SYSTEM
================================================================================
 Module       : gui.py
 Description  : This module implements the complete Tkinter graphical
                user interface of the application, and is the module
                that ties together every other component of the project:

                    - gas_data.py     : the component library, the
                                         GasComposition data model, and
                                         all validation logic
                    - calculations.py : the engineering calculation
                                         engine (MW, SG, Heating Value,
                                         Z-factor, Density)
                    - charts.py       : the embedded Matplotlib pie
                                         chart and bar chart panels
                    - file_handler.py : CSV import / export / template
                                         generation

                The interface is organized as follows:

                    - A dark navy header banner (title, version, org).
                    - A quick-action toolbar for the most common tasks.
                    - A left panel containing:
                        * an editable Gas Composition Table (double-click
                          any Mole % cell to edit, or use the Quick Entry
                          form)
                        * Operating Conditions inputs (pressure /
                          temperature) that drive the density and
                          Z-factor calculations
                        * Sample / Report metadata fields
                    - A right panel containing:
                        * a row of headline "result cards" (MW, SG, HV,
                          Z-factor, Density)
                        * a detailed results table
                        * a tabbed notebook holding the Pie Chart and Bar
                          Chart views
                    - A status bar reporting live composition validity.

 Author       : Semester Project
 Version      : 1.0.0
================================================================================
"""

import logging
import os
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import gas_data
from gas_data import GasComposition, validate_composition, validate_mole_percent_input
from calculations import GasCalculator, CalculationResults
from charts import CompositionPieChart, ComponentBarChart, THEME
import file_handler as fh

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. HEADLINE RESULT-CARD DEFINITIONS
# ==============================================================================
# Each tuple: (card_title, results_attribute, format_string, unit_suffix)
HEADLINE_CARDS = [
    ("Mol. Weight", "apparent_molecular_weight", "{:.3f}", "lb/lb-mol"),
    ("Spec. Gravity", "specific_gravity", "{:.4f}", "(air = 1.0)"),
    ("Heating Value", "gross_heating_value_btu_scf", "{:.1f}", "Btu/scf"),
    ("Z-Factor", "compressibility_factor_z", "{:.4f}", "dimensionless"),
    ("Gas Density", "gas_density_real_lb_ft3", "{:.4f}", "lb/ft³"),
]


# ==============================================================================
# 2. MAIN APPLICATION CLASS
# ==============================================================================
class NaturalGasApp:
    """
    The root controller class for the entire GUI. Constructed once by
    main.py with the already-created (but hidden) Tk root window.
    """

    def __init__(self, root: tk.Tk, app_name: str = "Natural Gas Data System",
                 app_version: str = "1.0.0"):
        self.root = root
        self.app_name = app_name
        self.app_version = app_version

        # --- Application state ---
        self.composition: GasComposition = gas_data.build_default_composition(use_sample_values=True)
        self.results: CalculationResults = None

        self.pressure_var = tk.StringVar(value="14.696")
        self.temperature_var = tk.StringVar(value="60.0")
        self.sample_id_var = tk.StringVar(value="")
        self.operator_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready.")
        self.total_percent_var = tk.StringVar(value="Total: 0.00 %")
        self.quick_component_var = tk.StringVar()
        self.quick_value_var = tk.StringVar()

        self.card_value_vars = {key: tk.StringVar(value="—") for _, key, _, _ in HEADLINE_CARDS}

        self._configure_styles()
        self._build_menu()
        self._build_layout()

        self._refresh_table()
        self._recalculate(silent=True)

        logger.info("NaturalGasApp GUI constructed and ready.")

    # ==================================================================== #
    # 2.1 STYLE CONFIGURATION
    # ==================================================================== #
    def _configure_styles(self):
        """
        Configures a consistent, professional visual theme across every
        ttk widget in the application, matching the color palette defined
        in charts.py (THEME) so the GUI and the embedded charts feel like
        a single cohesive product.
        """
        self.root.configure(bg="#EEF2F4")

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass  # fall back to the platform default theme silently

        style.configure("TFrame", background="#EEF2F4")
        style.configure("Card.TFrame", background="#FFFFFF", relief="flat")
        style.configure("Panel.TFrame", background="#FFFFFF")

        style.configure("TLabelframe", background="#FFFFFF", bordercolor=THEME["grid_line"])
        style.configure("TLabelframe.Label", background="#FFFFFF",
                         foreground=THEME["bg_dark"], font=("Segoe UI", 10, "bold"))

        style.configure("TLabel", background="#FFFFFF", foreground="#22303A",
                         font=("Segoe UI", 9))
        style.configure("Header.TLabel", background=THEME["bg_dark"],
                         foreground="#FFFFFF", font=("Segoe UI", 9))
        style.configure("Status.TLabel", background="#DCE4E8", foreground="#22303A",
                         font=("Segoe UI", 9))
        style.configure("CardTitle.TLabel", background="#FFFFFF", foreground=THEME["text_muted"],
                         font=("Segoe UI", 9, "bold"))
        style.configure("CardValue.TLabel", background="#FFFFFF", foreground=THEME["bg_dark"],
                         font=("Segoe UI", 17, "bold"))
        style.configure("CardUnit.TLabel", background="#FFFFFF", foreground=THEME["text_muted"],
                         font=("Segoe UI", 8))

        style.configure("TButton", font=("Segoe UI", 9), padding=6)
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"), padding=7,
                         foreground="#FFFFFF", background=THEME["accent_teal"])
        style.map("Accent.TButton",
                  background=[("active", THEME["accent_light"]), ("pressed", "#17786B")],
                  foreground=[("active", "#0F2A3F")])

        style.configure("Toolbar.TButton", font=("Segoe UI", 9), padding=6)

        style.configure("Treeview", background="#FFFFFF", fieldbackground="#FFFFFF",
                         foreground="#22303A", rowheight=25, font=("Segoe UI", 9),
                         borderwidth=0)
        style.configure("Treeview.Heading", background=THEME["bg_dark"], foreground="#FFFFFF",
                         font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Treeview.Heading", background=[("active", THEME["bg_panel"])])
        style.map("Treeview", background=[("selected", THEME["accent_teal"])],
                  foreground=[("selected", "#FFFFFF")])

        style.configure("TNotebook", background="#EEF2F4", borderwidth=0)
        style.configure("TNotebook.Tab", background="#DCE4E8", foreground="#22303A",
                         font=("Segoe UI", 9, "bold"), padding=(14, 7))
        style.map("TNotebook.Tab", background=[("selected", "#FFFFFF")],
                  foreground=[("selected", THEME["bg_dark"])])

        style.configure("TEntry", padding=4)
        style.configure("TCombobox", padding=4)

    # ==================================================================== #
    # 2.2 MENU BAR
    # ==================================================================== #
    def _build_menu(self):
        menubar = tk.Menu(self.root)

        # --- File menu ---
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New / Blank Composition", command=self._on_new_blank)
        file_menu.add_command(label="Load Sample Composition", command=self._on_load_sample)
        file_menu.add_separator()
        file_menu.add_command(label="Import Composition from CSV...", command=self._on_import_csv)
        file_menu.add_command(label="Generate CSV Import Template...", command=self._on_generate_template)
        file_menu.add_separator()
        file_menu.add_command(label="Export Composition to CSV...", command=self._on_export_composition)
        file_menu.add_command(label="Export Full Report to CSV...", command=self._on_export_report)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_exit)
        menubar.add_cascade(label="File", menu=file_menu)

        # --- Edit menu ---
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Normalize Composition to 100%", command=self._on_normalize)
        edit_menu.add_command(label="Clear All Values", command=self._on_clear_all)
        edit_menu.add_separator()
        edit_menu.add_command(label="Recalculate Now", command=lambda: self._recalculate(silent=False))
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # --- View menu ---
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Run Data Validation Report...", command=self._on_validate)
        menubar.add_cascade(label="View", menu=view_menu)

        # --- Help menu ---
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._on_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    # ==================================================================== #
    # 2.3 OVERALL LAYOUT
    # ==================================================================== #
    def _build_layout(self):
        self._build_header()
        self._build_toolbar()

        # Status bar is packed BEFORE the body so it always keeps its
        # space at the bottom even when the window is small.
        self._build_status_bar()

        body = ttk.Frame(self.root)
        body.pack(side="top", fill="both", expand=True, padx=10, pady=(4, 4))

        paned = ttk.PanedWindow(body, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left_panel = ttk.Frame(paned)
        right_panel = ttk.Frame(paned)
        paned.add(left_panel, weight=2)
        paned.add(right_panel, weight=3)

        self._build_composition_panel(left_panel)
        self._build_conditions_panel(left_panel)

        self._build_results_panel(right_panel)
        self._build_charts_panel(right_panel)

    # ------------------------------------------------------------------ #
    def _build_header(self):
        header = tk.Frame(self.root, bg=THEME["bg_dark"], height=64)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        accent_bar = tk.Frame(header, bg=THEME["accent_teal"], height=4)
        accent_bar.pack(side="bottom", fill="x")

        title_frame = tk.Frame(header, bg=THEME["bg_dark"])
        title_frame.pack(side="left", padx=18, pady=6)

        tk.Label(title_frame, text="⛽", font=("Segoe UI", 22), bg=THEME["bg_dark"],
                  fg=THEME["accent_teal"]).pack(side="left", padx=(0, 10))

        text_frame = tk.Frame(title_frame, bg=THEME["bg_dark"])
        text_frame.pack(side="left")
        tk.Label(text_frame, text=self.app_name, font=("Segoe UI", 14, "bold"),
                  bg=THEME["bg_dark"], fg="#FFFFFF", anchor="w").pack(anchor="w")
        tk.Label(text_frame, text="Composition Analysis  •  MW  •  Specific Gravity  •  "
                                    "Heating Value  •  Density",
                  font=("Segoe UI", 9), bg=THEME["bg_dark"], fg=THEME["text_muted"],
                  anchor="w").pack(anchor="w")

        version_label = tk.Label(header, text=f"v{self.app_version}",
                                   font=("Segoe UI", 9), bg=THEME["bg_dark"],
                                   fg=THEME["text_muted"])
        version_label.pack(side="right", padx=18)

    # ------------------------------------------------------------------ #
    def _build_toolbar(self):
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side="top", fill="x", padx=10, pady=6)

        ttk.Button(toolbar, text="📂 Import CSV", style="Toolbar.TButton",
                   command=self._on_import_csv).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="💾 Export Composition", style="Toolbar.TButton",
                   command=self._on_export_composition).pack(side="left", padx=6)
        ttk.Button(toolbar, text="📊 Export Full Report", style="Toolbar.TButton",
                   command=self._on_export_report).pack(side="left", padx=6)
        ttk.Button(toolbar, text="🧪 Load Sample Data", style="Toolbar.TButton",
                   command=self._on_load_sample).pack(side="left", padx=6)
        ttk.Button(toolbar, text="⚖ Normalize to 100%", style="Toolbar.TButton",
                   command=self._on_normalize).pack(side="left", padx=6)
        ttk.Button(toolbar, text="✔ Validate", style="Toolbar.TButton",
                   command=self._on_validate).pack(side="left", padx=6)
        ttk.Button(toolbar, text="⟳ Recalculate", style="Accent.TButton",
                   command=lambda: self._recalculate(silent=False)).pack(side="right")

    # ==================================================================== #
    # 2.4 LEFT PANEL — COMPOSITION TABLE
    # ==================================================================== #
    def _build_composition_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="  Gas Composition Table  (double-click Mole % to edit)  ")
        frame.pack(side="top", fill="both", expand=True, padx=(0, 6), pady=(0, 6))

        table_container = ttk.Frame(frame)
        table_container.pack(side="top", fill="both", expand=True, padx=8, pady=8)

        columns = ("mole", "mw", "ghv")
        self.tree = ttk.Treeview(table_container, columns=columns, show="tree headings", height=9)
        self.tree.heading("#0", text="Component")
        self.tree.column("#0", width=170, anchor="w", stretch=True)
        self.tree.heading("mole", text="Mole (%)")
        self.tree.column("mole", width=85, anchor="center", stretch=False)
        self.tree.heading("mw", text="MW (lb/lb-mol)")
        self.tree.column("mw", width=110, anchor="center", stretch=False)
        self.tree.heading("ghv", text="GHV (Btu/scf)")
        self.tree.column("ghv", width=105, anchor="center", stretch=False)

        v_scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # --- Quick Entry form ---
        quick_frame = ttk.Frame(frame)
        quick_frame.pack(side="top", fill="x", padx=8, pady=(0, 4))

        ttk.Label(quick_frame, text="Quick Entry:").pack(side="left", padx=(0, 6))
        self.quick_component_combo = ttk.Combobox(
            quick_frame, textvariable=self.quick_component_var,
            values=gas_data.get_component_names(), state="readonly", width=20
        )
        self.quick_component_combo.pack(side="left", padx=(0, 6))
        if gas_data.get_component_names():
            self.quick_component_combo.current(0)

        ttk.Entry(quick_frame, textvariable=self.quick_value_var, width=10,
                  justify="center").pack(side="left", padx=(0, 6))
        ttk.Label(quick_frame, text="mol %").pack(side="left", padx=(0, 10))
        ttk.Button(quick_frame, text="Set Value", command=self._on_quick_set).pack(side="left")

        # --- Total row ---
        total_frame = ttk.Frame(frame)
        total_frame.pack(side="top", fill="x", padx=8, pady=(0, 8))
        self.total_label = ttk.Label(total_frame, textvariable=self.total_percent_var,
                                       font=("Segoe UI", 10, "bold"))
        self.total_label.pack(side="left")

    # ------------------------------------------------------------------ #
    def _on_tree_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id or column != "#1":  # only the "mole" column (#1) is editable
            return

        bbox = self.tree.bbox(row_id, column)
        if not bbox:
            return
        x, y, width, height = bbox

        current_value = self.tree.set(row_id, "mole")
        edit_var = tk.StringVar(value=current_value)
        entry = ttk.Entry(self.tree, textvariable=edit_var, justify="center")
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus()
        entry.select_range(0, tk.END)

        def commit(_event=None):
            if not entry.winfo_exists():
                return
            raw_value = edit_var.get()
            is_valid, parsed_value, error_msg = validate_mole_percent_input(raw_value)
            entry.destroy()
            if not is_valid:
                messagebox.showerror("Invalid Entry", error_msg)
                return
            self.composition.set_mole_percent(row_id, parsed_value)
            self._refresh_table()
            self._recalculate(silent=True)
            self._set_status(f"Updated '{row_id}' to {parsed_value:.3f} mol %.")

        def cancel(_event=None):
            if entry.winfo_exists():
                entry.destroy()

        entry.bind("<Return>", commit)
        entry.bind("<KP_Enter>", commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>", cancel)

    # ------------------------------------------------------------------ #
    def _on_quick_set(self):
        name = self.quick_component_var.get()
        raw_value = self.quick_value_var.get()
        if not name:
            messagebox.showwarning("Quick Entry", "Please select a component first.")
            return

        is_valid, parsed_value, error_msg = validate_mole_percent_input(raw_value)
        if not is_valid:
            messagebox.showerror("Invalid Entry", error_msg)
            return

        self.composition.set_mole_percent(name, parsed_value)
        self._refresh_table()
        self._recalculate(silent=True)
        self._set_status(f"Updated '{name}' to {parsed_value:.3f} mol % via Quick Entry.")
        self.quick_value_var.set("")

    # ------------------------------------------------------------------ #
    def _refresh_table(self):
        """Repopulates the Treeview from the current self.composition state."""
        self.tree.delete(*self.tree.get_children())
        for comp in self.composition.components:
            self.tree.insert(
                "", "end", iid=comp.name, text=comp.name,
                values=(f"{comp.mole_percent:.3f}", f"{comp.molecular_weight:.3f}",
                        f"{comp.gross_heating_value:.1f}")
            )

        # Keep the Quick Entry dropdown in sync with whatever components
        # currently exist in the composition (including any custom ones
        # that arrived via CSV import).
        names = [c.name for c in self.composition.components]
        self.quick_component_combo.configure(values=names)

        total = self.composition.total_mole_percent()
        self.total_percent_var.set(f"Total: {total:.3f} %")
        if abs(total - 100.0) <= gas_data.COMPOSITION_SUM_TOLERANCE:
            self.total_label.configure(foreground=THEME["success"])
        else:
            self.total_label.configure(foreground=THEME["danger"])

    # ==================================================================== #
    # 2.5 LEFT PANEL — OPERATING CONDITIONS
    # ==================================================================== #
    def _build_conditions_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="  Operating Conditions & Sample Information  ")
        frame.pack(side="top", fill="x", padx=(0, 6), pady=(0, 6))

        grid = ttk.Frame(frame)
        grid.pack(fill="x", padx=8, pady=8)

        ttk.Label(grid, text="Pressure (psia):").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        pressure_entry = ttk.Entry(grid, textvariable=self.pressure_var, width=12)
        pressure_entry.grid(row=0, column=1, sticky="w", pady=4)
        pressure_entry.bind("<Return>", lambda e: self._recalculate(silent=False))

        ttk.Label(grid, text="Temperature (°F):").grid(row=0, column=2, sticky="w", padx=(18, 6), pady=4)
        temp_entry = ttk.Entry(grid, textvariable=self.temperature_var, width=12)
        temp_entry.grid(row=0, column=3, sticky="w", pady=4)
        temp_entry.bind("<Return>", lambda e: self._recalculate(silent=False))

        ttk.Label(grid, text="(Standard conditions: 14.696 psia, 60 °F)",
                  style="CardUnit.TLabel").grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 4))

        # --- Sample / report metadata (used in the exported report) ---
        ttk.Label(grid, text="Sample ID:").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(grid, textvariable=self.sample_id_var, width=12).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(grid, text="Operator:").grid(row=2, column=2, sticky="w", padx=(18, 6), pady=4)
        ttk.Entry(grid, textvariable=self.operator_var, width=12).grid(row=2, column=3, sticky="w", pady=4)

    # ==================================================================== #
    # 2.6 LEFT PANEL — SAMPLE / REPORT METADATA
    # ==================================================================== #
    def _build_metadata_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="  Sample & Report Information  ")
        frame.pack(side="top", fill="x", padx=(0, 6), pady=(0, 6))

        grid = ttk.Frame(frame)
        grid.pack(fill="x", padx=8, pady=8)

        ttk.Label(grid, text="Sample ID:").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(grid, textvariable=self.sample_id_var, width=20).grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(grid, text="Operator / Engineer:").grid(row=0, column=2, sticky="w", padx=(18, 6), pady=4)
        ttk.Entry(grid, textvariable=self.operator_var, width=20).grid(row=0, column=3, sticky="w", pady=4)

    # ==================================================================== #
    # 2.7 RIGHT PANEL — RESULTS (headline cards + detailed table)
    # ==================================================================== #
    def _build_results_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="  Calculated Engineering Results  ")
        frame.pack(side="top", fill="x", padx=(6, 0), pady=(0, 6))

        cards_frame = ttk.Frame(frame)
        cards_frame.pack(side="top", fill="x", padx=8, pady=8)

        self.card_widgets = {}
        for i, (title, key, fmt, unit) in enumerate(HEADLINE_CARDS):
            card = tk.Frame(cards_frame, bg="#FFFFFF", highlightbackground=THEME["grid_line"],
                             highlightthickness=1, bd=0)
            card.grid(row=0, column=i, padx=4, sticky="nsew")
            cards_frame.grid_columnconfigure(i, weight=1)

            accent = tk.Frame(card, bg=THEME["accent_teal"], height=3)
            accent.pack(side="top", fill="x")

            ttk.Label(card, text=title, style="CardTitle.TLabel",
                      background="#FFFFFF").pack(side="top", anchor="w", padx=10, pady=(8, 0))
            value_label = ttk.Label(card, textvariable=self.card_value_vars[key],
                                      style="CardValue.TLabel", background="#FFFFFF")
            value_label.pack(side="top", anchor="w", padx=10)
            ttk.Label(card, text=unit, style="CardUnit.TLabel",
                      background="#FFFFFF").pack(side="top", anchor="w", padx=10, pady=(0, 10))

            self.card_widgets[key] = (card, value_label)

        # --- Detailed results table ---
        detail_frame = ttk.Frame(frame)
        detail_frame.pack(side="top", fill="both", expand=True, padx=8, pady=(0, 8))

        self.results_tree = ttk.Treeview(detail_frame, columns=("value",), show="tree headings", height=4)
        self.results_tree.heading("#0", text="Property")
        self.results_tree.column("#0", width=280, anchor="w")
        self.results_tree.heading("value", text="Value")
        self.results_tree.column("value", width=160, anchor="center")

        results_scroll = ttk.Scrollbar(detail_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=results_scroll.set)
        self.results_tree.pack(side="left", fill="both", expand=True)
        results_scroll.pack(side="right", fill="y")

    # ==================================================================== #
    # 2.8 RIGHT PANEL — CHARTS NOTEBOOK
    # ==================================================================== #
    def _build_charts_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="  Visualizations  ")
        frame.pack(side="top", fill="both", expand=True, padx=(6, 0), pady=(0, 0))

        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        pie_tab = ttk.Frame(notebook)
        bar_tab = ttk.Frame(notebook)
        notebook.add(pie_tab, text="  🥧  Composition Pie Chart  ")
        notebook.add(bar_tab, text="  📶  Component Bar Chart  ")

        self.pie_chart = CompositionPieChart(pie_tab)
        self.bar_chart = ComponentBarChart(bar_tab)

    # ==================================================================== #
    # 2.9 STATUS BAR
    # ==================================================================== #
    def _build_status_bar(self):
        status_bar = ttk.Frame(self.root, style="Panel.TFrame")
        status_bar.pack(side="bottom", fill="x")

        status_label = ttk.Label(status_bar, textvariable=self.status_var, style="Status.TLabel",
                                   anchor="w", padding=(10, 4))
        status_label.pack(side="left", fill="x", expand=True)

        clock_label = ttk.Label(status_bar, text=datetime.now().strftime("%Y-%m-%d"),
                                  style="Status.TLabel", anchor="e", padding=(10, 4))
        clock_label.pack(side="right")

    def _set_status(self, message: str):
        self.status_var.set(message)

    # ==================================================================== #
    # 3. CALCULATION PIPELINE
    # ==================================================================== #
    def _recalculate(self, silent: bool = False):
        """
        Re-runs the full engineering calculation pipeline against the
        current composition and operating conditions, then refreshes the
        headline cards, the detailed results table, and both charts.

        If silent is False, validation issues are surfaced to the user
        via a message box; if True (used after every small table edit),
        validation issues are only reflected quietly in the status bar so
        typing is not constantly interrupted by pop-ups.
        """
        try:
            pressure = float(self.pressure_var.get())
            temperature = float(self.temperature_var.get())
        except ValueError:
            self._set_status("⚠ Invalid pressure or temperature value — using last valid conditions.")
            if not silent:
                messagebox.showerror("Invalid Operating Conditions",
                                      "Pressure and Temperature must both be numeric values.")
            return

        if pressure <= 0:
            self._set_status("⚠ Pressure must be greater than zero.")
            if not silent:
                messagebox.showerror("Invalid Operating Conditions", "Pressure must be greater than zero (psia).")
            return

        validation = validate_composition(self.composition)

        calculator = GasCalculator(self.composition, pressure_psia=pressure, temperature_f=temperature)
        self.results = calculator.compute_all()

        self._update_headline_cards()
        self._update_detailed_results_table()
        self.pie_chart.update_chart(self.composition)
        self.bar_chart.update_chart(self.composition)

        if validation.is_valid:
            self._set_status(f"✔ Composition valid (Total = {self.composition.total_mole_percent():.2f}%). "
                              f"Results updated at {datetime.now().strftime('%H:%M:%S')}.")
        else:
            self._set_status(f"⚠ Composition has validation issues — results shown are AS-ENTERED. "
                              f"Use 'Validate' for details.")
            if not silent:
                messagebox.showwarning(
                    "Composition Validation Warning",
                    validation.message + "\n\n" + "\n".join(f"• {issue}" for issue in validation.issues)
                )

        for warning_text in self.results.warnings:
            logger.warning(warning_text)

    def _update_headline_cards(self):
        for _, key, fmt, _ in HEADLINE_CARDS:
            value = getattr(self.results, key)
            self.card_value_vars[key].set(fmt.format(value))

    def _update_detailed_results_table(self):
        self.results_tree.delete(*self.results_tree.get_children())
        for label, value in self.results.as_flat_dict().items():
            self.results_tree.insert("", "end", text=label, values=(value,))

    # ==================================================================== #
    # 4. MENU / TOOLBAR ACTION HANDLERS
    # ==================================================================== #
    def _on_new_blank(self):
        if not messagebox.askyesno("New Blank Composition",
                                    "This will clear all current composition data (set every "
                                    "component to 0%). Continue?"):
            return
        self.composition = gas_data.build_default_composition(use_sample_values=False)
        self._refresh_table()
        self._recalculate(silent=True)
        self._set_status("Started a new blank composition.")

    def _on_load_sample(self):
        if not messagebox.askyesno("Load Sample Composition",
                                    "This will replace the current composition with a typical "
                                    "pipeline-quality sample dataset. Continue?"):
            return
        self.composition = gas_data.build_default_composition(use_sample_values=True)
        self._refresh_table()
        self._recalculate(silent=True)
        self._set_status("Loaded the sample gas composition.")

    def _on_normalize(self):
        total_before = self.composition.total_mole_percent()
        if total_before <= 0:
            messagebox.showwarning("Normalize", "Cannot normalize a composition that totals 0%.")
            return
        self.composition.normalize_to_100()
        self._refresh_table()
        self._recalculate(silent=True)
        self._set_status(f"Normalized composition from {total_before:.2f}% to 100.00%.")

    def _on_clear_all(self):
        if not messagebox.askyesno("Clear All Values", "Set every component's mole percent to 0%?"):
            return
        for comp in self.composition.components:
            comp.mole_percent = 0.0
        self._refresh_table()
        self._recalculate(silent=True)
        self._set_status("Cleared all composition values.")

    def _on_validate(self):
        result = validate_composition(self.composition, require_exact_100=False)
        if result.is_valid:
            messagebox.showinfo("Data Validation Report", result.message)
        else:
            detail = result.message + "\n\n" + "\n".join(f"• {issue}" for issue in result.issues)
            messagebox.showwarning("Data Validation Report", detail)
        self._set_status(result.message)

    # ------------------------------------------------------------------ #
    def _on_import_csv(self):
        filepath = filedialog.askopenfilename(
            title="Import Gas Composition from CSV",
            filetypes=fh.CSV_FILETYPES,
        )
        if not filepath:
            return

        result = fh.import_composition_from_csv(filepath)
        if not result.success:
            messagebox.showerror("Import Failed", result.error_message)
            self._set_status("Import failed — see error dialog.")
            return

        self.composition = result.composition
        self._refresh_table()
        self._recalculate(silent=True)

        message = f"Successfully imported {result.rows_read} row(s) from:\n{os.path.basename(filepath)}"
        if result.warnings:
            message += "\n\nNotes:\n" + "\n".join(f"• {w}" for w in result.warnings)
            messagebox.showwarning("Import Completed with Notes", message)
        else:
            messagebox.showinfo("Import Successful", message)

        self._set_status(f"Imported composition from '{os.path.basename(filepath)}'.")

    def _on_generate_template(self):
        filepath = filedialog.asksaveasfilename(
            title="Save CSV Import Template",
            defaultextension=".csv",
            initialfile="gas_composition_template.csv",
            filetypes=fh.CSV_FILETYPES,
        )
        if not filepath:
            return

        result = fh.generate_import_template_csv(filepath)
        if result.success:
            messagebox.showinfo("Template Created",
                                 f"A blank import template was saved to:\n{filepath}")
            self._set_status("CSV import template generated.")
        else:
            messagebox.showerror("Template Creation Failed", result.error_message)

    def _on_export_composition(self):
        filepath = filedialog.asksaveasfilename(
            title="Export Gas Composition to CSV",
            defaultextension=".csv",
            initialfile=fh.timestamped_filename("gas_composition"),
            filetypes=fh.CSV_FILETYPES,
        )
        if not filepath:
            return

        result = fh.export_composition_to_csv(self.composition, filepath)
        if result.success:
            messagebox.showinfo("Export Successful", f"Composition exported to:\n{filepath}")
            self._set_status(f"Composition exported to '{os.path.basename(filepath)}'.")
        else:
            messagebox.showerror("Export Failed", result.error_message)

    def _on_export_report(self):
        validation = validate_composition(self.composition)
        if not validation.is_valid:
            proceed = messagebox.askyesno(
                "Composition Not Fully Valid",
                validation.message + "\n\n" + "\n".join(f"• {issue}" for issue in validation.issues) +
                "\n\nDo you want to export the report anyway?"
            )
            if not proceed:
                return

        if self.results is None:
            self._recalculate(silent=True)

        filepath = filedialog.asksaveasfilename(
            title="Export Full Engineering Report to CSV",
            defaultextension=".csv",
            initialfile=fh.timestamped_filename("gas_analysis_report"),
            filetypes=fh.CSV_FILETYPES,
        )
        if not filepath:
            return

        result = fh.export_full_report_to_csv(
            self.composition, self.results, filepath,
            sample_id=self.sample_id_var.get(), operator_name=self.operator_var.get(),
        )
        if result.success:
            messagebox.showinfo("Export Successful", f"Full engineering report exported to:\n{filepath}")
            self._set_status(f"Full report exported to '{os.path.basename(filepath)}'.")
        else:
            messagebox.showerror("Export Failed", result.error_message)

    # ------------------------------------------------------------------ #
    def _on_about(self):
        messagebox.showinfo(
            "About",
            f"{self.app_name}\nVersion {self.app_version}\n\n"
            "A desktop engineering tool for compiling natural gas composition "
            "data and computing Molecular Weight, Specific Gravity, Heating "
            "Value, and Gas Density (via the Dranchuk & Abou-Kassem real-gas "
            "correlation with Wichert-Aziz sour-gas correction).\n\n"
            "Built with Python, Tkinter, Pandas, and Matplotlib."
        )

    def _on_exit(self):
        if messagebox.askokcancel("Exit Application", "Are you sure you want to exit?"):
            self.root.destroy()
