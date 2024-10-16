import GridCalEngine.api as gce

# fname = "../../../Grids_and_profiles/grids/ntc_8_bus.gridcal"
fname = "../../../Grids_and_profiles/grids/IEEE14 - ntc areas_voltages_hvdc.gridcal"

grid = gce.open_file(fname)

info = grid.get_inter_aggregation_info(objects_from=[grid.areas[0]],
                                       objects_to=[grid.areas[1]])

opf_options = gce.OptimalPowerFlowOptions()
lin_options = gce.LinearAnalysisOptions()

ntc_options = gce.OptimalNetTransferCapacityOptions(
    area_from_bus_idx=info.idx_bus_from,
    area_to_bus_idx=info.idx_bus_to,
    transfer_method=gce.AvailableTransferMode.InstalledPower,
    loading_threshold_to_report=98.0,
    skip_generation_limits=True,
    transmission_reliability_margin=0.1,
    branch_exchange_sensitivity=0.01,
    use_branch_exchange_sensitivity=True,
    branch_rating_contribution=1.0,
    use_branch_rating_contribution=True,
    consider_contingencies=True,
    opf_options=opf_options,
    lin_options=lin_options
)

drv = gce.OptimalNetTransferCapacityDriver(grid, ntc_options)

drv.run()

res = drv.results

drv.logger.print("Logger:")
print()
