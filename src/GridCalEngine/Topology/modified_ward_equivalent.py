# ward_reduce_gridcal.py
# Pivot-free Ward reduction + generator relocation using SciPy sparse and (optionally) GridCal
# Now with:
#   - 10× original-reactance pruning rule
#   - DC inverse PF redistribution to match boundary angles from the full network
#
# Requirements:
#   numpy, scipy, networkx
#   (optional) GridCal >= 5.x (for Y-bus + names and P injections)

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List, Dict, Tuple, Optional, Sequence

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import networkx as nx

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions


# -----------------------------
# Core Ward reduction (Schur)
# -----------------------------

def ward_reduce(Y: sp.csr_matrix, retain_idx: Sequence[int]) -> sp.csc_matrix:
    """
    Compute the Ward reduction (Schur complement) of Y onto the retained buses R.

    Parameters
    ----------
    Y : (n x n) complex sparse matrix
        Bus admittance matrix.
    retain_idx : list/array of ints
        Indices (0-based) of buses to retain.

    Returns
    -------
    Yeq : (|R| x |R|) complex CSC matrix
    """
    Y = Y.tocsc()
    n = Y.shape[0]
    retain_idx = np.asarray(retain_idx, dtype=int)
    mask = np.zeros(n, dtype=bool)
    mask[retain_idx] = True
    elim_idx = np.flatnonzero(~mask)

    Yrr = Y[retain_idx, :][:, retain_idx]
    Yre = Y[retain_idx, :][:, elim_idx]
    Yer = Y[elim_idx, :][:, retain_idx]
    Yee = Y[elim_idx, :][:, elim_idx]

    if Yee.shape[0] == 0:
        return Yrr.tocsc()

    # Solve Yee * X = Yer (multi-RHS sparse solve)
    X = spla.spsolve(Yee.tocsc(), Yer.toarray())
    Yeq = (Yrr - Yre @ sp.csr_matrix(X)).tocsc()
    return Yeq


# ---------------------------------------
# Helpers to compute reactances / pruning
# ---------------------------------------

def _max_original_reactance_from_Y(Y: sp.csc_matrix, eps: float = 1e-12) -> float:
    """
    Scan the ORIGINAL Y-bus off-diagonals and compute the maximum |x_ij|,
    where x_ij = imag( 1 / (-Y_ij) ). This is the per-pair equivalent reactance
    (sum of parallels already aggregated by Y).
    """
    Y = Y.tocsc()
    tril = sp.tril(Y, k=-1)
    _, _, off = sp.find(tril)
    if off.size == 0:
        return 0.0
    y_series = -off.astype(complex)
    mask = np.abs(y_series) > eps
    if not np.any(mask):
        return 0.0
    x_vals = np.abs(np.imag(1.0 / y_series[mask]))
    max_x = float(np.max(x_vals)) if x_vals.size else 0.0
    return max_x


@dataclass
class EquivElements:
    """
    Equivalent elements extracted from Yeq.
    """
    # complex shunt admittances at retained buses (diag of Yeq)
    shunt_diag: np.ndarray

    # rows: [i, j, y_series_complex, z_series_complex]
    branches: np.ndarray


def y_to_equivalents_10x_rule(Yeq: sp.csc_matrix,
                              Y_original: sp.csc_matrix,
                              eps: float = 1e-12) -> EquivElements:
    """
    Extract equivalents from Yeq and prune equivalent lines using the
    '10× original-reactance' rule: keep lines with |z_eq| <= 10 * max_x_original.

    Parameters
    ----------
    Yeq : reduced Y on retained set
    Y_original : original full Y-bus (to measure max original |x|)
    eps : small magnitude guard for y

    Returns
    -------
    EquivElements
    """
    Yeq = Yeq.tocsc()
    shunt_diag = Yeq.diagonal().astype(complex, copy=True)

    # Compute pruning threshold
    max_x = _max_original_reactance_from_Y(Y_original, eps=eps)
    if max_x <= 0.0:
        # Fallback: no pruning if we can't measure original |x|
        prune_impedance = np.inf
    else:
        prune_impedance = 10.0 * max_x

    tril = sp.tril(Yeq, k=-1)  # Return the lower triangular portion of a sparse array or matrix
    ii, jj, v = sp.find(tril)
    y_series = -v.astype(complex)
    mask_y = np.abs(y_series) > eps
    ii, jj, y_series = ii[mask_y], jj[mask_y], y_series[mask_y]
    z_series = 1.0 / y_series

    keep = np.abs(z_series) <= prune_impedance
    ii, jj = ii[keep], jj[keep]
    y_series = y_series[keep]
    z_series = z_series[keep]

    branches = np.column_stack([ii, jj, y_series, z_series])
    return EquivElements(shunt_diag=shunt_diag, branches=branches)


# -------------------------------------------------
# Electrical-distance graph + generator relocation
# -------------------------------------------------

def build_distance_graph_from_Yeq(Yeq: sp.csc_matrix, mode: str = "ac") -> nx.Graph:
    """
    Edge weight from Yeq off-diagonals:
        - 'ac' : |z| = |1/(-Yeq_ij)|
        - 'dc' : |x| = |imag(1/(-Yeq_ij))|
    """
    Yeq = Yeq.tocsc()
    tril = sp.tril(Yeq, k=-1)
    i, j, off = sp.find(tril)
    y_series = -off.astype(complex)
    eps = 1e-12
    mask = np.abs(y_series) > eps
    i, j, y_series = i[mask], j[mask], y_series[mask]
    z = 1.0 / y_series

    if mode == "ac":
        w = np.abs(z)
    elif mode == "dc":
        w = np.abs(np.imag(z))
    else:
        raise ValueError("mode must be 'ac' or 'dc'")

    G = nx.Graph()
    G.add_nodes_from(range(Yeq.shape[0]))
    for a, b, weight in zip(i, j, w):
        if G.has_edge(a, b):
            G[a][b]["weight"] = min(G[a][b]["weight"], float(weight))
        else:
            G.add_edge(a, b, weight=float(weight))
    return G


def relocate_generators(Yeq_G2: sp.csc_matrix,
                        gen_idx: Iterable[int],
                        boundary_idx: Iterable[int],
                        mode: str = "ac") -> Dict[int, int]:
    """
    Map each generator position in G2 to the closest boundary position in G2.
    Returns dict: {gen_pos_in_G2 -> boundary_pos_in_G2}
    """
    G = build_distance_graph_from_Yeq(Yeq_G2, mode=mode)
    link: Dict[int, int] = {}
    B = list(boundary_idx)
    if len(B) == 0:
        return link

    for g in gen_idx:
        try:
            dists = nx.single_source_dijkstra_path_length(G, g, weight="weight")
        except nx.NetworkXNoPath:
            continue
        best_b, best_val = None, np.inf
        for b in B:
            val = dists.get(b, np.inf)
            if val < best_val:
                best_b, best_val = b, val
        if best_b is not None and np.isfinite(best_val):
            link[g] = best_b
    return link


# -----------------------------------------
# Optional: GridCal convenience integration
# -----------------------------------------

def _gridcal_get_Y_and_names(circuit: MultiCircuit) -> Tuple[sp.csc_matrix, Iterable[str]]:
    """
    Obtain Y-bus and bus names from a GridCal circuit.
    :param circuit:
    :return: Ybus, bus_names
    """

    nc = compile_numerical_circuit_at(circuit=circuit, t_idx=None)
    adm = nc.get_admittance_matrices()
    bus_names = circuit.get_bus_names()
    return adm.Ybus, bus_names


def _gridcal_indices_from_names(all_names: List[str], target_names: Iterable[str]) -> List[int]:
    idx_map = {name: k for k, name in enumerate(all_names)}
    out = []
    for nm in target_names:
        if nm not in idx_map:
            raise KeyError(f"Bus name '{nm}' not found in GridCal Y-bus order.")
        out.append(idx_map[nm])
    return out


def _gridcal_generator_bus_indices_in_Y_order(circuit, y_order_names: List[str]) -> Tuple[List[int], List[object]]:
    """
    Return generator bus indices aligned to Y order, and the generator objects in the same order.
    """
    gens = [g for g in circuit.generators if g.active]

    gen_bus_names = []
    for g in gens:
        bus = getattr(g, "bus", None)
        name = getattr(bus, "name", None)
        if name is not None:
            gen_bus_names.append(name)
        else:
            gen_bus_names.append(None)

    gen_idx = []
    idx_map = {name: k for k, name in enumerate(y_order_names)}
    for nm in gen_bus_names:
        if nm is None or nm not in idx_map:
            gen_idx.append(None)
        else:
            gen_idx.append(idx_map[nm])

    # Filter out None (disconnected gens) keeping same order in 'gens'
    out_idx, out_gens = [], []
    for idx, g in zip(gen_idx, gens):
        if idx is not None:
            out_idx.append(idx)
            out_gens.append(g)
    return out_idx, out_gens


# ---------------------------
# DC inverse PF redistribution
# ---------------------------

def _get_float_attr(obj, candidates: Sequence[str], default: float = 0.0) -> float:
    for a in candidates:
        if hasattr(obj, a):
            try:
                v = getattr(obj, a)
                if v is None:
                    continue
                return float(v)
            except Exception:
                continue
    return default


def _gridcal_system_base_MVA(circuit) -> float:
    for attr in ["Sbase", "S_base", "Sbase_MVA", "S_base_MVA", "base_MVA", "baseMVA"]:
        if hasattr(circuit, attr):
            try:
                v = float(getattr(circuit, attr))
                if v > 0:
                    return v
            except Exception:
                pass
    # Conservative default
    return 100.0


def _gridcal_Pinj_pu(circuit, y_order_names: List[str]) -> np.ndarray:
    """
    Build P injection vector (per unit, +gen -load) aligned with Y order.
    """
    n = len(y_order_names)
    idx_map = {name: k for k, name in enumerate(y_order_names)}
    P_MW = np.zeros(n, dtype=float)

    # Generators
    gens = list(getattr(circuit, "generators", []))
    for g in gens:
        bus = getattr(g, "bus", None)
        bname = getattr(bus, "name", None)
        if bname is None or bname not in idx_map:
            continue
        k = idx_map[bname]
        Pg = _get_float_attr(g, ["Pg", "P", "p", "p_set", "p_mw", "P_MW"], default=0.0)
        P_MW[k] += Pg

    # Loads
    loads = list(getattr(circuit, "loads", []))
    for ld in loads:
        bus = getattr(ld, "bus", None)
        bname = getattr(bus, "name", None)
        if bname is None or bname not in idx_map:
            continue
        k = idx_map[bname]
        Pl = _get_float_attr(ld, ["P", "p", "p_set", "p_mw", "P_MW"], default=0.0)
        P_MW[k] -= Pl

    Sbase = _gridcal_system_base_MVA(circuit)
    return P_MW / max(Sbase, 1e-6)


def _build_B_from_Y(Y: sp.csc_matrix) -> sp.csr_matrix:
    """
    Build a DC susceptance-like matrix B' from Y using line reactances:
      B[i,j] = -1/x_ij for i!=j if there exists coupling,
      B[i,i] = -sum_{j!=i} B[i,j].
    Note: x_ij is taken from z_ij = 1/(-Y_ij).
    """
    Y = Y.tocsc()
    tril = sp.tril(Y, k=-1)
    i, j, off = sp.find(tril)
    y_series = -off.astype(complex)

    # avoid division by ~0
    eps = 1e-12
    mask = np.abs(y_series) > eps
    i, j, y_series = i[mask], j[mask], y_series[mask]
    z = 1.0 / y_series
    x = np.imag(z)

    # Build COO for off-diagonals
    data_off = []
    rows_off = []
    cols_off = []
    for a, b, xab in zip(i, j, x):
        if np.abs(xab) < eps:
            continue
        val = -1.0 / xab  # off-diagonal DC susceptance
        rows_off.extend([a, b])
        cols_off.extend([b, a])
        data_off.extend([val, val])

    n = Y.shape[0]
    B = sp.coo_matrix((data_off, (rows_off, cols_off)), shape=(n, n)).tocsc()
    # Diagonal = -row-sum of off-diagonals
    diag = -np.array(B.sum(axis=1)).ravel()
    B = B + sp.diags(diag, 0, shape=(n, n))
    return B.tocsc()


def _dc_theta(B: sp.csc_matrix, Pinj: np.ndarray, slack_idx: int) -> np.ndarray:
    """
    Solve B * theta = P with theta_slack = 0.
    """
    n = B.shape[0]
    mask = np.ones(n, dtype=bool)
    mask[slack_idx] = False
    Bnn = B[mask, :][:, mask]
    Pn = Pinj[mask]
    theta_n = spla.spsolve(Bnn.tocsc(), Pn.astype(float))
    theta = np.zeros(n, dtype=float)
    theta[mask] = theta_n
    theta[slack_idx] = 0.0
    return theta


def _B_from_Yeq_G1(Yeq_G1: sp.csc_matrix) -> sp.csr_matrix:
    """
    Build reduced DC B' from the boundary-only Yeq_G1 (same recipe as _build_B_from_Y).
    """
    return _build_B_from_Y(Yeq_G1)


@dataclass
class DCInversePF:
    theta_B: np.ndarray  # boundary angles (rad) from full-network DC
    Bred: sp.csr_matrix  # DC matrix on reduced boundary
    P_target: np.ndarray  # target boundary injections to reproduce theta_B on reduced grid
    Pgen_assigned: np.ndarray  # sum of relocated generator P at each boundary bus (pu)
    L_new: np.ndarray  # boundary loads (pu) to enforce P_target with relocated gens (L = Pg - P_target)


def dc_inverse_pf_redistribution(
        circuit,
        Y_full: sp.csc_matrix,
        Yeq_G1: sp.csc_matrix,
        y_order_names: List[str],
        boundary_idx_in_Y: List[int],
        retain2_idx_in_Y: List[int],
        boundary_idx_in_G2: List[int],
        gen_idx_in_G2: List[int],
        relocation_map_g2: Dict[int, int],
) -> DCInversePF:
    """
    Compute boundary loads in the reduced grid so that the reduced DC model reproduces
    the boundary angles of the original full network under DC.

    Steps:
      1) Full network DC: build B_full from Y_full; build Pinj_pu from circuit; solve B_full * theta_full = Pinj.
      2) Extract boundary angles theta_B in Y order restricted to boundary_idx_in_Y.
      3) Reduced DC: build Bred from Yeq_G1 and compute P_target = Bred * theta_B.
      4) Compute Pgen_assigned at boundary (pu) from relocation map (G2 positions).
      5) Set boundary loads L_new = Pgen_assigned - P_target  (net P = Pgen - L_new = P_target).

    Returns
    -------
    DCInversePF with fields described above.
    """
    # 1) Full network DC solve
    B_full = _build_B_from_Y(Y_full)
    Pinj = _gridcal_Pinj_pu(circuit, y_order_names)
    # choose a slack: the first boundary bus in Y order is sensible for alignment
    slack_y = int(boundary_idx_in_Y[0])
    theta_full = _dc_theta(B_full, Pinj, slack_y)

    # 2) boundary angles (aligned to Yeq_G1 order, which uses boundary_idx_in_Y order)
    theta_B = theta_full[np.asarray(boundary_idx_in_Y, dtype=int)]

    # 3) Reduced DC target injections
    Bred = _B_from_Yeq_G1(Yeq_G1)
    P_target = Bred @ theta_B  # P = B' * theta

    # 4) Aggregate relocated generator P at boundary (pu)
    # Map: G2 positions <-> Y order
    pos_map = {k: p for p, k in enumerate(retain2_idx_in_Y)}

    # gen_idx_in_G2 is in the same order as generators in GridCal (from our helper)
    gen_idx_in_Y, gen_objs = _gridcal_generator_bus_indices_in_Y_order(circuit, y_order_names)

    # Build array of generator P (pu) in same order as gen_idx_in_Y
    Sbase = _gridcal_system_base_MVA(circuit)
    Pg_pu = []
    for g in gen_objs:
        Pg = _get_float_attr(g, ["Pg", "P", "p", "p_set", "p_mw", "P_MW"], default=0.0)
        Pg_pu.append(Pg / max(Sbase, 1e-6))
    Pg_pu = np.asarray(Pg_pu, dtype=float)

    # Now map each generator's G2 position to boundary G2 position via relocation_map
    # and then to boundary index in G1 order.
    # boundary_idx_in_G2 is aligned with boundary_idx_in_Y ordering.
    boundary_pos_to_g1_idx = {pos: i for i, pos in enumerate(boundary_idx_in_G2)}  # G2 pos -> G1 idx
    Pgen_assigned = np.zeros(len(boundary_idx_in_Y), dtype=float)

    # Construct generator positions in G2, in the same order as gen_idx_in_Y/gen_objs
    gen_pos_in_G2 = []
    for y_idx in gen_idx_in_Y:
        gen_pos_in_G2.append(pos_map.get(y_idx, None))

    for g2_pos, pg in zip(gen_pos_in_G2, Pg_pu):
        if g2_pos is None:
            continue
        bpos_g2 = relocation_map_g2.get(g2_pos, None)
        if bpos_g2 is None:
            continue  # islanded or unreachable
        g1_idx = boundary_pos_to_g1_idx.get(bpos_g2, None)
        if g1_idx is None:
            continue
        Pgen_assigned[g1_idx] += pg

    # 5) boundary loads (pu) to set on reduced grid
    L_new = Pgen_assigned - np.asarray(P_target).ravel()

    return DCInversePF(
        theta_B=theta_B,
        Bred=Bred.tocsc(),
        P_target=np.asarray(P_target).ravel(),
        Pgen_assigned=Pgen_assigned,
        L_new=L_new,
    )


# -----------------------------
# Top-level: full reduction API
# -----------------------------

@dataclass
class ReductionOutputs:
    # Structural reduced grid (boundary-only)
    Yeq_G1: sp.csr_matrix
    boundary_idx_in_Y: List[int]
    boundary_names: List[str]
    # Reduced generator model (boundary ∪ gens)
    Yeq_G2: sp.csr_matrix
    retain2_idx_in_Y: List[int]
    retain2_names: List[str]
    gen_idx_in_G2: List[int]
    boundary_idx_in_G2: List[int]
    relocation_map: Dict[int, int]
    # Equivalents from G1 using 10× rule
    equiv_G1: EquivElements
    # Optional DC inverse PF result
    dc_fit: Optional[DCInversePF]


def reduce_with_gridcal(circuit,
                        boundary_bus_names: Iterable[str],
                        mode: str = "ac",
                        do_dc_inverse_pf: bool = True) -> ReductionOutputs:
    """
    Full pipeline using GridCal:
      1) Build Y from circuit
      2) G1 = Ward(Y, retain = boundary)
      3) G2 = Ward(Y, retain = boundary ∪ generator buses)
      4) Relocate generators by electrical distance in G2
      5) Extract equivalents from G1 with 10× original-reactance pruning
      6) (Optional) DC inverse PF redistribution -> boundary loads to set after relocation

    Returns ReductionOutputs with all artifacts.
    """
    # 1) Build Y and names
    Y, y_order_names = _gridcal_get_Y_and_names(circuit)

    # boundary indices in Y order
    boundary_names = list(boundary_bus_names)
    boundary_idx_in_Y = _gridcal_indices_from_names(y_order_names, boundary_names)

    # 2) G1: boundary-only retained
    Yeq_G1 = ward_reduce(Y, boundary_idx_in_Y)

    # 3) G2: boundary ∪ generator retained
    gen_idx_in_Y, gen_objs = _gridcal_generator_bus_indices_in_Y_order(circuit, y_order_names)
    retain2_in_Y = sorted(set(boundary_idx_in_Y).union(gen_idx_in_Y))
    Yeq_G2 = ward_reduce(Y, retain2_in_Y)

    # positions in G2
    pos_map = {k: p for p, k in enumerate(retain2_in_Y)}
    boundary_idx_in_G2 = [pos_map[k] for k in boundary_idx_in_Y]
    gen_idx_in_G2 = [pos_map[k] for k in gen_idx_in_Y if k in pos_map]
    retain2_names = [y_order_names[k] for k in retain2_in_Y]

    # 4) Relocation on G2
    relocation_map = relocate_generators(Yeq_G2, gen_idx_in_G2, boundary_idx_in_G2, mode=mode)

    # 5) Equivalents from G1 with 10× rule based on ORIGINAL Y
    equiv_G1 = y_to_equivalents_10x_rule(Yeq_G1, Y)

    # 6) DC inverse PF redistribution (optional)
    dc_fit: Optional[DCInversePF] = None
    if do_dc_inverse_pf:
        dc_fit = dc_inverse_pf_redistribution(
            circuit=circuit,
            Y_full=Y,
            Yeq_G1=Yeq_G1,
            y_order_names=y_order_names,
            boundary_idx_in_Y=boundary_idx_in_Y,
            retain2_idx_in_Y=retain2_in_Y,
            boundary_idx_in_G2=boundary_idx_in_G2,
            gen_idx_in_G2=gen_idx_in_G2,
            relocation_map_g2=relocation_map,
        )

    return ReductionOutputs(
        Yeq_G1=Yeq_G1,
        boundary_idx_in_Y=boundary_idx_in_Y,
        boundary_names=boundary_names,
        Yeq_G2=Yeq_G2,
        retain2_idx_in_Y=retain2_in_Y,
        retain2_names=retain2_names,
        gen_idx_in_G2=gen_idx_in_G2,
        boundary_idx_in_G2=boundary_idx_in_G2,
        relocation_map=relocation_map,
        equiv_G1=equiv_G1,
        dc_fit=dc_fit,
    )
