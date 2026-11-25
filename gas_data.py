"""
================================================================================
 NATURAL GAS DATA TRANSFORMATION AND COMPILATION SYSTEM
================================================================================
 Module       : gas_data.py
 Description  : This module is the "engineering reference library" of the
                application. It defines:

                    1. GasComponent   - a data model representing a single
                                         hydrocarbon / non-hydrocarbon
                                         constituent of a natural gas
                                         stream (name, formula, molecular
                                         weight, gross heating value, and
                                         critical properties used later
                                         for real-gas density calculations).

                    2. STANDARD_COMPONENT_LIBRARY - the reference table of
                                         physical constants for the most
                                         common natural-gas constituents,
                                         sourced from standard GPSA
                                         Engineering Data Book values.

                    3. GasComposition - a container class representing a
                                         full gas sample (a list of
                                         GasComponent entries with their
                                         mole fractions), with helper
                                         methods for totals, normalization,
                                         and conversion to/from a pandas
                                         DataFrame (used by the GUI table,
                                         calculations.py and file_handler.py).

                    4. Validation routines used by the GUI's manual data
                                         entry form and CSV import routine
                                         to guarantee that only physically
                                         sensible compositions are accepted
                                         for downstream calculation.

 Author       : Semester Project
 Version      : 1.0.0
================================================================================
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. PHYSICAL CONSTANTS
# ==============================================================================
MOLECULAR_WEIGHT_OF_AIR = 28.9647          # lb/lb-mol  (used for Specific Gravity)
UNIVERSAL_GAS_CONSTANT_R = 10.7316         # psia*ft3 / (lb-mol*R)
STANDARD_TEMPERATURE_R = 519.67            # 60 deg F expressed in Rankine
STANDARD_PRESSURE_PSIA = 14.696            # 1 atm

# Tolerance (in mole %) allowed when checking that a composition sums to 100%
COMPOSITION_SUM_TOLERANCE = 0.5


# ==============================================================================
# 2. GAS COMPONENT DATA MODEL
# ==============================================================================
@dataclass
class GasComponent:
    """
    Represents a single constituent of a natural gas mixture.

    Attributes:
        name                    Human-readable component name (e.g. "Methane")
        formula                 Chemical formula (e.g. "CH4")
        mole_percent            Mole fraction of this component in the
                                 mixture, expressed as a percentage (0-100)
        molecular_weight        Molecular weight in lb/lb-mol (g/mol)
        gross_heating_value     Gross (higher) heating value of the PURE
                                 component at standard conditions,
                                 expressed in Btu/scf (60 F, 14.696 psia)
        critical_temperature_R  Critical temperature of the pure component
                                 in degrees Rankine (used for pseudo-
                                 critical mixing rules in density calcs)
        critical_pressure_psia  Critical pressure of the pure component in
                                 psia (used for pseudo-critical mixing
                                 rules in density calcs)
    """
    name: str
    formula: str
    molecular_weight: float
    gross_heating_value: float
    critical_temperature_R: float
    critical_pressure_psia: float
    mole_percent: float = 0.0

    def mole_fraction(self) -> float:
        """Returns the mole fraction (0-1) rather than mole percent (0-100)."""
        return self.mole_percent / 100.0

    def copy_with_percent(self, mole_percent: float) -> "GasComponent":
        """
        Returns a new GasComponent identical to this one but with a
        different mole_percent value. Used when building a fresh
        GasComposition from the reference library so the library itself
        is never mutated.
        """
        return GasComponent(
            name=self.name,
            formula=self.formula,
            molecular_weight=self.molecular_weight,
            gross_heating_value=self.gross_heating_value,
            critical_temperature_R=self.critical_temperature_R,
            critical_pressure_psia=self.critical_pressure_psia,
            mole_percent=mole_percent,
        )

    def to_dict(self) -> dict:
        """Serializes the component to a plain dict (for CSV export, etc.)"""
        return {
            "Component": self.name,
            "Formula": self.formula,
            "Mole (%)": round(self.mole_percent, 4),
            "Molecular Weight (lb/lb-mol)": self.molecular_weight,
            "Gross Heating Value (Btu/scf)": self.gross_heating_value,
            "Critical Temp (R)": self.critical_temperature_R,
            "Critical Pressure (psia)": self.critical_pressure_psia,
        }


# ==============================================================================
# 3. STANDARD COMPONENT LIBRARY  (GPSA Engineering Data Book reference values)
# ==============================================================================
# Format: name -> GasComponent(molecular_weight, gross_heating_value,
#                               critical_temperature_R, critical_pressure_psia)
STANDARD_COMPONENT_LIBRARY: List[GasComponent] = [
    GasComponent("Methane",         "CH4",   16.043,  1010.0,  343.0,  666.4),
    GasComponent("Ethane",          "C2H6",  30.070,  1769.7,  549.6,  706.5),
    GasComponent("Propane",         "C3H8",  44.097,  2516.1,  665.7,  616.0),
    GasComponent("iso-Butane",      "C4H10", 58.123,  3251.9,  734.6,  527.9),
    GasComponent("n-Butane",        "C4H10", 58.123,  3262.3,  765.3,  550.6),
    GasComponent("iso-Pentane",     "C5H12", 72.150,  4000.9,  828.7,  490.4),
    GasComponent("n-Pentane",       "C5H12", 72.150,  4008.9,  845.5,  488.6),
    GasComponent("n-Hexane",        "C6H14", 86.177,  4755.9,  913.4,  436.9),
    GasComponent("Nitrogen",        "N2",    28.014,     0.0,  227.3,  493.1),
    GasComponent("Carbon Dioxide",  "CO2",   44.010,     0.0,  547.6, 1071.0),
    GasComponent("Hydrogen Sulfide","H2S",   34.082,   637.1,  672.4, 1306.0),
    GasComponent("Water Vapor",     "H2O",   18.015,     0.0, 1164.9, 3200.1),
    GasComponent("Oxygen",          "O2",    31.999,     0.0,  278.6,  731.4),
    GasComponent("Hydrogen",        "H2",     2.016,   324.2,   59.4,  188.1),
    GasComponent("Helium",          "He",     4.003,     0.0,    9.5,   32.9),
]

# Fast lookup dict: component name -> GasComponent reference entry
_LIBRARY_BY_NAME = {comp.name: comp for comp in STANDARD_COMPONENT_LIBRARY}

# A realistic "typical" pipeline-quality natural gas composition (mole %),
# used to pre-populate the GUI as a demonstration / starting sample so the
# user always has something sensible to edit rather than an empty table.
SAMPLE_COMPOSITION_PERCENTAGES = {
    "Methane": 89.5,
    "Ethane": 4.5,
    "Propane": 1.8,
    "iso-Butane": 0.4,
    "n-Butane": 0.6,
    "iso-Pentane": 0.2,
    "n-Pentane": 0.2,
    "n-Hexane": 0.15,
    "Nitrogen": 2.1,
    "Carbon Dioxide": 0.5,
    "Hydrogen Sulfide": 0.0,
    "Water Vapor": 0.0,
    "Oxygen": 0.0,
    "Hydrogen": 0.0,
    "Helium": 0.05,
}


def get_component_names() -> List[str]:
    """Returns the ordered list of all standard component names available."""
    return [comp.name for comp in STANDARD_COMPONENT_LIBRARY]


def get_reference_component(name: str) -> Optional[GasComponent]:
    """
    Looks up a component's physical-constant reference data by name.
    Returns None if the name is not found in the standard library (this
    is used by CSV import to flag unrecognized component names).
    """
    return _LIBRARY_BY_NAME.get(name)


def build_default_composition(use_sample_values: bool = True) -> "GasComposition":
    """
    Builds a fresh GasComposition using every component in the standard
    library. If use_sample_values is True, each component is pre-filled
    with the realistic SAMPLE_COMPOSITION_PERCENTAGES value; otherwise
    every mole_percent is initialized to 0.0 for a blank manual-entry form.
    """
    components = []
    for ref in STANDARD_COMPONENT_LIBRARY:
        pct = SAMPLE_COMPOSITION_PERCENTAGES.get(ref.name, 0.0) if use_sample_values else 0.0
        components.append(ref.copy_with_percent(pct))
    return GasComposition(components)


# ==============================================================================
# 4. GAS COMPOSITION CONTAINER
# ==============================================================================
class GasComposition:
    """
    Represents a complete natural gas sample: an ordered collection of
    GasComponent entries, each carrying its own mole percent. This class
    is the single source of truth passed between the GUI table,
    calculations.py (for MW / SG / HV / density), charts.py (for the pie
    and bar charts) and file_handler.py (for CSV import/export).
    """

    def __init__(self, components: Optional[List[GasComponent]] = None):
        self.components: List[GasComponent] = components if components is not None else []

    # ------------------------------------------------------------------ #
    # Basic accessors
    # ------------------------------------------------------------------ #
    def total_mole_percent(self) -> float:
        """Sums the mole percent across all components in the composition."""
        return sum(c.mole_percent for c in self.components)

    def active_components(self) -> List[GasComponent]:
        """Returns only the components with a non-zero mole percent."""
        return [c for c in self.components if c.mole_percent > 0.0]

    def get_component(self, name: str) -> Optional[GasComponent]:
        for c in self.components:
            if c.name == name:
                return c
        return None

    def set_mole_percent(self, name: str, value: float) -> bool:
        """
        Updates the mole percent of the named component in place.
        Returns True if the component was found and updated, False
        otherwise (e.g. name not present in this composition).
        """
        comp = self.get_component(name)
        if comp is None:
            return False
        comp.mole_percent = value
        return True

    def add_or_update_component(self, component: GasComponent):
        """
        Adds a new component to the composition, or overwrites the
        existing entry with the same name. Used by CSV import when a row
        refers to a component not already present in the composition.
        """
        existing = self.get_component(component.name)
        if existing is not None:
            existing.mole_percent = component.mole_percent
        else:
            self.components.append(component)

    # ------------------------------------------------------------------ #
    # Normalization
    # ------------------------------------------------------------------ #
    def normalize_to_100(self) -> "GasComposition":
        """
        Rescales every component's mole_percent proportionally so that the
        total sums to exactly 100%. Useful when a user's manual entry or
        an imported CSV is close to, but not exactly, 100% (e.g. due to
        rounding in lab measurement reports). Returns self for chaining.
        """
        total = self.total_mole_percent()
        if total <= 0:
            logger.warning("Cannot normalize a composition with zero total mole percent.")
            return self
        factor = 100.0 / total
        for c in self.components:
            c.mole_percent = c.mole_percent * factor
        return self

    # ------------------------------------------------------------------ #
    # DataFrame conversion (bridges to pandas for table display / export)
    # ------------------------------------------------------------------ #
    def to_dataframe(self) -> pd.DataFrame:
        """
        Converts the composition into a pandas DataFrame with one row per
        component, suitable for display in the GUI's Treeview table or
        for exporting to CSV via file_handler.py.
        """
        rows = [c.to_dict() for c in self.components]
        return pd.DataFrame(rows)

    @staticmethod
    def from_dataframe(df: pd.DataFrame) -> Tuple["GasComposition", List[str]]:
        """
        Builds a GasComposition from an imported/pasted pandas DataFrame.

        The DataFrame is expected to contain, at minimum, a component
        name column (accepted headers: 'Component', 'Name', 'Gas
        Component') and a mole percent column (accepted headers:
        'Mole (%)', 'Mole Percent', 'mol%', 'Percentage', 'Composition').

        Returns:
            (GasComposition, warnings): the constructed composition, plus
            a list of human-readable warning strings describing any rows
            that were skipped or any unrecognized component names that
            were nonetheless imported using user-supplied molecular
            weight / heating value data if present in the file.
        """
        warnings: List[str] = []

        name_col = _find_matching_column(df, ["Component", "Name", "Gas Component", "Component Name"])
        pct_col = _find_matching_column(df, ["Mole (%)", "Mole Percent", "mol%", "Mol%",
                                              "Percentage", "Composition", "Mole Fraction (%)"])
        mw_col = _find_matching_column(df, ["Molecular Weight (lb/lb-mol)", "Molecular Weight",
                                             "MW", "Mol. Wt."])
        hv_col = _find_matching_column(df, ["Gross Heating Value (Btu/scf)", "Heating Value",
                                             "GHV", "HV (Btu/scf)"])

        if name_col is None or pct_col is None:
            warnings.append(
                "Could not identify the required 'Component' and 'Mole (%)' "
                "columns in the imported file. No data was loaded."
            )
            return GasComposition(), warnings

        composition = build_default_composition(use_sample_values=False)

        for idx, row in df.iterrows():
            raw_name = str(row[name_col]).strip()
            if not raw_name or raw_name.lower() == "nan":
                continue

            try:
                raw_pct = float(row[pct_col])
            except (ValueError, TypeError):
                warnings.append(f"Row {idx + 2}: invalid mole percent for '{raw_name}' — skipped.")
                continue

            if raw_pct < 0:
                warnings.append(f"Row {idx + 2}: negative mole percent for '{raw_name}' — skipped.")
                continue

            reference = get_reference_component(raw_name)
            if reference is not None:
                composition.set_mole_percent(raw_name, raw_pct)
            else:
                # Unrecognized component name: attempt to build a custom
                # component if the file also supplies MW and heating value;
                # otherwise skip the row with a warning.
                if mw_col is not None and hv_col is not None:
                    try:
                        custom_mw = float(row[mw_col])
                        custom_hv = float(row[hv_col])
                        composition.add_or_update_component(
                            GasComponent(
                                name=raw_name,
                                formula="—",
                                molecular_weight=custom_mw,
                                gross_heating_value=custom_hv,
                                critical_temperature_R=0.0,
                                critical_pressure_psia=0.0,
                                mole_percent=raw_pct,
                            )
                        )
                        warnings.append(
                            f"Row {idx + 2}: '{raw_name}' is not in the standard "
                            f"component library — imported using the MW/heating "
                            f"value supplied in the file. Density/critical-property "
                            f"calculations will treat it as ideal (Tc=Pc=0)."
                        )
                    except (ValueError, TypeError):
                        warnings.append(
                            f"Row {idx + 2}: unrecognized component '{raw_name}' and "
                            f"no valid MW/heating value supplied — skipped."
                        )
                else:
                    warnings.append(
                        f"Row {idx + 2}: unrecognized component '{raw_name}' — skipped "
                        f"(not in standard library and no MW/heating value column found)."
                    )

        return composition, warnings


def _find_matching_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """
    Case-insensitive, whitespace-tolerant search for the first column in
    df whose name matches one of the given candidate header strings.
    """
    normalized_columns = {str(col).strip().lower(): col for col in df.columns}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalized_columns:
            return normalized_columns[key]
    return None


# ==============================================================================
# 5. VALIDATION ROUTINES
# ==============================================================================
class ValidationResult:
    """
    Simple container returned by all validation functions below, holding
    whether the check passed, an overall message, and a list of detailed
    issue strings suitable for direct display in the GUI.
    """
    def __init__(self, is_valid: bool, message: str, issues: Optional[List[str]] = None):
        self.is_valid = is_valid
        self.message = message
        self.issues = issues if issues is not None else []

    def __bool__(self):
        return self.is_valid


def validate_mole_percent_input(raw_value: str) -> Tuple[bool, Optional[float], str]:
    """
    Validates a single mole-percent value typed by the user into the
    manual data entry form.

    Returns:
        (is_valid, parsed_float_or_None, error_message)
    """
    if raw_value is None or str(raw_value).strip() == "":
        return True, 0.0, ""  # blank fields are treated as 0%

    text = str(raw_value).strip().replace("%", "")

    try:
        value = float(text)
    except ValueError:
        return False, None, "Value must be numeric (e.g. 12.5)."

    if value < 0:
        return False, None, "Mole percent cannot be negative."

    if value > 100:
        return False, None, "A single component cannot exceed 100 mole %."

    return True, value, ""


def validate_composition(composition: GasComposition,
                          require_exact_100: bool = False) -> ValidationResult:
    """
    Performs a full engineering-data-quality validation pass over an
    entire GasComposition before it is allowed to proceed to calculation:

        1. At least one component must have a non-zero mole percent.
        2. No individual mole percent may be negative.
        3. No individual mole percent may exceed 100%.
        4. The total of all mole percents must sum to 100% within
           COMPOSITION_SUM_TOLERANCE (or exactly 100% if
           require_exact_100 is True — used right before export/reporting).

    Returns:
        ValidationResult describing whether the composition is acceptable.
    """
    issues: List[str] = []

    active = composition.active_components()
    if not active:
        issues.append("At least one gas component must have a mole percent greater than zero.")

    for comp in composition.components:
        if comp.mole_percent < 0:
            issues.append(f"'{comp.name}': mole percent cannot be negative "
                           f"({comp.mole_percent:.3f}%).")
        if comp.mole_percent > 100:
            issues.append(f"'{comp.name}': mole percent cannot exceed 100% "
                           f"({comp.mole_percent:.3f}%).")

    total = composition.total_mole_percent()
    tolerance = 0.0 if require_exact_100 else COMPOSITION_SUM_TOLERANCE
    if abs(total - 100.0) > tolerance:
        issues.append(
            f"Total composition is {total:.3f}%, which deviates from 100% by "
            f"more than the allowed tolerance of ±{tolerance:.2f}%. "
            f"Please adjust the values or use 'Normalize to 100%'."
        )

    if issues:
        return ValidationResult(
            is_valid=False,
            message=f"Composition failed validation ({len(issues)} issue"
                    f"{'s' if len(issues) != 1 else ''} found).",
            issues=issues,
        )

    return ValidationResult(
        is_valid=True,
        message=f"Composition is valid. Total = {total:.3f}%.",
        issues=[],
    )
