"""
Conversion from:
https://ideone.com/9FW9Ud
"""

import pandas as pd
from math import *

k_factor31 = 100e6  # Conversion factor
k_factor31r = 1000e6  # Conversion factor

R31 = 0.0112013  # R[pu] - Winding kV, system MVA
X31 = 0.367610  # X[pu] - Winding kV, system MVA

R31r = 113400.007813  # R[W] - Load loss
X31r = 0.118200  # X[pu] - Z pu

V1_31 = 132e3  # Nominal V1
V2_31 = 11e3  # Nominal V2

V1_31r = 125e3  # Nominal V1
V2_31r = 11.5e3  # Nominal V2

MVA = 31.5e6  # MVA - base

# # PSSE - modell fra Statnett
Z31_base = V1_31 ** 2 / k_factor31  # I Ohm(kfaktor pga System MVA)
R31_ohm = R31 * Z31_base
X31_ohm = X31 * Z31_base
Z31_ohm = abs(R31_ohm + 1j * X31_ohm)
I31_nom = sqrt(MVA / Z31_ohm)

# Konvertert modell

Z31r_base = V1_31r ** 2 / (3 * MVA)  # I Ohm (3 * MVA pga Winding MVA)
R31r_pu = R31r / (MVA * 3)  # pu av MVA - rating
R31r_ohm = R31r_pu * Z31r_base
X31r_ohm = 3 * X31r * Z31_base
Z31r_ohm = abs(R31r_ohm + 1j * X31r_ohm)
I31r_nom = 3 * MVA / V1_31r

Z_base_compare = [Z31_base, Z31r_base]
R_compare = [R31_ohm, R31r_ohm]
X_compare = [X31_ohm, X31r_ohm]
Z_compare = [Z31_ohm, Z31r_ohm]
I_compare = [I31_nom, I31r_nom]

print('\n########### Comparison ##############\n')

data = [Z_base_compare, R_compare, X_compare, I_compare]
cols = ['PSSE 31', 'PSSE 31r']
index = ['Z base', 'R [ohm]', 'X [ohm]', 'I [Amps]']
df = pd.DataFrame(data=data, columns=cols, index=index)
print(df)
print()
