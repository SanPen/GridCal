import numpy as np
import GridCalEngine.api as gc
from GridCalEngine.IO import FileSave


def compare_inputs(circuit_1, circuit_2, tol=1e-6):
    # ------------------------------------------------------------------------------------------------------------------
    #  compile snapshots
    # ------------------------------------------------------------------------------------------------------------------

    nc_1 = gc.compile_numerical_circuit_at(circuit_1)
    nc_2 = gc.compile_numerical_circuit_at(circuit_2)

    # ------------------------------------------------------------------------------------------------------------------
    #  Compare data
    # ------------------------------------------------------------------------------------------------------------------

    CheckArr(nc_1.branch_data.F, nc_2.branch_data.F, tol, 'BranchData', 'F')
    CheckArr(nc_1.branch_data.T, nc_2.branch_data.T, tol, 'BranchData', 'T')
    CheckArr(nc_1.branch_data.active, nc_2.branch_data.active, tol,
             'BranchData', 'active')
    CheckArr(nc_1.branch_data.R, nc_2.branch_data.R, tol, 'BranchData', 'r')
    CheckArr(nc_1.branch_data.X, nc_2.branch_data.X, tol, 'BranchData', 'x')
    CheckArr(nc_1.branch_data.G, nc_2.branch_data.G, tol, 'BranchData', 'g')
    CheckArr(nc_1.branch_data.B, nc_2.branch_data.B, tol, 'BranchData', 'b')
    CheckArr(nc_1.branch_data.rates, nc_2.branch_data.rates, tol, 'BranchData',
             'rates')
    CheckArr(nc_1.branch_data.tap_module, nc_2.branch_data.tap_module, tol,
             'BranchData', 'tap_module')
    CheckArr(nc_1.branch_data.tap_angle, nc_2.branch_data.tap_angle, tol,
             'BranchData', 'tap_angle')

    CheckArr(nc_1.branch_data.G0, nc_2.branch_data.G0, tol, 'BranchData', 'g0')

    CheckArr(nc_1.branch_data.virtual_tap_f, nc_2.branch_data.virtual_tap_f,
             tol, 'BranchData', 'vtap_f')
    CheckArr(nc_1.branch_data.virtual_tap_t, nc_2.branch_data.virtual_tap_t,
             tol, 'BranchData', 'vtap_t')

    # bus data
    CheckArr(nc_1.bus_data.active, nc_2.bus_data.active, tol, 'BusData',
             'active')
    CheckArr(nc_1.bus_data.Vbus.real, nc_2.bus_data.Vbus.real, tol, 'BusData',
             'V0')
    CheckArr(nc_1.bus_data.installed_power, nc_2.bus_data.installed_power, tol,
             'BusData', 'installed power')
    CheckArr(nc_1.bus_data.bus_types, nc_2.bus_data.bus_types, tol, 'BusData',
             'types')

    # generator data
    CheckArr(nc_1.generator_data.active, nc_2.generator_data.active, tol,
             'GenData', 'active')
    CheckArr(nc_1.generator_data.p, nc_2.generator_data.p, tol, 'GenData', 'P')
    # CheckArr(nc_newton.generator_data.generator_pf, nc_gc.generator_data.generator_pf, tol, 'GenData', 'Pf')
    CheckArr(nc_1.generator_data.v, nc_2.generator_data.v, tol, 'GenData',
             'Vset')
    CheckArr(nc_1.generator_data.qmin, nc_2.generator_data.qmin, tol,
             'GenData', 'Qmin')
    CheckArr(nc_1.generator_data.qmax, nc_2.generator_data.qmax, tol,
             'GenData', 'Qmax')

    # load data
    CheckArr(nc_1.load_data.active, nc_2.load_data.active, tol, 'LoadData',
             'active')
    CheckArr(nc_1.load_data.S, nc_2.load_data.S, tol, 'LoadData', 'S')
    CheckArr(nc_1.load_data.I, nc_2.load_data.I, tol, 'LoadData', 'I')
    CheckArr(nc_1.load_data.Y, nc_2.load_data.Y, tol, 'LoadData', 'Y')

    # shunt
    CheckArr(nc_1.shunt_data.active, nc_2.shunt_data.active, tol, 'ShuntData',
             'active')
    CheckArr(nc_1.shunt_data.admittance, nc_2.shunt_data.admittance, tol,
             'ShuntData', 'S')
    CheckArr(nc_1.shunt_data.get_injections_per_bus(),
             nc_2.shunt_data.get_injections_per_bus(), tol, 'ShuntData',
             'Injections per bus')

    # ------------------------------------------------------------------------------------------------------------------
    #  Compare arrays and data
    # ------------------------------------------------------------------------------------------------------------------

    CheckArr(nc_1.Sbus.real, nc_2.Sbus.real, tol, 'Pbus', 'P')
    CheckArr(nc_1.Sbus.imag, nc_2.Sbus.imag, tol, 'Qbus', 'Q')

    CheckArr(nc_1.pq, nc_2.pq, tol, 'Types', 'pq')
    CheckArr(nc_1.pv, nc_2.pv, tol, 'Types', 'pv')
    CheckArr(nc_1.vd, nc_2.vd, tol, 'Types', 'vd')

    CheckArr(nc_1.Cf.toarray(), nc_2.Cf.toarray(), tol, 'Connectivity',
             'Cf (dense)')
    CheckArr(nc_1.Ct.toarray(), nc_2.Ct.toarray(), tol, 'Connectivity',
             'Ct (dense)')
    CheckArr(nc_1.Cf.tocsc().data, nc_2.Cf.tocsc().data, tol, 'Connectivity',
             'Cf')
    CheckArr(nc_1.Ct.tocsc().data, nc_2.Ct.tocsc().data, tol, 'Connectivity',
             'Ct')

    CheckArr(nc_1.Ybus.toarray(), nc_2.Ybus.toarray(), tol, 'Admittances',
             'Ybus (dense)')
    CheckArr(nc_1.Ybus.tocsc().data.real, nc_2.Ybus.tocsc().data.real, tol,
             'Admittances', 'Ybus (real)')
    CheckArr(nc_1.Ybus.tocsc().data.imag, nc_2.Ybus.tocsc().data.imag, tol,
             'Admittances', 'Ybus (imag)')
    CheckArr(nc_1.Yf.tocsc().data.real, nc_2.Yf.tocsc().data.realdata.real,
             tol, 'Admittances', 'Yf (real)')
    CheckArr(nc_1.Yf.tocsc().data.imag, nc_2.Yf.tocsc().data.imag, tol,
             'Admittances', 'Yf (imag)')
    CheckArr(nc_1.Yt.tocsc().data.real, nc_2.Yt.tocsc().data.real, tol,
             'Admittances', 'Yt (real)')
    CheckArr(nc_1.Yt.tocsc().data.imag, nc_2.Yt.tocsc().data.imag, tol,
             'Admittances', 'Yt (imag)')

    CheckArr(nc_1.Vbus, nc_2.Vbus, tol, 'NumericCircuit', 'V0')

    print("done!")


# def CheckArr(arr: Vec, arr_expected: Vec, tol: float, name: str, test: str, logger: Logger) -> None:
def CheckArr(arr, arr_expected, tol: float, name: str, test: str):
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

    if np.allclose(arr, arr_expected, atol=tol):
        print('ok:', name, test)
        return 0
    else:
        diff = arr - arr_expected
        print('failed:', name, test, '| max:', diff.max(), 'min:', diff.min())
        return 1


# MODELO TYNDP
cgmes_path = r"C:\Work\gridDigIt Kft\External projects - Documents\REE\test_models\cgmes_v2_4_15\cgmes_micro_grid_assmb_base\micro_grid_assmb_base.zip"

circuit_o = gc.open_file(cgmes_path)

nc_o = gc.compile_numerical_circuit_at(circuit_o)

# run power flow

# export to CGMES
# crate FileSave
cgmes_export = FileSave()
# boundary: micro grid Boundary
# gc.save_file() from FileHandler

# import the exported CGMES

# Compare with the original
