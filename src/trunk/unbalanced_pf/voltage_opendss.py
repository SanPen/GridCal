import dss
import numpy as np
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import polar_to_rect

# Crea el engine
engine = dss.DSS

# Cargar el circuito
engine.Text.Command = "ClearAll"
engine.Text.Command = r"Redirect C:/Users/alexb/OneDrive/eRoots/OpenDSS_Basics/13bus/full_trafo_validation.dss"
engine.Text.Command = "Solve"

# Acceder al circuito activo
circuit = engine.ActiveCircuit

# Lista de buses
all_buses = circuit.AllBusNames

# Base de tensión del circuito (en kV fase-fase)
Vbase_kV = 0.48    # <-- cámbialo según el nivel de tensión que te interese
Vbase = Vbase_kV * 1e3 / np.sqrt(3)  # base fase-neutro en V

Vpu = np.zeros(3, dtype=float)
ang = np.zeros(3, dtype=float)

circuit.SetActiveBus("634")  # ejemplo con bus 634
voltages = circuit.ActiveBus.VMagAngle  # [V1, ang1, V2, ang2, V3, ang3...]

for i in range(0, min(len(voltages), 6), 2):  # hasta 3 fases
    magn = voltages[i]       # magnitud en V
    angle = voltages[i+1]    # ángulo en grados
    idx = i // 2             # 0=A, 1=B, 2=C

    Vpu[idx] = magn / Vbase
    ang[idx] = angle

print("Voltages [pu]:", Vpu)
print("Angles [°]:", ang)

#######################################################################################################################
Vslack = np.zeros(3, dtype=complex)
Vslack[0] = 1 * np.exp(1j * (0*np.pi/180))
Vslack[1] = 1 * np.exp(1j * (-120*np.pi/180))
Vslack[2] = 1 * np.exp(1j * (120*np.pi/180))

Vload = np.zeros(3, dtype=complex)
Vload = Vpu * np.exp(1j * (ang*np.pi/180))

C = np.array([
    [(-0.06094868484727337+0.1108157906314061j), 0j, (0.06094868484727337-0.1108157906314061j)],
    [(0.06094868484727337-0.1108157906314061j), (-0.06094868484727337+0.1108157906314061j), 0j],
    [0j, (0.06094868484727337-0.1108157906314061j), (-0.06094868484727337+0.1108157906314061j)]
])

D = np.array([
    [(0.07037747920665388-0.12795905310300704j), (-0.03518873960332694+0.06397952655150352j), (-0.03518873960332694+0.06397952655150352j)],
    [(-0.03518873960332694+0.06397952655150352j), (0.07037747920665388-0.12795905310300704j), (-0.03518873960332694+0.06397952655150352j)],
    [(-0.03518873960332694+0.06397952655150352j), (-0.03518873960332694+0.06397952655150352j), (0.07037747920665388-0.12795905310300704j)]
])

Iload_pu = (D @ Vload) + (C @ Vslack)

print(Iload_pu * (100/3))

[-0.13850767+0.27999051j  0.29124339-0.07194752j -0.15273573-0.20804299j]