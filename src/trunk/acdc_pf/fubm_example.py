import GridCalEngine.api as gce

fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/fubm_caseHVDC_vt.gridcal'
grid = gce.open_file(fname)

results = gce.power_flow(grid)

print(results.get_bus_df())
print()
print(results.get_branch_df())
print("Error:", results.error)
