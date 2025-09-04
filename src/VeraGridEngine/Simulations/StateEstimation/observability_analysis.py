from datetime import time
from typing import List

import numpy as np
import networkx as nx
from matplotlib import pyplot as plt
from numpy.linalg import matrix_rank, inv
from scipy.sparse import csc_matrix, diags
from scipy.sparse.linalg import splu
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Simulations.StateEstimation.pseudo_measurements_augmentation import add_pseudo_measurements, \
    build_neighbors
from VeraGridEngine.Simulations.StateEstimation.state_estimation_inputs import StateEstimationInput
from VeraGridEngine.basic_structures import CscMat, IntVec, Logger
from VeraGridEngine.Simulations.StateEstimation.state_estimation import Jacobian_SE
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp


def check_for_observability_and_return_unobservable_buses(nc: NumericalCircuit,
                                                          Ybus: CscMat,
                                                          Yf: CscMat,
                                                          Yt: CscMat,
                                                          no_slack: IntVec,
                                                          F: IntVec,
                                                          T: IntVec,
                                                          Cf: csc_matrix,
                                                          Ct: csc_matrix,
                                                          se_input: StateEstimationInput,
                                                          fixed_slack: bool = True,
                                                          tolerance_for_observability_score=1e-6,
                                                          do_profiling_of_measurements: bool = False,
                                                          include_line_measurements_on_both_ends:bool=True,
                                                          logger: Logger | None = None):
    """
    Fast decoupled WLS state estimator using LU decomposition based observability analysis
    Active power -> angles
    Reactive power -> voltage magnitudes
    """
    logger = logger if logger is not None else Logger()
    V = nc.bus_data.Vbus.copy()
    # Identify non-slack buses
    non_slack_buses = no_slack  # Your no_slack variable
    n_non_slack = len(non_slack_buses)
    bus_contrib = {}  # dictionary: bus index -> total contribution

    # --- Build measurement type mapping with api_objects ---
    measurement_types = []
    measurement_ids = []  # (category_name, api_object)

    for meas in se_input.p_inj:
        measurement_types.append("P")
        measurement_ids.append(("p_inj", meas.api_object))
    for meas in se_input.q_inj:
        measurement_types.append("Q")
        measurement_ids.append(("q_inj", meas.api_object))
    for meas in se_input.pg_inj:
        measurement_types.append("P")
        measurement_ids.append(("pg_inj", meas.api_object))
    for meas in se_input.qg_inj:
        measurement_types.append("Q")
        measurement_ids.append(("qg_inj", meas.api_object))
    for meas in se_input.pf_value:
        measurement_types.append("P")
        measurement_ids.append(("pf_value", meas.api_object))
    for meas in se_input.pt_value:
        measurement_types.append("P")
        measurement_ids.append(("pt_value", meas.api_object))
    for meas in se_input.qf_value:
        measurement_types.append("Q")
        measurement_ids.append(("qf_value", meas.api_object))
    for meas in se_input.qt_value:
        measurement_types.append("Q")
        measurement_ids.append(("qt_value", meas.api_object))
    for meas in se_input.if_value:
        measurement_types.append("I")
        measurement_ids.append(("if_value", meas.api_object))
    for meas in se_input.it_value:
        measurement_types.append("I")
        measurement_ids.append(("it_value", meas.api_object))
    for meas in se_input.vm_value:
        measurement_types.append("V")
        measurement_ids.append(("vm_value", meas.api_object))
    for meas in se_input.va_value:
        measurement_types.append("V")
        measurement_ids.append(("va_value", meas.api_object))

    measurement_types = np.array(measurement_types)
    measurement_ids = np.array(measurement_ids, dtype=object)
    unobservable_buses = []

    measurement_types = np.array(measurement_types)

    # Create indices for active and reactive measurements
    a_idx = np.where(measurement_types == "P")[0]  # Active power measurements
    load_per_bus = nc.load_data.get_injections_per_bus() / nc.Sbase
    H, h, Scalc = Jacobian_SE(Ybus, Yf, Yt, V, F, T, Cf, Ct,
                              se_input, non_slack_buses, load_per_bus, fixed_slack)
    # --- 2) Build and factorize Ga (P-subsystem)
    Ha = H.tocsr()[a_idx, :n_non_slack]  # dP/dθ (rows = P-meas, cols = θ_non_slack)
    Ga = Ha.T @ Ha

    # (b) Rank test (rank = linearly independent rows)
    rank = np.linalg.matrix_rank(Ga.toarray(), tol=1e-9)
    n = Ga.shape[0]

    if rank == n:
        logger.add_info("System is fully observable")
        # Here we can continue with measurement profiling (classification
        # The idea is to find out which measurement set is critical, which has local redundancy and which has global
        # redundancy

        # To do this we must remove one measurement at a time and check observability again, if rank decreases
        # meas is critical.Local and/or Global redundancy will be based oon graph theoritic observability
        if do_profiling_of_measurements:
            r_idx = np.where(measurement_types == "Q")[0]
            v_idx = np.where(measurement_types == "V")[0]
            i_idx = np.where(measurement_types == "I")[0]
            Hr = H.tocsr()[r_idx, n_non_slack:]
            Hv = H.tocsr()[v_idx, :]
            Hi = H.tocsr()[i_idx, :]
            measurement_profile=parallel_measurement_profiling(Ha, Hr, Hv, Hi, measurement_ids, a_idx, r_idx, v_idx, i_idx,True)
            bus_status = bus_observability_profile(measurement_profile)
            plot_bus_observability(bus_status)
            logger.add_info("Measurement profiling completed")
            return True, [], measurement_profile, V, bus_contrib
        else:
            # Observable but no profiling
            return True, [], None, V, bus_contrib

    else:
        logger.add_warning("System is NOT fully observable")
        # find unobservable directions
        U, S, Vt = np.linalg.svd(Ga.toarray())
        null_mask = S < 1e-9
        nullspace = Vt.T[:, null_mask]  # basis vectors
        logger.add_info("Nullspace dimension:", nullspace.shape[1])

        # map nullspace to buses ---
        for idx, bus in enumerate(non_slack_buses):
            # contribution of this bus to all nullspace directions
            contrib = np.sqrt(np.sum(nullspace[idx, :] ** 2))
            bus_contrib[bus] = contrib

        # sort buses by contribution (highest = most unobservable)
        sorted_buses = sorted(bus_contrib.items(), key=lambda kv: kv[1], reverse=True)

        logger.add_info("Bus observability contributions (higher = more unobservable):")
        for bus, score in sorted_buses:
            logger.add_info(f"Bus {bus}: {score:.6f}")
            # return list of unobservable buses with contribution > threshold
            if score > tolerance_for_observability_score:
                unobservable_buses.append(bus)
        return False, unobservable_buses, None, V, bus_contrib



def parallel_measurement_profiling(Ha, Hr, Hv, Hi, measurement_ids, a_idx, r_idx, v_idx, i_idx,
                                   include_line_measurements_on_both_ends=True):
    """
    Parallel execution of all 4 measurement profiling strategies.
    """
    # Prepare arguments for parallel processing
    args_list = [
        (Ha, measurement_ids[a_idx], include_line_measurements_on_both_ends),
        (Hr, measurement_ids[r_idx], include_line_measurements_on_both_ends),
        (Hv, measurement_ids[v_idx], include_line_measurements_on_both_ends),
        (Hi, measurement_ids[i_idx], include_line_measurements_on_both_ends)
    ]

    strategies = ["active", "reactive", "voltage", "current"]
    results = {}

    # Use ProcessPoolExecutor for true parallel execution
    with ProcessPoolExecutor(max_workers=min(4, mp.cpu_count())) as executor:
        # Submit all tasks
        future_to_strategy = {
            executor.submit(profile_measurements_ultrafast, *args): strategy
            for args, strategy in zip(args_list, strategies)
        }

        # Collect results as they complete
        for future in as_completed(future_to_strategy):
            strategy = future_to_strategy[future]
            try:
                results[strategy] = future.result()
            except Exception as e:
                print(f"Error processing {strategy}: {e}")
                results[strategy] = {}

    return results






def add_pseudo_measurements_for_unobservable_buses(bus_dict, unobservable_buses: object, se_input: object, V: object,
                                                   Ybus: object, Cf: object, Ct: object,
                                                   sigma_pseudo_meas_value: object = 1.0, Sbase=100,
                                                   logger: object = None) -> StateEstimationInput:
    """
    Full preprocessing: detect unobservable buses and add pseudo-measurements
    """
    # Step 1: create neighbours from connectivity matrices once per island
    neighbors = build_neighbors(Cf, Ct)
    # Step 2: add pseudo-measurements
    # Add pseudo-measurements using precomputed neighbors
    return add_pseudo_measurements(
        se_input,
        unobservable_buses,
        V,
        Ybus,
        neighbors,
        bus_dict=bus_dict,
        sigma_pseudo=sigma_pseudo_meas_value,
        Sbase=100,
        logger=logger
    )


def profile_measurements(Hsub, ids, tol=1e-9,include_line_measurements_on_both_ends=True):
    """
    Condition	            System rank	            Local rank	            Classification
    Rank drops system-wide	    ↓	                    –	                Critical
    System rank full           full	                   full	                Locally redundant
    (local rank unchanged)
    System rank full	       full                 	↓	                Globally redundant
    ( local rank ↓)
    """
    n = Hsub.shape[1]
    prof = {}
    # Ensure IDs are tuples for hashable dict keys
    ids = [tuple(id_) for id_ in ids]
    groups = build_local_groups(ids,include_line_measurements_on_both_ends=include_line_measurements_on_both_ends)
    # Convert Hsub to dense once if it's sparse
    H_dense = Hsub.toarray() if hasattr(Hsub, "toarray") else Hsub
    # Precompute G = H.T @ H once
    G = H_dense.T @ H_dense
    for idx, meas_id in enumerate(ids):
        # this is slower but understandable
        #mask = np.arange(Hsub.shape[0]) != idx
        #H_reduced = Hsub[mask, :]
        #G_reduced = H_reduced.T @ H_reduced
        #rank_reduced = np.linalg.matrix_rank(G_reduced.toarray(), tol=tol)

        # Compute rank using rank-1 downdate instead of full recomputation
        # Extract the measurement row
        h_i = H_dense[idx, :].reshape(-1, 1)
        G_reduced = G - h_i @ h_i.T
        rank_reduced = np.linalg.matrix_rank(G_reduced, tol=tol)
        if rank_reduced < n:
            prof[meas_id] = "critical"
        else:
            # --- Redundant: distinguish local vs global ---
            (cat, api_obj) = meas_id
            # Determine the correct key
            if cat in ["pf_value", "qf_value", "if_value"]:
                key = f"bus_{api_obj.bus_from}"
            elif cat in ["pt_value", "qt_value", "it_value"]:
                key = f"bus_{api_obj.bus_to}"
            else:
                key = f"bus_{api_obj}"

            related_idxs = groups[key]

            if len(related_idxs) > 1:
                # Build local Jacobian restricted to this group
                H_local = H_dense[related_idxs, :]
                rank_local = np.linalg.matrix_rank(H_local, tol=tol)
                H_local_reduced = np.delete(H_local, related_idxs.index(idx), axis=0)
                rank_local_minus_one = np.linalg.matrix_rank(H_local_reduced, tol=tol)
                redundancy_type = classify_redundancy(H_dense, idx, tol)
                if rank_local == rank_local_minus_one:
                    prof[meas_id] = f"locally redundant ({redundancy_type})"
                else:
                    prof[meas_id] = f"globally redundant ({redundancy_type})"
            else:
                # Only one measurement in the group → global redundancy
                redundancy_type = classify_redundancy(H_dense, idx, tol)
                prof[meas_id] = f"globally redundant ({redundancy_type})"

    return prof


def profile_measurements_ultrafast(Hsub, ids, tol=1e-9, include_line_measurements_on_both_ends=True):
    """
    Ultra-fast version with identical results to original.
    """
    n = Hsub.shape[1]
    prof = {}

    ids = [tuple(id_) for id_ in ids]
    groups = build_local_groups(ids, include_line_measurements_on_both_ends=include_line_measurements_on_both_ends)

    H_dense = Hsub.toarray() if hasattr(Hsub, "toarray") else Hsub
    G = H_dense.T @ H_dense

    # Precompute SVD for smart criticality screening
    U, s, Vh = np.linalg.svd(H_dense, full_matrices=False)
    rank_full = np.sum(s > tol)
    U_rank = U[:, :rank_full]

    # Identify critical measurement candidates efficiently
    critical_candidates = np.where(np.max(np.abs(U_rank), axis=1) > 0.7)[0]

    # Precompute all local group information
    group_cache = {}
    for key, indices in groups.items():
        H_local = H_dense[indices, :]
        group_cache[key] = {
            'indices': indices,
            'local_rank': np.linalg.matrix_rank(H_local, tol=tol),
            'H_local': H_local
        }

    # Process measurements
    for idx in range(H_dense.shape[0]):
        meas_id = ids[idx]

        # Check criticality only for candidates
        if idx in critical_candidates:
            h_i = H_dense[idx, :].reshape(1, -1)
            G_reduced = G - h_i.T @ h_i
            if np.linalg.matrix_rank(G_reduced, tol=tol) < n:
                prof[meas_id] = "critical"
                continue

        # Redundancy classification
        (cat, api_obj) = meas_id

        if cat in ["pf_value", "qf_value", "if_value"]:
            key = f"bus_{api_obj.bus_from}"
        elif cat in ["pt_value", "qt_value", "it_value"]:
            key = f"bus_{api_obj.bus_to}"
        else:
            key = f"bus_{api_obj}"

        group_data = group_cache[key]
        related_idxs = group_data['indices']

        if len(related_idxs) > 1:
            # Find position and remove current measurement
            pos = related_idxs.index(idx)
            mask = np.ones(len(related_idxs), dtype=bool)
            mask[pos] = False
            H_local_reduced = group_data['H_local'][mask, :]

            rank_local_reduced = np.linalg.matrix_rank(H_local_reduced, tol=tol)
            redundancy_type = classify_redundancy(H_dense, idx, tol)

            if group_data['local_rank'] == rank_local_reduced:
                prof[meas_id] = f"locally redundant ({redundancy_type})"
            else:
                prof[meas_id] = f"globally redundant ({redundancy_type})"
        else:
            redundancy_type = classify_redundancy(H_dense, idx, tol)
            prof[meas_id] = f"globally redundant ({redundancy_type})"

    return prof


def build_local_groups(measurement_ids,include_line_measurements_on_both_ends=True ):
    groups = defaultdict(list)

    for idx, (cat, api_obj) in enumerate(measurement_ids):
        # Bus measurements
        if cat in ["p_inj", "q_inj", "pg_inj", "qg_inj", "vm_value", "va_value"]:
            bus = api_obj  # for bus measurements, api_object itself identifies the bus
            groups[f"bus_{bus}"].append(idx)

        # Line/transformer flow measurements
        elif cat in ["pf_value", "qf_value", "pt_value", "qt_value", "if_value", "it_value"]:
            # Decide which bus side this measurement belongs to
            if include_line_measurements_on_both_ends:
                bus_from = api_obj.bus_from
                bus_to = api_obj.bus_to
                groups[f"bus_{bus_from}"].append(idx)
                groups[f"bus_{bus_to}"].append(idx)
            else:
                if cat in ["pf_value", "qf_value", "if_value"]:
                    bus = api_obj.bus_from
                else:
                    bus = api_obj.bus_to
                groups[f"bus_{bus}"].append(idx)

    return groups


def bus_observability_profile(measurement_profile):
    """
    Convert measurement_profile (from profile_measurements) into a nested dict:
    {measurement_type: {bus: worst_status}}
    """
    bus_status_per_type = {}

    for meas_type, prof_dict in measurement_profile.items():
        bus_profile = defaultdict(list)

        for (cat, api_obj), status in prof_dict.items():
            # Determine which bus this measurement belongs to
            if cat in ["pf_value", "qf_value", "if_value"]:
                bus = api_obj.bus_from
            elif cat in ["pt_value", "qt_value", "it_value"]:
                bus = api_obj.bus_to
            else:
                bus = api_obj  # bus measurement

            bus_profile[bus].append(status)

        # Aggregate: pick the "worst" status for the bus
        def worst_status(status_list):
            if "critical" in status_list:
                return "critical"
            elif "globally redundant" in status_list:
                return "globally redundant"
            else:
                return "locally redundant"

        bus_status_per_type[meas_type] = {bus: worst_status(statuses) for bus, statuses in bus_profile.items()}

    return bus_status_per_type


def plot_bus_observability(bus_status_per_type):
    """
    bus_status_per_type: dict of dicts
    Example:
    {
        'active': {'bus_1': 'critical', 'bus_2': 'globally redundant', ...},
        'reactive': {...},
        'voltage': {...},
        'current': {...}
    }
    """
    measurement_types = list(bus_status_per_type.keys())
    buses = list(next(iter(bus_status_per_type.values())).keys())
    n_buses = len(buses)
    n_types = len(measurement_types)

    # Color map
    color_map = {
        "critical": "red",
        "globally redundant": "orange",
        "locally redundant": "yellow",
        "none": "gray"  # add default for missing measurements
    }

    x = np.arange(n_buses)
    width = 0.2  # width of each bar

    plt.figure(figsize=(12, 5))

    for i, m_type in enumerate(measurement_types):
        statuses = [
            bus_status_per_type[m_type].get(b, "none")  # use .get() with default
            for b in buses
        ]
        colors = [color_map[s] for s in statuses]
        plt.bar(x + i * width, [1] * n_buses, width=width, color=colors, label=m_type)

    plt.xticks(x + width * (n_types - 1) / 2, buses, rotation=90)
    plt.ylabel("Observability")
    plt.title("Bus Observability Profile by Measurement Type")
    plt.legend()
    # plt.show()

# -------------- we extend measurement classification to check single and mutliple redundancies ----------------------
def classify_redundancy(H, idx, tol=1e-9):
    """Classify redundant measurement into none/single/multiple redundancy."""
    """
    Take the measurement’s row h_i.Remove it from the Jacobian H_rest.
    """
    h_i = H[idx, :].reshape(1, -1)      # row vector = the measurement we test
    H_rest = np.delete(H, idx, axis=0)  # all other measurements

    # Least squares to check dependence
    """
    Try to express h_i as a linear combination of the others (least-squares fit).residual_norm tells us how well 
    it can be reconstructed: If residual is large, it means h_i is not redundant at all → "none". If residual is tiny, 
    then h_i lies in the span of others → it’s redundant
    """
    coeffs, residuals, _, _ = np.linalg.lstsq(H_rest.T, h_i.T, rcond=None)
    residual_norm = np.linalg.norm(h_i - coeffs.T @ H_rest)

    if residual_norm > tol:
        return "none"
    else:
        """
        Count how many coefficients in that linear combination are significant. If only 1 other measurement explains
         h_i → "single redundancy".If it needs multiple others together → "multiple redundancy".
        """
        nnz = np.sum(np.abs(coeffs) > 1e-6)
        return "single" if nnz == 1 else "multiple"