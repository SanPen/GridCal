import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

real_df = pd.read_excel('Solutions/GridLAB-D/Time Series/Voltages_Load_#1_#32_#53_24hr.xlsx', sheet_name='Load #1')
real_df = real_df.drop(columns=['# timestamp'])
real_df['U_a_real'] = abs(real_df['voltage_A.real'] + 1j * real_df['voltage_A.imag']) / (416/np.sqrt(3))
real_df = real_df.drop(columns=['voltage_A.real', 'voltage_A.imag'])
print('Real dataframe:\n',real_df.head())

actual_df = pd.read_excel('three_phase_results.xlsx')
n_rows = len(actual_df)
bus_names = ['Source', 'Impedance'] + [f'Bus{i}' for i in range(1, n_rows - 1)]
actual_df['Bus'] = bus_names
actual_df = actual_df[['Bus'] + [col for col in actual_df.columns if col != 'Bus']]
print('Actual dataframe:\n',actual_df.head())

row_actual = actual_df[actual_df['Bus'] == 'Bus34']

time = row_actual.columns[1:]
actual_voltage = row_actual.iloc[0, 1:].values
real_voltage = real_df['U_a_real']

plt.figure(figsize=(10, 4))
plt.plot(time, actual_voltage)
plt.plot(time, real_voltage)
plt.title('Magnitudes para Bus34')
plt.xlabel('Time [min]')
plt.ylabel('Voltage [pu]')
plt.grid(True)
#plt.xticks(ticks=range(row.shape[1] - 1), labels=row.columns[1:], rotation=45)
plt.tight_layout()
plt.show()