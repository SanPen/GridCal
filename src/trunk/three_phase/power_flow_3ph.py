import numpy as np
import GridCalEngine.api as gce
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import PfBasicFormulation3Ph
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx

grid = gce.open_file("3ph_Grid.gridcal")

nc = gce.compile_numerical_circuit_at(circuit=grid, fill_three_phase=True)


V0 = nc.bus_data.Vbus
S0 = nc.get_power_injections_pu()
Qmax, Qmin = nc.get_reactive_power_limits()

options = gce.PowerFlowOptions()

problem = PfBasicFormulation3Ph(V0=V0, S0=S0, Qmin=Qmin, Qmax=Qmax, nc=nc, options=options)

print("Ybus:\n", problem.Ybus.toarray())
print("fx:\n", problem.get_f_df(problem.fx()))
print("x:\n", problem.get_x_df(problem.var2x()))
print("J:\n", problem.get_jacobian_df(problem.Jacobian()))

res = newton_raphson_fx(problem=problem)

print(res.converged)
print("Vm:\n", np.abs(res.V))
print("Sbus:\n", res.Scalc)
print("Pf:\n", res.Sf.real)
print("Pt:\n", res.St.real)