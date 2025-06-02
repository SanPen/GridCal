import GridCalEngine.api as gce

grid = gce.open_file("2ph_AB.gridcal")
nc = gce.compile_numerical_circuit_at(circuit=grid, fill_three_phase=True)
print()