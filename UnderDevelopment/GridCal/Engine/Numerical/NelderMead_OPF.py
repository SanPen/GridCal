import copy
import numpy as np
from GridCal.Engine.IoStructures import OptimalPowerFlowResults
from GridCal.Engine.PowerFlowDriver import PowerFlowMP, PowerFlowOptions, SolverType
from GridCal.Engine.CalculationEngine import MultiCircuit

"""
Pure Python/Numpy implementation of the Nelder-Mead algorithm from
https://github.com/alxsoares/nelder-mead/blob/master/nelder_mead.py
Reference: https://en.wikipedia.org/wiki/Nelder%E2%80%93Mead_method

transformations from https://github.com/alexblaessle/constrNMPy/blob/master/constrNMPy/constrNMPy.py

Both use GPL license
"""


# def transform_x(x, LB, UB, offset=1E-20):
#     """Transforms ``x`` into constrained form, obeying upper bounds ``UB`` and lower bounds ``LB``.
#     .. note:: Will add tiny offset to LB if ``LB[i]=0``, to avoid singularities.
#     Idea taken from http://www.mathworks.com/matlabcentral/fileexchange/8277-fminsearchbnd--fminsearchcon
#     Args:
#         x (numpy.ndarray): Input vector.
#         LB (numpy.ndarray): Lower bounds.
#         UB (numpy.ndarray): Upper bounds.
#     Keyword Args:
#         offset (float): Small offset added to lower bound if LB=0.
#     Returns:
#         numpy.ndarray: Transformed x-values.
#     """
#
#     # Make sure everything is float
#     x = np.asarray(x, dtype=np.float64)
#
#     # Add offset if necessary to avoid singularities
#     for l in LB:
#         if l == 0:
#             l = l + offset
#
#     # Determine number of parameters to be fitted
#     nparams = len(x)
#
#     # Make empty vector
#     xtrans = np.zeros(np.shape(x))
#
#     # k allows some variables to be fixed, thus dropped from the
#     # optimization.
#     k = 0
#
#     for i in range(nparams):
#
#         # Upper bound only
#         if UB[i] is not None and LB[i] is None:
#
#             xtrans[i] = UB[i] - x[k] ** 2
#             k = k + 1
#
#         # Lower bound only
#         elif UB[i] is None and LB[i] is not None:
#
#             xtrans[i] = LB[i] + x[k] ** 2
#             k = k + 1
#
#         # Both bounds
#         elif UB[i] is not None and LB[i] is not None:
#
#             xtrans[i] = (np.sin(x[k]) + 1.) / 2. * (UB[i] - LB[i]) + LB[i]
#             xtrans[i] = max([LB[i], min([UB[i], xtrans[i]])])
#             k = k + 1
#
#         # No bounds
#         elif UB[i] is None and LB[i] is None:
#
#             xtrans[i] = x[k]
#             k = k + 1
#
#         # NOTE: The original file has here another case for fixed variable. We might need to add this here!!!
#
#     return np.array(xtrans)
#
#
# def transform_x0(x0, LB, UB):
#     r"""Transforms ``x0`` into constrained form, obeying upper bounds ``UB`` and lower bounds ``LB``.
#     Idea taken from http://www.mathworks.com/matlabcentral/fileexchange/8277-fminsearchbnd--fminsearchcon
#     Args:
#         x0 (numpy.ndarray): Input vector.
#         LB (numpy.ndarray): Lower bounds.
#         UB (numpy.ndarray): Upper bounds.
#     Returns:
#         numpy.ndarray: Transformed x-values.
#     """
#
#     # Turn into list
#     x0u = list(x0)
#
#     k = 0
#     for i in range(len(x0)):
#
#         # Upper bound only
#         if UB[i] is not None and LB[i] is None:
#             if UB[i] <= x0[i]:
#                 x0u[k] = 0
#             else:
#                 x0u[k] = np.sqrt(UB[i] - x0[i])
#             k = k + 1
#
#         # Lower bound only
#         elif UB[i] is None and LB[i] is not None:
#             if LB[i] >= x0[i]:
#                 x0u[k] = 0
#             else:
#                 x0u[k] = np.sqrt(x0[i] - LB[i])
#             k = k + 1
#
#         # Both bounds
#         elif UB[i] is not None and LB[i] is not None:
#             if UB[i] <= x0[i]:
#                 x0u[k] = np.pi / 2
#             elif LB[i] >= x0[i]:
#                 x0u[k] = -np.pi / 2
#             else:
#                 x0u[k] = 2 * (x0[i] - LB[i]) / (UB[i] - LB[i]) - 1;
#                 # shift by 2*pi to avoid problems at zero in fmin otherwise, the initial simplex is vanishingly small
#                 x0u[k] = 2 * np.pi + np.arcsin(max([-1, min(1, x0u[k])]));
#             k = k + 1
#
#         # No bounds
#         elif UB[i] is None and LB[i] is None:
#             x0u[k] = x0[i]
#             k = k + 1
#
#     return np.array(x0u)


# def create_initial_simplex_exploration(objective_function, x_start, LB, UB, step=0.1):
#     """
#
#     Args:
#         objective_function:
#         x_start:
#         LB:
#         UB:
#         step:
#
#     Returns:
#
#     """
#     dim = len(x_start)
#     prev_best = objective_function(transform_x(x_start, LB, UB))
#     res = [[x_start, prev_best]]
#     for i in range(dim):
#         x = copy.copy(x_start)
#         x[i] = x[i] + step
#         score = objective_function(transform_x(x, LB, UB))
#         res.append([x, score])
#     return res


def nelder_mead(objective_function, x_start,
                step=0.1, no_improve_thr=10e-6,
                no_improv_break=10, max_iter=0,
                alpha=1., gamma=2., rho=-0.5, sigma=0.5,
                break_at_value=False, good_enough_value=0.0, init_res=list(), callback=None):

    """

    Args:
        objective_function: function to optimize, must return a scalar score
            and operate over a numpy array of the same dimensions as x_start
        x_start: initial position
        LB: lower bounds (can be None)
        UB: upper bound (can be None)
        step: look-around radius in initial step
        no_improve_thr, no_improv_break: break after no_improv_break iterations with an improvement lower than no_improv_thr
        max_iter: always break after this number of iterations. Set it to 0 to loop indefinitely.
        alpha:
        gamma:
        rho:
        sigma:

    Returns: xsol, fsol
    """

    # init
    dim = len(x_start)
    no_improv = 0
    prev_best = objective_function(x_start)
    res = [[x_start, prev_best]]
    for i in range(dim):
        x = copy.copy(x_start)
        x[i] = x[i] + step
        score = objective_function(x)
        res.append([x, score])

        # simplex iter
    iters = 0
    while 1:
        # order
        res.sort(key=lambda x: x[1])
        best = res[0][1]

        # optimize until a good-enough value has been reached
        if break_at_value:
            if best <= good_enough_value:
                return res[0]

        # break after max_iter
        if max_iter and iters >= max_iter:
            return res[0]
        iters += 1

        # break after no_improv_break iterations with no improvement
        if callback is not None:
            callback(best)

        if best < prev_best - no_improve_thr:
            no_improv = 0
            prev_best = best
        else:
            no_improv += 1

        if no_improv >= no_improv_break:
            return res[0]

        # centroid
        x0 = [0.] * dim
        for tup in res[:-1]:
            for i, c in enumerate(tup[0]):
                x0[i] += c / (len(res)-1)

        # reflection
        xr = x0 + alpha*(x0 - res[-1][0])
        rscore = objective_function(xr)
        if res[0][1] <= rscore < res[-2][1]:
            del res[-1]
            res.append([xr, rscore])
            continue

        # expansion
        if rscore < res[0][1]:
            xe = x0 + gamma*(x0 - res[-1][0])
            escore = objective_function(xe)
            if escore < rscore:
                del res[-1]
                res.append([xe, escore])
                continue
            else:
                del res[-1]
                res.append([xr, rscore])
                continue

        # contraction
        xc = x0 + rho*(x0 - res[-1][0])
        cscore = objective_function(xc)
        if cscore < res[-1][1]:
            del res[-1]
            res.append([xc, cscore])
            continue

        # reduction
        x1 = res[0][0]
        nres = []
        for tup in res:
            redx = x1 + sigma*(tup[0] - x1)
            score = objective_function(redx)
            nres.append([redx, score])
        res = nres


class AcOpfNelderMead:

    def __init__(self, multi_circuit: MultiCircuit, options: PowerFlowOptions, verbose=False, break_at_value=True,
                 good_enough_value=0):

        self.break_at_value = break_at_value
        self.good_enough_value = good_enough_value

        self.multi_circuit = multi_circuit

        self.numerical_circuit = self.multi_circuit.compile()

        self.calculation_inputs = self.numerical_circuit.compute(add_storage=False, add_generation=True)

        self.pf = PowerFlowMP(self.multi_circuit, options)

        # indices of generators that contribute to the static power vector 'S'
        self.gen_s_idx = np.where((np.logical_not(self.numerical_circuit.controlled_gen_dispatchable)
                                   * self.numerical_circuit.controlled_gen_enabled) == True)[0]

        self.bat_s_idx = np.where((np.logical_not(self.numerical_circuit.battery_dispatchable)
                                   * self.numerical_circuit.battery_enabled) == True)[0]

        # indices of generators that are to be optimized via the solution vector 'x'
        self.gen_x_idx = np.where((self.numerical_circuit.controlled_gen_dispatchable
                                   * self.numerical_circuit.controlled_gen_enabled) == True)[0]

        self.bat_x_idx = np.where((self.numerical_circuit.battery_dispatchable
                                   * self.numerical_circuit.battery_enabled) == True)[0]

        self.n_batteries = len(self.numerical_circuit.battery_power)
        self.n_controlled_gen = len(self.numerical_circuit.controlled_gen_power)

        # compute the problem dimension
        self.dim = len(self.gen_x_idx) + len(self.bat_x_idx)

        # get the limits of the devices to control
        gens = np.array(multi_circuit.get_controlled_generators())
        bats = np.array(multi_circuit.get_batteries())
        gen_x_up = np.array([elm.Pmax for elm in gens[self.gen_x_idx]])
        gen_x_low = np.array([elm.Pmin for elm in gens[self.gen_x_idx]])
        bat_x_up = np.array([elm.Pmax for elm in bats[self.bat_x_idx]])
        bat_x_low = np.array([elm.Pmin for elm in bats[self.bat_x_idx]])

        self.ngen = len(self.gen_x_idx)

        self.xlow = np.r_[gen_x_low, bat_x_low] / self.multi_circuit.Sbase
        self.xup = np.r_[gen_x_up, bat_x_up] / self.multi_circuit.Sbase
        self.range = self.xup - self.xlow

        # form S static ################################################################################################

        # all the loads apply
        self.Sfix = None
        self.set_default_state()  # build Sfix

        self.Vbus = np.ones(self.numerical_circuit.nbus, dtype=complex)
        self.Ibus = np.zeros(self.numerical_circuit.nbus, dtype=complex)

        # other vars needed ############################################################################################

        self.converged = False

        self.result = None

        self.force_batteries_to_charge = False

        self.x = np.zeros(self.dim)

        self.fx = 0

        self.t = 0

        self.Emin = None
        self.Emax = None
        self.E = None
        self.bat_idx = None
        self.battery_loading_pu = 0.01
        self.dt = 0

    def set_state(self, load_power, static_gen_power, controlled_gen_power, storage_power,
                  Emin=None, Emax=None, E=None, dt=0,
                  force_batteries_to_charge=False, bat_idx=None, battery_loading_pu=0.01):

        # all the loads apply
        self.Sfix = self.numerical_circuit.C_load_bus.T * (
                - load_power / self.numerical_circuit.Sbase * self.numerical_circuit.load_enabled)

        # static generators (all apply)
        self.Sfix += self.numerical_circuit.C_sta_gen_bus.T * (
                static_gen_power / self.numerical_circuit.Sbase * self.numerical_circuit.static_gen_enabled)

        # controlled generators
        self.Sfix += (self.numerical_circuit.C_ctrl_gen_bus[self.gen_s_idx, :]).T * (
                    controlled_gen_power / self.numerical_circuit.Sbase)

        # batteries
        self.Sfix += (self.numerical_circuit.C_batt_bus[self.bat_s_idx, :]).T * (
                       storage_power / self.numerical_circuit.Sbase)

        # batteries variables to control the energy
        self.force_batteries_to_charge = force_batteries_to_charge
        self.Emin = Emin
        self.Emax = Emax
        self.E = E
        self.dt = dt
        self.bat_idx = bat_idx
        self.battery_loading_pu = battery_loading_pu

    def set_default_state(self):
        """
        Set the default loading state
        """
        self.set_state(load_power=self.numerical_circuit.load_power,
                       static_gen_power=self.numerical_circuit.static_gen_power,
                       controlled_gen_power=self.numerical_circuit.controlled_gen_power[self.gen_s_idx],
                       storage_power=self.numerical_circuit.battery_power[self.bat_s_idx],
                       Emin=self.numerical_circuit.battery_Enom * self.numerical_circuit.battery_min_soc,
                       Emax=self.numerical_circuit.battery_Enom * self.numerical_circuit.battery_max_soc,
                       E=self.numerical_circuit.battery_Enom * self.numerical_circuit.battery_soc_0,
                       dt=1)

    def set_state_at(self, t, force_batteries_to_charge=False, bat_idx=None, battery_loading_pu=0.01,
                     Emin=None, Emax=None, E=None, dt=0):
        """
        Set the problem state at at time index
        Args:
            t:
            force_batteries_to_charge:
            bat_idx:
            battery_loading_pu:
            Emin:
            Emax:
            E:
            dt:

        Returns:

        """
        self.set_state(load_power=self.numerical_circuit.load_power_profile[t, :],
                       static_gen_power=self.numerical_circuit.static_gen_power_profile[t, :],
                       controlled_gen_power=self.numerical_circuit.controlled_gen_power_profile[t, self.gen_s_idx],
                       storage_power=self.numerical_circuit.battery_power_profile[t, self.bat_s_idx],
                       Emin=Emin, Emax=Emax, E=E, dt=dt,
                       force_batteries_to_charge=force_batteries_to_charge,
                       bat_idx=bat_idx,
                       battery_loading_pu=battery_loading_pu)

        self.t = t

    def build_solvers(self):
        pass

    def f_obj(self, x):

        # if self.force_batteries_to_charge:
        #     # assign a negative upper limit to force to charge
        #     x_up = self.xup
        #     x_up[self.ngen:] = self.xlow[self.ngen:] * self.battery_loading_pu
        # else:
        #     # use the normal limits
        #     x_up = self.xup

        # compute the penalty for x outside boundaries
        penalty_x = 0.0
        idx_up = np.where(x > self.xup)[0]
        penalty_x += (x[idx_up] - self.xup[idx_up]).sum()
        idx_low = np.where(x < self.xlow)[0]
        penalty_x += (self.xlow[idx_low] - x[idx_low]).sum()
        penalty_x *= 10  # add a lot of weight to the boundary penalty

        # modify the power injections (apply x)
        S = self.Sfix.copy()
        controlled_gen_power = x[0:self.ngen]
        storage_power = x[self.ngen:]
        S += (self.numerical_circuit.C_ctrl_gen_bus[self.gen_x_idx, :]).T * controlled_gen_power
        S += (self.numerical_circuit.C_batt_bus[self.bat_x_idx, :]).T * storage_power

        # compute the penalty for trespassing the energy boundaries
        E = self.E - storage_power * self.dt
        idx = np.where(E > self.Emax)[0]
        penalty_x += (E[idx] - self.Emax[idx]).sum()
        idx = np.where(E < self.Emin)[0]
        penalty_x += (self.Emin[idx] - E[idx]).sum()

        # run a power flow
        results = self.pf.run_multi_island(self.numerical_circuit, self.calculation_inputs, self.Vbus, S, self.Ibus)

        loading = np.abs(results.loading)

        # get the indices of the branches with overload
        idx = np.where(loading > 1)[0]

        # return the summation of the overload
        if len(idx) > 0:
            f = (loading[idx] - 1).sum()
            # print('objective', f, 'x', x)
            return f + penalty_x
        else:
            return penalty_x

    def solve(self, verbose=False):

        if verbose:
            callback = print
        else:
            callback = None

        x0 = np.zeros_like(self.x)

        # Run the optimization
        self.x, self.fx = nelder_mead(self.f_obj, x_start=x0, callback=callback,
                                      break_at_value=self.break_at_value,
                                      good_enough_value=self.good_enough_value, step=0.01)

        print('objective', self.fx, 'x', self.x)
        # modify the power injections
        S = self.Sfix.copy()
        controlled_gen_power = self.x[0:self.ngen]
        storage_power = self.x[self.ngen:]
        S += (self.numerical_circuit.C_ctrl_gen_bus[self.gen_x_idx, :]).T * controlled_gen_power
        S += (self.numerical_circuit.C_batt_bus[self.bat_x_idx, :]).T * storage_power

        # run a power flow
        pf_res = self.pf.run_multi_island(self.numerical_circuit, self.calculation_inputs,
                                          self.Vbus, S, self.Ibus)

        # declare the results
        self.result = OptimalPowerFlowResults(Sbus=pf_res.Sbus,
                                              voltage=pf_res.voltage,
                                              load_shedding=None,
                                              generation_shedding=None,
                                              battery_power=None,
                                              controlled_generation_power=None,
                                              Sbranch=pf_res.Sbranch,
                                              overloads=None,
                                              loading=pf_res.loading,
                                              converged=True)

        self.result.battery_power = np.zeros(self.n_batteries)
        self.result.battery_power[self.bat_x_idx] = self.x[self.ngen:]
        self.result.controlled_generation_power = np.zeros(self.n_controlled_gen)
        self.result.controlled_generation_power[self.gen_x_idx] = self.x[0:self.ngen]
        self.result.load_shedding = np.zeros_like(self.numerical_circuit.load_power)
        self.result.generation_shedding = np.zeros_like(self.numerical_circuit.controlled_gen_power)

        # overloads
        self.result.overloads = np.zeros_like(self.result.loading)
        loading = np.abs(self.result.loading)
        idx = np.where(loading > 1)[0]
        self.result.overloads[idx] = loading[idx] - 1

        self.converged = True

        return self.result

    def get_branch_flows(self):

        return self.result.Sbranch

    def get_load_shedding(self):

        return self.result.load_shedding

    def get_batteries_power(self):

        return self.result.battery_power

    def get_controlled_generation(self):

        return self.result.controlled_generation_power

    def get_generation_shedding(self):

        return self.result.generation_shedding

    def get_voltage(self):

        return self.result.voltage

    def get_overloads(self):

        return self.result.overloads

    def get_loading(self):

        return self.result.loading


def nelder_mead_test():

    # test
    import math
    import numpy as np

    def f(x):
        return math.sin(x[0]) * math.cos(x[1]) * (1. / (abs(x[2]) + 1))

    x0 = np.array([0., 0., 0.])
    LB = np.ones_like(x0) * -1
    UB = np.ones_like(x0) * 1
    x, fx = nelder_mead(f, x0, callback=print)

    print('Result')
    print(fx, '->', x)


if __name__ == "__main__":

    # nelder_mead_test()

    main_circuit = MultiCircuit()
    # fname = 'D:\\GitHub\\GridCal\\Grids_and_profiles\\grids\\IEEE 30 Bus with storage.xlsx'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 30 Bus with storage.xlsx'

    print('Reading...')
    main_circuit.load_file(fname)
    options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False,
                               initialize_with_existing_solution=False,
                               multi_core=False, dispatch_storage=True, control_q=False, control_p=True)

    problem = AcOpfNelderMead(main_circuit, options=options)

    res = problem.solve()

    print('Done!')
    print('Overloads')
    print(problem.get_overloads())

    pass