# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

"""
This file implements a DC-OPF for time series
That means that solves the OPF problem for a complete time series at once
"""
from enum import Enum
from typing import List, Dict, Tuple
import numpy as np
from GridCal.Engine.Core.snapshot_opf_data import SnapshotOpfData
from GridCal.Engine.Simulations.OPF.opf_templates import Opf, MIPSolvers, pywraplp
from GridCal.Engine.Devices.enumerations import TransformerControlType, ConverterControlType, HvdcControlType, GenerationNtcFormulation
from GridCal.Engine.basic_structures import Logger

import pandas as pd
from scipy.sparse.csc import csc_matrix


def lpDot(mat, arr):
    """
    CSC matrix-vector or CSC matrix-matrix dot product (A x b)
    :param mat: CSC sparse matrix (A)
    :param arr: dense vector or matrix of object type (b)
    :return: vector or matrix result of the product
    """
    n_rows, n_cols = mat.shape

    # check dimensional compatibility
    assert (n_cols == arr.shape[0])

    # check that the sparse matrix is indeed of CSC format
    if mat.format == 'csc':
        mat_2 = mat
    else:
        # convert the matrix to CSC sparse
        mat_2 = csc_matrix(mat)

    if len(arr.shape) == 1:
        """
        Uni-dimensional sparse matrix - vector product
        """
        res = np.zeros(n_rows, dtype=arr.dtype)
        for i in range(n_cols):
            for ii in range(mat_2.indptr[i], mat_2.indptr[i + 1]):
                j = mat_2.indices[ii]  # row index
                res[j] += mat_2.data[ii] * arr[i]  # C.data[ii] is equivalent to C[i, j]
    else:
        """
        Multi-dimensional sparse matrix - matrix product
        """
        cols_vec = arr.shape[1]
        res = np.zeros((n_rows, cols_vec), dtype=arr.dtype)

        for k in range(cols_vec):  # for each column of the matrix "vec", do the matrix vector product
            for i in range(n_cols):
                for ii in range(mat_2.indptr[i], mat_2.indptr[i + 1]):
                    j = mat_2.indices[ii]  # row index
                    res[j, k] += mat_2.data[ii] * arr[i, k]  # C.data[ii] is equivalent to C[i, j]
    return res


def lpExpand(mat, arr):
    """
    CSC matrix-vector or CSC matrix-matrix dot product (A x b)
    :param mat: CSC sparse matrix (A)
    :param arr: dense vector or matrix of object type (b)
    :return: vector or matrix result of the product
    """
    n_rows, n_cols = mat.shape

    # check dimensional compatibility
    assert (n_cols == arr.shape[0])

    # check that the sparse matrix is indeed of CSC format
    if mat.format == 'csc':
        mat_2 = mat
    else:
        # convert the matrix to CSC sparse
        mat_2 = csc_matrix(mat)

    if len(arr.shape) == 1:
        """
        Uni-dimensional sparse matrix - vector product
        """
        res = np.zeros(n_rows, dtype=arr.dtype)
        for i in range(n_cols):
            for ii in range(mat_2.indptr[i], mat_2.indptr[i + 1]):
                j = mat_2.indices[ii]  # row index
                res[j] = arr[i]  # C.data[ii] is equivalent to C[i, j]
    else:
        """
        Multi-dimensional sparse matrix - matrix product
        """
        cols_vec = arr.shape[1]
        res = np.zeros((n_rows, cols_vec), dtype=arr.dtype)

        for k in range(cols_vec):  # for each column of the matrix "vec", do the matrix vector product
            for i in range(n_cols):
                for ii in range(mat_2.indptr[i], mat_2.indptr[i + 1]):
                    j = mat_2.indices[ii]  # row index
                    res[j, k] = arr[i, k]  # C.data[ii] is equivalent to C[i, j]
    return res


def get_inter_areas_branches(nbr, F, T, buses_areas_1, buses_areas_2):
    """
    Get the inter-area branches.
    :param buses_areas_1: Area from
    :param buses_areas_2: Area to
    :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
    """
    lst: List[Tuple[int, float]] = list()
    for k in range(nbr):
        if F[k] in buses_areas_1 and T[k] in buses_areas_2:
            lst.append((k, 1.0))
        elif F[k] in buses_areas_2 and T[k] in buses_areas_1:
            lst.append((k, -1.0))
    return lst


def get_generators_connectivity(Cgen, buses_in_a1, buses_in_a2):
    """

    :param Cgen:
    :param buses_in_a1:
    :param buses_in_a2:
    :return:
    """
    assert isinstance(Cgen, csc_matrix)

    gens_in_a1 = list()
    gens_in_a2 = list()
    gens_out = list()
    for j in range(Cgen.shape[1]):  # for each bus
        for ii in range(Cgen.indptr[j], Cgen.indptr[j + 1]):
            i = Cgen.indices[ii]
            if i in buses_in_a1:
                gens_in_a1.append((i, j))  # i: bus idx, j: gen idx
            elif i in buses_in_a2:
                gens_in_a2.append((i, j))  # i: bus idx, j: gen idx
            else:
                gens_out.append((i, j))  # i: bus idx, j: gen idx

    return gens_in_a1, gens_in_a2, gens_out


def compose_branches_df(num, solver_power_vars, overloads1, overloads2):

    data = list()
    for k in range(num.nbr):
        val = solver_power_vars[k].solution_value() * num.Sbase
        row = [
            num.branch_data.branch_names[k],
            val,
            val / num.Rates[k],
            overloads1[k].solution_value(),
            overloads2[k].solution_value()
        ]
        data.append(row)

    cols = ['Name', 'Power (MW)', 'Loading', 'SlackF', 'SlackT']
    return pd.DataFrame(data, columns=cols)


def compose_generation_df(nc, generation, dgen_arr, Pgen_arr):

    data = list()
    for i, (var, dgen, pgen) in enumerate(zip(generation, dgen_arr, Pgen_arr)):
        if not isinstance(var, float):
            data.append([str(var),
                         '',
                         var.Lb() * nc.Sbase,
                         var.solution_value() * nc.Sbase,
                         pgen * nc.Sbase,
                         dgen.solution_value() * nc.Sbase,
                         var.Ub() * nc.Sbase])

    cols = ['Name', 'Bus', 'LB', 'Power (MW)', 'Set (MW)', 'Delta (MW)', 'UB']
    return pd.DataFrame(data=data, columns=cols)


class OpfNTC(Opf):

    def __init__(self, numerical_circuit: SnapshotOpfData,
                 area_from_bus_idx,
                 area_to_bus_idx,
                 alpha,
                 LODF,
                 solver_type: MIPSolvers = MIPSolvers.CBC,
                 generation_formulation: GenerationNtcFormulation = GenerationNtcFormulation.Optimal,
                 monitor_only_sensitive_branches=False,
                 branch_sensitivity_threshold=0.01,
                 skip_generation_limits=False,
                 consider_contingencies=True,
                 maximize_exchange_flows=True,
                 tolerance=1e-2,
                 weight_power_shift=1e0,
                 weight_generation_cost=1e-2,
                 weight_generation_delta=1e0,
                 weight_kirchoff=1e5,
                 weight_overloads=1e5,
                 weight_hvdc_control=1e0,
                 logger: Logger=None):
        """
        DC time series linear optimal power flow
        :param numerical_circuit: NumericalCircuit instance
        :param area_from_bus_idx: indices of the buses of the area 1
        :param area_to_bus_idx: indices of the buses of the area 2
        :param solver_type: type of linear solver
        :param generation_formulation: type of generation formulation
        :param monitor_only_sensitive_branches: Monitor the loading of only the sensitive branches?
        :param branch_sensitivity_threshold: branch sensitivity
        :param skip_generation_limits:
        """

        self.area_from_bus_idx = area_from_bus_idx

        self.area_to_bus_idx = area_to_bus_idx

        self.generation_formulation = generation_formulation

        self.monitor_only_sensitive_branches = monitor_only_sensitive_branches

        self.branch_sensitivity_threshold = branch_sensitivity_threshold

        self.skip_generation_limits = skip_generation_limits

        self.consider_contingencies = consider_contingencies

        self.maximize_exchange_flows = maximize_exchange_flows

        self.tolerance = tolerance

        self.alpha = alpha

        self.LODF = LODF

        self.weight_power_shift = weight_power_shift
        self.weight_generation_cost = weight_generation_cost
        self.weight_generation_delta = weight_generation_delta
        self.weight_kirchoff = weight_kirchoff
        self.weight_overloads = weight_overloads
        self.weight_hvdc_control = weight_hvdc_control

        self.inf = 99999999999999

        # results
        self.all_slacks = None
        self.Pg_delta = None
        self.area_balance_slack = None
        self.generation_delta_slacks = None
        self.Pinj = None
        self.hvdc_flow = None
        self.hvdc_slacks = None
        self.phase_shift = None
        self.nodal_slacks = None
        self.inter_area_branches = None
        self.inter_area_hvdc = None

        self.logger = logger

        # this builds the formulation right away
        Opf.__init__(self, numerical_circuit=numerical_circuit,
                     solver_type=solver_type,
                     ortools=True)

    def formulate_optimal_generation(self, ngen, Cgen, Pgen, Pmax, Pmin, a1, a2, t=0):
        """

        :param ngen:
        :param Cgen:
        :param Pgen:
        :param Pmax:
        :param Pmin:
        :param a1:
        :param a2:
        :param t:
        :return:
        """
        gens1, gens2, gens_out = get_generators_connectivity(Cgen, a1, a2)
        gen_cost = self.numerical_circuit.generator_data.generator_cost[:, t] * self.numerical_circuit.Sbase  # pass from $/MWh to $/p.u.h
        generation = np.zeros(ngen, dtype=object)
        delta = np.zeros(ngen, dtype=object)
        delta_slack_1 = np.zeros(ngen, dtype=object)
        delta_slack_2 = np.zeros(ngen, dtype=object)

        dgen1 = list()
        dgen2 = list()

        generation1 = list()
        generation2 = list()

        Pgen1 = list()
        Pgen2 = list()

        gen_a1_idx = list()
        gen_a2_idx = list()

        for bus_idx, gen_idx in gens1:

            if self.numerical_circuit.generator_data.generator_active[gen_idx] and \
                    self.numerical_circuit.generator_data.generator_dispatchable[gen_idx]:
                name = 'Gen_up_{0}@bus{1}'.format(gen_idx, bus_idx)

                ul = Pmax[gen_idx] - Pgen[gen_idx]

                if ul <= 0:
                    self.logger.add_error('Pmax < Pgen in a regulation up generator', 'Generator index {0}'.format(gen_idx), ul)

                if Pmin[gen_idx] >= Pmax[gen_idx]:
                    self.logger.add_error('Pmin >= Pmax', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])

                generation[gen_idx] = self.solver.NumVar(Pmin[gen_idx], Pmax[gen_idx], name)
                delta[gen_idx] = self.solver.NumVar(0, ul, name + '_delta')
                delta_slack_1[gen_idx] = self.solver.NumVar(0, self.inf, name + '_delta_slack_up')
                delta_slack_2[gen_idx] = self.solver.NumVar(0, self.inf, name + '_delta_slack_down')
                self.solver.Add(delta[gen_idx] == generation[gen_idx] - Pgen[gen_idx] + delta_slack_1[gen_idx] - delta_slack_2[gen_idx], 'Delta_up_gen{}'.format(gen_idx))
            else:
                generation[gen_idx] = Pgen[gen_idx]
                delta[gen_idx] = 0

            dgen1.append(delta[gen_idx])
            generation1.append(generation[gen_idx])
            Pgen1.append(Pgen[gen_idx])
            gen_a1_idx.append(gen_idx)

        for bus_idx, gen_idx in gens2:

            if self.numerical_circuit.generator_data.generator_active[gen_idx] and \
                    self.numerical_circuit.generator_data.generator_dispatchable[gen_idx]:
                name = 'Gen_down_{0}@bus{1}'.format(gen_idx, bus_idx)
                ll = -Pgen[gen_idx]

                if ll > 0:
                    self.logger.add_error('-Pgen > 0 in a regulation down generator', 'Generator index {0}'.format(gen_idx), ll)

                if Pmin[gen_idx] >= Pmax[gen_idx]:
                    self.logger.add_error('Pmin >= Pmax', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])

                generation[gen_idx] = self.solver.NumVar(Pmin[gen_idx], Pmax[gen_idx], name)
                delta[gen_idx] = self.solver.NumVar(ll, 0, name + '_delta')

                delta_slack_1[gen_idx] = self.solver.NumVar(0, self.inf, name + '_delta_slack_up')
                delta_slack_2[gen_idx] = self.solver.NumVar(0, self.inf, name + '_delta_slack_down')
                self.solver.Add(delta[gen_idx] == generation[gen_idx] - Pgen[gen_idx] + delta_slack_1[gen_idx] - delta_slack_2[gen_idx], 'Delta_down_gen{}'.format(gen_idx))
            else:
                generation[gen_idx] = Pgen[gen_idx]
                delta[gen_idx] = 0

            dgen2.append(delta[gen_idx])
            generation2.append(generation[gen_idx])
            Pgen2.append(Pgen[gen_idx])
            gen_a2_idx.append(gen_idx)

        # set the generation in the non inter-area ones
        for bus_idx, gen_idx in gens_out:
            if self.numerical_circuit.generator_data.generator_active[gen_idx]:
                generation[gen_idx] = Pgen[gen_idx]

        power_shift = self.solver.NumVar(0, self.inf, 'Area_slack')
        # self.solver.Add(self.solver.Sum(dgen1) + self.solver.Sum(dgen2) == area_balance_slack, 'Area equality')
        self.solver.Add(self.solver.Sum(dgen1) == power_shift, 'Area equality_1')
        self.solver.Add(self.solver.Sum(dgen2) == - power_shift, 'Area equality_2')

        return generation, delta, gen_a1_idx, gen_a2_idx, power_shift, dgen1, gen_cost, delta_slack_1, delta_slack_2

    def formulate_proportional_generation(self, ngen, Cgen, Pgen, Pmax, Pmin, a1, a2, t=0):
        """

        :param ngen:
        :param Cgen:
        :param Pgen:
        :param Pmax:
        :param Pmin:
        :param a1:
        :param a2:
        :param t:
        :return:
        """
        gens1, gens2, gens_out = get_generators_connectivity(Cgen, a1, a2)
        gen_cost = self.numerical_circuit.generator_data.generator_cost[:, t] * self.numerical_circuit.Sbase  # pass from $/MWh to $/p.u.h
        generation = np.zeros(ngen, dtype=object)
        delta = np.zeros(ngen, dtype=object)
        delta_slack_1 = np.zeros(ngen, dtype=object)
        delta_slack_2 = np.zeros(ngen, dtype=object)

        dgen1 = list()
        dgen2 = list()

        generation1 = list()
        generation2 = list()

        Pgen1 = list()
        Pgen2 = list()

        gen_a1_idx = list()
        gen_a2_idx = list()

        sum_gen_1 = 0
        for bus_idx, gen_idx in gens1:
            if self.numerical_circuit.generator_data.generator_active[gen_idx] and \
                    self.numerical_circuit.generator_data.generator_dispatchable[gen_idx]:
                sum_gen_1 += Pgen[gen_idx]

        sum_gen_2 = 0
        for bus_idx, gen_idx in gens2:
            if self.numerical_circuit.generator_data.generator_active[gen_idx] and \
                    self.numerical_circuit.generator_data.generator_dispatchable[gen_idx]:
                sum_gen_2 += Pgen[gen_idx]

        power_shift = self.solver.NumVar(0, self.inf, 'Area_slack')

        for bus_idx, gen_idx in gens1:

            if self.numerical_circuit.generator_data.generator_active[gen_idx] and \
                    self.numerical_circuit.generator_data.generator_dispatchable[gen_idx]:

                name = 'Gen_up_{0}@bus{1}'.format(gen_idx, bus_idx)

                if Pmin[gen_idx] >= Pmax[gen_idx]:
                    self.logger.add_error('Pmin >= Pmax', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])

                generation[gen_idx] = self.solver.NumVar(Pmin[gen_idx], Pmax[gen_idx], name)
                delta[gen_idx] = self.solver.NumVar(0, self.inf, name + '_delta')
                delta_slack_1[gen_idx] = self.solver.NumVar(0, self.inf, name + '_delta_slack_up')
                delta_slack_2[gen_idx] = self.solver.NumVar(0, self.inf, name + '_delta_slack_down')
                prop = abs(Pgen[gen_idx] / sum_gen_1)
                self.solver.Add(delta[gen_idx] == prop * power_shift, 'Delta_up_gen{}'.format(gen_idx))
                self.solver.Add(generation[gen_idx] == Pgen[gen_idx] + delta[gen_idx] + delta_slack_1[gen_idx] - delta_slack_2[gen_idx], 'Gen_up_gen{}'.format(gen_idx))
            else:
                generation[gen_idx] = Pgen[gen_idx]
                delta[gen_idx] = 0

            dgen1.append(delta[gen_idx])
            generation1.append(generation[gen_idx])
            Pgen1.append(Pgen[gen_idx])
            gen_a1_idx.append(gen_idx)

        for bus_idx, gen_idx in gens2:

            if self.numerical_circuit.generator_data.generator_active[gen_idx] and \
                    self.numerical_circuit.generator_data.generator_dispatchable[gen_idx]:

                name = 'Gen_down_{0}@bus{1}'.format(gen_idx, bus_idx)

                if Pmin[gen_idx] >= Pmax[gen_idx]:
                    self.logger.add_error('Pmin >= Pmax', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])

                generation[gen_idx] = self.solver.NumVar(Pmin[gen_idx], Pmax[gen_idx], name)
                delta[gen_idx] = self.solver.NumVar(-self.inf, 0, name + '_delta')
                delta_slack_1[gen_idx] = self.solver.NumVar(0, self.inf, name + '_delta_slack_up')
                delta_slack_2[gen_idx] = self.solver.NumVar(0, self.inf, name + '_delta_slack_down')

                prop = abs(Pgen[gen_idx] / sum_gen_2)
                self.solver.Add(delta[gen_idx] == - prop * power_shift, 'Delta_down_gen{}'.format(gen_idx))
                self.solver.Add(generation[gen_idx] == Pgen[gen_idx] + delta[gen_idx] + delta_slack_1[gen_idx] - delta_slack_2[gen_idx], 'Gen_down_gen{}'.format(gen_idx))
            else:
                generation[gen_idx] = Pgen[gen_idx]
                delta[gen_idx] = 0

            dgen2.append(delta[gen_idx])
            generation2.append(generation[gen_idx])
            Pgen2.append(Pgen[gen_idx])
            gen_a2_idx.append(gen_idx)

        # set the generation in the non inter-area ones
        for bus_idx, gen_idx in gens_out:
            if self.numerical_circuit.generator_data.generator_active[gen_idx]:
                generation[gen_idx] = Pgen[gen_idx]

        self.solver.Add(self.solver.Sum(dgen1) == power_shift, 'Area equality_1')
        self.solver.Add(self.solver.Sum(dgen2) == - power_shift, 'Area equality_2')

        return generation, delta, gen_a1_idx, gen_a2_idx, power_shift, dgen1, gen_cost, delta_slack_1, delta_slack_2

    def formulate_angles(self, set_ref_to_zero=True):
        """

        :param set_ref_to_zero:
        :return:
        """
        theta = np.zeros(self.numerical_circuit.nbus, dtype=object)

        for i in range(self.numerical_circuit.nbus):

            if self.numerical_circuit.bus_data.angle_min[i] > self.numerical_circuit.bus_data.angle_max[i]:
                self.logger.add_error('Theta min > Theta max', 'Bus {0}'.format(i),
                                      self.numerical_circuit.bus_data.angle_min[i])

            theta[i] = self.solver.NumVar(self.numerical_circuit.bus_data.angle_min[i],
                                          self.numerical_circuit.bus_data.angle_max[i],
                                          'theta' + str(i))

        if set_ref_to_zero:
            for i in self.numerical_circuit.vd:
                self.solver.Add(theta[i] == 0, "Slack_angle_zero_" + str(i))

        return theta

    def formulate_power_injections(self, Cgen, generation, t=0):
        """

        :param Cgen:
        :param generation:
        :param t:
        :return:
        """
        nc = self.numerical_circuit
        gen_injections = lpExpand(Cgen, generation)
        load_fixed_injections = nc.load_data.get_injections_per_bus()[:, t].real / nc.Sbase  # with sign already

        return gen_injections + load_fixed_injections

    def formulate_node_balance(self, angles, Pinj):
        """

        :param angles:
        :param Pinj:
        :return:
        """
        nc = self.numerical_circuit
        node_balance = lpDot(nc.Bbus, angles)
        node_balance_slack_1 = np.zeros(nc.nbus, dtype=object)
        node_balance_slack_2 = np.zeros(nc.nbus, dtype=object)

        # equal the balance to the generation: eq.13,14 (equality)
        i = 0
        for balance, power in zip(node_balance, Pinj):
            if self.numerical_circuit.bus_data.bus_active[i] and not isinstance(balance, int):  # balance is 0 for isolated buses
                self.solver.Add(balance == power, "Node_power_balance_" + str(i))
            i += 1

        return node_balance, node_balance_slack_1, node_balance_slack_2

    def formulate_branches_flow(self, angles, alpha_abs):
        """

        :param angles: node angles array
        :param alpha_abs: absolute branch sensitivities array
        :return:
        """
        nc = self.numerical_circuit
        flow_f = np.zeros(nc.nbr, dtype=object)
        overload1 = np.zeros(nc.nbr, dtype=object)
        overload2 = np.zeros(nc.nbr, dtype=object)
        tau = np.zeros(nc.nbr, dtype=object)
        monitor = np.zeros(nc.nbr, dtype=bool)
        rates = nc.Rates / nc.Sbase

        # formulate flows
        for m in range(nc.nbr):

            if nc.branch_data.branch_active[m]:
                _f = nc.branch_data.F[m]
                _t = nc.branch_data.T[m]

                # declare the flow variable with ample limits
                flow_f[m] = self.solver.NumVar(-self.inf, self.inf, 'pftk_' + str(m))

                # compute the branch susceptance
                if nc.branch_data.branch_dc[m]:
                    bk = 1.0 / nc.branch_data.R[m]
                else:
                    bk = 1.0 / nc.branch_data.X[m]

                if nc.branch_data.control_mode[m] == TransformerControlType.Pt:  # is a phase shifter
                    # create the phase shift variable
                    tau[m] = self.solver.NumVar(nc.branch_data.theta_min[m], nc.branch_data.theta_max[m], 'phase_shift_' + str(m))
                    # branch power from-to eq.15
                    self.solver.Add(flow_f[m] == bk * (angles[_f] - angles[_t] + tau[m]), 'phase_shifter_power_flow_' + str(m))
                else:
                    # branch power from-to eq.15
                    self.solver.Add(flow_f[m] == bk * (angles[_f] - angles[_t]), 'branch_power_flow_' + str(m))

                # determine the monitoring logic
                if self.monitor_only_sensitive_branches:
                    if nc.branch_data.monitor_loading[m] and alpha_abs[m] > self.branch_sensitivity_threshold:
                        monitor[m] = True
                    else:
                        monitor[m] = False
                else:
                    monitor[m] = nc.branch_data.monitor_loading[m]

                if monitor[m]:

                    if rates[m] <= 0:
                        self.logger.add_error('Rate = 0',
                                              'Branch:{0}'.format(m) + ';' +
                                              self.numerical_circuit.branch_data.branch_names[m], rates[m])

                    # rating restriction in the sense from-to: eq.17
                    overload1[m] = self.solver.NumVar(0, self.inf, 'overload1_' + str(m))
                    self.solver.Add(flow_f[m] <= (rates[m] + overload1[m]), "ft_rating_" + str(m))

                    # rating restriction in the sense to-from: eq.18
                    overload2[m] = self.solver.NumVar(0, self.inf, 'overload2_' + str(m))
                    self.solver.Add((-rates[m] - overload2[m]) <= flow_f[m], "tf_rating_" + str(m))

        return flow_f, overload1, overload2, tau, monitor

    def formulate_contingency(self, flow_f, alpha_abs, monitor):
        """

        :param flow_f:
        :param monitor:
        :return:
        """
        nc = self.numerical_circuit
        rates = nc.ContingencyRates / nc.Sbase

        # get the indices of the branches marked for contingency
        con_br_idx = self.numerical_circuit.branch_data.get_contingency_enabled_indices()

        # formulate contingency flows
        # this is done in a separated loop because all te flow variables must exist beforehand
        flow_n1f = list()
        overloads1 = list()
        overloads2 = list()
        con_idx = list()
        for m in range(nc.nbr):  # for every branch

            if monitor[m]:  # the monitor variable is pre-computed in the previous loop
                _f = nc.branch_data.F[m]
                _t = nc.branch_data.T[m]

                for ic, c in enumerate(con_br_idx):  # for every contingency

                    if m != c and alpha_abs[c] > self.branch_sensitivity_threshold:

                        # compute the N-1 flow
                        flow_n1 = flow_f[m] + self.LODF[m, c] * flow_f[c]

                        # rating restriction in the sense from-to
                        overload1 = self.solver.NumVar(0, self.inf, 'n-1_overload1_' + str(m) + ',' + str(c))
                        self.solver.Add(flow_n1 <= (rates[m] + overload1), "n-1_ft_rating_" + str(m) + ',' + str(c))

                        # rating restriction in the sense to-from
                        overload2 = self.solver.NumVar(0, self.inf, 'n-1_overload2_' + str(m) + ',' + str(c))
                        self.solver.Add((-rates[m] - overload2) <= flow_n1, "n-1_tf_rating_" + str(m) + ',' + str(c))

                        # store vars
                        con_idx.append((m, c))
                        flow_n1f.append(flow_n1)
                        overloads1.append(overload1)
                        overloads2.append(overload2)

        return flow_n1f, overloads1, overloads2, con_idx

    def formulate_hvdc_flow(self, angles, Pinj, t=0):
        """

        :param angles:
        :param Pinj:
        :param t:
        :return:
        """
        nc = self.numerical_circuit

        rates = nc.hvdc_data.rate[:, t] / nc.Sbase
        F = nc.hvdc_data.get_bus_indices_f()
        T = nc.hvdc_data.get_bus_indices_t()

        flow_f = np.zeros(nc.nhvdc, dtype=object)
        overload1 = np.zeros(nc.nhvdc, dtype=object)
        overload2 = np.zeros(nc.nhvdc, dtype=object)
        hvdc_control1 = np.zeros(nc.nhvdc, dtype=object)
        hvdc_control2 = np.zeros(nc.nhvdc, dtype=object)

        for i in range(self.numerical_circuit.nhvdc):

            if nc.hvdc_data.active[i, t]:

                _f = F[i]
                _t = T[i]

                hvdc_control1[i] = self.solver.NumVar(0, self.inf, 'hvdc_control1_' + str(i))
                hvdc_control2[i] = self.solver.NumVar(0, self.inf, 'hvdc_control2_' + str(i))
                P0 = nc.hvdc_data.Pt[i, t] / nc.Sbase

                if nc.hvdc_data.control_mode[i] == HvdcControlType.type_0_free:

                    if rates[i] <= 0:
                        self.logger.add_error('Rate = 0', 'HVDC:{0}'.format(i), rates[i])

                    flow_f[i] = self.solver.NumVar(-rates[i], rates[i], 'hvdc_flow_' + str(i))

                    # formulate the hvdc flow as an AC line equivalent
                    bk = 1.0 / nc.hvdc_data.r[i]  # TODO: yes, I know... DC...
                    self.solver.Add(flow_f[i] == P0 + bk * (angles[_f] - angles[_t]) + hvdc_control1[i] - hvdc_control2[i], 'hvdc_power_flow_' + str(i))

                    # add the injections matching the flow
                    Pinj[_f] -= flow_f[i]
                    Pinj[_t] += flow_f[i]

                    # rating restriction in the sense from-to: eq.17
                    overload1[i] = self.solver.NumVar(0, self.inf, 'overload_hvdc1_' + str(i))
                    self.solver.Add(flow_f[i] <= (rates[i] + overload1[i]), "hvdc_ft_rating_" + str(i))

                    # rating restriction in the sense to-from: eq.18
                    overload2[i] = self.solver.NumVar(0, self.inf, 'overload_hvdc2_' + str(i))
                    self.solver.Add((-rates[i] - overload2[i]) <= flow_f[i], "hvdc_tf_rating_" + str(i))

                elif nc.hvdc_data.control_mode[i] == HvdcControlType.type_1_Pset and not nc.hvdc_data.dispatchable[i]:
                    # simple injections model: The power is set by the user
                    flow_f[i] = P0 + hvdc_control1[i] - hvdc_control2[i]
                    Pinj[_f] -= flow_f[i]
                    Pinj[_t] += flow_f[i]

                elif nc.hvdc_data.control_mode[i] == HvdcControlType.type_1_Pset and nc.hvdc_data.dispatchable[i]:
                    # simple injections model, the power is a variable and it is optimized
                    P0 = self.solver.NumVar(-rates[i], rates[i], 'hvdc_pf_' + str(i))
                    flow_f[i] = P0 + hvdc_control1[i] - hvdc_control2[i]
                    Pinj[_f] -= flow_f[i]
                    Pinj[_t] += flow_f[i]

        return flow_f, overload1, overload2, hvdc_control1, hvdc_control2

    def formulate_objective(self, node_balance_slack_1, node_balance_slack_2,
                            inter_area_branches, flows_f, overload1, overload2, n1overload1, n1overload2,
                            inter_area_hvdc, hvdc_flow_f, hvdc_overload1, hvdc_overload2, hvdc_control1, hvdc_control2,
                            power_shift, dgen1, gen_cost, generation_delta,
                            delta_slack_1, delta_slack_2):
        """

        :param node_balance_slack_1:
        :param node_balance_slack_2:
        :param inter_area_branches:
        :param flows_f:
        :param overload1:
        :param overload2:
        :param inter_area_hvdc:
        :param hvdc_flow_f:
        :param hvdc_overload1:
        :param hvdc_overload2:
        :param hvdc_control1:
        :param hvdc_control2:
        :param power_shift:
        :param dgen1:
        :param gen_cost:
        :param generation_delta:
        :return:
        """
        # maximize the power from->to
        flows_ft = np.zeros(len(inter_area_branches), dtype=object)
        for i, (k, sign) in enumerate(inter_area_branches):
            flows_ft[i] = sign * flows_f[k]

        flows_hvdc_ft = np.zeros(len(inter_area_hvdc), dtype=object)
        for i, (k, sign) in enumerate(inter_area_hvdc):
            flows_hvdc_ft[i] = sign * hvdc_flow_f[k]

        flow_from_a1_to_a2 = self.solver.Sum(flows_ft) + self.solver.Sum(flows_hvdc_ft)

        # summation of generation deltas in the area 1 (this should be positive)
        area_1_gen_delta = self.solver.Sum(dgen1)

        # include the cost of generation
        gen_cost_f = self.solver.Sum(gen_cost * generation_delta)

        node_balance_slacks = self.solver.Sum(node_balance_slack_1) + self.solver.Sum(node_balance_slack_2)

        branch_overload = self.solver.Sum(overload1) + self.solver.Sum(overload2)

        contingency_branch_overload = self.solver.Sum(n1overload1) + self.solver.Sum(n1overload2)

        hvdc_overload = self.solver.Sum(hvdc_overload1) + self.solver.Sum(hvdc_overload2)

        hvdc_control = self.solver.Sum(hvdc_control1) + self.solver.Sum(hvdc_control2)

        delta_slacks = self.solver.Sum(delta_slack_1) + self.solver.Sum(delta_slack_2)

        # formulate objective function
        f = - self.weight_power_shift * area_1_gen_delta
        f -= self.weight_power_shift * power_shift

        if self.maximize_exchange_flows:
            f -= self.weight_power_shift * flow_from_a1_to_a2
        else:
            print('Skipping the exchange branch flows maximization')

        f += self.weight_generation_cost * gen_cost_f
        f += self.weight_generation_delta * delta_slacks
        f += self.weight_overloads * branch_overload
        f += self.weight_overloads * contingency_branch_overload
        f += self.weight_overloads * hvdc_overload
        f += self.weight_hvdc_control * hvdc_control

        # objective function
        self.solver.Minimize(f)

        all_slacks = node_balance_slacks + branch_overload + hvdc_overload + hvdc_control + delta_slacks + contingency_branch_overload

        return all_slacks

    def formulate(self):
        """
        Formulate the Net Transfer Capacity problem
        :return:
        """

        self.inf = self.solver.infinity()

        # general indices
        n = self.numerical_circuit.nbus
        m = self.numerical_circuit.nbr
        ng = self.numerical_circuit.ngen
        nb = self.numerical_circuit.nbatt
        nl = self.numerical_circuit.nload
        Sbase = self.numerical_circuit.Sbase

        # battery
        Pb_max = self.numerical_circuit.battery_pmax / Sbase
        Pb_min = self.numerical_circuit.battery_pmin / Sbase
        cost_b = self.numerical_circuit.battery_cost
        Cbat = self.numerical_circuit.battery_data.C_bus_batt.tocsc()

        # generator
        Pg_max = self.numerical_circuit.generator_pmax / Sbase
        Pg_min = self.numerical_circuit.generator_pmin / Sbase
        cost_g = self.numerical_circuit.generator_cost
        Pg_fix = self.numerical_circuit.generator_p / Sbase
        enabled_for_dispatch = self.numerical_circuit.generator_dispatchable
        Cgen = self.numerical_circuit.generator_data.C_bus_gen.tocsc()

        if self.skip_generation_limits:
            print('Skipping generation limits')
            Pg_max = self.inf * np.ones(self.numerical_circuit.ngen)
            Pg_min = -self.inf * np.ones(self.numerical_circuit.ngen)

        # load
        Pl = (self.numerical_circuit.load_active * self.numerical_circuit.load_s.real) / Sbase
        cost_l = self.numerical_circuit.load_cost

        # branch
        branch_ratings = self.numerical_circuit.branch_rates / Sbase
        Ys = 1 / (self.numerical_circuit.branch_R + 1j * self.numerical_circuit.branch_X)
        Bseries = (self.numerical_circuit.branch_active * Ys).imag
        cost_br = self.numerical_circuit.branch_cost
        alpha_abs = np.abs(self.alpha)

        # time index
        t = 0

        # get the inter-area branches and their sign
        inter_area_branches = get_inter_areas_branches(nbr=m,
                                                       F=self.numerical_circuit.branch_data.F,
                                                       T=self.numerical_circuit.branch_data.T,
                                                       buses_areas_1=self.area_from_bus_idx,
                                                       buses_areas_2=self.area_to_bus_idx)

        inter_area_hvdc = get_inter_areas_branches(nbr=self.numerical_circuit.nhvdc,
                                                   F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
                                                   T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
                                                   buses_areas_1=self.area_from_bus_idx,
                                                   buses_areas_2=self.area_to_bus_idx)

        # formulate the generation
        if self.generation_formulation == GenerationNtcFormulation.Optimal:

            generation, generation_delta, gen_a1_idx, gen_a2_idx, \
            power_shift, dgen1, gen_cost, \
            delta_slack_1, delta_slack_2 = self.formulate_optimal_generation(ngen=ng,
                                                                             Cgen=Cgen,
                                                                             Pgen=Pg_fix,
                                                                             Pmax=Pg_max,
                                                                             Pmin=Pg_min,
                                                                             a1=self.area_from_bus_idx,
                                                                             a2=self.area_to_bus_idx,
                                                                             t=t)
        elif self.generation_formulation == GenerationNtcFormulation.Proportional:

            generation, generation_delta, \
            gen_a1_idx, gen_a2_idx, \
            power_shift, dgen1, gen_cost, \
            delta_slack_1, delta_slack_2 = self.formulate_proportional_generation(ngen=ng,
                                                                                  Cgen=Cgen,
                                                                                  Pgen=Pg_fix,
                                                                                  Pmax=Pg_max,
                                                                                  Pmin=Pg_min,
                                                                                  a1=self.area_from_bus_idx,
                                                                                  a2=self.area_to_bus_idx,
                                                                                  t=t)
        else:
            generation, generation_delta, \
            gen_a1_idx, gen_a2_idx, \
            power_shift, dgen1, gen_cost, \
            delta_slack_1, delta_slack_2 = self.formulate_optimal_generation(ngen=ng,
                                                                             Cgen=Cgen,
                                                                             Pgen=Pg_fix,
                                                                             Pmax=Pg_max,
                                                                             Pmin=Pg_min,
                                                                             a1=self.area_from_bus_idx,
                                                                             a2=self.area_to_bus_idx,
                                                                             t=t)

        # add the angles
        theta = self.formulate_angles()

        # formulate the power injections
        Pinj = self.formulate_power_injections(Cgen=Cgen, generation=generation, t=t)

        # formulate the flows
        flow_f, overload1, overload2, tau, monitor = self.formulate_branches_flow(angles=theta,
                                                                                  alpha_abs=alpha_abs)

        # formulate the contingencies
        if self.consider_contingencies:
            n1flow_f, n1overload1, n1overload2, con_br_idx = self.formulate_contingency(flow_f=flow_f,
                                                                                        alpha_abs=alpha_abs,
                                                                                        monitor=monitor)
        else:
            n1overload1 = list()
            n1overload2 = list()
            con_br_idx = list()
            n1flow_f = list()

        # formulate the HVDC flows
        hvdc_flow_f, hvdc_overload1, hvdc_overload2, \
        hvdc_control1, hvdc_control2 = self.formulate_hvdc_flow(angles=theta, Pinj=Pinj, t=t)

        # formulate the node power balance
        node_balance, \
        node_balance_slack_1, \
        node_balance_slack_2 = self.formulate_node_balance(angles=theta, Pinj=Pinj)

        # formulate the objective
        self.all_slacks = self.formulate_objective(node_balance_slack_1=node_balance_slack_1,
                                                   node_balance_slack_2=node_balance_slack_2,
                                                   inter_area_branches=inter_area_branches,
                                                   flows_f=flow_f,
                                                   overload1=overload1,
                                                   overload2=overload2,
                                                   n1overload1=n1overload1,
                                                   n1overload2=n1overload2,
                                                   inter_area_hvdc=inter_area_hvdc,
                                                   hvdc_flow_f=hvdc_flow_f,
                                                   hvdc_overload1=hvdc_overload1,
                                                   hvdc_overload2=hvdc_overload2,
                                                   hvdc_control1=hvdc_control1,
                                                   hvdc_control2=hvdc_control2,
                                                   power_shift=power_shift,
                                                   dgen1=dgen1,
                                                   gen_cost=gen_cost[gen_a1_idx],
                                                   generation_delta=generation_delta[gen_a1_idx],
                                                   delta_slack_1=delta_slack_1,
                                                   delta_slack_2=delta_slack_2)

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.theta = theta
        self.Pg = generation
        self.Pg_delta = generation_delta
        self.area_balance_slack = power_shift
        self.generation_delta_slacks = delta_slack_1 - delta_slack_2

        # self.Pb = Pb
        self.Pl = Pl
        self.Pinj = Pinj
        # self.load_shedding = load_slack
        self.s_from = flow_f
        self.s_to = - flow_f
        self.n1flow_f = n1flow_f
        self.contingency_br_idx = con_br_idx

        self.hvdc_flow = hvdc_flow_f
        self.hvdc_slacks = hvdc_overload1 - hvdc_overload2

        self.overloads = overload1 - overload2
        self.rating = branch_ratings
        self.phase_shift = tau
        self.nodal_restrictions = node_balance

        self.nodal_slacks = node_balance_slack_1 - node_balance_slack_2

        self.inter_area_branches = inter_area_branches
        self.inter_area_hvdc = inter_area_hvdc

        # n1flow_f, n1overload1, n1overload2, con_br_idx
        self.contingency_flows_list = n1flow_f
        self.contingency_indices_list = con_br_idx  # [(t, m, c), ...]
        self.contingency_flows_slacks_list = n1overload1

        return self.solver

    def save_lp(self, fname="ortools.lp"):
        """
        Save problem in LP format
        :param fname: name of the file
        """
        # save the problem in LP format to debug
        lp_content = self.solver.ExportModelAsLpFormat(obfuscated=False)
        # lp_content = solver.ExportModelAsMpsFormat(obfuscated=False, fixed_format=True)
        file2write = open(fname, 'w')
        file2write.write(lp_content)
        file2write.close()

    def solve(self):
        """
        Call ORTools to solve the problem
        """
        self.status = self.solver.Solve()

        # self.save_lp()

        return self.converged()

    def error(self):
        if self.status == pywraplp.Solver.OPTIMAL:
            return self.all_slacks.solution_value()
        else:
            return 99999

    def converged(self):
        return abs(self.error()) < self.tolerance

    @staticmethod
    def extract(arr, make_abs=False):  # override this method to call ORTools instead of PuLP
        """
        Extract values fro the 1D array of LP variables
        :param arr: 1D array of LP variables
        :param make_abs: substitute the result by its abs value
        :return: 1D numpy array
        """
        val = np.zeros(arr.shape)
        for i in range(val.shape[0]):
            if isinstance(arr[i], float) or isinstance(arr[i], int):
                val[i] = arr[i]
            else:
                val[i] = arr[i].solution_value()
        if make_abs:
            val = np.abs(val)

        return val

    def get_contingency_flows_list(self):
        """
        Square matrix of contingency flows (n branch, n contingency branch)
        :return:
        """

        x = np.zeros(len(self.contingency_flows_list))

        for i in range(len(self.contingency_flows_list)):
            try:
                x[i] = self.contingency_flows_list[i].solution_value() * self.numerical_circuit.Sbase
            except AttributeError:
                x[i] = float(self.contingency_flows_list[i]) * self.numerical_circuit.Sbase

        return x

    def get_contingency_flows_slacks_list(self):
        """
        Square matrix of contingency flows (n branch, n contingency branch)
        :return:
        """

        x = np.zeros(len(self.n1flow_f))

        for i in range(len(self.n1flow_f)):
            try:
                x[i] = self.contingency_flows_list[i].solution_value() * self.numerical_circuit.Sbase
            except AttributeError:
                x[i] = float(self.contingency_flows_slacks_list[i]) * self.numerical_circuit.Sbase

        return x

    def get_contingency_loading(self):
        """
        Square matrix of contingency flows (n branch, n contingency branch)
        :return:
        """

        x = np.zeros(len(self.n1flow_f))

        for i in range(len(self.n1flow_f)):
            try:
                x[i] = self.n1flow_f[i].solution_value() * self.numerical_circuit.Sbase / (self.rating[i] + 1e-20)
            except AttributeError:
                x[i] = float(self.n1flow_f[i]) * self.numerical_circuit.Sbase / (self.rating[i] + 1e-20)

        return x

    def get_power_injections(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.Pinj, make_abs=False) * self.numerical_circuit.Sbase

    def get_generator_delta(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.Pg_delta, make_abs=False) * self.numerical_circuit.Sbase

    def get_generator_delta_slacks(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.generation_delta_slacks, make_abs=False) * self.numerical_circuit.Sbase

    def get_node_slacks(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.nodal_slacks, make_abs=False) * self.numerical_circuit.Sbase

    def get_phase_angles(self):
        """
        Get the phase shift solution
        :return:
        """
        return self.extract(self.phase_shift, make_abs=False)

    def get_hvdc_flow(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.hvdc_flow, make_abs=False) * self.numerical_circuit.Sbase

    def get_hvdc_loading(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.hvdc_flow, make_abs=False) * self.numerical_circuit.Sbase / self.numerical_circuit.hvdc_data.rate[:, 0]

    def get_hvdc_slacks(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.hvdc_slacks, make_abs=False) * self.numerical_circuit.Sbase


if __name__ == '__main__':
    from GridCal.Engine.basic_structures import BranchImpedanceMode
    from GridCal.Engine.IO.file_handler import FileOpen
    from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit

    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas.gridcal'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas_voltages_hvdc_shifter.gridcal'
    fname = r'C:\Users\SPV86\Documents\Git\GitHub\GridCal\Grids_and_profiles\grids\IEEE14 - ntc areas_voltages_hvdc_shifter.gridcal'

    main_circuit = FileOpen(fname).open()

    # compute information about areas ----------------------------------------------------------------------------------

    area_from_idx = 1
    area_to_idx = 0
    areas = main_circuit.get_bus_area_indices()

    numerical_circuit_ = compile_snapshot_opf_circuit(circuit=main_circuit,
                                                      apply_temperature=False,
                                                      branch_tolerance_mode=BranchImpedanceMode.Specified)

    # get the area bus indices
    areas = areas[numerical_circuit_.original_bus_idx]
    a1 = np.where(areas == area_from_idx)[0]
    a2 = np.where(areas == area_to_idx)[0]

    problem = OpfNTC(numerical_circuit=numerical_circuit_, area_from_bus_idx=a1, area_to_bus_idx=a2,
                     generation_formulation=GenerationNtcFormulation.Proportional)

    print('Solving...')
    status = problem.solve()

    print("Status:", status)

    print('Angles\n', np.angle(problem.get_voltage()))
    print('Branch loading\n', problem.get_loading())
    print('Gen power\n', problem.get_generator_power())
    print('Delta power\n', problem.get_generator_delta())
    print('Area slack', problem.area_balance_slack.solution_value())
    print('HVDC flow\n', problem.get_hvdc_flow())
