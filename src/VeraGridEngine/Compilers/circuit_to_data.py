# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from scipy.sparse import lil_matrix
from cmath import rect
from typing import Dict, Union, TYPE_CHECKING

from VeraGridEngine.basic_structures import Logger
import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Fluid.fluid_injection_template import FluidInjectionTemplate
from VeraGridEngine.Devices.Aggregation.area import Area
from VeraGridEngine.enumerations import (BusMode, BranchImpedanceMode, ExternalGridMode, DeviceType,
                                         TapModuleControl, TapPhaseControl, HvdcControlType, ConverterControlType,
                                         ShuntConnectionType, ShuntControlMode, GeneratorControlMode, WindingType,
                                         StaticGeneratorControlMode)
from VeraGridEngine.basic_structures import BoolVec, IntVec
from VeraGridEngine.Devices.types import BRANCH_TYPES
from VeraGridEngine.DataStructures.battery_data import BatteryData
from VeraGridEngine.DataStructures.passive_branch_data import PassiveBranchData
from VeraGridEngine.DataStructures.active_branch_data import ActiveBranchData
from VeraGridEngine.DataStructures.bus_data import BusData
from VeraGridEngine.DataStructures.generator_data import GeneratorData
from VeraGridEngine.DataStructures.hvdc_data import HvdcData
from VeraGridEngine.DataStructures.vsc_data import VscData
from VeraGridEngine.DataStructures.load_data import LoadData
from VeraGridEngine.DataStructures.shunt_data import ShuntData
from VeraGridEngine.DataStructures.fluid_node_data import FluidNodeData
from VeraGridEngine.DataStructures.fluid_turbine_data import FluidTurbineData
from VeraGridEngine.DataStructures.fluid_pump_data import FluidPumpData
from VeraGridEngine.DataStructures.fluid_p2x_data import FluidP2XData
from VeraGridEngine.DataStructures.fluid_path_data import FluidPathData
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Utils.NumericalMethods.common import fortescue_012_to_abc

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults
    from VeraGridEngine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
    from VeraGridEngine.Simulations.NTC.ntc_results import OptimalNetTransferCapacityResults
    from VeraGridEngine.Simulations.NTC.ntc_ts_results import OptimalNetTransferCapacityTimeSeriesResults
    from VeraGridEngine.Simulations import OptimalNetTransferCapacityResults

    VALID_OPF_RESULTS = Union[
        OptimalPowerFlowResults,
        OptimalPowerFlowTimeSeriesResults,
        OptimalNetTransferCapacityResults,
        OptimalNetTransferCapacityTimeSeriesResults
    ]


def delta2StarAdmittance(Yab: complex,
                         Ybc: complex,
                         Yca: complex):
    """
    Converts Delta to Star in admittances
    :param Yab:
    :param Ybc:
    :param Yca:
    :return: Ya, Yb, Yc
    """
    return 1 / 3 * np.array([
        [0, 0, 0, 0],
        [0, Yab + Yca, -Yab, -Yca],
        [0, -Yab, Yab + Ybc, -Ybc],
        [0, -Yca, -Ybc, Ybc + Yca]
    ])


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
            # delete voltage control
            # bus_data.bus_types[j] = BusMode.PQV_tpe.value  # remote bus to PQV type
            bus_data.set_bus_mode(j, BusMode.PQV_tpe)
            # bus_data.bus_types[i] = BusMode.P_tpe.value  # local bus to P type
            bus_data.set_bus_mode(i, BusMode.P_tpe)
        else:
            # local voltage control
            # bus_data.bus_types[i] = BusMode.PV_tpe.value  # set as PV
            bus_data.set_bus_mode(i, BusMode.PV_tpe)

    controlled_bus_idx = j if remote_control and j > -1 and j != i else i

    if not bus_voltage_used[controlled_bus_idx]:
        existing_angle = np.angle(bus_data.Vbus[controlled_bus_idx])
        bus_data.Vbus[controlled_bus_idx] = rect(candidate_Vm, existing_angle)
        bus_voltage_used[controlled_bus_idx] = True

    elif not np.isclose(candidate_Vm, abs(bus_data.Vbus[controlled_bus_idx])):
        logger.add_error(msg='Different control voltage set points',
                         device=bus_name,
                         value=candidate_Vm,
                         expected_value=abs(bus_data.Vbus[controlled_bus_idx]))


def normalize_upper_bound(lower: float,
                          upper: float,
                          logger: Logger,
                          device_name: str,
                          device_class: str,
                          lower_name: str,
                          upper_name: str) -> tuple[float, float]:
    """
    Normalize a scalar box constraint so the upper bound is never below the lower bound.

    :param lower: Lower bound candidate.
    :param upper: Upper bound candidate.
    :param logger: Logger used to report the correction.
    :param device_name: Device name for the log entry.
    :param device_class: Device class for the log entry.
    :param lower_name: Human-readable lower-bound field name.
    :param upper_name: Human-readable upper-bound field name.
    :return: Tuple ``(lower, upper)`` with ``upper >= lower`` enforced.
    """
    lower_value: float = float(lower)
    upper_value: float = float(upper)

    # The LP/MIP formulations assume valid boxes. If the source data reverses the interval, clamp
    # the upper bound to the lower bound so the box degenerates to one feasible point instead of
    # becoming invalid and crashing the optimization model.
    if upper_value < lower_value:
        logger.add_warning(
            msg=f"Invalid bounds corrected: {upper_name} < {lower_name}",
            device=device_name,
            value=upper_value,
            expected_value=lower_value,
            device_class=device_class,
            comment=f"Setting {upper_name} = {lower_name}",
            device_property=upper_name,
        )
        upper_value = lower_value
    else:
        pass

    return lower_value, upper_value


def set_bus_control_voltage_vsc(i: int,
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
            # delete voltage control
            # bus_data.bus_types[j] = BusMode.PQV_tpe.value  # remote bus to PQV type
            # bus_data.set_bus_mode(j, BusMode.PQV_tpe)
            bus_data.is_p_controlled[j] = True
            bus_data.is_q_controlled[j] = True
            bus_data.is_vm_controlled[j] = True

            # bus_data.bus_types[i] = BusMode.P_tpe.value  # local bus to P type
            # bus_data.set_bus_mode(i, BusMode.P_tpe)
            bus_data.is_p_controlled[i] = True
        else:
            # local voltage control
            # bus_data.bus_types[i] = BusMode.PV_tpe.value  # set as PV
            # bus_data.set_bus_mode(i, BusMode.PV_tpe)
            bus_data.is_p_controlled[i] = True
            bus_data.is_vm_controlled[i] = True

    if not use_stored_guess:
        if not bus_voltage_used[i]:
            if remote_control and j > -1 and j != i:
                # initialize the remote bus voltage to the control value but preserve angle while updating magnitude
                existing_angle = np.angle(bus_data.Vbus[j])
                bus_data.Vbus[j] = complex(candidate_Vm, 0) * np.exp(1j * existing_angle)
                bus_voltage_used[j] = True
            else:
                # initialize the local bus voltage to the control value but preserve angle while updating magnitude
                existing_angle = np.angle(bus_data.Vbus[i])
                bus_data.Vbus[i] = complex(candidate_Vm, 0) * np.exp(1j * existing_angle)
                bus_voltage_used[i] = True

        elif candidate_Vm != bus_data.Vbus[i]:
            logger.add_error(msg='Different control voltage set points',
                             device=bus_name,
                             value=candidate_Vm,
                             expected_value=bus_data.Vbus[i])


def set_bus_control_angle_vsc(i: int,
                              j: int,
                              remote_control: bool,
                              bus_name: str,
                              bus_angle_used: BoolVec,
                              bus_data: BusData,
                              candidate_Va: float,
                              use_stored_guess: bool,
                              logger: Logger) -> None:
    """
    Set the bus control angle
    :param i: Bus index
    :param j: Remote Bus index
    :param remote_control: Using remote control?
    :param bus_name: Bus name
    :param bus_angle_used: Array of flags indicating if a bus angle has been modified before
    :param bus_data: BusData
    :param candidate_Va: Angle set point that you want to set in degrees
    :param use_stored_guess: Use the stored seed values?
    :param logger: Logger
    """
    if bus_data.bus_types[i] != BusMode.Slack_tpe.value:  # if it is not Slack
        if remote_control and j > -1 and j != i:
            # delete angle control
            # bus_data.bus_types[j] = BusMode.PQV_tpe.value  # remote bus to PQV type
            # bus_data.set_bus_mode(j, BusMode.PQV_tpe)
            bus_data.is_p_controlled[j] = True
            bus_data.is_q_controlled[j] = True
            bus_data.is_va_controlled[j] = True

            # bus_data.bus_types[i] = BusMode.P_tpe.value  # local bus to P type
            # bus_data.set_bus_mode(i, BusMode.P_tpe)
            bus_data.is_p_controlled[i] = True
        else:
            # local angle control controlling q as well
            # bus_data.bus_types[i] = BusMode.PV_tpe.value  # set as PV
            # bus_data.set_bus_mode(i, BusMode.PV_tpe)
            bus_data.is_q_controlled[i] = True
            bus_data.is_va_controlled[i] = True

    if not use_stored_guess:
        if not bus_angle_used[i]:
            if remote_control and j > -1 and j != i:
                # initialize the remote bus angle to the control value but preserve magnitude while updating angle
                existing_magnitude = np.abs(bus_data.Vbus[j])
                bus_data.Vbus[j] = existing_magnitude * np.exp(1j * candidate_Va * np.pi / 180)
                bus_angle_used[j] = True

            else:
                # initialize the local bus angle to the control value but preserve magnitude while updating angle
                existing_magnitude = np.abs(bus_data.Vbus[i])
                bus_data.Vbus[i] = existing_magnitude * np.exp(1j * candidate_Va * np.pi / 180)
                bus_angle_used[i] = True

        else:
            existing_angle = np.angle(bus_data.Vbus[i])
            if not np.isclose(candidate_Va, existing_angle):
                logger.add_error(msg='Different control angle set points',
                                 device=bus_name,
                                 value=candidate_Va,
                                 expected_value=existing_angle)


def set_bus_control_voltage_hvdc(i: int,
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
        # local voltage control
        bus_data.bus_types[i] = BusMode.PV_tpe.value  # set as PV
        # bus_data.set_bus_mode(i, BusMode.PV_tpe)
        bus_data.is_p_controlled[i] = True
        bus_data.is_vm_controlled[i] = True
        bus_data.is_q_controlled[i] = True

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
                 t_idx: int | None,
                 use_stored_guess=False,
                 consider_grounded_buses: bool = False,
                 logger: Logger = Logger()) -> None:
    """

    :param bus_data: BusData
    :param circuit:
    :param areas_dict:
    :param t_idx:
    :param use_stored_guess:
    :param consider_grounded_buses:
    :param logger:
    :return:
    """

    substation_dict = {sub: i for i, sub in enumerate(circuit.substations)}

    for i, bus in enumerate(circuit.buses):

        # bus parameters
        bus_data.original_idx[i] = i
        bus_data.names[i] = bus.name
        bus_data.idtag[i] = bus.idtag
        bus_data.Vnom[i] = bus.Vnom
        bus_data.cost_v[i] = bus.Vm_cost
        bus_data.Vbus[i] = bus.get_voltage_guess_at(t_idx=t_idx, use_stored_guess=use_stored_guess)
        bus_data.is_dc[i] = bus.is_dc

        # Grounded buses go to zero
        if bus.is_grounded and consider_grounded_buses and bus.is_dc:
            bus_data.Vbus[i] = 1e-20 * np.exp(1j * 1e-20)  # effectively zero
            bus_data.is_grounded[i] = bus.is_grounded
        else:
            bus_data.is_grounded[i] = False

        angle_min, angle_max = normalize_upper_bound(
            lower=bus.angle_min,
            upper=bus.angle_max,
            logger=logger,
            device_name=bus.name,
            device_class=str(bus.device_type.value),
            lower_name="angle_min",
            upper_name="angle_max",
        )
        bus_data.angle_min[i] = angle_min
        bus_data.angle_max[i] = angle_max

        if bus.get_is_slack_at(t=t_idx):
            # bus_data.bus_types[i] = BusMode.Slack_tpe.value  # VD
            bus_data.set_bus_mode(i, BusMode.Slack_tpe)

        else:
            # PQ by default, later it is modified by generators and batteries
            # bus_data.bus_types[i] = BusMode.PQ_tpe.value
            bus_data.set_bus_mode(i, BusMode.PQ_tpe)

        bus_data.substations[i] = substation_dict.get(bus.substation, 0)

        bus_data.areas[i] = areas_dict.get(bus.area, 0)

        bus_data.active[i] = bus.get_active_at(t_idx)
        bus_data.Vmin[i] = bus.get_Vmin_at(t_idx)
        bus_data.Vmax[i] = bus.get_Vmax_at(t_idx)

    return None


def get_load_data(data: LoadData,
                  circuit: MultiCircuit,
                  bus_dict: Dict[Bus, int],
                  bus_voltage_used: BoolVec,
                  bus_data: BusData,
                  t_idx: int | None,
                  logger: Logger,
                  use_stored_guess: bool = False,
                  opf_results: Union[OptimalPowerFlowResults, None] = None,
                  fill_three_phase: bool = False) -> LoadData:
    """

    :param data:
    :param circuit:
    :param bus_dict:
    :param bus_voltage_used:
    :param bus_data:
    :param logger:
    :param t_idx:
    :param opf_results:
    :param use_stored_guess:
    :param fill_three_phase: Fill the tree phase info?
    :return:
    """
    ii = 0
    for elm in circuit.get_loads():

        if elm.bus is None:
            data.bus_idx[ii] = -1
            data.active[ii] = False
        else:
            i = bus_dict[elm.bus]

            data.names[ii] = elm.name
            data.idtag[ii] = elm.idtag
            data.bus_idx[ii] = i
            data.original_idx[ii] = ii
            data.mttf[ii] = elm.mttf
            data.mttr[ii] = elm.mttr
            data.scalable[ii] = elm.scalable

            if opf_results is not None:
                if opf_results.load_shedding.ndim == 1:
                    data.S[ii] = elm.get_S_at(t_idx) - opf_results.load_shedding[ii]
                elif opf_results.load_shedding.ndim == 2:
                    data.S[ii] = elm.get_S_at(t_idx) - opf_results.load_shedding[t_idx, ii]
                else:
                    data.S[ii] = elm.get_S_at(t_idx)  # ???
            else:
                data.S[ii] = elm.get_S_at(t_idx)

            if fill_three_phase:
                if elm.conn == ShuntConnectionType.GroundedStar:

                    S_abc = any([elm.get_Sa_at(t_idx), elm.get_Sb_at(t_idx), elm.get_Sc_at(t_idx)])

                    if not S_abc:
                        data.S3_star[4 * ii + 1] = elm.get_S_at(t_idx) / 3
                        data.S3_star[4 * ii + 2] = elm.get_S_at(t_idx) / 3
                        data.S3_star[4 * ii + 3] = elm.get_S_at(t_idx) / 3

                    else:
                        data.S3_star[4 * ii + 1] = elm.get_Sa_at(t_idx)
                        data.S3_star[4 * ii + 2] = elm.get_Sb_at(t_idx)
                        data.S3_star[4 * ii + 3] = elm.get_Sc_at(t_idx)

                    I_abc = any(
                        [np.conj(elm.get_I1_at(t_idx)), np.conj(elm.get_I2_at(t_idx)), np.conj(elm.get_I3_at(t_idx))])

                    if not I_abc:
                        data.I3_star[4 * ii + 1] = np.conj(elm.get_I_at(t_idx)) / 3
                        data.I3_star[4 * ii + 2] = np.conj(elm.get_I_at(t_idx)) / 3
                        data.I3_star[4 * ii + 3] = np.conj(elm.get_I_at(t_idx)) / 3

                    else:
                        data.I3_star[4 * ii + 1] = np.conj(elm.get_I1_at(t_idx))
                        data.I3_star[4 * ii + 2] = np.conj(elm.get_I2_at(t_idx))
                        data.I3_star[4 * ii + 3] = np.conj(elm.get_I3_at(t_idx))

                    Y_abc = any([elm.get_Y1_at(t_idx), elm.get_Y2_at(t_idx), elm.get_Y3_at(t_idx)])

                    if not Y_abc:
                        if elm.conn == ShuntConnectionType.NeutralStar:
                            data.Y3_star[4 * ii + 0, 1] = -1 * elm.get_Y_at(t_idx) / 3
                            data.Y3_star[4 * ii + 0, 2] = -1 * elm.get_Y_at(t_idx) / 3
                            data.Y3_star[4 * ii + 0, 3] = -1 * elm.get_Y_at(t_idx) / 3
                            data.Y3_star[4 * ii + 1, 1] = elm.get_Y_at(t_idx) / 3
                            data.Y3_star[4 * ii + 2, 2] = elm.get_Y_at(t_idx) / 3
                            data.Y3_star[4 * ii + 3, 3] = elm.get_Y_at(t_idx) / 3
                        else:
                            data.Y3_star[4 * ii + 1, 1] = elm.get_Y_at(t_idx) / 3
                            data.Y3_star[4 * ii + 2, 2] = elm.get_Y_at(t_idx) / 3
                            data.Y3_star[4 * ii + 3, 3] = elm.get_Y_at(t_idx) / 3

                    else:
                        if elm.conn == ShuntConnectionType.NeutralStar:
                            data.Y3_star[4 * ii + 0, 1] = -1 * elm.get_Y1_at(t_idx)
                            data.Y3_star[4 * ii + 0, 2] = -1 * elm.get_Y2_at(t_idx)
                            data.Y3_star[4 * ii + 0, 3] = -1 * elm.get_Y3_at(t_idx)
                            data.Y3_star[4 * ii + 1, 1] = elm.get_Y1_at(t_idx)
                            data.Y3_star[4 * ii + 2, 2] = elm.get_Y2_at(t_idx)
                            data.Y3_star[4 * ii + 3, 3] = elm.get_Y3_at(t_idx)
                        else:
                            data.Y3_star[4 * ii + 1, 1] = elm.get_Y1_at(t_idx)
                            data.Y3_star[4 * ii + 2, 2] = elm.get_Y2_at(t_idx)
                            data.Y3_star[4 * ii + 3, 3] = elm.get_Y3_at(t_idx)

                elif elm.conn == ShuntConnectionType.FloatingStar:

                    # Admittances
                    Ya = elm.get_Y1_at(t_idx)
                    Yb = elm.get_Y2_at(t_idx)
                    Yc = elm.get_Y3_at(t_idx)

                    if Ya != 0.0 + 0.0j and Yb != 0.0 + 0.0j and Yc != 0.0 + 0.0j:
                        data.A_floatingstar[ii] = Ya / (Ya + Yb + Yc)
                        data.B_floatingstar[ii] = Yb / (Ya + Yb + Yc)
                        data.C_floatingstar[ii] = Yc / (Ya + Yb + Yc)

                        A = Ya / (Ya + Yb + Yc)
                        B = Yb / (Ya + Yb + Yc)
                        C = Yc / (Ya + Yb + Yc)

                        # First row
                        data.Y3_star[4 * ii + 1, 1] = (1 - A) * Ya
                        data.Y3_star[4 * ii + 1, 2] = -B * Ya
                        data.Y3_star[4 * ii + 1, 3] = -C * Ya

                        # Second row
                        data.Y3_star[4 * ii + 2, 1] = -A * Yb
                        data.Y3_star[4 * ii + 2, 2] = (1 - B) * Yb
                        data.Y3_star[4 * ii + 2, 3] = -C * Yb

                        # Third row
                        data.Y3_star[4 * ii + 3, 1] = -A * Yc
                        data.Y3_star[4 * ii + 3, 2] = -B * Yc
                        data.Y3_star[4 * ii + 3, 3] = (1 - C) * Yc

                    # Currents
                    Ia = np.conj(elm.get_I1_at(t_idx))
                    Ib = np.conj(elm.get_I2_at(t_idx))
                    Ic = np.conj(elm.get_I3_at(t_idx))

                    if Ia != 0.0 + 0.0j and Ib != 0.0 + 0.0j and Ic != 0.0 + 0.0j:
                        data.I3_floatingstar[4 * ii + 1] = Ia
                        data.I3_floatingstar[4 * ii + 2] = Ib
                        data.I3_floatingstar[4 * ii + 3] = Ic

                    # Powers
                    Sa = elm.get_Sa_at(t_idx)
                    Sb = elm.get_Sb_at(t_idx)
                    Sc = elm.get_Sc_at(t_idx)

                    if Sa != 0.0 + 0.0j and Sb != 0.0 + 0.0j and Sc != 0.0 + 0.0j:
                        data.S3_floatingstar[4 * ii + 1] = Sa
                        data.S3_floatingstar[4 * ii + 2] = Sb
                        data.S3_floatingstar[4 * ii + 3] = Sc

                elif elm.conn == ShuntConnectionType.NeutralStar:

                    # Admittance
                    Ya = elm.get_Y1_at(t_idx)
                    Yb = elm.get_Y2_at(t_idx)
                    Yc = elm.get_Y3_at(t_idx)
                    # First row
                    data.Y3_star[4 * ii + 0, 0] = Ya + Yb + Yc + 1e-4
                    data.Y3_star[4 * ii + 0, 1] = -Ya
                    data.Y3_star[4 * ii + 0, 2] = -Yb
                    data.Y3_star[4 * ii + 0, 3] = -Yc
                    # Second row
                    data.Y3_star[4 * ii + 1, 0] = -Ya
                    data.Y3_star[4 * ii + 1, 1] = Ya
                    # Third row
                    data.Y3_star[4 * ii + 2, 0] = -Yb
                    data.Y3_star[4 * ii + 2, 2] = Yb
                    # Fourth row
                    data.Y3_star[4 * ii + 3, 0] = -Yc
                    data.Y3_star[4 * ii + 3, 3] = Yc

                    # Current
                    data.I3_star[4 * ii + 0] = -np.conj(elm.get_I1_at(t_idx)) - np.conj(elm.get_I2_at(t_idx)) - np.conj(
                        elm.get_I3_at(t_idx))
                    data.I3_star[4 * ii + 1] = np.conj(elm.get_I1_at(t_idx))
                    data.I3_star[4 * ii + 2] = np.conj(elm.get_I2_at(t_idx))
                    data.I3_star[4 * ii + 3] = np.conj(elm.get_I3_at(t_idx))

                    # Current
                    data.S3_star[4 * ii + 0] = -elm.get_Sa_at(t_idx) - elm.get_Sb_at(t_idx) - elm.get_Sc_at(t_idx)
                    data.S3_star[4 * ii + 1] = elm.get_Sa_at(t_idx)
                    data.S3_star[4 * ii + 2] = elm.get_Sb_at(t_idx)
                    data.S3_star[4 * ii + 3] = elm.get_Sc_at(t_idx)

                elif elm.conn == ShuntConnectionType.Delta:

                    data.S3_delta[4 * ii + 1] = elm.get_Sa_at(t_idx)
                    data.S3_delta[4 * ii + 2] = elm.get_Sb_at(t_idx)
                    data.S3_delta[4 * ii + 3] = elm.get_Sc_at(t_idx)

                    data.I3_delta[4 * ii + 1] = np.conj(elm.get_I1_at(t_idx))
                    data.I3_delta[4 * ii + 2] = np.conj(elm.get_I2_at(t_idx))
                    data.I3_delta[4 * ii + 3] = np.conj(elm.get_I3_at(t_idx))

                    data.Y3_star[4 * ii:4 * ii + 4, [0, 1, 2, 3]] = delta2StarAdmittance(
                        Yab=elm.get_Y1_at(t_idx),
                        Ybc=elm.get_Y2_at(t_idx),
                        Yca=elm.get_Y3_at(t_idx)
                    )

                else:
                    raise Exception(f"Unhandled connection type {elm.conn}")

            data.I[ii] = elm.get_I_at(t_idx)
            data.Y[ii] = elm.get_Y_at(t_idx)
            data.active[ii] = elm.get_active_at(t_idx)
            data.cost[ii] = elm.get_Cost_at(t_idx)
            data.shift_key[ii] = elm.get_shift_key_at(t_idx)

            if elm.use_kw:
                # pass kW to MW
                data.S[ii] /= 1000.0
                data.I[ii] /= 1000.0
                data.Y[ii] /= 1000.0
                data.cost[ii] /= 1000.0

            # reactive power sharing data
            if data.active[ii]:
                bus_data.q_fixed[i] -= data.S[ii].imag
                bus_data.ii_fixed[i] -= data.I[ii].imag
                bus_data.b_fixed[i] -= data.Y[ii].imag

        # data.C_bus_elm[i, ii] = 1
        ii += 1

    for elm in circuit.get_static_generators():

        if elm.bus is None:
            data.bus_idx[ii] = -1
            data.active[ii] = False
        else:
            i = bus_dict[elm.bus]
            data.bus_idx[ii] = i
            data.names[ii] = elm.name
            data.idtag[ii] = elm.idtag
            data.original_idx[ii] = ii
            data.scalable[ii] = elm.scalable
            data.is_static_generator[ii] = True

            data.S[ii] -= elm.get_S_at(t_idx)
            data.active[ii] = elm.get_active_at(t_idx)
            data.cost[ii] = elm.get_Cost_at(t_idx)
            data.shift_key[ii] = elm.get_shift_key_at(t_idx)

            if elm.control_mode == StaticGeneratorControlMode.QVDroop and data.active[ii]:
                if (not np.all(np.isfinite((elm.Snom, elm.droop, elm.Vset, elm.Vset_min, elm.Vset_max)))
                        or elm.Snom <= 0.0 or elm.droop <= 0.0
                        or elm.Vset_min <= 0.0 or elm.Vset_min >= elm.Vset_max):
                    raise ValueError('Static generator Q-V droop requires positive Snom/droop and valid voltage clamps: '
                                     + elm.name)
                elif elm.bus.is_dc or not (elm.phA and elm.phB and elm.phC):
                    raise ValueError('Static generator Q-V droop requires an AC bus and all ABC phases: ' + elm.name)
                else:
                    data.q_droop[ii] = elm.droop
                    data.q_droop_snom[ii] = elm.Snom / 1000.0 if elm.use_kw else elm.Snom
                    data.q_droop_vset[ii] = elm.Vset
                    data.q_droop_vmin[ii] = elm.Vset_min
                    data.q_droop_vmax[ii] = elm.Vset_max
            else:
                pass

            # Controlled units inject I1 in the ABC formulation, not three fixed phase powers.
            if fill_three_phase and data.active[ii] and data.q_droop[ii] == 0.0:
                # Distribute missing P and Q independently, preserving explicit phase values.
                phase_power: np.ndarray = np.array((elm.get_Sa_at(t_idx),
                                                    elm.get_Sb_at(t_idx),
                                                    elm.get_Sc_at(t_idx)), dtype=complex)
                sequence_model: bool = (elm.conn == ShuntConnectionType.FloatingStar
                                        or any((elm.R0, elm.X0, elm.R2, elm.X2)))
                if sequence_model and not np.any(phase_power):
                    if elm.bus.is_dc or not (elm.phA and elm.phB and elm.phC):
                        raise ValueError('Static generator sequence model requires all AC phases: ' + elm.name)
                    else:
                        pass
                    z0: complex = complex(elm.R0, elm.X0)
                    z2: complex = complex(elm.R2, elm.X2)
                    if not np.isfinite(z0) or not np.isfinite(z2):
                        raise ValueError('Static generator Z0/Z2 must be finite: ' + elm.name)
                    else:
                        pass
                    y0: complex = 0j
                    if elm.conn == ShuntConnectionType.GroundedStar:
                        if abs(z0) < 1e-12:
                            raise ValueError('Grounded static generator needs nonzero Z0 (R0/X0): ' + elm.name)
                        else:
                            y0 = 1.0 / z0
                    elif elm.conn in (ShuntConnectionType.Delta, ShuntConnectionType.FloatingStar):
                        pass
                    else:
                        raise ValueError('Static generator sequence model does not support an explicit neutral: '
                                         + elm.name)
                    y2: complex = 1.0 / z2 if abs(z2) >= 1e-12 else 0j
                    # Keep the passive response in the existing ABC admittance storage.
                    # The positive sequence is a power source, never a passive shunt.
                    data.Y3_star[4 * ii + 1:4 * ii + 4, 1:4] = (
                        fortescue_012_to_abc(y0, 0j, y2) * circuit.Sbase / 3.0)
                    data.is_positive_sequence[ii] = True
                else:
                    pass

                if not sequence_model or np.any(phase_power):
                    # Explicit phase powers keep their original connection and profiles.
                    if not np.any(phase_power.real):
                        phase_power.real = elm.get_P_at(t_idx) / 3.0
                    else:
                        pass

                    if not np.any(phase_power.imag):
                        phase_power.imag = elm.get_Q_at(t_idx) / 3.0
                    else:
                        pass

                    if elm.conn == ShuntConnectionType.GroundedStar:
                        data.S3_star[4 * ii + 1:4 * ii + 4] -= phase_power
                    elif elm.conn == ShuntConnectionType.Delta:
                        data.S3_delta[4 * ii + 1:4 * ii + 4] -= phase_power
                    elif elm.conn == ShuntConnectionType.FloatingStar:
                        data.S3_floatingstar[4 * ii + 1:4 * ii + 4] -= phase_power
                    else:
                        raise ValueError(f'Unhandled static generator connection {elm.conn}: {elm.name}')
                else:
                    pass

            else:
                pass

            if elm.use_kw:
                # pass kW to MW
                data.S[ii] /= 1000.0
                data.cost[ii] /= 1000.0

            # reactive power sharing data
            if data.active[ii]:
                if data.q_droop[ii] > 0.0:
                    bus_data.q_fixed[i] -= data.S[ii].imag
                else:
                    bus_data.q_fixed[i] += data.S[ii].imag
                # bus_data.ii_fixed[i] += data.I[ii].imag
                # bus_data.b_fixed[i] += data.Y[ii].imag

        # data.C_bus_elm[i, ii] = 1
        ii += 1

    for elm in circuit.get_external_grids():

        if elm.bus is None:
            data.bus_idx[ii] = -1
            data.active[ii] = False
        else:
            i = bus_dict[elm.bus]
            data.bus_idx[ii] = i
            data.names[ii] = elm.name
            data.idtag[ii] = elm.idtag
            data.scalable[ii] = elm.scalable
            data.original_idx[ii] = ii

            # change stuff depending on the modes
            if elm.mode == ExternalGridMode.VD:
                # bus_data.bus_types[i] = BusMode.Slack_tpe.value  # set as Slack
                bus_data.set_bus_mode(i, BusMode.Slack_tpe)

                set_bus_control_voltage(i=i,
                                        j=-1,
                                        remote_control=False,
                                        bus_name=elm.bus.name,
                                        bus_data=bus_data,
                                        bus_voltage_used=bus_voltage_used,
                                        candidate_Vm=elm.get_Vm_at(t_idx),
                                        use_stored_guess=use_stored_guess,
                                        logger=logger)

            elif elm.mode == ExternalGridMode.PV:

                set_bus_control_voltage(i=i,
                                        j=-1,
                                        remote_control=False,
                                        bus_name=elm.bus.name,
                                        bus_data=bus_data,
                                        bus_voltage_used=bus_voltage_used,
                                        candidate_Vm=elm.get_Vm_at(t_idx),
                                        use_stored_guess=use_stored_guess,
                                        logger=logger)

            data.S[ii] += elm.get_S_at(t_idx)

            if fill_three_phase:
                if elm.conn == ShuntConnectionType.GroundedStar:
                    data.S3_star[3 * ii + 1] += elm.get_Sa_at(t_idx)
                    data.S3_star[3 * ii + 2] += elm.get_Sb_at(t_idx)
                    data.S3_star[3 * ii + 3] += elm.get_Sc_at(t_idx)

                elif elm.conn == ShuntConnectionType.Delta:
                    data.S3_delta[3 * ii + 1] += elm.get_Sa_at(t_idx)
                    data.S3_delta[3 * ii + 2] += elm.get_Sb_at(t_idx)
                    data.S3_delta[3 * ii + 3] += elm.get_Sc_at(t_idx)

                else:
                    raise Exception(f"Unhandled connection type {elm.conn}")

            data.active[ii] = elm.get_active_at(t_idx)
            data.shift_key[ii] = elm.get_shift_key_at(t_idx)

            if elm.use_kw:
                # pass kW to MW
                data.S[ii] /= 1000.0
                data.cost[ii] /= 1000.0

            # reactive power sharing data
            if data.active[ii]:
                bus_data.q_fixed[i] += data.S[ii].imag
                bus_data.ii_fixed[i] += data.I[ii].imag
                bus_data.b_fixed[i] += data.Y[ii].imag

        # data.C_bus_elm[i, ii] = 1
        ii += 1

    for elm in circuit.get_current_injections():

        if elm.bus is None:
            data.bus_idx[ii] = -1
            data.active[ii] = False
        else:
            i = bus_dict[elm.bus]
            data.bus_idx[ii] = i
            data.names[ii] = elm.name
            data.idtag[ii] = elm.idtag
            data.original_idx[ii] = ii
            data.mttf[ii] = elm.mttf
            data.mttr[ii] = elm.mttr
            data.scalable[ii] = elm.scalable

            data.I[ii] += elm.get_I_at(t_idx)

            if fill_three_phase:
                if elm.conn == ShuntConnectionType.GroundedStar:

                    data.I3_star[3 * ii + 1] += np.conj(elm.get_I1_at(t_idx))
                    data.I3_star[3 * ii + 2] += np.conj(elm.get_I2_at(t_idx))
                    data.I3_star[3 * ii + 3] += np.conj(elm.get_I3_at(t_idx))

                elif elm.conn == ShuntConnectionType.Delta:

                    data.I3_delta[3 * ii + 1] += np.conj(elm.get_I1_at(t_idx))
                    data.I3_delta[3 * ii + 2] += np.conj(elm.get_I2_at(t_idx))
                    data.I3_delta[3 * ii + 3] += np.conj(elm.get_I3_at(t_idx))

                else:
                    raise Exception(f"Unhandled connection type {elm.conn}")

            data.active[ii] = elm.get_active_at(t_idx)
            data.cost[ii] = elm.get_Cost_at(t_idx)
            data.shift_key[ii] = elm.get_shift_key_at(t_idx)

            if elm.use_kw:
                # pass kW to MW
                data.I[ii] /= 1000.0
                data.cost[ii] /= 1000.0

                # reactive power sharing data
            if data.active[ii]:
                bus_data.q_fixed[i] += data.S[ii].imag
                bus_data.ii_fixed[i] += data.I[ii].imag
                bus_data.b_fixed[i] += data.Y[ii].imag

        # data.C_bus_elm[i, ii] = 1
        ii += 1

    return data


def get_shunt_data(
        data: ShuntData,
        circuit: MultiCircuit,
        bus_dict,
        bus_voltage_used: BoolVec,
        bus_data: BusData,
        t_idx: int | None,
        logger: Logger,
        use_stored_guess: bool = False,
        control_remote_voltage: bool = True,
        fill_three_phase: bool = False
) -> None:
    """

    :param data:
    :param circuit:
    :param bus_dict:
    :param bus_voltage_used:
    :param bus_data:
    :param logger:
    :param t_idx:
    :param use_stored_guess:
    :param control_remote_voltage:
    :param fill_three_phase:
    :return:
    """

    ii = 0
    for k, elm in enumerate(circuit.shunts):

        if elm.bus is None:
            data.bus_idx[k] = -1
            data.active[k] = False
        else:

            i = bus_dict[elm.bus]
            data.bus_idx[k] = i
            data.names[k] = elm.name
            data.idtag[k] = elm.idtag
            data.original_idx[ii] = ii
            data.mttf[k] = elm.mttf
            data.mttr[k] = elm.mttr

            data.active[k] = elm.get_active_at(t_idx)
            data.grounds_neutral[k] = elm.phN and elm.conn == ShuntConnectionType.GroundedStar
            data.conn[k] = elm.conn.idx()
            data.Y[k] = elm.get_Y_at(t_idx)

            if fill_three_phase:

                if elm.conn == ShuntConnectionType.GroundedStar:

                    Y_abc = any([elm.get_Ya_at(t_idx), elm.get_Yb_at(t_idx), elm.get_Yc_at(t_idx)])

                    if not Y_abc:
                        data.Y3_star[4 * ii + 1, 1] = elm.get_Y_at(t_idx) / 3
                        data.Y3_star[4 * ii + 2, 2] = elm.get_Y_at(t_idx) / 3
                        data.Y3_star[4 * ii + 3, 3] = elm.get_Y_at(t_idx) / 3

                    else:
                        data.Y3_star[4 * ii + 1, 1] = elm.get_Ya_at(t_idx)
                        data.Y3_star[4 * ii + 2, 2] = elm.get_Yb_at(t_idx)
                        data.Y3_star[4 * ii + 3, 3] = elm.get_Yc_at(t_idx)

                elif (elm.conn == ShuntConnectionType.FloatingStar
                      or (elm.conn == ShuntConnectionType.NeutralStar and not elm.phN)):

                    # Admittances
                    Ya = elm.get_Ya_at(t_idx)
                    Yb = elm.get_Yb_at(t_idx)
                    Yc = elm.get_Yc_at(t_idx)

                    Ysum = Ya + Yb + Yc

                    if Ysum != 0.0 + 0.0j:
                        data.A_floating_star[ii] = Ya / Ysum
                        data.B_floating_star[ii] = Yb / Ysum
                        data.C_floating_star[ii] = Yc / Ysum

                        A = Ya / Ysum
                        B = Yb / Ysum
                        C = Yc / Ysum

                        # First row
                        data.Y3_star[4 * ii + 1, 1] = (1 - A) * Ya
                        data.Y3_star[4 * ii + 1, 2] = -B * Ya
                        data.Y3_star[4 * ii + 1, 3] = -C * Ya

                        # Second row
                        data.Y3_star[4 * ii + 2, 1] = -A * Yb
                        data.Y3_star[4 * ii + 2, 2] = (1 - B) * Yb
                        data.Y3_star[4 * ii + 2, 3] = -C * Yb

                        # Third row
                        data.Y3_star[4 * ii + 3, 1] = -A * Yc
                        data.Y3_star[4 * ii + 3, 2] = -B * Yc
                        data.Y3_star[4 * ii + 3, 3] = (1 - C) * Yc

                elif elm.conn == ShuntConnectionType.NeutralStar:

                    # Admittance
                    Ya = elm.get_Ya_at(t_idx)
                    Yb = elm.get_Yb_at(t_idx)
                    Yc = elm.get_Yc_at(t_idx)
                    # First row
                    data.Y3_star[4 * ii + 0, 0] = Ya + Yb + Yc + 1e-10j
                    data.Y3_star[4 * ii + 0, 1] = -Ya
                    data.Y3_star[4 * ii + 0, 2] = -Yb
                    data.Y3_star[4 * ii + 0, 3] = -Yc
                    # Second row
                    data.Y3_star[4 * ii + 1, 0] = -Ya
                    data.Y3_star[4 * ii + 1, 1] = Ya
                    # Third row
                    data.Y3_star[4 * ii + 2, 0] = -Yb
                    data.Y3_star[4 * ii + 2, 2] = Yb
                    # Fourth row
                    data.Y3_star[4 * ii + 3, 0] = -Yc
                    data.Y3_star[4 * ii + 3, 3] = Yc

                elif elm.conn == ShuntConnectionType.Delta:

                    data.Y3_star[4 * ii:4 * ii + 4, [0, 1, 2, 3]] = delta2StarAdmittance(
                        Yab=elm.get_Ya_at(t_idx),
                        Ybc=elm.get_Yb_at(t_idx),
                        Yca=elm.get_Yc_at(t_idx)
                    )

                else:
                    raise Exception(f"Unhandled connection type {elm.conn}")

            if elm.use_kw:
                # pass kW to MW
                data.Y[ii] /= 1000.0

            # reactive power sharing data
            if data.active[ii]:
                bus_data.b_fixed[i] += data.Y[ii].imag

        # data.C_bus_elm[i, k] = 1
        ii += 1

    for elm in circuit.controllable_shunts:

        if elm.bus is None:
            data.bus_idx[ii] = -1
            data.active[ii] = False
        else:
            i = bus_dict[elm.bus]
            data.bus_idx[ii] = i
            data.names[ii] = elm.name
            data.idtag[ii] = elm.idtag
            data.original_idx[ii] = ii
            data.mttf[ii] = elm.mttf
            data.mttr[ii] = elm.mttr

            data.control_mode_int[ii] = elm.control_mode.idx()
            data.conn[ii] = elm.conn.idx()

            data.vset[ii] = elm.get_Vset_at(t_idx)
            data.vmin[ii] = elm.Vmin
            data.vmax[ii] = elm.Vmax
            if elm.control_mode == ShuntControlMode.Continuous:
                data.qmin[ii] = -elm.Bmax
                data.qmax[ii] = -elm.Bmin
            else:
                data.qmin[ii] = elm.Bmin
                data.qmax[ii] = elm.Bmax

            data.step[ii] = elm.step
            data.g_steps.insert(i=ii, x=np.insert(np.cumsum(elm.g_steps), 0, 0))
            data.b_steps.insert(i=ii, x=np.insert(np.cumsum(elm.b_steps), 0, 0))

            data.active[ii] = elm.get_active_at(t_idx)
            data.cost[ii] = elm.get_Cost_at(t_idx)

            if elm.control_mode == ShuntControlMode.Locked:
                data.Y[ii] += elm.get_Y_at(t_idx)

            if elm.control_mode == ShuntControlMode.Continuous:
                data.Y[ii] += elm.get_Y_at(t_idx)

            if elm.control_mode == ShuntControlMode.Discrete:
                # Base injection at the current step, using the same 0-prepended
                # cumulative ladder as data.b_steps/data.g_steps and the discrete
                # controller (step 0 = neutral/off, step k = first k blocks on).
                cum_b = np.insert(np.cumsum(elm.b_steps), 0, 0.0)
                cum_g = np.insert(np.cumsum(elm.g_steps), 0, 0.0)
                s = elm.step if 0 <= elm.step < len(cum_b) else 0
                data.Y[ii] += complex(cum_g[s], cum_b[s])

            if fill_three_phase:
                if elm.control_mode == ShuntControlMode.Continuous:
                    # U1 control solves a common susceptance in the existing controller.
                    # Keep only conductance here, avoiding a second fixed B contribution.
                    if elm.conn == ShuntConnectionType.GroundedStar:
                        pattern: np.ndarray = np.eye(3, dtype=complex)
                    elif elm.conn in (ShuntConnectionType.Delta, ShuntConnectionType.FloatingStar):
                        pattern = fortescue_012_to_abc(0j, 1+0j, 1+0j)
                    else:
                        raise ValueError('Continuous shunt U1 control does not support an explicit neutral: '
                                         + elm.name)
                    admittance: complex = complex(data.Y[ii].real)
                    if bus_data.bus_types[i] == BusMode.Slack_tpe.value:
                        # The ideal slack supplies voltage control; retain this shunt's fixed step.
                        admittance = data.Y[ii]
                    else:
                        pass
                    if elm.use_kw:
                        admittance /= 1000.0
                    else:
                        pass
                    data.Y3_star[4 * ii + 1:4 * ii + 4, 1:4] = (
                        pattern * admittance * data.active[ii] / 3.0)
                    data.qmin[ii] /= 1000.0 if elm.use_kw else 1.0
                    data.qmax[ii] /= 1000.0 if elm.use_kw else 1.0
                elif elm.conn == ShuntConnectionType.GroundedStar:

                    data.Y3_star[3 * ii + 0, 1] = elm.get_Ya_at(t_idx)
                    data.Y3_star[3 * ii + 1, 2] = elm.get_Yb_at(t_idx)
                    data.Y3_star[3 * ii + 2, 3] = elm.get_Yc_at(t_idx)

                elif elm.conn == ShuntConnectionType.Delta:

                    data.Y3_star[4 * ii:4 * ii + 4, [0, 1, 2, 3]] = delta2StarAdmittance(
                        Yab=elm.get_Ya_at(t_idx),
                        Ybc=elm.get_Yb_at(t_idx),
                        Yca=elm.get_Yc_at(t_idx)
                    )

                else:
                    raise Exception(f"Unhandled connection type {elm.conn}")

            if elm.control_mode == ShuntControlMode.Continuous and data.active[ii]:
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
                                        candidate_Vm=elm.get_Vset_at(t_idx),
                                        use_stored_guess=use_stored_guess,
                                        logger=logger)

            if elm.use_kw:
                # pass kW to MW
                data.Y[ii] /= 1000.0

            # reactive power sharing data
            if data.active[ii]:
                if data.control_mode_int[ii] == ShuntControlMode.Locked.idx():
                    bus_data.q_shared_total[i] += data.Y[ii].imag
                    data.q_share[ii] = data.Y[ii].imag
                else:
                    bus_data.b_fixed[i] += data.Y[ii].imag

        # data.C_bus_elm[i, ii] = 1
        ii += 1


def fill_generator_parent(
        k: int,
        data: GeneratorData | BatteryData,
        elm: dev.Generator | dev.Battery,
        bus_dict: Dict[dev.Bus, int],
        bus_voltage_used: BoolVec,
        logger: Logger,
        bus_data: BusData,
        t_idx: int | None = None,
        use_stored_guess: bool = False,
        control_remote_voltage: bool = True,
        fill_three_phase: bool = False
) -> None:
    """
    Fill the common ancestor of generation and batteries
    :param k:
    :param data:
    :param elm:
    :param bus_dict:
    :param bus_voltage_used:
    :param logger:
    :param bus_data:
    :param t_idx:
    :param use_stored_guess:
    :param control_remote_voltage:
    :param fill_three_phase:
    :return:
    """
    if elm.bus is None:
        data.bus_idx[k] = -1
        data.active[k] = False
        return

    idx3 = np.arange(3)
    i = bus_dict[elm.bus]
    data.bus_idx[k] = i
    data.names[k] = elm.name
    data.idtag[k] = elm.idtag
    data.original_idx[k] = k
    data.mttf[k] = elm.mttf
    data.mttr[k] = elm.mttr

    control_mode: GeneratorControlMode = elm.get_control_mode_prof_at(t_idx)
    data.control_mode_int[k] = control_mode.idx()
    data.conn[k] = elm.conn.idx()
    data.installed_p[k] = elm.Snom
    bus_data.installed_power[i] += elm.Snom

    # r0, r1, r2, x0, x1, x2
    data.r0[k] = elm.R0
    data.r1[k] = elm.R1
    data.r2[k] = elm.R2
    data.x0[k] = elm.X0
    data.x1[k] = elm.X1
    data.x2[k] = elm.X2

    # asynchronous generator impedance
    data.Rs[k] = elm.Rs
    data.Xs[k] = elm.Xs
    data.Xm[k] = elm.Xm
    data.Rr[k] = elm.Rr
    data.Xr[k] = elm.Xr

    data.tpe_int[k] = elm.tpe.idx()

    data.startup_cost[k] = elm.startup_cost
    data.shut_down_cost[k] = elm.shutdown_cost

    data.ramp_up[k] = elm.ramp_up
    data.ramp_down[k] = elm.ramp_down
    data.min_time_up[k] = elm.min_time_up
    data.min_time_down[k] = elm.min_time_down

    data.dispatchable[k] = elm.get_enabled_dispatch_at(t_idx)
    data.must_run[k] = elm.get_must_run_at(t_idx)
    data.capex[k] = elm.capex

    data.snom[k] = elm.Snom
    data.scalable[k] = elm.scalable

    data.p[k] = elm.get_P_at(t_idx)
    data.active[k] = elm.get_active_at(t_idx)
    if hasattr(data, 'is_static_generator'):
        data.is_static_generator[k] = elm.is_static_generator

    data.v[k] = elm.get_Vset_at(t_idx)
    data.k_droop[k] = elm.k_droop
    data.dead_band[k] = elm.dead_band
    pmin, pmax = normalize_upper_bound(
        lower=elm.get_Pmin_at(t_idx),
        upper=elm.get_Pmax_at(t_idx),
        logger=logger,
        device_name=elm.name,
        device_class=str(elm.device_type.value),
        lower_name="Pmin",
        upper_name="Pmax",
    )
    data.pmax[k] = pmax
    data.pmin[k] = pmin

    if elm.use_reactive_power_curve:
        data.qmin[k] = elm.q_curve.get_qmin(data.p[k])
        data.qmax[k] = elm.q_curve.get_qmax(data.p[k])
    else:
        data.qmin[k] = elm.get_Qmin_at(t_idx)
        data.qmax[k] = elm.get_Qmax_at(t_idx)

    data.cost_0[k] = elm.get_Cost0_at(t_idx)
    data.cost_1[k] = elm.get_Cost_at(t_idx)
    data.cost_2[k] = elm.get_Cost2_at(t_idx)
    data.shift_key[k] = elm.get_shift_key_at(t_idx)

    if data.active[k]:
        if elm.get_srap_enabled_at(t_idx) and data.p[k] > 0.0:
            bus_data.srap_available_power[i] += data.p[k]

        if control_mode == GeneratorControlMode.V:
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
                                    candidate_Vm=elm.get_Vset_at(t_idx),
                                    use_stored_guess=use_stored_guess,
                                    logger=logger)
            data.q[k] = 0.0

        elif control_mode == GeneratorControlMode.Q:
            data.q[k] = elm.get_Q_at(t_idx)

        elif control_mode == GeneratorControlMode.QVDroop:
            # Q will be computed by the droop
            data.q[k] = 0.0
        else:
            pass

    if elm.use_kw:
        # pass kW to MW
        data.p[k] /= 1000.0
        data.pmax[k] /= 1000.0
        data.pmin[k] /= 1000.0
        data.qmax[k] /= 1000.0
        data.qmin[k] /= 1000.0
        data.snom[k] /= 1000.0
        # data.cost_0[k] /= 1000.0
        data.cost_1[k] /= 1000.0
        data.cost_2[k] /= 1e6  # this is because of MW^2

    if fill_three_phase:
        # Note: for a generator that is balanced, the delta and star configurations
        # translate to the same values in star
        data.p3_star[3 * k + idx3] = data.p[k] / 3.0

    # reactive power-sharing data
    # We use P as a reference for scaling, hence issues may arise if P = 0.0
    # Thus we add a small value to compensate for that
    # The small value cannot be 1e-20, as then the split of Q 
    # would be half the value (1e-20/1e-20). 
    # A value of 1e-14 seems a sweet compromise.
    if data.active[k]:
        if data.control_mode_int[k] == GeneratorControlMode.V.idx():
            bus_data.q_shared_total[i] += data.p[k] + 1e-14
            data.q_share[k] = data.p[k] + 1e-14
            # bus_data.q_shared_total[i] += data.p[k]
            # data.q_share[k] = data.p[k]
        else:
            bus_data.q_fixed[i] += data.get_q_at(k)


def get_generator_data(
        data: GeneratorData,
        circuit: MultiCircuit,
        bus_dict,
        bus_voltage_used: BoolVec,
        logger: Logger,
        bus_data: BusData,
        t_idx: int | None,
        opf_results: VALID_OPF_RESULTS | None = None,
        time_series: bool = False,
        use_stored_guess: bool = False,
        control_remote_voltage: bool = True,
        fill_three_phase: bool = False
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
    :param fill_three_phase:
    :return:
    """

    gen_index_dict: Dict[str, int] = dict()
    for k, elm in enumerate(circuit.get_generators()):

        gen_index_dict[elm.idtag] = k  # associate the idtag to the index

        fill_generator_parent(k=k,
                              elm=elm,
                              data=data,
                              bus_data=bus_data,
                              bus_dict=bus_dict,
                              bus_voltage_used=bus_voltage_used,
                              logger=logger,
                              t_idx=t_idx,
                              use_stored_guess=use_stored_guess,
                              control_remote_voltage=control_remote_voltage,
                              fill_three_phase=fill_three_phase)

        if opf_results is not None:
            # overwrite P with the OPF results
            if time_series:
                data.p[k] = opf_results.generator_power[t_idx, k] - opf_results.generator_shedding[t_idx, k]
            else:
                data.p[k] = opf_results.generator_power[k] - opf_results.generator_shedding[k]

    return gen_index_dict


def get_battery_data(
        data: BatteryData,
        circuit: MultiCircuit,
        bus_dict: Dict[Bus, int],
        bus_voltage_used: BoolVec,
        logger: Logger,
        bus_data: BusData,
        t_idx: int | None,
        opf_results: VALID_OPF_RESULTS | None = None,
        time_series=False,
        control_remote_voltage: bool = True,
        fill_three_phase: bool = False
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
    :param control_remote_voltage:
    :param fill_three_phase:
    :return:
    """

    for k, elm in enumerate(circuit.get_batteries()):

        fill_generator_parent(k=k,
                              elm=elm,
                              data=data,
                              bus_data=bus_data,
                              bus_dict=bus_dict,
                              bus_voltage_used=bus_voltage_used,
                              logger=logger,
                              t_idx=t_idx,
                              control_remote_voltage=control_remote_voltage,
                              fill_three_phase=fill_three_phase)

        data.enom[k] = elm.Enom
        min_soc, max_soc = normalize_upper_bound(
            lower=elm.min_soc,
            upper=elm.max_soc,
            logger=logger,
            device_name=elm.name,
            device_class=str(elm.device_type.value),
            lower_name="min_soc",
            upper_name="max_soc",
        )
        data.min_soc[k] = min_soc
        data.max_soc[k] = max_soc
        data.soc_0[k] = elm.soc_0
        e_min, e_max = normalize_upper_bound(
            lower=elm.Enom * data.min_soc[k],
            upper=elm.Enom * data.max_soc[k],
            logger=logger,
            device_name=elm.name,
            device_class=str(elm.device_type.value),
            lower_name="Emin",
            upper_name="Emax",
        )
        data.e_min[k] = e_min
        data.e_max[k] = e_max
        data.discharge_efficiency[k] = elm.discharge_efficiency
        data.charge_efficiency[k] = elm.charge_efficiency

        if opf_results is not None:
            # overwrite P with the OPF results
            if time_series:
                data.p[k] = opf_results.battery_power[t_idx, k]
            else:
                data.p[k] = opf_results.battery_power[k]


def fill_parent_branch(i: int,
                       elm: BRANCH_TYPES,
                       data: PassiveBranchData,
                       bus_data: BusData,
                       bus_dict: Dict[Bus, int],
                       bus_voltage_used: BoolVec,
                       use_stored_guess=False,
                       t_idx: int | None = None, ):
    """

    :param i:
    :param elm:
    :param data:
    :param bus_data:
    :param bus_dict:
    :param bus_voltage_used:
    :param use_stored_guess:
    :param t_idx:
    :return:
    """
    data.names[i] = elm.name
    data.idtag[i] = elm.idtag

    data.mttf[i] = elm.mttf
    data.mttr[i] = elm.mttr

    data.active[i] = elm.get_active_at(t_idx)
    data.rates[i] = elm.get_rate_at(t_idx)
    data.contingency_rates[i] = data.rates[i] * elm.get_contingency_factor_at(t_idx)
    data.protection_rates[i] = data.rates[i] * elm.get_protection_rating_factor_at(t_idx)
    data.overload_cost[i] = elm.get_Cost_at(t_idx)

    f = bus_dict[elm.bus_from]
    t = bus_dict[elm.bus_to]
    data.F[i] = f
    data.T[i] = t

    data.original_idx[i] = i
    data.reducible[i] = int(elm.reducible)
    data.contingency_enabled[i] = int(elm.contingency_enabled)
    data.monitor_loading[i] = int(elm.monitor_loading)

    data.virtual_tap_f[i], data.virtual_tap_t[i] = elm.get_virtual_taps()

    # This is to initialize the bus voltages for branches
    # that do have a significant virtual tap difference.
    # i.e. transformers for distribution systems

    # Grounded buses carry a pinned ground-reference Vbus from get_bus_data
    # and must not be overwritten by the virtual-tap default.
    if not bus_voltage_used[f] and not use_stored_guess and not bus_data.is_grounded[f]:
        bus_data.Vbus[f] = data.virtual_tap_f[i]

    if not bus_voltage_used[t] and not use_stored_guess and not bus_data.is_grounded[t]:
        bus_data.Vbus[t] = data.virtual_tap_t[i]

    return f, t


def fill_controllable_branch(
        ii: int,
        elm: Union[dev.Transformer2W, dev.Winding, dev.UPFC],
        data: PassiveBranchData,
        ctrl_data: ActiveBranchData,
        bus_data: BusData,
        bus_dict: Dict[Bus, int],
        t_idx: int | None,
        opf_results: VALID_OPF_RESULTS | None,
        use_stored_guess: bool,
        bus_voltage_used: BoolVec,
        Sbase: float,
        control_taps_modules: bool,
        control_taps_phase: bool,
        logger: Logger):
    """

    :param ii:
    :param elm:
    :param data:
    :param ctrl_data:
    :param bus_data:
    :param bus_dict:
    :param t_idx:
    :param opf_results:
    :param use_stored_guess:
    :param bus_voltage_used:
    :param Sbase:
    :param control_taps_modules:
    :param control_taps_phase:
    :param logger:
    :return:
    """
    fill_parent_branch(i=ii,
                       elm=elm,
                       data=data,
                       bus_data=bus_data,
                       bus_dict=bus_dict,
                       bus_voltage_used=bus_voltage_used,
                       use_stored_guess=use_stored_guess,
                       t_idx=t_idx)

    if control_taps_phase:
        ctrl_data.tap_phase_control_mode[ii] = elm.get_tap_phase_control_mode_at(t_idx).idx()

    if control_taps_modules:
        ctrl_data.tap_module_control_mode[ii] = elm.get_tap_module_control_mode_at(t_idx).idx()

        if elm.regulation_bus is None:
            reg_bus = elm.bus_from
            if ctrl_data.tap_module_control_mode[ii] == TapModuleControl.Vm.idx():
                logger.add_warning("Unspecified regulation bus",
                                   device_class=elm.device_type.value,
                                   device=elm.name)
        else:
            reg_bus = elm.regulation_bus

        ctrl_data.tap_controlled_buses[ii] = bus_dict[reg_bus]

    ctrl_data.Pset[ii] = elm.get_Pset_at(t_idx) / Sbase
    ctrl_data.Qset[ii] = elm.get_Qset_at(t_idx) / Sbase
    ctrl_data.vset[ii] = elm.get_vset_at(t_idx)

    if opf_results is not None:
        if opf_results.tap_angle.ndim == 1:
            ctrl_data.tap_angle[ii] = opf_results.tap_angle[ii]
        else:
            if t_idx is None:
                ctrl_data.tap_angle[ii] = opf_results.tap_angle[0, ii]
            else:
                ctrl_data.tap_angle[ii] = opf_results.tap_angle[t_idx, ii]

        ctrl_data.tap_module[ii] = elm.get_tap_module_at(t_idx)
        ctrl_data.tap_phase_control_mode[ii] = TapPhaseControl.fixed.idx()
        ctrl_data.tap_module_control_mode[ii] = TapModuleControl.fixed.idx()
    else:
        ctrl_data.tap_angle[ii] = elm.get_tap_phase_at(t_idx)
        ctrl_data.tap_module[ii] = elm.get_tap_module_at(t_idx)

    ctrl_data.is_controlled[ii] = 1
    tap_module_min, tap_module_max = normalize_upper_bound(
        lower=elm.tap_module_min,
        upper=elm.tap_module_max,
        logger=logger,
        device_name=elm.name,
        device_class=str(elm.device_type.value),
        lower_name="tap_module_min",
        upper_name="tap_module_max",
    )
    ctrl_data.tap_module_min[ii] = tap_module_min
    ctrl_data.tap_module_max[ii] = tap_module_max

    tap_angle_min, tap_angle_max = normalize_upper_bound(
        lower=elm.tap_phase_min,
        upper=elm.tap_phase_max,
        logger=logger,
        device_name=elm.name,
        device_class=str(elm.device_type.value),
        lower_name="tap_angle_min",
        upper_name="tap_angle_max",
    )
    ctrl_data.tap_angle_min[ii] = tap_angle_min
    ctrl_data.tap_angle_max[ii] = tap_angle_max

    if ctrl_data.tap_module_control_mode[ii] != TapModuleControl.fixed.idx():
        ctrl_data.any_pf_control = True

    if not ctrl_data.any_pf_control:  # if true, we can skip this step
        if ctrl_data.tap_phase_control_mode[ii] != TapPhaseControl.fixed.idx():
            ctrl_data.any_pf_control = True

    if not use_stored_guess:
        if ctrl_data.tap_module_control_mode[ii] == TapModuleControl.Vm.idx():
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

        # modify the voltage angle guess using the phase
        if ctrl_data.tap_angle[ii] != 0:
            f = bus_dict[elm.bus_from]
            t = bus_dict[elm.bus_to]
            Vm = abs(bus_data.Vbus[f])
            Va = np.angle(bus_data.Vbus[f], deg=False)
            bus_data.Vbus[f] = Vm * np.exp(1j * (Va + ctrl_data.tap_angle[ii]))


def get_branch_data(
        data: PassiveBranchData,
        ctrl_data: ActiveBranchData,
        circuit: MultiCircuit,
        bus_dict: Dict[Bus, int],
        bus_data: BusData,
        bus_voltage_used: BoolVec,
        apply_temperature: bool,
        branch_tolerance_mode: BranchImpedanceMode,
        t_idx: int | None,
        opf_results: VALID_OPF_RESULTS | None = None,
        use_stored_guess: bool = False,
        control_taps_modules: bool = True,
        control_taps_phase: bool = True,
        logger: Logger = Logger(),
        fill_three_phase: bool = False
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
    :param opf_results: OptimalPowerFlowResults
    :param use_stored_guess: use the stored voltage ?
    :param control_taps_modules: Control TapsModules
    :param control_taps_phase: Control TapsPhase
    :param logger: Logger
    :param fill_three_phase: Fill the tree phase info?
    :return: BranchData
    """

    branch_dict: Dict[BRANCH_TYPES, int] = dict()
    idx4 = np.array(range(4))

    ii = 0

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        # generic stuff
        fill_parent_branch(i=ii,
                           elm=elm,
                           data=data,
                           bus_data=bus_data,
                           bus_dict=bus_dict,
                           bus_voltage_used=bus_voltage_used,
                           use_stored_guess=use_stored_guess,
                           t_idx=t_idx)

        data.R[ii] = elm.R_corrected if apply_temperature else elm.R

        if branch_tolerance_mode == BranchImpedanceMode.Lower:
            data.R[ii] *= (1 - elm.tolerance / 100.0)
        elif branch_tolerance_mode == BranchImpedanceMode.Upper:
            data.R[ii] *= (1 + elm.tolerance / 100.0)

        data.X[ii] = elm.X
        data.B[ii] = elm.B
        # Keep the physical line shunt in the existing sequence data owners.
        data.G[ii] = elm.G

        data.R0[ii] = elm.R0
        data.X0[ii] = elm.X0
        data.B0[ii] = elm.B0
        data.G0[ii] = elm.G0

        data.R2[ii] = elm.R2
        data.X2[ii] = elm.X2
        data.B2[ii] = elm.B2

        if fill_three_phase:
            """
            yff = ys_abc + ysh_abc / 2
            yft = - ys_abc
            ytf = - ys_abc
            ytt = ys_abc + ysh_abc / 2
            """
            k4 = 4 * ii + idx4
            y1 = elm.ys.values + elm.ysh.values / 2.0 * 1e-6
            y2 = - elm.ys.values
            data.Yff3[k4, :] = y1
            data.Yft3[k4, :] = y2
            data.Ytf3[k4, :] = y2
            data.Ytt3[k4, :] = y1

            """ Save the phases of each line """
            data.phN[ii] = elm.ys.phN
            data.phA[ii] = elm.ys.phA
            data.phB[ii] = elm.ys.phB
            data.phC[ii] = elm.ys.phC

        # store for later
        branch_dict[elm] = ii

        # Physical line templates are defined by their phase matrices. A single-phase
        # tower or cable can have zero sequence scalars without being an ideal link.
        is_physical_line: bool = isinstance(
            elm.template,
            (dev.OverheadLineType, dev.UndergroundLineType),
        )
        if is_physical_line:
            pass
        else:
            data.detect_superconductor_at(ii)

        ii += 1

    # DC-lines
    for i, elm in enumerate(circuit.dc_lines):
        # generic stuff
        fill_parent_branch(i=ii,
                           elm=elm,
                           data=data,
                           bus_data=bus_data,
                           bus_dict=bus_dict,
                           bus_voltage_used=bus_voltage_used,
                           use_stored_guess=use_stored_guess,
                           t_idx=t_idx)

        data.R[ii] = elm.R_corrected if apply_temperature else elm.R

        if branch_tolerance_mode == BranchImpedanceMode.Lower:
            data.R[ii] *= (1 - elm.tolerance / 100.0)
        elif branch_tolerance_mode == BranchImpedanceMode.Upper:
            data.R[ii] *= (1 + elm.tolerance / 100.0)

        # store for later
        branch_dict[elm] = ii

        data.dc[ii] = 1

        # handle """superconductor branches"""
        data.detect_superconductor_at(ii)

        ii += 1

    # 2-winding transformers
    for i, elm in enumerate(circuit.transformers2w):
        fill_controllable_branch(ii=ii,
                                 elm=elm,
                                 data=data,
                                 ctrl_data=ctrl_data,
                                 bus_data=bus_data,
                                 bus_dict=bus_dict,
                                 t_idx=t_idx,
                                 opf_results=opf_results,
                                 use_stored_guess=use_stored_guess,
                                 bus_voltage_used=bus_voltage_used,
                                 Sbase=circuit.Sbase,
                                 control_taps_modules=control_taps_modules,
                                 control_taps_phase=control_taps_phase,
                                 logger=logger)

        data.R[ii] = elm.R_corrected if apply_temperature else elm.R

        if branch_tolerance_mode == BranchImpedanceMode.Lower:
            data.R[ii] *= (1 - elm.tolerance / 100.0)
        elif branch_tolerance_mode == BranchImpedanceMode.Upper:
            data.R[ii] *= (1 + elm.tolerance / 100.0)

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

        if fill_three_phase:
            k4 = 4 * ii + idx4
            (data.Yff3[k4, :],
             data.Yft3[k4, :],
             data.Ytf3[k4, :],
             data.Ytt3[k4, :]) = elm.transformer_admittance(vtap_f=data.virtual_tap_f[ii],
                                                            vtap_t=data.virtual_tap_t[ii],
                                                            logger=logger)
            (data.phN[ii],
             data.phA[ii],
             data.phB[ii],
             data.phC[ii]) = elm.transformer_phases(logger=logger)

        data.conn[ii] = elm.conn.idx()
        data.conn_f[ii] = elm.conn_f.idx()
        data.conn_t[ii] = elm.conn_t.idx()
        data.m_taps[ii] = elm.tap_changer.tap_modules_array
        data.tau_taps[ii] = elm.tap_changer.tap_angles_array

        # store for later
        branch_dict[elm] = ii

        # handle """superconductor branches"""
        data.detect_superconductor_at(ii)

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
                                     t_idx=t_idx,
                                     opf_results=opf_results,
                                     use_stored_guess=use_stored_guess,
                                     bus_voltage_used=bus_voltage_used,
                                     Sbase=circuit.Sbase,
                                     control_taps_modules=control_taps_modules,
                                     control_taps_phase=control_taps_phase,
                                     logger=logger)

            data.R[ii] = elm.R_corrected if apply_temperature else elm.R

            if branch_tolerance_mode == BranchImpedanceMode.Lower:
                data.R[ii] *= (1 - elm.tolerance / 100.0)
            elif branch_tolerance_mode == BranchImpedanceMode.Upper:
                data.R[ii] *= (1 + elm.tolerance / 100.0)

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

            if fill_three_phase:
                k4 = 4 * ii + idx4
                (data.Yff3[k4, :], data.Yft3[k4, :],
                 data.Ytf3[k4, :], data.Ytt3[k4, :]) = elm.transformer_admittance(
                    vtap_f=data.virtual_tap_f[ii], vtap_t=data.virtual_tap_t[ii], logger=logger)
                data.phN[ii], data.phA[ii], data.phB[ii], data.phC[ii] = elm.transformer_phases(logger)
            else:
                pass

            data.conn[ii] = elm.conn.idx()
            winding_conn_f: WindingType
            winding_conn_t: WindingType
            winding_conn_f, winding_conn_t = elm.get_winding_connections()
            data.conn_f[ii] = winding_conn_f.idx()
            data.conn_t[ii] = winding_conn_t.idx()
            data.m_taps[ii] = elm.tap_changer.tap_modules_array
            data.tau_taps[ii] = elm.tap_changer.tap_angles_array

            # store for later
            branch_dict[elm] = ii

            # handle """superconductor branches"""
            data.detect_superconductor_at(ii)

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
                                 t_idx=t_idx,
                                 opf_results=opf_results,
                                 use_stored_guess=use_stored_guess,
                                 bus_voltage_used=bus_voltage_used,
                                 Sbase=circuit.Sbase,
                                 control_taps_modules=control_taps_modules,
                                 control_taps_phase=control_taps_phase,
                                 logger=logger)
        ysh1 = elm.get_ysh1()
        data.R[ii] = elm.R
        data.X[ii] = elm.X
        data.G[ii] = ysh1.real
        data.B[ii] = ysh1.imag

        ysh0 = elm.get_ysh0()
        data.R0[ii] = elm.R0
        data.X0[ii] = elm.X0
        data.G0[ii] = ysh0.real
        data.B0[ii] = ysh0.imag

        ysh2 = elm.get_ysh2()
        data.R2[ii] = elm.R2
        data.X2[ii] = elm.X2
        data.G2[ii] = ysh2.real
        data.B2[ii] = ysh2.imag

        # store for later
        branch_dict[elm] = ii

        # handle """superconductor branches"""
        data.detect_superconductor_at(ii)

        ii += 1

    # Series reactance
    for i, elm in enumerate(circuit.series_reactances):
        # generic stuff
        fill_parent_branch(i=ii,
                           elm=elm,
                           data=data,
                           bus_data=bus_data,
                           bus_dict=bus_dict,
                           bus_voltage_used=bus_voltage_used,
                           use_stored_guess=use_stored_guess,
                           t_idx=t_idx)

        data.R[ii] = elm.R_corrected if apply_temperature else elm.R

        if branch_tolerance_mode == BranchImpedanceMode.Lower:
            data.R[ii] *= (1 - elm.tolerance / 100.0)
        elif branch_tolerance_mode == BranchImpedanceMode.Upper:
            data.R[ii] *= (1 + elm.tolerance / 100.0)

        data.X[ii] = elm.X

        data.R0[ii] = elm.R0
        data.X0[ii] = elm.X0

        data.R2[ii] = elm.R2
        data.X2[ii] = elm.X2

        if fill_three_phase:
            # Reuse the sequence transformation; a reactor has no shunt branch.
            # As for legacy lines, unspecified sequence data inherit Z1.
            z1: complex = complex(data.R[ii], data.X[ii])
            z0: complex = complex(data.R0[ii], data.X0[ii])
            z2: complex = complex(data.R2[ii], data.X2[ii])
            z0 = z0 if abs(z0) > 1e-10 else z1
            z2 = z2 if abs(z2) > 1e-10 else z1
            k4 = 4 * ii + idx4
            ys: np.ndarray = np.zeros((4, 4), dtype=complex)
            if abs(z1) > 0.0:
                ys[1:, 1:] = fortescue_012_to_abc(1.0 / z0, 1.0 / z1, 1.0 / z2)
            else:
                # Ideal links are handled by the existing topology reduction.
                pass
            data.Yff3[k4, :] = ys
            data.Yft3[k4, :] = -ys
            data.Ytf3[k4, :] = -ys
            data.Ytt3[k4, :] = ys
            data.phA[ii] = data.phB[ii] = data.phC[ii] = True
        else:
            pass

        # store for later
        branch_dict[elm] = ii

        # handle """superconductor branches"""
        data.detect_superconductor_at(ii)

        ii += 1

    # Switches
    for i, elm in enumerate(circuit.switch_devices):
        # generic stuff
        fill_parent_branch(i=ii,
                           elm=elm,
                           data=data,
                           bus_data=bus_data,
                           bus_dict=bus_dict,
                           bus_voltage_used=bus_voltage_used,
                           use_stored_guess=use_stored_guess,
                           t_idx=t_idx)

        if fill_three_phase:
            data.phN[ii] = 1
            data.phA[ii] = 1
            data.phB[ii] = 1
            data.phC[ii] = 1

        data.R[ii] = elm.R
        data.X[ii] = elm.X

        # store for later
        branch_dict[elm] = ii

        # handle """superconductor branches"""
        data.detect_superconductor_at(ii)

        ii += 1

    if fill_three_phase:
        compile_line_couplings(circuit=circuit, data=data)
    else:
        pass
    return branch_dict


def compile_line_couplings(circuit: MultiCircuit, data: PassiveBranchData) -> None:
    """Stamp complete physical tower sections, including mutual circuit admittances.

    :param circuit: Device model; only explicitly associated lines are coupled.
    :param data: Compiled branches, with lines occupying the first rows.
    :return: None.
    """
    groups: dict[str, list[int]] = dict()
    for k, line in enumerate(circuit.lines):
        if line.coupling_group and data.active[k]:
            groups.setdefault(line.coupling_group, list()).append(k)
        else:
            pass
    mutual: lil_matrix = lil_matrix((8 * data.nelm, 8 * data.nelm), dtype=complex)
    for name, indices in groups.items():
        first: dev.Line = circuit.lines[indices[0]]
        tower: dev.OverheadLineType
        if not isinstance(first.template, dev.OverheadLineType):
            raise ValueError(f"Line coupling {name}: an overhead tower template is required")
        else:
            tower = first.template
        if not tower.is_computed():
            tower.compute()
        else:
            pass
        phases: IntVec = np.empty(3 * len(indices), dtype=int)
        lengths: np.ndarray = np.empty(3 * len(indices))
        for i, k in enumerate(indices):
            line: dev.Line = circuit.lines[k]
            if line.template is not tower:
                raise ValueError(f"Line coupling {name}: circuits must share a template")
            else:
                pass
            lengths[3 * i:3 * i + 3] = line.length
            for p in range(3):
                positions: IntVec = np.flatnonzero(tower.z_phases_abc == 3 * (line.circuit_idx - 1) + p + 1)
                if len(positions) != 1:
                    raise ValueError(f"Line coupling {name}: each circuit must contain A, B and C")
                else:
                    phases[3 * i + p] = positions[0]
        if len(np.unique(phases)) != len(phases) or np.any(~np.isfinite(lengths) | (lengths <= 0)):
            raise ValueError(f"Line coupling {name}: repeated circuit index or invalid section length")
        else:
            pass
        # Use the existing earth-wire reduction. A guard wire is not a load neutral.
        # Select active circuits before inversion: absent circuits carry no series current.
        # Self blocks retain each circuit's length; mutual blocks span the shorter circuit.
        section_lengths: np.ndarray = np.minimum.outer(lengths, lengths)
        ys: np.ndarray = np.linalg.inv(tower.z_abc[np.ix_(phases, phases)] * section_lengths)
        yh: np.ndarray = tower.y_abc[np.ix_(phases, phases)] * section_lengths
        for i, k in enumerate(indices):
            line = circuit.lines[k]
            rows: IntVec = 4 * k + np.arange(1, 4)
            block: slice = slice(3 * i, 3 * i + 3)
            zbase: float = line.get_max_bus_nominal_voltage() ** 2 / circuit.Sbase
            data.Yff3[4 * k:4 * k + 4, :] = 0.0
            data.Yft3[4 * k:4 * k + 4, :] = 0.0
            data.Ytf3[4 * k:4 * k + 4, :] = 0.0
            data.Ytt3[4 * k:4 * k + 4, :] = 0.0
            data.Yff3[rows, 1:4] = (ys[block, block] + yh[block, block] / 2) * zbase
            data.Ytt3[rows, 1:4] = data.Yff3[rows, 1:4]
            data.Yft3[rows, 1:4] = -ys[block, block] * zbase
            data.Ytf3[rows, 1:4] = data.Yft3[rows, 1:4]
            data.phN[k] = False
            data.phA[k] = data.phB[k] = data.phC[k] = True
            for j, peer in enumerate(indices):
                if i != j:
                    other: dev.Line = circuit.lines[peer]
                    columns: IntVec = 4 * peer + np.arange(1, 4)
                    peer_block: slice = slice(3 * j, 3 * j + 3)
                    base: float = (line.get_max_bus_nominal_voltage() *
                                   other.get_max_bus_nominal_voltage() / circuit.Sbase)
                    series: np.ndarray = ys[block, peer_block] * base
                    shunt: np.ndarray = yh[block, peer_block] * base / 2
                    # Reversed lines swap physical terminals, preserving their public from/to orientation.
                    f: IntVec = rows + (4 * data.nelm if line.coupling_reversed else 0)
                    t: IntVec = rows + (0 if line.coupling_reversed else 4 * data.nelm)
                    pf: IntVec = columns + (4 * data.nelm if other.coupling_reversed else 0)
                    pt: IntVec = columns + (0 if other.coupling_reversed else 4 * data.nelm)
                    mutual[np.ix_(f, pf)] = series + shunt
                    mutual[np.ix_(f, pt)] = -series
                    mutual[np.ix_(t, pf)] = -series
                    mutual[np.ix_(t, pt)] = series + shunt
                else:
                    pass
    data.Ycoupling3 = mutual.tocsc()


def set_control_dev(k: int,
                    f: int,
                    t: int,
                    control_int: int,
                    control_dev: Bus | BRANCH_TYPES | None,
                    control_val: float,
                    control_bus_idx: IntVec,
                    control_branch_idx: IntVec,
                    bus_dict: Dict[Bus, int],
                    bus_data: BusData,
                    bus_voltage_used: BoolVec,
                    bus_angle_used: BoolVec,
                    use_stored_guess: bool,
                    logger: Logger):
    """

    :param k: device index
    :param f:
    :param t:
    :param control_int: ConverterControlType
    :param control_dev: control device
    :param control_val: control value
    :param control_bus_idx: array to be filled in
    :param control_branch_idx: array to be filled in
    :param bus_dict: dictionary to be filled in
    :param bus_data: bus data
    :param bus_voltage_used: used bus voltage
    :param bus_angle_used: used bus angle
    :param use_stored_guess:
    :param logger:
    """
    if control_dev is not None:
        if control_dev.device_type == DeviceType.BusDevice:

            bus_idx = bus_dict[control_dev]

            control_bus_idx[k] = bus_idx

            if control_int == ConverterControlType.Vm_ac.idx():

                set_bus_control_voltage_vsc(i=bus_idx,
                                            j=-1,
                                            remote_control=False,
                                            bus_name=str(bus_data.names[bus_idx]),
                                            bus_voltage_used=bus_voltage_used,
                                            bus_data=bus_data,
                                            candidate_Vm=control_val,
                                            use_stored_guess=use_stored_guess,
                                            logger=logger)

            elif control_int == ConverterControlType.Vm_dc.idx():

                set_bus_control_voltage_vsc(i=bus_idx,
                                            j=-1,
                                            remote_control=False,
                                            bus_name=str(bus_data.names[bus_idx]),
                                            bus_voltage_used=bus_voltage_used,
                                            bus_data=bus_data,
                                            candidate_Vm=control_val,
                                            use_stored_guess=use_stored_guess,
                                            logger=logger)

            elif control_int == ConverterControlType.Va_ac.idx():
                set_bus_control_angle_vsc(i=bus_idx,
                                          j=-1,
                                          remote_control=False,
                                          bus_name=str(bus_data.names[bus_idx]),
                                          bus_angle_used=bus_angle_used,
                                          bus_data=bus_data,
                                          candidate_Va=control_val,
                                          use_stored_guess=use_stored_guess,
                                          logger=logger)

        else:
            # TODO: the formulation does not allow for VSC remote control yet
            # control_branch_idx[k] = branch_dict[control_dev]
            control_branch_idx[k] = k

    else:
        if control_int == ConverterControlType.Vm_ac.idx():
            control_bus_idx[k] = t

            set_bus_control_voltage_vsc(i=t,
                                        j=-1,
                                        remote_control=False,
                                        bus_name=str(bus_data.names[t]),
                                        bus_voltage_used=bus_voltage_used,
                                        bus_data=bus_data,
                                        candidate_Vm=control_val,
                                        use_stored_guess=use_stored_guess,
                                        logger=logger)

        elif control_int == ConverterControlType.Vm_dc.idx():
            control_bus_idx[k] = f

            set_bus_control_voltage_vsc(i=f,
                                        j=-1,
                                        remote_control=False,
                                        bus_name=str(bus_data.names[f]),
                                        bus_voltage_used=bus_voltage_used,
                                        bus_data=bus_data,
                                        candidate_Vm=control_val,
                                        use_stored_guess=use_stored_guess,
                                        logger=logger)

        elif control_int == ConverterControlType.Va_ac.idx():
            control_bus_idx[k] = t

            set_bus_control_angle_vsc(i=t,
                                      j=-1,
                                      remote_control=False,
                                      bus_name=str(bus_data.names[t]),
                                      bus_angle_used=bus_angle_used,
                                      bus_data=bus_data,
                                      candidate_Va=control_val,
                                      use_stored_guess=use_stored_guess,
                                      logger=logger)

        else:
            # control_branch_idx[k] = len(branch_dict) + k  # TODO: why?
            control_branch_idx[k] = k


def get_vsc_data(
        data: VscData,
        circuit: MultiCircuit,
        bus_dict: Dict[Bus, int],
        branch_dict: Dict[BRANCH_TYPES, int],
        bus_data: BusData,
        bus_voltage_used: BoolVec,
        t_idx: int | None,
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
    :param opf_results: OptimalPowerFlowResults
    :param use_stored_guess: use the stored voltage ?
    :param control_remote_voltage: Control RemoteVoltage
    :param logger: Logger
    :return: VscData
    """
    bus_angle_used = np.array(bus_data.bus_types == BusMode.Slack_tpe.value).astype(bool)
    ii = 0

    # VSC
    for i, elm in enumerate(circuit.vsc_devices):
        # generic stuff
        data.names[i] = elm.name
        data.idtag[i] = elm.idtag

        data.mttf[i] = elm.mttf
        data.mttr[i] = elm.mttr
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]
        data.original_idx[i] = i

        data.F[i] = f

        # TODO SANPEN: Handle the -1 everywhere for this
        data.F_dcn[i] = -1 if elm.bus_dc_n is None else bus_dict[elm.bus_dc_n]
        data.T[i] = t

        data.active[i] = elm.get_active_at(t_idx)
        data.rates[i] = elm.get_rate_at(t_idx)
        data.contingency_rates[i] = data.rates[i] * elm.get_contingency_factor_at(t_idx)
        data.protection_rates[i] = data.rates[i] * elm.get_protection_rating_factor_at(t_idx)

        data.overload_cost[i] = elm.get_Cost_at(t_idx)

        data.control1_int[ii] = elm.get_control1_at(t_idx).idx()
        data.control2_int[ii] = elm.get_control2_at(t_idx).idx()
        data.fault_control_int[ii] = elm.get_fault_control_at(t_idx).idx()
        data.control1_val[ii] = elm.get_control1_val_at(t_idx)
        data.control2_val[ii] = elm.get_control2_val_at(t_idx)
        data.control1_val_min[ii] = elm.control1_val_min
        data.control1_val_max[ii] = elm.control1_val_max
        data.control1_val_droop[ii] = elm.get_control1_val_droop_at(t_idx)
        data.control1_droop_val[ii] = elm.get_control1_droop_val_at(t_idx)
        data.control1_droop_val_min[ii] = elm.control1_droop_val_min
        data.control1_droop_val_max[ii] = elm.control1_droop_val_max
        data.control2_val_min[ii] = elm.control2_val_min
        data.control2_val_max[ii] = elm.control2_val_max
        data.control2_val_droop[ii] = elm.get_control2_val_droop_at(t_idx)
        data.control2_droop_val[ii] = elm.get_control2_droop_val_at(t_idx)
        data.control2_droop_val_min[ii] = elm.control2_droop_val_min
        data.control2_droop_val_max[ii] = elm.control2_droop_val_max

        # Using DC_positive to set the controls, may need to also pass DC_negative
        set_control_dev(k=ii, f=f, t=t,
                        control_int=data.control1_int[ii],
                        control_dev=elm.get_control1_dev_at(t_idx),
                        control_val=data.control1_val[ii],
                        control_bus_idx=data.control1_bus_idx,
                        control_branch_idx=data.control1_branch_idx,
                        bus_dict=bus_dict,
                        bus_data=bus_data,
                        bus_voltage_used=bus_voltage_used,
                        bus_angle_used=bus_angle_used,
                        use_stored_guess=use_stored_guess,
                        logger=logger)

        set_control_dev(k=ii, f=f, t=t,
                        control_int=data.control2_int[ii],
                        control_dev=elm.get_control2_dev_at(t_idx),
                        control_val=data.control2_val[ii],
                        control_bus_idx=data.control2_bus_idx,
                        control_branch_idx=data.control2_branch_idx,
                        bus_dict=bus_dict,
                        bus_data=bus_data,
                        bus_voltage_used=bus_voltage_used,
                        bus_angle_used=bus_angle_used,
                        use_stored_guess=use_stored_guess,
                        logger=logger)

        data.contingency_enabled[i] = int(elm.contingency_enabled)
        data.monitor_loading[i] = int(elm.monitor_loading)

        # data.Kdp[ii] = elm.kdp
        data.alpha1[ii] = elm.alpha1
        data.alpha2[ii] = elm.alpha2
        data.alpha3[ii] = elm.alpha3
        data.min_ac_voltage[ii] = elm.min_ac_voltage

        data.ysvs[ii] = elm.ysvs

        ii += 1


def get_hvdc_data(data: HvdcData,
                  circuit: MultiCircuit,
                  bus_dict,
                  bus_data: BusData,
                  bus_voltage_used: BoolVec,
                  t_idx: int | None,
                  opf_results: Union[OptimalPowerFlowResults, OptimalNetTransferCapacityResults, None] = None,
                  use_stored_guess: bool = False,
                  logger: Logger = Logger()):
    """

    :param data:
    :param circuit:
    :param bus_dict:
    :param bus_data:
    :param bus_voltage_used:
    :param t_idx:
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
        data.original_idx[i] = i
        data.dispatchable[i] = int(elm.dispatchable)
        data.F[i] = f
        data.T[i] = t

        # hvdc values
        data.names[i] = elm.name
        data.idtag[i] = elm.idtag

        data.active[i] = elm.get_active_at(t_idx)
        data.rates[i] = elm.get_rate_at(t_idx)
        data.contingency_rates[i] = data.rates[i] * elm.get_contingency_factor_at(t_idx)
        data.protection_rates[i] = data.rates[i] * elm.get_protection_rating_factor_at(t_idx)
        data.angle_droop[i] = elm.get_angle_droop_at(t_idx)
        data.r[i] = elm.r

        if opf_results is not None:
            # if we are taking the values from the OPF, do not allow the free mode
            data.control_mode_int[i] = HvdcControlType.type_1_Pset.idx()
            data.Pset[i] = opf_results.hvdc_Pf[t_idx, i]
        else:
            data.control_mode_int[i] = elm.control_mode.idx()
            data.Pset[i] = elm.get_Pset_at(t_idx)

        data.Vset_f[i] = elm.get_Vset_f_at(t_idx)
        data.Vset_t[i] = elm.get_Vset_t_at(t_idx)

        # hack the bus types to believe they are PV
        if data.active[i] != 0:
            set_bus_control_voltage_hvdc(i=f,
                                         j=-1,
                                         remote_control=False,
                                         bus_name=elm.bus_from.name,
                                         bus_data=bus_data,
                                         bus_voltage_used=bus_voltage_used,
                                         candidate_Vm=data.Vset_f[i],
                                         use_stored_guess=use_stored_guess,
                                         logger=logger)

            set_bus_control_voltage_hvdc(i=t,
                                         j=-1,
                                         remote_control=False,
                                         bus_name=elm.bus_to.name,
                                         bus_data=bus_data,
                                         bus_voltage_used=bus_voltage_used,
                                         candidate_Vm=data.Vset_t[i],
                                         use_stored_guess=use_stored_guess,
                                         logger=logger)

        data.Vnf[i] = elm.bus_from.Vnom
        data.Vnt[i] = elm.bus_to.Vnom

        data.Qmin_f[i], data.Qmax_f[i], data.Qmin_t[i], data.Qmax_t[i] = elm.get_q_limits(P=data.Pset[i])


def get_fluid_node_data(data: FluidNodeData,
                        circuit: MultiCircuit,
                        t_idx: int | None = None,
                        logger: Logger = Logger()) -> Dict[str, int]:
    """

    :param data:
    :param circuit:
    :param t_idx:
    :param logger:
    :return:
    """
    plant_dict: Dict[str, int] = dict()

    for k, elm in enumerate(circuit.get_fluid_nodes()):
        plant_dict[elm.idtag] = k

        data.names[k] = elm.name
        data.idtag[k] = elm.idtag

        # Convert input data in hm3 to m3
        min_level, max_level = normalize_upper_bound(
            lower=1e6 * elm.min_level,
            upper=1e6 * elm.max_level,
            logger=logger,
            device_name=elm.name,
            device_class=str(elm.device_type.value),
            lower_name="min_level",
            upper_name="max_level",
        )
        data.min_level[k] = min_level
        data.max_level[k] = max_level
        data.initial_level[k] = 1e6 * elm.initial_level

        data.inflow[k] = elm.get_inflow_at(t_idx)
        data.spillage_cost[k] = elm.get_spillage_cost_at(t_idx)
        min_soc, max_soc = normalize_upper_bound(
            lower=elm.get_min_soc_at(t_idx),
            upper=elm.get_max_soc_at(t_idx),
            logger=logger,
            device_name=elm.name,
            device_class=str(elm.device_type.value),
            lower_name="min_soc",
            upper_name="max_soc",
        )
        data.max_soc[k] = max_soc
        data.min_soc[k] = min_soc

    return plant_dict


def resize_fluid_injection_data(data: FluidTurbineData, nelm: int) -> None:
    """
    Resize fluid injection data arrays to the valid compiled entries.

    :param data: Fluid injection data structure.
    :param nelm: Number of valid compiled entries.
    :return: None.
    """
    if data.nelm == nelm:
        pass
    else:
        data.names = data.names[:nelm].copy()
        data.idtag = data.idtag[:nelm].copy()
        data.efficiency = data.efficiency[:nelm].copy()
        data.max_flow_rate = data.max_flow_rate[:nelm].copy()
        data.plant_idx = data.plant_idx[:nelm].copy()
        data.generator_idx = data.generator_idx[:nelm].copy()
        data.nelm = nelm


def get_valid_fluid_injection_indices(elm: FluidInjectionTemplate,
                                      plant_dict: Dict[str, int],
                                      gen_dict: Dict[str, int],
                                      logger: Logger) -> tuple[int | None, int | None]:
    """
    Resolve the plant and generator indices for one fluid injection.

    :param elm: Fluid injection device.
    :param plant_dict: Fluid node index by idtag.
    :param gen_dict: Generator index by idtag.
    :param logger: Logger receiving invalid-link errors.
    :return: Plant and generator indices, or ``None`` for invalid links.
    """
    plant_idx: int | None = None
    gen_idx: int | None = None

    if elm.plant is None:
        logger.add_error(msg="Fluid injection has no plant",
                         device=elm.name,
                         device_class=str(elm.device_type.value),
                         device_property="plant")
    else:
        plant_idx = plant_dict.get(elm.plant.idtag, None)
        if plant_idx is None:
            logger.add_error(msg="Fluid injection plant is not in the compiled fluid nodes",
                             device=elm.name,
                             device_class=str(elm.device_type.value),
                             device_property="plant",
                             object_value=elm.plant.name)
        else:
            pass

    if elm.generator is None:
        logger.add_error(msg="Fluid injection has no generator",
                         device=elm.name,
                         device_class=str(elm.device_type.value),
                         device_property="generator")
    else:
        gen_idx = gen_dict.get(elm.generator.idtag, None)
        if gen_idx is None:
            logger.add_error(msg="Fluid injection generator is not in the compiled generators",
                             device=elm.name,
                             device_class=str(elm.device_type.value),
                             device_property="generator",
                             object_value=elm.generator.name)
        else:
            pass

    return plant_idx, gen_idx


def get_fluid_turbine_data(data: FluidTurbineData,
                           circuit: MultiCircuit,
                           plant_dict: Dict[str, int],
                           gen_dict: Dict[str, int],
                           logger: Logger = Logger()) -> FluidTurbineData:
    """

    :param data:
    :param circuit:
    :param plant_dict:
    :param gen_dict:
    :param logger:
    :return:
    """
    k: int = 0

    for elm in circuit.get_fluid_turbines():
        plant_idx, gen_idx = get_valid_fluid_injection_indices(elm=elm,
                                                               plant_dict=plant_dict,
                                                               gen_dict=gen_dict,
                                                               logger=logger)

        if plant_idx is not None and gen_idx is not None:
            data.plant_idx[k] = plant_idx
            data.generator_idx[k] = gen_idx

            data.names[k] = elm.name
            data.idtag[k] = elm.idtag

            data.efficiency[k] = elm.efficiency
            data.max_flow_rate[k] = elm.max_flow_rate

            k += 1
        else:
            pass

    resize_fluid_injection_data(data=data, nelm=k)

    return data


def get_fluid_pump_data(data: FluidPumpData,
                        circuit: MultiCircuit,
                        plant_dict: Dict[str, int],
                        gen_dict: Dict[str, int],
                        logger: Logger = Logger()) -> FluidPumpData:
    """

    :param data:
    :param circuit:
    :param plant_dict:
    :param gen_dict:
    :param logger:
    :return:
    """

    k: int = 0

    for elm in circuit.get_fluid_pumps():
        plant_idx, gen_idx = get_valid_fluid_injection_indices(elm=elm,
                                                               plant_dict=plant_dict,
                                                               gen_dict=gen_dict,
                                                               logger=logger)

        if plant_idx is not None and gen_idx is not None:
            data.plant_idx[k] = plant_idx
            data.generator_idx[k] = gen_idx

            data.names[k] = elm.name
            data.idtag[k] = elm.idtag

            data.efficiency[k] = elm.efficiency
            data.max_flow_rate[k] = elm.max_flow_rate

            k += 1
        else:
            pass

    resize_fluid_injection_data(data=data, nelm=k)

    return data


def get_fluid_p2x_data(data: FluidP2XData,
                       circuit: MultiCircuit,
                       plant_dict: Dict[str, int],
                       gen_dict: Dict[str, int],
                       logger: Logger = Logger()) -> FluidP2XData:
    """

    :param data:
    :param circuit:
    :param plant_dict:
    :param gen_dict:
    :param logger:
    :return:
    """

    k: int = 0

    for elm in circuit.get_fluid_p2xs():
        plant_idx, gen_idx = get_valid_fluid_injection_indices(elm=elm,
                                                               plant_dict=plant_dict,
                                                               gen_dict=gen_dict,
                                                               logger=logger)

        if plant_idx is not None and gen_idx is not None:
            data.plant_idx[k] = plant_idx
            data.generator_idx[k] = gen_idx

            data.names[k] = elm.name
            data.idtag[k] = elm.idtag

            data.efficiency[k] = elm.efficiency
            data.max_flow_rate[k] = elm.max_flow_rate

            k += 1
        else:
            pass

    resize_fluid_injection_data(data=data, nelm=k)

    return data


def get_fluid_path_data(data: FluidPathData,
                        circuit: MultiCircuit,
                        plant_dict: Dict[str, int],
                        logger: Logger = Logger()) -> FluidPathData:
    """

    :param data: FluidPathData
    :param circuit:
    :param plant_dict:
    :param logger:
    :return:
    """

    for k, elm in enumerate(circuit.get_fluid_paths()):
        data.names[k] = elm.name
        data.idtag[k] = elm.idtag

        # pass idx, check
        data.source_idx[k] = plant_dict[elm.source.idtag]
        data.target_idx[k] = plant_dict[elm.target.idtag]

        min_flow, max_flow = normalize_upper_bound(
            lower=elm.min_flow,
            upper=elm.max_flow,
            logger=logger,
            device_name=elm.name,
            device_class=str(elm.device_type.value),
            lower_name="min_flow",
            upper_name="max_flow",
        )
        data.min_flow[k] = min_flow
        data.max_flow[k] = max_flow

    return data


def compile_numerical_circuit_at(circuit: MultiCircuit,
                                 t_idx: Union[int, None] = None,
                                 apply_temperature: bool = False,
                                 branch_tolerance_mode=BranchImpedanceMode.Specified,
                                 opf_results: VALID_OPF_RESULTS | None = None,
                                 use_stored_guess: bool = False,
                                 bus_dict: Union[Dict[Bus, int], None] = None,
                                 areas_dict: Union[Dict[Area, int], None] = None,
                                 control_taps_modules: bool = True,
                                 control_taps_phase: bool = True,
                                 control_remote_voltage: bool = True,
                                 fill_gep: bool = False,
                                 fill_three_phase: bool = False,
                                 consider_grounded_buses: bool = False,
                                 logger: Logger = Logger()) -> NumericalCircuit:
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
    :param fill_gep: fill generation expansion planning parameters?
    :param fill_three_phase:
    :param consider_grounded_buses: Consider the is_grounded bus state
    :param logger: Logger instance
    :return: NumericalCircuit instance
    """

    # if any valid time index is specified, then the data is compiled from the time series
    time_series = t_idx is not None

    bus_voltage_used = np.zeros(circuit.get_bus_number(), dtype=bool)
    ngen = circuit.get_generators_number()
    nbatt = circuit.get_batteries_number()
    # declare the numerical circuit
    nc = NumericalCircuit(
        nbus=circuit.get_bus_number(),
        nbr=circuit.get_branch_number(add_vsc=False,
                                      add_hvdc=False,
                                      add_switch=True),
        nhvdc=circuit.get_hvdc_number(),
        nvsc=circuit.get_vsc_number(),
        nload=circuit.get_load_like_device_number(),
        ngen=ngen,
        nbatt=nbatt,
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
        areas_dict=areas_dict,
        use_stored_guess=use_stored_guess,
        consider_grounded_buses=consider_grounded_buses,
        logger=logger,
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
        control_remote_voltage=control_remote_voltage,
        use_stored_guess=use_stored_guess,
        fill_three_phase=fill_three_phase
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
        control_remote_voltage=control_remote_voltage,
        fill_three_phase=fill_three_phase
    )

    get_shunt_data(
        data=nc.shunt_data,  # filled here
        circuit=circuit,
        bus_dict=bus_dict,
        bus_voltage_used=bus_voltage_used,
        bus_data=nc.bus_data,
        t_idx=t_idx,
        logger=logger,
        use_stored_guess=use_stored_guess,
        control_remote_voltage=control_remote_voltage,
        fill_three_phase=fill_three_phase
    )

    get_load_data(
        data=nc.load_data,
        circuit=circuit,
        bus_dict=bus_dict,
        bus_voltage_used=bus_voltage_used,
        bus_data=nc.bus_data,
        t_idx=t_idx,
        logger=logger,
        use_stored_guess=use_stored_guess,
        opf_results=opf_results,
        fill_three_phase=fill_three_phase
    )

    branch_dict = get_branch_data(
        data=nc.passive_branch_data,
        ctrl_data=nc.active_branch_data,
        circuit=circuit,
        t_idx=t_idx,
        bus_dict=bus_dict,
        bus_data=nc.bus_data,
        bus_voltage_used=bus_voltage_used,
        apply_temperature=apply_temperature,
        branch_tolerance_mode=branch_tolerance_mode,
        opf_results=opf_results,
        use_stored_guess=use_stored_guess,
        control_taps_modules=control_taps_modules,
        control_taps_phase=control_taps_phase,
        fill_three_phase=fill_three_phase
    )

    get_vsc_data(
        data=nc.vsc_data,
        circuit=circuit,
        t_idx=t_idx,
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
        bus_dict=bus_dict,
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
            logger=logger,
        )

        get_fluid_turbine_data(
            data=nc.fluid_turbine_data,
            circuit=circuit,
            plant_dict=plant_dict,
            gen_dict=gen_dict,
            logger=logger,
        )
        nc.nfluidturbine = nc.fluid_turbine_data.nelm

        get_fluid_pump_data(
            data=nc.fluid_pump_data,
            circuit=circuit,
            plant_dict=plant_dict,
            gen_dict=gen_dict,
            logger=logger,
        )
        nc.nfluidpump = nc.fluid_pump_data.nelm

        get_fluid_p2x_data(
            data=nc.fluid_p2x_data,
            circuit=circuit,
            plant_dict=plant_dict,
            gen_dict=gen_dict,
            logger=logger,
        )
        nc.nfluidp2x = nc.fluid_p2x_data.nelm

        get_fluid_path_data(
            data=nc.fluid_path_data,
            circuit=circuit,
            plant_dict=plant_dict,
            logger=logger,
        )

    if fill_gep:

        # formulate the investment
        gen_dict = {elm.idtag: (idx, elm) for idx, elm in enumerate(circuit.generators)}
        batt_dict = {elm.idtag: (idx, elm) for idx, elm in enumerate(circuit.batteries)}

        for investment in circuit.investments:

            # search in generators
            data = gen_dict.get(investment.device_idtag, None)
            if data is not None:
                idx, elm = data

                if investment.CAPEX != 0.0:  # overwrite the base capex
                    nc.generator_data.capex[idx] = investment.CAPEX

                nc.generator_data.is_candidate[idx] = True
                nc.generator_data.discount_rate[idx] = investment.group.discount_rate
            else:

                # search in batteries
                data = batt_dict.get(investment.device_idtag, None)
                if data is not None:
                    idx, elm = data

                    if investment.CAPEX != 0.0:  # overwrite the base capex
                        nc.battery_data.capex[idx] = investment.CAPEX

                    nc.battery_data.is_candidate[idx] = True
                    nc.battery_data.discount_rate[idx] = investment.group.discount_rate
                else:
                    logger.add_error("Could not find investment device", value=investment.device_idtag)

    nc.bus_dict = bus_dict
    nc.consolidate_information()

    if nc.active_branch_data.any_pf_control is False:
        if nc.vsc_data.nelm > 0:
            nc.active_branch_data.any_pf_control = True

    return nc
