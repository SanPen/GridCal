import numpy as np
import pandas as pd
import GridCalEngine.api as gce
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import PfBasicFormulation3Ph
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx

def power_flow_3ph(grid, t_idx=None):
    nc = gce.compile_numerical_circuit_at(circuit=grid, fill_three_phase=True, t_idx = t_idx)

    V0 = nc.bus_data.Vbus
    S0 = nc.get_power_injections_pu()
    Qmax, Qmin = nc.get_reactive_power_limits()

    options = gce.PowerFlowOptions(tolerance=1e-10, max_iter=1000)

    problem = PfBasicFormulation3Ph(V0=V0, S0=S0, Qmin=Qmin*100, Qmax=Qmax*100, nc=nc, options=options)

    print('Ybus = \n', problem.Ybus.toarray())
    print('S0 = \n', problem.S0)
    print('I0 = \n', problem.I0)
    print('V0 = \n', problem.V)

    res = newton_raphson_fx(problem=problem, verbose=1)

    Ibus = problem.Ybus.dot(res.V)
    print('Ibus = \n', Ibus)

    Sbuss = res.V * np.conj(Ibus)
    print('Sbuss = \n', Sbuss)

    return res

grid = gce.open_file("Test_Ysh.gridcal")
#grid = gce.open_file("src/trunk/unbalanced_pf/mask_case.gridcal")
res_3ph = power_flow_3ph(grid)
print()