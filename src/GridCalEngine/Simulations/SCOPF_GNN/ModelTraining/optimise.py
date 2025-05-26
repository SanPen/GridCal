import random

import optuna
from copy import deepcopy
from sklearn.preprocessing import StandardScaler


import torch
from torch_geometric.loader import DataLoader
from GridCalEngine.Simulations.SCOPF_GNN.ModelTraining.train_pf import PowerSystemGNN, evaluate_epoch, train_epoch, \
    train_set, val_set

from GridCalEngine.Simulations.SCOPF_GNN.ModelTraining.train_pf import generate_augmented_scopf_data

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")
grid_file_path_train = "/Users/CristinaFray/PycharmProjects/GridCal/src/trunk/scopf/case14_cont_v12.gridcal"

# GNN Model
f_node_in = 2  # Node features: P_inj_pu, Q_inj_pu
f_edge_in = 4  # Edge features: R_pu, X_pu, B_pu, is_active (total line charging)
f_node_out = 2  # Node outputs: Vm_pu, Va_rad
f_edge_out = 4  # Edge outputs: Pf_pu, Pt_pu, Qf_pu, Qt_pu
hidden_channels = 2
num_layers = 2

def train_with_config(config, base_data):
    # Deepcopy base_data to avoid modifying original between trials
    train_data, val_data, test_data, scalers = deepcopy(base_data)

    train_loader = DataLoader(train_data, batch_size=config["batch_size"], shuffle=True)
    val_loader = DataLoader(val_data, batch_size=config["batch_size"], shuffle=False)

    model = PowerSystemGNN(
        node_in_feat=f_node_in,
        edge_in_feat=f_edge_in,
        hidden_feat=config["hidden_dim"],
        node_out_feat=f_node_out,
        edge_out_feat=f_edge_out,
        num_layers=config["num_layers"]
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=config["lr"], weight_decay=1e-5)
    criterion_node = torch.nn.MSELoss()
    criterion_edge = torch.nn.MSELoss()

    best_val_loss = float("inf")
    for epoch in range(1, config["epochs"] + 1):
        train_epoch(model, train_loader, optimizer, criterion_node, criterion_edge)
        val_loss, *_ = evaluate_epoch(model, val_loader, criterion_node, criterion_edge, scalers, set_name="Val")
        if val_loss < best_val_loss:
            best_val_loss = val_loss

    return best_val_loss

def objective(trial):
    config = {
        "lr": trial.suggest_loguniform("lr", 1e-5, 1e-2),
        "hidden_dim": trial.suggest_categorical("hidden_dim", [64, 128, 256]),
        "num_layers": trial.suggest_int("num_layers", 2, 6),
        "dropout": trial.suggest_uniform("dropout", 0.0, 0.5),
        "batch_size": trial.suggest_categorical("batch_size", [16, 32, 64]),
        "epochs": 50
    }
    val_loss = train_with_config(config, base_data)
    return val_loss

if __name__ == '__main__':
    # Setup data only once outside of Optuna loop
    all_data = generate_augmented_scopf_data(grid_file_path_train, num_variants=20, variation_scale=0.1)
    random.shuffle(all_data)
    num_total = len(all_data)
    num_train = int(train_set * num_total)
    num_val = int(val_set * num_total)
    train_data = all_data[:num_train]
    val_data = all_data[num_train:num_train + num_val]
    test_data = all_data[num_train + num_val:]
    # scalers = fit_and_apply_scalers(train_data, val_data, test_data)  # implement from your logic
    base_data = (train_data, val_data, test_data, None)  # Replace None with actual scalers if needed

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=30)

    print("Best parameters:", study.best_params)
    print("Best validation loss:", study.best_value)
