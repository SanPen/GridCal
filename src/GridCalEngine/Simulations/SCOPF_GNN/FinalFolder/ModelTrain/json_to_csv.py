import os
import json
import pandas as pd
import numpy as np


def process_json_file(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)

    Pg = data['Pg']
    rows = []

    for output in data['contingency_outputs']:
        row = {}

        # Inputs (Pg)
        for i, val in enumerate(Pg):
            row[f'Pg_{i}'] = val

        row['contingency_index'] = output['contingency_index']

        # Outputs
        row['W_k'] = output['W_k']

        # Get dynamic lengths
        num_u_j = len(output['u_j'])
        num_Z_k = len(output['Z_k'])

        for i in range(num_u_j):
            row[f'u_j_{i}'] = output['u_j'][i]

        for i in range(num_Z_k):
            row[f'Z_k_{i}'] = output['Z_k'][i]

        rows.append(row)

    return rows


def collate_json_folder(folder_path, output_csv='scopf_dataset_dynamic.csv'):
    all_rows = []
    for fname in os.listdir(folder_path):
        if fname.endswith('.json'):
            full_path = os.path.join(folder_path, fname)
            all_rows.extend(process_json_file(full_path))

    df = pd.DataFrame(all_rows)

    # Fill missing columns (some rows might be missing higher-indexed values)
    df = df.fillna(0.0)

    df.to_csv(output_csv, index=False)
    print(f"Dataset saved to {output_csv}")


# Example usage
# collate_json_folder('/Users/CristinaFray/PycharmProjects/GridCal/src//GridCalEngine/Simulations/SCOPF_GNN/new_aug_data/scopf_outputs_14', 'scopf_dataset_14.csv')
collate_json_folder('/Users/CristinaFray/PycharmProjects/GridCal/src//GridCalEngine/Simulations/SCOPF_GNN/new_aug_data/scopf_outputs_5', 'scopf_dataset_5.csv')
# collate_json_folder('/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/new_aug_data/scopf_outputs_39', 'scopf_dataset_39.csv')
