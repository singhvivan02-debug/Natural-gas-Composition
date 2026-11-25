# Natural Gas Data Transformation & Compilation System

Desktop engineering application (Python / Tkinter / Pandas / Matplotlib).

## Run
```
pip install -r requirements.txt
python main.py
```
(Tkinter ships with the standard Python installer on Windows/macOS.
On Linux: `sudo apt install python3-tk`.)

Keep all 6 files in ONE folder: main.py, gui.py, gas_data.py,
calculations.py, charts.py, file_handler.py

## Features
- Manual entry: double-click a Mole % cell, or use Quick Entry
- CSV import (flexible headers; needs "Component" + "Mole (%)") and template generator
- Validation: numeric / 0-100 range / total = 100% (+ Normalize to 100%)
- Molecular Weight, Specific Gravity, Gross Heating Value (Btu/scf, Btu/lb, MJ/m3)
- Gas density at any P/T using the Dranchuk-Abou-Kassem Z-factor with
  Wichert-Aziz sour-gas correction (real-gas vs ideal-gas shown)
- Pie chart + bar chart (pan / zoom / save-as-image toolbar)
- Export composition CSV or full engineering report CSV

## Formulas
- MWa = sum(yi * MWi)
- SG = MWa / 28.9647
- HV = sum(yi * HVi)
- rho = P * MWa / (Z * R * T), R = 10.7316 psia*ft3/(lb-mol*R)
