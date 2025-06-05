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
    "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/FinalFolder/ModelTrain/load_var_14.csv")

# Define input and output columns
all_cols = data.columns.tolist()
num_pg = len([col for col in all_cols if col.startswith('Pg_')])
input_cols = [f'Pg_{i}' for i in range(num_pg)] + ['contingency_index']
num_uj = sum(col.startswith('u_j_') for col in all_cols)
num_zk = sum(col.startswith('Z_k_') for col in all_cols)
output_cols = ['W_k'] + [f'u_j_{i}' for i in range(num_uj)] + [f'Z_k_{i}' for i in range(num_zk)]
# output_cols = ['W_k'] + [f'Z_k_{i}' for i in range(num_zk)]

X = data[input_cols]
y = data[output_cols]
print(y.describe())

c = data[['contingency_index']]

# # Oversample contingency 3 to increase its training influence
# cont3_mask = c['contingency_index'] == 3
# X_3 = X[cont3_mask]
# y_3 = y[cont3_mask]
# c_3 = c[cont3_mask]
#
# # Choose how many times to duplicate contingency 3 samples (e.g., 5x)
# oversample_factor = 5
#
# # Concatenate oversampled contingency 3 samples
# X = pd.concat([X] + [X_3] * oversample_factor, ignore_index=True)
# y = pd.concat([y] + [y_3] * oversample_factor, ignore_index=True)
# c = pd.concat([c] + [c_3] * oversample_factor, ignore_index=True)

# Scale features and target
scaler_X = StandardScaler()
scaler_y = StandardScaler()

# Fit the scalers (if not already done)
scaler_X.fit(X)
scaler_y.fit(y)

# Save the fitted scalers
scaler_X_path = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/scaler_X_load_var_14.pkl"
scaler_y_path = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/scaler_y_load_var_14.pkl"

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
# train_loader = DataLoader(TensorDataset(X_train_tensor, y_train_tensor), batch_size=32, shuffle=True)
# val_loader = DataLoader(TensorDataset(X_val_tensor, y_val_tensor), batch_size=32)
# test_loader = DataLoader(TensorDataset(X_test_tensor, y_test_tensor), batch_size=32)
train_loader = DataLoader(TensorDataset(X_train_tensor, y_train_tensor), batch_size=64, shuffle=True)
val_loader = DataLoader(TensorDataset(X_val_tensor, y_val_tensor), batch_size=64)
test_loader = DataLoader(TensorDataset(X_test_tensor, y_test_tensor), batch_size=64)

# Optimized model architecture
class Net(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(Net, self).__init__()
        self.model = nn.Sequential(
            nn.Linear(input_dim, 203),  # hidden1
            nn.ReLU(),
            nn.Dropout(0.2),  # dropout
            nn.Linear(203, 91),  # hidden2
            nn.ReLU(),
            nn.Linear(91, output_dim)
        )

    def forward(self, x):
        return self.model(x)

model = Net(input_dim=X.shape[1], output_dim=y.shape[1])
optimizer = optim.Adam(model.parameters(), lr=0.000833245668463311)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)
# scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=200)

# Best loss weights from latest trial
loss_weights = torch.tensor(
    [14.853780140469974] + [0.4056086018453528] * num_uj + [94.58529365514049] * num_zk,
    dtype=torch.float32
)
# loss_weights = torch.tensor(
#     [14.85] + [94.58] * num_zk,  # Remove u_j weights
#     dtype=torch.float32
# )
loss_weights /= loss_weights.sum()


def weighted_mse_loss1(pred, target, weights):
    return ((weights * (pred - target) ** 2).mean())

def weighted_mse_loss(pred, target, weights, alpha=0.8):
    mse = ((weights * (pred - target) ** 2).mean())
    mae = ((weights * (pred - target).abs()).mean())
    return alpha * mse + (1 - alpha) * mae


# Training loop with early stopping
EPOCHS = 200
early_stop_patience = 20
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

    # model.eval()
    # val_loss = 0
    # with torch.no_grad():
    #     for xb, yb in val_loader:
    #         pred = model(xb)
    #         loss = weighted_mse_loss(pred, yb, loss_weights)
    #         val_loss += loss.item() * xb.size(0)
    #
    # val_loss /= len(val_loader.dataset)
    # train_losses.append(train_loss)
    # val_losses.append(val_loss)
    # scheduler.step(val_loss)
    #
    # # Evaluate loss on only contingency 3 samples
    # model.eval()
    # with torch.no_grad():
    #     cont3_mask = (c_val['contingency_index'].values == 3)
    #     if np.any(cont3_mask):
    #         X_val_3 = torch.tensor(X_val[cont3_mask], dtype=torch.float32)
    #         y_val_3 = torch.tensor(y_val[cont3_mask], dtype=torch.float32)
    #         preds_3 = model(X_val_3)
            # cont3_loss = weighted_mse_loss(preds_3, y_val_3, loss_weights).item()
            # print(f"    Contingency 3 Val Loss: {cont3_loss:.4f}")

    print(f"Epoch {epoch + 1}/{EPOCHS} - Train Loss: {train_loss:.4f} - Val Loss: {val_loss:.4f}")

    if val_loss < best_val_loss:
        best_val_loss = val_loss
        torch.save(model.state_dict(), "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/load_var_14_v2.pt")
        patience_counter = 0
    else:
        patience_counter += 1
        if patience_counter >= early_stop_patience:
            print("Early stopping")
            break


# Evaluation
model.load_state_dict(torch.load("/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/load_var_14_v2.pt"))
model.eval()
all_preds, all_targets, all_conts = [], [], []


with torch.no_grad():
    for i in range(len(X_test_tensor)):
        x = X_test_tensor[i].unsqueeze(0)
        true_val = y_test_tensor[i]
        cont = c_test.iloc[i].values[0]
        pred_val = model(x).numpy()
        all_preds.append(pred_val[0])
        all_targets.append(true_val.numpy())
        all_conts.append(cont)


# Inverse transform
preds_inv = scaler_y.inverse_transform(all_preds)
targets_inv = scaler_y.inverse_transform(all_targets)


# Metrics per contingency
df_eval = pd.DataFrame(all_conts, columns=['contingency'])
for i, col in enumerate(output_cols):
    df_eval[f'{col}_pred'] = preds_inv[:, i]
    df_eval[f'{col}_true'] = targets_inv[:, i]
print(df_eval)

def compute_metrics(group):
    metrics = {}
    for col in output_cols:
        pred = group[f'{col}_pred']
        true = group[f'{col}_true']
        metrics[f'{col}_MSE'] = mean_squared_error(true, pred)
        metrics[f'{col}_MAE'] = mean_absolute_error(true, pred)
    return pd.Series(metrics)

grouped = df_eval.groupby('contingency', group_keys=False).apply(compute_metrics).reset_index()
print("\nPer-Contingency Metrics:")
# print(grouped)

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

print("Training samples:", len(X_train))
print(c['contingency_index'].value_counts())

output_labels = ['W_k'] + [f'u_j_{i}' for i in range(5)] + [f'Z_k_{i}' for i in range(5)]
# output_labels = ['W_k'] + [f'Z_k_{i}' for i in range(num_zk)]
# Reconstruct arrays from lists
y_true = np.array(all_targets)
y_pred = np.array(all_preds)

print("\nSample predictions for W_k and Z_k:")
print(y_true), print(y_pred)

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
        cmap='tab20', s=10, alpha=0.5000657035034387
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