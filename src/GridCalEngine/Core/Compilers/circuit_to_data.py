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
from typing import Dict, Union
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.Core.Devices.Aggregation.area import Area
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import BusMode, BranchImpedanceMode, CxVec, ExternalGridMode
from GridCalEngine.enumerations import ConverterControlType, TransformerControlType, HvdcControlType
import GridCalEngine.Core.DataStructures as ds


def get_bus_data(circuit: MultiCircuit,
                 areas_dict: Dict[Area, int],
                 t_idx: int = -1,
                 time_series=False,
                 use_stored_guess=False) -> ds.BusData:
    """

    :param circuit:
    :param areas_dict:
    :param t_idx:
    :param time_series:
    :param use_stored_guess:
    :return:
    """
    bus_data = ds.BusData(nbus=len(circuit.buses))

    substation_dict = {sub: i for i, sub in enumerate(circuit.substations)}

    for i, bus in enumerate(circuit.buses):

        # bus parameters
        bus_data.names[i] = bus.name
        bus_data.idtag[i] = bus.idtag
        bus_data.Vmin[i] = bus.Vmin
        bus_data.Vmax[i] = bus.Vmax
        bus_data.Vnom[i] = bus.Vnom
        bus_data.Vbus[i] = bus.get_voltage_guess(None, use_stored_guess=use_stored_guess)

        bus_data.angle_min[i] = bus.angle_min
        bus_data.angle_max[i] = bus.angle_max

        if bus.is_slack:
            bus_data.bus_types[i] = 3  # VD
        else:
            # bus.determine_bus_type().value
            bus_data.bus_types[i] = 1  # PQ by default, later it is modified by generators and batteries

        if bus.substation is not None:
            bus_data.substations[i] = substation_dict[bus.substation]

        bus_data.areas[i] = areas_dict.get(bus.area, 0)

        if time_series:
            bus_data.active[i] = bus.active_prof[t_idx]
        else:
            bus_data.active[i] = bus.active

    return bus_data


def get_load_data(circuit: MultiCircuit,
                  bus_dict: Dict[Bus, int],
                  Vbus: CxVec,
                  bus_data: ds.BusData,
                  logger: Logger,
                  t_idx=-1,
                  opf_results: Union["OptimalPowerFlowResults", None] = None,
                  time_series=False,
                  use_stored_guess=False) -> ds.LoadData:
    """

    :param circuit:
    :param bus_dict:
    :param Vbus:
    :param bus_data:
    :param logger:
    :param t_idx:
    :param opf_results:
    :param time_series:
    :param opf:
    :param use_stored_guess:
    :return:
    """

    data = ds.LoadData(nelm=circuit.get_calculation_loads_number(), nbus=len(circuit.buses))

    ii = 0
    for elm in circuit.get_loads():

        i = bus_dict[elm.bus]

        data.names[ii] = elm.name
        data.idtag[ii] = elm.idtag

        if time_series:
            if opf_results is not None:
                data.S[ii] = elm.P_prof[t_idx] + 1j * elm.Q_prof[t_idx] - opf_results.load_shedding[t_idx, ii]
            else:
                data.S[ii] = elm.P_prof[t_idx] + 1j * elm.Q_prof[t_idx]

            data.I[ii] = elm.Ir_prof[t_idx] + 1j * elm.Ii_prof[t_idx]
            data.Y[ii] = elm.G_prof[t_idx] + 1j * elm.B_prof[t_idx]

            data.active[ii] = elm.active_prof[t_idx]
            data.cost[ii] = elm.Cost_prof[t_idx]

        else:
            if opf_results is not None:
                data.S[ii] = complex(elm.P, elm.Q) - opf_results.load_shedding[ii]
            else:
                data.S[ii] = complex(elm.P, elm.Q)

            data.I[ii] = complex(elm.Ir, elm.Ii)
            data.Y[ii] = complex(elm.G, elm.B)
            data.active[ii] = elm.active
            data.cost[ii] = elm.Cost

        data.C_bus_elm[i, ii] = 1
        ii += 1

    for elm in circuit.get_static_generators():

        i = bus_dict[elm.bus]

        data.names[ii] = elm.name
        data.idtag[ii] = elm.idtag

        if time_series:
            if opf_results is not None:
                data.S[ii] -= elm.P_prof[t_idx] + 1j * elm.Q_prof[t_idx]
            else:
                data.S[ii] -= elm.P_prof[t_idx] + 1j * elm.Q_prof[t_idx]

            data.active[ii] = elm.active_prof[t_idx]
            data.cost[ii] = elm.Cost_prof[t_idx]

        else:
            if opf_results is not None:
                data.S[ii] -= complex(elm.P, elm.Q)
            else:
                data.S[ii] -= complex(elm.P, elm.Q)

            data.active[ii] = elm.active
            data.cost[ii] = elm.Cost

        data.C_bus_elm[i, ii] = 1
        ii += 1

    for elm in circuit.get_external_grids():

        i = bus_dict[elm.bus]

        data.names[ii] = elm.name
        data.idtag[ii] = elm.idtag

        # change stuff depending on the modes
        if elm.mode == ExternalGridMode.VD:
            bus_data.bus_types[i] = 3  # set as Slack

        elif elm.mode == ExternalGridMode.PV:
            if bus_data.bus_types[i] != 3:  # if it is not Slack
                bus_data.bus_types[i] = 2  # set as PV

                if not use_stored_guess:

                    if time_series:
                        if Vbus[i].real == 1.0:
                            Vbus[i] = complex(elm.Vm_prof[t_idx], 0)
                        elif elm.Vm_prof[t_idx] != Vbus[i]:
                            logger.add_error('Different set points', elm.bus.name, elm.Vm_prof[t_idx], Vbus[i])
                    else:
                        if Vbus[i].real == 1.0:
                            Vbus[i] = complex(elm.Vm, 0)
                        elif elm.Vm != Vbus[i]:
                            logger.add_error('Different set points', elm.bus.name, elm.Vm, Vbus[i])

        if time_series:
            if opf_results is not None:
                data.S[ii] = elm.P_prof[t_idx] + 1j * elm.Q_prof[t_idx]
            else:
                data.S[ii] = elm.P_prof[t_idx] + 1j * elm.Q_prof[t_idx]

            data.active[ii] = elm.active_prof[t_idx]

        else:
            if opf_results is not None:
                data.S[ii] = complex(elm.P, elm.Q)
            else:
                data.S[ii] = complex(elm.P, elm.Q)

            data.active[ii] = elm.active

        data.C_bus_elm[i, ii] = 1
        ii += 1

    return data


def get_shunt_data(circuit: MultiCircuit,
                   bus_dict,
                   Vbus,
                   logger: Logger,
                   t_idx=-1,
                   time_series=False,
                   use_stored_guess=False) -> ds.ShuntData:
    """

    :param circuit:
    :param bus_dict:
    :param Vbus:
    :param logger:
    :param t_idx:
    :param time_series:
    :param use_stored_guess:
    :return:
    """
    devices = circuit.get_shunts()

    data = ds.ShuntData(nelm=len(devices), nbus=len(circuit.buses))

    for k, elm in enumerate(devices):

        i = bus_dict[elm.bus]

        data.names[k] = elm.name
        data.idtag[k] = elm.idtag

        data.controlled[k] = elm.is_controlled
        data.b_min[k] = elm.Bmin
        data.b_max[k] = elm.Bmax

        if time_series:
            data.active[k] = elm.active_prof[t_idx]
            data.admittance[k] = elm.G_prof[t_idx] + 1j * elm.B_prof[t_idx]
        else:
            data.active[k] = elm.active
            data.admittance[k] = complex(elm.G, elm.B)

        if not use_stored_guess:
            if Vbus[i].real == 1.0:
                Vbus[i] = complex(elm.Vset, 0)
            elif elm.Vset != Vbus[i]:
                logger.add_error('Different set points', elm.bus.name, elm.Vset, Vbus[i])

        data.C_bus_elm[i, k] = 1

    return data


def get_generator_data(circuit: MultiCircuit,
                       bus_dict,
                       Vbus: CxVec,
                       logger: Logger,
                       bus_data: ds.BusData,
                       opf_results: Union["OptimalPowerFlowResults", None] = None,
                       t_idx=-1,
                       time_series=False,
                       use_stored_guess=False) -> ds.GeneratorData:
    """

    :param circuit:
    :param bus_dict:
    :param Vbus:
    :param logger:
    :param bus_data:
    :param opf_results:
    :param t_idx:
    :param time_series:
    :param opf:
    :param use_stored_guess:
    :return:
    """
    devices = circuit.get_generators()

    data = ds.GeneratorData(nelm=len(devices), nbus=len(circuit.buses))

    for k, elm in enumerate(devices):

        i = bus_dict[elm.bus]

        data.names[k] = elm.name
        data.idtag[k] = elm.idtag


        data.controllable[k] = elm.is_controlled
        data.installed_p[k] = elm.Snom

        # r0, r1, r2, x0, x1, x2
        data.r0[k] = elm.R0
        data.r1[k] = elm.R1
        data.r2[k] = elm.R2
        data.x0[k] = elm.X0
        data.x1[k] = elm.X1
        data.x2[k] = elm.X2

        data.availability[k] = 1.0
        data.ramp_up[k] = elm.RampUp
        data.ramp_down[k] = elm.RampDown
        data.min_time_up[k] = elm.MinTimeUp
        data.min_time_down[k] = elm.MinTimeDown

        data.dispatchable[k] = elm.enabled_dispatch
        data.pmax[k] = elm.Pmax
        data.pmin[k] = elm.Pmin

        if time_series:

            if opf_results is not None:
                data.p[k] = opf_results.generator_power[t_idx, k] - opf_results.generator_shedding[t_idx, k]
            else:
                data.p[k] = elm.P_prof[t_idx]

            data.active[k] = elm.active_prof[t_idx]
            data.pf[k] = elm.Pf_prof[t_idx]
            data.v[k] = elm.Vset_prof[t_idx]

            data.cost_0[k] = elm.Cost0_prof[t_idx]
            data.cost_1[k] = elm.Cost_prof[t_idx]

            if elm.active_prof[t_idx] and elm.is_controlled:

                if bus_data.bus_types[i] != 3:  # if it is not Slack
                    bus_data.bus_types[i] = 2  # set as PV

                    if not use_stored_guess:
                        if Vbus[i].real == 1.0:
                            Vbus[i] = complex(elm.Vset_prof[t_idx], 0)
                        elif elm.Vset_prof[t_idx] != Vbus[i]:
                            logger.add_error('Different set points', elm.bus.name, elm.Vset_prof[t_idx], Vbus[i])

        else:
            if opf_results is not None:
                data.p[k] = opf_results.generator_power[k] - opf_results.generator_shedding[k]
            else:
                data.p[k] = elm.P

            data.active[k] = elm.active
            data.pf[k] = elm.Pf
            data.v[k] = elm.Vset

            data.cost_0[k] = elm.Cost0
            data.cost_1[k] = elm.Cost

            if elm.active and elm.is_controlled:
                if bus_data.bus_types[i] != 3:  # if it is not Slack
                    bus_data.bus_types[i] = 2  # set as PV

                if not use_stored_guess:
                    if Vbus[i].real == 1.0:
                        Vbus[i] = complex(elm.Vset, 0)
                    elif elm.Vset != Vbus[i]:
                        logger.add_error('Different set points', elm.bus.name, elm.Vset, Vbus[i])

        # reactive power limits, for the given power value
        if elm.use_reactive_power_curve:
            data.qmin[k] = elm.q_curve.get_qmin(data.p[i])
            data.qmax[k] = elm.q_curve.get_qmax(data.p[i])
        else:
            data.qmin[k] = elm.Qmin
            data.qmax[k] = elm.Qmax

        data.C_bus_elm[i, k] = 1

    return data


def get_battery_data(circuit: MultiCircuit,
                     bus_dict: Dict[Bus, int],
                     Vbus: CxVec,
                     logger: Logger,
                     bus_data: ds.BusData,
                     opf_results: Union["OptimalPowerFlowResults", None] = None,
                     t_idx=-1,
                     time_series=False,
                     use_stored_guess=False) -> ds.BatteryData:
    """

    :param circuit:
    :param bus_dict:
    :param Vbus:
    :param logger:
    :param bus_data:
    :param opf_results:
    :param t_idx:
    :param time_series:
    :param opf:
    :param use_stored_guess:
    :return:
    """
    devices = circuit.get_batteries()

    data = ds.BatteryData(nelm=len(devices), nbus=circuit.get_bus_number())

    for k, elm in enumerate(devices):

        i = bus_dict[elm.bus]

        data.names[k] = elm.name
        data.idtag[k] = elm.idtag

        data.controllable[k] = elm.is_controlled
        data.installed_p[k] = elm.Snom

        # r0, r1, r2, x0, x1, x2
        data.r0[k] = elm.R0
        data.r1[k] = elm.R1
        data.r2[k] = elm.R2
        data.x0[k] = elm.X0
        data.x1[k] = elm.X1
        data.x2[k] = elm.X2

        data.dispatchable[k] = elm.enabled_dispatch
        data.pmax[k] = elm.Pmax
        data.pmin[k] = elm.Pmin
        data.enom[k] = elm.Enom

        data.availability[k] = 1.0
        data.ramp_up[k] = elm.RampUp
        data.ramp_down[k] = elm.RampDown
        data.min_time_up[k] = elm.MinTimeUp
        data.min_time_down[k] = elm.MinTimeDown

        data.min_soc[k] = elm.min_soc
        data.max_soc[k] = elm.max_soc
        data.soc_0[k] = elm.soc_0
        data.e_min[k] = elm.Enom * elm.min_soc
        data.e_max[k] = elm.Enom * elm.max_soc
        data.discharge_efficiency[k] = elm.discharge_efficiency
        data.charge_efficiency[k] = elm.charge_efficiency

        if time_series:
            if opf_results is not None:
                data.p[k] = opf_results.battery_power[t_idx, k]
            else:
                data.p[k] = elm.P_prof[t_idx]

            data.active[k] = elm.active_prof[t_idx]
            data.pf[k] = elm.Pf_prof[t_idx]
            data.v[k] = elm.Vset_prof[t_idx]

            data.cost_0[k] = elm.Cost0_prof[t_idx]
            data.cost_1[k] = elm.Cost_prof[t_idx]

            if elm.active_prof[t_idx] and elm.is_controlled:
                if bus_data.bus_types[i] != 3:  # if it is not Slack
                    bus_data.bus_types[i] = 2  # set as PV

                    if not use_stored_guess:
                        if Vbus[i].real == 1.0:
                            Vbus[i] = complex(elm.Vset_prof[t_idx], 0)
                        elif elm.Vset_prof[t_idx] != Vbus[i]:
                            logger.add_error('Different set points', elm.bus.name, elm.Vset_prof[t_idx], Vbus[i])

        else:
            if opf_results is not None:
                data.p[k] = opf_results.battery_power[k]
            else:
                data.p[k] = elm.P

            data.active[k] = elm.active
            data.pf[k] = elm.Pf
            data.v[k] = elm.Vset

            data.cost_0[k] = elm.Cost0
            data.cost_1[k] = elm.Cost

            if elm.active and elm.is_controlled:
                if bus_data.bus_types[i] != 3:  # if it is not Slack
                    bus_data.bus_types[i] = 2  # set as PV

                if not use_stored_guess:
                    if Vbus[i].real == 1.0:
                        Vbus[i] = complex(elm.Vset, 0)
                    elif elm.Vset != Vbus[i]:
                        logger.add_error('Different set points', elm.bus.name, elm.Vset, Vbus[i])

        # reactive power limits, for the given power value
        if elm.use_reactive_power_curve:
            data.qmin[k] = elm.q_curve.get_qmin(data.p[i])
            data.qmax[k] = elm.q_curve.get_qmax(data.p[i])
        else:
            data.qmin[k] = elm.Qmin
            data.qmax[k] = elm.Qmax

        data.C_bus_elm[i, k] = 1

    return data


def get_branch_data(circuit: MultiCircuit,
                    bus_dict,
                    Vbus,
                    apply_temperature,
                    branch_tolerance_mode: BranchImpedanceMode,
                    t_idx=-1,
                    time_series=False,
                    opf_results: Union["OptimalPowerFlowResults", None] = None,
                    use_stored_guess=False,
                    logger: Logger = Logger()):
    """

    :param circuit:
    :param bus_dict:
    :param Vbus: Array of bus voltages to be modified
    :param apply_temperature:
    :param branch_tolerance_mode:
    :param t_idx:
    :param time_series:
    :param opf_results:
    :param use_stored_guess:
    :param logger:
    :return:
    """

    data = ds.BranchData(nelm=circuit.get_branch_number_wo_hvdc(),
                         nbus=circuit.get_bus_number())

    ii = 0

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        # generic stuff
        data.names[i] = elm.name
        data.idtag[i] = elm.idtag

        if time_series:
            data.active[i] = elm.active_prof[t_idx]
            data.rates[i] = elm.rate_prof[t_idx]
            data.contingency_rates[i] = elm.rate_prof[t_idx] * elm.contingency_factor_prof[t_idx]

            data.overload_cost[i] = elm.Cost_prof[t_idx]

        else:
            data.active[i] = elm.active
            data.rates[i] = elm.rate
            data.contingency_rates[i] = elm.rate * elm.contingency_factor

            data.overload_cost[i] = elm.Cost

        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]
        data.C_branch_bus_f[i, f] = 1
        data.C_branch_bus_t[i, t] = 1
        data.F[i] = f
        data.T[i] = t

        if apply_temperature:
            data.R[i] = elm.R_corrected
        else:
            data.R[i] = elm.R

        if branch_tolerance_mode == BranchImpedanceMode.Lower:
            data.R[i] *= (1 - elm.tolerance / 100.0)
        elif branch_tolerance_mode == BranchImpedanceMode.Upper:
            data.R[i] *= (1 + elm.tolerance / 100.0)

        data.X[i] = elm.X
        data.B[i] = elm.B

        data.R0[i] = elm.R0
        data.X0[i] = elm.X0
        data.B0[i] = elm.B0

        data.R2[i] = elm.R2
        data.X2[i] = elm.X2
        data.B2[i] = elm.B2

        # data.conn[i] = elm.conn

        data.contingency_enabled[i] = int(elm.contingency_enabled)
        data.monitor_loading[i] = int(elm.monitor_loading)

        data.virtual_tap_f[i], data.virtual_tap_t[i] = elm.get_virtual_taps()

        ii += 1

    # DC-lines
    for i, elm in enumerate(circuit.dc_lines):
        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.names[ii] = elm.name
        data.idtag[ii] = elm.idtag
        data.dc[ii] = 1

        if time_series:
            data.active[ii] = elm.active_prof[t_idx]
            data.rates[ii] = elm.rate_prof[t_idx]
            data.contingency_rates[ii] = elm.rate_prof[t_idx] * elm.contingency_factor_prof[t_idx]
            data.overload_cost[ii] = elm.Cost_prof[t_idx]
        else:
            data.active[ii] = elm.active
            data.rates[ii] = elm.rate
            data.contingency_rates[ii] = elm.rate * elm.contingency_factor
            data.overload_cost[ii] = elm.Cost

        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

        data.contingency_enabled[ii] = int(elm.contingency_enabled)
        data.monitor_loading[ii] = int(elm.monitor_loading)

        data.virtual_tap_f[ii], data.virtual_tap_t[ii] = elm.get_virtual_taps()

        if apply_temperature:
            data.R[ii] = elm.R_corrected
        else:
            data.R[ii] = elm.R

        if branch_tolerance_mode == BranchImpedanceMode.Lower:
            data.R[ii] *= (1 - elm.tolerance / 100.0)
        elif branch_tolerance_mode == BranchImpedanceMode.Upper:
            data.R[ii] *= (1 + elm.tolerance / 100.0)

        ii += 1

    # 2-winding transformers
    for i, elm in enumerate(circuit.transformers2w):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.names[ii] = elm.name
        data.idtag[ii] = elm.idtag

        if time_series:
            data.active[ii] = elm.active_prof[t_idx]
            data.rates[ii] = elm.rate_prof[t_idx]
            data.contingency_rates[ii] = elm.rate_prof[t_idx] * elm.contingency_factor_prof[t_idx]
            data.overload_cost[ii] = elm.Cost_prof[t_idx]
        else:
            data.active[ii] = elm.active
            data.rates[ii] = elm.rate
            data.contingency_rates[ii] = elm.rate * elm.contingency_factor
            data.overload_cost[ii] = elm.Cost

        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

        data.R[ii] = elm.R
        data.X[ii] = elm.X
        data.G[ii] = elm.G
        data.B[ii] = elm.B

        data.R0[ii] = elm.R0
        data.X0[ii] = elm.X0
        data.G0[ii] = elm.G0
        data.B0[ii] = elm.B0

        data.R2[ii] = elm.R2
        data.X2[ii] = elm.X2
        data.G2[ii] = elm.G2
        data.B2[ii] = elm.B2

        data.conn[ii] = elm.conn

        if time_series:
            if opf_results is not None:
                data.tap_module[ii] = elm.tap_module
                data.tap_angle[ii] = opf_results.phase_shift[t_idx, ii]
            else:
                data.tap_module[ii] = elm.tap_module_prof[t_idx]
                data.tap_angle[ii] = elm.tap_phase_prof[t_idx]
        else:
            if opf_results is not None:
                data.tap_module[ii] = elm.tap_module
                data.tap_angle[ii] = opf_results.phase_shift[ii]
            else:
                data.tap_module[ii] = elm.tap_module
                data.tap_angle[ii] = elm.tap_phase

        data.tap_module_min[ii] = elm.tap_module_min
        data.tap_module_max[ii] = elm.tap_module_max
        data.tap_angle_min[ii] = elm.tap_phase_min
        data.tap_angle_max[ii] = elm.tap_phase_max

        data.Pfset[ii] = elm.Pset

        data.control_mode[ii] = elm.control_mode
        data.virtual_tap_f[ii], data.virtual_tap_t[ii] = elm.get_virtual_taps()

        data.contingency_enabled[ii] = int(elm.contingency_enabled)
        data.monitor_loading[ii] = int(elm.monitor_loading)

        if not use_stored_guess:
            if elm.control_mode == TransformerControlType.Vt:
                Vbus[t] = elm.vset

            elif elm.control_mode == TransformerControlType.PtVt:  # 2a:Vdc
                Vbus[t] = elm.vset

        ii += 1

    # windings
    for i, elm in enumerate(circuit.windings):

        if elm.bus_from is not None and elm.bus_to is not None:
            # generic stuff
            f = bus_dict[elm.bus_from]
            t = bus_dict[elm.bus_to]

            data.names[ii] = elm.name
            data.idtag[ii] = elm.idtag

            if time_series:
                data.active[ii] = elm.active_prof[t_idx]
                data.rates[ii] = elm.rate_prof[t_idx]
                data.contingency_rates[ii] = elm.rate_prof[t_idx] * elm.contingency_factor_prof[t_idx]
                data.overload_cost[ii] = elm.Cost_prof[t_idx]
            else:
                data.active[ii] = elm.active
                data.rates[ii] = elm.rate
                data.contingency_rates[ii] = elm.rate * elm.contingency_factor
                data.overload_cost[ii] = elm.Cost

            data.C_branch_bus_f[ii, f] = 1
            data.C_branch_bus_t[ii, t] = 1
            data.F[ii] = f
            data.T[ii] = t

            data.R[ii] = elm.R
            data.X[ii] = elm.X
            data.G[ii] = elm.G
            data.B[ii] = elm.B

            data.R0[ii] = elm.R0
            data.X0[ii] = elm.X0
            data.G0[ii] = elm.G0
            data.B0[ii] = elm.B0

            data.R2[ii] = elm.R2
            data.X2[ii] = elm.X2
            data.G2[ii] = elm.G2
            data.B2[ii] = elm.B2

            data.conn[ii] = elm.conn

            if time_series:
                if opf_results is not None:
                    data.tap_module[ii] = elm.tap_module
                    data.tap_angle[ii] = opf_results.phase_shift[t_idx, ii]
                else:
                    data.tap_module[ii] = elm.tap_module_prof[t_idx]
                    data.tap_angle[ii] = elm.tap_phase_prof[t_idx]
            else:
                if opf_results is not None:
                    data.tap_module[ii] = elm.tap_module
                    data.tap_angle[ii] = opf_results.phase_shift[ii]
                else:
                    data.tap_module[ii] = elm.tap_module
                    data.tap_angle[ii] = elm.tap_phase

            data.tap_module_min[ii] = elm.tap_module_min
            data.tap_module_max[ii] = elm.tap_module_max
            data.tap_angle_min[ii] = elm.tap_phase_min
            data.tap_angle_max[ii] = elm.tap_phase_max

            data.Pfset[ii] = elm.Pset

            data.control_mode[ii] = elm.control_mode
            data.virtual_tap_f[ii], data.virtual_tap_t[ii] = elm.get_virtual_taps()

            data.contingency_enabled[ii] = int(elm.contingency_enabled)
            data.monitor_loading[ii] = int(elm.monitor_loading)

            if not use_stored_guess:
                if elm.control_mode == TransformerControlType.Vt:
                    Vbus[t] = elm.vset

                elif elm.control_mode == TransformerControlType.PtVt:  # 2a:Vdc
                    Vbus[t] = elm.vset

            ii += 1

        else:
            logger.add_error("Ill connected winding", device=elm.idtag)

    # VSC
    for i, elm in enumerate(circuit.vsc_devices):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.names[ii] = elm.name
        data.idtag[ii] = elm.idtag

        if time_series:
            data.active[ii] = elm.active_prof[t_idx]
            data.rates[ii] = elm.rate_prof[t_idx]
            data.contingency_rates[ii] = elm.rate_prof[t_idx] * elm.contingency_factor_prof[t_idx]
            data.overload_cost[ii] = elm.Cost_prof[t_idx]
        else:
            data.active[ii] = elm.active
            data.rates[ii] = elm.rate
            data.contingency_rates[ii] = elm.rate * elm.contingency_factor
            data.overload_cost[ii] = elm.Cost

        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

        data.R[ii] = elm.R
        data.X[ii] = elm.X

        data.R0[ii] = elm.R0
        data.X0[ii] = elm.X0

        data.R2[ii] = elm.R2
        data.X2[ii] = elm.X2

        data.G0sw[ii] = elm.G0sw
        data.Beq[ii] = elm.Beq
        data.tap_module[ii] = elm.tap_module
        data.tap_module_max[ii] = elm.tap_module_max
        data.tap_module_min[ii] = elm.tap_module_min
        data.alpha1[ii] = elm.alpha1
        data.alpha2[ii] = elm.alpha2
        data.alpha3[ii] = elm.alpha3
        data.k[ii] = elm.k  # 0.8660254037844386  # sqrt(3)/2 (do not confuse with k droop)

        if time_series:
            if opf_results is not None:
                data.tap_angle[ii] = opf_results.phase_shift[t_idx, ii]
            else:
                data.tap_angle[ii] = elm.tap_phase
        else:
            if opf_results is not None:
                data.tap_angle[ii] = opf_results.phase_shift[ii]
            else:
                data.tap_angle[ii] = elm.tap_phase

        data.tap_angle_min[ii] = elm.tap_phase_min
        data.tap_angle_max[ii] = elm.tap_phase_max
        data.Pfset[ii] = elm.Pdc_set
        data.Qtset[ii] = elm.Qac_set
        data.Kdp[ii] = elm.kdp
        data.vf_set[ii] = elm.Vac_set
        data.vt_set[ii] = elm.Vdc_set
        data.control_mode[ii] = elm.control_mode
        data.contingency_enabled[ii] = int(elm.contingency_enabled)
        data.monitor_loading[ii] = int(elm.monitor_loading)

        '''
        type_0_free = '0:Free'
        type_I_1 = '1:Vac'
        type_I_2 = '2:Pdc+Qac'
        type_I_3 = '3:Pdc+Vac'
        type_II_4 = '4:Vdc+Qac'
        type_II_5 = '5:Vdc+Vac'
        type_III_6 = '6:Droop+Qac'
        type_III_7 = '7:Droop+Vac'
        '''

        if not use_stored_guess:
            if elm.control_mode == ConverterControlType.type_I_1:  # 1a:Vac
                Vbus[t] = elm.Vac_set

            elif elm.control_mode == ConverterControlType.type_I_3:  # 3:Pdc+Vac
                Vbus[t] = elm.Vac_set

            elif elm.control_mode == ConverterControlType.type_II_4:  # 4:Vdc+Qac
                Vbus[f] = elm.Vdc_set

            elif elm.control_mode == ConverterControlType.type_II_5:  # 5:Vdc+Vac
                Vbus[f] = elm.Vdc_set
                Vbus[t] = elm.Vac_set

            elif elm.control_mode == ConverterControlType.type_III_7:  # 7:Droop+Vac
                Vbus[t] = elm.Vac_set

            elif elm.control_mode == ConverterControlType.type_IV_I:  # 8:Vdc
                Vbus[f] = elm.Vdc_set

        ii += 1

    # UPFC
    for i, elm in enumerate(circuit.upfc_devices):
        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.names[ii] = elm.name
        data.idtag[ii] = elm.idtag

        if time_series:
            data.active[ii] = elm.active_prof[t_idx]
            data.rates[ii] = elm.rate_prof[t_idx]
            data.contingency_rates[ii] = elm.rate_prof[t_idx] * elm.contingency_factor_prof[t_idx]
            data.overload_cost[ii] = elm.Cost_prof[t_idx]
        else:
            data.active[ii] = elm.active
            data.rates[ii] = elm.rate
            data.contingency_rates[ii] = elm.rate * elm.contingency_factor
            data.overload_cost[ii] = elm.Cost

        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

        data.R[ii] = elm.Rs
        data.X[ii] = elm.Xs

        data.R0[ii] = elm.Rs0
        data.X0[ii] = elm.Xs0

        data.R2[ii] = elm.Rs2
        data.X2[ii] = elm.Xs2

        ysh1 = elm.get_ysh1()
        data.Beq[ii] = ysh1.imag

        data.Pfset[ii] = elm.Pfset

        data.contingency_enabled[ii] = int(elm.contingency_enabled)
        data.monitor_loading[ii] = int(elm.monitor_loading)

        ii += 1

    return data


def get_hvdc_data(circuit: MultiCircuit,
                  bus_dict,
                  bus_types,
                  t_idx=-1,
                  time_series=False,
                  opf_results: Union["OptimalPowerFlowResults", None] = None):
    """

    :param circuit:
    :param bus_dict:
    :param bus_types:
    :param t_idx:
    :param time_series:
    :param opf_results:
    :return:
    """
    data = ds.HvdcData(nelm=circuit.get_hvdc_number(), nbus=circuit.get_bus_number())

    # HVDC
    for i, elm in enumerate(circuit.hvdc_lines):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        # hvdc values
        data.names[i] = elm.name
        data.idtag[i] = elm.idtag

        data.dispatchable[i] = int(elm.dispatchable)
        data.F[i] = f
        data.T[i] = t

        if time_series:
            data.active[i] = elm.active_prof[t_idx]
            data.rate[i] = elm.rate_prof[t_idx]
            data.contingency_rate[i] = elm.rate_prof[t_idx] * elm.contingency_factor_prof[t_idx]
            data.angle_droop[i] = elm.angle_droop_prof[t_idx]

            if opf_results is not None:
                # if we are taking the valñues from the OPF, do not allow the free mode
                data.control_mode[i] = HvdcControlType.type_1_Pset
                data.Pset[i] = opf_results.hvdc_Pf[t_idx, i]
            else:
                data.control_mode[i] = elm.control_mode
                data.Pset[i] = elm.Pset_prof[t_idx]

            data.Vset_f[i] = elm.Vset_f_prof[t_idx]
            data.Vset_t[i] = elm.Vset_t_prof[t_idx]

            # hack the bus types to believe they are PV
            if elm.active_prof[t_idx]:
                bus_types[f] = BusMode.PV.value
                bus_types[t] = BusMode.PV.value

        else:
            data.active[i] = elm.active
            data.rate[i] = elm.rate
            data.contingency_rate[i] = elm.rate * elm.contingency_factor
            data.angle_droop[i] = elm.angle_droop
            data.r[i] = elm.r

            if opf_results is not None:
                # if we are taking the valñues from the OPF, do not allow the free mode
                data.control_mode[i] = HvdcControlType.type_1_Pset
                data.Pset[i] = opf_results.hvdc_Pf[i]
            else:
                data.control_mode[i] = elm.control_mode
                data.Pset[i] = elm.Pset

            data.Vset_f[i] = elm.Vset_f
            data.Vset_t[i] = elm.Vset_t

            # hack the bus types to believe they are PV
            if elm.active:
                bus_types[f] = BusMode.PV.value
                bus_types[t] = BusMode.PV.value

        data.Vnf[i] = elm.bus_from.Vnom
        data.Vnt[i] = elm.bus_to.Vnom

        data.Qmin_f[i] = elm.Qmin_f
        data.Qmax_f[i] = elm.Qmax_f
        data.Qmin_t[i] = elm.Qmin_t
        data.Qmax_t[i] = elm.Qmax_t

        # the bus-hvdc line connectivity
        data.C_hvdc_bus_f[i, f] = 1
        data.C_hvdc_bus_t[i, t] = 1

    return data
