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
import numba as nb
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
    :return: NumericPowerFlowResults
    """
    start = time.time()

    '''
    Split the AC and DC subsystems
    '''
    Ybus = nc.Ybus
    Ybus = isolate_AC_DC(nc, nc.Ybus)    

    '''
    Remove the generator powers from S0
    '''
    S0 = remove_gen_from_zip(S0, nc)

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

    '''
    Using known values, update setpoints
    '''
    Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus = update_setpoints(nc, Vm0, Va0, S0, I0, Y0, p_from, p_to, q_from, q_to, p_zip, q_zip, modulations, taus, verbose = 0)
    p_zip = update_zips(nc.nbus, p_zip, nc.kn_pzip_idx, nc.kn_pzip_setpoints)
    q_zip = update_zips(nc.nbus, q_zip, nc.kn_qzip_idx, nc.kn_qzip_setpoints)


    '''
    Create unknowns vector
    '''
    x0 = var2x(nc)
    logger = Logger()

    ret: ConvexMethodResult = newton_raphson(func=pf_function_raiyan,
                                                func_args=(Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, Ybus, nc),
                                                x0=x0,
                                                tol=pf_options.tolerance,
                                                max_iter=pf_options.max_iter,
                                                trust=pf_options.trust_radius,
                                                verbose=pf_options.verbose,
                                                logger= logger)

    # Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus  = update_setpoints(known_dict, nc, Vm0, Va0, S0, I0, Y0, p_from, p_to, q_from, q_to, p_zip, q_zip, modulations, taus, verbose = 0)
    Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus = update_setpoints(nc, Vm0, Va0, S0, I0, Y0, p_from, p_to, q_from, q_to, p_zip, q_zip, modulations, taus, verbose = 0)
    p_zip = update_zips(nc.nbus, p_zip, nc.kn_pzip_idx, nc.kn_pzip_setpoints)
    q_zip = update_zips(nc.nbus, q_zip, nc.kn_qzip_idx, nc.kn_qzip_setpoints)
    V = Vm0 * np.exp(1j * Va0)
    Scalc = compute_power(Ybus, V)

    # print("(newton_raphson_general.py) p_zip after running algo")
    # print(p_zip)

    # print("(newton_raphson_general.py) q_zip after running algo")
    # print(q_zip)


    # print("(newton_raphson_general.py) after compile information")
    # print("(newton_raphson_general.py) nc.ac_indices", nc.ac_indices)
    # print("(newton_raphson_general.py) nc.dc_indices", nc.dc_indices)

    # print("(newton_raphson_general.py) vsc data")
    # print("(newton_raphson_general.py) nc.vsc_data.F", nc.vsc_data.F)
    # print("(newton_raphson_general.py) nc.vsc_data.T", nc.vsc_data.T)

    # print("(newton_raphson_general.py) nc.vsc_data.branch_index", nc.vsc_data.branch_index)

    # print("(newton_raphson_general.py) nc.kn_volt_idx")
    # print(nc.kn_volt_idx)
    # print(nc.kn_volt_setpoints)

    # print("(newton_raphson_general.py) nc.kn_angle_idx")
    # print(nc.kn_angle_idx)
    # print(nc.kn_angle_setpoints)

    # print("(newton_raphson_general.py) nc.kn_pzip_idx")
    # print(nc.kn_pzip_idx)
    # print(nc.kn_pzip_setpoints)

    # print("(newton_raphson_general.py) create_gen_connection_matrix")
    # print(create_zip2bus_connection_matrix(nc.nbus, nc.kn_pzip_idx))
    # print("active power contribution to the bus", np.dot(create_zip2bus_connection_matrix(nc.nbus, nc.kn_pzip_idx), nc.kn_pzip_setpoints))

    # print("(newton_raphson_general.py) reactive power matrix")
    # print(create_zip2bus_connection_matrix(nc.nbus, nc.kn_qzip_idx))
    # print("reactive power contribution to the bus", np.dot(create_zip2bus_connection_matrix(nc.nbus, nc.kn_qzip_idx), nc.kn_qzip_setpoints))

    # print("(newton_raphson_general.py) nc.kn_qzip_idx")
    # print(nc.kn_qzip_idx)
    # print("(newton_raphson_general.py) nc.kn_qzip_setpoints")
    # print(nc.kn_qzip_setpoints)

    # print("(newton_raphson_general.py) nc.kn_pfrom_kdx")
    # print(nc.kn_pfrom_kdx)
    # print("(newton_raphson_general.py) nc.kn_pfrom_setpoints")
    # print(nc.kn_pfrom_setpoints)

    # print("(newton_raphson_general.py) nc.kn_qfrom_kdx")
    # print(nc.kn_qfrom_kdx)
    # print("(newton_raphson_general.py) nc.kn_qfrom_setpoints")
    # print(nc.kn_qfrom_setpoints)

    # print("(newton_raphson_general.py) nc.kn_pto_kdx")
    # print(nc.kn_pto_kdx)
    # print("(newton_raphson_general.py) nc.kn_pto_setpoints")
    # print(nc.kn_pto_setpoints)

    # print("(newton_raphson_general.py) nc.kn_qto_kdx")
    # print(nc.kn_qto_kdx)
    # print("(newton_raphson_general.py) nc.kn_qto_setpoints")
    # print(nc.kn_qto_setpoints)

    # print("(newton_raphson_general.py) nc.kn_tau_kdx")
    # print(nc.kn_tau_kdx)
    # print("(newton_raphson_general.py) nc.kn_tau_setpoints")
    # print(nc.kn_tau_setpoints)

    # print("(newton_raphson_general.py) nc.kn_mod_kdx")
    # print(nc.kn_mod_kdx)
    # print("(newton_raphson_general.py) nc.kn_mod_setpoints")
    # print(nc.kn_mod_setpoints)

    # print("(newton_raphson_general.py) nc.kn_passive_pfrom_kdx")
    # print(nc.kn_passive_pfrom_kdx)
    # print("(newton_raphson_general.py) nc.kn_passive_pfrom_setpoints")
    # print(nc.kn_passive_pfrom_setpoints)

    # print("(newton_raphson_general.py) nc.kn_passive_qfrom_kdx")
    # print(nc.kn_passive_qfrom_kdx)
    # print("(newton_raphson_general.py) nc.kn_passive_qfrom_setpoints")
    # print(nc.kn_passive_qfrom_setpoints)

    # print("(newton_raphson_general.py) nc.kn_passive_pto_kdx")
    # print(nc.kn_passive_pto_kdx)
    # print("(newton_raphson_general.py) nc.kn_passive_pto_setpoints")
    # print(nc.kn_passive_pto_setpoints)

    # print("(newton_raphson_general.py) nc.kn_passive_qto_kdx")
    # print(nc.kn_passive_qto_kdx)
    # print("(newton_raphson_general.py) nc.kn_passive_qto_setpoints")
    # print(nc.kn_passive_qto_setpoints)

    # print("(newton_raphson_general.py) nc.un_volt_idx")
    # print(nc.un_volt_idx)

    # print("(newton_raphson_general.py) nc.un_angle_idx")
    # print(nc.un_angle_idx)

    # print("(newton_raphson_general.py) nc.un_pzip_idx")
    # print(nc.un_pzip_idx)

    # print("(newton_raphson_general.py) nc.un_qzip_idx")
    # print(nc.un_qzip_idx)

    # print("(newton_raphson_general.py) nc.un_pfrom_kdx")
    # print(nc.un_pfrom_kdx)

    # print("(newton_raphson_general.py) nc.un_qfrom_kdx")
    # print(nc.un_qfrom_kdx)

    # print("(newton_raphson_general.py) nc.un_pto_kdx")
    # print(nc.un_pto_kdx)

    # print("(newton_raphson_general.py) nc.un_qto_kdx")
    # print(nc.un_qto_kdx)

    # print("(newton_raphson_general.py) nc.un_tau_kdx")
    # print(nc.un_tau_kdx)

    # print("(newton_raphson_general.py) nc.un_mod_kdx")
    # print(nc.un_mod_kdx)    

    end = time.time()
    elapsed = end - start

    # if ret.converged == False:
    #     #raise an exception that says the power flow did not converge
    #     raise Exception("Power flow did not converge")



    results = NumericPowerFlowResults(V=V, converged=ret.converged, norm_f=ret.error,
                                   Scalc=Scalc)
    
    results.converged = ret.converged
    return results


def update_zips(nbus, p_zip, pzip_keys, pzip_values):
    """
    Updates the p_zip vector with non-zero contributions from specified Pzip values.

    Parameters:
    nbus : int
        The number of buses.
    p_zip : np.array
        Original p_zip vector that needs to be updated.
    pzip_keys : iterable
        Keys indicating bus indices for Pzip values.
    pzip_values : iterable
        Pzip values corresponding to the keys.

    Returns:
    np.array
        Updated p_zip vector.
    """
    # Create the connection matrix for Pzip contributions
    connection_matrix = create_zip2bus_connection_matrix(nbus, pzip_keys)
    
    # Calculate the new contributions using dot product
    new_contributions = np.dot(connection_matrix, np.array(pzip_values))

    # Create a mask where the contributions are non-zero
    non_zero_mask = new_contributions != 0

    # Update the original p_zip vector only at positions where there are non-zero contributions
    p_zip[non_zero_mask] = new_contributions[non_zero_mask]

    return p_zip


def create_zip2bus_connection_matrix(nbus, zip_idx):
    """
    Create a binary connection matrix indicating which generators are connected to which buses.

    Parameters:
    nbus : int
        The number of buses in the system.
    kn_pzip_idx : list or np.array
        The indices of buses where each generator contributes power.

    Returns:
    np.array
        A binary matrix of shape (nbus, number of generators) where each column represents a generator
        and a '1' in a row indicates that the generator is connected to that bus.
    """
    # Number of generators is the length of the kn_pzip_idx array
    num_generators = len(zip_idx)
    
    # Initialize the matrix with zeros
    matrix = np.zeros((nbus, num_generators), dtype=int)
    
    # Populate the matrix with 1s indicating connections
    for i in range(num_generators):
        bus_index = zip_idx[i]
        matrix[bus_index, i] = 1

    return matrix



def remove_gen_from_zip(S0: CxVec,
                        nc: NumericalCircuit) -> CxVec:
    """
    Removes the generator powers from the ZIP load injections.

    This function removes the generator powers from the ZIP load injections to ensure that the generator powers are not included in the ZIP load calculations.

    Parameters
    ----------
    S0 : CxVec
        The power injections vector.
    nc : NumericalCircuit
        The numerical circuit object.

    Returns
    -------
    CxVec
        The updated power injections vector with generator powers removed.

    """
    # print("(newton_raphson_general.py) nc.generator_data.bus_idx")
    # print(nc.generator_data.bus_idx)
    S0 = S0.copy()
    for i, genIdx in enumerate(nc.generator_data.bus_idx):
        # print("(newton_raphson_general.py) i", i)
        # print("(newton_raphson_general.py) genIdx", genIdx)
        # print("(newton_raphson_general.py) active power", nc.generator_data.p[i])
        # print("(newton_raphson_general.py) power factor", nc.generator_data.pf[i])
        # print("(newton_raphson_general.py) reactive power", p2q(nc.generator_data.p[i], nc.generator_data.pf[i]))
        #convert nc.generator_data.p[i] to pu
        _activePower = nc.generator_data.p[i]/nc.Sbase
        _reactivePower = p2q(nc.generator_data.p[i], nc.generator_data.pf[i])/nc.Sbase
        S0[genIdx] -= _activePower + 1j * _reactivePower
    return S0


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
    # if nc.vsc_from_indices is empty, return the original Ybus
    if len(nc.vsc_data.F) == 0:
        return Ybus
    
    _matrix = Ybus.copy()
    n = _matrix.shape[0]  # Assuming Ybus is square

    #iterate through and first delete anything that has to do with the dc_lines
    for i in range(len(nc.vsc_data.F)):
        # Get indices for the buses
        from_idx = nc.vsc_data.F[i]
        to_idx = nc.vsc_data.T[i]
        _z1 = _matrix[from_idx, to_idx]
        _z2 = _matrix[to_idx, from_idx]
        _matrix[from_idx, to_idx] = 0
        _matrix[to_idx, from_idx] = 0
        #minus off _z1 and _z2 from the diagonals
        _matrix[from_idx, from_idx] += _z1
        _matrix[to_idx, to_idx] += _z2

        
    #set all diagonals to zero
    # for i in range(n):
    #     _matrix[i, i] = 0
    
    #recalculate the diagonals
    # for i in range(n):
    #     _matrix[i, i] = -np.sum(_matrix[i, :])



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

def p2q(p, pf):
    """
    Convert active power to reactive power based on power factor.

    This function converts active power to reactive power based on the power factor provided.

    Parameters
    ----------
    p : float
        The active power value.
    pf : float
        The power factor value.

    Returns
    -------
    float
        The reactive power value corresponding to the active power and power factor.

    """
    return p * np.tan(np.arccos(pf))


def update_setpoints(nc, Vm0, Va0, S0, I0, Y0, p_from, p_to, q_from, q_to, p_zip, q_zip, modulations, taus, verbose=0):
    """
    Updates the initial setpoints for various nc parameters based on known values stored in index and setpoint arrays.
    Uses numpy for efficient slicing and batch updating.
    """
    # Ensure all input arrays are numpy arrays for efficient slicing
    Vm0 = np.asarray(Vm0)
    Va0 = np.asarray(Va0)
    p_from = np.asarray(p_from)
    p_to = np.asarray(p_to)
    q_from = np.asarray(q_from)
    q_to = np.asarray(q_to)
    p_zip = np.asarray(p_zip)
    q_zip = np.asarray(q_zip)
    modulations = np.asarray(modulations)
    taus = np.asarray(taus)

    # Update Voltage magnitudes
    Vm0[nc.kn_volt_idx] = nc.kn_volt_setpoints

    # Update Voltage angles
    Va0[nc.kn_angle_idx] = nc.kn_angle_setpoints

    # Update p_from
    if nc.kn_pfrom_kdx:
        p_from[nc.kn_pfrom_kdx] = nc.kn_pfrom_setpoints

    # Update p_to
    if nc.kn_pto_kdx:
        p_to[nc.kn_pto_kdx] = nc.kn_pto_setpoints

    # Update q_from
    if nc.kn_qfrom_kdx:
        q_from[nc.kn_qfrom_kdx] = nc.kn_qfrom_setpoints

    # Update q_to
    if nc.kn_qto_kdx:
        q_to[nc.kn_qto_kdx] = nc.kn_qto_setpoints

    # Update p_zip
    p_zip[nc.kn_pzip_idx] = nc.kn_pzip_setpoints

    # Update q_zip
    q_zip[nc.kn_qzip_idx] = nc.kn_qzip_setpoints

    # Update modulations
    if nc.kn_mod_kdx:
        modulations[nc.kn_mod_kdx] = nc.kn_mod_setpoints

    # Update taus
    if nc.kn_tau_kdx:
        taus[nc.kn_tau_kdx] = nc.kn_tau_setpoints

    if verbose:
        print('Updated Vm0:', Vm0)
        print('Updated Va0:', Va0)
        print('Updated P_from:', p_from)
        print('Updated P_to:', p_to)
        print('Updated Q_from:', q_from)
        print('Updated Q_to:', q_to)
        print('Updated P_zip:', p_zip)
        print('Updated Q_zip:', q_zip)
        print('Updated Modulations:', modulations)
        print('Updated Taus:', taus)

    return Vm0, Va0, S0, I0, Y0, p_from, p_to, q_from, q_to, p_zip, q_zip, modulations, taus


def pf_function_raiyan(x: Vec,
                compute_jac: bool,
                # these are the args:
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
                nc: NumericalCircuit ) -> ConvexFunctionResult:

    Va = Va0.copy()
    Vm = Vm0.copy()

    Vm, Va, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus  = x2var(x, nc, Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, verbose = 0)
    V = Vm * np.exp(1j * Va)

    g = compute_g(V, Ybus, S0, I0, Y0, Vm, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, nc)

    if compute_jac:
        Gx = compute_gx(x, g, Vm, Va, Ybus, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, nc)
    else:
        Gx = None

    return ConvexFunctionResult(f=g, J=Gx)


def compute_g(V, Ybus, S0, I0, Y0, Vm, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, nc) -> Vec:
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
    ac_indices = nc.ac_indices
    dc_indices = nc.dc_indices
    vsc_data_from = nc.vsc_data.F
    vsc_data_to = nc.vsc_data.T

    g = compute_fx_raiyan(ac_indices, dc_indices, vsc_data_from, vsc_data_to, Scalc, Sbus, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, V)
    return g



def compute_gx(x, fx, Vm, Va, Ybus, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, nc) -> CscMat:

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
        Vm_after, Va_after, S0, I0, Y0, p_to_after, p_from_after, q_to_after, q_from_after, p_zip_after, q_zip_after, modulations_after, taus_after  = x2var(x1, nc, Vm_after, Va_after, S0, I0, Y0, p_to_after, p_from_after, q_to_after, q_from_after, p_zip_after, q_zip_after, modulations_after, taus_after, verbose = 0)
        '''
        Calculate powers
        '''
        V = Vm_after * np.exp(1j * Va_after)
        Sbus = compute_zip_power(S0, I0, Y0, Vm)
        Scalc = compute_power(Ybus, V)


        '''
        Get the difference in the vectors and append to J
        '''
        controllable_trafo_frombus = np.zeros((0))
        controllable_trafo_tobus = np.zeros((0))
        controllable_trafo_yshunt = np.zeros((0))
        controllable_trafo_yseries = np.zeros((0))
        ac_indices = nc.ac_indices
        dc_indices = nc.dc_indices
        vsc_data_from = nc.vsc_data.F
        vsc_data_to = nc.vsc_data.T

        fx_altered = compute_fx_raiyan(ac_indices, dc_indices, vsc_data_from, vsc_data_to, Scalc, Sbus, p_to_after, p_from_after, q_to_after, q_from_after, p_zip_after, q_zip_after, modulations_after, taus_after, V)
        diff = (fx_altered - fx) / delta
        J[:, i] = diff

    # print("(newton_raphson_general.py) J: ")
    # print(J)

    return csr_matrix((J), shape=(len(x), len(x))).tocsc()



@nb.jit(nopython=True)
def compute_fx_raiyan(ac_indices, dc_indices, vsc_data_from, vsc_data_to, Scalc, Sbus, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, V):
    """
    Compute the NR-like error function using properties from the network configuration object (nc),
    incorporating conditions to ensure operations are only performed when relevant data is present.
    :param nc: Network configuration object containing indices and other data.
    :param Scalc: Calculated power injections as a numpy array.
    :param Sbus: Specified power injections as a numpy array.
    :return: Error vector as a numpy array.
    """
    a = 0.00010000
    b = 0.01500000
    c = 0.20000000

    fx = []

    # Check and compute DC bus active power balance if there are any DC buses
    if dc_indices.size > 0:
        dc_active_power_balance = Scalc[dc_indices].real - Sbus[dc_indices].real + p_to[dc_indices] + p_from[dc_indices] - p_zip[dc_indices]
        fx.extend(dc_active_power_balance)

    # Check and compute AC bus active and reactive power balance if there are any AC buses
    if ac_indices.size > 0:
        ac_active_power_balance = Scalc[ac_indices].real - Sbus[ac_indices].real + p_to[ac_indices] + p_from[ac_indices] - p_zip[ac_indices]
        ac_reactive_power_balance = Scalc[ac_indices].imag - Sbus[ac_indices].imag + q_to[ac_indices] + q_from[ac_indices] - q_zip[ac_indices]
        fx.extend(ac_active_power_balance)
        fx.extend(ac_reactive_power_balance)

    # VSC active power balance, check if there are VSC buses
    if vsc_data_from.size > 0 and vsc_data_to.size > 0:
        Vm = np.abs(V)
        vsc_losses = (p_to[vsc_data_to]**2 + q_to[vsc_data_to]**2)**0.5 / Vm[vsc_data_to]
        vsc_active_power_balance = a + b * vsc_losses + c * vsc_losses**2 - p_to[vsc_data_to] - p_from[vsc_data_from]
        fx.extend(vsc_active_power_balance)

    # Transformer power balances, check if there are transformer indices
    # if nc.controllable_trafo_frombus.size > 0:
    #     Vm = np.abs(V)
    #     Vm_from = Vm[nc.controllable_trafo_frombus]
    #     Vm_to = Vm[nc.controllable_trafo_tobus]
    #     V_from = V[nc.controllable_trafo_frombus]
    #     V_to = V[nc.controllable_trafo_tobus]
        
    #     a_vector = Vm_from**2 * (np.conj(nc.controllable_trafo_yseries) + np.conj(nc.controllable_trafo_yshunt)) / modulations[nc.controllable_trafo_frombus]**2
    #     b_vector = V_from * np.conj(V_to) * np.conj(nc.controllable_trafo_yseries) / (modulations[nc.controllable_trafo_frombus] * np.exp(1j * taus[nc.controllable_trafo_frombus]))
    #     Sfrom = a_vector - b_vector
        
    #     c_vector = Vm_to**2 * (np.conj(nc.controllable_trafo_yseries) + np.conj(nc.controllable_trafo_yshunt))
    #     d_vector = V_to * np.conj(V_from) * np.conj(nc.controllable_trafo_yseries) / (modulations[nc.controllable_trafo_frombus] * np.exp(-1j * taus[nc.controllable_trafo_frombus]))
    #     Sto = c_vector - d_vector
        
    #     fx.extend(Sfrom.real - p_from[nc.controllable_trafo_frombus])
    #     fx.extend(Sto.real - p_to[nc.controllable_trafo_tobus])
    #     fx.extend(Sfrom.imag - q_from[nc.controllable_trafo_frombus])
    #     fx.extend(Sto.imag - q_to[nc.controllable_trafo_tobus])

    return np.array(fx)



def x2var(x,
        nc: NumericalCircuit,
        Vm0, Va0, 
        S0, I0, Y0, 
        p_to, p_from, q_to, q_from, 
        p_zip, q_zip, 
        modulations, 
        taus, 
        verbose=1):   
    """
    Converts a state vector 'x' back to individual system variables according to their indices.

    This function updates the variables for voltage magnitudes, angles, power injections,
    and control settings based on their positions in the input vector 'x', which is typically
    used after solving power system equations to update the system's state.

    Parameters:
    ----------
    x : list or np.array
        The flat array representing the entire state of the system.
    nc : NumericalCircuit
        The numerical circuit object containing data and indices needed to map the state vector back to system variables.
    Vm0, Va0 : np.array
        Arrays to be updated with voltage magnitudes and angles, respectively.
    S0, I0, Y0 : np.array
        System arrays for power, current, and admittance. These are present for completeness but not updated in this function.
    p_to, p_from, q_to, q_from : np.array
        Arrays to be updated with power flow variables.
    p_zip, q_zip : np.array
        Arrays to be updated with ZIP load power variables.
    modulations, taus : np.array
        Arrays to be updated with modulation and time constants for controllable devices.

    verbose : int, optional
        Level of verbosity for logging the updates (default is 1).

    Returns:
    --------
    tuple
        A tuple of updated arrays (Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus).

    """

    _volt_idx_set = remove_duplicates(nc.un_volt_idx)
    _angle_idx_set = remove_duplicates(nc.un_angle_idx)
    _pzip_idx_set = remove_duplicates(nc.un_pzip_idx)
    _qzip_idx_set = remove_duplicates(nc.un_qzip_idx)
    _pfrom_kdx_set = remove_duplicates(nc.un_pfrom_kdx)
    _qfrom_kdx_set = remove_duplicates(nc.un_qfrom_kdx)
    _pto_kdx_set = remove_duplicates(nc.un_pto_kdx)
    _qto_kdx_set = remove_duplicates(nc.un_qto_kdx)
    _mod_kdx_set = remove_duplicates(nc.un_mod_kdx)
    _tau_kdx_set = remove_duplicates(nc.un_tau_kdx)


    a = 0          
    x_volt = x[a:a + len(_volt_idx_set)]
    a += len(_volt_idx_set)
    x_angle = x[a:a + len(_angle_idx_set)]
    a += len(_angle_idx_set)
    x_pzip = x[a:a + len(_pzip_idx_set)]
    a += len(_pzip_idx_set)
    x_qzip = x[a:a + len(_qzip_idx_set)]
    a += len(_qzip_idx_set)
    x_pfrom = x[a:a + len(_pfrom_kdx_set)]
    a += len(_pfrom_kdx_set)
    x_qfrom = x[a:a + len(_qfrom_kdx_set)]
    a += len(_qfrom_kdx_set)
    x_pto = x[a:a + len(_pto_kdx_set)]
    a += len(_pto_kdx_set)
    x_qto = x[a:a + len(_qto_kdx_set)]
    a += len(_qto_kdx_set)
    x_mod = x[a:a + len(_mod_kdx_set)]
    a += len(_mod_kdx_set)
    x_tau = x[a:a + len(_tau_kdx_set)]
    a += len(_tau_kdx_set)

    Vm0[_volt_idx_set] = x_volt
    Va0[_angle_idx_set] = x_angle
    p_zip[_pzip_idx_set] = x_pzip
    q_zip[_qzip_idx_set] = x_qzip

    p_to[nc.branch_data.T[_pto_kdx_set]] = x_pto
    q_to[nc.branch_data.T[_qto_kdx_set]] = x_qto

    p_from[nc.branch_data.F[_pfrom_kdx_set]] = x_pfrom
    q_from[nc.branch_data.F[_qfrom_kdx_set]] = x_qfrom

    modulations[nc.branch_data.F[_mod_kdx_set]] = x_mod
    taus[nc.branch_data.F[_tau_kdx_set]] = x_tau

    return Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus


def var2x(nc: NumericalCircuit):
    """
    Generates an initial state vector 'x' for a numerical circuit simulation,
    with each element set to a default value based on the type of variable.

    The state vector is constructed by concatenating default values for different
    types of variables such as voltage, angle, power injections, and control settings.
    The indices for each type are first deduplicated to ensure uniqueness.

    Parameters:
    nc : NumericalCircuit
        An object representing the numerical circuit, which holds indices for various
        types of variables like voltage, angle, power (p and q), and controls (modulation and tau).

    Returns:
    list
        A list of floats representing the initial state vector where:
        - Voltage magnitudes are set to 1.0
        - Voltage angles, power injections (p and q from/to), are set to 0.0
        - Modulation indices are set to 1.0
        - Time constants (tau) are set to 0.0

    The lengths of each section of the vector correspond to the number of unique indices
    for each variable type in the circuit.
    """
    _volt_idx_set = remove_duplicates(nc.un_volt_idx)
    _angle_idx_set = remove_duplicates(nc.un_angle_idx)
    _pzip_idx_set = remove_duplicates(nc.un_pzip_idx)
    _qzip_idx_set = remove_duplicates(nc.un_qzip_idx)
    _pfrom_kdx_set = remove_duplicates(nc.un_pfrom_kdx)
    _qfrom_kdx_set = remove_duplicates(nc.un_qfrom_kdx)
    _pto_kdx_set = remove_duplicates(nc.un_pto_kdx)
    _qto_kdx_set = remove_duplicates(nc.un_qto_kdx)
    _mod_kdx_set = remove_duplicates(nc.un_mod_kdx)
    _tau_kdx_set = remove_duplicates(nc.un_tau_kdx)

    x = []
    x.extend([1.0] * len(_volt_idx_set))
    x.extend([0.0] * len(_angle_idx_set))
    x.extend([0.0] * len(_pzip_idx_set))
    x.extend([0.0] * len(_qzip_idx_set))
    x.extend([0.0] * len(_pfrom_kdx_set))
    x.extend([0.0] * len(_qfrom_kdx_set))
    x.extend([0.0] * len(_pto_kdx_set))
    x.extend([0.0] * len(_qto_kdx_set))
    x.extend([1.0] * len(_mod_kdx_set))
    x.extend([0.0] * len(_tau_kdx_set))

    return x



def remove_duplicates(arr):
    """
    Remove duplicates from a list while preserving the order of elements.

    Parameters
    ----------
    arr : list
        A list of elements that may contain duplicates.

    Returns
    -------
    list
        A list with duplicates removed while maintaining the order of elements.
    """
    seen = set()
    seen_add = seen.add
    return [x for x in arr if not (x in seen or seen_add(x))]