from datetime import time
from typing import List

import numpy as np
import networkx as nx
from numpy.linalg import matrix_rank, inv
from scipy.sparse import csc_matrix, diags
from scipy.sparse.linalg import splu
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Simulations.StateEstimation.pseudo_measurements_augmentation import add_pseudo_measurements, \
    build_neighbors
from GridCalEngine.Simulations.StateEstimation.state_estimation_inputs import StateEstimationInput
from GridCalEngine.basic_structures import CscMat, IntVec, Logger
from GridCalEngine.Simulations.StateEstimation.state_estimation import Jacobian_SE


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
                                                          logger: Logger | None = None):
    """
    Fast decoupled WLS state estimator using LU decomposition based observability analysis
    Active power -> angles
    Reactive power -> voltage magnitudes
    """
    logger if logger is not None else Logger()
    V = nc.bus_data.Vbus.copy()
    # Identify non-slack buses
    non_slack_buses = no_slack  # Your no_slack variable
    n_non_slack = len(non_slack_buses)
    bus_contrib = {}
    # --- Create measurement type mapping based on processing order ---
    # The measurements are processed in this fixed order:
    # 1. p_inj, 2. q_inj, 3. pg_inj, 4. qg_inj,
    # 5. pf_value, 6. pt_value, 7. qf_value, 8. qt_value,
    # 9. if_value, 10. it_value, 11. vm_value, 12. va_value

    # Count measurements in each category
    counts = [
        len(se_input.p_inj), len(se_input.q_inj),
        len(se_input.pg_inj), len(se_input.qg_inj),
        len(se_input.pf_value), len(se_input.pt_value),
        len(se_input.qf_value), len(se_input.qt_value),
        len(se_input.if_value), len(se_input.it_value),
        len(se_input.vm_value), len(se_input.va_value)
    ]

    # Create measurement type array
    measurement_types = []
    unobservable_buses=[]
    for i, count in enumerate(counts):
        if i in [0, 2, 4, 5]:  # p_inj, pg_inj, pf_value, pt_value
            measurement_types.extend(['P'] * count)

    measurement_types = np.array(measurement_types)

    # Create indices for active and reactive measurements
    a_idx = np.where(measurement_types == 'P')[0]  # Active power measurements
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
    else:
        logger.add_warning("System is NOT fully observable")
        # find unobservable directions
        U, S, Vt = np.linalg.svd(Ga.toarray())
        null_mask = S < 1e-9
        nullspace = Vt.T[:, null_mask]  # basis vectors
        logger.add_info("Nullspace dimension:", nullspace.shape[1])

        # map nullspace to buses ---
        bus_contrib = {}  # dictionary: bus index -> total contribution
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
    return unobservable_buses, V, bus_contrib


def add_pseudo_measurements_for_unobservable_buses(bus_dict,unobservable_buses: object, se_input: object, V: object, Ybus: object, Cf: object, Ct: object,
                                                   sigma_pseudo_meas_value: object = 1.0,Sbase=100,
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
