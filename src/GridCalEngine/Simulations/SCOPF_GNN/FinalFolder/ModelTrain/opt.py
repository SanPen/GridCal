import optuna
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import pandas as pd
import numpy as np

# Load dataset
# data = pd.read_csv("/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/FinalFolder/ModelTrain/scopf_dataset_5.csv")  # Update with actual file path
data = pd.read_csv("/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/FinalFolder/ModelTrain/scopf_dataset_14.csv")  # Update with actual file path

# Define input/output columns
all_cols = data.columns.tolist()
num_pg = len([col for col in all_cols if col.startswith('Pg_')])
input_cols = [f'Pg_{i}' for i in range(num_pg)] + ['contingency_index']
num_uj = sum(col.startswith('u_j_') for col in all_cols)
num_zk = sum(col.startswith('Z_k_') for col in all_cols)
output_cols = ['W_k'] + [f'u_j_{i}' for i in range(num_uj)] + [f'Z_k_{i}' for i in range(num_zk)]

X = data[input_cols]
y = data[output_cols]
c = data[['contingency_index']]

# Scaling
scaler_X = StandardScaler()
scaler_y = StandardScaler()
X_scaled = scaler_X.fit_transform(X)
y_scaled = scaler_y.fit_transform(y)

# Train/val split
X_train, X_val, y_train, y_val = train_test_split(X_scaled, y_scaled, test_size=0.2, stratify=c, random_state=42)

# Tensor conversion
X_train_tensor = torch.tensor(X_train, dtype=torch.float32)
y_train_tensor = torch.tensor(y_train, dtype=torch.float32)
X_val_tensor = torch.tensor(X_val, dtype=torch.float32)
y_val_tensor = torch.tensor(y_val, dtype=torch.float32)

train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
val_dataset = TensorDataset(X_val_tensor, y_val_tensor)

# Weighted loss setup
loss_weights = torch.tensor(
    [100.0] + [1.0] * num_uj + [100.0] * num_zk,
    dtype=torch.float32
)
loss_weights /= loss_weights.sum()


def weighted_mse_loss(pred, target, weights):
    return ((weights * (pred - target) ** 2).mean())


# Optuna objective
def objective(trial):
    # Hyperparameters
    hidden1 = trial.suggest_int("hidden1", 64, 256)
    hidden2 = trial.suggest_int("hidden2", 32, 128)
    dropout = trial.suggest_float("dropout", 0.0, 0.5)
    lr = trial.suggest_loguniform("lr", 1e-5, 1e-2)
    batch_size = trial.suggest_categorical("batch_size", [32, 64, 128])

    # Loss weights
    W_k_weight = trial.suggest_float("W_k_weight", 10, 100, log=True)
    u_j_weight = trial.suggest_float("u_j_weight", 0.1, 10.0, log=True)
    Z_k_weight = trial.suggest_float("Z_k_weight", 50, 250, log=True)

    # Dataloaders
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)

    # Model
    class Net(nn.Module):
        def __init__(self, input_dim, output_dim):
            super(Net, self).__init__()
            self.model = nn.Sequential(
                nn.Linear(input_dim, hidden1),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden1, hidden2),
                nn.ReLU(),
                nn.Linear(hidden2, output_dim)
            )

        def forward(self, x):
            return self.model(x)

    model = Net(input_dim=X.shape[1], output_dim=y.shape[1])
    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

    # Construct trial-specific loss weights
    loss_weights = torch.tensor(
        [W_k_weight] + [u_j_weight] * num_uj + [Z_k_weight] * num_zk,
        dtype=torch.float32
    )
    loss_weights /= loss_weights.sum()

    def weighted_mse_loss(pred, target, weights):
        return ((weights * (pred - target) ** 2).mean())

    # Training loop
    best_val_loss = float("inf")
    patience_counter = 0
    for epoch in range(100):
        model.train()
        for xb, yb in train_loader:
            optimizer.zero_grad()
            pred = model(xb)
            loss = weighted_mse_loss(pred, yb, loss_weights)
            loss.backward()
            optimizer.step()

        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                pred = model(xb)
                loss = weighted_mse_loss(pred, yb, loss_weights)
                val_loss += loss.item() * xb.size(0)
        val_loss /= len(val_loader.dataset)
        scheduler.step(val_loss)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= 10:
                break

    return best_val_loss

study = optuna.create_study(direction="minimize")
study.optimize(objective, n_trials=50)

print("Best trial:")
trial = study.best_trial
for key, value in trial.params.items():
    print(f"  {key}: {value}")
