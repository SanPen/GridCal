from GridCal.Engine import *
from GridCal.Engine.Core.Compilers.circuit_to_pgm import pgm_pf

# fname = './../../../../../Grids_and_profiles/grids/IEEE 14.xlsx'
# fname = './../../../../../Grids_and_profiles/grids/IEEE 30 Bus.gridcal'
fname = './../../../../../Grids_and_profiles/grids/Some distribution grid (Video).gridcal'
circ = FileOpen(fname).open()

pf_opt = PowerFlowOptions()
lgr = Logger()
pf_res_ = pgm_pf(circ, pf_opt, lgr, time_series=True)

print(pf_res_.voltage)
