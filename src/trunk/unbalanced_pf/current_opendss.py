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

for bus in all_buses:
    circuit.SetActiveBus(bus)
    voltages = circuit.ActiveBus.VMagAngle  # [V1, ang1, V2, ang2, V3, ang3...]

    # print(f"\nBus {bus}:")
    for i in range(0, len(voltages), 2):
        magn = voltages[i]
        angle = voltages[i+1]
        fase = ["A", "B", "C"][i//2] if i//2 < 3 else f"F{i//2+1}"
        # print(f"  Fase {fase}: {magn:.6f} V, {angle:.2f}°")

I = np.zeros(3, dtype=complex)
Ibranch = np.zeros(3, dtype=complex)

#######################################################################################################################

for idx, load in enumerate(["Load.634a", "Load.634b", "Load.634c"]):
    circuit.SetActiveElement(load)
    currents = circuit.ActiveCktElement.CurrentsMagAng

    magn = currents[0]
    angle = currents[1]

    I[idx] = magn * np.exp(1j * np.deg2rad(angle))

    #print(f"{load}: {magn:.2f} A, {angle:.2f}°")

print("\nVector de corrientes [Ia, Ib, Ic]:")
print(I)

#######################################################################################################################

# for idx, load in enumerate(["Load.634ab", "Load.634bc", "Load.634ca"]):
#     circuit.SetActiveElement(load)
#     currents = circuit.ActiveCktElement.CurrentsMagAng
#
#     # Corriente de rama (primer terminal)
#     magn = currents[0]
#     angle = currents[1]
#     Ibranch[idx] = magn * np.exp(1j * np.deg2rad(angle))
#
# print("\nCorrientes de carga [Iab, Ibc, Ica]:")
# print(Ibranch)
#
# # Convertir corrientes de rama en corrientes de línea
# Ia = Ibranch[0] - Ibranch[2]   # Iab - Ica
# Ib = Ibranch[1] - Ibranch[0]   # Ibc - Iab
# Ic = Ibranch[2] - Ibranch[1]   # Ica - Ibc
# I = np.array([Ia, Ib, Ic])
# print("\nCorrientes de línea [Ia, Ib, Ic]:")
# print(I)

#######################################################################################################################

print("\nSuma de corrientes = ", np.abs(I[0] + I[1] + I[2]))