import numpy as np
import GridCalEngine.api as gc

# MODELO TYNDP
# raw_path = r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2.raw"
# cgmes_path = [
#     r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\20230711T1201Z_ENTSO-E_EQ_BD_1574.xml",
#     r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\20230711T1201Z_ENTSO-E_TP_BD_1574.xml",
#     r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2_EQ.xml",
#     r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2_SSH.xml",
#     r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2_SV.xml",
#     r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2_TP.xml"
# ]
# one or list of files

# IEEE 14
raw_path = r'C:\Work\git_local\GridCal\Grids_and_profiles\grids\IEEE 14 bus.raw'
# cgmes_path = [r'C:\Work\git_local\GridCal\Grids_and_profiles\grids\IEEE14_topology.xml',
#               r'C:\Work\git_local\GridCal\Grids_and_profiles\grids\IEEE14_equipment_v16.xml']
cgmes_path = "C:\Work\gridDigIt Kft\External projects - Documents\REE\RAW_test_models\IEEE14_from_PF.zip"

circuit_1 = gc.open_file(raw_path)
circuit_1.buses.sort(key=lambda obj: obj.name)
circuit_2 = gc.open_file(cgmes_path)
circuit_2.buses.sort(key=lambda obj: obj.name)

nc_1 = gc.compile_numerical_circuit_at(circuit_1)
nc_2 = gc.compile_numerical_circuit_at(circuit_2)

# Compare Ybus: admittance matrix
# nc_1.Ybus     # sparse
# nc_1.Ybus.A   # dense version of Ybus, easier to compare
print(f'\n --- COMPARISON of Ybus ---')
print(f'Shape NC 1 = {nc_1.Ybus.A.shape}')
print(f'Shape NC 2 = {nc_2.Ybus.A.shape} \n')
print(f'Non-zero elements in NC 1 = {np.count_nonzero(nc_1.Ybus.A)}')
print(f'Non-zero elements in NC 2 = {np.count_nonzero(nc_2.Ybus.A)}')

# Set the tolerance (adjust as needed)
tolerance = 1e-6

# Perform element-wise comparison
comparison_result = np.isclose(nc_1.Ybus.A, nc_2.Ybus.A, atol=tolerance)

# Print the result
print("Element-wise comparison result:")
print(comparison_result)

# Compare Sbus: power injections --------------------------------------------
print(f'\n --- COMPARISON of Sbus  ---')
print(f'Shape NC 1 = {nc_1.Sbus.shape}')
print(f'Shape NC 2 = {nc_2.Sbus.shape} \n')
print(f'Non-zero elements in NC 1 = {np.count_nonzero(nc_1.Sbus)}')
print(f'Non-zero elements in NC 2 = {np.count_nonzero(nc_2.Sbus)}')

print(f'Sbus 1: {nc_1.Sbus}')
print(f'Sbus 1: {nc_2.Sbus}')

# TODO
# f1 = np.r_[nc_1.Sbus]
# f1 = np.r_[nc_1.Sbus[nc.pq].real, nc_1.Sbus[nc.pv].real, nc_1.Sbusnc.pq].imag]

print(np.isclose(nc_1.Sbus.real, nc_2.Sbus.real, atol=tolerance))
print(np.isclose(nc_1.Sbus.imag, nc_2.Sbus.imag, atol=tolerance))
print(np.isclose(nc_1.Sbus, nc_2.Sbus, atol=tolerance))
