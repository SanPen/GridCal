import torch
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
import torch.nn as nn


# ----------------------------
# Model Architecture (must match training)
# ----------------------------

class SCOPFModel(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(SCOPFModel, self).__init__()
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


# ----------------------------
# Load scalers and model
# ----------------------------

# Load dataset to fit scalers again (use same file used during training)
data = pd.read_csv("../FinalFolder/ModelTrain/scopf_dataset_14.csv")
input_cols = [f'Pg_{i}' for i in range(5)] + ['contingency_index']
output_cols = ['W_k'] + [f'u_j_{i}' for i in range(5)] + [f'Z_k_{i}' for i in range(5)]

X = data[input_cols]
y = data[output_cols]

scaler_X = StandardScaler()
scaler_y = StandardScaler()
scaler_X.fit(X)
scaler_y.fit(y)

# Load trained model
model = SCOPFModel(input_dim=X.shape[1], output_dim=y.shape[1])
model.load_state_dict(torch.load("best_model_14.pt"))
model.eval()

# ----------------------------
# Prediction + Visualization
# ----------------------------

def predict_outputs(pg_values, contingency_idx):
    assert len(pg_values) == 5, "Expected 5 Pg values"
    input_vec = np.array(pg_values + [contingency_idx]).reshape(1, -1)
    input_df = pd.DataFrame(input_vec, columns=scaler_X.feature_names_in_)
    input_scaled = scaler_X.transform(input_df)
    input_tensor = torch.tensor(input_scaled, dtype=torch.float32)

    with torch.no_grad():
        output_scaled = model(input_tensor).numpy()

    output = scaler_y.inverse_transform(output_scaled)[0]
    return output



def display_prediction(pg_values, contingency_idx, output):
    print(f"\n🔧 Test Input")
    print(f"Pg: {pg_values}")
    print(f"Contingency: {contingency_idx}\n")

    print(f"🎯 Model Prediction:")
    print(f"W_k: {output[0]:.6f}")
    for i in range(5):
        print(f"u_j_{i}: {output[1 + i]:.6f} \t Z_k_{i}: {output[6 + i]:.6f}")


def plot_grid_outputs(output):
    fig, ax = plt.subplots(figsize=(8, 3))
    u_j = output[1:6]
    Z_k = output[6:11]

    bar_width = 0.35
    index = np.arange(5)

    ax.bar(index, u_j, bar_width, label='u_j')
    ax.bar(index + bar_width, Z_k, bar_width, label='Z_k')

    ax.set_xlabel('Generator/Bus Index')
    ax.set_title('Predicted u_j and Z_k')
    ax.set_xticks(index + bar_width / 2)
    ax.set_xticklabels([f'j_{i}' for i in range(5)])
    ax.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


# ----------------------------
# Example usage
# ----------------------------

if __name__ == "__main__":
    test_pg = [207, 0, 0, 0, 0]  # Example Pg values
    contingency = 2  # Choose a contingency index (0–17)

    predicted = predict_outputs(test_pg, contingency)
    display_prediction(test_pg, contingency, predicted)
    plot_grid_outputs(predicted)
