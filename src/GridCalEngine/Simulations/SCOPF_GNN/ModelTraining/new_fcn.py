import torch.nn.functional as F
import os
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# Load dataset
df = pd.read_csv('scopf_dataset.csv')
# df_c3 = df[df['contingency_index'] == 3]
# df_oversampled = pd.concat([df, df_c3] * 5, ignore_index=True)

# Prepare input/output columns
input_cols = [f'Pg_{i}' for i in range(5)] + ['contingency_index']
output_cols = ['W_k'] + [f'u_j_{i}' for i in range(5)] + [f'Z_k_{i}' for i in range(5)]

X = df[input_cols].values
y = df[output_cols].values

# Normalize inputs and outputs
scaler_X = StandardScaler()
scaler_y = StandardScaler()
X_scaled = scaler_X.fit_transform(X)
y_scaled = scaler_y.fit_transform(y)

n_total = len(X_scaled)
n_train = int(0.8 * n_total)
n_val = int(0.1 * n_total)
n_test = n_total - n_train - n_val

X_train, X_val, X_test = X_scaled[:n_train], X_scaled[n_train:n_train + n_val], X_scaled[n_train + n_val:]
y_train, y_val, y_test = y_scaled[:n_train], y_scaled[n_train:n_train + n_val], y_scaled[n_train + n_val:]

# Convert to tensors
X_train_t = torch.tensor(X_train, dtype=torch.float32)
y_train_t = torch.tensor(y_train, dtype=torch.float32)
X_val_t = torch.tensor(X_val, dtype=torch.float32)
y_val_t = torch.tensor(y_val, dtype=torch.float32)
X_test_t = torch.tensor(X_test, dtype=torch.float32)
y_test_t = torch.tensor(y_test, dtype=torch.float32)

# DataLoaders
train_dataset = torch.utils.data.TensorDataset(X_train_t, y_train_t)
val_dataset = torch.utils.data.TensorDataset(X_val_t, y_val_t)

train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=64, shuffle=True)
val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=64)

# Include contingency_index as a separate input
contingency_all = df['contingency_index'].values
contingency_scaled = contingency_all.reshape(-1, 1)  # shape (N, 1)

# Same 90:5:5 split for contingency
contingency_train = contingency_scaled[:n_train]
contingency_val = contingency_scaled[n_train:n_train + n_val]
contingency_test = contingency_scaled[n_train + n_val:]

# Convert to tensors
contingency_train_t = torch.tensor(contingency_train, dtype=torch.int64).squeeze(1)
contingency_val_t = torch.tensor(contingency_val, dtype=torch.int64).squeeze(1)


# Create datasets that include contingency_index
# train_dataset = torch.utils.data.TensorDataset(X_train_t, y_train_t, contingency_train_t)
# val_dataset = torch.utils.data.TensorDataset(X_val_t, y_val_t, contingency_val_t)
#
# train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=64, shuffle=True)
# val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=64)

# Model definition
class SCOPFModel(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(SCOPFModel, self).__init__()
        # self.net = nn.Sequential(
        #     nn.Linear(input_dim, 64),
        #     nn.ReLU(),
        #     nn.Linear(64, 128),
        #     nn.ReLU(),
        #     nn.Linear(128, 64),
        #     nn.ReLU(),
        #     nn.Linear(64, output_dim)
        # )
        # self.net = nn.Sequential(
        #     nn.Linear(input_dim, 128),
        #     nn.ReLU(),
        #     nn.LayerNorm(128),
        #     nn.Dropout(0.2),
        #     nn.Linear(128, 128),
        #     nn.ReLU(),
        #     nn.Linear(128, output_dim)
        # )
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 256),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, output_dim)
        )

    def forward(self, x):
        return self.net(x)


model = SCOPFModel(input_dim=X.shape[1], output_dim=y.shape[1])
optimizer = optim.Adam(model.parameters(), lr=0.001)
loss_fn = nn.MSELoss()

# Training loop
epochs =300
# Before training loop
train_losses = []
val_losses = []

scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)

# Inside training loop
for epoch in range(epochs):
    model.train()
    train_loss = 0
    best_val = float('inf')
    patience_counter = 0
    patience = 10

    for xb, yb in train_loader:
        pred = model(xb)
        loss = loss_fn(pred, yb)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        # train_loss += loss.item()
        train_loss += loss.item() * xb.size(0)

    train_loss /= len(train_loader.dataset)  # Average loss over the entire training set

    model.eval()
    val_loss = 0
    with torch.no_grad():
        for xb, yb in val_loader:
            pred = model(xb)
            loss = loss_fn(pred, yb)
            val_loss += loss.item() * xb.size(0)

    val_loss /= len(val_loader.dataset)  # Average loss over the entire validation set
    # Step the scheduler
    scheduler.step(val_loss)

    # Save epoch losses
    train_losses.append(train_loss)
    val_losses.append(val_loss)

    print(f"Epoch {epoch + 1}/{epochs} - Train Loss: {train_loss:.4f} - Val Loss: {val_loss:.4f}")

    if val_loss < best_val:
        best_val = val_loss
        patience_counter = 0
    else:
        patience_counter += 1
        if patience_counter > patience:
            print("Early stopping triggered.")
            break

# Save losses to CSV for later plotting
pd.DataFrame({'train_loss': train_losses, 'val_loss': val_losses}).to_csv('loss_curve.csv', index=False)

# Evaluate on test set
X_test_t = torch.tensor(X_test, dtype=torch.float32)
y_test_t = torch.tensor(y_test, dtype=torch.float32)

model.eval()
with torch.no_grad():
    test_pred = model(X_test_t)
    test_loss = loss_fn(test_pred, y_test_t).item()

print(f"Test Loss: {test_loss:.4f}")

# Save to file for plotting later
with open("test_loss.txt", "w") as f:
    f.write(str(test_loss))

import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error
import matplotlib.pyplot as plt

# Load contingency index column (original, unscaled)
contingency_indices = df['contingency_index'].values
contingency_test = contingency_indices[n_train + n_val:]  # 5% test portion

# Predict on test set
model.eval()
with torch.no_grad():
    y_pred_test_scaled = model(X_test_t).numpy()

# Inverse transform
y_pred_test = scaler_y.inverse_transform(y_pred_test_scaled)
y_test_orig = scaler_y.inverse_transform(y_test)

# Per-contingency error calculation
unique_contingencies = np.unique(contingency_test)
mse_per_contingency = []
mae_per_contingency = []

for c in unique_contingencies:
    mask = contingency_test == c
    if np.sum(mask) > 0:
        mse = mean_squared_error(y_test_orig[mask], y_pred_test[mask])
        mae = mean_absolute_error(y_test_orig[mask], y_pred_test[mask])
        mse_per_contingency.append((c, mse))
        mae_per_contingency.append((c, mae))

# Convert to DataFrame
mse_df = pd.DataFrame(mse_per_contingency, columns=["Contingency", "MSE"]).sort_values(by="Contingency")
mae_df = pd.DataFrame(mae_per_contingency, columns=["Contingency", "MAE"]).sort_values(by="Contingency")

# Plot
# plt.figure(figsize=(12, 5))
# plt.bar(mse_df["Contingency"], mse_df["MSE"])
# plt.xlabel("Contingency Index")
# plt.ylabel("MSE")
# plt.title("Per-Contingency Test MSE")
# plt.grid(True)
# plt.tight_layout()
# plt.savefig("mse_per_contingency.png")
# plt.show()

# Optional: print top errors
print(mse_df.sort_values(by="MSE", ascending=False).head(5))

output_stds = scaler_y.scale_
weights = torch.tensor(1.0 / output_stds, dtype=torch.float32)


class WeightedMSELoss(nn.Module):
    def __init__(self, weights):
        super().__init__()
        self.weights = weights

    def forward(self, pred, target):
        diff = (pred - target) ** 2
        return torch.mean(self.weights * diff)


loss_fn = WeightedMSELoss(weights)

# class OPFPredictor(nn.Module):
#     def __init__(self, hidden_dim=64):
#         super(OPFPredictor, self).__init__()
#
#         input_dim = 5 + 18  # 5 Pg values + 18 contingency one-hot
#         output_dim = 11  # 1 W_k + 5 u_j + 5 Z_k
#
#         self.fc1 = nn.Linear(input_dim, hidden_dim)
#         self.fc2 = nn.Linear(hidden_dim, hidden_dim)
#         self.fc3 = nn.Linear(hidden_dim, output_dim)
#
#     def forward(self, pg, contingency_index):
#         # pg: tensor of shape [5]
#         # contingency_index: integer (0-17)
#
#         # One-hot encode the contingency index
#         contingency_one_hot = F.one_hot(contingency_index, num_classes=18).float()
#
#         # Concatenate Pg + contingency index
#         x = torch.cat([pg, contingency_one_hot], dim=-1)
#
#         # Forward pass
#         x = F.relu(self.fc1(x))
#         x = F.relu(self.fc2(x))
#         x = self.fc3(x)
#
#         return x  # returns [11] output vector
