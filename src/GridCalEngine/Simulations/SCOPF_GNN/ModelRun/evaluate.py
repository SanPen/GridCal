import torch
import torch.nn as nn
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np

# Load data
df = pd.read_csv('/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining'
                 '/scopf_dataset_14.csv')

# Define columns
input_cols = [f'Pg_{i}' for i in range(5)] + ['contingency_index']
output_cols = ['W_k'] + [f'u_j_{i}' for i in range(5)] + [f'Z_k_{i}' for i in range(5)]

# Extract and scale
X = df[input_cols].values
y = df[output_cols].values

scaler_X = StandardScaler()
scaler_y = StandardScaler()
X_scaled = scaler_X.fit_transform(X)
y_scaled = scaler_y.fit_transform(y)

# Split into test set (same logic as training)
from sklearn.model_selection import train_test_split

_, X_temp, _, y_temp = train_test_split(X_scaled, y_scaled, test_size=0.3, random_state=42)
X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42)

X_test_t = torch.tensor(X_test, dtype=torch.float32)
y_test_t = torch.tensor(y_test, dtype=torch.float32)


# Define model structure
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
model.load_state_dict(torch.load("/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/scopf_model.pt"))
model.eval()

# Predict on test set
with torch.no_grad():
    y_pred_test = model(X_test_t).numpy()

# Inverse scale
y_pred_orig = scaler_y.inverse_transform(y_pred_test)
y_test_orig = scaler_y.inverse_transform(y_test)

# Compute metrics
mae = mean_absolute_error(y_test_orig, y_pred_orig)
rmse = np.sqrt(mean_squared_error(y_test_orig, y_pred_orig))

print(f"Test MAE: {mae:.6f}")
print(f"Test RMSE: {rmse:.6f}")


# -------- INFERENCE --------
def predict_new(Pg, contingency_index):
    assert len(Pg) == 5, "Pg must have 5 values"
    input_vec = Pg + [contingency_index]
    input_scaled = scaler_X.transform([input_vec])
    input_tensor = torch.tensor(input_scaled, dtype=torch.float32)

    with torch.no_grad():
        output_scaled = model(input_tensor).numpy()[0]

    output = scaler_y.inverse_transform([output_scaled])[0]

    result = {
        'W_k': output[0],
        'u_j': output[1:6].tolist(),
        'Z_k': output[6:].tolist()
    }
    return result


# Example usage
example_Pg = [210.0, 0.0, 0.0, 0.0, 0.0]
example_contingency = 3

prediction = predict_new(example_Pg, example_contingency)
print("\nPrediction for new input:")
print(prediction)
