import os
import time
import numpy as np
from unittest import TestCase, TestLoader
from GridCal.Engine import basic_structures as bs
from GridCal.Engine import Devices as dev
from GridCal.Engine.Simulations.ATC.available_transfer_capacity_driver import AvailableTransferMode
from GridCal.Engine.Simulations.NTC.ntc_options import OptimalNetTransferCapacityOptions
from GridCal.Engine.Simulations.NTC.ntc_driver import OptimalNetTransferCapacityDriver
from GridCal.Engine.Simulations.NTC.ntc_ts_driver import OptimalNetTransferCapacityTimeSeriesDriver
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.basic_structures import SolverType
from GridCal.Engine import FileOpen


class TestCases(TestCase):

    # TestLoader.sortTestMethodsUsing = None

    def test_ntc_sn(self):
        tm0 = time.time()

        folder = r'\\mornt4.ree.es\DESRED\DPE-Internacional\Interconexiones\FRANCIA\2023 MoU Pmode3\Pmode3_conting\5GW\h_pmode1_esc_inst'
        fname = os.path.join(folder, r'unahorita_23_2_pmode1.gridcal')
        solution = 5502.0

        circuit = FileOpen(fname).open()

        areas_from_idx = [0]
        areas_to_idx = [1]

        areas_from = [circuit.areas[i] for i in areas_from_idx]
        areas_to = [circuit.areas[i] for i in areas_to_idx]

        lst_from = circuit.get_areas_buses(areas_from)
        lst_to = circuit.get_areas_buses(areas_to)

        idx_from = np.array([i for i, bus in lst_from])
        idx_to = np.array([i for i, bus in lst_to])

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
            consider_nx_contingencies=True,
            dispatch_all_areas=False,
            generation_contingency_threshold=1000,
            tolerance=1e-2,
            sensitivity_dT=100.0,
            transfer_method=AvailableTransferMode.InstalledPower,
            time_limit_ms=1e4,
            loading_threshold_to_report=98,
        )

        pf_options = PowerFlowOptions(
            solver_type=SolverType.DC
        )
        print('Running optimal net transfer capacity for snapshot...')

        # set optimal net transfer capacity driver instance
        driver = OptimalNetTransferCapacityDriver(
            grid=circuit,
            options=options,
            pf_options=pf_options,
        )

        driver.run()

        ttc = np.floor(driver.results.get_exchange_power())
        result = np.isclose(ttc, solution, atol=1)

        print(f'The computed TTC is {ttc}, the expected value is {solution}')
        print(f'Test result is {result}. Computed in {time.time()-tm0:.2f} scs.')

        self.assertTrue(result)

    def test_ntc_ts(self):
        tm0 = time.time()

        folder = r'\\mornt4.ree.es\DESRED\DPE-Internacional\Interconexiones\FRANCIA\2023 MoU Pmode3\Pmode3_conting\5GW\h_pmode1_esc_inst'
        fname = os.path.join(folder, r'MOU_2022_5GW_v6h-B_pmode1.gridcal')
        solution = [5502.0, 5502.0]
        start = 0
        end = 5

        circuit = FileOpen(fname).open()

        areas_from_idx = [0]
        areas_to_idx = [1]

        areas_from = [circuit.areas[i] for i in areas_from_idx]
        areas_to = [circuit.areas[i] for i in areas_to_idx]

        lst_from = circuit.get_areas_buses(areas_from)
        lst_to = circuit.get_areas_buses(areas_to)

        idx_from = np.array([i for i, bus in lst_from])
        idx_to = np.array([i for i, bus in lst_to])

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
            consider_nx_contingencies=True,
            dispatch_all_areas=False,
            generation_contingency_threshold=1000,
            tolerance=1e-2,
            sensitivity_dT=100.0,
            transfer_method=AvailableTransferMode.InstalledPower,
            time_limit_ms=1e4,
            loading_threshold_to_report=98,
        )

        print('Running optimal net transfer capacity for time series...')

        # set optimal net transfer capacity driver instance
        driver = OptimalNetTransferCapacityTimeSeriesDriver(
            grid=circuit,
            options=options,
            start_=start,
            end_=end,
            use_clustering=False,
            cluster_number=1)

        driver.run()

        ttc = [self.results[t].get_exchange_power() for t in range(start, end)]

        result = np.isclose(ttc, solution, atol=1)

        for t in range(start, end):
            print(f'The computed TTC is {ttc[t]}, the expected value is {solution[t]}')

        print(f'Test result is {result}. Computed in {time.time()-tm0:.2f} scs.')

        k=1

    def test_ntc_cluster_ts(self):
        tm0 = time.time()

        folder = r'\\mornt4.ree.es\DESRED\DPE-Internacional\Interconexiones\FRANCIA\2023 MoU Pmode3\Pmode3_conting\5GW\h_pmode1_esc_inst'
        fname = os.path.join(folder, r'MOU_2022_5GW_v6h-B_pmode1.gridcal')
        solution = [5502.0, 5502.0]
        n_cluster = 3

        circuit = FileOpen(fname).open()

        areas_from_idx = [0]
        areas_to_idx = [1]

        areas_from = [circuit.areas[i] for i in areas_from_idx]
        areas_to = [circuit.areas[i] for i in areas_to_idx]

        lst_from = circuit.get_areas_buses(areas_from)
        lst_to = circuit.get_areas_buses(areas_to)

        idx_from = np.array([i for i, bus in lst_from])
        idx_to = np.array([i for i, bus in lst_to])

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
            consider_nx_contingencies=True,
            dispatch_all_areas=False,
            generation_contingency_threshold=1000,
            tolerance=1e-2,
            sensitivity_dT=100.0,
            transfer_method=AvailableTransferMode.InstalledPower,
            time_limit_ms=1e4,
            loading_threshold_to_report=98,
        )

        print('Running optimal net transfer capacity for time series...')

        # set optimal net transfer capacity driver instance
        driver = OptimalNetTransferCapacityTimeSeriesDriver(
            grid=circuit,
            options=options,
            use_clustering=True,
            cluster_number=n_cluster)

        driver.run()


        ttc = [driver.results[t].get_exchange_power() for t in driver.results.time_indices]

        result = np.isclose(ttc, solution, atol=1)

        for t in range(driver.results.time_indices):
            print(f'The computed TTC is {ttc[t]}, the expected value is {solution[t]}')

        print(f'Test result is {result}. Computed in {time.time() - tm0:.2f} scs.')


if __name__ == '__main':
    TestCases.run()