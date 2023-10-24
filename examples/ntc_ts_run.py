import os
import GridCalEngine.basic_structures as bs
import GridCalEngine.Devices as dev
from GridCalEngine.api import *

folder = r'\\mornt4\DESRED\DPE-Planificacion\Plan 2021_2026\_0_TRABAJO\5_Plexos_PSSE\Peninsula\_2026_TRABAJO\Vesiones con alegaciones\Anexo II\TYNDP 2022 V2\5GW\Con N-x\merged\GridCal'
fname = os.path.join(folder, 'ES-PTv2--FR v4_fused - ts corta 5k.gridcal')

circuit = FileOpen(fname).open()

areas_from_idx = [0]
areas_to_idx = [1]

# areas_from_idx = [7]
# areas_to_idx = [0, 1, 2, 3, 4]

areas_from = [circuit.areas[i] for i in areas_from_idx]
areas_to = [circuit.areas[i] for i in areas_to_idx]

compatible_areas = True
for a1 in areas_from:
    if a1 in areas_to:
        compatible_areas = False
        print("The area from '{0}' is in the list of areas to. This cannot be.".format(a1.name),
              'Incompatible areas')

for a2 in areas_to:
    if a2 in areas_from:
        compatible_areas = False
        print("The area to '{0}' is in the list of areas from. This cannot be.".format(a2.name),
              'Incompatible areas')

lst_from = circuit.get_areas_buses(areas_from)
lst_to = circuit.get_areas_buses(areas_to)
lst_br = circuit.get_inter_areas_branches(areas_from, areas_to)
lst_br_hvdc = circuit.get_inter_areas_hvdc_branches(areas_from, areas_to)

idx_from = np.array([i for i, bus in lst_from])
idx_to = np.array([i for i, bus in lst_to])
idx_br = np.array([i for i, bus, sense in lst_br])
sense_br = np.array([sense for i, bus, sense in lst_br])
idx_hvdc_br = np.array([i for i, bus, sense in lst_br_hvdc])
sense_hvdc_br = np.array([sense for i, bus, sense in lst_br_hvdc])

if len(idx_from) == 0:
    print('The area "from" has no buses!')

if len(idx_to) == 0:
    print('The area "to" has no buses!')

if len(idx_br) == 0:
    print('There are no inter-area Branches!')


options = OptimalNetTransferCapacityOptions(
    area_from_bus_idx=idx_from,
    area_to_bus_idx=idx_to,
    mip_solver=bs.MIPSolvers.CBC,
    generation_formulation=dev.GenerationNtcFormulation.Proportional,
    monitor_only_sensitive_branches=True,
    branch_sensitivity_threshold=0.05,
    skip_generation_limits=True,
    consider_contingencies=True,
    consider_gen_contingencies=True,
    consider_hvdc_contingencies=True,
    generation_contingency_threshold=1000,
    dispatch_all_areas=False,
    lodf_tolerance=1e-2,
    sensitivity_dT=100.0,
    # transfer_mode=AvailableTransferMode.InstalledPower,
    # todo: checkear si queremos el ptdf por potencia generada
    perform_previous_checks=False,
    weight_power_shift=1e5,
    weight_generation_cost=1e2,
    time_limit_ms=1e4,
    loading_threshold_to_report=.98)

print('Running optimal net transfer capacity...')

# set optimal net transfer capacity driver instance
start = 5
end = 6  #circuit.get_time_number()-1

driver = OptimalNetTransferCapacityTimeSeriesDriver(
    grid=circuit,
    options=options,
    start_=start,
    end_=end,
    use_clustering=False,
    cluster_number=1)

driver.run()

driver.results.save_report(path_out=folder)
# driver.results.make_report()
