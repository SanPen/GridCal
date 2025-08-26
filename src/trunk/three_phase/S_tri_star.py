import numpy as np

# --- 1. Define Star Voltages (L-N) ---
# Balanced voltage example
V_LN = 230.0  # Line-to-neutral voltage magnitude (Volts)
a = np.exp(1j * 2 * np.pi / 3) # Note: Using engineering 'a' operator convention a = exp(j*120)
a2 = np.exp(-1j * 2 * np.pi / 3)

V_an_star = V_LN + 0j
V_bn_star = V_LN * a2 # Negative sequence: a-c-b for standard matrix
V_cn_star = V_LN * a  # Positive sequence: a-b-c

# If using standard C_v/C_i, phases usually correspond to V_an, V_bn, V_cn
V_star = np.array([[V_an_star], [V_bn_star], [V_cn_star]], dtype=complex)

# --- 2. Define Star Currents (Line Currents) ---
# Example: Unbalanced currents
I_a_mag, I_a_ang_deg = 10.0, -30.0
I_b_mag, I_b_ang_deg = 9.0, -150.0
I_c_mag, I_c_ang_deg = 11.0, 90.0

I_a_star = I_a_mag * np.exp(1j * np.deg2rad(I_a_ang_deg))
I_b_star = I_b_mag * np.exp(1j * np.deg2rad(I_b_ang_deg))
I_c_star = I_c_mag * np.exp(1j * np.deg2rad(I_c_ang_deg))

I_star = np.array([[I_a_star], [I_b_star], [I_c_star]], dtype=complex)

# --- 3. Calculate Star Powers Directly ---
# Matrix (Outer Product)
S_star_direct = V_star @ I_star.conj().T

# Vector (Element-wise V*I conjugate)
S_star_vec_direct = V_star * I_star.conj() # Note: Element-wise multiplication

print("--- Star Side Calculations ---")
print(f"V_star (L-N):\n{V_star}")
print(f"\nI_star (Line):\n{I_star}")
print(f"\nS_star (Matrix = V_star @ I_star_H) Direct:\n{S_star_direct}")
print(f"\nS_star_vec (Vector = V_star .* conj(I_star)) Direct:\n{S_star_vec_direct}")

# --- 4. Define Connectivity Matrices ---
# V_tri = C_v @ V_star (Delta Line-Line from Star L-N)
C_v = np.array([
    [1, -1, 0],
    [0, 1, -1],
    [-1, 0, 1]
], dtype=complex)

# I_star = C_i @ I_tri (Star Line from Delta Phase)
C_i = np.array([
    [1, 0, -1],
    [-1, 1, 0],
    [0, -1, 1]
], dtype=complex)
# Note: For this standard transformation C_i = C_v.T

print("\n--- Connectivity Matrices ---")
print(f"C_v:\n{C_v}")
print(f"C_i:\n{C_i}")

# --- 5. Calculate Delta Voltages ---
V_tri = C_v @ V_star

# --- 6. Calculate Delta Currents ---
# Need to invert I_star = C_i @ I_tri => I_tri = inv(C_i) @ I_star
# C_i is singular, use Moore-Penrose pseudo-inverse
C_i_inv = np.linalg.pinv(C_i)
I_tri = C_i_inv @ I_star

# --- 7. Calculate Delta Powers Directly ---
# Matrix (Outer Product)
S_tri_direct = V_tri @ I_tri.conj().T

# Vector (Element-wise V*I conjugate)
S_tri_vec_direct = V_tri * I_tri.conj() # Element-wise

print("\n--- Delta Side Calculations ---")
print(f"V_tri (L-L = C_v @ V_star):\n{V_tri}")
print(f"\nI_tri (Phase = pinv(C_i) @ I_star):\n{I_tri}")
print(f"\nS_tri (Matrix = V_tri @ I_tri_H) Direct:\n{S_tri_direct}")
print(f"\nS_tri_vec (Vector = V_tri .* conj(I_tri)) Direct:\n{S_tri_vec_direct}")


# --- 8. Validate Formula 1 (Matrix Power Relation) ---
# Formula: S_star = C_v_inv @ S_tri @ C_i_H
# Need C_v inverse (pseudo-inverse) and C_i conjugate transpose
print("\n--- Validation 1: Matrix Formula S_star = pinv(C_v) @ S_tri @ C_i_H ---")
C_v_inv = np.linalg.pinv(C_v)
C_i_H = C_i.conj().T # Hermitian (conjugate transpose)

S_star_formula = C_v_inv @ S_tri_direct @ C_i_H

# Compare
print(f"\nComparing S_star_direct vs S_star_formula:")
print(f"Are matrices close? {np.allclose(S_star_direct, S_star_formula)}")
print(S_star_formula)



# --- 9. Validate Formula 2 (Vector Power Conservation) ---
# Total power should be conserved: sum(S_star_vec) = sum(S_tri_vec)
print("\n--- Validation 2: Vector Power Conservation sum(S_star_vec) = sum(S_tri_vec) ---")

total_S_star = np.sum(S_star_vec_direct)
total_S_tri = np.sum(S_tri_vec_direct)

print(f"Total complex power from S_star_vec_direct: {total_S_star:.2f}")
print(f"Total complex power from S_tri_vec_direct: {total_S_tri:.2f}")
print(f"Are total powers equal? {np.allclose(total_S_star, total_S_tri)}")

# Optional: Verify trace relationship (total power from matrices)
trace_S_star = np.trace(S_star_direct)
trace_S_tri = np.trace(S_tri_direct)
print(f"\nTotal complex power from trace(S_star_direct): {trace_S_star:.2f}")
print(f"Total complex power from trace(S_tri_direct): {trace_S_tri:.2f}")
print(f"Are traces equal? {np.allclose(trace_S_star, trace_S_tri)}")
print(f"Are trace(S_star) and sum(S_star_vec) equal? {np.allclose(trace_S_star, total_S_star)}")
print(f"Are trace(S_tri) and sum(S_tri_vec) equal? {np.allclose(trace_S_tri, total_S_tri)}")