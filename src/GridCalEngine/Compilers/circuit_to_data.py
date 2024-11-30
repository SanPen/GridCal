# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from typing import Dict, Union, TYPE_CHECKING

from GridCalEngine.basic_structures import Logger
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Aggregation.area import Area
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import (BusMode, BranchImpedanceMode, ExternalGridMode, DeviceType,
                                        TapModuleControl, TapPhaseControl, HvdcControlType, ConverterControlType)
from GridCalEngine.basic_structures import BoolVec, IntVec
from GridCalEngine.Devices.types import BRANCH_TYPES
from GridCalEngine.DataStructures.battery_data import BatteryData
from GridCalEngine.DataStructures.passive_branch_data import PassiveBranchData
from GridCalEngine.DataStructures.active_branch_data import ActiveBranchData
from GridCalEngine.DataStructures.bus_data import BusData
from GridCalEngine.DataStructures.generator_data import GeneratorData
from GridCalEngine.DataStructures.hvdc_data import HvdcData
from GridCalEngine.DataStructures.vsc_data import VscData
from GridCalEngine.DataStructures.load_data import LoadData
from GridCalEngine.DataStructures.shunt_data import ShuntData
from GridCalEngine.DataStructures.fluid_node_data import FluidNodeData
from GridCalEngine.DataStructures.fluid_turbine_data import FluidTurbineData
from GridCalEngine.DataStructures.fluid_pump_data import FluidPumpData
from GridCalEngine.DataStructures.fluid_p2x_data import FluidP2XData
from GridCalEngine.DataStructures.fluid_path_data import FluidPathData
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults
    from GridCalEngine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
    from GridCalEngine.Simulations.NTC.ntc_results import OptimalNetTransferCapacityResults
    from GridCalEngine.Simulations.NTC.ntc_ts_results import OptimalNetTransferCapacityTimeSeriesResults
    from GridCalEngine.Simulations import OptimalNetTransferCapacityResults

    VALID_OPF_RESULTS = Union[
        OptimalPowerFlowResults,
        OptimalPowerFlowTimeSeriesResults,
        OptimalNetTransferCapacityResults,
        OptimalNetTransferCapacityTimeSeriesResults
    ]


def set_bus_control_voltage(i: int,
                            j: int,
                            remote_control: bool,
                            bus_name: str,
                            bus_voltage_used: BoolVec,
                            bus_data: BusData,
                            candidate_Vm: float,
                            use_stored_guess: bool,
                            logger: Logger) -> None:
    """
    Set the bus control voltage
    :param i: Bus index
    :param j: Remote Bus index
    :param remote_control: Using remote control?
    :param bus_name: Bus name
    :param bus_voltage_used: Array of flags indicating if a bus voltage has been modified before
    :param bus_data: BusData
    :param candidate_Vm: Voltage set point that you want to set
    :param use_stored_guess: Use the stored seed values?
    :param logger: Logger
    """
    if bus_data.bus_types[i] != BusMode.Slack_tpe.value:  # if it is not Slack
        if remote_control and j > -1 and j != i:
            # remove voltage control
            bus_data.bus_types[j] = BusMode.PQV_tpe.value  # remote bus to PQV type
            bus_data.bus_types[i] = BusMode.P_tpe.value  # local bus to P type
        else:
            # local voltage control
            bus_data.bus_types[i] = BusMode.PV_tpe.value  # set as PV

    if not use_stored_guess:
        if not bus_voltage_used[i]:
            if remote_control and j > -1 and j != i:
                # initialize the remote bus voltage to the control value
                bus_data.Vbus[j] = complex(candidate_Vm, 0)
                bus_voltage_used[j] = True
            else:
                # initialize the local bus voltage to the control value
                bus_data.Vbus[i] = complex(candidate_Vm, 0)
                bus_voltage_used[i] = True

        elif candidate_Vm != bus_data.Vbus[i]:
            logger.add_error(msg='Different control voltage set points',
                             device=bus_name,
                             value=candidate_Vm,
                             expected_value=bus_data.Vbus[i])


def get_bus_data(bus_data: BusData,
                 circuit: MultiCircuit,
                 areas_dict: Dict[Area, int],
                 t_idx: int = -1,
                 time_series=False,
                 use_stored_guess=False) -> None:
    """

    :param bus_data: BusData
    :param circuit:
    :param areas_dict:
    :param t_idx:
    :param time_series:
    :param use_stored_guess:
    :return:
    """
    substation_dict = {sub: i for i, sub in enumerate(circuit.substations)}

    for i, bus in enumerate(circuit.buses):

        # bus parameters
        bus_data.names[i] = bus.name
        bus_data.idtag[i] = bus.idtag
        bus_data.Vmin[i] = bus.Vmin
        bus_data.Vmax[i] = bus.Vmax
        bus_data.Vnom[i] = bus.Vnom
        bus_data.cost_v[i] = bus.Vm_cost
        bus_data.Vbus[i] = bus.get_voltage_guess(use_stored_guess=use_stored_guess)
        bus_data.is_dc[i] = bus.is_dc

        bus_data.angle_min[i] = bus.angle_min
        bus_data.angle_max[i] = bus.angle_max

        if bus.is_slack:
            bus_data.bus_types[i] = BusMode.Slack_tpe.value  # VD
        else:
            # PQ by default, later it is modified by generators and batteries
            bus_data.bus_types[i] = BusMode.PQ_tpe.value

        bus_data.substations[i] = substation_dict.get(bus.substation, 0)

        bus_data.areas[i] = areas_dict.get(bus.area, 0)

        if time_series:
            bus_data.active[i] = bus.active_prof[t_idx]
        else:
            bus_data.active[i] = bus.active

    return None


def get_load_data(data: LoadData,
                  circuit: MultiCircuit,
                  bus_dict: Dict[Bus, int],
                  bus_voltage_used: BoolVec,
                  bus_data: BusData,
                  logger: Logger,
                  t_idx=-1,
                  opf_results: Union[OptimalPowerFlowResults, None] = None,
                  time_series=False,
                  use_stored_guess=False) -> LoadData:
    """

    :param data:
    :param circuit:
    :param bus_dict:
    :param bus_voltage_used:
    :param bus_data:
    :param logger:
    :param t_idx:
    :param opf_results:
    :param time_series:
    :param use_stored_guess:
    :return:
    """

    ii = 0
    for elm in circuit.get_loads():

        i = bus_dict[elm.bus]

        data.names[ii] = elm.name
        data.idtag[ii] = elm.idtag
        data.bus_idx[ii] = i

        data.mttf[ii] = elm.mttf
        data.mttr[ii] = elm.mttr

        if time_series:
            if opf_results is not None:
                data.S[ii] = complex(elm.P_prof[t_idx], elm.Q_prof[t_idx]) - opf_results.load_shedding[t_idx, ii]
            else:
                data.S[ii] = complex(elm.P_prof[t_idx], elm.Q_prof[t_idx])

            data.I[ii] = complex(elm.Ir_prof[t_idx], elm.Ii_prof[t_idx])
            data.Y[ii] = complex(elm.G_prof[t_idx], elm.B_prof[t_idx])

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

        # reactive power sharing data
        if data.active[ii]:
            bus_data.q_fixed[i] -= data.S[ii].imag
            bus_data.ii_fixed[i] -= data.I[ii].imag
            bus_data.b_fixed[i] -= data.Y[ii].imag

        data.C_bus_elm[i, ii] = 1
        ii += 1

    for elm in circuit.get_static_generators():

        i = bus_dict[elm.bus]
        data.bus_idx[ii] = i
        data.names[ii] = elm.name
        data.idtag[ii] = elm.idtag

        if time_series:
            data.S[ii] -= complex(elm.P_prof[t_idx], elm.Q_prof[t_idx])
            data.active[ii] = elm.active_prof[t_idx]
            data.cost[ii] = elm.Cost_prof[t_idx]

        else:
            data.S[ii] -= complex(elm.P, elm.Q)
            data.active[ii] = elm.active
            data.cost[ii] = elm.Cost

        # reactive power sharing data
        if data.active[ii]:
            bus_data.q_fixed[i] += data.S[ii].imag
            # bus_data.ii_fixed[i] += data.I[ii].imag
            # bus_data.b_fixed[i] += data.Y[ii].imag

        data.C_bus_elm[i, ii] = 1
        ii += 1

    for elm in circuit.get_external_grids():

        i = bus_dict[elm.bus]
        data.bus_idx[ii] = i
        data.names[ii] = elm.name
        data.idtag[ii] = elm.idtag

        # change stuff depending on the modes
        if elm.mode == ExternalGridMode.VD:
            bus_data.bus_types[i] = BusMode.Slack_tpe.value  # set as Slack

        elif elm.mode == ExternalGridMode.PV:

            set_bus_control_voltage(i=i,
                                    j=-1,
                                    remote_control=False,
                                    bus_name=elm.bus.name,
                                    bus_data=bus_data,
                                    bus_voltage_used=bus_voltage_used,
                                    candidate_Vm=elm.Vm_prof[t_idx] if time_series else elm.Vm,
                                    use_stored_guess=use_stored_guess,
                                    logger=logger)

        if time_series:
            data.S[ii] += complex(elm.P_prof[t_idx], elm.Q_prof[t_idx])
            data.active[ii] = elm.active_prof[t_idx]

        else:
            data.S[ii] += complex(elm.P, elm.Q)
            data.active[ii] = elm.active

        # reactive power sharing data
        if data.active[ii]:
            bus_data.q_fixed[i] += data.S[ii].imag
            bus_data.ii_fixed[i] += data.I[ii].imag
            bus_data.b_fixed[i] += data.Y[ii].imag

        data.C_bus_elm[i, ii] = 1
        ii += 1

    for elm in circuit.get_current_injections():

        i = bus_dict[elm.bus]
        data.bus_idx[ii] = i
        data.names[ii] = elm.name
        data.idtag[ii] = elm.idtag

        data.mttf[ii] = elm.mttf
        data.mttr[ii] = elm.mttr

        if time_series:
            data.I[ii] += complex(elm.Ir_prof[t_idx], elm.Ii_prof[t_idx])
            data.active[ii] = elm.active_prof[t_idx]
            data.cost[ii] = elm.Cost_prof[t_idx]

        else:
            data.I[ii] += complex(elm.Ir, elm.Ii)
            data.active[ii] = elm.active
            data.cost[ii] = elm.Cost

        # reactive power sharing data
        if data.active[ii]:
            bus_data.q_fixed[i] += data.S[ii].imag
            bus_data.ii_fixed[i] += data.I[ii].imag
            bus_data.b_fixed[i] += data.Y[ii].imag

        data.C_bus_elm[i, ii] = 1
        ii += 1

    return data


def get_shunt_data(
        data: ShuntData,
        circuit: MultiCircuit,
        bus_dict,
        bus_voltage_used: BoolVec,
        bus_data: BusData,
        logger: Logger,
        t_idx=-1,
        time_series=False,
        use_stored_guess=False,
        control_remote_voltage: bool = True,
) -> None:
    """

    :param data:
    :param circuit:
    :param bus_dict:
    :param bus_voltage_used:
    :param bus_data:
    :param logger:
    :param t_idx:
    :param time_series:
    :param use_stored_guess:
    :param control_remote_voltage:
    :return:
    """

    ii = 0
    for k, elm in enumerate(circuit.get_shunts()):

        i = bus_dict[elm.bus]
        data.bus_idx[k] = i
        data.names[k] = elm.name
        data.idtag[k] = elm.idtag

        data.mttf[k] = elm.mttf
        data.mttr[k] = elm.mttr

        if time_series:
            data.active[k] = elm.active_prof[t_idx]
            data.Y[k] = complex(elm.G_prof[t_idx], elm.B_prof[t_idx])
        else:
            data.active[k] = elm.active
            data.Y[k] = complex(elm.G, elm.B)

        # reactive power sharing data
        if data.active[ii]:
            bus_data.b_fixed[i] += data.Y[ii].imag

        data.C_bus_elm[i, k] = 1
        ii += 1

    for elm in circuit.get_controllable_shunts():

        i = bus_dict[elm.bus]
        data.bus_idx[ii] = i
        data.names[ii] = elm.name
        data.idtag[ii] = elm.idtag

        data.mttf[ii] = elm.mttf
        data.mttr[ii] = elm.mttr

        data.controllable[ii] = elm.is_controlled
        data.vset[ii] = elm.Vset
        data.qmin[ii] = elm.Bmin
        data.qmax[ii] = elm.Bmax

        if time_series:
            data.Y[ii] += complex(elm.G_prof[t_idx], elm.B_prof[t_idx])
            data.active[ii] = elm.active_prof[t_idx]
            data.cost[ii] = elm.Cost_prof[t_idx]

            if elm.is_controlled and elm.active_prof[t_idx]:

                if elm.control_bus_prof[t_idx] is not None:
                    remote_control = True
                    j = bus_dict[elm.control_bus_prof[t_idx]]
                else:
                    remote_control = False
                    j = -1

                data.controllable_bus_idx[ii] = j

                set_bus_control_voltage(i=i,
                                        j=j,
                                        remote_control=remote_control and control_remote_voltage,
                                        bus_name=elm.bus.name,
                                        bus_data=bus_data,
                                        bus_voltage_used=bus_voltage_used,
                                        candidate_Vm=elm.Vset_prof[t_idx],
                                        use_stored_guess=use_stored_guess,
                                        logger=logger)

        else:
            data.Y[ii] += complex(elm.G, elm.B)
            data.active[ii] = elm.active
            data.cost[ii] = elm.Cost

            if elm.is_controlled and elm.active:
                if elm.control_bus is not None:
                    remote_control = True
                    j = bus_dict[elm.control_bus]
                else:
                    remote_control = False
                    j = -1

                data.controllable_bus_idx[ii] = j

                set_bus_control_voltage(i=i,
                                        j=j,
                                        remote_control=remote_control and control_remote_voltage,
                                        bus_name=elm.bus.name,
                                        bus_data=bus_data,
                                        bus_voltage_used=bus_voltage_used,
                                        candidate_Vm=elm.Vset,
                                        use_stored_guess=use_stored_guess,
                                        logger=logger)

        # reactive power sharing data
        if data.active[ii]:
            if data.controllable[ii]:
                bus_data.q_shared_total[i] += data.Y[ii].imag
                data.q_share[ii] = data.Y[ii].imag
            else:
                bus_data.b_fixed[i] += data.Y[ii].imag

        data.C_bus_elm[i, ii] = 1
        ii += 1


def get_generator_data(
        data: GeneratorData,
        circuit: MultiCircuit,
        bus_dict,
        bus_voltage_used: BoolVec,
        logger: Logger,
        bus_data: BusData,
        opf_results: VALID_OPF_RESULTS | None = None,
        t_idx=-1,
        time_series=False,
        use_stored_guess=False,
        control_remote_voltage: bool = True,
) -> Dict[str, int]:
    """

    :param data:
    :param circuit:
    :param bus_dict:
    :param bus_voltage_used:
    :param logger:
    :param bus_data:
    :param opf_results:
    :param t_idx:
    :param time_series:
    :param use_stored_guess:
    :param control_remote_voltage:
    :return:
    """

    gen_index_dict: Dict[str, int] = dict()
    for k, elm in enumerate(circuit.get_generators()):

        gen_index_dict[elm.idtag] = k  # associate the idtag to the index

        i = bus_dict[elm.bus]
        data.bus_idx[k] = i
        data.names[k] = elm.name
        data.idtag[k] = elm.idtag

        data.mttf[k] = elm.mttf
        data.mttr[k] = elm.mttr

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
            data.cost_2[k] = elm.Cost2_prof[t_idx]

            if elm.active_prof[t_idx]:

                if elm.srap_enabled_prof[t_idx] and data.p[k] > 0.0:
                    bus_data.srap_availbale_power[i] += data.p[k]

                if elm.is_controlled:
                    if elm.control_bus_prof[t_idx] is not None:
                        remote_control = True
                        j = bus_dict[elm.control_bus_prof[t_idx]]
                    else:
                        remote_control = False
                        j = -1

                    data.controllable_bus_idx[k] = j

                    set_bus_control_voltage(i=i,
                                            j=j,
                                            remote_control=remote_control and control_remote_voltage,
                                            bus_name=elm.bus.name,
                                            bus_data=bus_data,
                                            bus_voltage_used=bus_voltage_used,
                                            candidate_Vm=elm.Vset_prof[t_idx],
                                            use_stored_guess=use_stored_guess,
                                            logger=logger)

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
            data.cost_2[k] = elm.Cost2

            if elm.active:

                if elm.srap_enabled and data.p[k] > 0.0:
                    bus_data.srap_availbale_power[i] += data.p[k]

                if elm.is_controlled:
                    if elm.control_bus is not None:
                        remote_control = True
                        j = bus_dict[elm.control_bus]
                    else:
                        remote_control = False
                        j = -1

                    data.controllable_bus_idx[k] = j

                    set_bus_control_voltage(i=i,
                                            j=j,
                                            remote_control=remote_control and control_remote_voltage,
                                            bus_name=elm.bus.name,
                                            bus_data=bus_data,
                                            bus_voltage_used=bus_voltage_used,
                                            candidate_Vm=elm.Vset,
                                            use_stored_guess=use_stored_guess,
                                            logger=logger)

        # reactive power limits, for the given power value
        if elm.use_reactive_power_curve:
            data.qmin[k] = elm.q_curve.get_qmin(data.p[i])
            data.qmax[k] = elm.q_curve.get_qmax(data.p[i])
        else:
            data.qmin[k] = elm.Qmin
            data.qmax[k] = elm.Qmax

        # reactive power sharing data
        if data.active[k]:
            if data.controllable[k]:
                bus_data.q_shared_total[i] += data.p[k]
                data.q_share[k] = data.p[k]
            else:
                bus_data.q_fixed[i] += data.get_q_at(k)

        data.C_bus_elm[i, k] = 1

    return gen_index_dict


def get_battery_data(
        data: BatteryData,
        circuit: MultiCircuit,
        bus_dict: Dict[Bus, int],
        bus_voltage_used: BoolVec,
        logger: Logger,
        bus_data: BusData,
        opf_results: VALID_OPF_RESULTS | None = None,
        t_idx=-1,
        time_series=False,
        use_stored_guess=False,
        control_remote_voltage: bool = True,
) -> None:
    """

    :param data:
    :param circuit:
    :param bus_dict:
    :param bus_voltage_used:
    :param logger:
    :param bus_data:
    :param opf_results:
    :param t_idx:
    :param time_series:
    :param use_stored_guess:
    :param control_remote_voltage:
    :return:
    """

    for k, elm in enumerate(circuit.get_batteries()):

        i = bus_dict[elm.bus]
        data.bus_idx[k] = i

        data.names[k] = elm.name
        data.idtag[k] = elm.idtag

        data.mttf[k] = elm.mttf
        data.mttr[k] = elm.mttr

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
            data.cost_2[k] = elm.Cost2_prof[t_idx]

            if elm.active_prof[t_idx]:

                if elm.srap_enabled_prof[t_idx] and data.p[k] > 0.0:
                    bus_data.srap_availbale_power[i] += data.p[k]

                if elm.is_controlled:

                    if elm.control_bus_prof[t_idx] is not None:
                        remote_control = True
                        j = bus_dict[elm.control_bus_prof[t_idx]]
                    else:
                        remote_control = False
                        j = -1

                    data.controllable_bus_idx[k] = j

                    set_bus_control_voltage(i=i,
                                            j=j,
                                            remote_control=remote_control and control_remote_voltage,
                                            bus_name=elm.bus.name,
                                            bus_data=bus_data,
                                            bus_voltage_used=bus_voltage_used,
                                            candidate_Vm=elm.Vset_prof[t_idx],
                                            use_stored_guess=use_stored_guess,
                                            logger=logger)

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
            data.cost_2[k] = elm.Cost2

            if elm.active:

                if elm.srap_enabled and data.p[k] > 0.0:
                    bus_data.srap_availbale_power[i] += data.p[k]

                if elm.is_controlled:

                    if elm.control_bus is not None:
                        remote_control = True
                        j = bus_dict[elm.control_bus]
                    else:
                        remote_control = False
                        j = -1

                    data.controllable_bus_idx[k] = j

                    set_bus_control_voltage(i=i,
                                            j=j,
                                            remote_control=remote_control and control_remote_voltage,
                                            bus_name=elm.bus.name,
                                            bus_data=bus_data,
                                            bus_voltage_used=bus_voltage_used,
                                            candidate_Vm=elm.Vset,
                                            use_stored_guess=use_stored_guess,
                                            logger=logger)

        # reactive power limits, for the given power value
        if elm.use_reactive_power_curve:
            data.qmin[k] = elm.q_curve.get_qmin(data.p[i])
            data.qmax[k] = elm.q_curve.get_qmax(data.p[i])
        else:
            data.qmin[k] = elm.Qmin
            data.qmax[k] = elm.Qmax

        # reactive power sharing data
        if data.active[k]:
            if data.controllable[k]:
                bus_data.q_shared_total[i] += data.p[k]
                data.q_share[k] = data.p[k]
            else:
                bus_data.q_fixed[i] += data.get_q_at(k)

        data.C_bus_elm[i, k] = 1


def fill_parent_branch(i: int,
                       elm: BRANCH_TYPES,
                       data: PassiveBranchData,
                       bus_dict: Dict[Bus, int],
                       apply_temperature: bool,
                       branch_tolerance_mode: BranchImpedanceMode,
                       t_idx: int = -1,
                       time_series: bool = False,
                       is_dc_branch: bool = False, ):
    """

    :param i:
    :param elm:
    :param data:
    :param bus_dict:
    :param apply_temperature:
    :param branch_tolerance_mode:
    :param t_idx:
    :param time_series:
    :param is_dc_branch:
    :return:
    """
    data.names[i] = elm.name
    data.idtag[i] = elm.idtag

    data.mttf[i] = elm.mttf
    data.mttr[i] = elm.mttr

    if time_series:
        data.active[i] = elm.active_prof[t_idx]
        data.rates[i] = elm.rate_prof[t_idx]
        data.contingency_rates[i] = elm.rate_prof[t_idx] * elm.contingency_factor_prof[t_idx]
        data.protection_rates[i] = elm.rate_prof[t_idx] * elm.protection_rating_factor_prof[t_idx]

        data.overload_cost[i] = elm.Cost_prof[t_idx]

    else:
        data.active[i] = elm.active
        data.rates[i] = elm.rate
        data.contingency_rates[i] = elm.rate * elm.contingency_factor
        data.protection_rates[i] = elm.rate * elm.protection_rating_factor

        data.overload_cost[i] = elm.Cost

    f = bus_dict[elm.bus_from]
    t = bus_dict[elm.bus_to]
    data.C_branch_bus_f[i, f] = 1
    data.C_branch_bus_t[i, t] = 1
    data.F[i] = f
    data.T[i] = t

    data.branch_idx[i] = i  # Correct?

    if apply_temperature:
        data.R[i] = elm.R_corrected
    else:
        data.R[i] = elm.R

    if branch_tolerance_mode == BranchImpedanceMode.Lower:
        data.R[i] *= (1 - elm.tolerance / 100.0)
    elif branch_tolerance_mode == BranchImpedanceMode.Upper:
        data.R[i] *= (1 + elm.tolerance / 100.0)

    if not is_dc_branch:
        data.X[i] = elm.X
        data.B[i] = elm.B

        data.R0[i] = elm.R0
        data.X0[i] = elm.X0
        data.B0[i] = elm.B0

        data.R2[i] = elm.R2
        data.X2[i] = elm.X2
        data.B2[i] = elm.B2

    data.contingency_enabled[i] = int(elm.contingency_enabled)
    data.monitor_loading[i] = int(elm.monitor_loading)

    data.virtual_tap_f[i], data.virtual_tap_t[i] = elm.get_virtual_taps()

    return f, t


def fill_controllable_branch(
        ii: int,
        elm: Union[dev.Transformer2W, dev.Winding, dev.VSC, dev.UPFC],
        data: PassiveBranchData,
        ctrl_data: ActiveBranchData,
        bus_data: BusData,
        bus_dict: Dict[Bus, int],
        apply_temperature: bool,
        branch_tolerance_mode: BranchImpedanceMode,
        t_idx: int,
        time_series: bool,
        opf_results: VALID_OPF_RESULTS | None,
        use_stored_guess: bool,
        bus_voltage_used: BoolVec,
        Sbase: float,
        control_taps_modules: bool,
        control_taps_phase: bool,
        control_remote_voltage: bool,
        logger: Logger):
    """

    :param ii:
    :param elm:
    :param data:
    :param ctrl_data:
    :param bus_data:
    :param bus_dict:
    :param apply_temperature:
    :param branch_tolerance_mode:
    :param t_idx:
    :param time_series:
    :param opf_results:
    :param use_stored_guess:
    :param bus_voltage_used:
    :param Sbase:
    :param control_taps_modules:
    :param control_taps_phase:
    :param control_remote_voltage:
    :param logger:
    :return:
    """
    _, t = fill_parent_branch(i=ii,
                              elm=elm,
                              data=data,
                              bus_dict=bus_dict,
                              apply_temperature=apply_temperature,
                              branch_tolerance_mode=branch_tolerance_mode,
                              t_idx=t_idx,
                              time_series=time_series,
                              is_dc_branch=False)

    if time_series:

        if control_taps_phase:
            ctrl_data.tap_phase_control_mode[ii] = elm.tap_phase_control_mode_prof[t_idx]

        if control_taps_modules:
            ctrl_data.tap_module_control_mode[ii] = elm.tap_module_control_mode_prof[t_idx]
            if elm.regulation_bus is None:
                reg_bus = elm.bus_from
                if ctrl_data.tap_module_control_mode[ii] == TapModuleControl.Vm:
                    logger.add_warning("Unspecified regulation bus",
                                       device_class=elm.device_type.value,
                                       device=elm.name)
            else:
                reg_bus = elm.regulation_bus

            ctrl_data.tap_controlled_buses[ii] = bus_dict[reg_bus]

        ctrl_data.Pset[ii] = elm.Pset_prof[t_idx] / Sbase
        ctrl_data.Qset[ii] = elm.Qset_prof[t_idx] / Sbase
        ctrl_data.vset[ii] = elm.vset_prof[t_idx]

        if opf_results is not None:
            ctrl_data.tap_module[ii] = elm.tap_module
            ctrl_data.tap_angle[ii] = opf_results.phase_shift[t_idx, ii]
        else:
            ctrl_data.tap_module[ii] = elm.tap_module_prof[t_idx]
            ctrl_data.tap_angle[ii] = elm.tap_phase_prof[t_idx]
    else:

        if control_taps_phase:
            ctrl_data.tap_phase_control_mode[ii] = elm.tap_phase_control_mode

        if control_taps_modules:
            ctrl_data.tap_module_control_mode[ii] = elm.tap_module_control_mode

            if elm.regulation_bus is None:
                reg_bus = elm.bus_from
                if ctrl_data.tap_module_control_mode[ii] == TapModuleControl.Vm:
                    logger.add_warning("Unspecified regulation bus",
                                       device_class=elm.device_type.value,
                                       device=elm.name)
            else:
                reg_bus = elm.regulation_bus
            ctrl_data.tap_controlled_buses[ii] = bus_dict[reg_bus]

        ctrl_data.Pset[ii] = elm.Pset / Sbase
        ctrl_data.Qset[ii] = elm.Qset / Sbase
        ctrl_data.vset[ii] = elm.vset

        if opf_results is not None:
            ctrl_data.tap_module[ii] = elm.tap_module
            ctrl_data.tap_angle[ii] = opf_results.phase_shift[ii]
        else:
            ctrl_data.tap_module[ii] = elm.tap_module
            ctrl_data.tap_angle[ii] = elm.tap_phase

    ctrl_data.is_controlled[ii] = 1
    ctrl_data.tap_module_min[ii] = elm.tap_module_min
    ctrl_data.tap_module_max[ii] = elm.tap_module_max
    ctrl_data.tap_angle_min[ii] = elm.tap_phase_min
    ctrl_data.tap_angle_max[ii] = elm.tap_phase_max

    if (ctrl_data.tap_module_control_mode[ii] not in (TapModuleControl.fixed, 0)
            or ctrl_data.tap_phase_control_mode[ii] not in (TapPhaseControl.fixed, 0)):
        ctrl_data.any_pf_control = True

    if not use_stored_guess:
        if ctrl_data.tap_module_control_mode[ii] == TapModuleControl.Vm:
            ctrl_data.any_pf_control = True
            bus_idx = ctrl_data.tap_controlled_buses[ii]
            if not bus_voltage_used[bus_idx]:
                if elm.vset > 0.0:
                    bus_data.Vbus[bus_idx] = elm.vset
                else:
                    logger.add_warning("Branch control voltage out of bounds",
                                       device_class=str(elm.device_type.value),
                                       device=elm.name,
                                       value=elm.vset)
            elif elm.vset != bus_data.Vbus[bus_idx]:
                logger.add_error(msg='Different control voltage set points',
                                 device=bus_data.names[bus_idx],
                                 value=elm.vset,
                                 expected_value=bus_data.Vbus[bus_idx])


def get_branch_data(
        data: PassiveBranchData,
        ctrl_data: ActiveBranchData,
        circuit: MultiCircuit,
        bus_dict: Dict[Bus, int],
        bus_data: BusData,
        bus_voltage_used: BoolVec,
        apply_temperature: bool,
        branch_tolerance_mode: BranchImpedanceMode,
        t_idx: int = -1,
        time_series: bool = False,
        opf_results: VALID_OPF_RESULTS | None = None,
        use_stored_guess: bool = False,
        control_taps_modules: bool = True,
        control_taps_phase: bool = True,
        control_remote_voltage: bool = True,
        logger: Logger = Logger()
) -> Dict[BRANCH_TYPES, int]:
    """
    Compile BranchData for a time step or the snapshot
    :param data: BranchData
    :param ctrl_data: ControllableBranchData
    :param circuit: MultiCircuit
    :param bus_dict: Dictionary of buses to compute the indices
    :param bus_data: BusData
    :param bus_voltage_used:
    :param apply_temperature: apply the temperature correction?
    :param branch_tolerance_mode: BranchImpedanceMode
    :param t_idx: time index (-1 is useless)
    :param time_series: compile time series? else the sanpshot is compiled
    :param opf_results: OptimalPowerFlowResults
    :param use_stored_guess: use the stored voltage ?
    :param control_taps_modules: Control TapsModules
    :param control_taps_phase: Control TapsPhase
    :param control_remote_voltage: Control RemoteVoltage
    :param logger: Logger
    :return: BranchData
    """

    branch_dict: Dict[BRANCH_TYPES, int] = dict()

    ii = 0

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        # generic stuff
        fill_parent_branch(i=i,
                           elm=elm,
                           data=data,
                           bus_dict=bus_dict,
                           apply_temperature=apply_temperature,
                           branch_tolerance_mode=branch_tolerance_mode,
                           t_idx=t_idx,
                           time_series=time_series,
                           is_dc_branch=False)

        # store for later
        branch_dict[elm] = ii

        ii += 1

    # DC-lines
    for i, elm in enumerate(circuit.dc_lines):
        # generic stuff
        fill_parent_branch(i=ii,
                           elm=elm,
                           data=data,
                           bus_dict=bus_dict,
                           apply_temperature=apply_temperature,
                           branch_tolerance_mode=branch_tolerance_mode,
                           t_idx=t_idx,
                           time_series=time_series,
                           is_dc_branch=True)

        # store for later
        branch_dict[elm] = ii

        ii += 1

    # 2-winding transformers
    for i, elm in enumerate(circuit.transformers2w):
        fill_controllable_branch(ii=ii,
                                 elm=elm,
                                 data=data,
                                 ctrl_data=ctrl_data,
                                 bus_data=bus_data,
                                 bus_dict=bus_dict,
                                 apply_temperature=apply_temperature,
                                 branch_tolerance_mode=branch_tolerance_mode,
                                 t_idx=t_idx,
                                 time_series=time_series,
                                 opf_results=opf_results,
                                 use_stored_guess=use_stored_guess,
                                 bus_voltage_used=bus_voltage_used,
                                 Sbase=circuit.Sbase,
                                 control_taps_modules=control_taps_modules,
                                 control_taps_phase=control_taps_phase,
                                 control_remote_voltage=control_remote_voltage,
                                 logger=logger)

        data.conn[ii] = elm.conn
        data.m_taps[ii] = elm.tap_changer.tap_modules_array
        data.tau_taps[ii] = elm.tap_changer.tap_angles_array

        # store for later
        branch_dict[elm] = ii

        ii += 1

    # windings
    for i, elm in enumerate(circuit.windings):

        if elm.bus_from is not None and elm.bus_to is not None:
            # generic stuff
            fill_controllable_branch(ii=ii,
                                     elm=elm,
                                     data=data,
                                     ctrl_data=ctrl_data,
                                     bus_data=bus_data,
                                     bus_dict=bus_dict,
                                     apply_temperature=apply_temperature,
                                     branch_tolerance_mode=branch_tolerance_mode,
                                     t_idx=t_idx,
                                     time_series=time_series,
                                     opf_results=opf_results,
                                     use_stored_guess=use_stored_guess,
                                     bus_voltage_used=bus_voltage_used,
                                     Sbase=circuit.Sbase,
                                     control_taps_modules=control_taps_modules,
                                     control_taps_phase=control_taps_phase,
                                     control_remote_voltage=control_remote_voltage,
                                     logger=logger)

            data.conn[ii] = elm.conn
            data.m_taps[ii] = elm.tap_changer.tap_modules_array
            data.tau_taps[ii] = elm.tap_changer.tap_angles_array

            # store for later
            branch_dict[elm] = ii

            ii += 1

        else:
            logger.add_error("Ill connected winding", device=elm.idtag)

    # UPFC
    for i, elm in enumerate(circuit.upfc_devices):
        # generic stuff
        fill_controllable_branch(ii=ii,
                                 elm=elm,
                                 data=data,
                                 ctrl_data=ctrl_data,
                                 bus_data=bus_data,
                                 bus_dict=bus_dict,
                                 apply_temperature=apply_temperature,
                                 branch_tolerance_mode=branch_tolerance_mode,
                                 t_idx=t_idx,
                                 time_series=time_series,
                                 opf_results=opf_results,
                                 use_stored_guess=use_stored_guess,
                                 bus_voltage_used=bus_voltage_used,
                                 Sbase=circuit.Sbase,
                                 control_taps_modules=control_taps_modules,
                                 control_taps_phase=control_taps_phase,
                                 control_remote_voltage=control_remote_voltage,
                                 logger=logger)

        # store for later
        branch_dict[elm] = ii

        ii += 1

    # Series reactance
    for i, elm in enumerate(circuit.series_reactances):
        # generic stuff
        fill_parent_branch(i=ii,
                           elm=elm,
                           data=data,
                           bus_dict=bus_dict,
                           apply_temperature=apply_temperature,
                           branch_tolerance_mode=branch_tolerance_mode,
                           t_idx=t_idx,
                           time_series=time_series,
                           is_dc_branch=False)

        # store for later
        branch_dict[elm] = ii

        ii += 1

    return branch_dict


def get_vsc_data(
        data: VscData,
        circuit: MultiCircuit,
        bus_dict: Dict[Bus, int],
        branch_dict: Dict[BRANCH_TYPES, int],
        bus_data: BusData,
        bus_voltage_used: BoolVec,
        t_idx: int = -1,
        time_series: bool = False,
        opf_results: VALID_OPF_RESULTS | None = None,
        use_stored_guess: bool = False,
        control_remote_voltage: bool = True,
        logger: Logger = Logger()
) -> None:
    """
    Compile VscData for a time step or the snapshot
    :param data: VscData
    :param circuit: MultiCircuit
    :param bus_dict: Dictionary of buses to compute the indices
    :param branch_dict: Dictionary of branches to compute the indices
    :param bus_data: BusData
    :param bus_voltage_used:
    :param t_idx: time index (-1 is useless)
    :param time_series: compile time series? else the sanpshot is compiled
    :param opf_results: OptimalPowerFlowResults
    :param use_stored_guess: use the stored voltage ?
    :param control_remote_voltage: Control RemoteVoltage
    :param logger: Logger
    :return: VscData
    """

    def set_control_dev(k: int,
                        control: ConverterControlType,
                        control_dev: Bus | BRANCH_TYPES | None,
                        control_val: float,
                        control_bus_idx: IntVec,
                        control_branch_idx: IntVec):
        """

        :param k: device index
        :param control: ConverterControlType
        :param control_dev: control device
        :param control_val: control value
        :param control_bus_idx: array to be filled in
        :param control_branch_idx: array to be filled in
        """
        if control_dev is not None:
            if control_dev.device_type == DeviceType.BusDevice:

                bus_idx = bus_dict[control_dev]

                control_bus_idx[k] = bus_idx

                if control in (ConverterControlType.Vm_ac, ConverterControlType.Vm_dc):
                    set_bus_control_voltage(i=bus_idx,
                                            j=-1,
                                            remote_control=False,
                                            bus_name=bus_data.names[bus_idx],
                                            bus_voltage_used=bus_voltage_used,
                                            bus_data=bus_data,
                                            candidate_Vm=control_val,
                                            use_stored_guess=use_stored_guess,
                                            logger=logger)

            else:
                control_branch_idx[k] = branch_dict[control_dev]

    ii = 0

    # VSC
    for i, elm in enumerate(circuit.vsc_devices):
        # generic stuff
        data.names[i] = elm.name
        data.idtag[i] = elm.idtag

        data.mttf[i] = elm.mttf
        data.mttr[i] = elm.mttr

        if time_series:
            data.active[i] = elm.active_prof[t_idx]
            data.rates[i] = elm.rate_prof[t_idx]
            data.contingency_rates[i] = elm.rate_prof[t_idx] * elm.contingency_factor_prof[t_idx]
            data.protection_rates[i] = elm.rate_prof[t_idx] * elm.protection_rating_factor_prof[t_idx]

            data.overload_cost[i] = elm.Cost_prof[t_idx]

            data.control1[ii] = elm.control1_prof[t_idx]
            data.control2[ii] = elm.control2_prof[t_idx]
            data.control1_val[ii] = elm.control1_val_prof[t_idx]
            data.control2_val[ii] = elm.control2_val_prof[t_idx]
            set_control_dev(ii, data.control1[ii], elm.control1_dev_prof[t_idx], data.control1_val[ii],
                            data.control1_bus_idx, data.control1_branch_idx)
            set_control_dev(ii, data.control2[ii], elm.control2_dev_prof[t_idx], data.control2_val[ii],
                            data.control2_bus_idx, data.control2_branch_idx)

        else:
            data.active[i] = elm.active
            data.rates[i] = elm.rate
            data.contingency_rates[i] = elm.rate * elm.contingency_factor
            data.protection_rates[i] = elm.rate * elm.protection_rating_factor

            data.overload_cost[i] = elm.Cost

            data.control1[ii] = elm.control1
            data.control2[ii] = elm.control2
            data.control1_val[ii] = elm.control1_val
            data.control2_val[ii] = elm.control2_val
            set_control_dev(ii, data.control1[ii], elm.control1_dev, data.control1_val[ii],
                            data.control1_bus_idx, data.control1_branch_idx)
            set_control_dev(ii, data.control2[ii], elm.control2_dev, data.control2_val[ii],
                            data.control2_bus_idx, data.control2_branch_idx)

        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]
        data.C_branch_bus_f[i, f] = 1
        data.C_branch_bus_t[i, t] = 1
        data.F[i] = f
        data.T[i] = t

        data.contingency_enabled[i] = int(elm.contingency_enabled)
        data.monitor_loading[i] = int(elm.monitor_loading)

        data.Kdp[ii] = elm.kdp
        data.alpha1[ii] = elm.alpha1
        data.alpha2[ii] = elm.alpha2
        data.alpha3[ii] = elm.alpha3

        ii += 1


def get_hvdc_data(data: HvdcData,
                  circuit: MultiCircuit,
                  bus_dict,
                  bus_types,
                  bus_data: BusData,
                  bus_voltage_used: BoolVec,
                  t_idx=-1,
                  time_series=False,
                  opf_results: Union[OptimalPowerFlowResults, OptimalNetTransferCapacityResults, None] = None,
                  use_stored_guess: bool = False,
                  logger: Logger = Logger()):
    """

    :param data:
    :param circuit:
    :param bus_dict:
    :param bus_types:
    :param bus_data:
    :param bus_voltage_used:
    :param t_idx:
    :param time_series:
    :param opf_results:
    :param use_stored_guess:
    :param logger:
    :return:
    """

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
            data.protection_rates[i] = elm.rate_prof[t_idx] * elm.protection_rating_factor_prof[t_idx]
            data.angle_droop[i] = elm.angle_droop_prof[t_idx]

            if opf_results is not None:
                # if we are taking the values from the OPF, do not allow the free mode
                data.control_mode[i] = HvdcControlType.type_1_Pset
                data.Pset[i] = opf_results.hvdc_Pf[t_idx, i]
            else:
                data.control_mode[i] = elm.control_mode
                data.Pset[i] = elm.Pset_prof[t_idx]

            data.Vset_f[i] = elm.Vset_f_prof[t_idx]
            data.Vset_t[i] = elm.Vset_t_prof[t_idx]

            # hack the bus types to believe they are PV
            if elm.active_prof[t_idx]:
                set_bus_control_voltage(i=f,
                                        j=-1,
                                        remote_control=False,
                                        bus_name=elm.bus_from.name,
                                        bus_data=bus_data,
                                        bus_voltage_used=bus_voltage_used,
                                        candidate_Vm=elm.Vset_f_prof[t_idx],
                                        use_stored_guess=use_stored_guess,
                                        logger=logger)

                set_bus_control_voltage(i=t,
                                        j=-1,
                                        remote_control=False,
                                        bus_name=elm.bus_to.name,
                                        bus_data=bus_data,
                                        bus_voltage_used=bus_voltage_used,
                                        candidate_Vm=elm.Vset_t_prof[t_idx],
                                        use_stored_guess=use_stored_guess,
                                        logger=logger)

        else:
            data.active[i] = elm.active
            data.rate[i] = elm.rate
            data.contingency_rate[i] = elm.rate * elm.contingency_factor
            data.protection_rates[i] = elm.rate * elm.protection_rating_factor
            data.angle_droop[i] = elm.angle_droop
            data.r[i] = elm.r

            if opf_results is not None:
                # if we are taking the values from the OPF, do not allow the free mode
                data.control_mode[i] = HvdcControlType.type_1_Pset
                data.Pset[i] = opf_results.hvdc_Pf[i]
            else:
                data.control_mode[i] = elm.control_mode
                data.Pset[i] = elm.Pset

            data.Vset_f[i] = elm.Vset_f
            data.Vset_t[i] = elm.Vset_t

            # hack the bus types to believe they are PV
            if elm.active:
                set_bus_control_voltage(i=f,
                                        j=-1,
                                        remote_control=False,
                                        bus_name=elm.bus_from.name,
                                        bus_data=bus_data,
                                        bus_voltage_used=bus_voltage_used,
                                        candidate_Vm=elm.Vset_f,
                                        use_stored_guess=use_stored_guess,
                                        logger=logger)

                set_bus_control_voltage(i=t,
                                        j=-1,
                                        remote_control=False,
                                        bus_name=elm.bus_to.name,
                                        bus_data=bus_data,
                                        bus_voltage_used=bus_voltage_used,
                                        candidate_Vm=elm.Vset_t,
                                        use_stored_guess=use_stored_guess,
                                        logger=logger)

        data.Vnf[i] = elm.bus_from.Vnom
        data.Vnt[i] = elm.bus_to.Vnom

        data.Qmin_f[i] = elm.Qmin_f
        data.Qmax_f[i] = elm.Qmax_f
        data.Qmin_t[i] = elm.Qmin_t
        data.Qmax_t[i] = elm.Qmax_t

        # the bus-hvdc line connectivity
        data.C_hvdc_bus_f[i, f] = 1
        data.C_hvdc_bus_t[i, t] = 1


def get_fluid_node_data(data: FluidNodeData,
                        circuit: MultiCircuit,
                        t_idx=-1,
                        time_series=False) -> Dict[str, int]:
    """

    :param data:
    :param circuit:
    :param time_series:
    :param t_idx:
    :return:
    """
    plant_dict: Dict[str, int] = dict()

    for k, elm in enumerate(circuit.get_fluid_nodes()):
        plant_dict[elm.idtag] = k

        data.names[k] = elm.name
        data.idtag[k] = elm.idtag

        # Convert input data in hm3 to m3
        data.min_level[k] = 1e6 * elm.min_level
        data.max_level[k] = 1e6 * elm.max_level
        data.initial_level[k] = 1e6 * elm.initial_level

        if time_series:
            data.inflow[k] = elm.inflow_prof[t_idx]
            data.spillage_cost[k] = elm.spillage_cost_prof[t_idx]
            data.max_soc[k] = elm.max_soc_prof[t_idx]
            data.min_soc[k] = elm.min_soc_prof[t_idx]
        else:
            data.inflow[k] = elm.inflow
            data.spillage_cost[k] = elm.spillage_cost
            data.max_soc[k] = elm.max_soc
            data.min_soc[k] = elm.min_soc

    return plant_dict


def get_fluid_turbine_data(data: FluidTurbineData,
                           circuit: MultiCircuit,
                           plant_dict: Dict[str, int],
                           gen_dict: Dict[str, int],
                           t_idx=-1) -> FluidTurbineData:
    """

    :param data:
    :param circuit:
    :param plant_dict:
    :param gen_dict:
    :param t_idx:
    :return:
    """
    for k, elm in enumerate(circuit.get_fluid_turbines()):
        data.plant_idx[k] = plant_dict[elm.plant.idtag]
        data.generator_idx[k] = gen_dict[elm.generator.idtag]

        data.names[k] = elm.name
        data.idtag[k] = elm.idtag

        data.efficiency[k] = elm.efficiency
        data.max_flow_rate[k] = elm.max_flow_rate

    return data


def get_fluid_pump_data(data: FluidPumpData,
                        circuit: MultiCircuit,
                        plant_dict: Dict[str, int],
                        gen_dict: Dict[str, int],
                        t_idx=-1) -> FluidPumpData:
    """

    :param data:
    :param circuit:
    :param plant_dict:
    :param gen_dict:
    :param t_idx:
    :return:
    """

    for k, elm in enumerate(circuit.get_fluid_pumps()):
        data.plant_idx[k] = plant_dict[elm.plant.idtag]
        data.generator_idx[k] = gen_dict[elm.generator.idtag]

        data.names[k] = elm.name
        data.idtag[k] = elm.idtag

        data.efficiency[k] = elm.efficiency
        data.max_flow_rate[k] = elm.max_flow_rate

    return data


def get_fluid_p2x_data(data: FluidP2XData,
                       circuit: MultiCircuit,
                       plant_dict: Dict[str, int],
                       gen_dict: Dict[str, int],
                       t_idx=-1) -> FluidP2XData:
    """

    :param data:
    :param circuit:
    :param plant_dict:
    :param gen_dict:
    :param t_idx:
    :return:
    """

    for k, elm in enumerate(circuit.get_fluid_p2xs()):
        data.plant_idx[k] = plant_dict[elm.plant.idtag]
        data.generator_idx[k] = gen_dict[elm.generator.idtag]

        data.names[k] = elm.name
        data.idtag[k] = elm.idtag

        data.efficiency[k] = elm.efficiency
        data.max_flow_rate[k] = elm.max_flow_rate

    return data


def get_fluid_path_data(data: FluidPathData,
                        circuit: MultiCircuit,
                        plant_dict: Dict[str, int],
                        t_idx=-1) -> FluidPathData:
    """

    :param data: FluidPathData
    :param circuit:
    :param plant_dict:
    :param t_idx:
    :return:
    """

    for k, elm in enumerate(circuit.get_fluid_paths()):
        data.names[k] = elm.name
        data.idtag[k] = elm.idtag

        # pass idx, check
        data.source_idx[k] = plant_dict[elm.source.idtag]
        data.target_idx[k] = plant_dict[elm.target.idtag]

        data.min_flow[k] = elm.min_flow
        data.max_flow[k] = elm.max_flow

    return data


def compile_numerical_circuit_at(circuit: MultiCircuit,
                                 t_idx: Union[int, None] = None,
                                 apply_temperature=False,
                                 branch_tolerance_mode=BranchImpedanceMode.Specified,
                                 opf_results: VALID_OPF_RESULTS | None = None,
                                 use_stored_guess=False,
                                 bus_dict: Union[Dict[Bus, int], None] = None,
                                 areas_dict: Union[Dict[Area, int], None] = None,
                                 control_taps_modules: bool = True,
                                 control_taps_phase: bool = True,
                                 control_remote_voltage: bool = True,
                                 logger=Logger()) -> NumericalCircuit:
    """
    Compile a NumericalCircuit from a MultiCircuit
    :param circuit: MultiCircuit instance
    :param t_idx: time step from the time series to gather data from, if None the snapshot is used
    :param apply_temperature: apply the branch temperature correction
    :param branch_tolerance_mode: Branch tolerance mode
    :param opf_results:(optional) OptimalPowerFlowResults instance
    :param use_stored_guess: use the storage voltage guess?
    :param bus_dict (optional) Dict[Bus, int] dictionary
    :param areas_dict (optional) Dict[Area, int] dictionary
    :param control_taps_modules: control taps modules?
    :param control_taps_phase: control taps phase?
    :param control_remote_voltage: control remote voltage?
    :param logger: Logger instance
    :return: NumericalCircuit instance
    """

    if circuit.get_connectivity_nodes_number() + circuit.get_switches_number():
        # process topology, this
        circuit.process_topology_at(t_idx=t_idx, logger=logger)

    # if any valid time index is specified, then the data is compiled from the time series
    time_series = t_idx is not None

    bus_voltage_used = np.zeros(circuit.get_bus_number(), dtype=bool)

    # declare the numerical circuit
    nc = NumericalCircuit(
        nbus=circuit.get_bus_number(),
        nbr=circuit.get_branch_number(add_vsc=False,
                                      add_hvdc=False,
                                      add_switch=False),
        nhvdc=circuit.get_hvdc_number(),
        nvsc=circuit.get_vsc_number(),
        nload=circuit.get_load_like_device_number(),
        ngen=circuit.get_generators_number(),
        nbatt=circuit.get_batteries_number(),
        nshunt=circuit.get_shunt_like_device_number(),
        nfluidnode=circuit.get_fluid_nodes_number(),
        nfluidturbine=circuit.get_fluid_turbines_number(),
        nfluidpump=circuit.get_fluid_pumps_number(),
        nfluidp2x=circuit.get_fluid_p2xs_number(),
        nfluidpath=circuit.get_fluid_paths_number(),
        sbase=circuit.Sbase,
        t_idx=t_idx
    )

    if bus_dict is None:
        bus_dict = {bus: i for i, bus in enumerate(circuit.buses)}

    if areas_dict is None:
        areas_dict = {elm: i for i, elm in enumerate(circuit.areas)}

    get_bus_data(
        bus_data=nc.bus_data,  # filled here
        circuit=circuit,
        t_idx=t_idx,
        time_series=time_series,
        areas_dict=areas_dict,
        use_stored_guess=use_stored_guess
    )

    gen_dict = get_generator_data(
        data=nc.generator_data,  # filled here
        circuit=circuit,
        bus_dict=bus_dict,
        bus_data=nc.bus_data,
        t_idx=t_idx,
        time_series=time_series,
        bus_voltage_used=bus_voltage_used,
        logger=logger,
        opf_results=opf_results,
        use_stored_guess=use_stored_guess,
        control_remote_voltage=control_remote_voltage
    )

    get_battery_data(
        data=nc.battery_data,  # filled here
        circuit=circuit,
        bus_dict=bus_dict,
        bus_data=nc.bus_data,
        t_idx=t_idx,
        time_series=time_series,
        bus_voltage_used=bus_voltage_used,
        logger=logger,
        opf_results=opf_results,
        use_stored_guess=use_stored_guess,
        control_remote_voltage=control_remote_voltage
    )

    get_shunt_data(
        data=nc.shunt_data,  # filled here
        circuit=circuit,
        bus_dict=bus_dict,
        bus_voltage_used=bus_voltage_used,
        bus_data=nc.bus_data,
        t_idx=t_idx,
        time_series=time_series,
        logger=logger,
        use_stored_guess=use_stored_guess,
        control_remote_voltage=control_remote_voltage
    )

    get_load_data(
        data=nc.load_data,
        circuit=circuit,
        bus_dict=bus_dict,
        bus_voltage_used=bus_voltage_used,
        bus_data=nc.bus_data,
        logger=logger,
        t_idx=t_idx,
        time_series=time_series,
        opf_results=opf_results,
        use_stored_guess=use_stored_guess
    )

    branch_dict = get_branch_data(
        data=nc.passive_branch_data,
        ctrl_data=nc.active_branch_data,
        circuit=circuit,
        t_idx=t_idx,
        time_series=time_series,
        bus_dict=bus_dict,
        bus_data=nc.bus_data,
        bus_voltage_used=bus_voltage_used,
        apply_temperature=apply_temperature,
        branch_tolerance_mode=branch_tolerance_mode,
        opf_results=opf_results,
        use_stored_guess=use_stored_guess,
        control_taps_modules=control_taps_modules,
        control_taps_phase=control_taps_phase,
        control_remote_voltage=control_remote_voltage,
    )

    get_vsc_data(
        data=nc.vsc_data,
        circuit=circuit,
        t_idx=t_idx,
        time_series=time_series,
        bus_dict=bus_dict,
        branch_dict=branch_dict,
        bus_data=nc.bus_data,
        bus_voltage_used=bus_voltage_used,
        opf_results=opf_results,
        use_stored_guess=use_stored_guess,
        control_remote_voltage=control_remote_voltage,
    )

    get_hvdc_data(
        data=nc.hvdc_data,
        circuit=circuit,
        t_idx=t_idx,
        time_series=time_series,
        bus_dict=bus_dict,
        bus_types=nc.bus_data.bus_types,
        bus_data=nc.bus_data,
        bus_voltage_used=bus_voltage_used,
        opf_results=opf_results,
        use_stored_guess=use_stored_guess,
        logger=logger
    )

    if len(circuit.fluid_nodes) > 0:
        plant_dict = get_fluid_node_data(
            data=nc.fluid_node_data,
            circuit=circuit,
            t_idx=t_idx,
            time_series=time_series
        )

        get_fluid_turbine_data(
            data=nc.fluid_turbine_data,
            circuit=circuit,
            plant_dict=plant_dict,
            gen_dict=gen_dict,
            t_idx=t_idx
        )

        get_fluid_pump_data(
            data=nc.fluid_pump_data,
            circuit=circuit,
            plant_dict=plant_dict,
            gen_dict=gen_dict,
            t_idx=t_idx
        )

        get_fluid_p2x_data(
            data=nc.fluid_p2x_data,
            circuit=circuit,
            plant_dict=plant_dict,
            gen_dict=gen_dict,
            t_idx=t_idx
        )

        get_fluid_path_data(
            data=nc.fluid_path_data,
            circuit=circuit,
            plant_dict=plant_dict,
            t_idx=t_idx
        )

    nc.bus_dict = bus_dict
    nc.consolidate_information()

    return nc
