# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import time

import numpy as np

from GridCalEngine.DataStructures.numerical_circuit_general_pf import NumericalCircuit
from GridCalEngine.Topology.admittance_matrices import compile_y_acdc
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import control_q_inside_method
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.acdc_jacobian import fubm_jacobian, AcDcSolSlicer
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_acdc_fx,
                                                                                   compute_converter_losses,
                                                                                   compute_power, compute_zip_power)
from GridCalEngine.Utils.NumericalMethods.common import (ConvexMethodResult, ConvexFunctionResult)
from GridCalEngine.Utils.NumericalMethods.newton_raphson import newton_raphson
from GridCalEngine.enumerations import ReactivePowerControlMode
import GridCalEngine.Utils.NumericalMethods.sparse_solve as gcsp
from scipy.sparse import csr_matrix, csc_matrix
from GridCalEngine.basic_structures import Vec, CscMat, CxVec, IntVec, Logger


def NR_LS_GENERAL(nc: NumericalCircuit,
                  V0: CxVec,
                  S0: CxVec,
                  I0: CxVec,
                  Y0: CxVec,
                  tolerance=1e-6,
                  max_iter=4,
                  mu_0=1.0,
                  acceleration_parameter=0.05,
                  verbose=False,
                  control_q=ReactivePowerControlMode.NoControl,
                  pf_options=None) -> NumericPowerFlowResults:
    """
    Newton-Raphson Line search with the FUBM formulation
    :param nc: NumericalCircuit
    :param V0: Initial voltage solution
    :param S0: Power injections
    :param I0: Current injections
    :param Y0: Admittance injections
    :param tolerance: maximum error allowed
    :param max_iter: maximum number of iterations
    :param mu_0: Initial solution multiplier
    :param acceleration_parameter: Acceleration parameter (rate to decrease mu)
    :param verbose: Verbose?
    :param control_q: Reactive power control mode
    :param pf_options: PF options
    :return: NumericPowerFlowResults
    """
    start = time.time()

    '''
    Split the AC and DC subsystems
    '''
    Ybus = isolate_AC_DC(nc, nc.Ybus)
    print("Ybus")
    print(Ybus.todense())

    '''
    Initialising from and to powers, and tau and modulation
    '''
    p_from = np.zeros(nc.nbus)
    p_to = np.zeros(nc.nbus)
    q_from = np.zeros(nc.nbus)
    q_to = np.zeros(nc.nbus)
    p_zip = np.zeros(nc.nbus)
    q_zip = np.zeros(nc.nbus)
    modulations = np.ones(nc.nbus)
    taus = np.zeros(nc.nbus)
    Vm0 = np.abs(V0)
    Va0 = np.angle(V0)

    branch_from_indices = nc.branch_data.F
    branch_to_indices = nc.branch_data.T

    print("branch_from_indices full array")
    print(branch_from_indices)

    print("branch_to_indices full array")
    print(branch_to_indices)

    vsc_from_indices = nc.vsc_data.F
    vsc_to_indices = nc.vsc_data.T

    print("vsc_from_indices full array")
    print(vsc_from_indices)

    print("vsc_to_indices full array")
    print(vsc_to_indices)

    for i in range(len(nc.kn_pfrom_kdx)):
        print("(newtown_raphson_general.py) the from bus of the first pfrom kdx",
              branch_from_indices[nc.kn_pfrom_kdx[i]])
        print("(newtown_raphson_general.py) the setpoint of this", nc.kn_pfrom_setpoints[i])

    for i in range(len(nc.kn_qfrom_kdx)):
        print("(newtown_raphson_general.py) the from bus of the first qfrom kdx",
              branch_from_indices[nc.kn_qfrom_kdx[i]])
        print("(newtown_raphson_general.py) the setpoint of this", nc.kn_qfrom_setpoints[i])

    for i in range(len(nc.kn_pto_kdx)):
        print("(newtown_raphson_general.py) the to bus of the first pto kdx", branch_to_indices[nc.kn_pto_kdx[i]])
        print("(newtown_raphson_general.py) the setpoint of this", nc.kn_pto_setpoints[i])

    for i in range(len(nc.kn_qto_kdx)):
        print("(newtown_raphson_general.py) the to bus of the first qto kdx", branch_to_indices[nc.kn_qto_kdx[i]])
        print("(newtown_raphson_general.py) the setpoint of this", nc.kn_qto_setpoints[i])

    for i in range(len(nc.un_pfrom_kdx)):
        print("(newtown_raphson_general.py) known pfrom", branch_from_indices[nc.un_pfrom_kdx[i]])

    for i in range(len(nc.un_qfrom_kdx)):
        print("(newtown_raphson_general.py) known qfrom", branch_from_indices[nc.un_qfrom_kdx[i]])

    for i in range(len(nc.un_pto_kdx)):
        print("(newtown_raphson_general.py) known pto", branch_to_indices[nc.un_pto_kdx[i]])

    for i in range(len(nc.un_qto_kdx)):
        print("(newtown_raphson_general.py) known qto", branch_to_indices[nc.un_qto_kdx[i]])

    # Creating the known dictionary with checks for non-empty arrays
    known_dict = {
        'Voltage': {idx: val for idx, val in zip(nc.kn_volt_idx, nc.kn_volt_setpoints) if
                    len(nc.kn_volt_idx) > 0 and len(nc.kn_volt_setpoints) > 0},
        'Angle': {idx: val for idx, val in zip(nc.kn_angle_idx, nc.kn_angle_setpoints) if
                  len(nc.kn_angle_idx) > 0 and len(nc.kn_angle_setpoints) > 0},
        'Pzip': {idx: val for idx, val in zip(nc.kn_pzip_idx, nc.kn_pzip_setpoints) if
                 len(nc.kn_pzip_idx) > 0 and len(nc.kn_pzip_setpoints) > 0},
        'Qzip': {idx: val for idx, val in zip(nc.kn_qzip_idx, nc.kn_qzip_setpoints) if
                 len(nc.kn_qzip_idx) > 0 and len(nc.kn_qzip_setpoints) > 0},
        'Pfrom': {
            (branch_from_indices[nc.kn_pfrom_kdx[i]], branch_to_indices[nc.kn_pfrom_kdx[i]]): nc.kn_pfrom_setpoints[i]
            for i in range(len(nc.kn_pfrom_kdx)) if len(nc.kn_pfrom_setpoints) > 0},
        'Pto': {(branch_from_indices[nc.kn_pto_kdx[i]], branch_to_indices[nc.kn_pto_kdx[i]]): nc.kn_pto_setpoints[i] for
                i in range(len(nc.kn_pto_kdx)) if len(nc.kn_pto_setpoints) > 0},
        'Qfrom': {
            (branch_from_indices[nc.kn_qfrom_kdx[i]], branch_to_indices[nc.kn_qfrom_kdx[i]]): nc.kn_qfrom_setpoints[i]
            for i in range(len(nc.kn_qfrom_kdx)) if len(nc.kn_qfrom_setpoints) > 0},
        'Qto': {(branch_from_indices[nc.kn_qto_kdx[i]], branch_to_indices[nc.kn_qto_kdx[i]]): nc.kn_qto_setpoints[i] for
                i in range(len(nc.kn_qto_kdx)) if len(nc.kn_qto_setpoints) > 0},
        'Modulation': {
            (branch_from_indices[nc.kn_mod_kdx[i]], branch_to_indices[nc.kn_mod_kdx[i]]): nc.kn_mod_setpoints[i] for i
            in range(len(nc.kn_mod_kdx)) if len(nc.kn_mod_setpoints) > 0},
        'Tau': {(branch_from_indices[nc.kn_tau_kdx[i]], branch_to_indices[nc.kn_tau_kdx[i]]): nc.kn_tau_setpoints[i] for
                i in range(len(nc.kn_tau_kdx)) if len(nc.kn_tau_setpoints) > 0}
    }

    # Creating the unknown dictionary with similar checks
    unknown_dict = {
        'Voltage': {idx: '' for idx in nc.un_volt_idx if len(nc.un_volt_idx) > 0},
        'Angle': {idx: '' for idx in nc.un_angle_idx if len(nc.un_angle_idx) > 0},
        'Pzip': {idx: '' for idx in nc.un_pzip_idx if len(nc.un_pzip_idx) > 0},
        'Qzip': {idx: '' for idx in nc.un_qzip_idx if len(nc.un_qzip_idx) > 0},
        'Pfrom': {(branch_from_indices[nc.un_pfrom_kdx[i]], branch_to_indices[nc.un_pfrom_kdx[i]]): '' for i in
                  range(len(nc.un_pfrom_kdx)) if len(nc.un_pfrom_kdx) > 0},
        'Pto': {(branch_from_indices[nc.un_pto_kdx[i]], branch_to_indices[nc.un_pto_kdx[i]]): '' for i in
                range(len(nc.un_pto_kdx)) if len(nc.un_pto_kdx) > 0},
        'Qfrom': {(branch_from_indices[nc.un_qfrom_kdx[i]], branch_to_indices[nc.un_qfrom_kdx[i]]): '' for i in
                  range(len(nc.un_qfrom_kdx)) if len(nc.un_qfrom_kdx) > 0},
        'Qto': {(branch_from_indices[nc.un_qto_kdx[i]], branch_to_indices[nc.un_qto_kdx[i]]): '' for i in
                range(len(nc.un_qto_kdx)) if len(nc.un_qto_kdx) > 0},
        'Modulation': {(branch_from_indices[nc.un_mod_kdx[i]], branch_to_indices[nc.un_mod_kdx[i]]): '' for i in
                       range(len(nc.un_mod_kdx)) if len(nc.un_mod_kdx) > 0},
        'Tau': {(branch_from_indices[nc.un_tau_kdx[i]], branch_to_indices[nc.un_tau_kdx[i]]): '' for i in
                range(len(nc.un_tau_kdx)) if len(nc.un_tau_kdx) > 0}
    }

    # Passive branch dictionary remains empty as previously defined
    passive_branch_dict = {
        'Pfrom': {},
        'Pto': {},
        'Qfrom': {},
        'Qto': {}
    }

    print("known_dict: ", known_dict)
    print("unknown_dict: ", unknown_dict)
    print("passive_branch_dict: ", passive_branch_dict)

    '''
    Using known values, update setpoints
    '''
    Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus = update_setpoints(known_dict, nc,
                                                                                                         Vm0, Va0, S0,
                                                                                                         I0, Y0, p_from,
                                                                                                         p_to, q_from,
                                                                                                         q_to, p_zip,
                                                                                                         q_zip,
                                                                                                         modulations,
                                                                                                         taus,
                                                                                                         verbose=0)

    '''
    Create unknowns vector
    '''
    x0 = var2x_raiyan_ver2(unknown_dict, Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations,
                           taus, verbose=1)

    logger = Logger()

    ret: ConvexMethodResult = newton_raphson(func=pf_function_raiyan,
                                             func_args=(
                                             unknown_dict, passive_branch_dict, known_dict, Vm0, Va0, S0, I0, Y0, p_to,
                                             p_from, q_to, q_from, p_zip, q_zip, modulations, taus, nc.Ybus, nc,
                                             nc.dc_indices, nc.ac_indices),
                                             x0=x0,
                                             tol=pf_options.tolerance,
                                             max_iter=pf_options.max_iter,
                                             trust=pf_options.trust_radius,
                                             verbose=pf_options.verbose,
                                             logger=logger)

    Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus = update_setpoints(known_dict, nc,
                                                                                                         Vm0, Va0, S0,
                                                                                                         I0, Y0, p_from,
                                                                                                         p_to, q_from,
                                                                                                         q_to, p_zip,
                                                                                                         q_zip,
                                                                                                         modulations,
                                                                                                         taus,
                                                                                                         verbose=0)
    V = Vm0 * np.exp(1j * Va0)
    Scalc = compute_power(nc.Ybus, V)

    print("(newton_raphson_general.py) after compile information")
    print("(newton_raphson_general.py) nc.ac_indices", nc.ac_indices)
    print("(newton_raphson_general.py) nc.dc_indices", nc.dc_indices)

    print("(newton_raphson_general.py) vsc data")
    print("(newton_raphson_general.py) nc.vsc_data.F", nc.vsc_data.F)
    print("(newton_raphson_general.py) nc.vsc_data.T", nc.vsc_data.T)

    print("(newton_raphson_general.py) nc.vsc_data.branch_index", nc.vsc_data.branch_index)

    print("(newton_raphson_general.py) nc.kn_volt_idx")
    print(nc.kn_volt_idx)
    print(nc.kn_volt_setpoints)

    print("(newton_raphson_general.py) nc.kn_angle_idx")
    print(nc.kn_angle_idx)
    print(nc.kn_angle_setpoints)

    print("(newton_raphson_general.py) nc.kn_pzip_idx")
    print(nc.kn_pzip_idx)
    print(nc.kn_pzip_setpoints)

    print("(newton_raphson_general.py) nc.kn_qzip_idx")
    print(nc.kn_qzip_idx)
    print(nc.kn_qzip_setpoints)

    print("(newton_raphson_general.py) nc.kn_pfrom_kdx")
    print(nc.kn_pfrom_kdx)
    print(nc.kn_pfrom_setpoints)

    print("(newton_raphson_general.py) nc.kn_qfrom_kdx")
    print(nc.kn_qfrom_kdx)
    print(nc.kn_qfrom_setpoints)

    print("(newton_raphson_general.py) nc.kn_pto_kdx")
    print(nc.kn_pto_kdx)
    print(nc.kn_pto_setpoints)

    print("(newton_raphson_general.py) nc.kn_qto_kdx")
    print(nc.kn_qto_kdx)
    print(nc.kn_qto_setpoints)

    print("(newton_raphson_general.py) nc.kn_tau_kdx")
    print(nc.kn_tau_kdx)
    print(nc.kn_tau_setpoints)

    print("(newton_raphson_general.py) nc.kn_mod_kdx")
    print(nc.kn_mod_kdx)
    print(nc.kn_mod_setpoints)

    print("(newton_raphson_general.py) nc.kn_passive_pfrom_kdx")
    print(nc.kn_passive_pfrom_kdx)
    print(nc.kn_passive_pfrom_setpoints)

    print("(newton_raphson_general.py) nc.kn_passive_qfrom_kdx")
    print(nc.kn_passive_qfrom_kdx)
    print(nc.kn_passive_qfrom_setpoints)

    print("(newton_raphson_general.py) nc.kn_passive_pto_kdx")
    print(nc.kn_passive_pto_kdx)
    print(nc.kn_passive_pto_setpoints)

    print("(newton_raphson_general.py) nc.kn_passive_qto_kdx")
    print(nc.kn_passive_qto_kdx)
    print(nc.kn_passive_qto_setpoints)

    print("(newton_raphson_general.py) nc.un_volt_idx")
    print(nc.un_volt_idx)

    print("(newton_raphson_general.py) nc.un_angle_idx")
    print(nc.un_angle_idx)

    print("(newton_raphson_general.py) nc.un_pzip_idx")
    print(nc.un_pzip_idx)

    print("(newton_raphson_general.py) nc.un_qzip_idx")
    print(nc.un_qzip_idx)

    print("(newton_raphson_general.py) nc.un_pfrom_kdx")
    print(nc.un_pfrom_kdx)

    print("(newton_raphson_general.py) nc.un_qfrom_kdx")
    print(nc.un_qfrom_kdx)

    print("(newton_raphson_general.py) nc.un_pto_kdx")
    print(nc.un_pto_kdx)

    print("(newton_raphson_general.py) nc.un_qto_kdx")
    print(nc.un_qto_kdx)

    print("(newton_raphson_general.py) nc.un_tau_kdx")
    print(nc.un_tau_kdx)

    print("(newton_raphson_general.py) nc.un_mod_kdx")
    print(nc.un_mod_kdx)

    print("(newton_raphson_general.py) Voltages")
    for i in range(len(V)):
        print("Bus", i, ":", V[i])

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V=V, converged=ret.converged, norm_f=ret.error,
                                   Scalc=Scalc)


def isolate_AC_DC(nc, Ybus) -> csc_matrix:
    """
    Isolates the AC and DC components of a power nc within its admittance matrix.

    This function modifies the admittance matrix (Ybus) of a power nc to isolate the contributions of DC lines. It zeroes out the admittance values directly associated with DC lines and adjusts the matrix to account for the DC lines' resistances as conductances. This operation helps in analyzing the AC network components separately from DC elements.

    Parameters
    ----------
    nc : nc object
        An object representing the power nc, which includes AC and DC buses and lines.
    Ybus : csc_matrix
        The original sparse column-compressed admittance matrix of the nc.

    Returns
    -------
    csc_matrix
        The modified admittance matrix with the AC and DC components isolated.

    """
    _matrix = Ybus.copy()
    n = _matrix.shape[0]  # Assuming Ybus is square

    # iterate through and first delete anything that has to do with the dc_lines
    for i in range(len(nc.vsc_data.F)):
        # Get indices for the buses
        from_idx = nc.vsc_data.F[i]
        to_idx = nc.vsc_data.T[i]
        _z1 = _matrix[from_idx, to_idx]
        _z2 = _matrix[to_idx, from_idx]
        _matrix[from_idx, to_idx] = 0
        _matrix[to_idx, from_idx] = 0

    # set all diagonals to zero
    for i in range(n):
        _matrix[i, i] = 0

    # recalculate the diagonals
    for i in range(n):
        _matrix[i, i] = -np.sum(_matrix[i, :])

    # for elm in nc.dc_lines:
    #     # Get indices for the buses
    #     from_idx = nc.buses.index(elm.bus_from)
    #     to_idx = nc.buses.index(elm.bus_to)

    #     # print("from_idx: ", from_idx)
    #     # print("to_idx: ", to_idx)
    #     # print("R", elm.R)

    #     # Convert resistance to conductance?
    #     G = 1 / elm.R
    #     # G = elm.R

    #     # Subtract conductance from off-diagonal elements
    #     _matrix[from_idx, to_idx] -= G
    #     _matrix[to_idx, from_idx] -= G

    #     # Add conductance to diagonal elements
    #     _matrix[from_idx, from_idx] += G
    #     _matrix[to_idx, to_idx] += G

    # print("altered Ybus: ", _matrix.copy().todense())

    return _matrix


def update_setpoints(known_dict,
                     nc,
                     Vm0,
                     Va0,
                     S0,
                     I0,
                     Y0,
                     p_from,
                     p_to,
                     q_from,
                     q_to,
                     p_zip,
                     q_zip,
                     modulations,
                     taus,
                     verbose=0):
    """
    Updates the initial setpoints for various nc parameters based on the known values.

    This function takes a dictionary of known setpoints for different parameters (such as voltage magnitude, voltage angle, power flows, and others) and updates the corresponding initial guess arrays/lists for these parameters.

    Parameters
    ----------
    known_dict : dict
        A dictionary containing known setpoints for various parameters like 'Voltage', 'Angle', 'Pto', etc.
    nc : nc object
        The electrical nc object. Currently not used directly but required for future extensions or checks.
    Vm0, Va0 : list or np.array
        Initial guesses for voltage magnitudes and angles, respectively.
    S0, I0, Y0 : list or np.array
        Not directly updated but included for consistency and future use.
    p_from, p_to, q_from, q_to : list or np.array
        Lists containing initial guesses for active and reactive power flows from and to connected buses.
    p_zip, q_zip : list or np.array
        Lists containing initial guesses for active and reactive ZIP load injections at buses.
    modulations, taus : list or np.array
        Lists containing initial guesses for modulation values and time constants associated with dynamic components.
    verbose : int, optional
        If set to 1, prints updated arrays/lists after applying known setpoints.

    Returns
    -------
    tuple
        Returns a tuple containing updated arrays/lists for all input parameters, reflecting the known setpoints.
    """

    # Check and update 'Voltage' if it's present in known_dict
    if 'Voltage' in known_dict:
        for bus_index, voltage in known_dict['Voltage'].items():
            Vm0[bus_index] = voltage  # Update the voltage magnitude at the specified bus index

    # Check and update 'Angle' if it's present in known_dict
    if 'Angle' in known_dict:
        for bus_index, angle in known_dict['Angle'].items():
            Va0[bus_index] = angle  # Convert angle to radians and update

    if 'Pto' in known_dict:
        for bus_index, pto in known_dict['Pto'].items():
            # add the pto setpoint to the p_to list using the index
            p_to[bus_index[1]] = pto

    if 'Pfrom' in known_dict:
        for bus_index, pfrom in known_dict['Pfrom'].items():
            # add the pfrom setpoint to the p_from list using the index
            p_from[bus_index[0]] = pfrom

    if 'Qto' in known_dict:
        for bus_index, qto in known_dict['Qto'].items():
            # add the qto setpoint to the q_to list using the index
            q_to[bus_index[1]] = qto

    if 'Qfrom' in known_dict:
        for bus_index, qfrom in known_dict['Qfrom'].items():
            # add the qfrom setpoint to the q_from list using the index
            q_from[bus_index[0]] = qfrom

    if 'Pzip' in known_dict:
        for bus_index, pzip in known_dict['Pzip'].items():
            # add the pzip setpoint to the p_zip list using the index
            p_zip[bus_index] = pzip

    if 'Qzip' in known_dict:
        for bus_index, qzip in known_dict['Qzip'].items():
            # add the qzip setpoint to the q_zip list using the index
            q_zip[bus_index] = qzip

    if 'Modulation' in known_dict:
        for bus_index, modulation in known_dict['Modulation'].items():
            modulations[bus_index[0]] = modulation

    if 'Tau' in known_dict:
        for bus_index, tau in known_dict['Tau'].items():
            taus[bus_index[0]] = tau

    if verbose:
        print('Vm0 after updating known Voltage setpoints:', Vm0)
        print('Va0 after updating known Angle setpoints:', Va0)
        print('Pto after updating known Pto setpoints:', p_to)
        print('Pfrom after updating known Pfrom setpoints:', p_from)
        print('Qto after updating known Qto setpoints:', q_to)
        print('Qfrom after updating known Qfrom setpoints:', q_from)
        print('Pzip after updating known Pzip setpoints:', p_zip)
        print('Qzip after updating known Qzip setpoints:', q_zip)
        print('Modulation after updating known Modulation setpoints:', modulations)
        print('Tau after updating known Tau setpoints:', taus)
    return Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus


def pf_function_raiyan(x: Vec,
                       compute_jac: bool,
                       # these are the args:
                       unknown_dict: dict,
                       passive_branch_dict: dict,
                       known_dict: dict,
                       Vm0: Vec,
                       Va0: Vec,
                       S0: CxVec,
                       I0: CxVec,
                       Y0: CxVec,
                       p_to: Vec,
                       p_from: Vec,
                       q_to: Vec,
                       q_from: Vec,
                       p_zip: Vec,
                       q_zip: Vec,
                       modulations: Vec,
                       taus: Vec,
                       Ybus: CscMat,
                       nc: NumericalCircuit,
                       dc_buses: IntVec,
                       ac_buses) -> ConvexFunctionResult:
    Va = Va0.copy()
    Vm = Vm0.copy()
    Vm, Va, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus = x2var_raiyan_ver2(x, unknown_dict,
                                                                                                        Vm0, Va0, S0,
                                                                                                        I0, Y0, p_to,
                                                                                                        p_from, q_to,
                                                                                                        q_from, p_zip,
                                                                                                        q_zip,
                                                                                                        modulations,
                                                                                                        taus, verbose=0)
    V = Vm * np.exp(1j * Va)

    g = compute_g(V, Ybus, S0, I0, Y0, Vm, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, nc, dc_buses,
                  ac_buses, passive_branch_dict, known_dict)

    if compute_jac:
        Gx = compute_gx(x, g, Vm, Va, Ybus, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, nc,
                        dc_buses, ac_buses, unknown_dict, passive_branch_dict, known_dict)
    else:
        Gx = None

    return ConvexFunctionResult(f=g, J=Gx)


def compute_g(V, Ybus, S0, I0, Y0, Vm, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, nc, dc_buses,
              ac_buses, passive_branch_dict, known_dict) -> Vec:
    """
    Compose the power flow function
    :param V:
    :param Ybus:
    :param S0:
    :param I0:
    :param Y0:
    :param Vm:
    :param pq:
    :param pvpq:
    :return:
    """
    Sbus = compute_zip_power(S0, I0, Y0, Vm)
    Scalc = compute_power(Ybus, V)

    # mapping of bus-VSC and bus-trafo
    vsc_frombus = nc.vsc_data.F
    vsc_tobus = nc.vsc_data.T
    controllable_trafo_frombus = np.zeros((0))
    controllable_trafo_tobus = np.zeros((0))
    controllable_trafo_yshunt = np.zeros((0))
    controllable_trafo_yseries = np.zeros((0))

    g = compute_fx_raiyan(Scalc, Sbus, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, dc_buses, ac_buses,
                          vsc_frombus, vsc_tobus, controllable_trafo_frombus, controllable_trafo_tobus,
                          controllable_trafo_yshunt, controllable_trafo_yseries, V, passive_branch_dict, known_dict,
                          Ybus)
    return g


def compute_gx(x, fx, Vm, Va, Ybus, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, nc,
               dc_buses, ac_buses, unknown_dict, passive_branch_dict, known_dict) -> CscMat:
    delta = 1e-6
    x1 = x.copy()
    J = np.zeros((len(x), len(x)), dtype=float)
    for i in range(len(x)):
        '''
        Make a deepcopy and alter the ith element
        '''
        x1 = np.array(x.copy())
        Va_after = np.array(Va.copy())
        Vm_after = np.array(Vm.copy())
        p_to_after = np.array(p_to.copy())
        p_from_after = np.array(p_from.copy())
        q_to_after = np.array(q_to.copy())
        q_from_after = np.array(q_from.copy())
        p_zip_after = np.array(p_zip.copy())
        q_zip_after = np.array(q_zip.copy())
        modulations_after = np.array(modulations.copy())
        taus_after = np.array(taus.copy())
        x1[i] += delta

        '''
        Put the unknowns back into their vectors
        '''
        Vm_after, Va_after, S0, I0, Y0, p_to_after, p_from_after, q_to_after, q_from_after, p_zip_after, q_zip_after, modulations_after, taus_after = x2var_raiyan_ver2(
            x1, unknown_dict, Vm_after, Va_after, S0, I0, Y0, p_to_after, p_from_after, q_to_after, q_from_after,
            p_zip_after, q_zip_after, modulations_after, taus_after, verbose=0)

        '''
        Calculate powers
        '''
        V = Vm_after * np.exp(1j * Va_after)
        Sbus = compute_zip_power(S0, I0, Y0, Vm)
        Scalc = compute_power(Ybus, V)

        '''
        Get the difference in the vectors and append to J
        '''
        # move this outside maybe? get mapping between bus-vsc and bus-trafo
        vsc_frombus = nc.vsc_data.F
        vsc_tobus = nc.vsc_data.T
        controllable_trafo_frombus = np.zeros((0))
        controllable_trafo_tobus = np.zeros((0))
        controllable_trafo_yshunt = np.zeros((0))
        controllable_trafo_yseries = np.zeros((0))

        fx_altered = compute_fx_raiyan(Scalc, Sbus, p_to_after, p_from_after, q_to_after, q_from_after, p_zip_after,
                                       q_zip_after, modulations_after, taus_after, dc_buses, ac_buses, vsc_frombus,
                                       vsc_tobus, controllable_trafo_frombus, controllable_trafo_tobus,
                                       controllable_trafo_yshunt, controllable_trafo_yseries, V, passive_branch_dict,
                                       known_dict, Ybus)
        diff = (fx_altered - fx) / delta
        J[:, i] = diff

    # print("(newton_raphson_general.py) J: ")
    # print(J)
    # make a df of J
    # import pandas as pd
    # df = pd.DataFrame(J)
    # listOfFuncs =  ['DC Real Bus:3', 'DC Real Bus:4', 'DC Real Bus:5', 'AC Real Bus:0', 'AC Imag Bus:0', 'AC Real Bus:1', 'AC Imag Bus:1', 'AC Real Bus:2', 'AC Imag Bus:2', 'AC Real Bus:6', 'AC Imag Bus:6', 'AC Real Bus:7', 'AC Imag Bus:7', 'AC Real Bus:8', 'AC Imag Bus:8', 'AC Real Bus:9', 'AC Imag Bus:9', 'VSC Active Power Balance:32', 'VSC Active Power Balance:56', 'Trafo Active Power From:8', 'Trafo Active Power From:8', 'Trafo Reactive Power To:9', 'Trafo Reactive Power To:9']
    # df.index = listOfFuncs
    # df.columns = ['V_1', 'V_2', 'V_4', 'V_5', 'V_7', 'V_8', 'Angle_1', 'Angle_2', 'Angle_6', 'Angle_7', 'Angle_8', 'Pzip_0', 'Pzip_9', 'Qzip_0', 'Qzip_9', 'Pfrom_3', 'Pfrom_5', 'Pfrom_8', 'Pto_2', 'Pto_6', 'Qfrom_8', 'Qto_9', 'Mod_8']

    return csr_matrix((J), shape=(len(x), len(x))).tocsc()


def compute_fx_raiyan(Scalc, Sbus, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, dc_buses, ac_buses,
                      vsc_frombus, vsc_tobus, controllable_trafo_frombus, controllable_trafo_tobus,
                      controllable_trafo_yshunt, controllable_trafo_yseries, V, passive_branch_dict, known_dict,
                      Ybus) -> Vec:
    """
    Compute the NR-like error function
    :param Scalc: Calculated power injections
    :param Sbus: Specified power injections
    :return: error
    """
    a = 0.00010000
    b = 0.01500000
    c = 0.20000000

    fx = []
    listOfFuncs = []

    '''
    DC bus active power balance
    '''
    for bus in dc_buses:
        fx.append(Scalc[bus].real - Sbus[bus].real + p_to[bus] + p_from[bus] - p_zip[bus])
        listOfFuncs.append("DC Real Bus:" + str(bus))

    '''
    AC bus active and reactive power balance
    '''
    for bus in ac_buses:
        fx.append(Scalc[bus].real - Sbus[bus].real + p_to[bus] + p_from[bus] - p_zip[bus])
        fx.append(Scalc[bus].imag - Sbus[bus].imag + q_to[bus] + q_from[bus] - q_zip[bus])
        listOfFuncs.append("AC Real Bus:" + str(bus))
        listOfFuncs.append("AC Imag Bus:" + str(bus))

    '''
    VSC active power balance
    '''
    Vm = np.abs(V)
    for busfrom, busTo in zip(vsc_frombus, vsc_tobus):
        _loss = (p_to[busTo] ** 2 + q_to[busTo] ** 2) ** 0.5 / Vm[busTo]
        fx.append(a + b * _loss + c * _loss ** 2 - p_to[busTo] - p_from[busfrom])
        listOfFuncs.append("VSC Active Power Balance:" + str(busfrom) + str(busTo))

    '''
    Trafo from and to bus active and reactive power balance
    '''
    for i in range(len(controllable_trafo_frombus)):
        # right what are we going to do here, we need to form four equations
        _a = Vm[controllable_trafo_frombus[i]] ** 2 * (
                    np.conj(controllable_trafo_yseries[i]) + np.conj(controllable_trafo_yshunt[i])) / modulations[
                 controllable_trafo_frombus[i]] ** 2
        _b = V[controllable_trafo_frombus[i]] * np.conj(V[controllable_trafo_tobus[i]]) * np.conj(
            controllable_trafo_yseries[i]) / (
                         modulations[controllable_trafo_frombus[i]] * np.exp(1j * taus[controllable_trafo_frombus[i]]))
        Sfrom = _a - _b
        _c = Vm[controllable_trafo_tobus[i]] ** 2 * (
                    np.conj(controllable_trafo_yseries[i]) + np.conj(controllable_trafo_yshunt[i]))
        _d = V[controllable_trafo_tobus[i]] * np.conj(V[controllable_trafo_frombus[i]]) * np.conj(
            controllable_trafo_yseries[i]) / (
                         modulations[controllable_trafo_frombus[i]] * np.exp(-1j * taus[controllable_trafo_frombus[i]]))
        Sto = _c - _d

        fx.append(Sfrom.real - p_from[controllable_trafo_frombus[i]])
        fx.append(Sto.real - p_to[controllable_trafo_tobus[i]])
        fx.append(Sfrom.imag - q_from[controllable_trafo_frombus[i]])
        fx.append(Sto.imag - q_to[controllable_trafo_tobus[i]])

        listOfFuncs.append("Trafo Active Power From:" + str(controllable_trafo_frombus[i]))
        listOfFuncs.append("Trafo Active Power From:" + str(controllable_trafo_frombus[i]))
        listOfFuncs.append("Trafo Reactive Power To:" + str(controllable_trafo_tobus[i]))
        listOfFuncs.append("Trafo Reactive Power To:" + str(controllable_trafo_tobus[i]))

    if len(passive_branch_dict["Pfrom"]):
        for key, value in passive_branch_dict["Pfrom"].items():
            print("Passive Branch Active Power From:")
            print("Key: ", key)
            print("Value: ", value)
            from_bus = key[0]
            to_bus = key[1]
            _a = value - (V[from_bus] * (V[from_bus] - V[to_bus]) * np.conj(Ybus[from_bus, to_bus])).real
            fx.append(_a)

    if len(passive_branch_dict["Pto"]):
        for key, value in passive_branch_dict["Pto"].items():
            print("Passive Branch Active Power To:")
            print("Key: ", key)
            print("Value: ", value)
            from_bus = key[0]
            to_bus = key[1]
            _a = value - (V[to_bus] * (V[to_bus] - V[from_bus]) * np.conj(Ybus[to_bus, from_bus])).real
            fx.append(_a)

    if len(passive_branch_dict["Qfrom"]):
        for key, value in passive_branch_dict["Qfrom"].items():
            print("Passive Branch Reactive Power From:")
            print("Key: ", key)
            print("Value: ", value)
            from_bus = key[0]
            to_bus = key[1]
            _a = value - (V[from_bus] * (V[from_bus] - V[to_bus]) * np.conj(Ybus[from_bus, to_bus])).imag
            fx.append(_a)

    if len(passive_branch_dict["Qto"]):
        for key, value in passive_branch_dict["Qto"].items():
            print("Passive Branch Reactive Power To:")
            print("Key: ", key)
            print("Value: ", value)
            from_bus = key[0]
            to_bus = key[1]
            _a = value - (V[to_bus] * (V[to_bus] - V[from_bus]) * np.conj(Ybus[to_bus, from_bus])).imag
            fx.append(_a)

    # DO NOT DELETE THIS LINE: nb has does not do well with loops
    for i in range(1):
        pass

    return np.array(fx)


def x2var_raiyan_ver2(x0,
                      unknown_dict,
                      Vm0, Va0,
                      S0, I0, Y0,
                      p_to, p_from, q_to, q_from,
                      p_zip, q_zip,
                      modulations,
                      taus,
                      verbose=1):
    """
    Arrange the unknowns vector into the physical variables
    """

    # Initialize an index for x0
    x0_index = 0

    # Process Voltage and Angle which are directly indexed
    if 'Voltage' in unknown_dict:
        for bus_index in unknown_dict['Voltage']:
            Vm0[bus_index] = x0[x0_index]
            x0_index += 1
    if 'Angle' in unknown_dict:
        for bus_index in unknown_dict['Angle']:
            Va0[bus_index] = x0[x0_index]
            x0_index += 1

    # Assuming similar direct indexing for Pzip, Qzip, Modulation, and Tau
    if 'Pzip' in unknown_dict:
        for bus_index in unknown_dict['Pzip']:
            p_zip[bus_index] = x0[x0_index]
            x0_index += 1
    if 'Qzip' in unknown_dict:
        for bus_index in unknown_dict['Qzip']:
            q_zip[bus_index] = x0[x0_index]
            x0_index += 1

    # Process other parameters which might involve tuple keys
    # For tuples, use the specified index for p_from/p_to and q_from/q_to
    for category, items in unknown_dict.items():
        if category in ['Pfrom', 'Pto', 'Qfrom', 'Qto', 'Modulation', 'Tau']:
            for bus_indices in items:
                if category == 'Pfrom':
                    p_from[bus_indices[0]] = x0[x0_index]
                elif category == 'Pto':
                    p_to[bus_indices[1]] = x0[x0_index]
                elif category == 'Qfrom':
                    q_from[bus_indices[0]] = x0[x0_index]
                elif category == 'Qto':
                    q_to[bus_indices[1]] = x0[x0_index]
                elif category == 'Modulation':
                    modulations[bus_indices[0]] = x0[x0_index]
                elif category == 'Tau':
                    taus[bus_indices[0]] = x0[x0_index]
                    # raise an aerror
                x0_index += 1

    if verbose:
        # Print updated values
        print("Updated Vm0: ", Vm0)
        print("Updated Va0: ", Va0)
        print("Updated p_to: ", p_to)
        print("Updated p_from: ", p_from)
        print("Updated q_to: ", q_to)
        print("Updated q_from: ", q_from)
        print("Updated p_zip: ", p_zip)
        print("Updated q_zip: ", q_zip)
        print("Updated modulations: ", modulations)
        print("Updated taus: ", taus)

    # Return the updated arrays
    return Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus


def var2x_raiyan_ver2(unknown_dict, Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus,
                      verbose=0):
    """
    Converts variable parameters into a vector form based on a dictionary of unknowns.

    This function takes various electrical network parameters and a dictionary specifying which of these parameters are unknown. It then constructs a vector `x` that contains the values of these unknown parameters for use in optimization or analysis processes. Additionally, it generates a list of names `x_names` corresponding to each entry in `x` for identification.

    Parameters
    ----------
    unknown_dict : dict
        A dictionary with keys corresponding to parameter types (e.g., 'Voltage', 'Angle') and values being lists of indices or tuples indicating which parameters are unknown.
    Vm0, Va0 : list or np.array
        Lists containing initial guesses or values for voltage magnitudes and angles, respectively.
    S0, I0, Y0 : list or np.array
        Lists containing initial values for power, current, and admittance injections at buses (not directly used but included for completeness and future extensions).
    p_to, p_from, q_to, q_from : list or np.array
        Lists containing power flow values to and from connected buses.
    p_zip, q_zip : list or np.array
        Lists containing ZIP load injections at buses.
    modulations, taus : list or np.array
        Lists containing modulation variables and time constants associated with dynamic elements of the network.
    verbose : int, optional
        If set to 1, prints detailed information about the constructed vector `x` and its identifiers `x_names`.

    Returns
    -------
    list
        The vector `x` containing values for the unknown parameters as specified in `unknown_dict`.
    """

    x = []
    x_names = []

    if 'Voltage' in unknown_dict:
        for bus_index in unknown_dict['Voltage']:
            x.append(Vm0[bus_index])
            x_names.append(f'Voltage_{bus_index}')

    if 'Angle' in unknown_dict:
        for bus_index in unknown_dict['Angle']:
            x.append(Va0[bus_index])
            x_names.append(f'Angle_{bus_index}')

    if 'Pzip' in unknown_dict:
        for bus_index in unknown_dict['Pzip']:
            x.append(p_zip[bus_index])
            x_names.append(f'Pzip_{bus_index}')

    if 'Qzip' in unknown_dict:
        for bus_index in unknown_dict['Qzip']:
            x.append(q_zip[bus_index])
            x_names.append(f'Qzip_{bus_index}')

    if 'Pfrom' in unknown_dict:
        for bus_indices in unknown_dict['Pfrom']:
            x.append(p_from[bus_indices[0]])
            x_names.append(f'Pfrom_{bus_indices[0]}')

    if 'Pto' in unknown_dict:
        for bus_indices in unknown_dict['Pto']:
            x.append(p_to[bus_indices[1]])
            x_names.append(f'Pto_{bus_indices[1]}')

    if 'Qfrom' in unknown_dict:
        for bus_indices in unknown_dict['Qfrom']:
            x.append(q_from[bus_indices[0]])
            x_names.append(f'Qfrom_{bus_indices[0]}')

    if 'Qto' in unknown_dict:
        for bus_indices in unknown_dict['Qto']:
            x.append(q_to[bus_indices[1]])
            x_names.append(f'Qto_{bus_indices[1]}')

    if 'Modulation' in unknown_dict:
        for bus_indices in unknown_dict['Modulation']:
            x.append(modulations[bus_indices[0]])
            x_names.append(f'Modulation_{bus_indices[0]}')

    if 'Tau' in unknown_dict:
        for bus_indices in unknown_dict['Tau']:
            x.append(taus[bus_indices[0]])
            x_names.append(f'Tau_{bus_indices[0]}')

    if verbose:
        print('Unknowns vector x:', x)
        print('Identifiers of x:', x_names)
        print('Length of x:', len(x))

    return x
