# from GridCalEngine.IO import FileOpen
# from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at
import GridCalEngine.api as gce

grid = gce.FileOpen('../Grids_and_profiles/grids/IEEE39.xlsx').open()
snapshot = gce.compile_numerical_circuit_at(grid)
print('Done')
