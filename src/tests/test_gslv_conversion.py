# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import numpy as np
import GridCalEngine.api as gce
from GridCalEngine.Compilers.circuit_to_gslv import GSLV_AVAILABLE, pg, to_gslv


def CheckArr(arr, arr_expected, tol: float, name: str, test: str, verbose=False):
    """

    :param arr:
    :param arr_expected:
    :param tol:
    :param name:
    :param test:
    :param verbose:
    :return:
    """
    if arr.shape != arr_expected.shape:
        print('failed (shape):', name, test)
        return 1

    if np.allclose(arr, arr_expected, atol=tol):
        if verbose:
            print('ok:', name, test)
        return 0
    else:
        diff = arr - arr_expected
        print('failed:', name, test, '| max:', diff.max(), 'min:', diff.min())
        return 1


def compare_nc(nc_gslv: "pg.NumericalCircuit", nc_gc: gce.NumericalCircuit, tol: float):
    """

    :param nc_gslv:
    :param nc_gc:
    :param tol:
    :return:
    """
    errors = 0

    errors += CheckArr(nc_gslv.passive_branch_data.F, nc_gc.passive_branch_data.F, tol,
                       'BranchData', 'F')
    errors += CheckArr(nc_gslv.passive_branch_data.T, nc_gc.passive_branch_data.T, tol,
                       'BranchData', 'T')
    errors += CheckArr(nc_gslv.passive_branch_data.active, nc_gc.passive_branch_data.active, tol,
                       'BranchData', 'active')

    errors += CheckArr(nc_gslv.passive_branch_data.R, nc_gc.passive_branch_data.R, tol, 'BranchData', 'r')
    errors += CheckArr(nc_gslv.passive_branch_data.X, nc_gc.passive_branch_data.X, tol, 'BranchData', 'x')
    errors += CheckArr(nc_gslv.passive_branch_data.G, nc_gc.passive_branch_data.G, tol, 'BranchData', 'g')
    errors += CheckArr(nc_gslv.passive_branch_data.B, nc_gc.passive_branch_data.B, tol, 'BranchData', 'b')
    errors += CheckArr(nc_gslv.passive_branch_data.rates, nc_gc.passive_branch_data.rates, tol,
                       'BranchData', 'rates')
    errors += CheckArr(nc_gslv.passive_branch_data.virtual_tap_f, nc_gc.passive_branch_data.virtual_tap_f, tol,
                       'BranchData', 'vtap_f')
    errors += CheckArr(nc_gslv.passive_branch_data.virtual_tap_t, nc_gc.passive_branch_data.virtual_tap_t, tol,
                       'BranchData',
                       'vtap_t')

    errors += CheckArr(nc_gslv.active_branch_data.tap_module, nc_gc.active_branch_data.tap_module, tol,
                       'BranchData', 'tap_module')
    errors += CheckArr(nc_gslv.active_branch_data.tap_angle, nc_gc.active_branch_data.tap_angle, tol,
                       'BranchData', 'tap_angle')

    errors += CheckArr(nc_gslv.vsc_data.alpha1, nc_gc.vsc_data.alpha1, tol, 'BranchData', 'alpha1')
    errors += CheckArr(nc_gslv.vsc_data.alpha2, nc_gc.vsc_data.alpha2, tol, 'BranchData', 'alpha2')
    errors += CheckArr(nc_gslv.vsc_data.alpha3, nc_gc.vsc_data.alpha3, tol, 'BranchData', 'alpha3')

    # bus data
    # tpes = convert_bus_types(nc_gslv.bus_data.types)
    errors += CheckArr(nc_gslv.bus_data.active, nc_gc.bus_data.active, tol, 'BusData', 'active')
    errors += CheckArr(nc_gslv.bus_data.Vbus.real, nc_gc.bus_data.Vbus.real, tol, 'BusData', 'V0')
    errors += CheckArr(nc_gslv.bus_data.installed_power, nc_gc.bus_data.installed_power, tol,
                       'BusData', 'installed power')
    # CheckArr(tpes, nc_gc.bus_data.bus_types, tol, 'BusData', 'types')

    # generator data
    errors += CheckArr(nc_gslv.generator_data.bus_idx, nc_gc.generator_data.bus_idx, tol, 'GenData', 'bus_idx')
    errors += CheckArr(nc_gslv.generator_data.active, nc_gc.generator_data.active, tol, 'GenData', 'active')
    errors += CheckArr(nc_gslv.generator_data.p, nc_gc.generator_data.p, tol, 'GenData', 'P')
    errors += CheckArr(nc_gslv.generator_data.pf, nc_gc.generator_data.pf, tol, 'GenData', 'Pf')
    errors += CheckArr(nc_gslv.generator_data.v, nc_gc.generator_data.v, tol, 'GenData', 'v')
    errors += CheckArr(nc_gslv.generator_data.qmin, nc_gc.generator_data.qmin, tol, 'GenData', 'qmin')
    errors += CheckArr(nc_gslv.generator_data.qmax, nc_gc.generator_data.qmax, tol, 'GenData', 'qmax')

    # load data
    errors += CheckArr(nc_gslv.load_data.bus_idx, nc_gc.load_data.bus_idx, tol, 'LoadData', 'bus_idx')
    errors += CheckArr(nc_gslv.load_data.active, nc_gc.load_data.active.astype(int), tol, 'LoadData', 'active')
    errors += CheckArr(nc_gslv.load_data.S, nc_gc.load_data.S, tol, 'LoadData', 'S')
    errors += CheckArr(nc_gslv.load_data.I, nc_gc.load_data.I, tol, 'LoadData', 'I')
    errors += CheckArr(nc_gslv.load_data.Y, nc_gc.load_data.Y, tol, 'LoadData', 'Y')

    # shunt
    errors += CheckArr(nc_gslv.shunt_data.bus_idx, nc_gc.shunt_data.bus_idx, tol, 'ShuntData', 'bus_idx')
    errors += CheckArr(nc_gslv.shunt_data.active, nc_gc.shunt_data.active, tol, 'ShuntData', 'active')
    errors += CheckArr(nc_gslv.shunt_data.Y, nc_gc.shunt_data.Y, tol, 'ShuntData', 'Y')

    # ------------------------------------------------------------------------------------------------------------------
    #  Compare arrays and data
    # ------------------------------------------------------------------------------------------------------------------

    gslv_inj = nc_gslv.get_power_injections()
    gslv_types = nc_gslv.get_simulation_indices(gslv_inj.real)
    gslv_conn = nc_gslv.get_connectivity_matrices()
    gslv_adm = nc_gslv.get_admittance_matrices(gslv_conn)

    gc_inj = nc_gc.get_power_injections()
    gc_types = nc_gc.get_simulation_indices(gc_inj)
    gc_conn = nc_gc.get_connectivity_matrices()
    gc_adm = nc_gc.get_admittance_matrices()

    errors += CheckArr(gslv_inj.real, gc_inj.real, tol, 'Pbus', 'P')
    errors += CheckArr(gslv_inj.imag, gc_inj.imag, tol, 'Qbus', 'Q')

    errors += CheckArr(gslv_types.pq, gc_types.pq, tol, 'Types', 'pq')
    errors += CheckArr(gslv_types.pv, gc_types.pv, tol, 'Types', 'pv')
    errors += CheckArr(gslv_types.vd, gc_types.vd, tol, 'Types', 'vd')

    errors += CheckArr(gslv_conn.Cf.toarray(), gc_conn.Cf.toarray(), tol, 'Connectivity', 'Cf (dense)')
    errors += CheckArr(gslv_conn.Ct.toarray(), gc_conn.Ct.toarray(), tol, 'Connectivity', 'Ct (dense)')
    errors += CheckArr(gslv_conn.Cf.data, gc_conn.Cf.tocsc().data, tol, 'Connectivity', 'Cf')
    errors += CheckArr(gslv_conn.Ct.data, gc_conn.Ct.tocsc().data, tol, 'Connectivity', 'Ct')

    errors += CheckArr(gslv_adm.Ybus.toarray(), gc_adm.Ybus.toarray(), tol, 'Admittances', 'Ybus (dense)')
    errors += CheckArr(gslv_adm.Ybus.data.real, gc_adm.Ybus.tocsc().data.real, tol,
                       'Admittances', 'Ybus (real)')
    errors += CheckArr(gslv_adm.Ybus.data.imag, gc_adm.Ybus.tocsc().data.imag, tol,
                       'Admittances', 'Ybus (imag)')
    errors += CheckArr(gslv_adm.Yf.data.real, gc_adm.Yf.tocsc().data.real, tol, 'Admittances', 'Yf (real)')
    errors += CheckArr(gslv_adm.Yf.data.imag, gc_adm.Yf.tocsc().data.imag, tol, 'Admittances', 'Yf (imag)')
    errors += CheckArr(gslv_adm.Yt.data.real, gc_adm.Yt.tocsc().data.real, tol, 'Admittances', 'Yt (real)')
    errors += CheckArr(gslv_adm.Yt.data.imag, gc_adm.Yt.tocsc().data.imag, tol, 'Admittances', 'Yt (imag)')

    return errors


def compare_inputs(grid_gslv: "pg.MultiCircuit", grid_gc: gce.MultiCircuit, tol=1e-6, t_idx=None):
    """

    :param grid_gslv:
    :param grid_gc:
    :param tol:
    :param t_idx:
    :return:
    """
    # ------------------------------------------------------------------------------------------------------------------
    #  compile snapshots
    # ------------------------------------------------------------------------------------------------------------------

    if t_idx is None:
        nc_gslv = pg.compile(grid=grid_gslv, logger=pg.Logger(), t_idx=0)
        nc_gc = gce.compile_numerical_circuit_at(circuit=grid_gc, t_idx=None)
    else:
        nc_gslv = pg.compile(grid=grid_gslv, logger=pg.Logger(), t_idx=t_idx)
        nc_gc = gce.compile_numerical_circuit_at(circuit=grid_gc, t_idx=t_idx)

    # ------------------------------------------------------------------------------------------------------------------
    #  Compare base data
    errors = compare_nc(nc_gslv, nc_gc, tol)

    # compare islands

    gslv_islands = nc_gslv.split_into_islands()
    gc_islands = nc_gc.split_into_islands()

    assert len(gslv_islands) == len(gc_islands)

    for i in range(len(gslv_islands)):
        print("*" * 200)
        print("Comparing island", i)
        print("*" * 200)
        errors += compare_nc(gslv_islands[i], gc_islands[i], tol)

    return errors


def compare_power_flow(grid_gslv: "pg.MultiCircuit", grid_gc: gce.MultiCircuit, tol=1e-6):
    """

    :param grid_gslv:
    :param grid_gc:
    :param tol:
    :return:
    """
    gc_options = gce.PowerFlowOptions(gce.SolverType.NR,
                                      verbose=False,
                                      tolerance=1e-6,
                                      retry_with_other_methods=True,
                                      control_q=False,
                                      max_iter=15)
    gc_power_flow = gce.PowerFlowDriver(grid_gc, gc_options)
    gc_power_flow.run()
    gridcal_res = gc_power_flow.results

    pf_opt = pg.PowerFlowOptions(verbose=False,
                                 solver_type=pg.SolverType.NR,
                                 tolerance=1e-6,
                                 retry_with_other_methods=True,
                                 control_q_mode=False,
                                 max_iter=15)
    newton_res = pg.multi_island_pf(grid_gslv, pf_opt, 1, [0])

    errors = 0
    errors += CheckArr(np.abs(gridcal_res.voltage), np.abs(newton_res.voltage[0, :]), tol, 'V', 'abs')
    errors += CheckArr(gridcal_res.voltage.real, newton_res.voltage.real[0, :], tol, 'V', 'real')
    errors += CheckArr(gridcal_res.voltage.imag, newton_res.voltage.imag[0, :], tol, 'V', 'imag')
    errors += CheckArr(gridcal_res.Sf.real, newton_res.Sf.real[0, :], tol, 'Sf', 'real')
    errors += CheckArr(gridcal_res.Sf.imag, newton_res.Sf.imag[0, :], tol, 'Sf', 'imag')

    return errors


def test_gslv_compatibility():
    """

    :return:
    """

    if not GSLV_AVAILABLE:
        return

    files = [
        'IEEE 14 bus.raw',
        'IEEE 30 bus.raw',
        'IEEE 118 Bus v2.raw',
    ]

    for f1 in files:
        fname = os.path.join('data', 'grids', 'RAW', f1)

        print(f"Testing: {fname}")

        grid_gc = gce.open_file(filename=fname)

        # correct zero rates
        for br in grid_gc.get_branches():
            if br.rate <= 0:
                br.rate = 9999.0

        grid_gslv, gslv_dict = to_gslv(circuit=grid_gc,
                                       use_time_series=False,
                                       time_indices=None,
                                       override_branch_controls=False,
                                       opf_results=None)

        errors = compare_inputs(grid_gslv=grid_gslv,
                                grid_gc=grid_gc,
                                tol=1e-6,
                                t_idx=None)

        assert errors == 0


def test_gslv_compatibility_ts():
    """

    :return:
    """

    if not GSLV_AVAILABLE:
        return

    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')

    print(f"Testing: {fname}")

    grid_gc = gce.open_file(filename=fname)

    # correct zero rates
    for br in grid_gc.get_branches():
        if br.rate <= 0:
            br.rate = 9999.0

    grid_gslv, gslv_dict = to_gslv(circuit=grid_gc,
                                   use_time_series=True,
                                   time_indices=None,
                                   override_branch_controls=False,
                                   opf_results=None)

    for t_idx in range(grid_gc.get_time_number()):
        print("Time step:", t_idx)
        errors = compare_inputs(grid_gslv=grid_gslv,
                                grid_gc=grid_gc,
                                tol=1e-6,
                                t_idx=t_idx)

        assert errors == 0


def test_power_flow_ts():

    if not GSLV_AVAILABLE:
        return

    grid = gce.open_file(filename=os.path.join('data', 'grids', 'IEEE39_1W.gridcal'))

    options = gce.PowerFlowOptions(verbose=False,
                                   )

    drv = gce.PowerFlowTimeSeriesDriver(grid=grid,
                                        options=options,
                                        engine=gce.EngineType.GSLV)

    drv.run()

    res = drv.results


if __name__ == '__main__':
    # test_gslv_compatibility()
    # test_gslv_compatibility_ts()
    test_power_flow_ts()