# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import numpy as np
import VeraGridEngine.api as gce
from VeraGridEngine.Compilers.circuit_to_gslv import GSLV_AVAILABLE, pg, to_gslv, compare_nc, CheckArr


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
    errors = compare_nc(nc_gslv=nc_gslv, nc_gc=nc_gc, tol=tol)

    # compare islands
    gslv_islands = nc_gslv.split_into_islands()
    gc_islands = nc_gc.split_into_islands()

    assert len(gslv_islands) == len(gc_islands)

    for i in range(len(gslv_islands)):
        print("*" * 200)
        print("Comparing island", i)
        print("*" * 200)
        errors += compare_nc(nc_gslv=gslv_islands[i], nc_gc=gc_islands[i], tol=tol)

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
        'AC-DC with all and DCload.gridcal',
        'RAW/IEEE 14 bus.raw',
        'RAW/IEEE 30 bus.raw',
        'RAW/IEEE 118 Bus v2.raw',
    ]

    for f1 in files:
        fname = os.path.join('data', 'grids', f1)

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

    options = gce.PowerFlowOptions(verbose=False)

    drv = gce.PowerFlowTimeSeriesDriver(grid=grid,
                                        options=options,
                                        engine=gce.EngineType.GSLV)

    drv.run()

    res = drv.results


def test_contingencies_ts():
    if not GSLV_AVAILABLE:
        return

    grid = gce.open_file(filename=os.path.join('data', 'grids', 'IEEE39_1W.gridcal'))

    options = gce.ContingencyAnalysisOptions(
        use_provided_flows=False,
        Pf=None,
        pf_options=gce.PowerFlowOptions(gce.SolverType.Linear),
        lin_options=gce.LinearAnalysisOptions(),
        use_srap=False,
        srap_max_power=1400.0,
        srap_top_n=5,
        srap_deadband=10,
        srap_rever_to_nominal_rating=False,
        detailed_massive_report=False,
        contingency_deadband=0.0,
        contingency_method=gce.ContingencyMethod.PowerFlow,
        contingency_groups=grid.contingency_groups
    )

    drv = gce.ContingencyAnalysisTimeSeriesDriver(grid=grid,
                                                  options=options,
                                                  engine=gce.EngineType.GSLV)

    drv.run()

    res = drv.results


def test_results_compatibility():
    """
    Test to check the 1:1 results of gslv
    :return:
    """

    if not GSLV_AVAILABLE:
        return

    paths = [
        # "data/grids/Matpower/case57.m",
        # "data/grids/Matpower/case3012wp.m"
        # "data/grids/Matpower/case16am.m"
    ]

    # run this one to compile the stuff
    folder = os.path.join("data", "grids", "Matpower")
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith(".m"):
                path = os.path.join(root, file)
                paths.append(path)

    for path in paths:
        fname = os.path.basename(path)

        grid = gce.open_file(filename=path)

        # if grid.get_bus_number() < 2000000000:
        print("^" * 100)
        print("Testing: ", fname)
        gslv_grid, _ = to_gslv(grid, use_time_series=False)

        inpt_err_number = 0
        # inpt_err_number = compare_inputs(grid_gslv=gslv_grid, grid_gc=grid)

        # power flow ---------------------------------------------------------------

        options = gce.PowerFlowOptions(verbose=0,
                                       use_stored_guess=True,
                                       retry_with_other_methods=False,
                                       solver_type=gce.SolverType.NR,
                                       control_q=False,
                                       tolerance=1e-8)

        drv_gc = gce.PowerFlowDriver(grid=grid,
                                     options=options,
                                     engine=gce.EngineType.VeraGrid)
        drv_gc.run()
        res_gc = drv_gc.results

        drv_gslv = gce.PowerFlowDriver(grid=grid,
                                       options=options,
                                       engine=gce.EngineType.GSLV)
        drv_gslv.run()
        res_gslv = drv_gslv.results

        all_ok, logger = res_gc.compare(res_gslv, tol=1e-4)

        if not all_ok or inpt_err_number > 0:
            logger.print(title=path)
            gce.save_file(grid=grid, filename=os.path.join("output", fname + ".gridcal"))
            print()
        assert all_ok


if __name__ == '__main__':
    # test_gslv_compatibility()
    # test_gslv_compatibility_ts()
    # test_power_flow_ts()
    # test_contingencies_ts()
    test_results_compatibility()
