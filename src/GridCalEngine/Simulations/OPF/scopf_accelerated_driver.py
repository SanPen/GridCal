import joblib
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

from GridCalEngine import SimulationTypes
from GridCalEngine.Simulations.OPF.scopf_accelerated_results import SCOPFNNResults
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate

from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import LinearMultiContingencies
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.OPF.scopf_results import SCOPFResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCalEngine.enumerations import SimulationTypes, EngineType, SolverType, AcOpfMode
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at

from GridCalEngine.Simulations.SCOPF_GNN.NumericalMethods.scopf import (run_nonlinear_MP_opf, run_nonlinear_SP_scopf)



class SCOPFNNDriver(TimeSeriesDriverTemplate):
    name = 'Security-constrained optimal power flow'
    tpe = SimulationTypes.SCOPF_accelerated_run

    def __init__(self,
                 grid: MultiCircuit,
                 pf_options: PowerFlowOptions,
                 scopf_options: OptimalPowerFlowOptions,
                 engine: EngineType = EngineType.GridCal,
                 df: pd.DataFrame = None):
        super().__init__(grid=grid,
                         time_indices=None,
                         clustering_results=None,
                         engine=engine,
                         check_time_series=False)
        self.scopf_options = scopf_options
        self.pf_options = pf_options
        self.results: SCOPFNNResults = None
        self.df = df

    def run_scopf_accelerated(self, contingency_vectors):
        import numpy as np
        import time
        from GridCalEngine.Simulations.SCOPF_GNN.NumericalMethods.scopf import (
            run_nonlinear_MP_opf, run_nonlinear_SP_scopf
        )
        time_start = time.time()
        self.scopf_options.acopf_mode = AcOpfMode.ACOPFslacks
        self.scopf_options.ips_tolerance = 1e-6
        grid = self.grid
        pf_options = self.pf_options
        scopf_options = self.scopf_options

        # Monitor branch loading
        for line in grid.lines:
            line.monitor_loading = True
        for tr in grid.transformers2w:
            tr.monitor_loading = True

        nc = compile_numerical_circuit_at(grid, t_idx=None)
        contingency_outputs = []

        for cont_idx, (W_k_vec, Z_k_vec, u_j_vec) in contingency_vectors.items():
            acopf_results = run_nonlinear_MP_opf(
                nc=nc,
                pf_options=pf_options,
                opf_options=scopf_options,
                pf_init=False,
                W_k_vec=W_k_vec,
                Z_k_vec=Z_k_vec,
                u_j_vec=u_j_vec
            )
            contingency_outputs.append((cont_idx, W_k_vec, Z_k_vec, u_j_vec, acopf_results))

        # print('')
        # print("--- Feeding SPs info to MP ---")
        # acopf_results = run_nonlinear_MP_opf(nc=nc,
        #                                      pf_options=pf_options,
        #                                      opf_options=scopf_options,
        #                                      pf_init=False,
        #                                      W_k_vec=W_k_vec_used,
        #                                      Z_k_vec=Z_k_vec_used,
        #                                      u_j_vec=u_j_vec_used)
        #
        # contingency_outputs.append(W_k_vec_used, Z_k_vec_used, u_j_vec_used)

        time_end = time.time()

        print(f"SCOPF completed in {time_end - time_start:.2f} seconds")

        from GridCalEngine.Simulations.OPF.scopf_accelerated_results import SCOPFNNResults

        self.results = SCOPFNNResults(
            bus_names=np.array([bus.name for bus in self.grid.buses]),
            generator_names=np.array([gen.name for gen in self.grid.generators]),
            branch_names=np.array([line.name for line in self.grid.lines]),
            Pg=acopf_results.Pg,
            contingency_outputs=contingency_outputs
        )

        return self.results

    def run(self) -> None:
        data = self.df
        # Define input and output columns
        all_cols = data.columns.tolist()
        num_pg = len([col for col in all_cols if col.startswith('Pg_')])
        input_cols = [f'Pg_{i}' for i in range(num_pg)] + ['contingency_index']
        num_uj = sum(col.startswith('u_j_') for col in all_cols)
        num_zk = sum(col.startswith('Z_k_') for col in all_cols)
        output_cols = ['W_k'] + [f'u_j_{i}' for i in range(num_uj)] + [f'Z_k_{i}' for i in range(num_zk)]
        # output_cols = ['W_k'] + [f'Z_k_{i}' for i in range(num_zk)]

        X = data[input_cols]
        y = data[output_cols]
        # print(y.describe())

        c = data[['contingency_index']]
        cont3_mask = c['contingency_index'] == 3
        X_3 = X[cont3_mask]
        y_3 = y[cont3_mask]
        c_3 = c[cont3_mask]

        if self.grid == '14_cont_v12.gridcal':
            # Increase oversampling factor
            oversample_factor = 10  # Try 10–20 for strong emphasis

            X = pd.concat([X] + [X_3] * oversample_factor, ignore_index=True)
            y = pd.concat([y] + [y_3] * oversample_factor, ignore_index=True)
            c = pd.concat([c] + [c_3] * oversample_factor, ignore_index=True)

        # Scale features and target
        scaler_X = StandardScaler()
        scaler_y = StandardScaler()

        # Fit the scalers (if not already done)
        scaler_X.fit(X)
        scaler_y.fit(y)

        # Save the fitted scalers
        scaler_X_path = f"/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/scaler_X_{self.grid}.pkl"
        scaler_y_path = f"/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/scaler_y_{self.grid}.pkl"

        joblib.dump(scaler_X, scaler_X_path)
        joblib.dump(scaler_y, scaler_y_path)

        print("Scalers saved successfully.")

        X_scaled = scaler_X.fit_transform(X)
        y_scaled = scaler_y.fit_transform(y)

        # Train/val/test split
        X_train, X_temp, y_train, y_temp, c_train, c_temp = train_test_split(X_scaled, y_scaled, c, test_size=0.2, stratify=c,
                                                                             random_state=42)
        X_val, X_test, y_val, y_test, c_val, c_test = train_test_split(X_temp, y_temp, c_temp, test_size=0.5, stratify=c_temp,
                                                                       random_state=42)

        # Count frequency of each contingency in training set
        contingency_counts = c_train['contingency_index'].value_counts()
        contingency_weights = 1.0 / contingency_counts
        contingency_weights = contingency_weights / contingency_weights.sum()  # Normalize

        if self.grid == '14_cont_v12.gridcal':
            contingency_weights[3] *= 3  # Manually boost weight for contingency 3
            contingency_weights = contingency_weights / contingency_weights.sum()  # Renormalize

        # Map to tensor (for fast lookup)
        max_index = c_train['contingency_index'].max()
        contingency_weight_tensor = torch.zeros(max_index + 1)
        for idx, weight in contingency_weights.items():
            contingency_weight_tensor[int(idx)] = weight

        # Convert to tensors
        X_train_tensor = torch.tensor(X_train, dtype=torch.float32)
        y_train_tensor = torch.tensor(y_train, dtype=torch.float32)
        X_val_tensor = torch.tensor(X_val, dtype=torch.float32)
        y_val_tensor = torch.tensor(y_val, dtype=torch.float32)
        X_test_tensor = torch.tensor(X_test, dtype=torch.float32)
        y_test_tensor = torch.tensor(y_test, dtype=torch.float32)

        # DataLoaders with tuned batch size
        c_train_tensor = torch.tensor(c_train.values, dtype=torch.int64)
        c_val_tensor = torch.tensor(c_val.values, dtype=torch.int64)
        c_test_tensor = torch.tensor(c_test.values, dtype=torch.int64)

        train_loader = DataLoader(TensorDataset(X_train_tensor, y_train_tensor, c_train_tensor), batch_size=64, shuffle=True)
        val_loader = DataLoader(TensorDataset(X_val_tensor, y_val_tensor, c_val_tensor), batch_size=64)
        test_loader = DataLoader(TensorDataset(X_test_tensor, y_test_tensor, c_test_tensor), batch_size=64)

        # Optimized model architecture
        class Net(nn.Module):
            def __init__(self, input_dim, output_dim):
                super(Net, self).__init__()
                self.model = nn.Sequential(
                    nn.Linear(input_dim, 128),  # hidden1
                    nn.ReLU(),
                    nn.Dropout(0.3),  # dropout
                    nn.Linear(128, 64),  # hidden2
                    nn.ReLU(),
                    nn.Linear(64, output_dim)
                )

            def forward(self, x):
                return self.model(x)

        model = Net(input_dim=X.shape[1], output_dim=y.shape[1])
        optimizer = optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-5)  # Optimized learning rate and weight decay
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)
        # scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=200)

        # Best loss weights from latest trial
        loss_weights = torch.tensor(
            [10] + [0.1] * num_uj + [100] * num_zk,
            dtype=torch.float32
        )
        # loss_weights = torch.tensor(
        #     [14.85] + [94.58] * num_zk,  # Remove u_j weights
        #     dtype=torch.float32
        # )
        loss_weights /= loss_weights.sum()

        def weighted_mse_loss(pred, target, weights, alpha=0.8):
            mse = ((weights * (pred - target) ** 2).mean())
            mae = ((weights * (pred - target).abs()).mean())
            return alpha * mse + (1 - alpha) * mae

        # Training loop with early stopping
        EPOCHS = 50
        early_stop_patience = 20
        best_val_loss = float('inf')
        patience_counter = 0
        train_losses, val_losses = [], []

        # Initialize lists for storing test loss
        test_losses = []

        # Training loop with early stopping
        for epoch in range(EPOCHS):
            model.train()
            train_loss = 0
            for xb, yb, cb in train_loader:  # cb = contingency_index batch
                optimizer.zero_grad()
                pred = model(xb)

                # Get per-sample weights based on contingency
                sample_weights = contingency_weight_tensor[cb.view(-1).long()]  # shape: (batch_size,)
                sample_weights = sample_weights.to(xb.device)

                # Compute weighted loss
                loss_per_sample = ((pred - yb) ** 2).mean(dim=1)  # shape: (batch_size,)
                loss = (sample_weights * loss_per_sample).mean()

                loss.backward()
                optimizer.step()

                train_loss += loss.item() * xb.size(0)

            train_loss /= len(train_loader.dataset)

            model.eval()
            val_loss = 0
            with torch.no_grad():
                for xb, yb, _ in val_loader:
                    pred = model(xb)
                    loss = weighted_mse_loss(pred, yb, loss_weights)
                    val_loss += loss.item() * xb.size(0)

            val_loss /= len(val_loader.dataset)

            # Add test loss computation
            test_loss = 0
            with torch.no_grad():
                for xb, yb, _ in test_loader:
                    pred = model(xb)
                    loss = weighted_mse_loss(pred, yb, loss_weights)
                    test_loss += loss.item() * xb.size(0)

            test_loss /= len(test_loader.dataset)

            # Store the losses for plotting
            train_losses.append(train_loss)
            val_losses.append(val_loss)
            test_losses.append(test_loss)

            scheduler.step(val_loss)

            print(
                f"Epoch {epoch + 1}/{EPOCHS} - Train Loss: {train_loss:.4f} - Val Loss: {val_loss:.4f} - Test Loss: {test_loss:.4f}")

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                torch.save(model.state_dict(), "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/load_var_14_v5.pt")
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= early_stop_patience:
                    print("Early stopping")
                    break

        # Evaluation
        model.load_state_dict(torch.load("/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/load_var_14_v5.pt"))
        model.eval()
        all_preds, all_targets, all_conts = [], [], []


        with torch.no_grad():
            for i in range(len(X_test_tensor)):
                x = X_test_tensor[i].unsqueeze(0)
                true_val = y_test_tensor[i]
                cont = c_test.iloc[i].values[0]
                pred_val = model(x).numpy()
                all_preds.append(pred_val[0])
                all_targets.append(true_val.numpy())
                all_conts.append(cont)

        from collections import defaultdict

        # Inverse transform the predicted outputs
        preds_inv = scaler_y.inverse_transform(all_preds)

        # Organize by contingency
        contingency_dict = defaultdict(list)

        for pred_vec, cont in zip(preds_inv, all_conts):
            contingency_dict[cont].append(pred_vec)
        #
        # # Inverse transform
        # preds_inv = scaler_y.inverse_transform(all_preds)
        # targets_inv = scaler_y.inverse_transform(all_targets)

        contingency_seen = set()
        contingency_vectors = {}

        # Inverse transform predictions
        preds_inv = scaler_y.inverse_transform(all_preds)

        # Loop through all predictions
        for pred_vec, cont in zip(preds_inv, all_conts):
            if cont not in contingency_seen:
                contingency_seen.add(cont)

                W_k = np.array([pred_vec[0]])
                u_j = pred_vec[1:1 + num_uj]
                Z_k = pred_vec[1 + num_uj:]

                contingency_vectors[cont] = (W_k, Z_k, u_j)

        # Metrics per contingency
        # df_eval = pd.DataFrame(all_conts, columns=['contingency'])
        # for i, col in enumerate(output_cols):
        #     df_eval[f'{col}_pred'] = preds_inv[:, i]
        #     df_eval[f'{col}_true'] = targets_inv[:, i]
        # print(df_eval)

        self.run_scopf_accelerated(
            contingency_vectors=contingency_vectors
        )

        return None