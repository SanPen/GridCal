# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import pdb

import pandas as pd
import matplotlib.pyplot as plt

def merge_simulation_results_by_time(csv1, csv2, output_csv= 'merged_data_hardcoded_init_rms.csv', time_col='Time [s]'):
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

comparison = merge_simulation_results_by_time('simulation_results.csv', 'simulation_results_automatic_init.csv')
# andes is automatic
# Load merged CSV
i = 1
merged_df = comparison
# merged_df['Pl_Gridcal'] = merged_df['Pl_Gridcal'] * (-100)

variable_pairs = [
     [f"omega_0_VeraGrid", f"omega_VeraGrid"],
     [f"omega_1_VeraGrid", f"omega_VeraGrid.1"],
     # [f"omega_3_VeraGrid", f"omega_VeraGrid.2"],
     # [f"omega_4_VeraGrid", f"omega_VeraGrid.3"],
     # [f"Vline_to_Gridcal", f"Vm_Gridcal.1"],
     # [f"dline_to_Gridcal", f"Va_Gridcal.1"],
     # [f"dline_from_Gridcal", f"Va_Gridcal"],
     # [f"Vline_from_Gridcal", f"Vm_Gridcal"]
    ]


# Automatically detect time columns
time_column = merged_df['Time [s]']
time_columns = [col for col in merged_df.columns if 'Time [s]' in col.lower()]
time1 = time_column

# Create subplots
n = len(variable_pairs)
cols = 2
rows = (n + 1) // cols

fig, axes = plt.subplots(rows, cols, figsize=(10, 2 * rows), sharex=True)
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

axes[-1].set_xlabel("Time (s)")
plt.tight_layout(rect=[0, 0, 1, 0.97])
# plt.suptitle("Simulation Variable Comparison (VeraGrid vs GENCLS)", fontsize=16, y=1.02)
plt.ylim([0.85, 1.15])
plt.subplots_adjust(top=0.95)
plt.show()

# plt.savefig('comparison_plots.png', dpi=300)

