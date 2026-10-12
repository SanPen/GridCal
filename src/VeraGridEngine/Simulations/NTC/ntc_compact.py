# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Physical corrective states with a shared passive network factorization.

A removed branch is replaced by an unknown compensation transaction. Its
flow equals that transaction. 
Only converter powers, compensation transactions and component reference shifts
are optimization variables. Bus potentials and branch flows are expressions.
This file allows us to compute contingency NTC cases with Pmode3 VSCs much faster.
"""
from __future__ import annotations

from itertools import product
from enum import Enum
from typing import Callable, Iterator, Protocol, cast
import numpy as np
import networkx as nx
from scipy.sparse import coo_matrix, csc_matrix
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import SuperLU, splu

from VeraGridEngine.enumerations import ConverterControlType as Control, HvdcControlType
from VeraGridEngine.basic_structures import BoolVec, IntVec, Mat, ObjMat, ObjVec, Vec, Logger
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.DataStructures.passive_branch_data import PassiveBranchData
from VeraGridEngine.DataStructures.vsc_data import VscData
from VeraGridEngine.DataStructures.hvdc_data import HvdcData
from VeraGridEngine.Simulations.LinearFactors.linear_analysis import LinearMultiContingencies, LinearMultiContingency
from VeraGridEngine.Utils.MIP.selected_interface import LpModel, LpExp, LpVar

class BusVariables(Protocol):
    """Describe the bus arrays shared by standard and strict NTC results."""
    __slots__ = ()
    Pinj: ObjMat
    Va: ObjMat
    Vm: ObjMat


class ConverterVariables(Protocol):
    """Describe converter powers supplied by either NTC formulation."""
    __slots__ = ()
    flows: ObjMat


class BranchVariables(Protocol):
    """Describe branch arrays and the existing result-registration interface."""
    __slots__ = ()
    flows: ObjMat
    monitor_logic: BoolVec
    contingency_rates: Mat
    tap_angles: ObjMat

    def add_contingency_flow(self: BranchVariables, t: int, m: int, c: int,
                             flow_var: float | LpVar | LpExp,
                             neg_slack: float | LpVar, pos_slack: float | LpVar) -> None:
        """Register an admitted branch constraint in the formulation's results.

        :param t: Result time index.
        :param m: Monitored branch index.
        :param c: Contingency group index.
        :param flow_var: Physical branch-flow expression.
        :param neg_slack: Lower-limit relaxation.
        :param pos_slack: Upper-limit relaxation.
        :return: None.
        """
        ...


class BaseVariables(Protocol):
    """Describe the existing standard/strict containers without circular imports."""
    __slots__ = ()
    bus_vars: BusVariables
    branch_vars: BranchVariables
    vsc_vars: ConverterVariables
    hvdc_vars: ConverterVariables


class SolverProgress:
    """Adapt the existing GUI callback API at the boundary of this module."""
    __slots__ = ('_callback',)

    def __init__(self: SolverProgress, callback: Callable[[str], None] | None) -> None:
        """Keep the legacy callback behind an explicit reporting interface.

        :param callback: Existing GUI text callback, or None for silent operation.
        :return: None.
        """
        self._callback: Callable[[str], None] | None = callback

    def report(self: SolverProgress, message: str) -> None:
        """Send progress to the GUI when a receiver exists.

        :param message: Description of the current optimization stage.
        :return: None.
        """
        if self._callback is not None:
            self._callback(message)
        else:
            pass  # Headless computations do not require a progress receiver.


class OperatingPoint:
    """Store named operating-point arrays instead of string-keyed dictionaries."""
    __slots__ = ('q', 'flow', 'inj', 'potential')

    def __init__(self: OperatingPoint, q: Vec | ObjVec, flow: Vec | ObjVec,
                 inj: Vec | ObjVec, potential: Vec | ObjVec) -> None:
        """Retain arrays whose lengths are fixed by the compiled circuit.

        :param q: Converter active powers in per unit.
        :param flow: Passive branch powers in per unit.
        :param inj: Non-converter bus injections in per unit.
        :param potential: AC angles and DC voltage magnitudes.
        :return: None.
        """
        self.q: Vec | ObjVec = q
        self.flow: Vec | ObjVec = flow
        self.inj: Vec | ObjVec = inj
        self.potential: Vec | ObjVec = potential

    def evaluate(self: OperatingPoint, prob: LpModel) -> OperatingPoint:
        """Extract a numerical snapshot without modifying the symbolic arrays.

        :param prob: Solver owning the expressions.
        :return: Independent numerical operating point.
        """
        q: Vec = evaluate_vector(prob, self.q)
        flow: Vec = evaluate_vector(prob, self.flow)
        inj: Vec = evaluate_vector(prob, self.inj)
        potential: Vec = evaluate_vector(prob, self.potential)
        return OperatingPoint(q=q, flow=flow, inj=inj, potential=potential)


def evaluate_vector(prob: LpModel, values: Vec | ObjVec) -> Vec:
    """Extract solver values into a preallocated numerical vector.

    :param prob: Solver owning the expressions.
    :param values: Numerical constants or solver expressions.
    :return: Numerical values in the same order.
    """
    result: Vec = np.empty(len(values), dtype=float)
    index: int
    for index in range(len(values)):
        result[index] = prob.get_value(values[index])
    return result


class DroopRegion(Enum):
    """Identify the three physical regions of the clipped droop law."""
    __slots__ = ()
    Linear = 0
    Lower = -1
    Upper = 1


def linear_dot(prob: LpModel, coefficients: Vec, values: Vec | ObjVec) -> float | LpExp:
    """Evaluate a numeric dot product or construct its solver expression.

    :param prob: Model owning symbolic expressions.
    :param coefficients: Numerical response coefficients.
    :param values: Fixed-length numerical or symbolic vector.
    :return: Numerical dot product or linear expression without zero terms.
    """
    if values.dtype == object:
        nonzero: IntVec = np.flatnonzero(coefficients)
        terms: ObjVec = np.empty(len(nonzero), dtype=object)
        index: int
        for index in range(len(nonzero)):
            column: int = int(nonzero[index])
            terms[index] = float(coefficients[column]) * values[column]
        return prob.sum(terms)
    else:
        return float(np.dot(coefficients, values))


def add_clipped_flow(prob: LpModel,
                     flow: float | LpVar | LpExp,
                     demand: float | LpVar | LpExp,
                     rate: float,
                     lower: float,
                     upper: float,
                     name: str) -> None:
    """Exact clipped affine law, using at most two binary variables.

    Bounds are bounds on the unclipped power, not a guessed multiple of the
    device rating, as before with the M factor.
    The formulation also supports negative and zero droop.

    :param prob: Solver model owning the symbolic expressions.
    :param flow: Branch or converter active-power expression.
    :param demand: Unclipped affine droop demand.
    :param rate: Nonnegative saturation rating in per unit.
    :param lower: Lower bound on the unclipped demand.
    :param upper: Upper bound on the unclipped demand.
    :param name: Unique prefix for solver variables and constraints.
    :return: None.
    """
    if rate <= 0:
        prob.add_cst(flow == 0.0, name=name + '_zero')
    elif upper <= -rate:
        prob.add_cst(flow == -rate, name=name + '_lower')
    elif lower >= rate:
        prob.add_cst(flow == rate, name=name + '_upper')
    else:
        binaries: ObjVec = np.empty(2, dtype=object)
        binary_count: int = 0
        if upper > rate:
            z: LpVar = prob.add_int(lb=0, ub=1, name=name + '_zu')
            up: float | LpVar = prob.add_var(lb=0, ub=upper - rate, name=name + '_up')
            prob.add_cst(up <= (upper - rate) * z, name=name + '_up_bound')
            prob.add_cst(flow >= rate - 2 * rate * (1 - z), name=name + '_up_flow')
            binaries[binary_count] = z
            binary_count += 1
        else:
            up = 0.0
        if lower < -rate:
            z = prob.add_int(lb=0, ub=1, name=name + '_zd')
            dn: float | LpVar = prob.add_var(lb=0, ub=-rate - lower, name=name + '_dn')
            prob.add_cst(dn <= (-rate - lower) * z, name=name + '_dn_bound')
            prob.add_cst(flow <= -rate + 2 * rate * (1 - z), name=name + '_dn_flow')
            binaries[binary_count] = z
            binary_count += 1
        else:
            dn = 0.0
        if binary_count == 2:
            prob.add_cst(prob.sum(binaries) <= 1, name=name + '_one_region')
        else:
            pass  # One saturation binary cannot select conflicting regions.
        prob.add_cst(flow == demand - up + dn, name=name + '_law')


class Converter:
    """Hold one converter's fixed-size post-contingency control data."""
    __slots__ = ('active', 'rate', 'fixed', 'voltage', 'droop')

    def __init__(self: Converter, active: bool, rate: float) -> None:
        """Initialize a converter before applying its specific control law.

        :param active: Whether the converter survives the contingency.
        :param rate: Effective active-power rating in per unit.
        :return: None.
        """
        self.active: bool = active
        self.rate: float = rate
        self.fixed: float | None = None
        self.voltage: tuple[int, float] | None = None
        self.droop: tuple[int, int, float, float] | None = None


class PassiveResponse:
    """The same lossless AC/DC branch equations as the NTC optimization."""
    __slots__ = (
        'f',
        't',
        'b',
        'A',
        'labels',
        'refs',
        'keep',
        'lu',
        'converter_f',
        'converter_t',
        'Zc',
        'component_c',
        'lower',
        'upper',
        'slacks',
        'has_slack',
        'live',
        'tin',
        'bridges',
    )

    def __init__(self: PassiveResponse, nc: NumericalCircuit) -> None:
        """Factor the passive network once and identify exact bridge responses.

        :param nc: Compiled numerical circuit for the current time step.
        :return: None.
        """
        k: int
        root: int
        slack: int
        # Match the lossless NTC branch equations before factoring each connected island.
        bd: PassiveBranchData = nc.passive_branch_data
        n: int = nc.nbus
        m: int = nc.nbr
        self.f: IntVec = bd.F
        self.t: IntVec = bd.T
        x: Vec = np.where(bd.dc, bd.R, bd.X)
        self.b: Vec = np.zeros(m)
        live: IntVec = np.flatnonzero(bd.active)
        self.live: IntVec = live
        self.b[live] = np.divide(1., x[live], out=np.full(len(live), 1e-6), where=x[live] != 0)
        self.A: csc_matrix = coo_matrix((np.r_[np.ones(len(live)), -np.ones(len(live))],
                             (np.r_[live, live], np.r_[self.f[live], self.t[live]])),
                            shape=(m, n)).tocsc()
        adjacency: csc_matrix = coo_matrix((np.ones(2 * len(live)),
                                 (np.r_[self.f[live], self.t[live]], np.r_[self.t[live], self.f[live]])),
                                shape=(n, n)).tocsc()
        components: tuple[int, IntVec] = connected_components(adjacency, directed=False)
        count: int = components[0]
        self.labels: IntVec = components[1]
        self.refs: IntVec = np.full(count, n, dtype=int)
        np.minimum.at(self.refs, self.labels, np.arange(n))
        # The reference bus absorbs whatever imbalance a contingency leaves in its component.
        self.slacks: IntVec = nc.get_simulation_indices().vd
        self.has_slack: BoolVec = np.zeros(count, dtype=bool)
        for slack in self.slacks:
            if nc.bus_data.is_dc[slack]:
                pass  # DC voltage references belong to converter controls.
            else:
                self.refs[self.labels[slack]] = slack
                self.has_slack[self.labels[slack]] = True
        self.keep: IntVec = np.setdiff1d(np.arange(n), self.refs)
        B: csc_matrix = coo_matrix((np.r_[self.b[live], self.b[live], -self.b[live], -self.b[live]],
                        (np.r_[self.f[live], self.t[live], self.f[live], self.t[live]],
                         np.r_[self.f[live], self.t[live], self.t[live], self.f[live]])),
                       shape=(n, n)).tocsc()
        if len(self.keep):
            self.lu: SuperLU | None = splu(B[self.keep][:, self.keep])
        else:
            self.lu = None
        # Converter transactions share the same factorization for every outage.
        converter_incidence: Mat = np.zeros((n, nc.nvsc + nc.nhvdc))
        self.converter_f: IntVec = np.r_[nc.vsc_data.F, nc.hvdc_data.F]
        self.converter_t: IntVec = np.r_[nc.vsc_data.T, nc.hvdc_data.T]
        converter_indices: IntVec = np.arange(nc.nvsc + nc.nhvdc)
        converter_incidence[self.converter_f, converter_indices] -= 1.
        converter_incidence[self.converter_t, converter_indices] += 1.
        self.Zc: Mat = self.solve(converter_incidence)
        self.component_c: Mat = np.zeros((count, converter_incidence.shape[1]))
        np.add.at(self.component_c, self.labels, converter_incidence)
        self.lower: Vec = np.where(nc.bus_data.is_dc, nc.bus_data.Vmin, nc.bus_data.angle_min)
        self.upper: Vec = np.where(nc.bus_data.is_dc, nc.bus_data.Vmax, nc.bus_data.angle_max)
        # Graph bridges have exact integer transfer factors
        graph: nx.MultiGraph = nx.MultiGraph()
        graph.add_nodes_from(range(n))
        for k in live:
            graph.add_edge(int(self.f[k]), int(self.t[k]), key=int(k))
        self.tin: IntVec = np.full(n, -1, dtype=int)
        tout: IntVec = np.zeros(n, dtype=int)
        clock: int = 0
        # Each node is popped once, and each undirected edge is examined at
        # most twice across all components
        max_traversal_steps: int = graph.number_of_nodes() + 2 * graph.number_of_edges()
        traversal_steps: int = 0
        stack_nodes: IntVec = np.empty(n, dtype=int)
        stack_iterators: ObjVec = np.empty(n, dtype=object)
        for root in self.refs:
            self.tin[root] = clock
            clock += 1
            stack_size: int = 1
            stack_nodes[0] = root
            stack_iterators[0] = iter(graph[root])
            while stack_size > 0 and traversal_steps < max_traversal_steps:
                traversal_steps += 1
                node: int = int(stack_nodes[stack_size - 1])
                neighbors: Iterator[int] = cast(Iterator[int], stack_iterators[stack_size - 1])
                other: int | None = next(neighbors, None)
                if other is None:
                    tout[node] = clock
                    stack_size -= 1
                elif self.tin[other] < 0:
                    self.tin[other] = clock
                    clock += 1
                    stack_nodes[stack_size] = other
                    stack_iterators[stack_size] = iter(graph[other])
                    stack_size += 1
                else:
                    pass  # The neighbor was already visited; do not revisit its subtree.
            if stack_size > 0:
                raise RuntimeError('NTC graph traversal exceeded its graph-size iteration bound')
            else:
                pass  # The component traversal finished within the graph-size bound.
        self.bridges: dict[int, tuple[int, int, float]] = dict()
        bridge_pair: tuple[int, int]
        for bridge_pair in nx.bridges(graph):
            f: int = bridge_pair[0]
            t: int = bridge_pair[1]
            k = next(iter(graph[f][t]))
            if self.tin[f] > self.tin[t]:
                child: int = f
            else:
                child = t
            if child == self.f[k]:
                sense: float = 1.
            else:
                sense = -1.
            self.bridges[k] = (self.tin[child], tout[child], sense)

    def solve(self: PassiveResponse, rhs: Vec | Mat) -> Vec | Mat:
        """Solve passive-network responses while keeping component references fixed.

        :param rhs: Right-hand side vector or matrix to solve against the passive network.
        :return: Passive-network solution with zero reference entries.
        """
        result: Vec | Mat = np.zeros_like(rhs, dtype=float)
        if self.lu is not None:
            result[self.keep] = self.lu.solve(np.asarray(rhs[self.keep], dtype=float))
        else:
            pass  # A network of isolated references has a zero passive response.
        return result

    def cut_injections(self: PassiveResponse, branch: int, buses: IntVec) -> Vec:
        """Flow on a bridge per unit injection balanced at its component root.

        :param branch: Passive branch index in the compiled circuit.
        :param buses: Bus indices to evaluate or constrain.
        :return: Numerical response vector.
        """
        bridge: tuple[int, int, float] | None = self.bridges.get(branch, None)
        if bridge is not None:
            lo: int = bridge[0]
            hi: int = bridge[1]
            sense: float = bridge[2]
            return sense * ((self.tin[buses] >= lo) & (self.tin[buses] < hi))
        else:
            return np.zeros(len(buses), dtype=float)

    def post_outage_labels(self: PassiveResponse, out: IntVec) -> IntVec:
        """Label the connected parts of the passive network once some branches are removed.

        :param out: In service passive branch indices tripped by the contingency.
        :return: Part label per bus after the outage.
        """
        if len(out) == 0:
            return self.labels
        elif len(out) == 1:
            bridge: tuple[int, int, float] | None = self.bridges.get(int(out[0]), None)
            if bridge is None:
                # one branch that is not a bridge cannot split its component
                return self.labels
            else:
                # the side of the bridge away from the reference becomes a part of its own
                split: IntVec = self.labels.copy()
                split[(self.tin >= bridge[0]) & (self.tin < bridge[1])] = len(self.refs)
                return split
        else:
            # several branches can form a cut that none of them forms alone, so rebuild the graph
            remaining: IntVec = np.setdiff1d(self.live, out)
            n: int = len(self.labels)
            adjacency: csc_matrix = coo_matrix(
                (np.ones(2 * len(remaining)),
                 (np.r_[self.f[remaining], self.t[remaining]], np.r_[self.t[remaining], self.f[remaining]])),
                shape=(n, n)).tocsc()
            components: tuple[int, IntVec] = connected_components(adjacency, directed=False)
            return components[1]


class CompactState:
    """One small corrective block with no bus or branch optimization variable arrays."""
    __slots__ = (
        'owner',
        'index',
        'out',
        'out_mask',
        'Zo',
        'inj_bus',
        'inj_factor',
        'Zi',
        'qn',
        'on',
        'n',
        'converters',
        'active',
        'absorbed',
        'droops',
        'variables',
        'exact',
        'rows',
        'bus_rows',
    )

    def __init__(self: CompactState, owner: CompactContingencies, index: int) -> None:
        """Prepare one compact contingency using shared factors and fixed-size arrays.

        :param owner: Coordinator providing shared network responses and the solver.
        :param index: Contingency group index.
        :return: None.
        """
        k: int
        sweep: int
        self.owner: CompactContingencies = owner
        self.index: int = index
        nc: NumericalCircuit = owner.nc
        net: PassiveResponse = owner.net
        event: LinearMultiContingency = owner.contingencies.multi_contingencies[index]
        self.out: IntVec = np.unique(event.branch_indices[nc.passive_branch_data.active[event.branch_indices].astype(bool)])
        self.out_mask: BoolVec = np.zeros(nc.nbr, dtype=bool)
        self.out_mask[self.out] = True
        self.Zo: Mat = net.solve(net.A[self.out].T.toarray())
        # Combine repeated injection changes multiplicatively, preserving input order.
        unique_buses: tuple[IntVec, IntVec, IntVec] = np.unique(event.bus_indices, return_index=True, return_inverse=True)
        first_occurrences: IntVec = unique_buses[1]
        inverse_indices: IntVec = unique_buses[2]
        multipliers: Vec = np.ones(len(unique_buses[0]), dtype=float)
        np.multiply.at(multipliers, inverse_indices, 1. + event.injections_factor)
        bus_order: IntVec = np.argsort(first_occurrences)
        self.inj_bus: IntVec = unique_buses[0][bus_order]
        self.inj_factor: Vec = multipliers[bus_order] - 1.
        rhs: Mat = np.zeros((nc.nbus, len(self.inj_bus)))
        rhs[self.inj_bus, np.arange(len(self.inj_bus))] = self.inj_factor
        self.Zi: Mat = net.solve(rhs)
        self.qn: int = nc.nvsc + nc.nhvdc
        self.on: int = len(self.out)
        self.n: int = self.qn + self.on + len(net.refs)
        self.converters: ObjVec = owner.converter_data(self.out, event.vsc_indices, event.hvdc_indices)
        item: Converter

        # Which buses remain connected to each other once the tripped branches are gone.
        post: IntVec = net.post_outage_labels(self.out)
        post_count: int = int(post.max()) + 1 if len(post) > 0 else 0

        # A converter left alone on its DC side cannot move power. 
        self.active: BoolVec = np.zeros(self.qn, dtype=bool)
        for k in range(self.qn):
            item = cast(Converter, self.converters[k])
            self.active[k] = item.active
        dc_from: BoolVec = nc.bus_data.is_dc[net.converter_f].astype(bool)
        dc_to: BoolVec = nc.bus_data.is_dc[net.converter_t].astype(bool)
        for sweep in range(self.qn):
            attached: IntVec = np.zeros(post_count, dtype=int)
            np.add.at(attached, post[net.converter_f[self.active & dc_from]], 1)
            np.add.at(attached, post[net.converter_t[self.active & dc_to]], 1)
            stranded: BoolVec = self.active & ((dc_from & (attached[post[net.converter_f]] == 1))
                                               | (dc_to & (attached[post[net.converter_t]] == 1)))
            self.active[stranded] = False
        for k in range(self.qn):
            item = cast(Converter, self.converters[k])
            item.active = bool(self.active[k])

        # Parts that a converter free to change its power still links can exchange power, so they
        # can be rebalanced. Instead, parts without such a link cannot.
        linked: IntVec = np.arange(post_count)
        for k in range(self.qn):
            item = cast(Converter, self.converters[k])
            if item.active and item.fixed is None:
                group_from: int = int(linked[post[net.converter_f[k]]])
                group_to: int = int(linked[post[net.converter_t[k]]])
                if group_from != group_to:
                    linked[linked == group_to] = group_from
                else:
                    pass  # both terminals already belong to the same linked group
            else:
                pass  # tripped, stranded or fixed converters cannot rebalance anything

        # A tripped branch whose ends are now in different parts belongs to a cut. If converters
        # can still feed the separated part, the exact outage applies and they rebalance it.
        part_from: IntVec = post[net.f[self.out]]
        part_to: IntVec = post[net.t[self.out]]
        in_cut: BoolVec = part_from != part_to
        if owner.absorb_islands:
            # feasibility retry: absorb every cut, whether or not converters could rebalance it
            self.absorbed: BoolVec = in_cut
        else:
            self.absorbed = in_cut & (linked[part_from] != linked[part_to])

        droop_mask: BoolVec = np.zeros(self.qn, dtype=bool)
        for k in range(self.qn):
            item = cast(Converter, self.converters[k])
            droop_mask[k] = item.active and item.droop is not None
        self.droops: IntVec = np.flatnonzero(droop_mask)
        self.variables: ObjVec | None = None
        self.exact: bool = False
        self.rows: BoolVec = np.zeros(nc.nbr, dtype=bool)
        self.bus_rows: BoolVec = np.zeros(nc.nbus, dtype=bool)

    def potential_row(self: CompactState, bus: int) -> Vec:
        """Build the bus-potential coefficients of the compact unknowns.

        :param bus: Compiled bus index.
        :return: Numerical response vector.
        """
        row: Vec = np.zeros(self.n)
        row[:self.qn] = self.owner.net.Zc[bus]
        row[self.qn:self.qn + self.on] = self.Zo[bus]
        row[self.qn + self.on + self.owner.net.labels[bus]] = 1.
        return row

    def flow_row(self: CompactState, branch: int) -> Vec:
        """Build physical branch-flow coefficients, including exact bridge cuts.

        :param branch: Passive branch index in the compiled circuit.
        :return: Numerical response vector.
        """
        net: PassiveResponse = self.owner.net
        if branch in net.bridges:
            row: Vec = np.zeros(self.n)
            row[:self.qn] = -(net.cut_injections(branch, net.converter_f) - net.cut_injections(branch, net.converter_t))
            row[self.qn:self.qn + self.on] = (net.cut_injections(branch, net.f[self.out]) - net.cut_injections(branch, net.t[self.out]))
            return row
        else:
            return net.b[branch] * (self.potential_row(net.f[branch]) - self.potential_row(net.t[branch]))

    def offset(self: CompactState, base: OperatingPoint, bus: int) -> float | LpExp:
        """Calculate the potential offset caused by base converter powers and injection changes.

        :param base: Symbolic or numerical base operating point.
        :param bus: Compiled bus index.
        :return: Numerical constant or symbolic linear expression.
        """
        net: PassiveResponse = self.owner.net
        return (-linear_dot(self.owner.prob, net.Zc[bus], base.q)
                + linear_dot(self.owner.prob, self.Zi[bus], base.inj[self.inj_bus]))

    def flow_constant(self: CompactState, base: OperatingPoint, branch: int) -> float | LpVar | LpExp:
        """Calculate the affine branch-flow term inherited from the base state.

        :param base: Symbolic or numerical base operating point.
        :param branch: Passive branch index in the compiled circuit.
        :return: Affine flow constant.
        """
        net: PassiveResponse = self.owner.net
        if branch in net.bridges:
            return (base.flow[branch] - linear_dot(self.owner.prob, self.flow_row(branch)[:self.qn], base.q)
                    + linear_dot(self.owner.prob, net.cut_injections(branch, self.inj_bus) * self.inj_factor,
                                     base.inj[self.inj_bus]))
        else:
            return base.flow[branch] + net.b[branch] * (
                self.offset(base, net.f[branch]) - self.offset(base, net.t[branch]))

    def equations(self: CompactState, base: OperatingPoint) -> tuple[Mat, ObjVec]:
        """Build fixed-capacity component, outage and controller balance rows.

        :param base: Numerical or symbolic base operating point.
        :return: Coefficient matrix and matching right-hand side, trimmed to used rows.
        """
        bus: int
        component: int
        j: int
        k: int
        nc: NumericalCircuit = self.owner.nc
        net: PassiveResponse = self.owner.net
        # Two controller equations per converter is an upper bound; views expose
        # only used rows without reallocating or growing the underlying arrays.
        capacity: int = len(net.refs) + self.on + len(net.slacks) + 2 * self.qn
        rows: Mat = np.zeros((capacity, self.n), dtype=float)
        rhs: ObjVec = np.empty(capacity, dtype=object)
        row_index: int = 0
        for component in range(len(net.refs)):
            coefficients: Vec = net.component_c[component]
            rows[row_index, :self.qn] = coefficients
            if net.has_slack[component]:
                # The slack of this component picks up a lost injection and the power of a lost
                # converter, so only the surviving converters must keep their net exchange with it.
                rhs[row_index] = linear_dot(self.owner.prob, coefficients * self.active, base.q)
            else:
                # Without a slack (a DC grid) the converters must restore the balance themselves.
                changed: Vec = self.inj_factor * (net.labels[self.inj_bus] == component)
                rhs[row_index] = (linear_dot(self.owner.prob, coefficients, base.q)
                                  - linear_dot(self.owner.prob, changed, base.inj[self.inj_bus]))
            row_index += 1
        for j in range(self.on):
            branch: int = int(self.out[j])
            if self.absorbed[j]:
                # Cut that no converter can rebalance: no transaction, so nothing else moves.
                rows[row_index, self.qn + j] = 1.
                rhs[row_index] = 0.
            else:
                # Compensation flow equals the flow on the removed branch
                rows[row_index] = self.flow_row(branch)
                rows[row_index, self.qn + j] -= 1.
                rhs[row_index] = -self.flow_constant(base, branch)
            row_index += 1
        for bus in net.slacks:
            if not nc.bus_data.is_dc[bus]:
                rows[row_index] = self.potential_row(bus)
                rhs[row_index] = (float(np.angle(nc.bus_data.Vbus[bus]))
                                  - base.potential[bus] - self.offset(base, bus))
                row_index += 1
            else:
                pass  # DC voltage references belong to converter controls.
        for k in range(self.qn):
            item: Converter = cast(Converter, self.converters[k])
            if not item.active or item.fixed is not None:
                rows[row_index, k] = 1.
                if item.active:
                    rhs[row_index] = item.fixed
                else:
                    rhs[row_index] = 0.
                row_index += 1
            else:
                pass  # Dispatchable powers are determined by the remaining equations.
            if item.active and item.voltage is not None:
                bus = item.voltage[0]
                voltage: float = item.voltage[1]
                rows[row_index] = self.potential_row(bus)
                rhs[row_index] = voltage - base.potential[bus] - self.offset(base, bus)
                row_index += 1
            else:
                pass  # No DC voltage equation is requested by this controller.
        return rows[:row_index], rhs[:row_index]

    def demand(self: CompactState, base: OperatingPoint, k: int) -> tuple[Vec, float | LpVar | LpExp]:
        """Construct the affine unclipped demand of one droop-controlled converter.

        :param base: Symbolic or numerical base operating point.
        :param k: Converter index in the combined VSC/HVDC ordering.
        :return: Demand coefficients and affine constant.
        """
        item: Converter = cast(Converter, self.converters[k])
        droop_control: tuple[int, int, float, float] = cast(tuple[int, int, float, float], item.droop)
        ref: int = droop_control[0]
        local: int = droop_control[1]
        p0: float = droop_control[2]
        slope: float = droop_control[3]
        row: Vec = slope * (self.potential_row(ref) - self.potential_row(local))
        constant: float | LpVar | LpExp = p0 + slope * ((base.potential[ref] + self.offset(base, ref)) - (base.potential[local] + self.offset(base, local)))
        return row, constant

    def numeric(self: CompactState, base: OperatingPoint) -> Vec | None:
        """Find a physical witness. Failure causes exact master admission.

        :param base: Symbolic or numerical base operating point.
        :return: Physical state, or None when certification requires an exact block.
        """
        k: int
        initial: Vec = np.r_[base.q, np.zeros(self.n - self.qn)]
        if self.variables is not None:
            initial = evaluate_vector(self.owner.prob, self.variables)
            error: float = 0.0
            for k in self.droops:
                item: Converter = cast(Converter, self.converters[k])
                demand: tuple[Vec, float | LpVar | LpExp] = self.demand(base, k)
                row: Vec = demand[0]
                constant: float = float(demand[1])
                expected: float = float(np.clip(constant + row @ initial, -item.rate, item.rate))
                error = max(error, abs(float(initial[k]) - expected))
            if error <= self.owner.mip_feasibility_tolerance:
                return initial
            elif self.exact:
                self.owner.logger.add_error('Solved corrective droop exceeds the physical tolerance',
                                            device=str(self.index), value=error * self.owner.nc.Sbase)
                return None
            else:
                return self._find_numeric_witness(base, initial)
        else:
            return self._find_numeric_witness(base, initial)

    def _find_numeric_witness(self: CompactState, base: OperatingPoint, initial: Vec) -> Vec | None:
        """Search a bounded set of exact droop regions without modifying the master.

        :param base: Numerical operating point to certify.
        :param initial: Initial converter powers and network reference shifts.
        :return: Best physical witness, or None when exact admission is needed.
        """
        j: int
        k: int
        if len(self.droops) > 5:
            return None
        else:
            equations: tuple[Mat, ObjVec] = self.equations(base)
            eq: Mat = equations[0]
            rhs: Vec = evaluate_vector(self.owner.prob, equations[1])
            base_rows: int = eq.shape[0]
            droop_count: int = len(self.droops)
            matrix: Mat = np.zeros((base_rows + droop_count, self.n), dtype=float)
            values: Vec = np.empty(base_rows + droop_count, dtype=float)
            matrix[:base_rows] = eq
            values[:base_rows] = rhs
            demand_rows: Mat = np.empty((droop_count, self.n), dtype=float)
            demand_constants: Vec = np.empty(droop_count, dtype=float)
            droop_rates: Vec = np.empty(droop_count, dtype=float)
            converter_rates: Vec = np.empty(self.qn, dtype=float)
            for k in range(self.qn):
                item: Converter = cast(Converter, self.converters[k])
                converter_rates[k] = item.rate
            # Only the droop rows vary between regions, so reuse every other row
            # and the small dense workspace across all candidate solves.
            for j in range(droop_count):
                k = int(self.droops[j])
                demand: tuple[Vec, float | LpVar | LpExp] = self.demand(base, k)
                demand_rows[j] = demand[0]
                demand_constants[j] = float(demand[1])
                droop_rates[j] = converter_rates[k]
            best: Vec | None = None
            best_score: float = np.inf
            region_combinations: Iterator[tuple[DroopRegion, ...]] = product(tuple(DroopRegion), repeat=droop_count)
            max_region_combinations: int = 3 ** droop_count
            region_index: int = 0
            while region_index < max_region_combinations and best_score != 0:
                regions: tuple[DroopRegion, ...] = next(region_combinations)
                region_index += 1
                matrix[base_rows:] = 0.
                for j in range(droop_count):
                    k = int(self.droops[j])
                    region: DroopRegion = regions[j]
                    matrix[base_rows + j, k] = 1.
                    if region == DroopRegion.Linear:
                        matrix[base_rows + j] -= demand_rows[j]
                        values[base_rows + j] = demand_constants[j]
                    elif region == DroopRegion.Lower:
                        values[base_rows + j] = -droop_rates[j]
                    else:
                        values[base_rows + j] = droop_rates[j]
                candidate: Vec = initial + np.linalg.lstsq(matrix, values - matrix @ initial, rcond=1e-11)[0]
                expected_droop: Vec = np.clip(demand_constants + demand_rows @ candidate, -droop_rates, droop_rates)
                if np.max(np.abs(matrix @ candidate - values), initial=0.) > 1e-7:
                    pass  # A candidate must satisfy the complete network balance.
                elif np.any(np.abs(candidate[:self.qn]) > converter_rates + 1e-7):
                    pass  # Corrective powers must stay inside converter ratings.
                elif np.any(np.abs(candidate[self.droops] - expected_droop) > 1e-7):
                    pass  # Region equations alone do not prove the clipped law.
                else:
                    evaluated_state: tuple[Vec, Vec] = self.evaluate(base, candidate)
                    potential: Vec = evaluated_state[0]
                    flow: Vec = evaluated_state[1]
                    violations: tuple[IntVec, IntVec] = self.violations(potential, flow)
                    score: int = len(violations[0]) + len(violations[1])
                    if score < best_score:
                        best = candidate
                        best_score = float(score)
                    else:
                        pass  # Keep the first witness with the same violation count.
            return best

    def evaluate(self: CompactState, base: OperatingPoint, value: Vec) -> tuple[Vec, Vec]:
        """Reconstruct physical bus potentials and branch powers from compact unknowns.

        :param base: Symbolic or numerical base operating point.
        :param value: Numerical corrective-state vector.
        :return: Post-contingency bus potentials and branch flows.
        """
        net: PassiveResponse = self.owner.net
        # Superpose controller changes, removed-branch transactions and island shifts.
        delta: Vec = (np.einsum('ij,j->i', net.Zc, value[:self.qn] - base.q)
                 + np.einsum('ij,j->i', self.Zo, value[self.qn:self.qn + self.on])
                 + value[self.qn + self.on:][net.labels])
        if len(self.inj_bus):
            delta += self.Zi @ base.inj[self.inj_bus]
        else:
            pass  # This outage leaves non-converter injections unchanged.
        potential: Vec = base.potential + delta
        flow: Vec = base.flow + net.b * (delta[net.f] - delta[net.t])
        flow[self.out] = 0.
        return potential, flow

    def violations(self: CompactState, potential: Vec, flow: Vec) -> tuple[IntVec, IntVec]:
        """Locate potential and monitored thermal-limit violations.

        :param potential: Post-contingency AC angles and DC voltages.
        :param flow: Post-contingency passive branch powers in per unit.
        :return: Violating bus and branch indices.
        """
        owner: CompactContingencies = self.owner
        net: PassiveResponse = self.owner.net
        buses: IntVec = np.flatnonzero((potential < net.lower - 1e-7) | (potential > net.upper + 1e-7))
        rows: IntVec = np.flatnonzero(owner.monitor & (np.abs(flow) > owner.rates + 1e-6))
        return buses, rows

    def admit(self: CompactState, buses: IntVec, rows: IntVec) -> int:
        """Add a compact controller block and new violated limits to the master model.

        :param buses: Bus indices to evaluate or constrain.
        :param rows: Passive branch indices requiring thermal constraints.
        :return: Number of newly admitted blocks and limit rows.
        """
        branch: int
        bus: int
        j: int
        k: int
        owner: CompactContingencies = self.owner
        prob: LpModel = self.owner.prob
        prefix: str = f'compact_{self.index}'
        base: OperatingPoint = owner.symbolic_base
        added: int = 0
        if self.variables is None:
            self.variables = np.empty(self.n, dtype=object)
            for k in range(self.qn):
                item: Converter = cast(Converter, self.converters[k])
                if item.active:
                    self.variables[k] = prob.add_var(lb=-item.rate, ub=item.rate, name=f'{prefix}_p_{k}')
                else:
                    self.variables[k] = 0.
            for j in range(self.on):
                self.variables[self.qn + j] = prob.add_var(
                    lb=-prob.INFINITY, ub=prob.INFINITY, name=f'{prefix}_out_{j}')
            for j in range(len(owner.net.refs)):
                self.variables[self.qn + self.on + j] = prob.add_var(
                    lb=-prob.INFINITY, ub=prob.INFINITY, name=f'{prefix}_ref_{j}')
            equations: tuple[Mat, ObjVec] = self.equations(base)
            A: Mat = equations[0]
            rhs: ObjVec = equations[1]
            for j in range(len(rhs)):
                row: Vec = A[j]
                value: float | LpVar | LpExp = rhs[j]
                prob.add_cst(linear_dot(owner.prob, row, self.variables) == value, name=f'{prefix}_balance_{j}')
            added += 1
        else:
            pass  # Reuse the compact variables and balance equations already admitted.
        if not self.exact:
            for k in self.droops:
                item = cast(Converter, self.converters[k])
                droop_demand: tuple[Vec, float | LpVar | LpExp] = self.demand(base, k)
                row = droop_demand[0]
                constant: float | LpVar | LpExp = droop_demand[1]
                droop_control: tuple[int, int, float, float] = cast(tuple[int, int, float, float], item.droop)
                ref: int = droop_control[0]
                local: int = droop_control[1]
                p0: float = droop_control[2]
                slope: float = droop_control[3]
                a: float = slope * (owner.net.lower[ref] - owner.net.upper[local])
                b: float = slope * (owner.net.upper[ref] - owner.net.lower[local])
                add_clipped_flow(prob, self.variables[k], constant + linear_dot(owner.prob, row, self.variables),
                                 item.rate, p0 + min(a, b), p0 + max(a, b), f'{prefix}_droop_{k}')
            self.exact = True
            added += 1
        else:
            pass  # The exact clipped controller equations are already present.
        for bus in buses:
            if not self.bus_rows[bus]:
                expression: float | LpVar | LpExp = (base.potential[bus] + self.offset(base, bus)) + linear_dot(owner.prob, self.potential_row(bus), self.variables)
                prob.add_cst(expression >= owner.net.lower[bus], name=f'{prefix}_vmin_{bus}')
                prob.add_cst(expression <= owner.net.upper[bus], name=f'{prefix}_vmax_{bus}')
                self.bus_rows[bus] = True
                added += 1
            else:
                pass  # The bus bounds are already represented in the master.
        for branch in rows:
            if not self.rows[branch] and not self.out_mask[branch]:
                expression = self.flow_constant(base, branch) + linear_dot(owner.prob, self.flow_row(branch), self.variables)
                if owner.strict:
                    up: float | LpVar = 0.0
                    dn: float | LpVar = 0.0
                else:
                    up = prob.add_var(lb=0, ub=prob.INFINITY, name=f'{prefix}_over_up_{branch}')
                    dn = prob.add_var(lb=0, ub=prob.INFINITY, name=f'{prefix}_over_dn_{branch}')
                    owner.objective += 1e4 * (up + dn)
                prob.add_cst(expression <= owner.rates[branch] + up, name=f'{prefix}_max_{branch}')
                prob.add_cst(expression >= -owner.rates[branch] - dn, name=f'{prefix}_min_{branch}')
                owner.base_vars.branch_vars.add_contingency_flow(t=0, m=int(branch), c=self.index,
                                                                 flow_var=expression, neg_slack=dn, pos_slack=up)
                self.rows[branch] = True
                added += 1
            else:
                pass  # Already monitored or outaged branches need no new thermal row.
        return added


class CompactContingencies:
    """Incrementally admit exact physical corrective states and violated limits."""
    __slots__ = (
        'nc',
        'base_vars',
        'contingencies',
        'prob',
        'logger',
        'strict',
        'mip_feasibility_tolerance',
        'vsc_control_lookup',
        'hvdc_control_lookup',
        'net',
        'rates',
        'monitor',
        'symbolic_base',
        'states',
        'witnesses',
        'objective',
        'final_base',
        'complete',
        'absorb_islands',
    )

    def __init__(self: CompactContingencies,
                 nc: NumericalCircuit,
                 base_vars: BaseVariables,
                 multi_contingencies: LinearMultiContingencies,
                 prob: LpModel,
                 logger: Logger,
                 strict: bool = False,
                 droop_tolerance_mw: float = 0.01,
                 absorb_islands: bool = False) -> None:
        """Initialize shared responses and fixed-capacity contingency bookkeeping.

        :param nc: Compiled numerical circuit for the current time step.
        :param base_vars: Existing standard or strict NTC variable containers.
        :param multi_contingencies: Selected and compiled contingency groups.
        :param prob: Solver model owning the symbolic expressions.
        :param logger: Destination for diagnostics and certification failures.
        :param strict: Enforce hard contingency limits instead of penalized overload slacks.
        :param droop_tolerance_mw: Solved droop-law tolerance in MW, defaults to 10 kW.
        :param absorb_islands: Absorb every part a contingency cuts off, even where converters could
                               rebalance it. Used only as the feasibility retry.
        :return: None.
        """
        hvdc_control: HvdcControlType
        vsc_control: Control
        self.absorb_islands: bool = absorb_islands
        self.nc: NumericalCircuit = nc
        self.base_vars: BaseVariables = base_vars
        self.contingencies: LinearMultiContingencies = multi_contingencies
        self.prob: LpModel = prob
        self.logger: Logger = logger
        self.strict: bool = strict
        self.mip_feasibility_tolerance: float = droop_tolerance_mw / nc.Sbase
        self.vsc_control_lookup: dict[int, Control] = dict()
        for vsc_control in Control:
            self.vsc_control_lookup[vsc_control.idx()] = vsc_control
        self.hvdc_control_lookup: dict[int, HvdcControlType] = dict()
        for hvdc_control in HvdcControlType:
            self.hvdc_control_lookup[hvdc_control.idx()] = hvdc_control
        self.net: PassiveResponse = PassiveResponse(nc)
        self.rates: Vec = nc.passive_branch_data.contingency_rates / nc.Sbase
        self.monitor: BoolVec = (nc.passive_branch_data.monitor_loading.astype(bool)
                        & (base_vars.branch_vars.monitor_logic[0].astype(bool)
                           | nc.passive_branch_data.dc.astype(bool)))
        base_vars.branch_vars.contingency_rates[0] = nc.passive_branch_data.contingency_rates
        self.symbolic_base: OperatingPoint = OperatingPoint(q=np.r_[base_vars.vsc_vars.flows[0], base_vars.hvdc_vars.flows[0]],
                                  flow=base_vars.branch_vars.flows[0], inj=base_vars.bus_vars.Pinj[0],
                                  potential=np.where(nc.bus_data.is_dc, base_vars.bus_vars.Vm[0], base_vars.bus_vars.Va[0]))
        self.states: ObjVec = np.empty(len(multi_contingencies.multi_contingencies), dtype=object)
        self.states.fill(None)
        self.witnesses: ObjVec = np.empty(len(multi_contingencies.multi_contingencies), dtype=object)
        self.witnesses.fill(None)
        self.objective: LpExp = prob.sum(np.empty(0, dtype=object))
        self.final_base: OperatingPoint | None = None
        self.complete: bool = False

    def converter_data(self: CompactContingencies, out: IntVec, vsc_out: IntVec, hvdc_out: IntVec) -> ObjVec:
        """Build surviving converter controls using hourly contingency ratings.

        :param out: Outaged passive branch indices.
        :param vsc_out: Outaged VSC indices.
        :param hvdc_out: Outaged standalone HVDC indices.
        :return: Fixed-size array of concrete converter control objects.
        """
        k: int
        nc: NumericalCircuit = self.nc
        bd: PassiveBranchData = nc.passive_branch_data
        vd: VscData = nc.vsc_data
        hd: HvdcData = nc.hvdc_data
        # A surviving converter is limited by the remaining incident DC capacity.
        active_dc: BoolVec = bd.active.astype(bool) & bd.dc.astype(bool)
        active_dc[out] = False
        dc_rate: Vec = np.zeros(nc.nbus)
        np.add.at(dc_rate, bd.F[active_dc], bd.contingency_rates[active_dc])
        np.add.at(dc_rate, bd.T[active_dc], bd.contingency_rates[active_dc])
        result: ObjVec = np.empty(nc.nvsc + nc.nhvdc, dtype=object)
        for k in range(nc.nvsc):
            active: bool = bool(vd.active[k] and k not in vsc_out)
            item: Converter = Converter(active=active, rate=vd.rates[k] / nc.Sbase)
            if active:
                c1: Control | None = self.vsc_control_lookup.get(int(vd.control1_int[k]), None)
                c2: Control | None = self.vsc_control_lookup.get(int(vd.control2_int[k]), None)
                if c1 == Control.Pdc_angle_droop and c2 == Control.Pac:
                    if dc_rate[vd.F[k]] > 0:
                        item.rate = min(item.rate, dc_rate[vd.F[k]] / nc.Sbase)
                    else:
                        pass  # Without a live incident DC rating, retain the converter rating.
                    if vd.control1_bus_idx[k] < 0:
                        item.fixed = vd.control2_val[k] / nc.Sbase
                    else:
                        item.droop = (int(vd.control1_bus_idx[k]), int(vd.T[k]),
                                      vd.control2_val[k] / nc.Sbase, vd.control1_val[k] * 57.295779513 / nc.Sbase)
                elif c1 == Control.Vm_dc or c2 == Control.Vm_dc:
                    if c1 == Control.Vm_dc:
                        value: float = vd.control1_val[k]
                    else:
                        value = vd.control2_val[k]

                    if value != 0:
                        item.voltage = (int(vd.F[k]), value)
                    else:
                        item.voltage = (int(vd.F[k]), 1.)

                    if c2 == Control.Vm_ac:
                        item.fixed = 0.
                    else:
                        pass  # The remaining active power follows the network balance.
                elif c1 == Control.Pdc and c2 == Control.Vm_ac:
                    item.fixed = float(np.clip(vd.control1_val[k] / nc.Sbase, -item.rate, item.rate))
                else:
                    pass  # The remaining control combination leaves active power dispatchable.
            else:
                pass  # An outaged converter is fixed to zero by the balance equations.
            result[k] = item
        for k in range(nc.nhvdc):
            item = Converter(active=bool(hd.active[k] and k not in hvdc_out), rate=hd.rates[k] / nc.Sbase)
            if item.active:
                hvdc_control: HvdcControlType | None = self.hvdc_control_lookup.get(int(hd.control_mode_int[k]), None)
                if hvdc_control == HvdcControlType.type_0_free:
                    item.droop = (int(hd.F[k]), int(hd.T[k]), hd.Pset[k] / nc.Sbase,
                                  hd.get_angle_droop_in_pu_rad_at(k, nc.Sbase))
                elif not hd.dispatchable[k]:
                    item.fixed = float(np.clip(hd.Pset[k] / nc.Sbase, -item.rate, item.rate))
                else:
                    pass  # A dispatchable Pmode1 HVDC retains corrective power freedom.
            else:
                pass  # An outaged HVDC is fixed to zero by the balance equations.
            result[nc.nvsc + k] = item
        return result

    def solve(self: CompactContingencies,
              objective: float | LpVar | LpExp,
              status: int,
              batch_size: int = 8,
              robust: bool = False,
              show_logs: bool = False,
              progress: SolverProgress | None = None) -> int:
        """Admit constraints until every selected contingency is certified.

        Each pass that requires another solve must add a new block or limit.
        Per group, at most two blocks (balance and exact control), one bound
        pair per bus and one limit pair per monitored branch can be admitted.
        This gives a finite pass bound, including a final pass
        to certify the last solution. Already admitted components stay in place.

        :param objective: Base-case optimization objective.
        :param status: Status of the preceding base-case solve.
        :param batch_size: Positive number of pending groups to admit per solve.
        :param robust: Enable the backend's existing robust solution mode.
        :param show_logs: Display backend optimization logs.
        :param progress: Optional typed adapter for GUI progress messages.
        :return: Solver status, or NOT_SOLVED when certification fails.
        """
        c: int
        selected_index: int
        self.complete = False
        self.final_base = None
        self.witnesses.fill(None)
        if batch_size <= 0:
            status = self.prob.NOT_SOLVED
        else:
            components_per_group: int = 2 + self.nc.nbus + int(np.count_nonzero(self.monitor))
            max_screening_passes: int = len(self.states) * components_per_group + 1
            screening_pass: int = 0
            # A bounded counter guarantees termination
            while (screening_pass < max_screening_passes
                   and status == self.prob.OPTIMAL and not self.complete):
                screening_pass += 1
                base: OperatingPoint = self.symbolic_base.evaluate(self.prob)
                # Fixed size work arrays avoid growing per contingency records.
                scores: Vec = np.full(len(self.states), -np.inf, dtype=float)
                pending_buses: ObjVec = np.empty(len(self.states), dtype=object)
                pending_rows: ObjVec = np.empty(len(self.states), dtype=object)
                witnesses: ObjVec = np.empty(len(self.states), dtype=object)
                witnesses.fill(None)
                c = 0
                while c < len(self.states) and status == self.prob.OPTIMAL:
                    state: CompactState | None = cast(CompactState | None, self.states[c])
                    if state is None:
                        state = CompactState(self, c)
                    else:
                        pass  # Reuse the admitted compact state for this contingency.
                    value: Vec | None = state.numeric(base)
                    if value is None:
                        if state.exact:
                            status = self.prob.NOT_SOLVED
                        else:
                            scores[c] = np.inf
                            pending_buses[c] = np.empty(0, dtype=int)
                            pending_rows[c] = np.flatnonzero(self.monitor)
                    else:
                        evaluated_state: tuple[Vec, Vec] = state.evaluate(base, value)
                        potential: Vec = evaluated_state[0]
                        flow: Vec = evaluated_state[1]
                        violations: tuple[IntVec, IntVec] = state.violations(potential, flow)
                        buses: IntVec = violations[0]
                        rows: IntVec = violations[1]
                        # Admitted thermal rows may have explicit penalized slacks.
                        rows = rows[~state.rows[rows]]
                        buses = buses[~state.bus_rows[buses]]
                        if len(buses) or len(rows):
                            score: float = max(np.max((np.abs(flow[rows]) - self.rates[rows])
                                               / np.maximum(self.rates[rows], 1e-6), initial=0.),
                                        np.max(np.maximum(potential[buses] - self.net.upper[buses],
                                                          self.net.lower[buses] - potential[buses]), initial=0.))
                            scores[c] = float(score)
                            pending_buses[c] = buses
                            pending_rows[c] = rows
                        else:
                            pass  # The witness already satisfies all unrepresented limits.
                        witnesses[c] = value
                    c += 1

                if status != self.prob.OPTIMAL:
                    pass  # A failed physical check cannot certify the partial pass.
                else:
                    pending_indices: IntVec = np.flatnonzero(scores > -np.inf)
                    if len(pending_indices) == 0:
                        self.complete = True
                        self.final_base = base
                        self.witnesses = witnesses
                    else:
                        order: IntVec = np.argsort(-scores[pending_indices], kind='stable')
                        selected: IntVec = pending_indices[order[:batch_size]]
                        added: int = 0
                        for selected_index in range(len(selected)):
                            c = int(selected[selected_index])
                            state = cast(CompactState | None, self.states[c])
                            if state is None:
                                state = CompactState(self, c)
                                self.states[c] = state
                            else:
                                pass  # Add new limits to the existing compact block.
                            added += state.admit(pending_buses[c], pending_rows[c])
                        if added <= 0:
                            status = self.prob.NOT_SOLVED
                        else:
                            self.prob.minimize(objective + self.objective)
                            if progress is not None:
                                progress.report('Solving compact corrective NTC constraints...')
                            else:
                                pass  # The numerical solve also supports headless callers.
                            status = self.prob.solve(robust=robust, show_logs=show_logs)

            if status == self.prob.OPTIMAL and not self.complete:
                # Even an exhausted safety bound cannot accept an unchecked solution.
                status = self.prob.NOT_SOLVED
            else:
                pass  # Preserve a certified solution or the backend failure status.
        return status

    def numeric_state(self: CompactContingencies, c: int) -> tuple[Vec, Vec, Vec]:
        """Reconstruct an audited state without storing a groups-by-buses array.

        :param c: Selected contingency group index.
        :return: Certified potentials, branch flows and converter powers; NaNs if unavailable.
        """
        value: Vec | None = cast(Vec | None, self.witnesses[c])
        if self.final_base is not None and value is not None:
            state: CompactState | None = cast(CompactState | None, self.states[c])
            if state is None:
                state = CompactState(self, c)
            else:
                pass  # Reuse the already admitted exact block.
            evaluated_state: tuple[Vec, Vec] = state.evaluate(self.final_base, value)
            potential: Vec = evaluated_state[0]
            flow: Vec = evaluated_state[1]
            return potential, flow, value[:state.qn]
        else:
            self.logger.add_error('Requested contingency has no certified physical state', device=str(c))
            potential = np.full(self.nc.nbus, np.nan, dtype=float)
            flow = np.full(self.nc.nbr, np.nan, dtype=float)
            powers: Vec = np.full(self.nc.nvsc + self.nc.nhvdc, np.nan, dtype=float)
            return potential, flow, powers
