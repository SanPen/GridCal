import os
import time
import numpy as np
from GridCal.Engine import FileOpen
from GridCal.Engine.Core.numerical_circuit import compile_numerical_circuit_at
from GridCal.Engine.Core.Compilers.circuit_to_data2 import get_branch_data
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.Core.admittance_matrices import compute_linear_admittances
from GridCal.Engine.Core.multi_circuit import get_grouped_indices
from GridCal.Engine.Core.topology import find_different_states

def nc_snapshot():
    tm0 = time.time()

    folder = r'\\mornt4.ree.es\DESRED\DPE-Internacional\Interconexiones\FRANCIA\2023 MoU Pmode3\Pmode3_conting\5GW\h_pmode1_esc_inst'
    fname = os.path.join(folder, r'MOU_2022_5GW_v6h-B_pmode1.gridcal')
    solution = 5502.0

    tm_ = time.time()
    circuit = FileOpen(fname).open()
    print(f'Opened in {(time.time()-tm_):.2f} scs.')

    tm_ = time.time()
    nc = compile_numerical_circuit_at(
        circuit=circuit,
        t_idx=None
    )
    print(f'Compiled in {(time.time()-tm_):.2f} scs.')

    k=1

def nc_time_series(last_time_idx=None):
    tm0 = time.time()

    # folder = r'\\mornt4.ree.es\DESRED\DPE-Internacional\Interconexiones\FRANCIA\2023 MoU Pmode3\Pmode3_conting\5GW\h_pmode1_esc_inst'
    folder = r'C:\Users\ramferan\Downloads'
    fname = os.path.join(folder, r'MOU_2022_5GW_v6h-B_pmode1.gridcal')
    solution = 5502.0

    tm_ = time.time()
    circuit = FileOpen(fname).open()
    print(f'Opened in {(time.time() - tm_):.2f} scs.')

    tm_ = time.time()
    if not last_time_idx:
        last_time_idx = len(circuit.time_profile) + 1

    for i, t in enumerate(circuit.time_profile[:last_time_idx]):
        nc = compile_numerical_circuit_at(
            circuit=circuit,
            t_idx=i
        )
    total_time = time.time() - tm_
    print(f'Compiled {last_time_idx} full numerical circuits in {total_time:.2f} scs. '
          f'[{total_time/last_time_idx:.2f} scs. each]')

    tm_ = time.time()
    bus_dict = {bus: i for i, bus in enumerate(circuit.buses)}
    for i, t in enumerate(circuit.time_profile[:last_time_idx]):
        branch_data = get_branch_data(
            circuit=circuit,
            bus_dict=bus_dict,
            Vbus=np.ones(circuit.get_bus_number()),
            apply_temperature=False,
            branch_tolerance_mode=BranchImpedanceMode.Specified,
            t_idx=i,
            time_series=False,
            opf=False,
            opf_results=None,
            use_stored_guess=False
        )

    circuit.get_branches()
    total_time = time.time() - tm_
    print(f'Compiled {last_time_idx} only branch circuits in {total_time:.2f} scs. '
          f'[{total_time/last_time_idx:.2f} scs. each]')

    tm_ = time.time()
    for i, t in enumerate(circuit.time_profile[:last_time_idx]):
        Bbus, Bf, Btheta = compute_linear_admittances(
            nbr=circuit.get_branch_number(),
            X=branch_data.X,
            R=branch_data.R,
            tap_modules=branch_data.tap_module,
            active=branch_data.active,
            Cf=branch_data.C_branch_bus_f,
            Ct=branch_data.C_branch_bus_t,
            ac=branch_data.get_ac_indices(),
            dc=branch_data.get_dc_indices(),
        )
    total_time = time.time() - tm_
    print(f'Computed {last_time_idx} Bf matrices in {total_time:.2f} scs. '
          f'[{total_time/last_time_idx:.2f} scs. each]')

def check_indices_groups():
    folder = r'C:\Users\ramferan\Downloads'
    fname = os.path.join(folder, r'MOU_2022_5GW_v6h-B_pmode1.gridcal')

    tm_ = time.time()
    circuit = FileOpen(fname).open()
    print(f'Opened in {(time.time() - tm_):.2f} scs.')

    tm_ = time.time()
    actives = circuit.get_branch_active_time_array()

    # some changes, only for debugging. Creating 3 groups
    actives[100, :20] = 0
    actives[200:205, 30:40] = 0
    actives[300:315, 30:40] = 0
    actives[1000:1003, 1100:1300] = 0

    groups = get_grouped_indices(
        array=actives,
        axis=0
    )

    ncs = circuit.get_nc_by_time_index()

    total_time = time.time() - tm_
    print(f'Computed {len(groups)} topology groups in {total_time:.2f} scs. '
          f'[{total_time/len(groups):.2f} scs. each]')
    k = 1

def create_numerical_circuits():
    tm0 = time.time()

    # folder = r'\\mornt4.ree.es\DESRED\DPE-Internacional\Interconexiones\FRANCIA\2023 MoU Pmode3\Pmode3_conting\5GW\h_pmode1_esc_inst'
    folder = r'C:\Users\ramferan\Downloads'
    fname = os.path.join(folder, r'MOU_2022_5GW_v6h-B_pmode1.gridcal')
    solution = 5502.0

    tm_ = time.time()
    circuit = FileOpen(fname).open()
    print(f'Opened in {(time.time() - tm_):.2f} scs.')


    # for debugging purposes
    # some changes, only for debugging. Creating 3 groups
    topologic = circuit.get_branch_active_time_array()
    topologic[100, :20] = 0
    topologic[200:205, 30:40] = 0
    topologic[300:315, 30:40] = 0
    topologic[1000:1003, 1100:1300] = 0

    ttotal =0
    for i in range(10):
        tm_ = time.time()
        g_ = find_different_states(states_array=topologic)
        ttotal += time.time() - tm_

    print(f'Con find_different_statuis he tardado {ttotal/10:.02f} scs.')

    ttotal = 0
    for i in range(10):
        tm_ = time.time()
        groups = get_grouped_indices(
            array=topologic,
            axis=0
        )
        ttotal += time.time() - tm_
    print(f'Con numpy he tardado {ttotal/10:.02f} scs.')


    # groups = circuit.get_topologic_group_indices()
    ncs = np.empty(len(circuit.time_profile), dtype=object)

    for g in groups:
        ncs[g] = compile_numerical_circuit_at(
            circuit=circuit,
            t_idx=g[0]
        )

    k = 1

    # areas_from_idx = [0]
    # areas_to_idx = [1]
    #
    # areas_from = [circuit.areas[i] for i in areas_from_idx]
    # areas_to = [circuit.areas[i] for i in areas_to_idx]
    #
    # lst_from = circuit.get_areas_buses(areas_from)
    # lst_to = circuit.get_areas_buses(areas_to)
    #
    # idx_from = np.array([i for i, bus in lst_from])
    # idx_to = np.array([i for i, bus in lst_to])
    #
    # options = OptimalNetTransferCapacityOptions(
    #     area_from_bus_idx=idx_from,
    #     area_to_bus_idx=idx_to,
    #     mip_solver=bs.MIPSolvers.CBC,
    #     generation_formulation=dev.GenerationNtcFormulation.Proportional,
    #     monitor_only_sensitive_branches=True,
    #     branch_sensitivity_threshold=0.05,
    #     skip_generation_limits=True,
    #     consider_contingencies=True,
    #     consider_gen_contingencies=True,
    #     consider_hvdc_contingencies=True,
    #     consider_nx_contingencies=True,
    #     dispatch_all_areas=False,
    #     generation_contingency_threshold=1000,
    #     tolerance=1e-2,
    #     sensitivity_dT=100.0,
    #     transfer_method=AvailableTransferMode.InstalledPower,
    #     time_limit_ms=1e4,
    #     loading_threshold_to_report=98,
    # )
    #
    # pf_options = PowerFlowOptions(
    #     solver_type=SolverType.DC
    # )
    # print('Running optimal net transfer capacity for snapshot...')
    #
    # # set optimal net transfer capacity driver instance
    # driver = OptimalNetTransferCapacityDriver(
    #     grid=circuit,
    #     options=options,
    #     pf_options=pf_options,
    # )
    #
    # driver.run()
    #
    # ttc = np.floor(driver.results.get_exchange_power())
    # result = np.isclose(ttc, solution, atol=1)
    #
    # print(f'The computed TTC is {ttc}, the expected value is {solution}')
    # print(f'Test result is {result}. Computed in {time.time()-tm0:.2f} scs.')
    #
    # self.assertTrue(result)

# nc_time_series(last_time_idx=20)
# check_indices_groups()
create_numerical_circuits()