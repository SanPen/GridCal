import numpy as np
import pandas as pd
import newtonpa as npa
import GridCal.Engine as gce
import scipy.sparse as sp
from typing import List
from GridCal.Engine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.ac_jacobian import AC_jacobian
npa.findAndActivateLicense()


def convert_bus_types(arr: List["npa.BusType"]):

    tpe = np.zeros(len(arr), dtype=int)
    for i, val in enumerate(arr):
        if val == npa.BusType.VD:
            tpe[i] = 3
        elif val == npa.BusType.PV:
            tpe[i] = 2
        elif val == npa.BusType.PQ:
            tpe[i] = 1
    return tpe


def CheckArr(arr, arr_expected, tol, name, test):
    """

    :param arr:
    :param arr_expected:
    :param tol:
    :param name:
    :param test:
    :return:
    """
    if arr.shape != arr_expected.shape:
        print('failed (shape):', name, test)
        return 1

    if (np.abs(arr - arr_expected) < tol).all():
        print('ok:', name, test)
        return 0
    else:
        diff = arr - arr_expected
        print('failed:', name, test, '| max:', diff.max(), 'min:', diff.min())
        return 1


def loadArmadilloCooMat(file_name, is_complex=False):
    ydf = pd.read_csv(file_name, sep=" ", header=None)
    if is_complex:
        data = ydf.values[:, 2] + 1j * ydf.values[:, 3]
    else:
        data = ydf.values[:, 2]
    ii = ydf.values.astype(int)
    jj = ydf.values[:, 1].astype(int)
    return sp.coo_matrix((data, (ii, jj)), shape=(max(ii) + 1, max(jj) + 1)).tocsc()


def compare_inputs(grid_newton, grid_gc, tol=1e-6):

    # ------------------------------------------------------------------------------------------------------------------
    #  compile snapshots
    # ------------------------------------------------------------------------------------------------------------------

    nc_newton = npa.compileAt(grid_newton, 0)
    nc_gc = gce.compile_numerical_circuit_at(grid_gc, t_idx=0)

    # ------------------------------------------------------------------------------------------------------------------
    #  Compare data
    # ------------------------------------------------------------------------------------------------------------------

    CheckArr(nc_newton.branch_data.F, nc_gc.branch_data.F, tol, 'BranchData', 'F')
    CheckArr(nc_newton.branch_data.T, nc_gc.branch_data.T, tol, 'BranchData', 'T')
    CheckArr(nc_newton.branch_data.active, nc_gc.branch_data.active, tol, 'BranchData', 'active')
    CheckArr(nc_newton.branch_data.r, nc_gc.branch_data.R, tol, 'BranchData', 'r')
    CheckArr(nc_newton.branch_data.x, nc_gc.branch_data.X, tol, 'BranchData', 'x')
    CheckArr(nc_newton.branch_data.g, nc_gc.branch_data.G, tol, 'BranchData', 'g')
    CheckArr(nc_newton.branch_data.b, nc_gc.branch_data.B, tol, 'BranchData', 'b')
    CheckArr(nc_newton.branch_data.rates, nc_gc.branch_data.rates, tol, 'BranchData', 'rates')
    CheckArr(nc_newton.branch_data.tap_module, nc_gc.branch_data.tap_module, tol, 'BranchData', 'tap_module')
    CheckArr(nc_newton.branch_data.tap_angle, nc_gc.branch_data.tap_angle, tol, 'BranchData', 'tap_angle')

    CheckArr(nc_newton.branch_data.g0, nc_gc.branch_data.G0, tol, 'BranchData', 'g0')
    CheckArr(nc_newton.branch_data.G0sw, nc_gc.branch_data.G0sw, tol, 'BranchData', 'G0sw')
    CheckArr(nc_newton.branch_data.k, nc_gc.branch_data.k, tol, 'BranchData', 'k')
    CheckArr(nc_newton.branch_data.beq, nc_gc.branch_data.Beq, tol, 'BranchData', 'beq')
    CheckArr(nc_newton.branch_data.alpha1, nc_gc.branch_data.alpha1, tol, 'BranchData', 'alpha1')
    CheckArr(nc_newton.branch_data.alpha2, nc_gc.branch_data.alpha2, tol, 'BranchData', 'alpha2')
    CheckArr(nc_newton.branch_data.alpha3, nc_gc.branch_data.alpha3, tol, 'BranchData', 'alpha3')

    CheckArr(nc_newton.branch_data.vtap_f, nc_gc.branch_data.virtual_tap_f, tol, 'BranchData', 'vtap_f')
    CheckArr(nc_newton.branch_data.vtap_t, nc_gc.branch_data.virtual_tap_t, tol, 'BranchData', 'vtap_t')

    # bus data
    tpes = convert_bus_types(nc_newton.bus_data.types)
    CheckArr(nc_newton.bus_data.active, nc_gc.bus_data.active, tol, 'BusData', 'active')
    CheckArr(nc_newton.bus_data.v0.real, nc_gc.bus_data.Vbus.real, tol, 'BusData', 'V0')
    CheckArr(nc_newton.bus_data.installed_power, nc_gc.bus_data.installed_power, tol, 'BusData', 'installed power')
    CheckArr(tpes, nc_gc.bus_data.bus_types, tol, 'BusData', 'types')

    # generator data
    g_idx = [list(nc_gc.generator_data.names).index(x) for x in nc_newton.generator_data.names]
    CheckArr(nc_newton.generator_data.active, nc_gc.generator_data.active[g_idx].astype(int), tol, 'GenData', 'active')
    CheckArr(nc_newton.generator_data.P, nc_gc.generator_data.p[g_idx], tol, 'GenData', 'P')
    # CheckArr(nc_newton.generator_data.pf, nc_gc.generator_data.generator_pf[g_idx], tol, 'GenData', 'Pf')
    CheckArr(nc_newton.generator_data.vset, nc_gc.generator_data.v[g_idx], tol, 'GenData', 'Vset')
    CheckArr(nc_newton.generator_data.Qmin, nc_gc.generator_data.qmin[g_idx], tol, 'GenData', 'Qmin')
    CheckArr(nc_newton.generator_data.Qmax, nc_gc.generator_data.qmax[g_idx], tol, 'GenData', 'Qmax')

    # load data
    l_idx = [list(nc_gc.load_data.names).index(x) for x in nc_newton.load_data.names]
    CheckArr(nc_newton.load_data.active, nc_gc.load_data.active.astype(int)[l_idx], tol, 'LoadData', 'active')
    CheckArr(nc_newton.load_data.S, nc_gc.load_data.S[l_idx], tol, 'LoadData', 'S')
    CheckArr(nc_newton.load_data.I, nc_gc.load_data.I[l_idx], tol, 'LoadData', 'I')
    CheckArr(nc_newton.load_data.Y, nc_gc.load_data.Y[l_idx], tol, 'LoadData', 'Y')

    # shunt
    CheckArr(nc_newton.shunt_data.active, nc_gc.shunt_data.active, tol, 'ShuntData', 'active')
    CheckArr(nc_newton.shunt_data.S, nc_gc.shunt_data.admittance, tol, 'ShuntData', 'S')
    CheckArr(nc_newton.shunt_data.getInjectionsPerBus(), nc_gc.shunt_data.get_injections_per_bus(), tol, 'ShuntData', 'Injections per bus')

    # ------------------------------------------------------------------------------------------------------------------
    #  Compare arrays and data
    # ------------------------------------------------------------------------------------------------------------------

    newton_inj = nc_newton.getInjections()
    newton_types = nc_newton.getSimulationIndices(newton_inj.S0, False)
    newton_conn = nc_newton.getConnectivity()
    newton_adm = nc_newton.getAdmittances(newton_conn)

    CheckArr(newton_inj.S0.real, nc_gc.Sbus.real, tol, 'Pbus', 'P')
    CheckArr(newton_inj.S0.imag, nc_gc.Sbus.imag, tol, 'Qbus', 'Q')

    CheckArr(newton_types.pq, nc_gc.pq, tol, 'Types', 'pq')
    CheckArr(newton_types.pv, nc_gc.pv, tol, 'Types', 'pv')
    CheckArr(newton_types.vd, nc_gc.vd, tol, 'Types', 'vd')

    CheckArr(newton_conn.Cf.toarray(), nc_gc.Cf.toarray(), tol, 'Connectivity', 'Cf (dense)')
    CheckArr(newton_conn.Ct.toarray(), nc_gc.Ct.toarray(), tol, 'Connectivity', 'Ct (dense)')
    CheckArr(newton_conn.Cf.data, nc_gc.Cf.tocsc().data, tol, 'Connectivity', 'Cf')
    CheckArr(newton_conn.Ct.data, nc_gc.Ct.tocsc().data, tol, 'Connectivity', 'Ct')

    CheckArr(newton_adm.Ybus.toarray(), nc_gc.Ybus.toarray(), tol, 'Admittances', 'Ybus (dense)')
    CheckArr(newton_adm.Ybus.data.real, nc_gc.Ybus.tocsc().data.real, tol, 'Admittances', 'Ybus (real)')
    CheckArr(newton_adm.Ybus.data.imag, nc_gc.Ybus.tocsc().data.imag, tol, 'Admittances', 'Ybus (imag)')
    CheckArr(newton_adm.Yf.data.real, nc_gc.Yf.tocsc().data.real, tol, 'Admittances', 'Yf (real)')
    CheckArr(newton_adm.Yf.data.imag, nc_gc.Yf.tocsc().data.imag, tol, 'Admittances', 'Yf (imag)')
    CheckArr(newton_adm.Yt.data.real, nc_gc.Yt.tocsc().data.real, tol, 'Admittances', 'Yt (real)')
    CheckArr(newton_adm.Yt.data.imag, nc_gc.Yt.tocsc().data.imag, tol, 'Admittances', 'Yt (imag)')


    CheckArr(nc_newton.Vbus, nc_gc.Vbus, tol, 'NumericCircuit', 'V0')

    # ------------------------------------------------------------------------------------------------------------------
    #  Compare calculated arrays
    # ------------------------------------------------------------------------------------------------------------------

    J_newton = npa.getJacobian(nc_newton)
    J_gc = AC_jacobian(nc_gc.Ybus, nc_gc.Vbus, np.r_[nc_gc.pv, nc_gc.pq], nc_gc.pq)

    J_gc2 = AC_jacobian(newton_adm.Ybus, nc_newton.Vbus, np.r_[newton_types.pv, newton_types.pq], newton_types.pq)

    CheckArr(J_gc2.tocsc().data, J_gc.tocsc().data, tol, 'Jacobian', 'using GridCal function with newton data')
    CheckArr((J_newton - J_gc).data, np.zeros_like((J_newton - J_gc).data), tol, 'Jacobian', '')

    print("done!")


def compare_inputs_at(grid_newton, grid_gc, tol=1e-6, t = 0):

    err_count = 0

    # ------------------------------------------------------------------------------------------------------------------
    #  compile snapshots
    # ------------------------------------------------------------------------------------------------------------------

    nc_newton = npa.compileAt(grid_newton, t)
    nc_gc = compile_numerical_circuit_at(grid_gc, t)

    # ------------------------------------------------------------------------------------------------------------------
    #  Compare data
    # ------------------------------------------------------------------------------------------------------------------

    err_count += CheckArr(nc_newton.branch_data.F, nc_gc.branch_data.F, tol, 'BranchData', 'F')
    err_count += CheckArr(nc_newton.branch_data.T, nc_gc.branch_data.T, tol, 'BranchData', 'T')
    err_count += CheckArr(nc_newton.branch_data.active, nc_gc.branch_data.active, tol, 'BranchData', 'active')
    err_count += CheckArr(nc_newton.branch_data.r, nc_gc.branch_data.R, tol, 'BranchData', 'r')
    err_count += CheckArr(nc_newton.branch_data.x, nc_gc.branch_data.X, tol, 'BranchData', 'x')
    err_count += CheckArr(nc_newton.branch_data.g, nc_gc.branch_data.G, tol, 'BranchData', 'g')
    err_count += CheckArr(nc_newton.branch_data.b, nc_gc.branch_data.B, tol, 'BranchData', 'b')
    err_count += CheckArr(nc_newton.branch_data.rates, nc_gc.branch_data.rates, tol, 'BranchData', 'rates')
    err_count += CheckArr(nc_newton.branch_data.tap_module, nc_gc.branch_data.tap_module, tol, 'BranchData', 'tap_module')
    err_count += CheckArr(nc_newton.branch_data.tap_angle, nc_gc.branch_data.tap_angle, tol, 'BranchData', 'tap_angle')

    err_count += CheckArr(nc_newton.branch_data.g0, nc_gc.branch_data.G0, tol, 'BranchData', 'g0')
    err_count += CheckArr(nc_newton.branch_data.G0sw, nc_gc.branch_data.G0sw, tol, 'BranchData', 'G0sw')
    err_count += CheckArr(nc_newton.branch_data.k, nc_gc.branch_data.k, tol, 'BranchData', 'k')
    err_count += CheckArr(nc_newton.branch_data.beq, nc_gc.branch_data.Beq, tol, 'BranchData', 'beq')
    err_count += CheckArr(nc_newton.branch_data.alpha1, nc_gc.branch_data.alpha1, tol, 'BranchData', 'alpha1')
    err_count += CheckArr(nc_newton.branch_data.alpha2, nc_gc.branch_data.alpha2, tol, 'BranchData', 'alpha2')
    err_count += CheckArr(nc_newton.branch_data.alpha3, nc_gc.branch_data.alpha3, tol, 'BranchData', 'alpha3')
    err_count += CheckArr(nc_newton.branch_data.vtap_f, nc_gc.branch_data.virtual_tap_f, tol, 'BranchData', 'vtap_f')
    err_count += CheckArr(nc_newton.branch_data.vtap_t, nc_gc.branch_data.virtual_tap_t, tol, 'BranchData', 'vtap_t')

    # bus data
    tpes = convert_bus_types(nc_newton.bus_data.types)
    err_count += CheckArr(nc_newton.bus_data.active, nc_gc.bus_data.active, tol, 'BusData', 'active')
    err_count += CheckArr(nc_newton.bus_data.v0.real, nc_gc.bus_data.Vbus.real, tol, 'BusData', 'V0')
    err_count += CheckArr(nc_newton.bus_data.installed_power, nc_gc.bus_data.installed_power, tol, 'BusData', 'installed power')
    err_count += CheckArr(tpes, nc_gc.bus_data.bus_types, tol, 'BusData', 'types')

    # generator data
    g_idx = [list(nc_gc.generator_data.names).index(x) for x in nc_newton.generator_data.names]
    err_count += CheckArr(nc_newton.generator_data.active, nc_gc.generator_data.active[g_idx].astype(int), tol, 'GenData', 'active')
    err_count += CheckArr(nc_newton.generator_data.P, nc_gc.generator_data.p[g_idx], tol, 'GenData', 'P')
    # CheckArr(nc_newton.generator_data.pf, nc_gc.generator_data.pf[g_idx], tol, 'GenData', 'Pf')
    err_count += CheckArr(nc_newton.generator_data.vset, nc_gc.generator_data.v[g_idx], tol, 'GenData', 'Vset')
    err_count += CheckArr(nc_newton.generator_data.Qmin, nc_gc.generator_data.qmin[g_idx], tol, 'GenData', 'Qmin')
    err_count += CheckArr(nc_newton.generator_data.Qmax, nc_gc.generator_data.qmax[g_idx], tol, 'GenData', 'Qmax')
    err_count += CheckArr(nc_newton.generator_data.controllable, nc_gc.generator_data.controllable, tol, 'GenData', 'controllable')

    # load data
    l_idx = [list(nc_gc.load_data.names).index(x) for x in nc_newton.load_data.names]
    err_count += CheckArr(nc_newton.load_data.active, nc_gc.load_data.active.astype(int)[l_idx], tol, 'LoadData', 'active')
    err_count += CheckArr(nc_newton.load_data.S, nc_gc.load_data.S[l_idx], tol, 'LoadData', 'S')
    err_count += CheckArr(nc_newton.load_data.I, nc_gc.load_data.I[l_idx], tol, 'LoadData', 'I')
    err_count += CheckArr(nc_newton.load_data.Y, nc_gc.load_data.Y[l_idx], tol, 'LoadData', 'Y')

    # shunt
    err_count += CheckArr(nc_newton.shunt_data.active, nc_gc.shunt_data.active, tol, 'ShuntData', 'active')
    err_count += CheckArr(nc_newton.shunt_data.S, nc_gc.shunt_data.admittance, tol, 'ShuntData', 'S')
    err_count += CheckArr(nc_newton.shunt_data.getInjectionsPerBus(), nc_gc.shunt_data.get_injections_per_bus(), tol, 'ShuntData', 'Injections per bus')

    # ------------------------------------------------------------------------------------------------------------------
    #  Compare arrays and data
    # ------------------------------------------------------------------------------------------------------------------

    newton_inj = nc_newton.getInjections()
    newton_types = nc_newton.getSimulationIndices(newton_inj.S0, False)
    newton_conn = nc_newton.getConnectivity()
    newton_adm = nc_newton.getAdmittances(newton_conn)

    err_count += CheckArr(newton_inj.S0.real, nc_gc.Sbus.real, tol, 'Pbus', 'P')
    err_count += CheckArr(newton_inj.S0.imag, nc_gc.Sbus.imag, tol, 'Qbus', 'Q')

    err_count += CheckArr(newton_types.pq, nc_gc.pq, tol, 'Types', 'pq')
    err_count += CheckArr(newton_types.pv, nc_gc.pv, tol, 'Types', 'pv')
    err_count += CheckArr(newton_types.vd, nc_gc.vd, tol, 'Types', 'vd')

    err_count += CheckArr(newton_conn.Cf.toarray(), nc_gc.Cf.toarray(), tol, 'Connectivity', 'Cf (dense)')
    err_count += CheckArr(newton_conn.Ct.toarray(), nc_gc.Ct.toarray(), tol, 'Connectivity', 'Ct (dense)')
    err_count += CheckArr(newton_conn.Cf.data, nc_gc.Cf.tocsc().data, tol, 'Connectivity', 'Cf')
    err_count += CheckArr(newton_conn.Ct.data, nc_gc.Ct.tocsc().data, tol, 'Connectivity', 'Ct')

    err_count += CheckArr(newton_adm.Ybus.toarray(), nc_gc.Ybus.toarray(), tol, 'Admittances', 'Ybus (dense)')
    err_count += CheckArr(newton_adm.Ybus.data.real, nc_gc.Ybus.tocsc().data.real, tol, 'Admittances', 'Ybus (real)')
    err_count += CheckArr(newton_adm.Ybus.data.imag, nc_gc.Ybus.tocsc().data.imag, tol, 'Admittances', 'Ybus (imag)')
    err_count += CheckArr(newton_adm.Yf.data.real, nc_gc.Yf.tocsc().data.real, tol, 'Admittances', 'Yf (real)')
    err_count += CheckArr(newton_adm.Yf.data.imag, nc_gc.Yf.tocsc().data.imag, tol, 'Admittances', 'Yf (imag)')
    err_count += CheckArr(newton_adm.Yt.data.real, nc_gc.Yt.tocsc().data.real, tol, 'Admittances', 'Yt (real)')
    err_count += CheckArr(newton_adm.Yt.data.imag, nc_gc.Yt.tocsc().data.imag, tol, 'Admittances', 'Yt (imag)')

    err_count += CheckArr(nc_newton.Vbus, nc_gc.Vbus, tol, 'NumericCircuit', 'V0')

    # ------------------------------------------------------------------------------------------------------------------
    #  Compare calculated arrays
    # ------------------------------------------------------------------------------------------------------------------

    J_newton = npa.getJacobian(nc_newton)
    J_gc = AC_jacobian(nc_gc.Ybus, nc_gc.Vbus, np.r_[nc_gc.pv, nc_gc.pq], nc_gc.pq)

    J_gc2 = AC_jacobian(newton_adm.Ybus, nc_newton.Vbus, np.r_[newton_types.pv, newton_types.pq], newton_types.pq)

    err_count += CheckArr(J_gc2.tocsc().data, J_gc.tocsc().data, tol, 'Jacobian', 'using GridCal function with newton data')

    if J_newton.shape == J_gc.shape:
        err_count += CheckArr((J_newton - J_gc).data, np.zeros_like((J_newton - J_gc).data), tol, 'Jacobian', '')
    else:
        err_count += 1
        print("Different Jacobian shapes!")

    print("done!")

    return err_count


def compare_power_flow(grid_newton, grid_gc, tol=1e-6):

    gc_options = gce.PowerFlowOptions(gce.SolverType.NR,
                                      verbose=False,
                                      tolerance=1e-6,
                                      retry_with_other_methods=True,
                                      control_q=gce.ReactivePowerControlMode.NoControl,
                                      max_iter=15)
    gc_power_flow = gce.PowerFlowDriver(grid_gc, gc_options)
    gc_power_flow.run()
    gridcal_res = gc_power_flow.results

    pf_opt = npa.PowerFlowOptions(verbose=False,
                                  solver_type=npa.SolverType.NR,
                                  tolerance=1e-6,
                                  retry_with_other_methods=True,
                                  control_q_mode=npa.ReactivePowerControlMode.NoControl,
                                  max_iter=15)
    newton_res = npa.runPowerFlow(grid_newton, pf_opt, [0])

    CheckArr(np.abs(gridcal_res.voltage), np.abs(newton_res.voltage[0, :]), tol, 'V', 'abs')
    CheckArr(gridcal_res.voltage.real, newton_res.voltage.real[0, :], tol, 'V', 'real')
    CheckArr(gridcal_res.voltage.imag, newton_res.voltage.imag[0, :], tol, 'V', 'imag')

    CheckArr(gridcal_res.Sf.real, newton_res.Sf.real[0, :], tol, 'Sf', 'real')
    CheckArr(gridcal_res.Sf.imag, newton_res.Sf.imag[0, :], tol, 'Sf', 'imag')

    print()

