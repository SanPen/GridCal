# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import pdb

import pandas as pd
import matplotlib.pyplot as plt

def merge_simulation_results_by_time(csv1, csv2, output_csv= 'merged_data.csv', time_col='Time [s]'):
    """
    Merge two simulation result CSVs by matching nearest time steps.

    Parameters:
    ----------
    csv1 : str
        Path to the first CSV file.
    csv2 : str
        Path to the second CSV file.
    output_csv : str or None
        Path to save the merged CSV. If None, the result is not saved.
    time_col : str
        Name of the time column in both CSVs.

    Returns:
    -------
    merged_df : pd.DataFrame
        The merged DataFrame.
    """

    # Load both CSV files
    df1 = pd.read_csv(csv1)
    df2 = pd.read_csv(csv2)

    # Sort both by time column
    df1 = df1.sort_values(by=time_col)
    df2 = df2.sort_values(by=time_col)

    # Using merge_asof to align by closest time
    merged_df = pd.merge_asof(
        df1, df2,
        on=time_col,
        direction='nearest',
        suffixes=('_sim1', '_sim2')
    )

    if output_csv:
        merged_df.to_csv(output_csv, index=False)
        print(f"Merged results saved to: {output_csv}")

    return merged_df

comparison = merge_simulation_results_by_time('simulation_results.csv', 'simulation_andes_output.csv')

# Load merged CSV
i = 3
merged_df = comparison
merged_df['Pl_7_Gridcal'] = merged_df['Pl_7_Gridcal'] * (-100)
merged_df[f"tm_{i}_Gridcal"] = merged_df[f"tm_{i}_Gridcal"] * (100)
merged_df[f"t_e_{i}_Gridcal"] = merged_df[f"t_e_{i}_Gridcal"] * (100)
# Define variable pairs to compare (each pair goes into one subplot)


variable_pairs = [
     [f"omega_{i}_Gridcal", f"omega_andes_gen_{i}"],
     ['Pl_7_Gridcal', 'Ppf_andes_load_0'],
     [f"tm_{i}_Gridcal", f"tm_andes_gen_{i}"],
     [f"t_e_{i}_Gridcal", f"te_andes_gen_{i}"]

    #  ['tm_2_Gridcal', 'tm_andes_gen_2'],
    #  ['tm_3_Gridcal', 'tm_andes_gen_3'],
    #  ['tm_4_Gridcal', 'tm_andes_gen_4'],
    #  ['omega_2_Gridcal', 'omega_andes_gen_2'],
    #  ['omega_3_Gridcal', 'omega_andes_gen_3'],
    #  ['omega_4_Gridcal', 'omega_andes_gen_4'],
     #['omega2_Gridcal', 'omega_andes_gen_2'],
     #['omega3_Gridcal', 'omega_andes_gen_3'],
     #['omega4_Gridcal', 'omega_andes_gen_4']
         #  ['Vline_from_12_Gridcal', 'v_andes_Bus_2'],
    #  ['Vline_from_11_Gridcal', 'v_andes_Bus_1'],
    #  ['Vline_from_14_Gridcal', 'v_andes_Bus_4'],
    #  ['Vline_from_13_Gridcal', 'v_andes_Bus_3'],
]

# Automatically detect time columns
time_column = merged_df['Time [s]']
time_columns = [col for col in merged_df.columns if 'Time [s]' in col.lower()]
time1 = time_column

#time1 = merged_df[time_columns]
#time2 = merged_df[time_columns[1]] if len(time_columns) > 1 else time1  # fallback to same time

# Create subplots
n = len(variable_pairs)
cols = 2
rows = (n + 1) // cols

fig, axes = plt.subplots(rows, cols, figsize=(16, 4 * rows), sharex=True)
axes = axes.flatten()
for idx, (var1, var2) in enumerate(variable_pairs):
    ax = axes[idx]
    if var1 in merged_df and var2 in merged_df:

        ax.plot(time1, merged_df[var1], label=var1, linestyle='-')
        ax.plot(time1, merged_df[var2], label=var2, linestyle='--')
        ax.set_title(f"{var1} vs {var2}", fontsize=9)
        ax.set_xlabel("Time (s)", fontsize=8)
        ax.set_ylabel("Value (pu)", fontsize=8)
        ax.tick_params(axis='both', labelsize=7)
        ax.legend(fontsize=7, loc='best')
        ax.grid(True)
        if idx == 0:
            ax.set_ylim(0.998, 1.002)
        if idx == 2 or idx == 3:
            ax.set_ylim(6, 8)
    else:
        ax.set_visible(False)  # hide empty subplot

axes[-1].set_xlabel("Time (s)")
plt.tight_layout(rect=[0, 0, 1, 0.97])
plt.suptitle("Simulation Variable Comparison (GridCal vs GENCLS)", fontsize=16, y=1.02)
plt.subplots_adjust(top=0.95)
plt.show()

# plt.savefig('comparison_plots.png', dpi=300)

