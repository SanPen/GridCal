import joblib
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

# Load dataset
data = pd.read_csv(
    "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/FinalFolder/ModelTrain/load_var_5_v4.csv")

# Define input and output columns
all_cols = data.columns.tolist()
num_pg = len([col for col in all_cols if col.startswith('Pg_')])
input_cols = [f'Pg_{i}' for i in range(num_pg)] + ['contingency_index']
num_uj = sum(col.startswith('u_j_') for col in all_cols)
num_zk = sum(col.startswith('Z_k_') for col in all_cols)
# output_cols = ['W_k'] + [f'Z_k_{i}' for i in range(num_zk)]
output_cols = ['W_k'] + [f'u_j_{i}' for i in range(num_uj)] + [f'Z_k_{i}' for i in range(num_zk)]

X = data[input_cols]
y = data[output_cols]
c = data[['contingency_index']]

# Scale features and target
scaler_X = StandardScaler()
scaler_y = StandardScaler()

# Fit the scalers (if not already done)
scaler_X.fit(X)
scaler_y.fit(y)

# Save the fitted scalers
scaler_X_path = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/scaler_X_load_var_5.pkl"
scaler_y_path = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/scaler_y_load_var_5.pkl"

joblib.dump(scaler_X, scaler_X_path)
joblib.dump(scaler_y, scaler_y_path)

print("Scalers saved successfully.")

X_scaled = scaler_X.fit_transform(X)
y_scaled = scaler_y.fit_transform(y)

# Train/val/test split
X_train, X_temp, y_train, y_temp, c_train, c_temp = train_test_split(X_scaled, y_scaled, c, test_size=0.2, stratify=c,
                                                                     random_state=42)
X_val, X_test, y_val, y_test, c_val, c_test = train_test_split(X_temp, y_temp, c_temp, test_size=0.5, stratify=c_temp,
                                                               random_state=42)

# Convert to tensors
X_train_tensor = torch.tensor(X_train, dtype=torch.float32)
y_train_tensor = torch.tensor(y_train, dtype=torch.float32)
X_val_tensor = torch.tensor(X_val, dtype=torch.float32)
y_val_tensor = torch.tensor(y_val, dtype=torch.float32)
X_test_tensor = torch.tensor(X_test, dtype=torch.float32)
y_test_tensor = torch.tensor(y_test, dtype=torch.float32)

# DataLoaders with tuned batch size
train_loader = DataLoader(TensorDataset(X_train_tensor, y_train_tensor), batch_size=32, shuffle=True)
val_loader = DataLoader(TensorDataset(X_val_tensor, y_val_tensor), batch_size=32)
test_loader = DataLoader(TensorDataset(X_test_tensor, y_test_tensor), batch_size=32)

# Optimized model architecture
class Net(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(Net, self).__init__()
        self.model = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim)
        )

    def forward(self, x):
        return self.model(x)

# Model and optimizer setup
model = Net(input_dim=X.shape[1], output_dim=y.shape[1])
optimizer = optim.Adam(model.parameters(), lr=0.0065690653086478736)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)
# scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)

# Optimized loss weights

# loss_weights = torch.tensor(
#     [14.85] + [94.58] * num_zk,  # Remove u_j weights
#     dtype=torch.float32
# )
loss_weights = torch.tensor(
    [14.853780140469974] + [0.4056086018453528] * num_uj + [94.58529365514049] * num_zk,
    dtype=torch.float32
)
loss_weights /= loss_weights.sum()

def weighted_mse_loss(pred, target, weights):
    return ((weights * (pred - target) ** 2).mean())

# Training loop with early stopping
EPOCHS = 200
early_stop_patience = 30
best_val_loss = float('inf')
patience_counter = 0
train_losses, val_losses = [], []

for epoch in range(EPOCHS):
    model.train()
    train_loss = 0
    for xb, yb in train_loader:
        optimizer.zero_grad()
        pred = model(xb)
        loss = weighted_mse_loss(pred, yb, loss_weights)
        loss.backward()
        optimizer.step()
        train_loss += loss.item() * xb.size(0)

    train_loss /= len(train_loader.dataset)

    model.eval()
    val_loss = 0
    with torch.no_grad():
        for xb, yb in val_loader:
            pred = model(xb)
            loss = weighted_mse_loss(pred, yb, loss_weights)
            val_loss += loss.item() * xb.size(0)

    val_loss /= len(val_loader.dataset)
    train_losses.append(train_loss)
    val_losses.append(val_loss)
    scheduler.step(val_loss)

    print(f"Epoch {epoch + 1}/{EPOCHS} - Train Loss: {train_loss:.4f} - Val Loss: {val_loss:.4f}")

    if val_loss < best_val_loss:
        best_val_loss = val_loss
        torch.save(model.state_dict(), "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/load_var_5_v4.pt")
        patience_counter = 0
    else:
        patience_counter += 1
        if patience_counter >= early_stop_patience:
            print("Early stopping")
            break

# Evaluation
model.load_state_dict(torch.load("/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/load_var_5_v4.pt"))
model.eval()
all_preds, all_targets, all_conts = [], [], []

with torch.no_grad():
    for i in range(len(X_test_tensor)):
        x = X_test_tensor[i].unsqueeze(0)
        y_true = y_test_tensor[i]
        cont = c_test.iloc[i].values[0]
        y_pred = model(x).numpy()
        all_preds.append(y_pred[0])
        all_targets.append(y_true.numpy())
        all_conts.append(cont)

# Inverse transform
preds_inv = scaler_y.inverse_transform(all_preds)
targets_inv = scaler_y.inverse_transform(all_targets)

# Metrics per contingency
df_eval = pd.DataFrame(all_conts, columns=['contingency'])
for i, col in enumerate(output_cols):
    df_eval[f'{col}_pred'] = preds_inv[:, i]
    df_eval[f'{col}_true'] = targets_inv[:, i]

def compute_metrics(group):
    metrics = {}
    for col in output_cols:
        pred = group[f'{col}_pred']
        true = group[f'{col}_true']
        metrics[f'{col}_MSE'] = mean_squared_error(true, pred)
        metrics[f'{col}_MAE'] = mean_absolute_error(true, pred)
    return pd.Series(metrics)

grouped = df_eval.groupby('contingency').apply(compute_metrics).reset_index()
print("\nPer-Contingency Metrics:")
print(grouped)

# Plot loss curves
plt.figure()
plt.plot(train_losses, label="Train Loss")
plt.plot(val_losses, label="Val Loss")
plt.xlabel("Epoch")
plt.ylabel("Loss")
plt.legend()
plt.title("Training and Validation Loss")
plt.grid(True)
plt.show()

# Smoothened loss curve
# def moving_average(data, window_size=5):
#     return np.convolve(data, np.ones(window_size)/window_size, mode='valid')
#
# smoothed_train = moving_average(train_losses, window_size=5)
# smoothed_val = moving_average(val_losses, window_size=5)
#
# plt.figure()
# plt.plot(smoothed_train, label="Train Loss (smoothed)")
# plt.plot(smoothed_val, label="Val Loss (smoothed)")
# plt.xlabel("Epoch")
# plt.ylabel("Loss")
# plt.legend()
# plt.title("Smoothed Training and Validation Loss")
# plt.grid(True)
# plt.show()

print("Training samples:", len(X_train))
print(c['contingency_index'].value_counts())

# Predict
with torch.no_grad():
    y_pred_scaled = model(X_test_tensor).numpy()
y_pred = scaler_y.inverse_transform(y_pred_scaled)
y_true = scaler_y.inverse_transform(y_test)


# # Plot parity plots with coloring
# # output_labels = ['W_k'] + [f'u_j_{i}' for i in range(5)] + [f'Z_k_{i}' for i in range(5)]
# output_labels = ['W_k'] + [f'Z_k_{i}' for i in range(num_zk)]
#
# plt.figure(figsize=(15, 10))
# for i in range(len(output_labels)):
#     plt.subplot(3, 4, i + 1)
#     sc = plt.scatter(
#         y_true[:, i], y_pred[:, i],
#         c=c_test.values.ravel(),  # FIXED: flatten the contingency index array
#         cmap='tab20', s=10, alpha=0.8
#     )
#     plt.plot(
#         [y_true[:, i].min(), y_true[:, i].max()],
#         [y_true[:, i].min(), y_true[:, i].max()], 'r--'
#     )
#     plt.xlabel("True")
#     plt.ylabel("Predicted")
#     plt.title(output_labels[i])
#     plt.grid(True)
#
# plt.tight_layout()
# plt.subplots_adjust(right=0.9)
# cbar_ax = plt.gcf().add_axes([0.93, 0.15, 0.015, 0.7])
# plt.colorbar(sc, cax=cbar_ax, label='Contingency Index')
#
# plt.savefig("parity_colored_by_contingency.png", dpi=300)
# plt.show()

import matplotlib.pyplot as plt
import numpy as np

output_labels = ['W_k'] + [f'u_j_{i}' for i in range(num_uj)] + [f'Z_k_{i}' for i in range(num_zk)]
# output_labels = ['W_k'] + [f'Z_k_{i}' for i in range(num_zk)]

n_outputs = len(output_labels)
n_cols = 4
n_rows = int(np.ceil(n_outputs / n_cols))

fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 3.5 * n_rows))
axes = axes.flatten()

for i in range(n_outputs):
    ax = axes[i]
    sc = ax.scatter(
        y_true[:, i], y_pred[:, i],
        c=c_test.values.ravel(),
        cmap='tab20', s=10, alpha=0.8
    )
    ax.plot(
        [y_true[:, i].min(), y_true[:, i].max()],
        [y_true[:, i].min(), y_true[:, i].max()], 'r--'
    )
    ax.set_xlabel("True")
    ax.set_ylabel("Predicted")
    ax.set_title(output_labels[i])
    ax.grid(True)

# Hide unused subplots if any
for j in range(i + 1, len(axes)):
    fig.delaxes(axes[j])

# Adjust layout and add colorbar
plt.tight_layout(rect=[0, 0, 0.92, 1])
cbar_ax = fig.add_axes([0.94, 0.15, 0.015, 0.7])
fig.colorbar(sc, cax=cbar_ax, label='Contingency Index')

plt.savefig("parity_colored_by_contingency.png", dpi=300)
plt.show()
