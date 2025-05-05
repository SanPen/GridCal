import pygslv as pg

print("GSLV", pg.get_version())
pg.activate(r"C:\Users\santi\.GridCal\license.gslv", verbose=True)

logger = pg.Logger()
verbose = 0
mc: pg.MultiCircuit = pg.read_file("IEEE39_1W.gridcal", logger, verbose)

options = pg.PowerFlowOptions(solver_type=pg.SolverType.NR)
nt = len(mc.time_array)
res = pg.multi_island_pf(grid=mc, options=options, time_indices=list(range(nt)))

print(res.voltage)