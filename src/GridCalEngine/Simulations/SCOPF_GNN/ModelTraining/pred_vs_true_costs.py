import os
import json
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np

# Directories
pred_dir = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/new_aug_data/pred_costs_14"
true_dir = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/new_aug_data/true_costs_14"

# Sorted file lists
pred_files = sorted([f for f in os.listdir(pred_dir) if f.endswith(".json")])
true_files = sorted([f for f in os.listdir(true_dir) if f.endswith(".json")])

# Data storage
data = {}  # {perturbation: list of (true_wk, pred_wk)}

# Load and organize data
for pred_file, true_file in zip(pred_files, true_files):
    with open(os.path.join(pred_dir, pred_file), "r") as f_pred, open(os.path.join(true_dir, true_file), "r") as f_true:
        pred_data = json.load(f_pred)
        true_data = json.load(f_true)

        perturb_id = pred_data["Perturbation"]
        pred_outputs = pred_data["contingency_outputs"]
        true_outputs = true_data["contingency_outputs"]

        for pred_entry, true_entry in zip(pred_outputs, true_outputs):
            cont_id = pred_entry["contingency_index"]
            pred_cost = pred_entry["W_k"]
            true_cost = true_entry["W_k"]

            if perturb_id not in data:
                data[perturb_id] = []
            data[perturb_id].append((true_cost, pred_cost))

# Plotting
plt.figure(figsize=(10, 6))

# Generate unique colors for each perturbation
unique_perturbations = sorted(data.keys())
colors = plt.cm.tab20(np.linspace(0, 1, len(unique_perturbations)))  # You can also try tab20, Set1, etc.

for i, p in enumerate(unique_perturbations):
    points = data[p]
    true_vals, pred_vals = zip(*points)
    plt.scatter(true_vals, pred_vals, color=colors[i], label=f'Perturbation {p}', s=60)

# Diagonal line
min_val = min(min(true for true, _ in points) for points in data.values())
max_val = max(max(true for true, _ in points) for points in data.values())
plt.plot([min_val, max_val], [min_val, max_val], 'k--', label='Ideal: Predicted = True')

plt.xlabel("True W_k")
plt.ylabel("Predicted W_k")
plt.title("Predicted vs True W_k by Perturbation and Contingency")
plt.legend(title="Perturbation", bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True)
plt.tight_layout()
plt.show()

import os
import json
import matplotlib.pyplot as plt
import numpy as np

# Directories
pred_dir = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/new_aug_data/pred_costs_14"
true_dir = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/new_aug_data/true_costs_14"

# Sorted file lists
pred_files = sorted([f for f in os.listdir(pred_dir) if f.endswith(".json")])
true_files = sorted([f for f in os.listdir(true_dir) if f.endswith(".json")])

# Data storage
perturb_ids = []
true_costs = []
pred_costs = []

# Load and compare total_costs
for pred_file, true_file in zip(pred_files, true_files):
    with open(os.path.join(pred_dir, pred_file), "r") as f_pred, open(os.path.join(true_dir, true_file), "r") as f_true:
        pred_data = json.load(f_pred)
        true_data = json.load(f_true)

        perturb_id = pred_data["Perturbation"]
        pred_total_cost = pred_data["total_cost"]
        true_total_cost = true_data["total_cost"]

        perturb_ids.append(perturb_id)
        pred_costs.append(pred_total_cost)
        true_costs.append(true_total_cost)

# Plotting
plt.figure(figsize=(8, 6))
plt.scatter(true_costs, pred_costs, color='tab:blue', s=70)

# Diagonal line for perfect prediction
min_val = min(min(true_costs), min(pred_costs))
max_val = max(max(true_costs), max(pred_costs))
plt.plot([min_val, max_val], [min_val, max_val], 'k--', label='Ideal: Predicted = True')

plt.xlabel("True Total Cost")
plt.ylabel("Predicted Total Cost")
plt.title("Predicted vs True Total Generation Cost per Perturbation")
for i, pid in enumerate(perturb_ids):
    plt.annotate(f"P{pid}", (true_costs[i], pred_costs[i]), textcoords="offset points", xytext=(0,5), ha='center')

plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()


# import os
# import json
# import matplotlib.pyplot as plt
#
# # Directories
# pred_dir = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/new_aug_data/pred_costs_5"
# true_dir = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/new_aug_data/true_costs_5"
#
# # Sorted file lists
# pred_files = sorted([f for f in os.listdir(pred_dir) if f.endswith(".json")])
# true_files = sorted([f for f in os.listdir(true_dir) if f.endswith(".json")])
# # Data storage
# perturb_ids = []
# contingency_ids = []
# true_wk = []
# pred_wk = []
#
# # Loop over files
# for pred_file, true_file in zip(pred_files, true_files):
#     pred_path = os.path.join(pred_dir, pred_file)
#     true_path = os.path.join(true_dir, true_file)
#
#     with open(pred_path, "r") as f_pred, open(true_path, "r") as f_true:
#         pred_data = json.load(f_pred)
#         true_data = json.load(f_true)
#
#         perturb_id = pred_data["Perturbation"]
#         print(f"Processing Perturbation ID: {perturb_id}")
#
#         pred_outputs = pred_data["contingency_outputs"]
#         true_outputs = true_data["contingency_outputs"]
#
#         for pred_entry, true_entry in zip(pred_outputs, true_outputs):
#             cont_id = pred_entry["contingency_index"]
#             pred_cost = pred_entry["W_k"]
#             true_cost = true_entry["W_k"]
#
#             perturb_ids.append(perturb_id)
#             contingency_ids.append(cont_id)
#             pred_wk.append(pred_cost)
#             true_wk.append(true_cost)
#
# # Plotting
# plt.figure(figsize=(10, 6))
# scatter = plt.scatter(true_wk, pred_wk, c=perturb_ids, cmap="viridis", alpha=0.5)
# plt.plot([min(true_wk), max(true_wk)],
#          [min(true_wk), max(true_wk)],
#          'k--', label="Ideal: Predicted = True")
#
# plt.xlabel("True Total Cost")
# plt.ylabel("Predicted Total Cost")
# plt.title("Total Costs per Contingency and Perturbation")
# cbar = plt.colorbar(scatter)
# cbar.set_label("Perturbation Index")
# plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.show()
