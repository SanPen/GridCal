import numpy as np
import pandas as pd
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.linearized_power_flow import acdc_lin_pf
import GridCalEngine.api as gce

# grid = gce.open_file("/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/4node_acdc.gridcal")
grid = gce.open_file("/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/case5_3_he.gridcal")

nc = gce.compile_numerical_circuit_at(grid)

S0 = nc.get_power_injections_pu()
V0 = nc.bus_data.Vbus
I0 = nc.get_current_injections_pu()
Y0 = nc.get_admittance_injections_pu()
indices = nc.get_simulation_indices(Sbus=S0)
lin_adm = nc.get_linear_admittance_matrices(indices=indices)
Bpqpv = lin_adm.get_Bred(pqpv=indices.no_slack)
Bref = lin_adm.get_Bslack(pqpv=indices.no_slack, vd=indices.vd)

# print("B:", lin_adm.Bbus.toarray())
# print("G:", lin_adm.Gbus.toarray())

res = acdc_lin_pf(
    nc=nc,
    Bbus=lin_adm.Bbus,
    Bf=lin_adm.Bf,
    Gbus=lin_adm.Gbus,
    Gf=lin_adm.Gf,
    ac=indices.ac,
    dc=indices.dc,
    vd=indices.vd,
    pv=indices.pv,
    S0=S0,
    I0=I0,
    Y0=Y0,
    V0=V0,
    tau=nc.active_branch_data.tap_angle
)

df = pd.DataFrame(data={
    "Va": np.angle(res.V),
    "Vm": np.abs(res.V)
}, index=nc.bus_data.names)

print(df)
