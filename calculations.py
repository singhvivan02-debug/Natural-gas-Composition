"""
================================================================================
 NATURAL GAS DATA TRANSFORMATION AND COMPILATION SYSTEM
================================================================================
 Module       : calculations.py
 Description  : This module is the engineering calculation core of the
                application. Given a validated GasComposition (see
                gas_data.py), it computes:

                    1. Apparent Molecular Weight of the gas mixture
                       (MWa = sum of yi * MWi)

                    2. Gas Specific Gravity (relative to dry air)

                    3. Gross (Higher) Heating Value of the mixture, on a
                       molar-additive basis, in Btu/scf, Btu/lb and MJ/m3

                    4. Real-gas Compressibility Factor (Z) using the
                       Dranchuk & Abou-Kassem (1975) equation of state
                       fitted to the Standing-Katz chart, including the
                       Wichert-Aziz (1972) sour-gas correction for
                       pseudo-critical properties when CO2 and/or H2S are
                       present.

                    5. Gas Density at any user-specified pressure and
                       temperature, using the real-gas law:
                            rho = (P * MWa) / (Z * R * T)
                       An ideal-gas density (Z = 1) is also reported for
                       comparison, which is standard practice in
                       engineering PVT reports.

 Author       : Semester Project
 Version      : 1.0.0
================================================================================
"""

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional

from gas_data import (
    GasComposition,
    MOLECULAR_WEIGHT_OF_AIR,
    UNIVERSAL_GAS_CONSTANT_R,
    STANDARD_TEMPERATURE_R,
    STANDARD_PRESSURE_PSIA,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. UNIT CONVERSION HELPERS
# ==============================================================================
def fahrenheit_to_rankine(temp_f: float) -> float:
    """Converts a temperature in degrees Fahrenheit to degrees Rankine."""
    return temp_f + 459.67


def rankine_to_fahrenheit(temp_r: float) -> float:
    """Converts a temperature in degrees Rankine to degrees Fahrenheit."""
    return temp_r - 459.67


def lb_per_ft3_to_kg_per_m3(density_lb_ft3: float) -> float:
    """Converts a density value from lb/ft3 to kg/m3."""
    return density_lb_ft3 * 16.0184634


def btu_per_scf_to_mj_per_m3(hv_btu_scf: float) -> float:
    """Converts a heating value from Btu/scf to MJ/m3."""
    return hv_btu_scf * 0.0372589


# ==============================================================================
# 2. DRANCHUK & ABOU-KASSEM (DAK) EQUATION-OF-STATE CONSTANTS
# ==============================================================================
# These eleven empirical constants reproduce the Standing-Katz Z-factor
# chart over the range 0.2 <= Pr <= 30 and 1.0 <= Tr <= 3.0, and are the
# industry-standard correlation used by natural-gas PVT software when an
# analytical (non-graphical) Z-factor is required.
DAK_A1 = 0.3265
DAK_A2 = -1.0700
DAK_A3 = -0.5339
DAK_A4 = 0.01569
DAK_A5 = -0.05165
DAK_A6 = 0.5475
DAK_A7 = -0.7361
DAK_A8 = 0.1844
DAK_A9 = 0.1056
DAK_A10 = 0.6134
DAK_A11 = 0.7210

DAK_MAX_ITERATIONS = 100
DAK_CONVERGENCE_TOLERANCE = 1.0e-8


# ==============================================================================
# 3. RESULT CONTAINER
# ==============================================================================
@dataclass
class CalculationResults:
    """
    Holds every engineering result produced by GasCalculator.compute_all(),
    in a structure that both the GUI (for display) and file_handler.py
    (for CSV export) can consume directly without recomputation.
    """
    # Composition basis
    total_mole_percent: float = 0.0
    number_of_active_components: int = 0

    # Molecular weight & specific gravity
    apparent_molecular_weight: float = 0.0     # lb/lb-mol
    specific_gravity: float = 0.0              # dimensionless (relative to air)

    # Heating values
    gross_heating_value_btu_scf: float = 0.0   # Btu per standard cubic foot
    gross_heating_value_btu_lb: float = 0.0    # Btu per pound
    gross_heating_value_mj_m3: float = 0.0     # MJ per standard cubic meter

    # Pseudo-critical properties (Kay's rule + Wichert-Aziz sour correction)
    pseudo_critical_temperature_R: float = 0.0
    pseudo_critical_pressure_psia: float = 0.0
    wichert_aziz_correction_R: float = 0.0
    is_sour_gas: bool = False

    # Reduced properties at operating conditions
    operating_pressure_psia: float = 0.0
    operating_temperature_F: float = 0.0
    reduced_pressure: float = 0.0
    reduced_temperature: float = 0.0

    # Compressibility & density
    compressibility_factor_z: float = 1.0
    z_factor_iterations: int = 0
    gas_density_real_lb_ft3: float = 0.0
    gas_density_real_kg_m3: float = 0.0
    gas_density_ideal_lb_ft3: float = 0.0      # Z = 1 comparison basis

    # Density at standard conditions (60 F, 14.696 psia) for reference
    gas_density_standard_lb_ft3: float = 0.0

    warnings: List[str] = field(default_factory=list)

    def as_flat_dict(self) -> dict:
        """
        Flattens the results into a single dict of {label: value} pairs
        formatted for direct display in the GUI results panel or export
        to a summary CSV row via file_handler.py.
        """
        return {
            "Total Composition (%)": round(self.total_mole_percent, 3),
            "Active Components": self.number_of_active_components,
            "Apparent Molecular Weight (lb/lb-mol)": round(self.apparent_molecular_weight, 4),
            "Specific Gravity (air = 1.0)": round(self.specific_gravity, 4),
            "Gross Heating Value (Btu/scf)": round(self.gross_heating_value_btu_scf, 2),
            "Gross Heating Value (Btu/lb)": round(self.gross_heating_value_btu_lb, 2),
            "Gross Heating Value (MJ/m3)": round(self.gross_heating_value_mj_m3, 3),
            "Pseudo-Critical Temperature (R)": round(self.pseudo_critical_temperature_R, 2),
            "Pseudo-Critical Pressure (psia)": round(self.pseudo_critical_pressure_psia, 2),
            "Sour Gas Correction Applied": "Yes" if self.is_sour_gas else "No",
            "Operating Pressure (psia)": round(self.operating_pressure_psia, 2),
            "Operating Temperature (F)": round(self.operating_temperature_F, 2),
            "Reduced Pressure (Pr)": round(self.reduced_pressure, 4),
            "Reduced Temperature (Tr)": round(self.reduced_temperature, 4),
            "Compressibility Factor Z": round(self.compressibility_factor_z, 5),
            "Gas Density - Real Gas (lb/ft3)": round(self.gas_density_real_lb_ft3, 5),
            "Gas Density - Real Gas (kg/m3)": round(self.gas_density_real_kg_m3, 4),
            "Gas Density - Ideal Gas (lb/ft3)": round(self.gas_density_ideal_lb_ft3, 5),
            "Gas Density at Standard Conditions (lb/ft3)": round(self.gas_density_standard_lb_ft3, 5),
        }


# ==============================================================================
# 4. GAS CALCULATOR ENGINE
# ==============================================================================
class GasCalculator:
    """
    Performs the full suite of engineering calculations required by the
    project on a given GasComposition, evaluated at a specified operating
    pressure and temperature (defaulting to standard conditions).
    """

    def __init__(self, composition: GasComposition,
                 pressure_psia: float = STANDARD_PRESSURE_PSIA,
                 temperature_f: float = 60.0):
        """
        Args:
            composition:      The validated GasComposition to evaluate.
            pressure_psia:    Operating pressure in psia for density/Z calcs.
            temperature_f:    Operating temperature in degrees Fahrenheit
                               for density/Z calcs.
        """
        self.composition = composition
        self.pressure_psia = pressure_psia
        self.temperature_f = temperature_f
        self.temperature_r = fahrenheit_to_rankine(temperature_f)

    # ------------------------------------------------------------------ #
    # 4.1 Molecular Weight
    # ------------------------------------------------------------------ #
    def apparent_molecular_weight(self) -> float:
        """
        Computes the apparent (average) molecular weight of the gas
        mixture using the molar mixing rule:

                MWa = sum( yi * MWi )   for all components i

        where yi is the mole fraction and MWi is the pure-component
        molecular weight (lb/lb-mol).
        """
        return sum(c.mole_fraction() * c.molecular_weight
                   for c in self.composition.components)

    # ------------------------------------------------------------------ #
    # 4.2 Specific Gravity
    # ------------------------------------------------------------------ #
    def specific_gravity(self, mwa: Optional[float] = None) -> float:
        """
        Computes gas specific gravity relative to dry air:

                SG = MWa / MW_air        (MW_air = 28.9647 lb/lb-mol)

        A dimensionless value slightly less than 1.0 indicates a gas
        lighter than air (typical of lean, methane-rich natural gas);
        values above 1.0 indicate a heavier gas (rich in NGLs, CO2, H2S).
        """
        if mwa is None:
            mwa = self.apparent_molecular_weight()
        return mwa / MOLECULAR_WEIGHT_OF_AIR

    # ------------------------------------------------------------------ #
    # 4.3 Heating Value
    # ------------------------------------------------------------------ #
    def gross_heating_value_btu_scf(self) -> float:
        """
        Computes the gross (higher) heating value of the mixture on a
        molar-additive basis:

                HVmix = sum( yi * HVi )     [Btu/scf]

        where HVi is each pure component's gross heating value at
        standard conditions (60 F, 14.696 psia).
        """
        return sum(c.mole_fraction() * c.gross_heating_value
                   for c in self.composition.components)

    def gross_heating_value_btu_lb(self, hv_btu_scf: Optional[float] = None,
                                    mwa: Optional[float] = None) -> float:
        """
        Converts the volumetric heating value (Btu/scf) into a mass basis
        (Btu/lb) using the ideal-gas molar volume at standard conditions
        (379.48 scf per lb-mol):

                HV(Btu/lb) = HV(Btu/scf) * 379.48 / MWa
        """
        if hv_btu_scf is None:
            hv_btu_scf = self.gross_heating_value_btu_scf()
        if mwa is None:
            mwa = self.apparent_molecular_weight()
        if mwa <= 0:
            return 0.0
        standard_molar_volume_scf_per_lbmol = 379.48
        return hv_btu_scf * standard_molar_volume_scf_per_lbmol / mwa

    # ------------------------------------------------------------------ #
    # 4.4 Pseudo-Critical Properties (Kay's Rule + Wichert-Aziz Correction)
    # ------------------------------------------------------------------ #
    def pseudo_critical_properties(self):
        """
        Computes the mixture's pseudo-critical temperature and pressure
        using Kay's mixing rule:

                Tpc = sum( yi * Tci )      [Rankine]
                Ppc = sum( yi * Pci )      [psia]

        If the mixture contains CO2 and/or H2S ("sour gas"), the
        Wichert-Aziz (1972) correction is applied, which is the standard
        industry adjustment because acid gases cause the simple Kay's
        rule to under-predict the Z-factor:

                A = yCO2 + yH2S
                B = yH2S
                eps = 120*(A^0.9 - A^1.6) + 15*(B^0.5 - B^4)     [Rankine]

                Tpc' = Tpc - eps
                Ppc' = Ppc * Tpc' / (Tpc + B*(1 - B)*eps)

        Returns:
            (Tpc_corrected, Ppc_corrected, epsilon, is_sour) tuple
        """
        tpc = sum(c.mole_fraction() * c.critical_temperature_R
                  for c in self.composition.components)
        ppc = sum(c.mole_fraction() * c.critical_pressure_psia
                  for c in self.composition.components)

        co2_comp = self.composition.get_component("Carbon Dioxide")
        h2s_comp = self.composition.get_component("Hydrogen Sulfide")
        y_co2 = co2_comp.mole_fraction() if co2_comp else 0.0
        y_h2s = h2s_comp.mole_fraction() if h2s_comp else 0.0

        a = y_co2 + y_h2s
        b = y_h2s
        is_sour = a > 0.0

        if is_sour:
            epsilon = (120.0 * (a ** 0.9 - a ** 1.6)) + (15.0 * (b ** 0.5 - b ** 4))
            tpc_corrected = tpc - epsilon
            denominator = tpc + b * (1.0 - b) * epsilon
            ppc_corrected = (ppc * tpc_corrected / denominator) if denominator != 0 else ppc
        else:
            epsilon = 0.0
            tpc_corrected = tpc
            ppc_corrected = ppc

        return tpc_corrected, ppc_corrected, epsilon, is_sour

    # ------------------------------------------------------------------ #
    # 4.5 Real-Gas Compressibility Factor (Dranchuk & Abou-Kassem, 1975)
    # ------------------------------------------------------------------ #
    def compressibility_factor(self, pressure_psia: Optional[float] = None,
                                temperature_r: Optional[float] = None):
        """
        Solves for the real-gas compressibility factor Z at the given
        pressure and temperature using the Dranchuk & Abou-Kassem (DAK)
        equation of state, an implicit correlation solved here by
        Newton-Raphson iteration on the reduced density.

        Returns:
            (Z, Tr, Pr, iterations_used)
        """
        if pressure_psia is None:
            pressure_psia = self.pressure_psia
        if temperature_r is None:
            temperature_r = self.temperature_r

        tpc, ppc, _, _ = self.pseudo_critical_properties()

        if tpc <= 0 or ppc <= 0:
            logger.warning("Invalid pseudo-critical properties (Tpc=%.2f, Ppc=%.2f); "
                            "defaulting Z = 1.0 (ideal gas).", tpc, ppc)
            return 1.0, 0.0, 0.0, 0

        tr = temperature_r / tpc
        pr = pressure_psia / ppc

        # Initial guess for reduced density (rho_r) based on Z = 1
        z = 1.0
        rho_r = 0.27 * pr / (z * tr)

        iterations = 0
        for iterations in range(1, DAK_MAX_ITERATIONS + 1):
            rho_r_sq = rho_r * rho_r

            c1 = (DAK_A1 + DAK_A2 / tr + DAK_A3 / tr ** 3
                  + DAK_A4 / tr ** 4 + DAK_A5 / tr ** 5)
            c2 = (DAK_A6 + DAK_A7 / tr + DAK_A8 / tr ** 2)
            c3 = DAK_A9 * (DAK_A7 / tr + DAK_A8 / tr ** 2)

            # DAK function: f(rho_r) = rho_r - 0.27*Pr / (Z(rho_r) * Tr) = 0,
            # expressed via the explicit Z(rho_r) relation below.
            z_calc = (
                1.0
                + c1 * rho_r
                + c2 * rho_r_sq
                - c3 * rho_r ** 5
                + DAK_A10 * (1.0 + DAK_A11 * rho_r_sq) * (rho_r_sq / tr ** 3)
                * math.exp(-DAK_A11 * rho_r_sq)
            )

            f = rho_r - (0.27 * pr) / (z_calc * tr)

            # Numerical derivative of f with respect to rho_r for Newton-Raphson
            delta = 1.0e-6
            rho_r_perturbed = rho_r + delta
            rho_r_perturbed_sq = rho_r_perturbed * rho_r_perturbed
            z_calc_perturbed = (
                1.0
                + c1 * rho_r_perturbed
                + c2 * rho_r_perturbed_sq
                - c3 * rho_r_perturbed ** 5
                + DAK_A10 * (1.0 + DAK_A11 * rho_r_perturbed_sq)
                * (rho_r_perturbed_sq / tr ** 3)
                * math.exp(-DAK_A11 * rho_r_perturbed_sq)
            )
            f_perturbed = rho_r_perturbed - (0.27 * pr) / (z_calc_perturbed * tr)

            derivative = (f_perturbed - f) / delta
            if derivative == 0:
                break

            rho_r_new = rho_r - f / derivative
            rho_r_new = max(rho_r_new, 1.0e-8)  # keep density physically positive

            if abs(rho_r_new - rho_r) < DAK_CONVERGENCE_TOLERANCE:
                rho_r = rho_r_new
                z = z_calc
                break

            rho_r = rho_r_new
            z = z_calc

        return z, tr, pr, iterations

    # ------------------------------------------------------------------ #
    # 4.6 Gas Density
    # ------------------------------------------------------------------ #
    def gas_density(self, mwa: Optional[float] = None,
                     pressure_psia: Optional[float] = None,
                     temperature_r: Optional[float] = None,
                     z_factor: Optional[float] = None):
        """
        Computes real-gas density using the real gas law:

                rho = (P * MWa) / (Z * R * T)     [lb/ft3]

        where P is in psia, T is in Rankine, MWa is the apparent
        molecular weight in lb/lb-mol, R is the universal gas constant
        (10.7316 psia*ft3/(lb-mol*R)), and Z is the real-gas
        compressibility factor at (P, T).

        Also returns the ideal-gas density (Z = 1) at the same
        conditions for direct comparison, which highlights how far the
        gas deviates from ideal behaviour.

        Returns:
            (density_real_lb_ft3, density_ideal_lb_ft3)
        """
        if mwa is None:
            mwa = self.apparent_molecular_weight()
        if pressure_psia is None:
            pressure_psia = self.pressure_psia
        if temperature_r is None:
            temperature_r = self.temperature_r
        if z_factor is None:
            z_factor, _, _, _ = self.compressibility_factor(pressure_psia, temperature_r)

        density_real = (pressure_psia * mwa) / (z_factor * UNIVERSAL_GAS_CONSTANT_R * temperature_r)
        density_ideal = (pressure_psia * mwa) / (1.0 * UNIVERSAL_GAS_CONSTANT_R * temperature_r)

        return density_real, density_ideal

    # ------------------------------------------------------------------ #
    # 4.7 Master Routine — computes and packages every result at once
    # ------------------------------------------------------------------ #
    def compute_all(self) -> CalculationResults:
        """
        Runs the complete calculation sequence (MW -> SG -> Heating Value
        -> Pseudo-critical properties -> Z-factor -> Density) and returns
        a single populated CalculationResults object ready for display in
        the GUI or export via file_handler.py.
        """
        results = CalculationResults()
        warnings = []

        results.total_mole_percent = self.composition.total_mole_percent()
        results.number_of_active_components = len(self.composition.active_components())

        if abs(results.total_mole_percent - 100.0) > 0.5:
            warnings.append(
                f"Composition totals {results.total_mole_percent:.2f}%, not 100%. "
                f"Results below are computed on the AS-ENTERED basis; consider "
                f"normalizing the composition for accurate results."
            )

        # --- Molecular weight & specific gravity ---
        mwa = self.apparent_molecular_weight()
        results.apparent_molecular_weight = mwa
        results.specific_gravity = self.specific_gravity(mwa)

        # --- Heating values ---
        hv_scf = self.gross_heating_value_btu_scf()
        results.gross_heating_value_btu_scf = hv_scf
        results.gross_heating_value_btu_lb = self.gross_heating_value_btu_lb(hv_scf, mwa)
        results.gross_heating_value_mj_m3 = btu_per_scf_to_mj_per_m3(hv_scf)

        # --- Pseudo-critical properties ---
        tpc, ppc, epsilon, is_sour = self.pseudo_critical_properties()
        results.pseudo_critical_temperature_R = tpc
        results.pseudo_critical_pressure_psia = ppc
        results.wichert_aziz_correction_R = epsilon
        results.is_sour_gas = is_sour

        # --- Operating conditions & real-gas behaviour ---
        results.operating_pressure_psia = self.pressure_psia
        results.operating_temperature_F = self.temperature_f

        z, tr, pr, iterations = self.compressibility_factor()
        results.compressibility_factor_z = z
        results.reduced_temperature = tr
        results.reduced_pressure = pr
        results.z_factor_iterations = iterations

        if z < 0.2 or z > 1.5:
            warnings.append(
                f"Computed Z-factor ({z:.4f}) is outside the typical natural-gas "
                f"range (0.2-1.5). Verify pressure/temperature inputs and "
                f"composition, especially critical-property values for any "
                f"custom (non-library) components."
            )

        density_real, density_ideal = self.gas_density(mwa, self.pressure_psia,
                                                          self.temperature_r, z)
        results.gas_density_real_lb_ft3 = density_real
        results.gas_density_real_kg_m3 = lb_per_ft3_to_kg_per_m3(density_real)
        results.gas_density_ideal_lb_ft3 = density_ideal

        # --- Density at standard conditions (60 F, 14.696 psia) for reference ---
        z_std, _, _, _ = self.compressibility_factor(STANDARD_PRESSURE_PSIA, STANDARD_TEMPERATURE_R)
        density_std, _ = self.gas_density(mwa, STANDARD_PRESSURE_PSIA, STANDARD_TEMPERATURE_R, z_std)
        results.gas_density_standard_lb_ft3 = density_std

        results.warnings = warnings

        logger.info(
            "Calculation complete | MWa=%.4f | SG=%.4f | HV=%.2f Btu/scf | "
            "Z=%.5f | rho=%.5f lb/ft3",
            mwa, results.specific_gravity, hv_scf, z, density_real
        )

        return results
