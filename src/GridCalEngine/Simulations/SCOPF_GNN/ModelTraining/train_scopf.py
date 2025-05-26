import torch
import torch.nn.functional as F
from matplotlib import cm
from torch import nn
from torch_geometric.nn import NNConv, global_mean_pool
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import networkx as nx
from torch_geometric.utils import to_networkx
from sklearn.preprocessing import StandardScaler
import random
import os
import time

from GridCalEngine import (FileOpen, PowerFlowOptions, SolverType, AcOpfMode, OptimalPowerFlowOptions,
                           compile_numerical_circuit_at, FileSave)
from GridCalEngine.Simulations.SCOPF_GNN.NumericalMethods.scopf import (run_nonlinear_MP_opf, LinearMultiContingencies,
                                                                        run_nonlinear_SP_scopf)

from codecarbon import EmissionsTracker

# GPU/CPU configuration
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

# Grid file path
grid_file_path_train = "/Users/CristinaFray/PycharmProjects/GridCal/src/trunk/scopf/case5.gridcal"

# GNN Model params
f_node_in = 3  # W_k, u_j, Z_k
f_edge_in = 3  # P, Q and is_active
hidden_channels = 64
num_layers = 4


# Modify training targets and model output for SCOPF to predict W_k, u_j, Z_k
def generate_scopf_data(grid_file_path):
    print(f"Generating SCOPF N-1 Contingency training data from: {grid_file_path}")
    if not os.path.exists(grid_file_path):
        print(f"ERROR: File not found: {grid_file_path}")
        return []

    grid = FileOpen(grid_file_path).open()

    for ll in range(len(grid.lines)):
        grid.lines[ll].monitor_loading = True
    for tt in range(len(grid.transformers2w)):
        grid.transformers2w[tt].monitor_loading = True

    pf_options = PowerFlowOptions(control_q=False)
    opf_slack_options = OptimalPowerFlowOptions(
        ips_method=SolverType.NR,
        ips_tolerance=1e-6,
        ips_iterations=50,
        acopf_mode=AcOpfMode.ACOPFslacks,
        verbose=0)

    # Compile base circuit and contingencies
    nc = compile_numerical_circuit_at(grid)

    acopf_results = run_nonlinear_MP_opf(nc=nc, pf_options=pf_options,
                                         opf_options=opf_slack_options, pf_init=False, load_shedding=False)

    print()
    print(f"--- Base case ---")
    print(f"Base OPF loading {acopf_results.loading} .")
    print(f"Voltage magnitudes: {acopf_results.Vm}")
    print(f"Generators P: {acopf_results.Pg}")
    print(f"Generators Q: {acopf_results.Qg}")
    print(f"Error: {acopf_results.error}")

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
    contingency_groups = linear_multiple_contingencies.contingency_groups_used

    data_scopf = []
    prob_cont = 0
    max_iter = 25
    tolerance = 1e-5

    n_con_groups = len(linear_multiple_contingencies.contingency_groups_used)
    n_con_all = n_con_groups * 100
    v_slacks = np.zeros(n_con_all)
    f_slacks = np.zeros(n_con_all)
    W_k_vec = np.zeros(n_con_all)
    Z_k_vec = np.zeros((n_con_all, nc.generator_data.nelm))
    u_j_vec = np.zeros((n_con_all, nc.generator_data.nelm))

    for klm in range(max_iter):
        print(f"General iteration {klm + 1} of {max_iter}")

        viols = 0
        W_k_local = np.zeros(n_con_groups)

        br_lists = grid.get_branch_lists()
        all_branches = [br for group in br_lists for br in group]

        for ic, contingency_group in enumerate(linear_multiple_contingencies.contingency_groups_used):

            contingencies = linear_multiple_contingencies.contingency_group_dict[contingency_group.idtag]
            print(f"\nContingency group {ic}: {contingency_group.name}")

            if contingencies is None:
                print(f"Contingencies have not been initialised.")
                break

            nc.set_con_or_ra_status(contingencies)

            # --- Deactivate N-1 branches ---
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

                    bus_names = list(island.bus_data.names)
                    print(f"Bus names: {bus_names}")

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

                        # Collect slacks
                        v_slack = max(np.maximum(slack_sol_cont.sl_vmax, slack_sol_cont.sl_vmin))
                        f_slack = max(np.maximum(slack_sol_cont.sl_sf, slack_sol_cont.sl_st))
                        v_slacks[ic] = v_slack
                        f_slacks[ic] = f_slack
                        W_k_local[ic] = slack_sol_cont.W_k

                        if slack_sol_cont.error > 1e-6:
                            print(f"Error: {slack_sol_cont.error}")
                        print(f"u_j: {slack_sol_cont.u_j}")

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

                            # --- Node features ---
                            Pg = island.generator_data.p
                            Qg = island.generator_data.qmin

                            # Create node feature vectors: for all buses, not just generators
                            P_node = np.zeros(island.nbus)
                            Q_node = np.zeros(island.nbus)
                            P_node[island.generator_data.bus_idx] = Pg
                            Q_node[island.generator_data.bus_idx] = Qg

                            x_node = torch.tensor(np.vstack([P_node, Q_node]).T, dtype=torch.float32)

                            y_node = torch.tensor(np.vstack([slack_sol_cont.Vm, slack_sol_cont.Va]).T,
                                                  dtype=torch.float32)

                            R = island.passive_branch_data.R
                            X = island.passive_branch_data.X
                            B = island.passive_branch_data.B
                            F = island.passive_branch_data.F
                            T = island.passive_branch_data.T
                            is_active = island.passive_branch_data.active.astype(np.float32)

                            original_to_new = island.bus_data.get_original_to_island_bus_dict()

                            filtered_edges = []
                            filtered_attrs = []
                            for i, (f, t) in enumerate(zip(F, T)):
                                f = int(f)
                                t = int(t)
                                if f in original_to_new and t in original_to_new:
                                    filtered_edges.append((original_to_new[f], original_to_new[t]))
                                    filtered_attrs.append([R[i], X[i], B[i], is_active[i]])

                            if not filtered_edges:
                                print("No valid edges after remapping. Skipping sample.")
                                continue

                            edge_index = torch.tensor(filtered_edges, dtype=torch.long).T
                            edge_attr = torch.tensor(filtered_attrs, dtype=torch.float32)

                            if edge_index.max() >= x_node.shape[0]:
                                print(
                                    f"Skipping sample due to invalid edge_index (max={edge_index.max().item()}, nodes={x_node.shape[0]})")
                                continue

                            y_edge = torch.zeros((len(filtered_edges), 4), dtype=torch.float32)

                            data = Data(
                                x=x_node,
                                edge_index=edge_index,
                                edge_attr=edge_attr,
                                y_node=y_node,
                                y_edge=y_edge,
                                num_nodes=len(y_node)
                            )

                            data.bus_names = bus_names  # attach to data object
                            print(f"Bus names: {bus_names}")

                            data_scopf.append(data)
                            print(f"Sample {len(data_scopf)} added.")

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
        else:  # assign small number
            W_k_vec_used = np.zeros(1)
            Z_k_vec_used = np.zeros((1, nc.generator_data.nelm))
            u_j_vec_used = np.zeros((1, nc.generator_data.nelm))

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
        print('Length Z_k_vec', len(Z_k_vec))
        print('Length u_j_vec', len(u_j_vec))

    print(f"\nDone. Total training samples generated: {len(data_scopf)}")
    return data_scopf


def generate_augmented_scopf_data(grid_file_path, num_variants=10, variation_scale=0.1):
    all_augmented_data = []

    # Target directory to save variants
    variant_dir = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/GridVariants"
    os.makedirs(variant_dir, exist_ok=True)

    for i in range(num_variants):
        print(f"\nGenerating variant {i + 1} of {num_variants}")

        # Load grid
        grid = FileOpen(grid_file_path).open()

        for line in grid.lines:
            line.R *= (1.0 + np.random.uniform(-variation_scale, variation_scale))
            line.X *= (1.0 + np.random.uniform(-variation_scale, variation_scale))
            line.B *= (1.0 + np.random.uniform(-variation_scale, variation_scale))

        for tf in grid.transformers2w:
            tf.R *= (1.0 + np.random.uniform(-variation_scale, variation_scale))
            tf.X *= (1.0 + np.random.uniform(-variation_scale, variation_scale))
            tf.B *= (1.0 + np.random.uniform(-variation_scale, variation_scale))

        for gen in grid.generators:
            gen.P *= (1.0 + np.random.uniform(-variation_scale, variation_scale))
            # gen.Q *= (1.0 + np.random.uniform(-variation_scale, variation_scale))

        variant_filename = os.path.join(variant_dir, f"variant_{i + 1}.gridcal")
        FileSave(grid, variant_filename).save()
        print(f"Saved variant to: {variant_filename}")

        # Generate SCOPF data from this variant
        variant_data = generate_scopf_data(variant_filename)
        all_augmented_data.extend(variant_data)

    print(f"\nTotal augmented training samples: {len(all_augmented_data)}")
    return all_augmented_data


class SCOPFGNN(torch.nn.Module):
    def __init__(self, node_in_feat, edge_in_feat, hidden_feat, num_generators, num_layers=3):
        super().__init__()
        self.node_embed = torch.nn.Sequential(
            torch.nn.Linear(node_in_feat, hidden_feat),
            torch.nn.ReLU(),
            torch.nn.BatchNorm1d(hidden_feat)
        )

        self.convs = torch.nn.ModuleList()
        for _ in range(num_layers):
            mlp = torch.nn.Sequential(
                torch.nn.Linear(edge_in_feat, hidden_feat * 2),
                torch.nn.ReLU(),
                torch.nn.Linear(hidden_feat * 2, hidden_feat * hidden_feat)
            )
            self.convs.append(NNConv(hidden_feat, hidden_feat, mlp, aggr='mean'))

        # Global prediction heads
        self.fc_wk = torch.nn.Sequential(
            torch.nn.Linear(hidden_feat, hidden_feat),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_feat, 1)
        )
        self.fc_uj = torch.nn.Sequential(
            torch.nn.Linear(hidden_feat, hidden_feat),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_feat, num_generators)
        )
        self.fc_zk = torch.nn.Sequential(
            torch.nn.Linear(hidden_feat, hidden_feat),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_feat, num_generators)
        )

    def forward(self, data):
        x, edge_index, edge_attr, batch = data.x, data.edge_index, data.edge_attr, data.batch
        h = self.node_embed(x)
        for conv in self.convs:
            h = F.relu(conv(h, edge_index, edge_attr))

        hg = global_mean_pool(h, batch)

        wk_pred = self.fc_wk(hg).squeeze(-1)
        uj_pred = self.fc_uj(hg)
        zk_pred = self.fc_zk(hg)

        return wk_pred, uj_pred, zk_pred


def train_scopf(model, loader, optimizer, loss_fn):
    model.train()
    total_loss = 0
    for data in loader:
        data = data.to(model.device)
        optimizer.zero_grad()
        wk_pred, uj_pred, zk_pred = model(data)
        loss = (
                loss_fn(wk_pred, data.y_wk) +
                loss_fn(uj_pred, data.y_uj) +
                loss_fn(zk_pred, data.y_zk)
        )
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * data.num_graphs
    return total_loss / len(loader.dataset)


def evaluate_scopf(model, loader, loss_fn):
    model.eval()
    total_loss = 0
    all_wk_true, all_wk_pred = [], []
    all_uj_true, all_uj_pred = [], []
    all_zk_true, all_zk_pred = [], []

    with torch.no_grad():
        for data in loader:
            data = data.to(model.device)
            wk_pred, uj_pred, zk_pred = model(data)

            loss = (
                    loss_fn(wk_pred, data.y_wk) +
                    loss_fn(uj_pred, data.y_uj) +
                    loss_fn(zk_pred, data.y_zk)
            )
            total_loss += loss.item() * data.num_graphs

            all_wk_true.append(data.y_wk)
            all_wk_pred.append(wk_pred)
            all_uj_true.append(data.y_uj)
            all_uj_pred.append(uj_pred)
            all_zk_true.append(data.y_zk)
            all_zk_pred.append(zk_pred)

    return (
        total_loss / len(loader.dataset),
        torch.cat(all_wk_true),
        torch.cat(all_wk_pred),
        torch.cat(all_uj_true),
        torch.cat(all_uj_pred),
        torch.cat(all_zk_true),
        torch.cat(all_zk_pred),
    )


def plot_predictions(wk_true, wk_pred, title="W_k Predictions", save_path=None):
    wk_true = wk_true.cpu().numpy()
    wk_pred = wk_pred.cpu().numpy()

    plt.figure(figsize=(8, 6))
    plt.scatter(wk_true, wk_pred, alpha=0.6, edgecolors='k')
    min_val = min(wk_true.min(), wk_pred.min())
    max_val = max(wk_true.max(), wk_pred.max())
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', label='Ideal')
    plt.xlabel('True W_k')
    plt.ylabel('Predicted W_k')
    plt.title(title)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path)
        print(f"Saved W_k plot to {save_path}")
    plt.show()


def plot_vector_predictions(true_tensor, pred_tensor, label="u_j", save_path=None):
    true_np = true_tensor.cpu().numpy().flatten()
    pred_np = pred_tensor.cpu().numpy().flatten()

    plt.figure(figsize=(8, 6))
    plt.scatter(true_np, pred_np, alpha=0.6, edgecolors='k')
    min_val = min(true_np.min(), pred_np.min())
    max_val = max(true_np.max(), pred_np.max())
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', label='Ideal')
    plt.xlabel(f"True {label}")
    plt.ylabel(f"Predicted {label}")
    plt.title(f"{label} Prediction")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path)
        print(f"Saved {label} plot to {save_path}")
    plt.show()


def visualize_grid_sample(data, node_key='y_node', edge_key='y_edge', title="Grid Sample Visualization", error_mode=False):
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    import matplotlib.cm as cm

    G = to_networkx(data, to_undirected=True)
    pos = nx.spring_layout(G, seed=42)

    # --- Node values: voltage magnitude Vm or error ---
    node_vals = getattr(data, node_key, None)
    if node_vals is not None:
        node_vals = node_vals.cpu().numpy()
        node_vals_flat = node_vals[:, 0]  # Vm is the first column
        if error_mode and hasattr(data, 'y_node_pred'):
            pred_vals = data.y_node_pred.cpu().numpy()
            node_vals_flat = np.abs(pred_vals[:, 0] - node_vals[:, 0])
        node_norm = mcolors.Normalize(vmin=node_vals_flat.min(), vmax=node_vals_flat.max())
        node_cmap = plt.get_cmap('viridis')
        node_colors = node_cmap(node_norm(node_vals_flat))
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=400)

        labels = {i: f"{v:.2f}" for i, v in enumerate(node_vals_flat)}
        if hasattr(data, 'bus_names'):
            labels = {i: f"{data.bus_names[i]}\n{v:.2f}" for i, v in enumerate(node_vals_flat)}
        nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)
    else:
        nx.draw_networkx_nodes(G, pos, node_color='gray', node_size=400)

    # --- Edge values: flow magnitude or error ---
    edge_vals = getattr(data, edge_key, None)
    if edge_vals is not None and data.edge_index.numel() > 0:
        edge_vals = edge_vals.cpu().numpy()
        edge_magnitudes = np.linalg.norm(edge_vals[:, :2], axis=1)
        if error_mode and hasattr(data, 'y_edge_pred'):
            pred_edge = data.y_edge_pred.cpu().numpy()
            edge_magnitudes = np.abs(np.linalg.norm(pred_edge[:, :2], axis=1) - edge_magnitudes)

        edge_norm = mcolors.Normalize(vmin=edge_magnitudes.min(), vmax=edge_magnitudes.max())
        edge_cmap = plt.get_cmap('plasma')
        edge_colors = edge_cmap(edge_norm(edge_magnitudes))
        nx.draw_networkx_edges(G, pos, edge_color=edge_colors, width=2)

        sm = cm.ScalarMappable(norm=edge_norm, cmap=edge_cmap)
    else:
        nx.draw_networkx_edges(G, pos)
        sm = None if node_vals is None else cm.ScalarMappable(norm=node_norm, cmap=node_cmap)

    plt.title(title)
    if sm:
        cbar = plt.colorbar(sm, ax=plt.gca(), shrink=0.7)
        cbar.set_label('Error' if error_mode else 'Magnitude')

    plt.axis('off')
    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    tracker = EmissionsTracker(
        project_name="SCOPF_GNN_Training",
        output_dir="/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/CO2",
    )
    tracker.start()

    train_set = 0.9
    val_set = 0.05
    test_set = 0.05
    batch_size = 32
    epochs = 50
    lr = 1e-3

    all_data = generate_augmented_scopf_data(
        grid_file_path=grid_file_path_train,
        num_variants=10,
        variation_scale=0.01
    )

    for d in all_data:
        d.y_wk = torch.tensor([getattr(d, 'W_k', 0.0)], dtype=torch.float32)
        d.y_uj = torch.tensor(getattr(d, 'u_j', np.zeros(5)), dtype=torch.float32).unsqueeze(0)
        d.y_zk = torch.tensor(getattr(d, 'Z_k', np.zeros(5)), dtype=torch.float32).unsqueeze(0)

    random.Random(42).shuffle(all_data)
    num_total = len(all_data)
    num_train = int(train_set * num_total)
    num_val = int(val_set * num_total)

    train_data = all_data[:num_train]
    val_data = all_data[num_train: num_train + num_val]
    test_data = all_data[num_train + num_val:]

    train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=batch_size)
    test_loader = DataLoader(test_data, batch_size=batch_size)

    model = SCOPFGNN(node_in_feat=2, edge_in_feat=4, hidden_feat=64, num_generators=5).to(device)
    model.device = device
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    loss_fn = nn.MSELoss()

    train_losses, val_losses = [], []

    for epoch in range(1, epochs + 1):
        train_loss = train_scopf(model, train_loader, optimizer, loss_fn)
        val_loss, *_ = evaluate_scopf(model, val_loader, loss_fn)
        train_losses.append(train_loss)
        val_losses.append(val_loss)
        print(f"Epoch {epoch:03d}: Train Loss = {train_loss:.6f}, Val Loss = {val_loss:.6f}")

    print("\nEvaluating on Test Set...")
    (
        test_loss,
        test_wk_true, test_wk_pred,
        test_uj_true, test_uj_pred,
        test_zk_true, test_zk_pred
    ) = evaluate_scopf(model, test_loader, loss_fn)
    print(f"Test Loss: {test_loss:.6f}")

    emissions = tracker.stop()
    print(f"Estimated CO2 emissions: {emissions:.6f} kg")

    # --- Plots ---
    plot_predictions(test_wk_true, test_wk_pred, title="W_k Prediction on Test Set")
    plot_vector_predictions(test_uj_true, test_uj_pred, label="u_j")
    plot_vector_predictions(test_zk_true, test_zk_pred, label="Z_k")

    plt.figure(figsize=(10, 6))
    plt.plot(train_losses, label='Train Loss')
    plt.plot(val_losses, label='Validation Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss (MSE)')
    plt.title(f'Training & Validation Loss ({os.path.basename(grid_file_path_train)})')
    plt.legend()
    plt.grid(True)
    plt.yscale('log')
    plt.tight_layout()
    plt.show()

    # --- Ground Truth + Prediction Error ---
    sample = all_data[0]
    visualize_grid_sample(sample, title="Voltage & Flow (Ground Truth)")

    model.eval()
    with torch.no_grad():
        sample = sample.to(device)
        # TODO: Replace with actual model prediction logic
        # need a model that returns node/edge predictions to support these:
        sample.y_node_pred = sample.y_node.clone()  # Replace with actual node prediction
        sample.y_edge_pred = sample.y_edge.clone()  # Replace with actual edge prediction

    visualize_grid_sample(sample, error_mode=True, title="Prediction Error on Grid")


# import torch
# import torch.nn.functional as F
# from matplotlib import cm
# from torch import nn
# from torch_geometric.nn import NNConv
# from torch_geometric.data import Data
# from torch_geometric.loader import DataLoader
# import numpy as np
# import matplotlib.pyplot as plt
# import matplotlib.colors as mcolors
# import networkx as nx
# from torch_geometric.utils import to_networkx
# from sklearn.preprocessing import StandardScaler
# import random
# import os
# import time
#
# from GridCalEngine import (FileOpen, PowerFlowOptions, SolverType, AcOpfMode, OptimalPowerFlowOptions,
#                            compile_numerical_circuit_at, FileSave)
# from GridCalEngine.Simulations.SCOPF_GNN.NumericalMethods.scopf import (run_nonlinear_MP_opf, LinearMultiContingencies,
#                                                                         run_nonlinear_SP_scopf)
#
# from codecarbon import EmissionsTracker
#
#
# # GPU/CPU configuration
# device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
# print(f"Using device: {device}")
#
# # First try with 5-bus and 14-bus grid
# grid_file_path_train = "/Users/CristinaFray/PycharmProjects/GridCal/src/trunk/scopf/case5.gridcal"
# # grid_file_path_train = "/Users/CristinaFray/PycharmProjects/GridCal/src/trunk/scopf/case14_cont_v12.gridcal"
#
# data_cache_train = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/Models/gnn_data_gce_ieee39.pt"
# model_save_path = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/Models/best_model_gce.pth"
# scalers_save_path = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/Models/scalers_gce.pt"
#
# data_cache_test_new = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/Models/powerflow_gnn_data_gce_ieee39_as_test.pt"
# results_plot_prefix = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/Results/"
#
# num_sample_from_ts = -1  # -1 means use all available
#
# # GNN Model
# f_node_in = 2  # Node features: P_inj_pu, Q_inj_pu
# f_edge_in = 4  # Edge features: R_pu, X_pu, B_pu, is_active (total line charging)
# f_node_out = 2  # Node outputs: Vm_pu, Va_rad
# f_edge_out = 4  # Edge outputs: Pf_pu, Pt_pu, Qf_pu, Qt_pu
# hidden_channels = 64
# num_layers = 4
#
#
# def visualize_grid_predictions(data, y_node_pred, y_edge_pred, error_mode=False, title='Grid GNN Prediction'):
#     import matplotlib.colors as mcolors
#     import matplotlib.cm as cm
#
#     G = to_networkx(data, to_undirected=True)
#
#     node_vals = y_node_pred.cpu().detach().numpy()
#     if error_mode:
#         node_vals = np.abs(node_vals - data.y_node.cpu().numpy())
#
#     # Edge values
#     if y_edge_pred is not None and data.edge_index.numel() > 0 and data.y_edge is not None:
#         edge_vals = y_edge_pred.cpu().detach().numpy()
#         if error_mode:
#             edge_vals = np.abs(edge_vals - data.y_edge.cpu().numpy())
#         edge_vals = np.linalg.norm(edge_vals[:, :2], axis=1)  # Pf and Pt magnitude
#     else:
#         edge_vals = None
#
#     pos = nx.spring_layout(G, seed=42)
#
#     plt.figure(figsize=(10, 8))
#
#     # Normalize node values for color
#     node_vals_flat = node_vals[:, 0]  # Vm prediction or error
#     node_norm = mcolors.Normalize(vmin=node_vals_flat.min(), vmax=node_vals_flat.max())
#     node_cmap = plt.get_cmap('viridis')
#     node_colors = node_cmap(node_norm(node_vals_flat))
#
#     # Draw nodes
#     nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=400)
#
#     # Draw node labels (numeric Vm or error)
#     # labels = {i: f"{v:.2f}" for i, v in enumerate(node_vals_flat)}
#     if hasattr(data, 'bus_names'):
#         labels = {i: f"{data.bus_names[i]}\n{node_vals_flat[i]:.2f}" for i in range(len(node_vals_flat))}
#     else:
#         labels = {i: f"{v:.2f}" for i, v in enumerate(node_vals_flat)}
#
#     nx.draw_networkx_labels(G, pos, labels=labels, font_color='black')
#
#     # Edges
#     if edge_vals is not None:
#         edge_norm = mcolors.Normalize(vmin=edge_vals.min(), vmax=edge_vals.max())
#         edge_cmap = plt.get_cmap('plasma')
#         edge_colors = edge_cmap(edge_norm(edge_vals))
#         nx.draw_networkx_edges(G, pos, edge_color=edge_colors, width=2)
#         sm = cm.ScalarMappable(norm=edge_norm, cmap=edge_cmap)
#     else:
#         nx.draw_networkx_edges(G, pos)
#         sm = cm.ScalarMappable(norm=node_norm, cmap=node_cmap)
#
#     ax = plt.gca()
#     cbar = plt.colorbar(sm, ax=ax, shrink=0.7)
#     cbar.set_label('Error' if error_mode else 'Prediction')
#
#     plt.title(title)
#     plt.axis('off')
#     plt.tight_layout()
#     plt.show()
#
#
# def mean_absolute_error(pred, true):
#     return torch.mean(torch.abs(pred - true)).item()
#
#
# def root_mean_squared_error(pred, true):
#     return torch.sqrt(F.mse_loss(pred, true)).item()
#
#
# def generate_scopf_data(grid_file_path):
#     print(f"Generating SCOPF N-1 Contingency training data from: {grid_file_path}")
#     if not os.path.exists(grid_file_path):
#         print(f"ERROR: File not found: {grid_file_path}")
#         return []
#
#     grid = FileOpen(grid_file_path).open()
#
#     for ll in range(len(grid.lines)):
#         grid.lines[ll].monitor_loading = True
#     for tt in range(len(grid.transformers2w)):
#         grid.transformers2w[tt].monitor_loading = True
#
#     pf_options = PowerFlowOptions(control_q=False)
#     opf_slack_options = OptimalPowerFlowOptions(
#         ips_method=SolverType.NR,
#         ips_tolerance=1e-6,
#         ips_iterations=50,
#         acopf_mode=AcOpfMode.ACOPFslacks,
#         verbose=0)
#
#     # Compile base circuit and contingencies
#     nc = compile_numerical_circuit_at(grid)
#
#     acopf_results = run_nonlinear_MP_opf(nc=nc, pf_options=pf_options,
#                                          opf_options=opf_slack_options, pf_init=False, load_shedding=False)
#
#     print()
#     print(f"--- Base case ---")
#     print(f"Base OPF loading {acopf_results.loading} .")
#     print(f"Voltage magnitudes: {acopf_results.Vm}")
#     print(f"Generators P: {acopf_results.Pg}")
#     print(f"Generators Q: {acopf_results.Qg}")
#     print(f"Error: {acopf_results.error}")
#
#     iteration_data = {
#         'max_wk': [],
#         'num_violations': [],
#         'max_voltage_slack': [],
#         'avg_voltage_slack': [],
#         'max_flow_slack': [],
#         'avg_flow_slack': [],
#         'total_cost': [],
#         'num_cuts': []
#     }
#
#     linear_multiple_contingencies = LinearMultiContingencies(grid, grid.get_contingency_groups())
#     contingency_groups = linear_multiple_contingencies.contingency_groups_used
#
#     data_scopf = []
#     prob_cont = 0
#     max_iter = 25
#     tolerance = 1e-5
#
#     n_con_groups = len(linear_multiple_contingencies.contingency_groups_used)
#     n_con_all = n_con_groups * 100
#     v_slacks = np.zeros(n_con_all)
#     f_slacks = np.zeros(n_con_all)
#     W_k_vec = np.zeros(n_con_all)
#     Z_k_vec = np.zeros((n_con_all, nc.generator_data.nelm))
#     u_j_vec = np.zeros((n_con_all, nc.generator_data.nelm))
#
#     for klm in range(max_iter):
#         print(f"General iteration {klm + 1} of {max_iter}")
#
#         viols = 0
#         W_k_local = np.zeros(n_con_groups)
#
#         br_lists = grid.get_branch_lists()
#         all_branches = [br for group in br_lists for br in group]
#
#         for ic, contingency_group in enumerate(linear_multiple_contingencies.contingency_groups_used):
#
#             contingencies = linear_multiple_contingencies.contingency_group_dict[contingency_group.idtag]
#             print(f"\nContingency group {ic}: {contingency_group.name}")
#
#             if contingencies is None:
#                 print(f"Contingencies have not been initialised.")
#                 break
#
#             nc.set_con_or_ra_status(contingencies)
#
#             # --- Deactivate affected branches ---
#             for cont in contingencies:
#                 try:
#                     br_idx = next(i for i, br in enumerate(all_branches) if br.name == cont.name)
#                     nc.passive_branch_data.active[br_idx] = False  # Deactivate the affected branch
#
#                     # Rebuild islands after modification
#                     islands = nc.split_into_islands()
#
#                     if len(islands) > 1:
#                         island_sizes = [island.nbus for island in islands]
#                         largest_island_idx = np.argmax(island_sizes)
#                         island = islands[largest_island_idx]
#                     else:
#                         island = islands[0]
#
#                     indices = island.get_simulation_indices()
#
#                     bus_names = list(island.bus_data.names)
#                     print(f"Bus names: {bus_names}")
#
#                     if len(indices.vd) > 0:
#                         print('Selected island with size:', island.nbus)
#
#                         slack_sol_cont = run_nonlinear_SP_scopf(
#                             nc=island,
#                             pf_options=pf_options,
#                             opf_options=opf_slack_options,
#                             pf_init=False,
#                             mp_results=acopf_results,
#                             load_shedding=False,
#                         )
#
#                         # Collect slacks
#                         v_slack = max(np.maximum(slack_sol_cont.sl_vmax, slack_sol_cont.sl_vmin))
#                         f_slack = max(np.maximum(slack_sol_cont.sl_sf, slack_sol_cont.sl_st))
#                         v_slacks[ic] = v_slack
#                         f_slacks[ic] = f_slack
#                         W_k_local[ic] = slack_sol_cont.W_k
#
#                         if slack_sol_cont.error > 1e-6:
#                             print(f"Error: {slack_sol_cont.error}")
#                         print(f"u_j: {slack_sol_cont.u_j}")
#
#                         if slack_sol_cont.W_k > tolerance:
#                             W_k_vec[prob_cont] = slack_sol_cont.W_k
#                             Z_k_vec[prob_cont, island.generator_data.original_idx] = slack_sol_cont.Z_k
#                             u_j_vec[prob_cont, island.generator_data.original_idx] = slack_sol_cont.u_j
#                             prob_cont += 1
#                             viols += 1
#
#                             # print('nbus', island.nbus, 'ngen', island.ngen)
#                             print(f"W_k: {slack_sol_cont.W_k}")
#                             print(f"Z_k: {slack_sol_cont.Z_k}")
#                             print(f"u_j: {slack_sol_cont.u_j}")
#                             print(f"Vmax slack: {slack_sol_cont.sl_vmax}")
#                             print(f"Vmin slack: {slack_sol_cont.sl_vmin}")
#                             print(f"Sf slack: {slack_sol_cont.sl_sf}")
#                             print(f"St slack: {slack_sol_cont.sl_st}")
#
#                             # --- Node features ---
#                             Pg = island.generator_data.p
#                             Qg = island.generator_data.qmin
#
#                             # Create node feature vectors: for all buses, not just generators
#                             P_node = np.zeros(island.nbus)
#                             Q_node = np.zeros(island.nbus)
#                             P_node[island.generator_data.bus_idx] = Pg
#                             Q_node[island.generator_data.bus_idx] = Qg
#
#                             x_node = torch.tensor(np.vstack([P_node, Q_node]).T, dtype=torch.float32)
#
#                             y_node = torch.tensor(np.vstack([slack_sol_cont.Vm, slack_sol_cont.Va]).T,
#                                                   dtype=torch.float32)
#
#                             R = island.passive_branch_data.R
#                             X = island.passive_branch_data.X
#                             B = island.passive_branch_data.B
#                             F = island.passive_branch_data.F
#                             T = island.passive_branch_data.T
#                             is_active = island.passive_branch_data.active.astype(np.float32)
#
#                             original_to_new = island.bus_data.get_original_to_island_bus_dict()
#
#                             filtered_edges = []
#                             filtered_attrs = []
#                             for i, (f, t) in enumerate(zip(F, T)):
#                                 f = int(f)
#                                 t = int(t)
#                                 if f in original_to_new and t in original_to_new:
#                                     filtered_edges.append((original_to_new[f], original_to_new[t]))
#                                     filtered_attrs.append([R[i], X[i], B[i], is_active[i]])
#
#                             if not filtered_edges:
#                                 print("No valid edges after remapping. Skipping sample.")
#                                 continue
#
#                             edge_index = torch.tensor(filtered_edges, dtype=torch.long).T
#                             edge_attr = torch.tensor(filtered_attrs, dtype=torch.float32)
#
#                             if edge_index.max() >= x_node.shape[0]:
#                                 print(
#                                     f"Skipping sample due to invalid edge_index (max={edge_index.max().item()}, nodes={x_node.shape[0]})")
#                                 continue
#
#                             y_edge = torch.zeros((len(filtered_edges), 4), dtype=torch.float32)
#
#                             data = Data(
#                                 x=x_node,
#                                 edge_index=edge_index,
#                                 edge_attr=edge_attr,
#                                 y_node=y_node,
#                                 y_edge=y_edge,
#                                 num_nodes=len(y_node)
#                             )
#
#                             data.bus_names = bus_names  # attach to data object
#                             print(f"Bus names: {bus_names}")
#
#                             data_scopf.append(data)
#                             print(f"Sample {len(data_scopf)} added.")
#
#                     else:
#                         print("No valid voltage-dependent nodes found in island. Skipping.")
#
#                     nc.passive_branch_data.active[br_idx] = True
#                 except StopIteration:
#                     print(f"Line with name '{cont.name}' not found in grid.lines. Skipping.")
#
#                 # Revert contingency
#             nc.set_con_or_ra_status(contingencies, revert=True)
#
#         if viols > 0:
#             # crop the dimension 0
#             W_k_vec_used = W_k_vec[:prob_cont]
#             Z_k_vec_used = Z_k_vec[:prob_cont, :]
#             u_j_vec_used = u_j_vec[:prob_cont, :]
#         else:  # assign small number
#             W_k_vec_used = np.zeros(1)
#             Z_k_vec_used = np.zeros((1, nc.generator_data.nelm))
#             u_j_vec_used = np.zeros((1, nc.generator_data.nelm))
#
#         # Store metrics for this iteration
#         if viols > 0:
#             iteration_data['max_wk'].append(W_k_local.max())
#             iteration_data['max_voltage_slack'].append(v_slacks.max())
#             iteration_data['avg_voltage_slack'].append(v_slacks.mean())
#             iteration_data['max_flow_slack'].append(f_slacks.max())
#             iteration_data['avg_flow_slack'].append(f_slacks.mean())
#         else:
#             iteration_data['max_wk'].append(1e-10)
#             iteration_data['max_voltage_slack'].append(1e-10)
#             iteration_data['avg_voltage_slack'].append(1e-10)
#             iteration_data['max_flow_slack'].append(1e-10)
#             iteration_data['avg_flow_slack'].append(1e-10)
#             print('Master problem solution found')
#
#         iteration_data['num_violations'].append(viols)
#
#         # Run the MP with information from the SPs
#         print('')
#         print("--- Feeding SPs info to MP ---")
#         acopf_results = run_nonlinear_MP_opf(nc=nc,
#                                              pf_options=pf_options,
#                                              opf_options=opf_slack_options,
#                                              pf_init=False,
#                                              W_k_vec=W_k_vec_used,
#                                              Z_k_vec=Z_k_vec_used,
#                                              u_j_vec=u_j_vec_used,
#                                              load_shedding=False)
#
#         total_cost = np.sum(acopf_results.Pcost)
#         iteration_data['total_cost'].append(total_cost)
#
#         # Print current iteration metrics
#         print(f"Maximum W_k: {iteration_data['max_wk'][-1]}")
#         print(f"Number of violations: {iteration_data['num_violations'][-1]}")
#         print(f"Maximum voltage slack: {iteration_data['max_voltage_slack'][-1]}")
#         print(f"Average voltage slack: {iteration_data['avg_voltage_slack'][-1]}")
#         print(f"Maximum flow slack: {iteration_data['max_flow_slack'][-1]}")
#         print(f"Average flow slack: {iteration_data['avg_flow_slack'][-1]}")
#         print(f"Total generation cost: {total_cost}")
#
#         if viols == 0:
#             break
#         iteration_data['num_cuts'].append(prob_cont)
#         print(f"Total number of cuts: {iteration_data['num_cuts'][-1]}")
#         print('-')
#         print('Length W_k_vec', len(W_k_vec))
#         print('Length Z_k_vec', len(Z_k_vec))
#         print('Length u_j_vec', len(u_j_vec))
#
#     print(f"\nDone. Total training samples generated: {len(data_scopf)}")
#     return data_scopf
#
#
# ### TO DO ###
# # Modify training targets and model output for SCOPF:
# # - Instead of predicting node-level Vm, Va and edge-level flows
# # - Predict: W_k (scalar), u_j (1D vector), Z_k (1D vector)
#
# # Changes needed:
# # 1. Change data object to store y_target = {'wk': float, 'uj': tensor, 'zk': tensor}
# # 2. Update model architecture to predict global outputs (using global pooling)
# # 3. Update loss functions to compare W_k, u_j, Z_k
#
# # Basic sketch of model changes
#
# from torch_geometric.nn import global_mean_pool
#
# class SCOPFGNN(torch.nn.Module):
#     def __init__(self, node_in_feat, edge_in_feat, hidden_feat, num_generators, num_layers=3):
#         super().__init__()
#         self.node_embed = torch.nn.Sequential(
#             torch.nn.Linear(node_in_feat, hidden_feat),
#             torch.nn.ReLU(),
#             torch.nn.BatchNorm1d(hidden_feat)
#         )
#
#         self.convs = torch.nn.ModuleList()
#         for _ in range(num_layers):
#             mlp = torch.nn.Sequential(
#                 torch.nn.Linear(edge_in_feat, hidden_feat * 2),
#                 torch.nn.ReLU(),
#                 torch.nn.Linear(hidden_feat * 2, hidden_feat * hidden_feat)
#             )
#             self.convs.append(NNConv(hidden_feat, hidden_feat, mlp, aggr='mean'))
#
#         # Global prediction heads
#         self.fc_wk = torch.nn.Sequential(
#             torch.nn.Linear(hidden_feat, hidden_feat),
#             torch.nn.ReLU(),
#             torch.nn.Linear(hidden_feat, 1)
#         )
#         self.fc_uj = torch.nn.Sequential(
#             torch.nn.Linear(hidden_feat, hidden_feat),
#             torch.nn.ReLU(),
#             torch.nn.Linear(hidden_feat, num_generators)
#         )
#         self.fc_zk = torch.nn.Sequential(
#             torch.nn.Linear(hidden_feat, hidden_feat),
#             torch.nn.ReLU(),
#             torch.nn.Linear(hidden_feat, num_generators)
#         )
#
#     def forward(self, data):
#         x, edge_index, edge_attr, batch = data.x, data.edge_index, data.edge_attr, data.batch
#         h = self.node_embed(x)
#         for conv in self.convs:
#             h = F.relu(conv(h, edge_index, edge_attr))
#
#         hg = global_mean_pool(h, batch)  # Graph-level representation
#
#         wk_pred = self.fc_wk(hg).squeeze(-1)  # [batch_size]
#         uj_pred = self.fc_uj(hg)             # [batch_size, num_gens]
#         zk_pred = self.fc_zk(hg)             # [batch_size, num_gens]
#
#         return wk_pred, uj_pred, zk_pred
#
#
# class PowerSystemGNN(torch.nn.Module):
#     def __init__(self, node_in_feat, edge_in_feat, hidden_feat, node_out_feat, edge_out_feat, num_layers=3):
#         super().__init__()
#         # self.node_embed = torch.nn.Linear(node_in_feat, hidden_feat)
#         #
#         # self.convs = torch.nn.ModuleList()
#         # current_node_feat_dim = hidden_feat
#         # for _ in range(num_layers):
#         #     mlp_for_nnconv = torch.nn.Sequential(
#         #         torch.nn.Linear(edge_in_feat, hidden_feat * 2),
#         #         torch.nn.ReLU(),
#         #         torch.nn.Linear(hidden_feat * 2, current_node_feat_dim * hidden_feat)
#         #     )
#         #     self.convs.append(NNConv(current_node_feat_dim, hidden_feat, mlp_for_nnconv, aggr='mean'))
#         #     current_node_feat_dim = hidden_feat
#         #
#         # self.node_decoder = torch.nn.Linear(hidden_feat, node_out_feat)
#         #
#         # edge_decoder_mlp_in_dim = 2 * hidden_feat + edge_in_feat
#         # self.edge_decoder = torch.nn.Sequential(
#         #     torch.nn.Linear(edge_decoder_mlp_in_dim, hidden_feat * 2),  # Increased capacity slightly
#         #     torch.nn.ReLU(),
#         #     torch.nn.Linear(hidden_feat * 2, edge_out_feat)
#         # )
#
#         self.node_embed = torch.nn.Sequential(
#             torch.nn.Linear(node_in_feat, hidden_feat),
#             torch.nn.ReLU(),
#             torch.nn.BatchNorm1d(hidden_feat)
#         )
#
#         self.convs = torch.nn.ModuleList()
#         for _ in range(num_layers):
#             # mlp_for_nnconv = torch.nn.Sequential(
#             #     torch.nn.Linear(edge_in_feat, hidden_feat),
#             #     torch.nn.ReLU(),
#             #     torch.nn.Linear(hidden_feat, hidden_feat * hidden_feat)
#             # )
#             mlp_for_nnconv = torch.nn.Sequential(
#                 torch.nn.Linear(edge_in_feat, hidden_feat * 2),
#                 torch.nn.ReLU(),
#                 torch.nn.Linear(hidden_feat * 2, hidden_feat * hidden_feat)
#             )
#
#             self.convs.append(NNConv(hidden_feat, hidden_feat, mlp_for_nnconv, aggr='mean'))
#
#         self.node_decoder = torch.nn.Sequential(
#             torch.nn.Linear(hidden_feat, hidden_feat),
#             torch.nn.ReLU(),
#             torch.nn.Linear(hidden_feat, node_out_feat)
#         )
#
#         self.edge_decoder = torch.nn.Sequential(
#             torch.nn.Linear(2 * hidden_feat + edge_in_feat, hidden_feat),
#             torch.nn.ReLU(),
#             torch.nn.Linear(hidden_feat, edge_out_feat)
#         )
#
#     def forward(self, data):
#         x, edge_index, edge_attr = data.x, data.edge_index, data.edge_attr
#         # h_node = F.relu(self.node_embed(x))
#         h_node = self.node_embed(x)
#
#         for conv_layer in self.convs:
#             h_node = F.relu(conv_layer(h_node, edge_index, edge_attr))
#
#         y_node_pred = self.node_decoder(h_node)
#
#         row, col = edge_index
#         if h_node[row].shape[0] == 0 or h_node[col].shape[0] == 0:  # Handles cases with no edges in a batch item
#             # Create an empty tensor with the correct number of output features for edges
#             y_edge_pred = torch.empty((0, self.edge_decoder[-1].out_features), device=x.device, dtype=x.dtype)
#         else:
#             h_source, h_target = h_node[row], h_node[col]
#             edge_decoder_input = torch.cat([h_source, h_target, edge_attr], dim=-1)
#             y_edge_pred = self.edge_decoder(edge_decoder_input)
#
#         return y_node_pred, y_edge_pred
#
#
# # Training Parameters
# train_set = 0.9
# val_set = 0.05
# batch_size = 16
#
# # Testing Parameters
# test_set = 0.05
# epochs = 50
# lr = 1e-3
#
# # Generate data
# # data_list = generate_scopf_data(grid_file_path_train)
# # print(data_list)
#
# # Training and eval fns
# def train_epoch(model, loader, optimizer, criterion_node, criterion_edge):
#     model.train()
#     total_loss = 0
#     for data in loader:
#         data = data.to(device)
#         optimizer.zero_grad()
#         y_node_pred, y_edge_pred = model(data)
#
#         loss_node = criterion_node(y_node_pred, data.y_node)
#
#         # Handle cases where a graph in the batch might have no edges
#         if data.edge_index.numel() == 0 or y_edge_pred.shape[0] == 0:
#             loss_edge = torch.tensor(0.0, device=device, requires_grad=False)  # No edges, no edge loss
#             if data.y_edge.numel() > 0:  # Should not happen if y_edge_pred is empty
#                 print("Warning: y_edge_pred is empty but data.y_edge is not. This indicates an issue.")
#         else:
#             loss_edge = criterion_edge(y_edge_pred, data.y_edge)
#
#         loss = loss_node + loss_edge
#         loss.backward()
#         torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)  # Gradient clipping
#         optimizer.step()
#         total_loss += loss.item() * data.num_graphs  # num_graphs in batch
#     return total_loss / len(loader.dataset)
#
# @torch.no_grad()
# def evaluate_epoch(model, loader, criterion_node, criterion_edge, scalers, set_name="Test"):
#     model.eval()
#     total_loss = 0
#     all_y_node_true_unscaled_vm, all_y_node_pred_unscaled_vm = [], []
#     all_y_edge_true_unscaled_pf, all_y_edge_pred_unscaled_pf = [], []
#     all_y_edge_true_unscaled_pt, all_y_edge_pred_unscaled_pt = [], []
#
#     for data in loader:
#         data = data.to(device)
#         y_node_pred, y_edge_pred = model(data)
#         loss_node = criterion_node(y_node_pred, data.y_node)
#
#         if data.edge_index.numel() == 0 or y_edge_pred.shape[0] == 0 or data.y_edge.shape[0] == 0:
#             loss_edge = torch.tensor(0.0, device=device)
#         else:
#             loss_edge = criterion_edge(y_edge_pred, data.y_edge)
#
#         loss = loss_node + loss_edge
#         total_loss += loss.item() * data.num_graphs
#
#         assert y_node_pred.shape == data.y_node.shape
#         assert y_edge_pred.shape == data.y_edge.shape
#
#         # Unscale node predictions for Vm
#         if y_node_pred.shape[0] > 0:  # Ensure there's data
#             y_node_pred_cpu = y_node_pred.cpu().numpy()
#             y_node_true_cpu = data.y_node.cpu().numpy()
#             if scalers and 'y_node' in scalers:
#                 y_node_pred_unscaled = scalers['y_node'].inverse_transform(y_node_pred_cpu)
#                 y_node_true_unscaled = scalers['y_node'].inverse_transform(y_node_true_cpu)
#                 all_y_node_pred_unscaled_vm.append(torch.from_numpy(y_node_pred_unscaled[:, 0]))
#                 all_y_node_true_unscaled_vm.append(torch.from_numpy(y_node_true_unscaled[:, 0]))
#             else:  # No scaler
#                 all_y_node_pred_unscaled_vm.append(y_node_pred.cpu()[:, 0])
#                 all_y_node_true_unscaled_vm.append(data.y_node.cpu()[:, 0])
#
#         # Unscale edge predictions for Pf and Pt
#         if y_edge_pred.shape[0] > 0 and data.y_edge.shape[0] > 0:  # Ensure there's edge data
#             y_edge_pred_cpu = y_edge_pred.cpu().numpy()
#             y_edge_true_cpu = data.y_edge.cpu().numpy()
#
#             if scalers and 'y_edge' in scalers:
#                 y_edge_pred_unscaled = scalers['y_edge'].inverse_transform(y_edge_pred_cpu)
#                 y_edge_true_unscaled = scalers['y_edge'].inverse_transform(y_edge_true_cpu)
#             else:  # No scaler
#                 y_edge_pred_unscaled = y_edge_pred_cpu
#                 y_edge_true_unscaled = y_edge_true_cpu
#
#             # Pf is at index 0, Pt is at index 1 of y_edge
#             all_y_edge_pred_unscaled_pf.append(torch.from_numpy(y_edge_pred_unscaled[:, 0]))
#             all_y_edge_true_unscaled_pf.append(torch.from_numpy(y_edge_true_unscaled[:, 0]))
#             all_y_edge_pred_unscaled_pt.append(torch.from_numpy(y_edge_pred_unscaled[:, 1]))
#             all_y_edge_true_unscaled_pt.append(torch.from_numpy(y_edge_true_unscaled[:, 1]))
#
#     avg_loss = total_loss / len(loader.dataset) if len(loader.dataset) > 0 else 0
#
#     if all_y_node_true_unscaled_vm:
#         all_y_node_true_unscaled_vm = torch.cat(all_y_node_true_unscaled_vm)
#         all_y_node_pred_unscaled_vm = torch.cat(all_y_node_pred_unscaled_vm)
#
#     if all_y_edge_true_unscaled_pf:
#         all_y_edge_true_unscaled_pf = torch.cat(all_y_edge_true_unscaled_pf)
#         all_y_edge_pred_unscaled_pf = torch.cat(all_y_edge_pred_unscaled_pf)
#         all_y_edge_true_unscaled_pt = torch.cat(all_y_edge_true_unscaled_pt)
#         all_y_edge_pred_unscaled_pt = torch.cat(all_y_edge_pred_unscaled_pt)
#
#     if all_y_node_true_unscaled_vm.numel() > 0:
#         mae_vm = mean_absolute_error(all_y_node_pred_unscaled_vm, all_y_node_true_unscaled_vm)
#         rmse_vm = root_mean_squared_error(all_y_node_pred_unscaled_vm, all_y_node_true_unscaled_vm)
#         print(f"[Vm] MAE: {mae_vm:.4f}, RMSE: {rmse_vm:.4f}")
#
#     if all_y_edge_true_unscaled_pf.numel() > 0:
#         mae_pf = mean_absolute_error(all_y_edge_pred_unscaled_pf, all_y_edge_true_unscaled_pf)
#         rmse_pf = root_mean_squared_error(all_y_edge_pred_unscaled_pf, all_y_edge_true_unscaled_pf)
#         print(f"[Pf] MAE: {mae_pf:.4f}, RMSE: {rmse_pf:.4f}")
#
#     if all_y_edge_true_unscaled_pt.numel() > 0:
#         mae_pt = mean_absolute_error(all_y_edge_pred_unscaled_pt, all_y_edge_true_unscaled_pt)
#         rmse_pt = root_mean_squared_error(all_y_edge_pred_unscaled_pt, all_y_edge_true_unscaled_pt)
#         print(f"[Pt] MAE: {mae_pt:.4f}, RMSE: {rmse_pt:.4f}")
#
#     return (avg_loss,
#             all_y_node_true_unscaled_vm, all_y_node_pred_unscaled_vm,
#             all_y_edge_true_unscaled_pf, all_y_edge_pred_unscaled_pf,
#             all_y_edge_true_unscaled_pt, all_y_edge_pred_unscaled_pt)
#
# def train_scopf(model, loader, optimizer, loss_fn):
#     model.train()
#     total_loss = 0
#     for data in loader:
#         data = data.to(model.device)
#         optimizer.zero_grad()
#         wk_pred, uj_pred, zk_pred = model(data)
#         loss = (
#             loss_fn(wk_pred, data.wk) +
#             loss_fn(uj_pred, data.uj) +
#             loss_fn(zk_pred, data.zk)
#         )
#         loss.backward()
#         optimizer.step()
#         total_loss += loss.item() * data.num_graphs
#     return total_loss / len(loader.dataset)
#
# def evaluate_scopf(model, loader, loss_fn):
#     model.eval()
#     total_loss = 0
#     all_wk_true, all_wk_pred = [], []
#     with torch.no_grad():
#         for data in loader:
#             data = data.to(model.device)
#             wk_pred, uj_pred, zk_pred = model(data)
#             loss = (
#                 loss_fn(wk_pred, data.wk) +
#                 loss_fn(uj_pred, data.uj) +
#                 loss_fn(zk_pred, data.zk)
#             )
#             total_loss += loss.item() * data.num_graphs
#             all_wk_true.append(data.wk)
#             all_wk_pred.append(wk_pred)
#
#     return total_loss / len(loader.dataset), torch.cat(all_wk_true), torch.cat(all_wk_pred)
#
# def generate_augmented_scopf_data(grid_file_path, num_variants=10, variation_scale=0.1):
#     all_augmented_data = []
#
#     # Target directory to save variants
#     variant_dir = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/GridVariants"
#     os.makedirs(variant_dir, exist_ok=True)
#
#     for i in range(num_variants):
#         print(f"\nGenerating variant {i + 1} of {num_variants}")
#
#         # Load grid
#         grid = FileOpen(grid_file_path).open()
#
#         for line in grid.lines:
#             line.R *= (1.0 + np.random.uniform(-variation_scale, variation_scale))
#             line.X *= (1.0 + np.random.uniform(-variation_scale, variation_scale))
#             line.B *= (1.0 + np.random.uniform(-variation_scale, variation_scale))
#
#         for tf in grid.transformers2w:
#             tf.R *= (1.0 + np.random.uniform(-variation_scale, variation_scale))
#             tf.X *= (1.0 + np.random.uniform(-variation_scale, variation_scale))
#             tf.B *= (1.0 + np.random.uniform(-variation_scale, variation_scale))
#
#         for gen in grid.generators:
#             gen.P *= (1.0 + np.random.uniform(-variation_scale, variation_scale))
#             # gen.Q *= (1.0 + np.random.uniform(-variation_scale, variation_scale))
#
#         variant_filename = os.path.join(variant_dir, f"variant_{i + 1}.gridcal")
#         FileSave(grid, variant_filename).save()
#         print(f"Saved variant to: {variant_filename}")
#
#         # Generate SCOPF data from this variant
#         variant_data = generate_scopf_data(variant_filename)
#         all_augmented_data.extend(variant_data)
#
#     print(f"\nTotal augmented training samples: {len(all_augmented_data)}")
#     return all_augmented_data
#
#
# if __name__ == '__main__':
#
#     train_set = 0.9
#     val_set = 0.05
#     batch_size = 16
#
#     # Testing Parameters
#     test_set = 0.05
#     epochs = 50
#     lr = 1e-3
#
#     all_data = generate_augmented_scopf_data(
#                 grid_file_path=grid_file_path_train,
#                 num_variants=20,  # More variants = more data
#                 variation_scale=0.1  # ±10% noise
#             )
#
#     num_total = len(all_data)
#     random.Random(42).shuffle(all_data)
#     num_train = int(train_set * num_total)
#     num_val = int(val_set * num_total)
#
#     train_data = all_data[:num_train]
#     val_data = all_data[num_train: num_train + num_val]
#     test_data = all_data[num_train + num_val:]
#
#     train_loader = DataLoader(train_data, batch_size=32, shuffle=True)
#     val_loader = DataLoader(val_data, batch_size=32)
#
#     model = SCOPFGNN(node_in_feat=2, edge_in_feat=4, hidden_feat=32, num_generators=5).to(device)
#     model.device = device
#     optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
#     loss_fn = nn.MSELoss()
#
#     for epoch in range(1, 101):
#         train_loss = train_scopf(model, train_loader, optimizer, loss_fn)
#         val_loss, _, _ = evaluate_scopf(model, val_loader, loss_fn)
#         print(f"Epoch {epoch:03d}: Train Loss = {train_loss:.6f}, Val Loss = {val_loss:.6f}")
#
#
# # if __name__ == '__main__':
# #     tracker = EmissionsTracker(
# #         project_name="SCOPF_GNN_Training",
# #         output_dir="/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/CO2",  # You can change this path
# #     )
# #     tracker.start()
# #
# #     start_time = time.time()
# #
# #     grid_file_to_process = grid_file_path_train
# #     data_cache_file = data_cache_train
# #     plot_suffix = "_train_grid"
# #
# #     # 1. Generate or Load Data for the current mode
# #     # all_data = []
# #     # if os.path.exists(data_cache_file):
# #     #     print(f"Loading pre-generated data from {data_cache_file}...")
# #     #     try:
# #     #         loaded_content = torch.load(data_cache_file, weights_only=False)  # Set weights_only based on content
# #     #         all_data = loaded_content['data']
# #     #     except Exception as e:
# #     #         print(f"Could not load data from {data_cache_file}: {e}. Regenerating...")
# #     #         all_data = []  # Ensure it's empty to trigger regeneration
# #     #
# #     # if not all_data:  # If cache file didn't exist or failed to load
# #     #     print(f"Generating new data for {grid_file_to_process}...")
# #     #     all_data = generate_scopf_data(grid_file_to_process)
# #     #     if all_data:
# #     #         os.makedirs(os.path.dirname(data_cache_file), exist_ok=True)
# #     #         torch.save({'data': all_data}, data_cache_file)
# #     #         print(f"Saved generated data to {data_cache_file}")
# #     #     else:
# #     #         print(f"ERROR: No data generated from {grid_file_to_process}. Exiting.")
# #     #         exit()
# #
# #     # 1. Always generate new data (ignore cache)
# #     print(f"Generating new data for {grid_file_to_process}...")
# #     # all_data = generate_scopf_data(grid_file_to_process)
# #     all_data = generate_augmented_scopf_data(
# #         grid_file_path=grid_file_to_process,
# #         num_variants=20,  # More variants = more data
# #         variation_scale=0.1  # ±10% noise
# #     )
# #
# #     if not all_data:
# #         raise RuntimeError("No SCOPF data generated. Check your grid file or contingency definition.")
# #     print(f"Generated {all_data} data samples.")
# #
# #     # Optionally save it for future reuse
# #     os.makedirs(os.path.dirname(data_cache_file), exist_ok=True)
# #     torch.save({'data': all_data}, data_cache_file)
# #     print(f"Saved generated data to {data_cache_file}")
# #
# #     num_total = len(all_data)
# #     if num_total < 5:  # Increased minimum slightly
# #         print(f"Error: Very few data samples loaded/generated ({num_total}). Cannot proceed.")
# #         exit()
# #
# #     scalers = {}  # Initialize scalers dictionary
# #
# #     # 2. Train/Val/Test Split (only for training mode)
# #     random.Random(42).shuffle(all_data)
# #     num_train = int(train_set * num_total)
# #     num_val = int(val_set * num_total)
# #
# #     train_data = all_data[:num_train]
# #     val_data = all_data[num_train: num_train + num_val]
# #     test_data = all_data[num_train + num_val:]
# #
# #     print(f"Dataset split: Train={len(train_data)}, Val={len(val_data)}, Test={len(test_data)}")
# #     if not train_data or not val_data or not test_data:
# #         print("Error: One or more data splits are empty for training. Check NUM_SAMPLES and ratios.")
# #         exit()
# #
# #     # 3. Normalization (Fit scalers on train_data, then transform all splits)
# #     for key in ['x', 'edge_attr', 'y_node', 'y_edge']:
# #         features_to_scale = []
# #         for data_sample in train_data:  # Fit only on training data
# #             sample_feature = getattr(data_sample, key)
# #             if sample_feature is not None and sample_feature.numel() > 0:
# #                 features_to_scale.append(sample_feature)
# #
# #         if features_to_scale:
# #             all_train_features = torch.cat(features_to_scale, dim=0).numpy()
# #             if all_train_features.shape[0] > 0:
# #                 scalers[key] = StandardScaler().fit(all_train_features)
# #             else:
# #                 print(f"Warning: No data to fit scaler for '{key}' in training mode.")
# #         else:
# #             print(f"Warning: No features collected for scaling for key '{key}' in training mode.")
# #
# #     # Save the fitted scalers
# #     os.makedirs(os.path.dirname(scalers_save_path), exist_ok=True)
# #     torch.save(scalers, scalers_save_path)
# #     print(f"Saved fitted scalers to {scalers_save_path}")
# #
# #     # Apply scalers to all splits
# #     for dataset_part in [train_data, val_data, test_data]:
# #         for i in range(len(dataset_part)):
# #             for key_s in scalers.keys():  # Use keys from fitted scalers
# #                 original_tensor = getattr(dataset_part[i], key_s)
# #                 if original_tensor is not None and original_tensor.numel() > 0:
# #                     scaled_array = scalers[key_s].transform(original_tensor.numpy())
# #                     setattr(dataset_part[i], key_s, torch.from_numpy(scaled_array).float())
# #
# #     train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=True,
# #                               drop_last=True if len(train_data) > batch_size else False)
# #     val_loader = DataLoader(val_data, batch_size=batch_size, shuffle=False)
# #     test_loader = DataLoader(test_data, batch_size=batch_size, shuffle=False)  # Test loader for the training grid
# #
# #     # 4. Initialize Model
# #     model = PowerSystemGNN(
# #         node_in_feat=f_node_in, edge_in_feat=f_edge_in,
# #         hidden_feat=hidden_channels, node_out_feat=f_node_out,
# #         edge_out_feat=f_edge_out, num_layers=num_layers
# #     ).to(device)
# #
# #     criterion_node = torch.nn.MSELoss()  # Needed for evaluation in both modes
# #     criterion_edge = torch.nn.MSELoss()  # Needed for evaluation in both modes
# #
# #     optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
# #
# #     # 5. Training Loop
# #     train_losses, val_losses = [], []
# #     print(f"\nStarting training for {epochs} epochs...")
# #     best_val_loss = float('inf')
# #
# #     for epoch in range(1, epochs + 1):
# #         epoch_start_time = time.time()
# #         train_loss = train_epoch(model, train_loader, optimizer, criterion_node, criterion_edge)
# #         val_loss_eval_results = evaluate_epoch(model, val_loader, criterion_node, criterion_edge, scalers,
# #                                                "Validation")
# #         val_loss = val_loss_eval_results[0]  # First element is avg_loss
# #
# #         train_losses.append(train_loss)
# #         val_losses.append(val_loss)
# #
# #         epoch_duration = time.time() - epoch_start_time
# #         if epoch % 10 == 0 or epoch == epochs:
# #             print(
# #                 f'Epoch: {epoch:03d}, Train Loss: {train_loss:.6f}, Val Loss: {val_loss:.6f}, Time: {epoch_duration:.2f}s')
# #
# #         if best_val_loss > val_loss > 0:
# #             best_val_loss = val_loss
# #             os.makedirs(os.path.dirname(model_save_path), exist_ok=True)
# #             torch.save(model.state_dict(), model_save_path)
# #             print(f"Saved new best model to {model_save_path} with Val Loss: {best_val_loss:.6f}")
# #
# #     print(f"Training finished. Best Val Loss: {best_val_loss:.6f}")
# #     print(f"Model saved to {model_save_path}")
# #     print(f"Scalers saved to {scalers_save_path}")
# #
# #     # Load the best model for final evaluation on the training grid's test set
# #     print(f"Loading best model from {model_save_path} for final evaluation on training grid's test set.")
# #     model.load_state_dict(torch.load(model_save_path, map_location=device))
# #
# #     # 6. Final Evaluation (on test_data of the respective grid)
# #     print(f"Evaluating on Test Set of {grid_file_to_process}...")
# #     eval_results = evaluate_epoch(
# #         model, test_loader, criterion_node, criterion_edge, scalers, "Test"
# #     )
# #     test_loss = eval_results[0]
# #     test_y_node_true_vm, test_y_node_pred_vm = eval_results[1], eval_results[2]
# #     test_y_edge_true_pf, test_y_edge_pred_pf = eval_results[3], eval_results[4]
# #     test_y_edge_true_pt, test_y_edge_pred_pt = eval_results[5], eval_results[6]
# #
# #     print(f"Final Test Loss on {grid_file_to_process}: {test_loss:.6f}")
# #
# #     # Stop tracking and print the result
# #     emissions = tracker.stop()
# #     print(f"Estimated CO2 emissions: {emissions:.6f} kg")
# #
# #     model.eval()
# #     for test_batch in test_loader:
# #         test_batch = test_batch.to(device)
# #         y_node_pred, y_edge_pred = model(test_batch)
# #
# #         # Convert batch back into individual graphs
# #         data_list = test_batch.to_data_list()
# #
# #         node_offset = 0
# #         edge_offset = 0
# #         for data in data_list:
# #             num_nodes = data.num_nodes
# #             num_edges = data.edge_index.size(1)
# #
# #             visualize_grid_predictions(
# #                 data,
# #                 y_node_pred[node_offset:node_offset + num_nodes],
# #                 y_edge_pred[edge_offset:edge_offset + num_edges],
# #                 error_mode=False,
# #                 title="GNN Predictions"
# #             )
# #             # visualize_grid_predictions(data, y_node_pred, y_edge_pred, error_mode=True)
# #
# #             node_offset += num_nodes
# #             edge_offset += num_edges
# #
# #             break  # just show one sample
# #
# #
# #     # Pick the first graph from the batch
# #     #     data = test_batch.to_data_list()[0]
# #     #     y_node = y_node_pred[:data.num_nodes]
# #     #     y_edge = y_edge_pred[:data.edge_index.shape[1]]
# #     #
# #     #     visualize_grid_predictions(
# #     #         data,
# #     #         y_node_pred=y_node,
# #     #         y_edge_pred=y_edge,
# #     #         error_mode=False,
# #     #         title="GNN Prediction for a Single Test Contingency"
# #     #     )
# #     #     break  # Show one graph only
# #
# #     # 7. Plotting Results
# #     # Ensure the results directory exists
# #     os.makedirs(results_plot_prefix, exist_ok=True)
# #
# #     # Plot 1: Training and Validation Loss (only in train mode)
# #     plt.figure(figsize=(10, 6))
# #     plt.plot(train_losses, label='Train Loss')
# #     plt.plot(val_losses, label='Validation Loss')
# #     plt.xlabel('Epoch')
# #     plt.ylabel('Loss (MSE)')
# #     plt.title(f'Training & Validation Loss ({os.path.basename(grid_file_to_process)})')
# #     plt.legend()
# #     plt.grid(True)
# #     plt.yscale('log')
# #     plt.tight_layout()
# #     loss_plot_filename = f"{results_plot_prefix}gnn_loss_plot{plot_suffix}.png"
# #     plt.savefig(loss_plot_filename)
# #     print(f"Saved loss plot to {loss_plot_filename}")
# #     plt.close()  # Close the figure
# #
# #     # Plot 2: Vm Scatter Plot (Predicted vs. True)
# #     if (test_y_node_true_vm is not None and len(test_y_node_true_vm) > 0 and
# #             test_y_node_pred_vm is not None and len(test_y_node_pred_vm) > 0):
# #         true_vms_np = test_y_node_true_vm.cpu().numpy()
# #         pred_vms_np = test_y_node_pred_vm.cpu().numpy()
# #         valid_indices = np.isfinite(true_vms_np) & np.isfinite(pred_vms_np)
# #         true_vms_np = true_vms_np[valid_indices]
# #         pred_vms_np = pred_vms_np[valid_indices]
# #
# #         plt.hist(pred_vms_np, bins=20, alpha=0.7, label='Predicted Vm')
# #         plt.hist(true_vms_np, bins=20, alpha=0.7, label='True Vm')
# #         plt.xlabel("Voltage Magnitude (pu)")
# #         plt.ylabel("Frequency")
# #         plt.title("Distribution of Vm Predictions vs True Values")
# #         plt.legend()
# #         plt.grid(True)
# #         plt.tight_layout()
# #         plt.show()
# #
# #         if len(true_vms_np) > 0:
# #             plt.figure(figsize=(8, 7))
# #             min_val = min(true_vms_np.min(), pred_vms_np.min()) * 0.99
# #             max_val = max(true_vms_np.max(), pred_vms_np.max()) * 1.01
# #             plt.scatter(true_vms_np, pred_vms_np, alpha=0.5, s=10, label='Predictions')
# #             plt.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=1.5, label='Ideal (y=x)')
# #             plt.xlabel('True Vm (pu)')
# #             plt.ylabel('Predicted Vm (pu)')
# #             plt.title(
# #                 f'Vm: Predicted vs. True ({os.path.basename(grid_file_to_process)} Test - {len(true_vms_np)} points)')
# #             plt.xlim(min_val, max_val)
# #             plt.ylim(min_val, max_val)
# #             plt.legend()
# #             plt.grid(True)
# #             plt.gca().set_aspect('equal', adjustable='box')
# #             plt.tight_layout()
# #             # vm_scatter_filename = f"{results_plot_prefix}gnn_vm_scatter{plot_suffix}.png"
# #             # plt.savefig(vm_scatter_filename)
# #             # print(f"Saved Vm scatter plot to {vm_scatter_filename}")
# #             # plt.close()
# #             plt.show()
# #         else:
# #             print("No valid Vm data for scatter plot after filtering.")
# #     else:
# #         print("Vm data not available for scatter plot.")
# #
# #     # Plot 3: Pf Scatter Plot (Predicted vs. True)
# #     if (test_y_edge_true_pf is not None and len(test_y_edge_true_pf) > 0 and
# #             test_y_edge_pred_pf is not None and len(test_y_edge_pred_pf) > 0):
# #         true_pf_np = test_y_edge_true_pf.cpu().numpy()
# #         pred_pf_np = test_y_edge_pred_pf.cpu().numpy()
# #         valid_indices_pf = np.isfinite(true_pf_np) & np.isfinite(pred_pf_np)
# #         true_pf_np = true_pf_np[valid_indices_pf]
# #         pred_pf_np = pred_pf_np[valid_indices_pf]
# #
# #         if len(true_pf_np) > 0:
# #             plt.figure(figsize=(8, 7))
# #             min_val_pf = min(true_pf_np.min(), pred_pf_np.min()) * 0.99
# #             max_val_pf = max(true_pf_np.max(), pred_pf_np.max()) * 1.01
# #             plt.scatter(true_pf_np, pred_pf_np, alpha=0.5, s=10, label='Pf Predictions')
# #             plt.plot([min_val_pf, max_val_pf], [min_val_pf, max_val_pf], 'r--', linewidth=1.5, label='Ideal (y=x)')
# #             plt.xlabel('True Pf (pu)')
# #             plt.ylabel('Predicted Pf (pu)')
# #             plt.title(
# #                 f'Pf: Predicted vs. True ({os.path.basename(grid_file_to_process)} Test - {len(true_pf_np)} points)')
# #             plt.xlim(min_val_pf, max_val_pf)
# #             plt.ylim(min_val_pf, max_val_pf)
# #             plt.legend()
# #             plt.grid(True)
# #             plt.gca().set_aspect('equal', adjustable='box')
# #             plt.tight_layout()
# #             # pf_scatter_filename = f"{results_plot_prefix}gnn_pf_scatter{plot_suffix}.png"
# #             # plt.savefig(pf_scatter_filename)
# #             # print(f"Saved Pf scatter plot to {pf_scatter_filename}")
# #             # plt.close()
# #             plt.show()
# #         else:
# #             print("No valid Pf data for scatter plot after filtering.")
# #     else:
# #         print("Pf data not available for scatter plot.")
# #
# #     # Plot 4: Pt Scatter Plot (Predicted vs. True)
# #     if (test_y_edge_true_pt is not None and len(test_y_edge_true_pt) > 0 and
# #             test_y_edge_pred_pt is not None and len(test_y_edge_pred_pt) > 0):
# #         true_pt_np = test_y_edge_true_pt.cpu().numpy()
# #         pred_pt_np = test_y_edge_pred_pt.cpu().numpy()
# #         valid_indices_pt = np.isfinite(true_pt_np) & np.isfinite(pred_pt_np)
# #         true_pt_np = true_pt_np[valid_indices_pt]
# #         pred_pt_np = pred_pt_np[valid_indices_pt]
# #
# #         if len(true_pt_np) > 0:
# #             plt.figure(figsize=(8, 7))
# #             min_val_pt = min(true_pt_np.min(), pred_pt_np.min()) * 0.99
# #             max_val_pt = max(true_pt_np.max(), pred_pt_np.max()) * 1.01
# #             plt.scatter(true_pt_np, pred_pt_np, alpha=0.5, s=10, label='Pt Predictions', color='green')
# #             plt.plot([min_val_pt, max_val_pt], [min_val_pt, max_val_pt], 'r--', linewidth=1.5, label='Ideal (y=x)')
# #             plt.xlabel('True Pt (pu)')
# #             plt.ylabel('Predicted Pt (pu)')
# #             plt.title(
# #                 f'Pt: Predicted vs. True ({os.path.basename(grid_file_to_process)} Test - {len(true_pt_np)} points)')
# #             plt.xlim(min_val_pt, max_val_pt)
# #             plt.ylim(min_val_pt, max_val_pt)
# #             plt.legend()
# #             plt.grid(True)
# #             plt.gca().set_aspect('equal', adjustable='box')
# #             plt.tight_layout()
# #             # pt_scatter_filename = f"{results_plot_prefix}gnn_pt_scatter{plot_suffix}.png"
# #             # plt.savefig(pt_scatter_filename)
# #             # print(f"Saved Pt scatter plot to {pt_scatter_filename}")
# #             # plt.close()
# #             plt.show()
# #
# #
# #         else:
# #             print("No valid Pt data for scatter plot after filtering.")
# #     else:
# #         print("Pt data not available for scatter plot.")
#
#
