import numpy as np
import pandas as pd
import GridCalEngine.api as gce
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import PfBasicFormulation3Ph
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx

def power_flow_3ph(grid, t_idx):
    nc = gce.compile_numerical_circuit_at(circuit=grid, fill_three_phase=True, t_idx = t_idx)

    V0 = nc.bus_data.Vbus
    S0 = nc.get_power_injections_pu()
    Qmax, Qmin = nc.get_reactive_power_limits()

    options = gce.PowerFlowOptions(tolerance=1e-10, max_iter=1000)

    problem = PfBasicFormulation3Ph(V0=V0, S0=S0, Qmin=Qmin*100, Qmax=Qmax*100, nc=nc, options=options)

    res = newton_raphson_fx(problem=problem, verbose=1, max_iter=100)

    return res

grid = gce.open_file("IEEE Test Distribution.gridcal")

df_U_a = pd.DataFrame()
df_U_b = pd.DataFrame()
df_U_c = pd.DataFrame()

for i in range(grid.get_time_number()):
    res_3ph = power_flow_3ph(grid, i)

    U = np.abs(res_3ph.V)
    angle = np.angle(res_3ph.V) * (180/np.pi)

    # Reshape to (n_buses, 3) where columns are [a, b, c]
    U_reshaped = U.reshape(-1, 3)
    angle_reshaped = angle.reshape(-1, 3)

    # Add this column to the DataFrame
    df_U_a[f't={i}'] = U_reshaped[:, 0]
    df_U_b[f't={i}'] = U_reshaped[:, 1]
    df_U_c[f't={i}'] = U_reshaped[:, 2]

    print(res_3ph.converged)

# Export to Excel
df_U_a.to_excel("Ua_results.xlsx", index=False)
df_U_b.to_excel("Ub_results.xlsx", index=False)
df_U_c.to_excel("Uc_results.xlsx", index=False)