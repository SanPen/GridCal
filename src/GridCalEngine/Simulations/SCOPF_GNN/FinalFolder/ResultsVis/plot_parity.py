import torch
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
import numpy as np
import torch.nn as nn

# Load dataset
df = pd.read_csv(
    '/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/FinalFolder/ModelTrain/scopf_dataset_14.csv')
input_cols = [f'Pg_{i}' for i in range(5)] + ['contingency_index']
output_cols = ['W_k'] + [f'u_j_{i}' for i in range(5)] + [f'Z_k_{i}' for i in range(5)]

# Extract features and labels
X = df[input_cols].values
y = df[output_cols].values
contingency_indices = df['contingency_index'].values

# Scale
scaler_X = StandardScaler()
scaler_y = StandardScaler()
X_scaled = scaler_X.fit_transform(X)
y_scaled = scaler_y.fit_transform(y)

# Split
from sklearn.model_selection import train_test_split

X_train, X_temp, y_train, y_temp, ci_train, ci_temp = train_test_split(
    X_scaled, y_scaled, contingency_indices, test_size=0.3, random_state=42)
X_val, X_test, y_val, y_test, ci_val, ci_test = train_test_split(
    X_temp, y_temp, ci_temp, test_size=0.5, random_state=42)

X_test_t = torch.tensor(X_test, dtype=torch.float32)


# Model definition
class SCOPFModel(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(SCOPFModel, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim)
        )

    def forward(self, x):
        return self.net(x)


# Load model
model = SCOPFModel(input_dim=X.shape[1], output_dim=y.shape[1])
model.load_state_dict(torch.load(
    '/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/scopf_model.pt'))
model.eval()

# Predict
with torch.no_grad():
    y_pred_scaled = model(X_test_t).numpy()
y_pred = scaler_y.inverse_transform(y_pred_scaled)
y_true = scaler_y.inverse_transform(y_test)

# Plot parity plots with coloring
output_labels = ['W_k'] + [f'u_j_{i}' for i in range(5)] + [f'Z_k_{i}' for i in range(5)]

plt.figure(figsize=(15, 10))
for i in range(len(output_labels)):
    plt.subplot(3, 4, i + 1)
    sc = plt.scatter(
        y_true[:, i], y_pred[:, i],
        c=ci_test, cmap='tab20', s=10, alpha=0.8
    )
    plt.plot([y_true[:, i].min(), y_true[:, i].max()],
             [y_true[:, i].min(), y_true[:, i].max()], 'r--')
    plt.xlabel("True")
    plt.ylabel("Predicted")
    plt.title(output_labels[i])
    plt.grid(True)

plt.tight_layout()
plt.subplots_adjust(right=0.9)
cbar_ax = plt.gcf().add_axes([0.93, 0.15, 0.015, 0.7])
plt.colorbar(sc, cax=cbar_ax, label='Contingency Index')

plt.savefig("parity_colored_by_contingency.png")
plt.show()



