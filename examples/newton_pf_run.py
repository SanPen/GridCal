from GridCalEngine.api import *
from GridCalEngine.Compilers.circuit_to_newton_pa import translate_newton_pa_pf_results, newton_pa_pf

# fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14_from_raw.gridcal'
fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE39.gridcal'
_grid = FileOpen(fname).open()

# _newton_grid = to_newton_pa(circuit=_grid, time_series=False)
_options = PowerFlowOptions()
_res = newton_pa_pf(circuit=_grid, pf_opt=_options, time_series=True)

_res2 = translate_newton_pa_pf_results(_grid, _res)

print()