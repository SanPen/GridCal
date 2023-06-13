from GridCal.Engine import FileOpen
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.helm_power_flow import helm_josep
import pandas as pd
import numpy as np

np.set_printoptions(linewidth=2000, suppress=True)
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)

# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/lynn5buspv.xlsx'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118.xlsx'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
# fname = 'helm_data1.gridcal'

grid = FileOpen(fname).open()

nc = grid.compile_snapshot()
inputs = nc.compute()[0]  # pick the first island

results = helm_josep(Ybus=inputs.Ybus,
                     Yseries=inputs.Yseries,
                     V0=inputs.Vbus,
                     S0=inputs.Sbus,
                     Ysh0=inputs.Ysh,
                     pq=inputs.pq,
                     pv=inputs.pv,
                     sl=inputs.ref,
                     pqpv=inputs.pqpv,
                     tolerance=1e-6,
                     max_coefficients=10,
                     use_pade=False,
                     verbose=False)
Vm = np.abs(results.V)
Va = np.angle(results.V)
dP = np.abs(inputs.Sbus.real - results.Scalc.real)
dP[inputs.ref] = 0
dQ = np.abs(inputs.Sbus.imag - results.Scalc.imag)
dQ[inputs.pv] = np.nan
dQ[inputs.ref] = np.nan
df = pd.DataFrame(data=np.c_[inputs.bus_types, Vm, Va, np.abs(inputs.Vbus), dP, dQ],
                  columns=['Types', 'Vm', 'Va', 'Vset', 'P mismatch', 'Q mismatch'])
print(df)
print('Error', results.norm_f)
print('P error', np.max(np.abs(dP)))
print('Elapsed', results.elapsed)
