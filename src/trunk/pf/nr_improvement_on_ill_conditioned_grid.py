import GridCalEngine.api as gce

# fname = "../../../Grids_and_profiles/grids/ntc_8_bus.gridcal"
fname = "../../tests/data/grids/RAW/IEEE_14_v35_3_nudox_1_hvdc_desf_rates_fs_ss.raw"

grid = gce.open_file(fname)

options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, retry_with_other_methods=False)
driver = gce.PowerFlowDriver(grid=grid, options=options)

driver.run()

driver.logger.print()
