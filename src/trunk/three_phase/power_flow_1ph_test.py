import numpy as np
import GridCalEngine.api as gce
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation import PfBasicFormulation
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import PfBasicFormulation3Ph
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx

grid = gce.open_file("SinglePhase_Test.gridcal")

nc = gce.compile_numerical_circuit_at(circuit=grid)

V0 = nc.bus_data.Vbus
S0 = nc.get_power_injections_pu()
I0 = nc.get_current_injections_pu()
Y0 = nc.get_admittance_injections_pu()
Qmax, Qmin = nc.get_reactive_power_limits()

options = gce.PowerFlowOptions(tolerance=1e-10)

problem = PfBasicFormulation(V0=V0, S0=S0, I0=I0, Y0=Y0, Qmin=Qmin, Qmax=Qmax, nc=nc, options=options)

res = newton_raphson_fx(problem=problem)

print("Converged: ", res.converged)
print("Iter: ", res.iterations)
print("Vm:\n", np.abs(res.V))
print("Va:\n", np.angle(res.V)*180/np.pi)