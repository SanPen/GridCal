# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
from cmath import log
import numpy as np
import numba as nb
from typing import Union
from GridCalEngine.basic_structures import Vec, CxVec, CxMat


# Double check units!
# Eng + Management (CEngManag)
def calculate_eng_management_cost(K: float, X: float, CEngManag: float) -> float:
    """
    Calculate the cost for engineering and management.
    :param K: multiplication factor
    :param X: add on to total
    :param CEngManag: cost for engineering and management
    :return: total cost
    """
    return K * CEngManag + X


# Turbine (Cturbine)
def calculate_turbine_cost(K: float, X: float, power: float, category: str) -> float:
    """
    Calculate the cost for the turbine.
    :param K: multiplication factor
    :param X: add on to total
    :param power: power of the turbine
    :param category: category of the turbine
    :return: total cost
    """
    if category == "Scope A":
        cost_turbine = 3.5  # M€/MW

    elif category == "Scope B":
        cost_turbine = 2.7  # M€/MW

    else:
        raise ValueError("Category of the turbine is not valid")

    return cost_turbine * power * K + X


# IAC (CcablesIAC)
def calculate_cables_iac_cost(K: float, X: float) -> float:
    """
    Calculate the cost for the IAC cables.
    :param K: multiplication factor
    :param X: add on to total
    """
    cost_cables_iac = 0.22  # M€/MW
    return cost_cables_iac * K + X


# OFFSET (CssOff)
def calculate_offset_cost(K: float, X: float) -> float:
    """
    Calculate the cost for the offset.
    :param K: multiplication factor
    :param X: add on to total
    """
    cost_offset = 0.18  # M€/MW
    return cost_offset * K + X


# EXC (Ccablesoff)
def calculate_exc_cost(L, A, V, K, X):
    """
    Calculate the cost for the EXC.
    :param L: length of the cable
    :param A: cross-section of the cable
    :param V: voltage of the cable
    :param K: multiplication factor
    :param X: add on to total
    """
    # cost for cross-section
    CA = 355 * 1e-6  # M€/m
    cost_cross_section = CA * (A / 240) ** log(1.2)  # M€/m
    # cost for voltage
    cost_voltage = cost_cross_section * (V / 66) ** log(1.2)  # M€/m
    # total cable cost
    cost_cable = cost_voltage * L
    # cost for installing length
    cost_installation = 580 * 1e-6 * L  # M€/m
    return X + (cost_cable + cost_installation) * K


# Onshore cables (Ccableson)
def calculate_onshore_cable_cost(L, A, V, num_circuits, num_trenches, cable_type, K, X):
    """
    Calculate the cost for the onshore cables.
    :param L: length of the cable (in meters)
    :param A: cross-section of the cable (in mm^2)
    :param V: voltage of the cable (in kV)
    :param num_circuits: number of circuits
    :param num_trenches: number of trenches (only for buried cables)
    :param cable_type: type of cable ('buried' or 'overhead')
    :param K: multiplication factor
    :param X: fixed additional cost
    """
    if cable_type == "buried":
        CA = 1.0
        CT = 1.0
        known_A = 1.0
        ratio = 1.0

        if V == 132:
            known_A = 1000  # mm^2
            CA = 90 * 1e-6  # M€/m
            ratio = 1.25
            CT = 275 * 1e-6  # M€/m trench cost per meter for 1 circuit
        elif V == 220:
            known_A = 800
            CA = 98 * 1e-6
            ratio = 1.25
            CT = 375 * 1e-6
        elif V == 380:
            known_A = 630
            CA = 215 * 1e-6
            ratio = 1.15
            CT = 475 * 1e-6

        ratio_price = 1.2
        ratio_installation = 1.2
        multiplier = 1.57  # Multiplier for two circuits

        # Calculate cost for cross-section
        cost_cross_section = CA * (A / known_A) ** log(ratio)  # €/m
        # Calculate total cable cost
        cost_cable = cost_cross_section * L  # €/m
        # Calculate cost with supplies
        cost_with_supplies = cost_cable * ratio_price  # €/m
        # Calculate cost for installation
        cost_installation = cost_with_supplies * ratio_installation  # €/m
        # Calculate cost for trench
        cost_trench = CT * L * num_trenches * num_circuits  # €/m
        if num_trenches == 2:  # or > 1 ???
            cost_trench *= multiplier  # €/m
        # Total cost for buried cables
        total_cost = cost_installation + cost_trench

    elif cable_type == "overhead":
        cost_per_km = 1.0

        if V == 132:
            cost_per_km = 0.175  # M€/km
        elif V == 220:
            cost_per_km = 0.25
        elif V == 380:
            cost_per_km = 0.375

        multiplier = 1.57  # Multiplier for two circuits
        cost_per_meter = cost_per_km / 1000
        # Calculate overhead cable cost
        cost_cable = cost_per_meter * L  # M€/m
        if num_circuits == 2:  # or > 1 ???
            cost_cable *= multiplier  # Factor for 2 circuits
        total_cost = cost_cable

    else:
        raise ValueError("Cable type is not valid.")

    return K * total_cost + X  # €/m


# ONSSET (CssOn)
def calculate_onshore_substation_cost(mw_transformer, num_transformers, num_lines, mvar_shunt_reactor, mvar_statcom,
                                      mvar_harmonic_filter_banks, K, X, Y):
    """
    Calculate the cost for the onshore substation.
    :param mw_transformer: power of the transformers
    :param num_transformers: number of transformers
    :param num_lines: number of lines
    :param mvar_shunt_reactor: number of shunt reactors
    :param mvar_statcom: number of statcom
    :param mvar_harmonic_filter_banks: number of harmonic filter banks
    :param K: multiplication factor
    :param X: add on to total
    :param Y: factor GIS
    """
    if 100 <= mw_transformer <= 200:
        cost_transformer = 0.014
        cost_civil_works = 0.3
        cost_indoorequip_transformer = 0.4
        cost_indoorequip_line = 0.825
        cost_busbar = 0.12
        cost_cable = 0.06
        cost_metal_structure = 0.15
        cost_lighting = 0.075
        cost_scada = 0.3
        cost_building = 0.25
        cost_eng = 0.18
        cost_misc = 0.075

    elif 200 < mw_transformer <= 500:
        cost_transformer = 0.012
        cost_civil_works = 0.5
        cost_indoorequip_transformer = 0.7
        cost_indoorequip_line = 0.9
        cost_busbar = 0.175
        cost_cable = 0.2
        cost_metal_structure = 0.22
        cost_lighting = 0.1
        cost_scada = 0.3
        cost_building = 0.6
        cost_eng = 0.3
        cost_misc = 0.15

    elif mw_transformer > 500:
        cost_transformer = 0.01
        cost_civil_works = 0.8
        cost_indoorequip_transformer = 0.8125
        cost_indoorequip_line = 1.25
        cost_busbar = 0.2
        cost_cable = 0.3
        cost_metal_structure = 0.35
        cost_lighting = 0.12
        cost_scada = 0.4
        cost_building = 1.2
        cost_eng = 0.4
        cost_misc = 0.25
    else:
        raise ValueError("Power of the transformers is not valid.")

    cost_shunt_reactor = 0.05
    cost_statcom = 0.13
    cost_harmonic_filter_banks = 0.05

    total_cost_transformer = mw_transformer * cost_transformer * num_transformers
    total_cost_civil_works = cost_civil_works * num_transformers
    total_cost_indoorequip_transformer = cost_indoorequip_transformer * num_transformers
    total_cost_indoorequip_line = cost_indoorequip_line * num_lines
    equipment_installation = 0.2
    total_cost_installation = equipment_installation * (
            total_cost_indoorequip_transformer + total_cost_indoorequip_line)
    total_cost_busbar = cost_busbar * num_lines
    total_cost_cable = cost_cable * num_transformers

    total_cost_shunt_reactor = cost_shunt_reactor * mvar_shunt_reactor
    total_cost_statcom = cost_statcom * mvar_statcom
    total_cost_harmonic_filter_banks = cost_harmonic_filter_banks * mvar_harmonic_filter_banks
    total_cost_additional = (cost_lighting + cost_scada + cost_building +
                             cost_eng + cost_misc +
                             total_cost_shunt_reactor + total_cost_statcom +
                             total_cost_harmonic_filter_banks)

    total_cost = (total_cost_transformer + total_cost_civil_works + cost_metal_structure +
                  total_cost_indoorequip_transformer + total_cost_indoorequip_line +
                  total_cost_installation + total_cost_busbar + total_cost_cable + total_cost_additional)

    # Where do we multiply Y??
    return K * total_cost + X


# POI (CPOI)
def calculate_poi_cost(K: float, X: float, CPOI: float) -> float:
    """
    Calculate the cost for the POI.
    :param K: multiplication factor
    :param X: add on to total
    :param CPOI: cost for the POI
    """
    return K * CPOI + X


# Other costs (Cothers)
def calculate_other_costs(K: float, X: float, cost_others: float) -> float:
    """
    Calculate the cost for other costs.
    :param K: multiplication factor
    :param X: add on to total
    :param cost_others: cost for other factors
    """
    return K * cost_others + X


K = 1.0
X = 0.0
Y = 1.0
L = 1.0  # length m
A = 1.0  # input cross section mm^2
V = 1.0  # voltage kV
num_circuits = 2
num_trenches = 1
ratio = 1.0
mw_trafos = 300  # MW
num_trafos = 2
num_lines = 4
num_shunt_reactor = 1
num_statcom = 1
num_harmonic_filter_banks = 1

# Calculate all costs
cost_onshore_substation = calculate_onshore_substation_cost(mw_trafos, num_trafos, num_lines, num_shunt_reactor,
                                                            num_statcom,
                                                            num_harmonic_filter_banks, K, X, Y)
cost_onshore_cable = calculate_onshore_cable_cost(L, A, V, num_circuits, num_trenches, "buried", K, X)
cost_exc = calculate_exc_cost(L, A, V, K, X)
cost_offset = calculate_offset_cost(K, X)
cost_cables_iac = calculate_cables_iac_cost(K, X)
cost_turbine = calculate_turbine_cost(K, X, 100, "Scope A")
cost_eng_management = calculate_eng_management_cost(K, X, 0.0)
cost_poi = calculate_poi_cost(K, X, 0.0)
cost_others = calculate_other_costs(K, X, 0.0)

capex = cost_onshore_substation + cost_onshore_cable + cost_exc + cost_offset + cost_cables_iac + cost_turbine + \
        cost_eng_management + cost_poi + cost_others

print(f"Capex: {capex}")

# @nb.njit(cache=True)
# def get_overload_score(loading: Union[CxMat, CxVec], branches_cost: Vec, threshold=1.0) -> float:
#     """
#     Compute overload score by multiplying the loadings above 100% by the associated branch cost.
#     :param loading: load results
#     :param branches_cost: all branch elements from studied grid
#     :param threshold: threshold for overload
#     :return: sum of all costs associated to branch overloads
#     """
#     cost_ = float(0.0)
#
#     if loading.ndim == 1:
#         for i in range(loading.shape[0]):
#             absloading = np.abs(loading[i])
#             if absloading > threshold:
#                 cost_ += (absloading - threshold) * float(branches_cost[i])
#
#     elif loading.ndim == 2:
#
#         for i in range(loading.shape[0]):
#             for j in range(loading.shape[1]):
#                 absloading = np.abs(loading[i, j])
#                 if absloading > threshold:
#                     cost_ += (absloading - threshold) * branches_cost[j]
#
#     return cost_
#
#
# @nb.njit(cache=True)
# def get_voltage_module_score(voltage: Union[CxVec, CxMat], vm_cost: Vec, vm_max: Vec, vm_min: Vec) -> float:
#     """
#     Compute voltage module score by multiplying the voltages outside limits by the associated bus costs.
#     :param voltage: voltage results
#     :param vm_cost: Vm cost array
#     :param vm_max: maximum voltage
#     :param vm_min: minimum voltage
#     :return: sum of all costs associated to voltage module deviation
#     """
#     cost_ = 0.0
#
#     if voltage.ndim == 1:
#         for i in range(voltage.shape[0]):
#             vm = np.abs(voltage[i])
#             if vm < vm_min[i]:
#                 cost_ += vm_cost[i] * (vm_min[i] - vm)
#             elif vm > vm_max[i]:
#                 cost_ += vm_cost[i] * (vm - vm_max[i])
#     elif voltage.ndim == 2:
#         for i in range(voltage.shape[0]):
#             for j in range(voltage.shape[1]):
#                 vm = np.abs(voltage[i, j])
#                 if vm < vm_min[j]:
#                     cost_ += vm_cost[j] * (vm_min[j] - vm)
#                 elif vm > vm_max[j]:
#                     cost_ += vm_cost[j] * (vm - vm_max[j])
#
#     return cost_
#
#
# @nb.njit(cache=True)
# def get_voltage_phase_score(voltage: Union[CxMat, CxVec], va_cost: Vec, va_max: Vec, va_min: Vec) -> float:
#     """
#     Compute voltage phase score by multiplying the phases outside limits by the associated bus costs.
#     :param voltage: voltage results
#     :param va_cost: array of bus angles costs
#     :param va_max: maximum voltage angles
#     :param va_min: minimum voltage angles
#     :return: sum of all costs associated to voltage module deviation
#     """
#     cost_ = 0.0
#
#     if voltage.ndim == 1:
#         for i in range(voltage.shape[0]):
#             va = np.angle(voltage[i])
#             if va < va_min[i]:
#                 cost_ += va_cost[i] * (va_min[i] - va)
#             elif va > va_max[i]:
#                 cost_ += va_cost[i] * (va - va_max[i])
#
#     elif voltage.ndim == 2:
#         for i in range(voltage.shape[0]):
#             for j in range(voltage.shape[1]):
#                 va = np.angle(voltage[i, j])
#                 if va < va_min[j]:
#                     cost_ += va_cost[j] * (va_min[j] - va)
#                 elif va > va_max[j]:
#                     cost_ += va_cost[j] * (va - va_max[j])
#
#     return cost_
