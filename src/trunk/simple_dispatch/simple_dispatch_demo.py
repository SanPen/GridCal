import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from GridCalEngine.Simulations.OPF.simple_dispatch_ts import greedy_dispatch

# === Simulation parameters ===
T = 24  # hours
L = 2  # loads
G = 3  # generators (e.g., 2 dispatchable + 1 solar)
B = 2  # batteries

np.random.seed(0)

# === Load profile (MW) ===
load = np.random.uniform(30, 50, size=(T, L))

# === Generator configuration ===
dispatchable = np.array([1, 1, 0])  # last generator is solar
active = np.ones((T, G), dtype=np.bool_)  # all active
cost_gen = np.tile(np.array([10.0, 20.0, 0.0]), (T, 1))  # solar is free

# === Generator output profile ===
gen_profile = np.zeros((T, G))
gen_profile[:, 0] = 50.0  # constant max for G0
gen_profile[:, 1] = 30.0  # constant max for G1
# Solar curve for G2
gen_profile[:, 2] = 40 * np.clip(np.sin(np.pi * (np.arange(T) - 6) / 12), 0, 1)

# === Battery parameters ===
p_max_charge = np.full((T, B), 10.0)
p_max_discharge = np.full((T, B), 10.0)
energy_max = np.full((T, B), 50.0)
eff_charge = np.full((T, B), 0.95)
eff_discharge = np.full((T, B), 0.9)
soc0 = np.full((B,), 20.0)
soc_min = np.full(B, 10.0)  # minimum 10 MWh
force_charge_if_low = True
dt = np.ones(T)

# === Run dispatch ===
gen_dispatch, batt_dispatch, soc, total_cost = greedy_dispatch(
    load, gen_profile, dispatchable, active, cost_gen,
    p_max_charge, p_max_discharge, energy_max,
    eff_charge, eff_discharge, soc0, soc_min, dt, force_charge_if_low
)

# === Aggregated values ===
load_total = np.sum(load, axis=1)
gen_total = np.sum(gen_dispatch, axis=1)
batt_total = np.sum(batt_dispatch, axis=1)
supply_total = gen_total + batt_total
load_not_supplied = load_total - supply_total

# === Create DataFrames ===
df_dispatch = pd.DataFrame(gen_dispatch, columns=[f'Gen_{i}' for i in range(G)])
for i in range(B):
    df_dispatch[f'Batt_{i}'] = batt_dispatch[:, i]
    df_dispatch[f'Batt_SoC_{i}'] = soc[:, i]

df_dispatch['Gen_total'] = gen_total
df_dispatch['Batt_total'] = batt_total
df_dispatch['Supply_total'] = supply_total
df_dispatch['Load_total'] = load_total
df_dispatch['Load not supplied'] = load_not_supplied

print("\nDispatch Summary:")
print(df_dispatch)
print(f"\nTotal Dispatch Cost: ${total_cost:.2f}")

# === Power Balance Plot ===
# plt.figure(figsize=(10, 5))
# plt.plot(load_total, label='Load Total', linewidth=2)
# plt.plot(supply_total, label='Gen + Battery Supply', linewidth=2)
# plt.plot(load_not_supplied, label='Imbalance', linestyle='--')
# plt.xlabel('Time step')
# plt.ylabel('Power [MW]')
# plt.title('Power Balance with Renewables')
# plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.show()
#
# # === Battery SoC Plot ===
# plt.figure(figsize=(10, 4))
# for i in range(B):
#     plt.plot(soc[:, i], label=f'SoC Battery {i}')
# plt.xlabel('Time step')
# plt.ylabel('Energy [MWh]')
# plt.title('Battery State of Charge Over Time')
# plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.show()
#
# # === Generator Contributions Plot ===
# plt.figure(figsize=(10, 5))
# for g in range(G):
#     plt.plot(gen_dispatch[:, g], label=f'Gen_{g}{" (Solar)" if dispatchable[g]==0 else ""}')
# plt.xlabel('Time step')
# plt.ylabel('Power [MW]')
# plt.title('Generator Dispatch by Source')
# plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.show()
