import pandas as pd
import matplotlib.pyplot as plt

# Load the dataset
df = pd.read_csv('src/GridCalEngine/Simulations/SCOPF_GNN/FinalFolder/ModelTrain/scopf_dataset_5_nn.csv')

# Define predictor variables
predictors = ['Pg_0', 'Pg_1', 'Pg_2', 'contingency_index']

# Compute the full correlation matrix, then select only rows for predictors
corr_matrix = df.corr().loc[predictors, :]

# Plot a heatmap of these correlations
fig, ax = plt.subplots(figsize=(12, 4))

# Show correlation values as a heatmap
im = ax.imshow(corr_matrix.values, aspect='auto')

# Set x and y tick labels
ax.set_xticks(range(len(corr_matrix.columns)))
ax.set_xticklabels(corr_matrix.columns, rotation=90, fontsize=8)
ax.set_yticks(range(len(predictors)))
ax.set_yticklabels(predictors, fontsize=10)

# Add colorbar
cbar = fig.colorbar(im, ax=ax)
cbar.set_label('Pearson Correlation')

# Title and layout adjustments
ax.set_title('Correlation: Predictors vs. All Variables', pad=10)
plt.tight_layout()

# Display the plot
plt.show()

