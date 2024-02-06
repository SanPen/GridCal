import GridCalEngine.api as gce
from trunk.pf.power_flow_research import linn5bus_example


grid = linn5bus_example()

options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=2)
driver = gce.PowerFlowDriver(grid=grid, options=options)
driver.run()
driver.logger.print()
