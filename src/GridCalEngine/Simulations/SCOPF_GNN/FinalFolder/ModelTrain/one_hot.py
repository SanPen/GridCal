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

# Load dataset (replace with your actual path and loading logic)
data = pd.read_csv("../../ModelTraining/scopf_dataset.csv")
# data = pd.read_csv("/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/FinalFolder/ModelTrain/scopf_dataset_39.csv")

# Define input and output columns
input_cols = [f'Pg_{i}' for i in range(5)] + ['contingency_index']
output_cols = ['W_k'] + [f'u_j_{i}' for i in range(5)] + [f'Z_k_{i}' for i in range(5)]

X = data[input_cols]
y = data[output_cols]
c = data[['contingency_index']]

# Scale features and target
scaler_X = StandardScaler()
scaler_y = StandardScaler()
X_scaled = scaler_X.fit_transform(X)
y_scaled = scaler_y.fit_transform(y)

# Train/val/test split
X_train, X_temp, y_train, y_temp, c_train, c_temp = train_test_split(X_scaled, y_scaled, c, test_size=0.3, stratify=c, random_state=42)
X_val, X_test, y_val, y_test, c_val, c_test = train_test_split(X_temp, y_temp, c_temp, test_size=0.5, stratify=c_temp, random_state=42)

# Convert to tensors
X_train_tensor = torch.tensor(X_train, dtype=torch.float32)
y_train_tensor = torch.tensor(y_train, dtype=torch.float32)
X_val_tensor = torch.tensor(X_val, dtype=torch.float32)
y_val_tensor = torch.tensor(y_val, dtype=torch.float32)
X_test_tensor = torch.tensor(X_test, dtype=torch.float32)
y_test_tensor = torch.tensor(y_test, dtype=torch.float32)

# Loaders
train_loader = DataLoader(TensorDataset(X_train_tensor, y_train_tensor), batch_size=64, shuffle=True)
val_loader = DataLoader(TensorDataset(X_val_tensor, y_val_tensor), batch_size=64)
test_loader = DataLoader(TensorDataset(X_test_tensor, y_test_tensor), batch_size=64)

# Model definition
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

model = Net(input_dim=X.shape[1], output_dim=y.shape[1])
optimizer = optim.Adam(model.parameters(), lr=0.001)
# Weights: [W_k, u_j_0..4, Z_k_0..4]
loss_weights = torch.tensor([
    100.0,     # W_k
    1.0, 1.0, 1.0, 1.0, 1.0,
    100.0, 100.0, 100.0, 100.0, 100.0
], dtype=torch.float32)
loss_weights /= loss_weights.sum()


def weighted_mse_loss(pred, target, weights):
    return ((weights * (pred - target)**2).mean())


loss_fn = nn.MSELoss()


scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)

# Training loop with early stopping
EPOCHS = 200
best_val_loss = float('inf')
early_stop_patience = 20
patience_counter = 0
train_losses, val_losses = [], []

for epoch in range(EPOCHS):
    model.train()
    train_loss = 0
    for xb, yb in train_loader:
        pred = model(xb)
        # loss = loss_fn(pred, yb)
        optimizer.zero_grad()
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
        torch.save(model.state_dict(), "../../ModelTraining/best_model.pt")
        # torch.save(model.state_dict(), "../../ModelTraining/best_model_39.pt")
        patience_counter = 0
    else:
        patience_counter += 1
        if patience_counter >= early_stop_patience:
            print("Early stopping")
            break

# Evaluation
model.load_state_dict(torch.load("../../ModelTraining/best_model.pt"))
# model.load_state_dict(torch.load("../../ModelTraining/best_model_39.pt"))
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