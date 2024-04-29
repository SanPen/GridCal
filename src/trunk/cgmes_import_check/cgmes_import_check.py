import numpy as np
import GridCalEngine.api as gc


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


def CheckArr(arr: Vec, arr_expected: Vec, tol: float, name: str, test: str, logger: Logger) -> None:
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
raw_path = r"C:\Work\gridDigIt Kft\External projects - Documents\REE\test_models\cgmes_v2_4_15\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2.raw"
cgmes_path = [
    r"C:\Work\gridDigIt Kft\External projects - Documents\REE\test_models\cgmes_v2_4_15\MODELO_TYNDP\20230711T1201Z_ENTSO-E_EQ_BD_1574.xml",
    r"C:\Work\gridDigIt Kft\External projects - Documents\REE\test_models\cgmes_v2_4_15\MODELO_TYNDP\20230711T1201Z_ENTSO-E_TP_BD_1574.xml",
    r"C:\Work\gridDigIt Kft\External projects - Documents\REE\test_models\cgmes_v2_4_15\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2_EQ.xml",
    r"C:\Work\gridDigIt Kft\External projects - Documents\REE\test_models\cgmes_v2_4_15\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2_SSH.xml",
    r"C:\Work\gridDigIt Kft\External projects - Documents\REE\test_models\cgmes_v2_4_15\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2_SV.xml",
    r"C:\Work\gridDigIt Kft\External projects - Documents\REE\test_models\cgmes_v2_4_15\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2_TP.xml"
]
# one or list of files

# IEEE 14
# raw_path = r'C:\Work\git_local\GridCal\Grids_and_profiles\grids\IEEE 14 bus.raw'
# # cgmes_path = [r'C:\Work\git_local\GridCal\Grids_and_profiles\grids\IEEE14_topology.xml',
# #               r'C:\Work\git_local\GridCal\Grids_and_profiles\grids\IEEE14_equipment_v16.xml']
# cgmes_path = "C:\Work\gridDigIt Kft\External projects - Documents\REE\RAW_test_models\IEEE14_from_PF.zip"

circuit_1 = gc.open_file(raw_path)
circuit_1.buses.sort(key=lambda obj: obj.name)
circuit_2 = gc.open_file(cgmes_path)
circuit_2.buses.sort(key=lambda obj: obj.name)

err, logger = circuit_1.compare_circuits(circuit_2, detailed_profile_comparison=False)
print(logger.to_df())
logger.to_df().to_csv('logger_comparison.csv')
compare_inputs(circuit_1, circuit_2)

# nc_1 = gc.compile_numerical_circuit_at(circuit_1)
# nc_2 = gc.compile_numerical_circuit_at(circuit_2)
#
# # Compare Ybus: admittance matrix
# # nc_1.Ybus     # sparse
# # nc_1.Ybus.A   # dense version of Ybus, easier to compare
# print(f'\n --- COMPARISON of Ybus ---')
# print(f'Shape NC 1 = {nc_1.Ybus.A.shape}')
# print(f'Shape NC 2 = {nc_2.Ybus.A.shape} \n')
# print(f'Non-zero elements in NC 1 = {np.count_nonzero(nc_1.Ybus.A)}')
# print(f'Non-zero elements in NC 2 = {np.count_nonzero(nc_2.Ybus.A)}')
# print(nc_1.Ybus.A[0:10, 0:10])
# print(nc_2.Ybus.A[0:10, 0:10])
#
# # Set the tolerance (adjust as needed)
# tolerance = 1e-6
#
# # Perform element-wise comparison
# comparison_result = np.isclose(nc_1.Ybus.A, nc_2.Ybus.A, atol=tolerance)
#
# # Print the result
# print("Element-wise comparison result:")
# print(comparison_result)
#
# # Compare Sbus: power injections --------------------------------------------
# print(f'\n --- COMPARISON of Sbus  ---')
# print(f'Shape NC 1 = {nc_1.Sbus.shape}')
# print(f'Shape NC 2 = {nc_2.Sbus.shape} \n')
# print(f'Non-zero elements in NC 1 = {np.count_nonzero(nc_1.Sbus)}')
# print(f'Non-zero elements in NC 2 = {np.count_nonzero(nc_2.Sbus)}')
#
# print(f'Sbus 1: {nc_1.Sbus}')
# print(f'Sbus 1: {nc_2.Sbus}')
#
# # TODO
#
# print(np.isclose(nc_1.Sbus.real, nc_2.Sbus.real, atol=tolerance))
# print(np.isclose(nc_1.Sbus.imag, nc_2.Sbus.imag, atol=tolerance))
# print(np.isclose(nc_1.Sbus, nc_2.Sbus, atol=tolerance))
#
# f1 = np.r_[nc_1.Sbus[nc_1.pq].real, nc_1.Sbus[nc_1.pv].real, nc_1.Sbus[nc_1.pq].imag]
# f2 = np.r_[nc_2.Sbus[nc_2.pq].real, nc_2.Sbus[nc_2.pv].real, nc_2.Sbus[nc_2.pq].imag]
# print(f1)
# print(f2)
# print(np.isclose(f1, f2, atol=tolerance))
#
# print(f'End of import check!')

