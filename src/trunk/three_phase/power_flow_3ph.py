import numpy as np
import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import PfBasicFormulation3Ph
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation import PfBasicFormulation
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx


def power_flow(grid):
    nc = gce.compile_numerical_circuit_at(circuit=grid)

    V0 = nc.bus_data.Vbus
    S0 = nc.get_power_injections_pu()
    I0 = nc.get_current_injections_pu()
    Y0 = nc.get_admittance_injections_pu()
    Qmax, Qmin = nc.get_reactive_power_limits()

    options = gce.PowerFlowOptions(tolerance=1e-10, max_iter=1000)

    problem = PfBasicFormulation(V0=V0, S0=S0, I0=I0, Y0=Y0, Qmin=Qmin, Qmax=Qmax, nc=nc, options=options)

    print('Ybus = \n', problem.adm.Ybus.toarray())
    print('S0 = \n', problem.S0)
    print('I0 = \n', problem.I0)
    print('V0 = \n', problem.V)

    res = newton_raphson_fx(problem=problem)

    return res


def power_flow_3ph(grid, t_idx=None):
    nc = gce.compile_numerical_circuit_at(circuit=grid, fill_three_phase=True, t_idx=t_idx)

    V0 = nc.bus_data.Vbus
    S0 = nc.get_power_injections_pu()
    Qmax, Qmin = nc.get_reactive_power_limits()

    options = gce.PowerFlowOptions(tolerance=1e-10, max_iter=1000)

    problem = PfBasicFormulation3Ph(
        V0=V0,
        S0=S0,
        Qmin=Qmin * 100,
        Qmax=Qmax * 100,
        nc=nc,
        options=options)

    res = newton_raphson_fx(problem=problem, verbose=1, max_iter=1000)

    return res


grid = gce.open_file("ThreePhase_Test.gridcal")

res_1 = power_flow(grid)
res_3ph = power_flow_3ph(grid)

print("Converged: ", res_1.converged)
print("Iter: ", res_1.iterations)
print("Vm:\n", np.abs(res_1.V))
print("Va:\n", np.angle(res_1.V) * 180 / np.pi)

print("Converged: ", res_3ph.converged)
print("Iter: ", res_3ph.iterations)
print("Vm:\n", np.abs(res_3ph.V))
print("Va:\n", np.angle(res_3ph.V) * 180 / np.pi)
