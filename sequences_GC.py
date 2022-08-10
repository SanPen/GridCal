from GridCal.Engine import *
from GridCal.Engine.IO.file_handler import FileOpen

grid = FileOpen('IEEE30.xlsx').open()

pf_options = PowerFlowOptions(solver_type=SolverType.NR,  # Base method to use
                          verbose=False,  # Verbose option where available
                          tolerance=1e-6,  # power error in p.u.
                          max_iter=25,  # maximum iteration number
                          )
pf = PowerFlowDriver(grid, pf_options)
pf.run()

sc_options = ShortCircuitOptions(bus_index=[29], fault_type='3x')
sc = ShortCircuitDriver(grid, options=sc_options, pf_options=pf_options, pf_results=pf.results)
sc.run()

print(abs(sc.results.voltage))

print('Finished!')