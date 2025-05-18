import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from GridCalEngine.Simulations.OPF.simple_dispatch_ts import fast_dispatch_with_renewables
import GridCalEngine.api as gce

fname = os.path.join("..", "..", "..", "Grids_and_profiles", "grids", "IEEE39_1W.gridcal")
grid = gce.open_file(fname)
#
# # === Simulation parameters ===
# T = 24   # hours
# L = 2    # loads
# G = 3    # generators (e.g., 2 dispatchable + 1 solar)
# B = 2    # batteries
# dt = 1.0
#
# np.random.seed(0)
#
# # === Load profile (MW) ===
# load = np.random.uniform(30, 50, size=(T, L))
#
# # === Generator configuration ===
# dispatchable = np.array([1, 1, 0])  # last generator is solar
# active = np.ones((T, G), dtype=np.bool_)  # all active
# cost_gen = np.tile(np.array([10.0, 20.0, 0.0]), (T, 1))  # solar is free
#
# # === Generator output profile ===
# gen_profile = np.zeros((T, G))
# gen_profile[:, 0] = 50.0  # constant max for G0
# gen_profile[:, 1] = 30.0  # constant max for G1
# # Solar curve for G2
# gen_profile[:, 2] = 40 * np.clip(np.sin(np.pi * (np.arange(T) - 6) / 12), 0, 1)
#
# # === Battery parameters ===
# p_max_charge = np.full((T, B), 10.0)
# p_max_discharge = np.full((T, B), 10.0)
# energy_max = np.full((T, B), 50.0)
# eff_charge = np.full((T, B), 0.95)
# eff_discharge = np.full((T, B), 0.9)
# soc0 = np.full((B,), 20.0)
# soc_min = np.full(B, 10.0)  # minimum 10 MWh
# force_charge_if_low = True

nt = grid.get_time_number()
nl = grid.get_loads_number()
ng = grid.get_generators_number()
nb = grid.get_batteries_number()

# loads
load = np.zeros((nt, nl))
for i, elm in enumerate(grid.loads):
    load[:, i] = elm.P_prof.toarray()

# generators
gen_profile = np.zeros((nt, ng))
dispatchable = np.zeros(ng, dtype=int)
gen_active = np.zeros((nt, ng), dtype=int)
gen_cost = np.zeros((nt, ng))
for i, elm in enumerate(grid.generators):
    gen_profile[:, i] = elm.P_prof.toarray()
    gen_active[:, i] = elm.active_prof.toarray()
    gen_cost[:, i] = elm.Cost_prof.toarray()
    dispatchable[i] = elm.enabled_dispatch

# batteries
p_max_charge = np.zeros((nt, nb), dtype=int)
p_max_discharge = np.zeros((nt, nb), dtype=int)
energy_max = np.zeros((nt,nb), dtype=int)
eff_charge = np.zeros((nt,nb), dtype=int)
eff_discharge = np.zeros((nt,nb), dtype=int)
soc0 = np.zeros(nb, dtype=int) + 0.5
soc_min = np.zeros(nb, dtype=int) + 0.1
for i, elm in enumerate(grid.batteries):
    p_max_charge[:, i] = elm.Pmax * 0.5
    p_max_discharge[:, i] = elm.Pmax * 0.5
    energy_max[:, i] = elm.Enom
    eff_charge[:, i] = elm.charge_efficiency if elm.charge_efficiency > 0.0 else 1.0
    eff_discharge[:, i] = elm.discharge_efficiency if elm.discharge_efficiency > 0.0 else 1.0
    soc0[i] = elm.Enom * 0.5
    soc_min[i] = elm.Enom * elm.min_soc

dt=grid.get_time_deltas_in_hours()

# === Run dispatch ===
gen_dispatch, batt_dispatch, soc, total_cost = fast_dispatch_with_renewables(
    load_profile=load,
    gen_profile=gen_profile,
    gen_dispatchable=dispatchable,
    gen_active=gen_active,
    gen_cost=gen_cost,
    batt_p_max_charge=p_max_charge,
    batt_p_max_discharge=p_max_discharge,
    batt_energy_max=energy_max,
    batt_eff_charge=eff_charge,
    batt_eff_discharge=eff_discharge,
    batt_soc0=soc0,
    batt_soc_min=soc_min,
    dt=dt,
    force_charge_if_low=True
)

# === Aggregated values ===
load_total = np.sum(load, axis=1)
gen_total = np.sum(gen_dispatch, axis=1)
batt_total = np.sum(batt_dispatch, axis=1)
supply_total = gen_total + batt_total
load_not_supplied = load_total - supply_total

# === Create DataFrames ===
df_dispatch = pd.DataFrame(gen_dispatch, columns=[f'Gen_{i}' for i in range(ng)])
for i in range(nb):
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
