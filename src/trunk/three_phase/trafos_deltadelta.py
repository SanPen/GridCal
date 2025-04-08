import numpy as np
import sympy

# Define fundamental symbols
R, X, G, B, t, phi = sympy.symbols('R, X, G, B, t, phi', real=True)
I = sympy.I  # Imaginary unit

# --- Define Series and Shunt Admittances Symbolically ---
# Series Admittance (Ys)
Ys = sympy.Symbol('Y_s')
# Shunt (Magnetizing) Admittance (Ym)
Ym = sympy.Symbol('Y_m')

# Define the relationships (for display purposes, not direct substitution in Ybus formulas below)
Ys_definition = 1 / (R + I * X)
Ym_definition = G + I * B

# Complex tap ratio (tau)
# Assuming tap 'tau' is on the PRIMARY ('p') side, ratio tau:1
# V_p / V_s = tau / 1 => V_p = tau * V_s
tau = t * sympy.exp(I * phi)

# --- Standard Pi-Model Components for Ybus using Ys and Ym ---
# Assuming tap 'tau' is on the PRIMARY ('p') side (ratio tau:1)
# V_p relates to V_s as V_p = tau * V_s

# Contribution to Ybus[p, p] (self-admittance at primary bus 'p')
# Includes series admittance referred to primary (divided by |tau|^2) and half shunt
Ypp_contribution = Ys / (sympy.Abs(tau)**2) + Ym / 2

# Contribution to Ybus[s, s] (self-admittance at secondary bus 's')
# Includes series admittance (as is on secondary) and half shunt
Yss_contribution = Ys + Ym / 2

# Contribution to Ybus[p, s] (mutual admittance between p and s)
# Needs division by tau* (conjugate of tau)
Yps_contribution = -Ys / sympy.conjugate(tau)

# Contribution to Ybus[s, p] (mutual admittance between s and p)
# Needs division by tau
Ysp_contribution = -Ys / tau

# --- Create the 2x2 Transformer Admittance Matrix ---
# Using the contributions derived earlier (tap 'tau' on primary 'p')
Y_transformer_matrix = sympy.Matrix([
    [Ypp_contribution, Yps_contribution],
    [Ysp_contribution, Yss_contribution]
])

# Apply substitutions for cleaner display (Abs(tau)**2 = t**2)
Y_transformer_matrix_subs = Y_transformer_matrix.subs(sympy.Abs(tau)**2, t**2)

print("\nTransformer 2x2 Admittance Matrix Contribution to Ybus (Tap 'tau' on primary 'p'):")
print("  [ Ypp  Yps ]")
print("  [ Ysp  Yss ]")
print("-" * 70)
sympy.pprint(Y_transformer_matrix_subs)
print("-" * 70)


# Triangle matrix
Yp2 = Ym/2
Ysa2 = Ys / (sympy.Abs(tau)**2)
Ysac = Ys / sympy.conjugate(tau)
Ysa = Ys / tau

Y_tri = sympy.Matrix([
    [Yp2 + Ysa2, -Yp2 - Ysa2, 0, -Ysac, Ysac, 0],
    [-Ysa, Ysa, 0, Ys + Yp2, -Ys - Yp2, 0],
    [0, Yp2 + Ysa2, -Yp2 - Ysa2, 0, -Ysac, Ysac],
    [0, -Ysa, Ysa, 0, Ys + Yp2, -Ys - Yp2],
    [-Yp2 - Ysa2, 0, Yp2 + Ysa2, Ysac, 0, -Ysac],
    [Ysa, 0, -Ysa, -Ys - Yp2, 0, Ys + Yp2]
])

sympy.pprint(Y_tri)

Ycon = np.array([[1, 0, 0, 0, -1, 0],
                 [-1, 0, 1, 0, 0, 0],
                 [0, 0, -1, 0, 1, 0],
                 [0, 1, 0, 0, 0, -1],
                 [0, -1, 0, 1, 0, 0],
                 [0, 0, 0, -1, 0, 1],
])

Y_final = Ycon @ Y_tri
print(Y_final)

Y_final_sym = sympy.Matrix(Y_final)
sympy.pprint(Y_final_sym)


