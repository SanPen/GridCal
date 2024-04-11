import numpy as np
import GridCalEngine.api as gc

raw_path = r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2.raw"
cgmes_path = [r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\20230711T1201Z_ENTSO-E_EQ_BD_1574.xml",
              r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\20230711T1201Z_ENTSO-E_TP_BD_1574.xml",
              r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2_EQ.xml",
              r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2_SSH.xml",
              r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2_SV.xml",
              r"C:\Work\gridDigIt Kft\External projects - Documents\REE\CGMES test models\MODELO_TYNDP\TYNDP2024_2030NT_REE_v2.2_TP.xml"]
# one or list of files

circuit_1 = gc.open_file(raw_path)
circuit_2 = gc.open_file(cgmes_path)

nc_1 = gc.compile_numerical_circuit_at(circuit_1)
nc_2 = gc.compile_numerical_circuit_at(circuit_2)

# Compare Ybus: admittance
# nc_1.Ybus     # sparse
# nc_1.Ybus.A   # dense version of Ybus, easier to compare
print(f' --- COMPARISON ---')
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

# Compare Sbus: power injections
# nc_1.Sbus.A
print(f'Shape NC 1 = {nc_1.Sbus.shape}')
print(f'Shape NC 2 = {nc_2.Sbus.shape} \n')
print(f'Non-zero elements in NC 1 = {np.count_nonzero(nc_1.Sbus)}')
print(f'Non-zero elements in NC 2 = {np.count_nonzero(nc_2.Sbus)}')

np.isclose(nc_1.Sbus.real, nc_2.Sbus.real, atol=tolerance)
np.isclose(nc_1.Sbus.imag, nc_2.Sbus.imag, atol=tolerance)
np.isclose(nc_1.Sbus, nc_2.Sbus, atol=tolerance)
