import os
import cvxpy as cp
import numpy as np
import jax.numpy as jnp
from jax import grad, hessian
import GridCalEngine.api as gce

fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', 'Lynn 5 Bus pv.gridcal')
grid = gce.open_file(fname)

nc = gce.compile_numerical_circuit_at(grid)

# demand per bus
S_d = nc.load_data.get_injections_per_bus()

# Generator cost function coefficients
a = 0.01
b = 2.0
c = 100.0

# Define the power balance constraints
constraints = list()

# Define the optimization variable (generator outputs)
Pg = cp.Variable(nc.ngen)
Qg = cp.Variable(nc.ngen)
Vm = cp.Variable(nc.nbus)
Va = cp.Variable(nc.nbus)

for i in range(nc.ngen):
    constraints.append(Pg[i] >= nc.generator_data.pmin[i] / nc.Sbase)
    constraints.append(Pg[i] <= nc.generator_data.pmax[i] / nc.Sbase)

for i in nc.vd:
    constraints.append(Vm[i] == 1.0)
    constraints.append(Va[i] == 0.0)

for i in nc.pqpv:
    constraints.append(Vm[i] <= nc.bus_data.Vmax[i])
    constraints.append(Vm[i] >= nc.bus_data.Vmin[i])
    constraints.append(Va[i] <= nc.bus_data.angle_max[i])
    constraints.append(Va[i] >= nc.bus_data.angle_min[i])

G = nc.Ybus.real
B = nc.Ybus.imag
I_re = G @ V_re - B @ V_im
I_im = G @ V_im + B @ V_re

# Define the objective function
objective = cp.Minimize(cp.sum(cp.square(Pg) * a) + cp.sum(b * Pg) + c)



# JAX function to calculate power mismatch
def power_mismatch(P_g):
    return 0

# Use JAX to compute the Jacobian and Hessian
power_mismatch_jacobian = grad(power_mismatch)
power_mismatch_hessian = hessian(power_mismatch)

# Add power balance constraints to the problem
# for i in range(n_bus):
#     constraints.append(cp.constraints.NonPos(power_mismatch_jacobian(P_g)[i]))

# Define the problem and solve
problem = cp.Problem(objective, constraints)
problem.solve()

# Output the results
print("Generator outputs:", Pg.value)
print("Optimal cost:", problem.value)