import GridCalEngine as gce

grid = gce.open_file("3-bus-demo.gridcal")

nc = gce.compile_numerical_circuit_at(grid, fill_three_phase=True)

print("yff:\n", nc.passive_branch_data.Yff3)
print("yft:\n", nc.passive_branch_data.Yft3)
print("ytf:\n", nc.passive_branch_data.Ytf3)
print("ytt:\n", nc.passive_branch_data.Ytt3)

