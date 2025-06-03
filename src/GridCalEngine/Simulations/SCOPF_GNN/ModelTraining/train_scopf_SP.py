import numpy as np
import torch
import torch.nn as nn
from matplotlib import pyplot as plt
from torch_geometric.data import Data
from GridCalEngine import FileOpen, PowerFlowOptions, SolverType, AcOpfMode, OptimalPowerFlowOptions, \
    compile_numerical_circuit_at, LinearMultiContingencies
from GridCalEngine.Simulations.SCOPF_GNN.NumericalMethods.scopf import run_nonlinear_SP_scopf, run_nonlinear_MP_opf
from torch_geometric.loader import DataLoader
import pandas as pd
from sklearn.model_selection import train_test_split

import os
import json
import torch.nn.functional as F
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error, r2_score

from torch_geometric.data import Data

def load_scopf_json_dataset(json_dir: str):
    dataset = []

    for filename in os.listdir(json_dir):
        if not filename.endswith(".json"):
            continue

        with open(os.path.join(json_dir, filename), 'r') as f:
            record = json.load(f)

        Pg = record["Pg"]
        for cont in record["contingency_outputs"]:
            x_input = torch.tensor([cont["contingency_index"]] + Pg, dtype=torch.float32).view(1, -1)

            wk = torch.tensor(cont["W_k"], dtype=torch.float32).view(1)         # [1]
            uj = torch.tensor(cont["u_j"], dtype=torch.float32)                 # [5]
            zk = torch.tensor(cont["Z_k"], dtype=torch.float32)                 # [5]
            # Create a Data object with y_wk as primary label, uj and zk as additional
            data = Data(
                x=x_input,                    # [6]
                y_wk=wk,                      # [1]
            )
            data.y_uj = uj                   # Attach manually to avoid flattening
            data.y_zk = zk

            dataset.append(data)
    return dataset


class SCOPFParameterRegressor(nn.Module):
    def __init__(self, input_dim, hidden_dim, num_generators):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU()
        )
        self.out_wk = nn.Linear(hidden_dim, 1)
        self.out_uj = nn.Linear(hidden_dim, num_generators)
        self.out_zk = nn.Linear(hidden_dim, num_generators)

    def forward(self, x):
        h = self.mlp(x)
        wk = self.out_wk(h).squeeze(-1)
        uj = self.out_uj(h)
        zk = self.out_zk(h)
        return wk, uj, zk


def plot_scopf_progress(iteration_data):
    """
    Plot the evolution of various metrics across SCOPF iterations
    :param iteration_data: Dictionary containing lists of metrics per iteration
    """
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

    # Plot maximum W_k evolution
    ax1.plot(iteration_data['max_wk'], 'b.-', label='Max W_k')
    ax1.set_xlabel('Iteration')
    ax1.set_ylabel('Maximum W_k Value')
    ax1.set_title('Evolution of Maximum W_k')
    ax1.grid(True)
    ax1.legend()

    # Plot number of violations
    ax2.plot(iteration_data['num_violations'], 'r.-', label='Violations')
    ax2.set_xlabel('Iteration')
    ax2.set_ylabel('Number of Violations')
    ax2.set_title('Number of Constraint Violations')
    ax2.grid(True)
    ax2.legend()

    # Plot slack values statistics
    ax3.plot(iteration_data['max_voltage_slack'], 'g.-', label='Max V Slack')
    ax3.plot(iteration_data['avg_voltage_slack'], 'g--', label='Avg V Slack')
    ax3.plot(iteration_data['max_flow_slack'], 'm.-', label='Max F Slack')
    ax3.plot(iteration_data['avg_flow_slack'], 'm--', label='Avg F Slack')
    ax3.set_xlabel('Iteration')
    ax3.set_ylabel('Slack Values')
    ax3.set_title('Evolution of Slack Values in Subproblems')
    ax3.grid(True)
    ax3.legend()

    # Plot generation cost
    ax4.plot(iteration_data['total_cost'], 'k.-', label='Cost')
    ax4.set_xlabel('Iteration')
    ax4.set_ylabel('Generation Cost')
    ax4.set_title('Evolution of Generation Cost')
    ax4.grid(True)
    ax4.legend()

    plt.tight_layout()
    plt.show()


def build_dataset(grid_file_path):
    grid = FileOpen(grid_file_path).open()

    print(grid.lines[0].rate)

    # configure grid for load shedding testing
    for ll in range(len(grid.lines)):
        grid.lines[ll].monitor_loading = True
    for tt in range(len(grid.transformers2w)):
        grid.transformers2w[tt].monitor_loading = True

    # Set options
    pf_options = PowerFlowOptions(control_q=False)

    opf_slack_options = OptimalPowerFlowOptions(ips_method=SolverType.NR,
                                                ips_tolerance=1e-6,
                                                ips_iterations=50,
                                                acopf_mode=AcOpfMode.ACOPFslacks,
                                                verbose=0)

    nc = compile_numerical_circuit_at(grid, t_idx=None)
    acopf_results = run_nonlinear_MP_opf(nc=nc, pf_options=pf_options,
                                         opf_options=opf_slack_options, pf_init=False, load_shedding=False)

    print()
    print(f"--- Base case ---")
    print(f"Base OPF loading {acopf_results.loading} .")
    print(f"Voltage magnitudes: {acopf_results.Vm}")
    print(f"Generators P: {acopf_results.Pg}")
    print(f"Generators Q: {acopf_results.Qg}")
    print(f"Error: {acopf_results.error}")

    print()
    print("--- Starting loop with fixed number of repetitions, then breaking ---")

    # Initialize tracking dictionary
    iteration_data = {
        'max_wk': [],
        'num_violations': [],
        'max_voltage_slack': [],
        'avg_voltage_slack': [],
        'max_flow_slack': [],
        'avg_flow_slack': [],
        'total_cost': [],
        'num_cuts': []
    }

    linear_multiple_contingencies = LinearMultiContingencies(grid, grid.get_contingency_groups())

    prob_cont = 0
    max_iter = 50
    tolerance = 1e-5

    n_con_groups = len(linear_multiple_contingencies.contingency_groups_used)
    n_con_all = n_con_groups * 100
    v_slacks = np.zeros(n_con_all)
    f_slacks = np.zeros(n_con_all)
    W_k_vec = np.zeros(n_con_all)
    Z_k_vec = np.zeros((n_con_all, nc.generator_data.nelm))
    u_j_vec = np.zeros((n_con_all, nc.generator_data.nelm))

    dataset = []

    # Start main loop over iterations
    for klm in range(max_iter):
        print(f"General iteration {klm + 1} of {max_iter}")

        viols = 0

        W_k_local = np.zeros(n_con_groups)

        br_lists = grid.get_branch_lists()
        all_branches = [br for group in br_lists for br in group]
        # print(len(all_branches))

        for ic, contingency_group in enumerate(linear_multiple_contingencies.contingency_groups_used):

            contingencies = linear_multiple_contingencies.contingency_group_dict[contingency_group.idtag]
            print(f"\nContingency group {ic}: {contingency_group.name}")

            if contingencies is None:
                print(f"Contingencies have not been initialised.")
                break

            # Set contingency status
            nc.set_con_or_ra_status(contingencies)

            for cont in contingencies:
                try:
                    br_idx = next(i for i, br in enumerate(all_branches) if br.name == cont.name)
                    nc.passive_branch_data.active[br_idx] = False  # Deactivate the affected branch

                    # Rebuild islands after modification
                    islands = nc.split_into_islands()

                    if len(islands) > 1:
                        island_sizes = [island.nbus for island in islands]
                        largest_island_idx = np.argmax(island_sizes)
                        island = islands[largest_island_idx]
                    else:
                        island = islands[0]

                    indices = island.get_simulation_indices()

                    if len(indices.vd) > 0:
                        print('Selected island with size:', island.nbus)



                        slack_sol_cont = run_nonlinear_SP_scopf(
                            nc=island,
                            pf_options=pf_options,
                            opf_options=opf_slack_options,
                            pf_init=False,
                            mp_results=acopf_results,
                            load_shedding=False,
                        )
                        # print(f"Error: {slack_sol_cont.error}")

                        # Collect slacks
                        v_slack = max(np.maximum(slack_sol_cont.sl_vmax, slack_sol_cont.sl_vmin))
                        f_slack = max(np.maximum(slack_sol_cont.sl_sf, slack_sol_cont.sl_st))
                        v_slacks[ic] = v_slack
                        f_slacks[ic] = f_slack
                        W_k_local[ic] = slack_sol_cont.W_k

                        if slack_sol_cont.error > 1e-6:
                            print(f"Error: {slack_sol_cont.error}")
                        print(f"u_j: {slack_sol_cont.u_j}")

                        # if slack_sol_cont.W_k > tolerance:
                        #     W_k_vec[prob_cont] = slack_sol_cont.W_k
                        #     Z_k_vec[prob_cont, island.generator_data.original_idx] = slack_sol_cont.Z_k
                        #     u_j_vec[prob_cont, island.generator_data.original_idx] = slack_sol_cont.u_j
                        #     prob_cont += 1
                        #     viols += 1
                        #
                        #     # print('nbus', island.nbus, 'ngen', island.ngen)
                        #     print(f"W_k: {slack_sol_cont.W_k}")
                        #     print(f"Z_k: {slack_sol_cont.Z_k}")
                        #     print(f"u_j: {slack_sol_cont.u_j}")
                        #     print(f"Vmax slack: {slack_sol_cont.sl_vmax}")
                        #     print(f"Vmin slack: {slack_sol_cont.sl_vmin}")
                        #     print(f"Sf slack: {slack_sol_cont.sl_sf}")
                        #     print(f"St slack: {slack_sol_cont.sl_st}")
                        if slack_sol_cont.W_k > tolerance:
                            W_k_vec[prob_cont] = slack_sol_cont.W_k
                            Z_k_vec[prob_cont, island.generator_data.original_idx] = slack_sol_cont.Z_k
                            u_j_vec[prob_cont, island.generator_data.original_idx] = slack_sol_cont.u_j
                            prob_cont += 1
                            viols += 1

                            # print('nbus', island.nbus, 'ngen', island.ngen)
                            print(f"W_k: {slack_sol_cont.W_k}")
                            print(f"Z_k: {slack_sol_cont.Z_k}")
                            print(f"u_j: {slack_sol_cont.u_j}")
                            print(f"Vmax slack: {slack_sol_cont.sl_vmax}")
                            print(f"Vmin slack: {slack_sol_cont.sl_vmin}")
                            print(f"Sf slack: {slack_sol_cont.sl_sf}")
                            print(f"St slack: {slack_sol_cont.sl_st}")

                            full_u_j = torch.zeros(nc.generator_data.nelm, dtype=torch.float32)
                            full_z_k = torch.zeros(nc.generator_data.nelm, dtype=torch.float32)

                            if hasattr(island.generator_data, "original_idx"):
                                for i, idx_g in enumerate(island.generator_data.original_idx):
                                    full_u_j[idx_g] = slack_sol_cont.u_j[i]
                                    full_z_k[idx_g] = slack_sol_cont.Z_k[i]

                                x_input = torch.cat([
                                    torch.tensor([ic], dtype=torch.float32),
                                    torch.tensor(acopf_results.Pg, dtype=torch.float32)
                                ]).unsqueeze(0)

                                # data = Data(
                                #     x=x_input,
                                #     y_wk=torch.tensor([slack_sol_cont.W_k], dtype=torch.float32),
                                #     y_uj=full_u_j,
                                #     y_zk=full_z_k
                                # )
                                # dataset.append(data)


                    else:
                        print("No valid voltage-dependent nodes found in island. Skipping.")

                    nc.passive_branch_data.active[br_idx] = True
                except StopIteration:
                    print(f"Line with name '{cont.name}' not found in grid.lines. Skipping.")

            # Revert contingency
            nc.set_con_or_ra_status(contingencies, revert=True)

        if viols > 0:
            # crop the dimension 0
            W_k_vec_used = W_k_vec[:prob_cont]
            Z_k_vec_used = Z_k_vec[:prob_cont, :]
            u_j_vec_used = u_j_vec[:prob_cont, :]

        # Store metrics for this iteration
        if viols > 0:
            iteration_data['max_wk'].append(W_k_local.max())
            iteration_data['max_voltage_slack'].append(v_slacks.max())
            iteration_data['avg_voltage_slack'].append(v_slacks.mean())
            iteration_data['max_flow_slack'].append(f_slacks.max())
            iteration_data['avg_flow_slack'].append(f_slacks.mean())
        else:
            iteration_data['max_wk'].append(1e-10)
            iteration_data['max_voltage_slack'].append(1e-10)
            iteration_data['avg_voltage_slack'].append(1e-10)
            iteration_data['max_flow_slack'].append(1e-10)
            iteration_data['avg_flow_slack'].append(1e-10)
            print('Master problem solution found')

        iteration_data['num_violations'].append(viols)

        # Run the MP with information from the SPs
        print('')
        print("--- Feeding SPs info to MP ---")
        acopf_results = run_nonlinear_MP_opf(nc=nc,
                                             pf_options=pf_options,
                                             opf_options=opf_slack_options,
                                             pf_init=False,
                                             W_k_vec=W_k_vec_used,
                                             Z_k_vec=Z_k_vec_used,
                                             u_j_vec=u_j_vec_used,
                                             load_shedding=False)

        # Store generation cost
        total_cost = np.sum(acopf_results.Pcost)
        iteration_data['total_cost'].append(total_cost)

        # Print current iteration metrics
        print(f"Maximum W_k: {iteration_data['max_wk'][-1]}")
        print(f"Number of violations: {iteration_data['num_violations'][-1]}")
        print(f"Maximum voltage slack: {iteration_data['max_voltage_slack'][-1]}")
        print(f"Average voltage slack: {iteration_data['avg_voltage_slack'][-1]}")
        print(f"Maximum flow slack: {iteration_data['max_flow_slack'][-1]}")
        print(f"Average flow slack: {iteration_data['avg_flow_slack'][-1]}")
        print(f"Total generation cost: {total_cost}")

        if viols == 0:
            break
        iteration_data['num_cuts'].append(prob_cont)
        print(f"Total number of cuts: {iteration_data['num_cuts'][-1]}")
        print('-')
        print('Length W_k_vec', len(W_k_vec))

    # Plot the results
    # plot_scopf_progress(iteration_data)

    return dataset


from sklearn.preprocessing import StandardScaler

scaler_wk = StandardScaler()
scaler_uj = StandardScaler()
scaler_zk = StandardScaler()

def scale_targets(dataset):
    global scaler_wk, scaler_uj, scaler_zk

    wk = []
    uj = []
    zk = []

    # Collect all targets
    for data in dataset:
        wk.append(data.y_wk.numpy().reshape(-1, 1))  # shape (n, 1)
        uj.append(data.y_uj.numpy().reshape(1, -1))  # shape (1, n)
        zk.append(data.y_zk.numpy().reshape(1, -1))  # shape (1, n)

    wk = np.vstack(wk)  # shape (samples, 1)
    uj = np.vstack(uj)  # shape (samples, uj_dim)
    zk = np.vstack(zk)  # shape (samples, zk_dim)

    # Fit scalers
    scaler_wk.fit(wk)
    scaler_uj.fit(uj)
    scaler_zk.fit(zk)

    # Transform and reassign
    for data in dataset:
        data.y_wk = torch.tensor(scaler_wk.transform(data.y_wk.reshape(-1, 1)), dtype=torch.float).squeeze()
        data.y_uj = torch.tensor(scaler_uj.transform(data.y_uj.reshape(1, -1)), dtype=torch.float).squeeze()
        data.y_zk = torch.tensor(scaler_zk.transform(data.y_zk.reshape(1, -1)), dtype=torch.float).squeeze()

def train_model(model, train_loader, val_loader, optimizer, loss_fn, epochs=500, alpha=10, beta=100):
    train_losses = []
    val_losses = []

    for epoch in range(epochs):
        model.train()
        total_train_loss = 0

        for batch in train_loader:
            optimizer.zero_grad()

            x = batch.x.to(model.device)
            wk_pred, uj_pred, zk_pred = model(x)

            # Reshape the manually-attached y_uj and y_zk to [batch_size, 5]
            batch_size = x.size(0)
            uj_true = batch.y_uj.view(batch_size, -1).to(model.device)
            zk_true = batch.y_zk.view(batch_size, -1).to(model.device)

            loss_wk = loss_fn(wk_pred, batch.y_wk.to(model.device))
            loss_uj = loss_fn(uj_pred, uj_true)
            loss_zk = loss_fn(zk_pred, zk_true)

            loss = loss_wk + alpha * loss_uj + beta * loss_zk
            loss.backward()
            optimizer.step()

            total_train_loss += loss.item()

        model.eval()
        total_val_loss = 0

        with torch.no_grad():
            for batch in val_loader:
                x = batch.x.to(model.device)
                wk_pred, uj_pred, zk_pred = model(x)

                batch_size = x.size(0)
                uj_true = batch.y_uj.view(batch_size, -1).to(model.device)
                zk_true = batch.y_zk.view(batch_size, -1).to(model.device)

                loss_wk = loss_fn(wk_pred, batch.y_wk.to(model.device))
                loss_uj = loss_fn(uj_pred, uj_true)
                loss_zk = loss_fn(zk_pred, zk_true)

                val_loss = loss_wk + alpha * loss_uj + beta * loss_zk
                total_val_loss += val_loss.item()

        avg_train_loss = total_train_loss / len(train_loader)
        avg_val_loss = total_val_loss / len(val_loader)

        train_losses.append(avg_train_loss)
        val_losses.append(avg_val_loss)

        print(f"Epoch {epoch+1:03}: Train Loss = {avg_train_loss:.6f}, Val Loss = {avg_val_loss:.6f}")

    return train_losses[-1]

# === Denormalize function ===
def denormalize_predictions(y_true_wk, y_pred_wk, y_true_uj, y_pred_uj, y_true_zk, y_pred_zk):
    y_true_wk = scaler_wk.inverse_transform(np.array(y_true_wk).reshape(-1, 1)).flatten()
    y_pred_wk = scaler_wk.inverse_transform(np.array(y_pred_wk).reshape(-1, 1)).flatten()

    y_true_uj = scaler_uj.inverse_transform(np.array(y_true_uj).reshape(-1, num_generators))
    y_pred_uj = scaler_uj.inverse_transform(np.array(y_pred_uj).reshape(-1, num_generators))

    y_true_zk = scaler_zk.inverse_transform(np.array(y_true_zk).reshape(-1, num_generators))
    y_pred_zk = scaler_zk.inverse_transform(np.array(y_pred_zk).reshape(-1, num_generators))

    return y_true_wk, y_pred_wk, y_true_uj, y_pred_uj, y_true_zk, y_pred_zk


# def evaluate_model(model, test_loader):
#     model.eval()
#     all_y_uj = []
#     all_uj_pred = []
#
#     num_generators = model.out_uj.out_features
#
#     with torch.no_grad():
#         for batch in test_loader:
#             x = batch.x.to(model.device)
#             y_uj = batch.y_uj.to(model.device)
#
#             # Forward pass
#             _, uj_pred, _ = model(x)
#
#             # Reshape to (batch_size, num_generators)
#             y_uj = y_uj.view(-1, num_generators)
#             uj_pred = uj_pred.view(-1, num_generators)
#
#             all_y_uj.append(y_uj)
#             all_uj_pred.append(uj_pred)
#
#     # Concatenate all batches
#     all_y_uj = torch.cat(all_y_uj, dim=0)
#     all_uj_pred = torch.cat(all_uj_pred, dim=0)
#
#     # Denormalize
#     uj_pred_denorm = scaler_uj.inverse_transform(all_uj_pred.cpu().numpy())
#     y_uj_denorm = scaler_uj.inverse_transform(all_y_uj.cpu().numpy())
#
#     # Convert back to tensors if needed
#     uj_pred_denorm = torch.tensor(uj_pred_denorm)
#     y_uj_denorm = torch.tensor(y_uj_denorm)
#
#     # Example: compute and print MSE
#     mse = torch.nn.functional.mse_loss(uj_pred_denorm, y_uj_denorm)
#     print(f"Test MSE on denormalized u_j: {mse.item():.4f}")

def evaluate_model(model, data_loader):
    # Collect predictions
    model.eval()
    y_true_wk, y_pred_wk, y_true_uj, y_pred_uj, y_true_zk, y_pred_zk = [], [], [], [], [], []

    with torch.no_grad():
        for batch in test_loader:
            x = batch.x.to(model.device)
            wk_pred, uj_pred, zk_pred = model(x)

            y_true_wk.extend(batch.y_wk.cpu().numpy())
            y_pred_wk.extend(wk_pred.cpu().numpy())

            y_true_uj.extend(batch.y_uj.view(-1, uj_pred.shape[1]).cpu().numpy())
            y_pred_uj.extend(uj_pred.cpu().numpy())

            y_true_zk.extend(batch.y_zk.view(-1, zk_pred.shape[1]).cpu().numpy())
            y_pred_zk.extend(zk_pred.cpu().numpy())

    # ✅ Denormalize
    y_true_wk, y_pred_wk, y_true_uj, y_pred_uj, y_true_zk, y_pred_zk = denormalize_predictions(
        y_true_wk, y_pred_wk, y_true_uj, y_pred_uj, y_true_zk, y_pred_zk
    )

    # Evaluate and plot
    evaluate_model_from_arrays(y_true_wk, y_pred_wk, y_true_uj, y_pred_uj, y_true_zk, y_pred_zk)

def evaluate_model_from_arrays(y_true_wk, y_pred_wk, y_true_uj, y_pred_uj, y_true_zk, y_pred_zk):
    def plot_pred_vs_true(true, pred, label):
        true = np.array(true).flatten()
        pred = np.array(pred).flatten()
        plt.figure()
        plt.scatter(true, pred, alpha=0.6)
        min_val = min(true.min(), pred.min())
        max_val = max(true.max(), pred.max())
        plt.plot([min_val, max_val], [min_val, max_val], 'r--')
        plt.xlabel('True')
        plt.ylabel('Predicted')
        plt.title(f'{label} - True vs Predicted')
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    def plot_error_hist(true, pred, label):
        errors = np.array(pred) - np.array(true)
        plt.figure()
        plt.hist(errors, bins=40, alpha=0.7)
        plt.title(f'{label} - Prediction Error Histogram')
        plt.xlabel('Error')
        plt.ylabel('Frequency')
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    def print_metrics(true, pred, label):
        mse = mean_squared_error(true, pred)
        r2 = r2_score(true, pred)
        print(f" {label} Metrics:")
        print(f"    MSE = {mse:.6f}")
        print(f"    R²  = {r2:.4f}")
        print()

    def save_to_csv(true_wk, pred_wk, true_uj, pred_uj, true_zk, pred_zk):
        df = pd.DataFrame({
            'W_k_true': np.array(true_wk).flatten(),
            'W_k_pred': np.array(pred_wk).flatten(),
            'u_j_true': np.array(true_uj).flatten(),
            'u_j_pred': np.array(pred_uj).flatten(),
            'Z_k_true': np.array(true_zk).flatten(),
            'Z_k_pred': np.array(pred_zk).flatten(),
        })
        df.to_csv("scopf_predictions.csv", index=False)
        print("✅ Results saved to scopf_predictions.csv")

    # Run evaluation
    plot_pred_vs_true(y_true_uj, y_pred_uj, 'u_j')
    plot_error_hist(y_true_uj, y_pred_uj, 'u_j')
    print_metrics(y_true_uj, y_pred_uj, 'u_j')

    plot_pred_vs_true(y_true_wk, y_pred_wk, 'W_k')
    plot_error_hist(y_true_wk, y_pred_wk, 'W_k')
    print_metrics(y_true_wk, y_pred_wk, 'W_k')

    plot_pred_vs_true(y_true_zk, y_pred_zk, 'Z_k')
    plot_error_hist(y_true_zk, y_pred_zk, 'Z_k')
    print_metrics(y_true_zk, y_pred_zk, 'Z_k')

    save_to_csv(y_true_wk, y_pred_wk, y_true_uj, y_pred_uj, y_true_zk, y_pred_zk)
    #
    # # Plot and metrics
    # def plot_pred_vs_true(true, pred, label):
    #     true = np.array(true).flatten()
    #     pred = np.array(pred).flatten()
    #     plt.figure()
    #     plt.scatter(true, pred, alpha=0.6)
    #     min_val = min(true.min(), pred.min())
    #     max_val = max(true.max(), pred.max())
    #     plt.plot([min_val, max_val], [min_val, max_val], 'r--')
    #     plt.xlabel('True')
    #     plt.ylabel('Predicted')
    #     plt.title(f'{label} - True vs Predicted')
    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.show()
    #
    # def plot_error_hist(true, pred, label):
    #     errors = np.array(pred) - np.array(true)
    #     plt.figure()
    #     plt.hist(errors, bins=40, alpha=0.7)
    #     plt.title(f'{label} - Prediction Error Histogram')
    #     plt.xlabel('Error')
    #     plt.ylabel('Frequency')
    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.show()
    #
    # def print_metrics(true, pred, label):
    #     true = np.array(true).flatten()
    #     pred = np.array(pred).flatten()
    #     print(f"🔍 {label} shape check: true={true.shape}, pred={pred.shape}")
    #
    #     mse = mean_squared_error(true, pred)
    #     r2 = r2_score(true, pred)
    #     print(f"📌 {label} Metrics:")
    #     print(f"    MSE = {mse:.6f}")
    #     print(f"    R²  = {r2:.4f}")
    #     print()
    #
    # def save_to_csv(true_wk, pred_wk, true_uj, pred_uj, true_zk, pred_zk):
    #     # Ensure all arrays are 1D
    #     true_wk = np.array(true_wk).flatten()
    #     pred_wk = np.array(pred_wk).flatten()
    #     true_uj = np.array(true_uj).flatten()
    #     pred_uj = np.array(pred_uj).flatten()
    #     true_zk = np.array(true_zk).flatten()
    #     pred_zk = np.array(pred_zk).flatten()
    #
    #     # Determine minimum length to align them
    #     min_len = min(len(true_wk), len(pred_wk), len(true_uj), len(pred_uj), len(true_zk), len(pred_zk))
    #
    #     df = pd.DataFrame({
    #         'W_k_true': true_wk[:min_len],
    #         'W_k_pred': pred_wk[:min_len],
    #         'u_j_true': true_uj[:min_len],
    #         'u_j_pred': pred_uj[:min_len],
    #         'Z_k_true': true_zk[:min_len],
    #         'Z_k_pred': pred_zk[:min_len],
    #     })
    #
    #     df.to_csv("scopf_predictions.csv", index=False)
    #     print(" Results saved to scopf_predictions.csv")
    #
    # # Run visualizations and evaluation
    # plot_pred_vs_true(y_true_uj, y_pred_uj, 'u_j')
    # plot_error_hist(y_true_uj, y_pred_uj, 'u_j')
    # print_metrics(y_true_uj, y_pred_uj, 'u_j')
    #
    # plot_pred_vs_true(y_true_wk, y_pred_wk, 'W_k')
    # plot_error_hist(y_true_wk, y_pred_wk, 'W_k')
    # print_metrics(y_true_wk, y_pred_wk, 'W_k')
    #
    # plot_pred_vs_true(y_true_zk, y_pred_zk, 'Z_k')
    # plot_error_hist(y_true_zk, y_pred_zk, 'Z_k')
    # print_metrics(y_true_zk, y_pred_zk, 'Z_k')
    #
    # save_to_csv(y_true_wk, y_pred_wk, y_true_uj, y_pred_uj, y_true_zk, y_pred_zk)


if __name__ == '__main__':
    grid_file_path = "/Users/CristinaFray/PycharmProjects/GridCal/src/trunk/scopf/case14_cont_v12.gridcal"
    grid = FileOpen(grid_file_path).open()

    # # Placeholder contingencies
    # contingency_list = [[] for _ in range(len(grid.get_contingency_groups()))]
    # print(contingency_list)
    #
    nc = compile_numerical_circuit_at(grid, t_idx=None)

    print(f"Number of buses: {nc.bus_data.nbus}")
    print(f"Number of generators: {nc.generator_data.nelm}")

    class MPResultsMock:
        Pg = np.random.rand(nc.generator_data.nelm)
        Qg = np.random.rand(nc.generator_data.nelm)

    mp_results = MPResultsMock()

    json_dir = "/GridCalEngine/Simulations/SCOPF_GNN/new_aug_data/scopf_outputs_14"  # your directory with saved JSONs
    dataset = load_scopf_json_dataset(json_dir)

    print(f"Loaded {len(dataset)} contingency samples from JSON")

    # Build and split dataset
    # dataset = build_dataset(grid_file_path)
    # train_dataset, val_dataset = train_test_split(dataset, test_size=0.05, random_state=42)
    train_val, test_dataset = train_test_split(dataset, test_size=0.10, random_state=42)

    # Step 2: Split 5% of the remaining 95% for validation
    val_ratio = 0.1  # 10% of the remaining 90% will be validation
    train_dataset, val_dataset = train_test_split(train_val, test_size=val_ratio, random_state=42)
    print(f"Train samples: {len(train_dataset)}")
    print(f"Val samples: {len(val_dataset)}")
    print(f"Test samples: {len(test_dataset)}")

    scale_targets(train_dataset + val_dataset)

    # Create DataLoaders
    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=16, shuffle=False)

    # Inspect batch format
    for batch in train_loader:
        print("--- Debug Batch Shapes ---")
        print(f"x: {batch.x.shape}")
        print(f"y_wk: {batch.y_wk.shape}")
        print(f"y_uj: {batch.y_uj.shape}")
        print(f"y_zk: {batch.y_zk.shape}")
        break

    input_dim = dataset[0].x.size(-1)
    hidden_dim = 64
    num_generators = len(mp_results.Pg)

    model = SCOPFParameterRegressor(input_dim, hidden_dim, num_generators)
    model.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(model.device)

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = torch.nn.MSELoss()

    # Train the model
    train_model(model, train_loader, val_loader, optimizer, loss_fn)
    evaluate_model(model, test_loader)

    print(f"Total samples in dataset: {len(dataset)}")

    # Build results DataFrame
    df = pd.DataFrame({
        'Contingency ID': [data.x[0, 0].item() for data in dataset],
        'Pg': [data.x[0, 1:].tolist() for data in dataset],
        'W_k': [data.y_wk.item() for data in dataset],
        'Z_k': [data.y_zk.tolist() for data in dataset],
        'u_j': [data.y_uj.tolist() for data in dataset],
    })

    print(df.head())


import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.decomposition import PCA

def evaluate_and_plot(model, test_dataset):
    model.eval()
    all_preds = []
    all_targets = []

    with torch.no_grad():
        for data in test_dataset:
            x = data.x.unsqueeze(0).to(model.device)
            _, pred_uj, _ = model(x)
            all_preds.append(pred_uj.cpu().squeeze().numpy())
            all_targets.append(data.y_uj.cpu().numpy())

    all_preds = np.array(all_preds)
    all_targets = np.array(all_targets)

    # PCA projection to 2D
    pca = PCA(n_components=2)
    preds_2d = pca.fit_transform(all_preds)
    targets_2d = pca.transform(all_targets)

    # Plot
    plt.figure(figsize=(10, 6))
    sns.scatterplot(x=targets_2d[:, 0], y=targets_2d[:, 1], label='Actual', color='blue', alpha=0.6)
    sns.scatterplot(x=preds_2d[:, 0], y=preds_2d[:, 1], label='Predicted', color='red', alpha=0.6)
    plt.title("PCA Projection of Predicted vs Actual $u_j$")
    plt.xlabel("PCA Component 1")
    plt.ylabel("PCA Component 2")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

# Call it after model evaluation
