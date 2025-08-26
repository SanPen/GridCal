import GridCalEngine.api as gce
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at

my_grid = gce.open_file("src/trunk/three_phase/3ph_Grid.gridcal")
nc = compile_numerical_circuit_at(circuit=my_grid, fill_three_phase=True)
print()