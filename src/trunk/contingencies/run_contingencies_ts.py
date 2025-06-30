import os
import GridCalEngine as gce

folder = os.path.join("..","..","..",'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'IEEE39_1W.gridcal')
main_circuit = gce.open_file(fname)

results = gce.contingencies_ts(circuit=main_circuit,
                               detailed_massive_report=False,
                               contingency_deadband=0.0,
                               contingency_method=gce.ContingencyMethod.PowerFlow)

print()