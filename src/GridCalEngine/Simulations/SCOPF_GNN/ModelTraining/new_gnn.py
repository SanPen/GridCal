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

# Train/val/test split
X_train, X_temp, y_train, y_temp = train_test_split(X_scaled, y_scaled, test_size=0.3, random_state=42)
X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42)

# Convert to PyTorch tensors
X_train_t = torch.tensor(X_train, dtype=torch.float32)
y_train_t = torch.tensor(y_train, dtype=torch.float32)
X_val_t = torch.tensor(X_val, dtype=torch.float32)
y_val_t = torch.tensor(y_val, dtype=torch.float32)

# Data loaders
train_dataset = torch.utils.data.TensorDataset(X_train_t, y_train_t)
val_dataset = torch.utils.data.TensorDataset(X_val_t, y_val_t)

train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=64, shuffle=True)
val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=64)


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


model = SCOPFModel(input_dim=X.shape[1], output_dim=y.shape[1])
optimizer = optim.Adam(model.parameters(), lr=0.01)
loss_fn = nn.MSELoss()

# Training loop
EPOCHS = 100
# Before training loop
train_losses = []
val_losses = []

# Inside training loop
for epoch in range(EPOCHS):
    model.train()
    train_loss = 0
    for xb, yb in train_loader:
        pred = model(xb)
        loss = loss_fn(pred, yb)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        train_loss += loss.item()

    model.eval()
    val_loss = 0
    with torch.no_grad():
        for xb, yb in val_loader:
            pred = model(xb)
            loss = loss_fn(pred, yb)
            val_loss += loss.item()

    # Save epoch losses
    train_losses.append(train_loss)
    val_losses.append(val_loss)

    print(f"Epoch {epoch + 1}/{EPOCHS} - Train Loss: {train_loss:.4f} - Val Loss: {val_loss:.4f}")

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

#
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
