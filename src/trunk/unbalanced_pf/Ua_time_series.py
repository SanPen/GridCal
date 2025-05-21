import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

"""
Real Dataframes
"""
Ua_real_df = pd.read_excel('Solutions/GridLAB-D/Time Series/Voltages_Load_#1_#32_#53_24hr.xlsx', sheet_name='Load #1')
Ua_real_df = Ua_real_df.drop(columns=['# timestamp'])
Ua_real_df['U_a_real'] = abs(Ua_real_df['voltage_A.real'] + 1j * Ua_real_df['voltage_A.imag']) / (416/np.sqrt(3))
Ua_real_df = Ua_real_df.drop(columns=['voltage_A.real', 'voltage_A.imag'])
Ua_real = Ua_real_df['U_a_real']

Ub_real_df = pd.read_excel('Solutions/GridLAB-D/Time Series/Voltages_Load_#1_#32_#53_24hr.xlsx', sheet_name='Load #53')
Ub_real_df = Ub_real_df.drop(columns=['# timestamp'])
Ub_real_df['U_b_real'] = abs(Ub_real_df['voltage_B.real'] + 1j * Ub_real_df['voltage_B.imag']) / (416/np.sqrt(3))
Ub_real_df = Ub_real_df.drop(columns=['voltage_B.real', 'voltage_B.imag'])
Ub_real = Ub_real_df['U_b_real']

Uc_real_df = pd.read_excel('Solutions/GridLAB-D/Time Series/Voltages_Load_#1_#32_#53_24hr.xlsx', sheet_name='Load #32')
Uc_real_df = Uc_real_df.drop(columns=['# timestamp'])
Uc_real_df['U_c_real'] = abs(Uc_real_df['voltage_C.real'] + 1j * Uc_real_df['voltage_C.imag']) / (416/np.sqrt(3))
Uc_real_df = Uc_real_df.drop(columns=['voltage_C.real', 'voltage_C.imag'])
Uc_real = Uc_real_df['U_c_real']

"""
Simulated Dataframes
"""
def load_simulations(df, bus):
    n_rows = len(df)
    bus_names = ['Source', 'Impedance'] + [f'Bus{i}' for i in range(1, n_rows - 1)]
    df['Bus'] = bus_names
    df = df[['Bus'] + [col for col in df.columns if col != 'Bus']]
    row_df = df[df['Bus'] == f'Bus{bus}']
    time = row_df.columns[1:]
    U_simulation = row_df.iloc[0, 1:].values

    return U_simulation, time

Ua_df = pd.read_excel('Ua_results.xlsx')
Ua_simulation, time_a = load_simulations(Ua_df, 34)

Ub_df = pd.read_excel('Ub_results.xlsx')
Ub_simulation, time_b = load_simulations(Ub_df, 900)

Uc_df = pd.read_excel('Uc_results.xlsx')
Uc_simulation, time_c = load_simulations(Uc_df, 614)

plt.figure(figsize=(10, 4))
plt.plot(time_a, Ua_real, label='Real A')
plt.plot(time_a, Uc_real, label='Real C')
plt.plot(time_a, Ub_real, label='Real B')
plt.title('Real Values')
plt.xlabel('Time [min]')
plt.ylabel('Voltage [pu]')
plt.grid(True)
plt.tight_layout()
plt.legend()
plt.show()

plt.figure(figsize=(10, 4))
plt.plot(time_a, Ua_simulation, label='Simulated A')
plt.plot(time_a, Uc_simulation, label='Simulated C')
plt.plot(time_a, Ub_simulation, label='Simulated B')
plt.title('Simulated Values')
plt.xlabel('Time [min]')
plt.ylabel('Voltage [pu]')
plt.grid(True)
plt.tight_layout()
plt.legend()
plt.show()

plt.figure(figsize=(10, 4))
plt.plot(time_a, Ua_simulation, label='Simulated')
plt.plot(time_a, Ua_real, label='Real')
plt.title('Bus34 - PhaseA')
plt.xlabel('Time [min]')
plt.ylabel('Voltage [pu]')
plt.grid(True)
plt.tight_layout()
plt.legend()
plt.show()

plt.figure(figsize=(10, 4))
plt.plot(time_b, Ub_simulation, label='Simulated')
plt.plot(time_b, Ub_real, label='Real')
plt.title('Bus900 - PhaseB')
plt.xlabel('Time [min]')
plt.ylabel('Voltage [pu]')
plt.grid(True)
plt.tight_layout()
plt.legend()
plt.show()

plt.figure(figsize=(10, 4))
plt.plot(time_c, Uc_simulation, label='Simulated')
plt.plot(time_c, Uc_real, label='Real')
plt.title('Bus614 - PhaseC')
plt.xlabel('Time [min]')
plt.ylabel('Voltage [pu]')
plt.grid(True)
plt.tight_layout()
plt.legend()
plt.show()