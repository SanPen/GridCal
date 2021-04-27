"""
Compute the available transfer capacity
"""
from GridCal.Engine import *

if __name__ == '__main__':

    fname = r'C:\Users\penversa\Git\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'

    main_circuit = FileOpen(fname).open()

    simulation = LinearAnalysis(grid=main_circuit)
    simulation.run()
    ptdf = simulation.results.PTDF
    lodf = simulation.results.LODF
    print()
