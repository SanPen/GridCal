import os
import numpy as np
import pandas as pd
import GridCalEngine.api as gce
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import run_nonlinear_opf
from GridCalEngine.enumerations import AcOpfMode


def voltage_control_opf(file_path):
    """
    This case takes a real-life grid from REE and runs the OPF to achieve pilot bus voltage improvement
    """

    grid = gce.FileOpen(file_path).open()

    # the generators in these areas are the ones that we want to dispatch the reactive power
    disp_areas = ['A11', 'A15']

    # this is the information of the monitoring nodes whose voltage we want to have in range
    # code -> [lower voltage, upper voltage] kV
    dict_bus_lims = {'21215': [230, 225],
                     '11055': [410, 405],
                     '21075': [230, 225],
                     '25130': [230, 225],
                     '15005': [410, 405],
                     '15015': [410, 405]}

    # ------------------------------------------------------------------------------------------------------------------
    # Data wrangling
    # ------------------------------------------------------------------------------------------------------------------

    tol = 1e-4
    vm_cost = 1e4

    bus_set = set()

    for i, gen in enumerate(grid.generators):
        if gen.bus.is_slack or gen.bus.area.name in disp_areas:
            print(str(i) + ' pass')
            bus_set.add(i)
        elif gen.bus.area.name in disp_areas:
            # P limits -> restrict them very close to P
            print(i)
            bus_set.add(i)
            # gen.Pmax = gen.P + tol
            # gen.Pmin = gen.P - tol
            # Tanmax -> set pf close to 0 to get large tanmax
            # gen.Pf = tol
        else:
            pass
            # gen.enabled_dispatch = False
            # gen.Pmax = gen.P + tol
            # gen.Pmin = gen.P - tol

    print('reset i')
    bus_indices = list()
    bus_names = list()
    bus_codes = list()
    Vnom = list()
    Vmin = list()
    Vmax = list()
    pilot_flag = list()
    for i, bus in enumerate(grid.buses):
        is_pilot = False

        if bus.code in dict_bus_lims.keys():
            # Increase Vm slack cost to enforce limits
            # bus.Vm_cost = vm_cost
            # Redo Vm limits from the inputs
            vm_lims = dict_bus_lims[bus.code]
            # bus.Vmax = vm_lims[0] / bus.Vnom
            # bus.Vmin = vm_lims[1] / bus.Vnom
            bus_set.add(i)
            is_pilot = True

        if i in bus_set:
            bus_indices.append(i)
            bus_names.append(bus.name)
            bus_codes.append(bus.code)
            Vnom.append(bus.Vnom)
            Vmin.append(bus.Vmin)
            Vmax.append(bus.Vmax)
            pilot_flag.append(is_pilot)

    Vnom = np.array(Vnom)
    Vmax = np.array(Vmax)
    Vmin = np.array(Vmin)

    genlist = grid.get_generation_like_devices()
    dic = {gen.code: k for k, gen in enumerate(genlist)}

    # ------------------------------------------------------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------------------------------------------------------

    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    pf_vm = np.abs(power_flow.results.voltage[bus_indices])

    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF,
                                              acopf_mode=AcOpfMode.ACOPFstd,
                                              verbose=1,
                                              ips_iterations=250,
                                              ips_tolerance=1e-8)

    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                      verbose=3)

    opf_res = run_nonlinear_opf(grid=grid,
                                pf_options=pf_options,
                                opf_options=opf_options,
                                plot_error=True,
                                pf_init=True)

    opf_vm = opf_res.Vm[bus_indices]

    # ------------------------------------------------------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------------------------------------------------------

    df = pd.DataFrame({'Bus': bus_codes,
                       'Pilot bus': pilot_flag,
                       'Voltage pre (p.u.)': pf_vm,
                       'Voltage pre (kV)': pf_vm * Vnom,
                       'Vmin (kV)': Vmin * Vnom,
                       'Vmax (kV)': Vmax * Vnom,
                       'Voltage post (p.u.)': opf_vm,
                       'Voltage post (kV)': opf_vm * Vnom})

    print(df)


if __name__ == '__main__':
    voltage_control_opf(file_path='/home/santi/Escritorio/Redes/entrada_a_aopf.raw')
