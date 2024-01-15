import os
import numpy as np
import time
import numba as nb
import cProfile
import math
import pstats
from scipy import sparse

from GridCalEngine.api import FileOpen
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at, NumericalCircuit
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis, LinearMultiContingencies
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import ContingencyAnalysisOptions, \
    ContingencyAnalysisDriver
from GridCalEngine.basic_structures import Vec, Mat, IntVec

from GridCalEngine.enumerations import BranchImpedanceMode
from GridCalEngine.Simulations.LinearFactors.srap import get_PTDF_LODF_NX_sparse_f16, compute_srap


def run_srap(numerical_circuit: NumericalCircuit, srap_limit: float = 1.4, pmax_mw: float = 1400.0):
    """

    :param numerical_circuit:
    :param srap_limit:
    :param pmax_mw:
    :return:
    """
    tm0 = time.time()

    print(f'[{time.time() - tm0:.2f} scs.]')

    print("Linear analysis")
    linear_analysis = LinearAnalysis(numerical_circuit=numerical_circuit,
                                     distributed_slack=False,
                                     correct_values=True)
    linear_analysis.run()

    linear_multiple_contingencies = LinearMultiContingencies(grid=grid)

    linear_multiple_contingencies.update(lodf=linear_analysis.LODF,
                                         ptdf=linear_analysis.PTDF,
                                         threshold=0.01)  # PTDF LODF threshold to make it sparse

    pmax = pmax_mw

    # get the monitored lines
    mon_idx = numerical_circuit.branch_data.get_monitor_enabled_indices()

    # get the rates
    rates = numerical_circuit.branch_data.rates

    # get the flows
    flows_n = linear_analysis.get_flows(numerical_circuit.Sbus) * numerical_circuit.Sbase

    # get the number of lines
    num_lines = len(rates)

    # this value should be studied according preferences
    p_available = numerical_circuit.generator_data.get_injections_per_bus().real

    # get ptdf, lodf, and p_available to reduce
    PTDF = linear_analysis.PTDF
    LODF = linear_analysis.LODF

    # reduce to float32
    PTDF = PTDF.astype(np.float32)
    LODF = LODF.astype(np.float32)
    p_available = p_available.astype(np.float32)

    # set the first conditions to run srap
    c1 = np.zeros(num_lines, dtype=bool)
    c1[mon_idx] = True  # If the line is being monitored

    time_ptdf_acum = 0
    time_compute_srap_acum = 0

    tm_total = time.time()

    print("Iterate contingencies")
    # for each contingency group
    for ic, multi_contingency in enumerate(linear_multiple_contingencies.multi_contingencies):

        if multi_contingency.has_injection_contingencies():
            injections = numerical_circuit.generator_data.get_injections().real
        else:
            injections = None

        # duda 1: esto lo quiero reducir del p_available. estas injections son positivas o negativas
        # p_available = np.strip(p_available-injections, 0, 999999999)

        # get the flows for every line with this contingency
        c_flow = multi_contingency.get_contingency_flows(base_flow=flows_n,
                                                         injections=injections)  # flujo ante contingencia variable

        # set remaining conditions
        c_flow_abs = np.abs(c_flow)
        # If the line is overloaded when a contingency takes place and
        # If the overload is lower that srap_limit, srap works
        # c2 and c3 are arrays with length=number of lines
        c2 = rates < c_flow_abs
        c3 = c_flow_abs <= srap_limit * rates
        cond = c1 * c2 * c3

        # set overloads, if 0 no overloads, if != 0 overloads . This is the load that exceeds rates
        ov = np.zeros(num_lines, dtype=np.float32)
        ov[cond] = (np.sign(c_flow[cond]) * (np.abs(c_flow[cond]) - rates[cond]))

        # set failed branches (might be more than one)
        branch_failed = multi_contingency.branch_indices.astype(int)

        # evaluate only lines with overloads, positives or negatives
        ov_exists = np.where(ov != 0)[0]  # ov_exists set the indexes of the lines with overloads

        if len(ov_exists):  # only evaluate this if we have any overloads

            time_ptdf1 = time.time()
            # compute PTDF_LODF_NX matrix. it is a ptdf updated with failed branches

            PTDF_LODF_NX = get_PTDF_LODF_NX_sparse_f16(PTDF, LODF, branch_failed, ov_exists)
            time_ptdf2 = time.time()
            time_ptdf_acum = time_ptdf_acum + (time_ptdf2 - time_ptdf1)

            # print(f'Mult in  {time.time() - time_ptdf:.2f} scs.')

            # run srap. results provide a true false array setting if srap can fix each overload
            # tm_srap = time.time()
            time_compute_srap1 = time.time()
            result = compute_srap(p_available, ov, pmax, branch_failed, PTDF_LODF_NX, ov_exists)
            time_compute_srap2 = time.time()
            time_compute_srap_acum = time_compute_srap_acum + (time_compute_srap2 - time_compute_srap1)

            # print(f'SRAP computed in {time.time() - tm_srap:.2f} scs.')

            # solved_by_srap = sum(result) * 100 / (sum(cond) + 1e-10)
            # print(f'SRAP solved {solved_by_srap:.2f} % of the  cases')

    print(f'Total mult time  {time_ptdf_acum:.3f} scs.')
    print(f'Total compute srap  {time_compute_srap_acum:.3f} scs.')
    print(f'Total time {time.time() - tm_total:.3f} scs.')


if __name__ == '__main__':
    # path = os.path.join(
    #     r'C:\Users\posmarfe\OneDrive - REDEIA\Escritorio\2023 MoU Pmode1-3\srap',
    #     '1_hour_MOU_2022_5GW_v6h-B_pmode1_withcont_1link.gridcal'
    # )

    path = os.path.join(
        r'C:\Users\posmarfe\OneDrive - REDEIA\Escritorio\2023 MoU Pmode1-3\srap',
        '15_Caso_2026.gridcal'
    )
    # path = '/home/santi/Descargas/15_Caso_2026.gridcal'
    # path = r"C:\ReposGit\github\fernpos\GridCal5\GridCal\Grids_and_profiles\grids\GB reduced network.gridcal"

    # pr = cProfile.Profile()
    # cProfile.run('run_srap(gridcal_path = path)', r'C:\Users\posmarfe\OneDrive - REDEIA\Escritorio')
    # ps = pstats.Stats(pr)
    # ps.strip_dirs().sort_stats('cumtime').print_stats(0.0001)

    print('Loading grical circuit... ', sep=' ')
    grid = FileOpen(path).open()

    numerical_circuit_ = compile_numerical_circuit_at(circuit=grid, t_idx=None)

    print("SRAP started")
    run_srap(numerical_circuit=numerical_circuit_, srap_limit=1.4, pmax_mw=1400)
