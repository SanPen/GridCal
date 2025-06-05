import pandas as pd
import matplotlib.pyplot as plt

# Load the dataset
# df = pd.read_csv('/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/FinalFolder/ModelTrain/load_var_5_v4.csv')
df = pd.read_csv('/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/FinalFolder/ModelTrain/load_var_14.csv')

# Define predictor variables
# predictors = ['Pg_0', 'Pg_1', 'Pg_2', 'contingency_index']
predictors = ['Pg_0', 'Pg_1', 'Pg_2', 'Pg_3', 'Pg_4', 'contingency_index']

# Clean column names if needed (remove extra spaces)
df.columns = [col.strip() for col in df.columns]

# Compute correlation matrix
corr_matrix = df.corr()

# Select only the first 11 columns as targets
first_11_columns = df.columns[:12]

# Get correlations of predictors with just the first 11 columns
corr_subset = corr_matrix.loc[predictors, first_11_columns]

# Plot heatmap
fig, ax = plt.subplots(figsize=(10, 4))
im = ax.imshow(corr_subset.values, aspect='auto', vmin=-1, vmax=1)

# Set tick labels
ax.set_xticks(range(len(first_11_columns)))
ax.set_xticklabels(first_11_columns, rotation=90, fontsize=8)
ax.set_yticks(range(len(predictors)))
ax.set_yticklabels(predictors, fontsize=10)

# Add colorbar
cbar = fig.colorbar(im, ax=ax)
cbar.set_label('Pearson Correlation')

# Title and layout
ax.set_title('Correlation: Predictors vs. All Variables', pad=10)
plt.tight_layout()
plt.show()

# import pandas as pd
# import matplotlib.pyplot as plt
#
# # Load the dataset
# df = pd.read_csv('/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/FinalFolder/ModelTrain/load_var_5_v4.csv')
#
# # Define predictor variables
# # predictors = ['P_g_sps_0','P_g_sps_1','P_g_sps_2', 'contingency_index']
# predictors = ['Pg_0',' Pg_1', 'Pg_2', 'contingency_index']
#
# # Compute the full correlation matrix, then select only rows for predictors
# corr_matrix = df.corr().loc[predictors, :]
#
# # Plot a heatmap of these correlations
# fig, ax = plt.subplots(figsize=(12, 4))
#
# # Show correlation values as a heatmap
# im = ax.imshow(corr_matrix.values, aspect='auto')
#
# # Set x and y tick labels
# ax.set_xticks(range(len(corr_matrix.columns)))
# ax.set_xticklabels(corr_matrix.columns, rotation=90, fontsize=8)
# ax.set_yticks(range(len(predictors)))
# ax.set_yticklabels(predictors, fontsize=10)
#
# # Add colorbar
# cbar = fig.colorbar(im, ax=ax)
# cbar.set_label('Pearson Correlation')
#
# # Title and layout adjustments
# ax.set_title('Correlation: Predictors vs. All Variables', pad=10)
# plt.tight_layout()
#
# # Display the plot
# plt.show()
#
