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
from typing import List, Dict, Tuple
import numpy as np
from GridCal.Engine.Core.snapshot_opf_data import SnapshotOpfData
from GridCal.Engine.Simulations.OPF.opf_templates import Opf, MIPSolvers, pywraplp
from GridCal.Engine.Devices.enumerations import TransformerControlType, ConverterControlType, HvdcControlType

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

    def __init__(self, numerical_circuit: SnapshotOpfData, area_from_bus_idx, area_to_bus_idx,
                 solver_type: MIPSolvers = MIPSolvers.CBC):
        """
        DC time series linear optimal power flow
        :param numerical_circuit: NumericalCircuit instance
        """
        self.area_from_bus_idx = area_from_bus_idx

        self.area_to_bus_idx = area_to_bus_idx

        # this builds the formulation right away
        Opf.__init__(self, numerical_circuit=numerical_circuit, solver_type=solver_type)

    def formulate_generation(self, ngen, Cgen, Pgen, Pmax, Pmin, a1, a2):

        gens1, gens2, gens_out = get_generators_connectivity(Cgen, a1, a2)

        generation = np.zeros(ngen, dtype=object)
        delta = np.zeros(ngen, dtype=object)

        dgen1 = list()
        dgen2 = list()

        generation1 = list()
        generation2 = list()

        Pgen1 = list()
        Pgen2 = list()

        gen_a1_idx = list()
        gen_a2_idx = list()

        for bus_idx, gen_idx in gens1:
            name = 'Gen_up_{0}@bus{1}'.format(gen_idx, bus_idx)

            generation[gen_idx] = self.solver.NumVar(Pmin[gen_idx], Pmax[gen_idx], name)
            delta[gen_idx] = self.solver.NumVar(0, Pmax[gen_idx] - Pgen[gen_idx], name + '_delta')
            self.solver.Add(delta[gen_idx] == generation[gen_idx] - Pgen[gen_idx], 'Delta_up_gen{}'.format(gen_idx))

            dgen1.append(delta[gen_idx])
            generation1.append(generation[gen_idx])
            Pgen1.append(Pgen[gen_idx])
            gen_a1_idx.append(gen_idx)

        for bus_idx, gen_idx in gens2:
            name = 'Gen_down_{0}@bus{1}'.format(gen_idx, bus_idx)

            generation[gen_idx] = self.solver.NumVar(Pmin[gen_idx], Pmax[gen_idx], name)
            delta[gen_idx] = self.solver.NumVar(-Pgen[gen_idx], 0, name + '_delta')
            self.solver.Add(delta[gen_idx] == generation[gen_idx] - Pgen[gen_idx], 'Delta_down_gen{}'.format(gen_idx))

            dgen2.append(delta[gen_idx])
            generation2.append(generation[gen_idx])
            Pgen2.append(Pgen[gen_idx])
            gen_a2_idx.append(gen_idx)

        # set the generation in the non inter-area ones
        for bus_idx, gen_idx in gens_out:
            generation[gen_idx] = Pgen[gen_idx]

        area_balance_slack = self.solver.NumVar(0, 99999, 'Area_slack')
        self.solver.Add(self.solver.Sum(dgen1) + self.solver.Sum(dgen2) == area_balance_slack, 'Area equality')

        return generation, delta, gen_a1_idx, gen_a2_idx, area_balance_slack, dgen1

    def formulate_angles(self, set_ref_to_zero=True):

        theta = np.array([self.solver.NumVar(-6.28, 6.28, 'theta' + str(i)) for i in range(self.numerical_circuit.nbus)])

        if set_ref_to_zero:
            for i in self.numerical_circuit.vd:
                self.solver.Add(theta[i] == 0, "Slack_angle_zero_" + str(i))

        return theta

    def formulate_phase_shift(self):

        phase_shift_dict = dict()
        nc = self.numerical_circuit
        for i in range(nc.branch_data.nbr):
            if nc.branch_data.control_mode[i] == TransformerControlType.Pt:  # is a phase shifter
                phase_shift_dict[i] = self.solver.NumVar(nc.branch_data.theta_min[i],
                                            nc.branch_data.theta_max[i],
                                            'phase_shift' + str(i))
        return phase_shift_dict

    def formulate_power_injections(self, Cgen, generation, t=0):

        nc = self.numerical_circuit
        gen_injections = lpExpand(Cgen, generation)
        load_fixed_injections = nc.load_data.get_injections_per_bus()[:, t].real / nc.Sbase  # with sign already

        return gen_injections + load_fixed_injections

    def formulate_node_balance(self, angles, Pinj):

        nc = self.numerical_circuit
        node_balance = lpDot(nc.Bbus, angles)

        node_balance_slack_1 = [self.solver.NumVar(0, 99999, 'balance_slack1_' + str(i)) for i in range(nc.nbus)]
        node_balance_slack_2 = [self.solver.NumVar(0, 99999, 'balance_slack2_' + str(i)) for i in range(nc.nbus)]

        # equal the balance to the generation: eq.13,14 (equality)
        i = 0
        for balance, power in zip(node_balance, Pinj):
            self.solver.Add(balance == power + node_balance_slack_1[i] - node_balance_slack_2[i],
                       "Node_power_balance_" + str(i))
            i += 1

        return node_balance, node_balance_slack_1, node_balance_slack_2

    def formulate_branches_flow(self, angles, tau_dict):

        nc = self.numerical_circuit

        flow_f = np.empty(nc.nbr, dtype=object)
        rates = nc.Rates / nc.Sbase
        overload1 = np.empty(nc.nbr, dtype=object)
        overload2 = np.empty(nc.nbr, dtype=object)
        for i in range(nc.nbr):

            _f = nc.branch_data.F[i]
            _t = nc.branch_data.T[i]
            flow_f[i] = self.solver.NumVar(-rates[i], rates[i], 'pftk_' + str(i))

            # compute the branch susceptance
            bk = (1.0 / complex(nc.branch_data.R[i], nc.branch_data.X[i])).imag

            if i in tau_dict.keys():
                # branch power from-to eq.15
                self.solver.Add(flow_f[i] == bk * (angles[_t] - angles[_f] - tau_dict[i]), 'phase_shifter_power_flow_' + str(i))
            else:
                # branch power from-to eq.15
                self.solver.Add(flow_f[i] == bk * (angles[_t] - angles[_f]), 'branch_power_flow_' + str(i))

            # rating restriction in the sense from-to: eq.17
            overload1[i] = self.solver.NumVar(0, 9999, 'overload1_' + str(i))
            self.solver.Add(flow_f[i] <= (rates[i] + overload1[i]), "ft_rating_" + str(i))

            # rating restriction in the sense to-from: eq.18
            overload2[i] = self.solver.NumVar(0, 9999, 'overload2_' + str(i))
            self.solver.Add((-rates[i] - overload2[i]) <= flow_f[i], "tf_rating_" + str(i))

        return flow_f, overload1, overload2

    def formulate_hvdc_flow(self, angles, t=0):
        nc = self.numerical_circuit

        flow_f = np.empty(nc.nhvdc, dtype=object)
        rates = nc.hvdc_data.rate[:, t] / nc.Sbase
        F = nc.hvdc_data.get_bus_indices_f()
        T = nc.hvdc_data.get_bus_indices_t()
        overload1 = np.empty(nc.nhvdc, dtype=object)
        overload2 = np.empty(nc.nhvdc, dtype=object)

        hvdc_control1 = np.empty(nc.nhvdc, dtype=object)
        hvdc_control2 = np.empty(nc.nhvdc, dtype=object)

        for i in range(self.numerical_circuit.nhvdc):
            _f = F[i]
            _t = T[i]
            flow_f[i] = self.solver.NumVar(-rates[i], rates[i], 'hvdc_flow_' + str(i))
            hvdc_control1[i] = self.solver.NumVar(0, 9999, 'hvdc_control1_' + str(i))
            hvdc_control2[i] = self.solver.NumVar(0, 9999, 'hvdc_control2_' + str(i))
            P0 = nc.hvdc_data.Pf[i, t]

            if nc.hvdc_data.control_mode[i] == HvdcControlType.type_0_free:
                bk = 1.0 / nc.hvdc_data.r[i]  # TODO: yes, I know... DC...
                self.solver.Add(flow_f[i] == P0 + bk * (angles[_t] - angles[_f]) + hvdc_control1[i], 'hvdc_power_flow_' + str(i))

            elif nc.hvdc_data.control_mode[i] == HvdcControlType.type_1_Pset:
                bk = 1.0
                self.solver.Add(flow_f[i] == P0 + bk * (angles[_t] - angles[_f]) + hvdc_control2[i], 'hvdc_power_flow_' + str(i))

            # rating restriction in the sense from-to: eq.17
            overload1[i] = self.solver.NumVar(0, 9999, 'overload_hvdc1_' + str(i))
            self.solver.Add(flow_f[i] <= (rates[i] + overload1[i]), "hvdc_ft_rating_" + str(i))

            # rating restriction in the sense to-from: eq.18
            overload2[i] = self.solver.NumVar(0, 9999, 'overload_hvdc2_' + str(i))
            self.solver.Add((-rates[i] - overload2[i]) <= flow_f[i], "hvdc_tf_rating_" + str(i))

        return flow_f, overload1, overload2, hvdc_control1, hvdc_control2

    def formulate_objective(self, node_balance_slack_1, node_balance_slack_2,
                            inter_area_branches, flows_f, overload1, overload2,
                            inter_area_hvdc, hvdc_flow_f, hvdc_overload1, hvdc_overload2, hvdc_control1, hvdc_control2,
                            area_balance_slack, dgen1):

        # maximize the power from->to
        flows_ft = np.zeros(len(inter_area_branches), dtype=object)
        for i, (k, sign) in enumerate(inter_area_branches):
            flows_ft[i] = sign * flows_f[k]

        flows_hvdc_ft = np.zeros(len(inter_area_hvdc), dtype=object)
        for i, (k, sign) in enumerate(inter_area_hvdc):
            flows_hvdc_ft[i] = sign * hvdc_flow_f[k]

        flow_from_a1_to_a2 = self.solver.Sum(flows_ft)

        # include the cost of generation
        # gen_cost_f = solver.Sum(gen_cost * delta)

        node_balance_slack_f = self.solver.Sum(node_balance_slack_1) + self.solver.Sum(node_balance_slack_2)

        branch_overload = self.solver.Sum(overload1) + self.solver.Sum(overload2)

        hvdc_overload = self.solver.Sum(hvdc_overload1) + self.solver.Sum(hvdc_overload2)

        hvdc_control = self.solver.Sum(hvdc_control1) + self.solver.Sum(hvdc_control2)

        # objective function
        self.solver.Minimize(
            # - 1.0 * flow_from_a1_to_a2
            - 1.0 * self.solver.Sum(dgen1)
            + 1.0 * area_balance_slack
            # + 1.0 * gen_cost_f
            + 1e0 * node_balance_slack_f
            + 1e0 * branch_overload
            + 1e0 * hvdc_overload
            + 1.0 * hvdc_control
        )

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
            if isinstance(arr[i], float):
                val[i] = arr[i]
            else:
                val[i] = arr[i].solution_value()
        if make_abs:
            val = np.abs(val)

        return val

    def formulate(self):
        """
        Formulate the Net Transfer Capacity problem
        :return:
        """

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

        # load
        Pl = (self.numerical_circuit.load_active * self.numerical_circuit.load_s.real) / Sbase
        cost_l = self.numerical_circuit.load_cost

        # branch
        branch_ratings = self.numerical_circuit.branch_rates / Sbase
        Ys = 1 / (self.numerical_circuit.branch_R + 1j * self.numerical_circuit.branch_X)
        Bseries = (self.numerical_circuit.branch_active * Ys).imag
        cost_br = self.numerical_circuit.branch_cost

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

        # add te generation
        Pg, delta, gen_a1_idx, gen_a2_idx, \
        area_balance_slack, dgen1 = self.formulate_generation(ngen=ng,
                                                              Cgen=Cgen,
                                                              Pgen=Pg_fix,
                                                              Pmax=Pg_max,
                                                              Pmin=Pg_min,
                                                              a1=self.area_from_bus_idx,
                                                              a2=self.area_to_bus_idx)

        # add the angles
        theta = self.formulate_angles()

        phase_shift_dict = self.formulate_phase_shift()

        Pinj = self.formulate_power_injections(Cgen=Cgen, generation=Pg, t=t)

        node_balance, \
        node_balance_slack_1, \
        node_balance_slack_2 = self.formulate_node_balance(angles=theta, Pinj=Pinj)

        flow_f, overload1, overload2 = self.formulate_branches_flow(angles=theta,
                                                                    tau_dict=phase_shift_dict)

        hvdc_flow_f, hvdc_overload1, hvdc_overload2, hvdc_control1, hvdc_control2 = self.formulate_hvdc_flow(angles=theta, t=t)

        self.formulate_objective(node_balance_slack_1, node_balance_slack_2,
                                 inter_area_branches, flow_f, overload1, overload2,
                                 inter_area_hvdc, hvdc_flow_f, hvdc_overload1, hvdc_overload2, hvdc_control1, hvdc_control2,
                                 area_balance_slack, dgen1)

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.theta = theta
        self.Pg = Pg
        # self.Pb = Pb
        self.Pl = Pl
        self.Pinj = Pinj
        # self.load_shedding = load_slack
        self.s_from = flow_f
        self.s_to = - flow_f

        self.hvdc_flow = hvdc_flow_f

        self.overloads = overload1 + overload2
        self.rating = branch_ratings
        self.phase_shift_dict = phase_shift_dict
        self.nodal_restrictions = node_balance

        return self.solver

    def solve(self):
        """
        Call ORTools to solve the problem
        """
        self.status = self.solver.Solve()

        return self.converged()

    def converged(self):
        return self.status == pywraplp.Solver.OPTIMAL

    def get_power_injections(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.Pinj, make_abs=False) * self.numerical_circuit.Sbase

    def get_phase_angles(self):
        """
        Get the phase shift solution
        :return:
        """
        arr = np.zeros(self.numerical_circuit.nbr)
        for i, var in self.phase_shift_dict.values():
            arr[i] = var.solution_value()

        return arr

    def get_hvdc_flow(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.hvdc_flow, make_abs=False) * self.numerical_circuit.Sbase


if __name__ == '__main__':
    from GridCal.Engine.basic_structures import BranchImpedanceMode
    from GridCal.Engine.IO.file_handler import FileOpen
    from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit

    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas.gridcal'
    fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas_voltages_hvdc_shifter.gridcal'
    # fname = r'D:\ReeGit\github\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'

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

    problem = OpfNTC(numerical_circuit=numerical_circuit_, area_from_bus_idx=a1, area_to_bus_idx=a2)

    print('Solving...')
    status = problem.solve()

    print("Status:", status)

    print('Angles\n', np.angle(problem.get_voltage()))
    print('Branch loading\n', problem.get_loading())
    print('Gen power\n', problem.get_generator_power())
    print('HVDC flow\n', problem.get_hvdc_flow())
