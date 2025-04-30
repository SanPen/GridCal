import pulp

# ---------------------- SYSTEM ---------------------------------
# One HVDC line and one normal line joining 2 nodes
#
#            /-----HVDC------\
#    Gen -> O                 O -> load
#            \____ line______/
#
# The HVDC uses the PMODE3 equation
# The line uses the simple 1/x · (theta_f - theta_t)
# The system is loss-less

# ---------------------- PARAMETERS ---------------------------------
P0 = 4  # example offset
k = 1  # example slope
rate_hvdc = 10  # |Pf| can never exceed this
rate_line = 0
M = 1 * rate_hvdc  # exact, tight value — NOT an arbitrary big number
x = 0.5
load = 9

# ---------------------- MODEL --------------------------------------
prob = pulp.LpProblem("exhausted PMODE3", pulp.LpMaximize)  # any objective; just a toy

# Decision variables
Pf_hvdc = pulp.LpVariable('Pf_hvdc', lowBound=P0, upBound=rate_hvdc)  # always inside ±rate
Pf_line = pulp.LpVariable('Pf_line', lowBound=-rate_line, upBound=rate_line)  # always inside ±rate
gen = pulp.LpVariable('Gen', lowBound=0, upBound=200)  # always inside ±rate
th1 = 0
th2 = pulp.LpVariable('th2')  # free
y = pulp.LpVariable('y')  # helper = P0 + k(th1–th2)
z = pulp.LpVariable('z', cat='Binary')  # 1  ⇒ equality enforced

# HVDC PMODE3
prob += y == P0 + k * (th1 - th2), "y_definition"
prob += y - Pf_hvdc <= M * (1 - z), "equality_if_z1_pos"  # Conditional equality (Pf = y  only if z = 1)
prob += y - Pf_hvdc >= -M * (1 - z), "equality_if_z1_neg"  # Conditional equality (Pf = y  only if z = 1)

# normal line
prob += Pf_line == (1 / x) * (th1 - th2), "Pf_line_definition"

# Balance node 1
prob += gen == Pf_hvdc + Pf_line, "Balance1"

# Balance node 2
prob += load == Pf_hvdc + Pf_line, "Balance2"

# Objective (just to illustrate behaviour; replace with your own)
prob += gen, "obj"

# ---------------------- SOLVE --------------------------------------
prob.solve(pulp.PULP_CBC_CMD())  # or GUROBI_CMD / CPLEX_CMD / HiGHS_CMD …

# ---------------------- RESULTS ------------------------------------
print("Status  :", pulp.LpStatus[prob.status])
print("Pf_hvdc :", Pf_hvdc.value())
print("Pf_line :", Pf_line.value())
print("gen     :", gen.value())
print("y       :", y.value())
print("Pmode3? :", z.value())
print("th2     :", th2.value())
