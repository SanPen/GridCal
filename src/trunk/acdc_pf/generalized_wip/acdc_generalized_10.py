import os
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType
from GridCalEngine.enumerations import ConverterControlType
import GridCalEngine.api as gce
import faulthandler

faulthandler.enable()  # start @ the beginning
def run_time_5bus():
    """
    Check that a transformer can regulate the voltage at a bus
    """
    fname = os.path.abspath("C:/Users/raiya/Documents/8. eRoots/HVDCPAPER/leuvenTestCasesACDC/case5_3_he_fixed_controls_final.gridcal")
    # fname = "G:/.shortcut-targets-by-id/1B4zzyZBFXXFuEGTYGLt-sPLVc6VD2iL4/eRoots Analytics Shared Drive/Development/Project ACDC1 AC-DC Power Flow/Training grids/5714v2.gridcal"

    grid = gce.open_file(fname)

    options = PowerFlowOptions(SolverType.NR,
                               verbose=1,
                               control_q=False,
                               retry_with_other_methods=False,
                               control_taps_phase=False,
                               control_taps_modules=False,
                               max_iter=80,
                               tolerance=1e-8, )

    results = gce.power_flow(grid, options)

    # print(results.get_bus_df())
    # print(results.get_branch_df())
    # print("results.error", results.error)
    print("results.elapsed_time", results.elapsed)
    return results.elapsed
    # assert results.converged

def run_time_39bus():
    fname = os.path.abspath("C:/Users/raiya/Documents/8. eRoots/HVDCPAPER/leuvenTestCasesACDC/case39_10_he.gridcal")

    grid = gce.open_file(fname)

    # for j in range(len(grid.vsc_devices)):
    #     print(grid.vsc_devices[j].name)
    #     print("control1:", grid.vsc_devices[j].control1)
    #     print("control1val:", grid.vsc_devices[j].control1_val)
    #     print("control2:", grid.vsc_devices[j].control2)
    #     print("control2val:", grid.vsc_devices[j].control2_val)

    grid.vsc_devices[0].control1 = ConverterControlType.Pac
    grid.vsc_devices[1].control1 = ConverterControlType.Pac
    grid.vsc_devices[2].control1 = ConverterControlType.Pac
    grid.vsc_devices[3].control1 = ConverterControlType.Vm_dc
    grid.vsc_devices[3].control1_val = 1.0
    grid.vsc_devices[4].control1 = ConverterControlType.Pac
    grid.vsc_devices[5].control1 = ConverterControlType.Pac
    grid.vsc_devices[6].control1 = ConverterControlType.Pac
    grid.vsc_devices[7].control1 = ConverterControlType.Pac
    grid.vsc_devices[8].control1 = ConverterControlType.Pac
    grid.vsc_devices[9].control1 = ConverterControlType.Pac

    for dc_line in grid.dc_lines:
        dc_line.R = 0.005

    for j in range(len(grid.vsc_devices)):
        print(grid.vsc_devices[j].name)
        print("control1:", grid.vsc_devices[j].control1)
        print("control1val:", grid.vsc_devices[j].control1_val)
        print("control2:", grid.vsc_devices[j].control2)
        print("control2val:", grid.vsc_devices[j].control2_val)


    options = PowerFlowOptions(SolverType.NR,
                               verbose=1,
                               control_q=False,
                               retry_with_other_methods=False,
                               control_taps_phase=True,
                               control_taps_modules=True,
                               max_iter=80,
                               tolerance=1e-8, )

    results = gce.power_flow(grid, options)

    # print(results.get_bus_df())
    # print(results.get_branch_df())
    # print("results.error", results.error)
    print("results.elapsed_time", results.elapsed)
    return results.elapsed
    # assert results.converged


def run_time_3kbus():
    fname = os.path.abspath("C:/Users/raiya/Documents/8. eRoots/HVDCPAPER/leuvenTestCasesACDC/case3120_5_he.gridcal")

    grid = gce.open_file(fname)

    for dc_line in grid.dc_lines:
        dc_line.R = 0.005

    for j in range(len(grid.vsc_devices)):
        print(grid.vsc_devices[j].name)
        print("control1:", grid.vsc_devices[j].control1)
        print("control1val:", grid.vsc_devices[j].control1_val)
        print("control2:", grid.vsc_devices[j].control2)
        print("control2val:", grid.vsc_devices[j].control2_val)


    options = PowerFlowOptions(SolverType.NR,
                               verbose=1,
                               control_q=False,
                               retry_with_other_methods=False,
                               control_taps_phase=True,
                               control_taps_modules=True,
                               max_iter=80,
                               tolerance=1e-8, )

    results = gce.power_flow(grid, options)

    # print(results.get_bus_df())
    # print(results.get_branch_df())
    # print("results.error", results.error)
    # print("results.elapsed_time", results.elapsed)
    return results.elapsed
    # assert results.converged


def run_time_spanishGrid():
    fname = os.path.abspath("C:/Users/raiya/Documents/8. eRoots/HVDCPAPER/leuvenTestCasesACDC/202206011015_original.gridcal")

    grid = gce.open_file(fname)

    # for dc_line in grid.dc_lines:
    #     dc_line.R = 0.005

    # for j in range(len(grid.vsc_devices)):
    #     print(grid.vsc_devices[j].name)
    #     print("control1:", grid.vsc_devices[j].control1)
    #     print("control1val:", grid.vsc_devices[j].control1_val)
    #     print("control2:", grid.vsc_devices[j].control2)
    #     print("control2val:", grid.vsc_devices[j].control2_val)
    print("how many buses here?", len(grid.buses))

    options = PowerFlowOptions(SolverType.NR,
                               verbose=1,
                               control_q=False,
                               retry_with_other_methods=False,
                               control_taps_phase=False,
                               control_taps_modules=False,
                               max_iter=80,
                               tolerance=1e-8, )

    # results = gce.power_flow(grid, options)

    # print(results.get_bus_df())
    # print(results.get_branch_df())
    # print("results.error", results.error)
    # print("results.elapsed_time", results.elapsed)
    # return results.elapsed
    # assert results.converged




import numpy as np
elapsed = run_time_spanishGrid()
times = np.zeros((11))
for i in range(11):
    elapsed = run_time_spanishGrid()
    times[i] = elapsed

print("time list", times)
#delete outlier (more than 0.1 seconds)
# times = times[times < 0.1]
print("mean time for spanish grid:", np.mean(times))

