# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Build per-device operating points consumed by EMT initialization."""

from typing import Dict, List

import numpy as np

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.types import INJECTION_DEVICE_TYPES
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.enumerations import DeviceType


class EmtInjectionOperatingPoint:
    """Store fixed-size power-flow operating points for EMT injections.

    Rows follow the order of the injection-device list supplied to the builder.
    AC powers use NABC conductor order and the system three-phase power
    base. DC power uses the system power base. Positive values mean
    injection into the connected bus.

    :param n_injections: Number of injection devices represented by the store.
    """

    __slots__ = (
        "_ac_power",
        "_dc_power",
        "_has_seed",
    )

    def __init__(self, n_injections: int) -> None:
        """Allocate the numerical storage for every EMT injection.

        :param n_injections: Number of injection devices represented by the store.
        :return: None.
        """
        # The injection count is known before initialization, so all numerical
        # memory is allocated once and remains fixed during the build.
        self._ac_power: np.ndarray = np.zeros((n_injections, 4), dtype=np.complex128)
        self._dc_power: np.ndarray = np.zeros(n_injections, dtype=np.float64)
        self._has_seed: np.ndarray = np.zeros(n_injections, dtype=bool)

    def set_ac_seed(self, injection_index: int, phase_power: np.ndarray) -> None:
        """Store one AC power operating point in NABC order.

        :param injection_index: Row of the injection device.
        :param phase_power: Complex NABC power on the system power base.
        :return: None.
        """
        self._ac_power[injection_index, :] = phase_power
        self._has_seed[injection_index] = True

    def set_dc_seed(self, injection_index: int, power_value: float) -> None:
        """Store one DC active-power operating point.

        :param injection_index: Row of the injection device.
        :param power_value: Active power on the system power base.
        :return: None.
        """
        self._dc_power[injection_index] = power_value
        self._has_seed[injection_index] = True

    def has_seed(self, injection_index: int) -> bool:
        """Return whether one device has an operating-point seed.

        :param injection_index: Row of the injection device.
        :return: ``True`` when the adapter produced a seed.
        """
        return bool(self._has_seed[injection_index])


    def get_ac_seed(self, injection_index: int) -> np.ndarray:
        """Return a copy of one AC power seed.

        :param injection_index: Row of the injection device.
        :return: Complex NABC power vector.
        """
        return self._ac_power[injection_index, :].copy()

    def get_dc_seed(self, injection_index: int) -> float:
        """Return one DC active-power seed.

        :param injection_index: Row of the injection device.
        :return: Active power on the system power base.
        """
        return float(self._dc_power[injection_index])


def get_balanced_device_power_pu(
        grid: MultiCircuit,
        power_flow_results: PowerFlowResults,
        injection: INJECTION_DEVICE_TYPES,
        bus_dict: Dict[Bus, int],
        generator_index: int,
        battery_index: int,
) -> complex:
    """Return the RMS-compatible balanced operating point of one device.

    Generator and battery powers come from the existing per-device PF result
    arrays. The remaining devices use the same voltage-dependent expressions
    as ``RmsProblemTemplate``.

    :param grid: Static network model supplying the system power base.
    :param power_flow_results: Converged balanced power-flow results.
    :param injection: Injection device whose operating point is requested.
    :param bus_dict: Mapping from static buses to result positions.
    :param generator_index: Position in generator results, or ``-1``.
    :param battery_index: Position in battery results, or ``-1``.
    :return: Complex injected power in per unit.
    """
    device_power: complex

    if injection.active:
        if injection.device_type == DeviceType.GeneratorDevice:
            device_power = complex(
                power_flow_results.gen_p[generator_index],
                power_flow_results.gen_q[generator_index],
            ) / float(grid.Sbase)
        elif injection.device_type == DeviceType.BatteryDevice:
            device_power = complex(
                power_flow_results.battery_p[battery_index],
                power_flow_results.battery_q[battery_index],
            ) / float(grid.Sbase)
        elif injection.device_type == DeviceType.LoadDevice:
            bus_index: int = int(bus_dict[injection.bus])
            voltage_magnitude: float = float(abs(power_flow_results.voltage[bus_index]))
            unit_scale: float = 1000.0 if injection.use_kw else 1.0
            constant_power: complex = -injection.get_S_at(None) / unit_scale / float(grid.Sbase)
            constant_current: complex = -injection.get_I_at(None) / unit_scale / float(grid.Sbase)
            constant_admittance: complex = -injection.get_Y_at(None) / unit_scale / float(grid.Sbase)
            device_power = constant_power + np.conj(
                constant_current + constant_admittance * voltage_magnitude
            ) * voltage_magnitude
        elif injection.device_type == DeviceType.ExternalGridDevice:
            unit_scale = 1000.0 if injection.use_kw else 1.0
            device_power = -injection.get_S_at(None) / unit_scale / float(grid.Sbase)
        elif injection.device_type == DeviceType.StaticGeneratorDevice:
            unit_scale = 1000.0 if injection.use_kw else 1.0
            device_power = injection.get_S_at(None) / unit_scale / float(grid.Sbase)
        elif injection.device_type == DeviceType.ShuntDevice:
            bus_index = int(bus_dict[injection.bus])
            bus_voltage: complex = complex(power_flow_results.voltage[bus_index])
            unit_scale = 1000.0 if injection.use_kw else 1.0
            shunt_admittance: complex = injection.get_Y_at(None) / unit_scale / float(grid.Sbase)
            # V*conj(YV) is the power absorbed by the shunt branch. EMT stores
            # power as injection into the bus, so the adapter must negate it.
            device_power = -bus_voltage * np.conj(shunt_admittance * bus_voltage)
        elif injection.device_type == DeviceType.ControllableShuntDevice:
            bus_index = int(bus_dict[injection.bus])
            bus_voltage = complex(power_flow_results.voltage[bus_index])
            unit_scale = 1000.0 if injection.use_kw else 1.0
            shunt_admittance = injection.get_Y_at(None) / unit_scale / float(grid.Sbase)
            # Controllable and fixed shunts share the same admittance and EMT
            # injection conventions, independently of how B is controlled.
            device_power = -bus_voltage * np.conj(shunt_admittance * bus_voltage)
        elif injection.device_type == DeviceType.CurrentInjectionDevice:
            bus_index = int(bus_dict[injection.bus])
            bus_voltage = complex(power_flow_results.voltage[bus_index])
            unit_scale = 1000.0 if injection.use_kw else 1.0
            specified_current: complex = injection.get_I_at(None) / unit_scale / float(grid.Sbase)
            device_power = -bus_voltage * np.conj(specified_current)
        else:
            device_power = 0.0 + 0.0j
    else:
        device_power = 0.0 + 0.0j

    return complex(device_power)
