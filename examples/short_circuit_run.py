from GridCal.Engine import *

fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/South Island of New Zealand.gridcal'

grid = FileOpen(fname).open()

pf_options = PowerFlowOptions(solver_type=SolverType.NR,  # Base method to use
                              verbose=False,  # Verbose option where available
                              tolerance=1e-6,  # power error in p.u.
                              max_iter=25,  # maximum iteration number
                              )
pf = PowerFlowDriver(grid, pf_options)
pf.run()

sc_options = ShortCircuitOptions(bus_index=[2], fault_type=FaultType.LG)
sc = ShortCircuitDriver(grid, options=sc_options, pf_options=pf_options, pf_results=pf.results)
sc.run()