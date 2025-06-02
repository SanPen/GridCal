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

        # Inputs
        for i, val in enumerate(Pg):
            row[f'Pg_{i}'] = val
        row['contingency_index'] = output['contingency_index']

        # Outputs
        row['W_k'] = output['W_k']
        for i in range(5):
            row[f'u_j_{i}'] = output['u_j'][i] if i < len(output['u_j']) else 0.0
            row[f'Z_k_{i}'] = output['Z_k'][i] if i < len(output['Z_k']) else 0.0

        rows.append(row)

    return rows

def collate_json_folder(folder_path, output_csv='scopf_dataset.csv'):
    all_rows = []
    for fname in os.listdir(folder_path):
        if fname.endswith('.json'):
            full_path = os.path.join(folder_path, fname)
            all_rows.extend(process_json_file(full_path))

    df = pd.DataFrame(all_rows)
    df.to_csv(output_csv, index=False)
    print(f"Dataset saved to {output_csv}")

# Example usage
collate_json_folder('/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/new_aug_data/scopf_outputs', 'scopf_dataset.csv')
