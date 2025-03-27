import GridCalEngine.api as gce

grid = gce.open_file('src/trunk/three_phase/switch_try.gridcal')

pf_ts_driver = gce.PowerFlowTimeSeriesDriver(grid)

pf_ts_driver.run()

print(pf_ts_driver.results.voltage)

