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
    AC quantities use NABC conductor order and the system three-phase power and
    current bases. DC power uses the system power base. Positive values mean
    injection into the connected bus.

    :param n_injections: Number of injection devices represented by the store.
    """

    __slots__ = (
        "_ac_power",
        "_ac_current",
        "_dc_power",
        "_has_seed",
        "_has_current",
        "_current_is_authoritative",
    )

    def __init__(self, n_injections: int) -> None:
        """Allocate the numerical storage for every EMT injection.

        :param n_injections: Number of injection devices represented by the store.
        :return: None.
        """
        # The injection count is known before initialization, so all numerical
        # memory is allocated once and remains fixed during the build.
        self._ac_power: np.ndarray = np.zeros((n_injections, 4), dtype=np.complex128)
        self._ac_current: np.ndarray = np.zeros((n_injections, 4), dtype=np.complex128)
        self._dc_power: np.ndarray = np.zeros(n_injections, dtype=np.float64)
        self._has_seed: np.ndarray = np.zeros(n_injections, dtype=bool)
        self._has_current: np.ndarray = np.zeros(n_injections, dtype=bool)
        self._current_is_authoritative: np.ndarray = np.zeros(n_injections, dtype=bool)

    def set_ac_seed(self, injection_index: int, phase_power: np.ndarray) -> None:
        """Store one AC power operating point in NABC order.

        :param injection_index: Row of the injection device.
        :param phase_power: Complex NABC power on the system power base.
        :return: None.
        """
        self._ac_power[injection_index, :] = phase_power
        self._has_seed[injection_index] = True

    def set_ac_current_seed(
            self,
            injection_index: int,
            phase_current: np.ndarray,
            authoritative: bool,
    ) -> None:
        """Store one AC current operating point in NABC order.

        :param injection_index: Row of the injection device.
        :param phase_current: Complex NABC current on the system current base.
        :param authoritative: Whether PF supplied the current directly.
        :return: None.
        """
        self._ac_current[injection_index, :] = phase_current
        self._has_current[injection_index] = True
        self._current_is_authoritative[injection_index] = authoritative

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

    def has_current_seed(self, injection_index: int) -> bool:
        """Return whether one device has an AC current seed.

        :param injection_index: Row of the injection device.
        :return: ``True`` when an NABC current is available.
        """
        return bool(self._has_current[injection_index])

    def current_is_authoritative(self, injection_index: int) -> bool:
        """Return whether one current seed originates directly in PF.

        :param injection_index: Row of the injection device.
        :return: ``True`` for a directly evaluated PF current.
        """
        return bool(self._current_is_authoritative[injection_index])

    def get_ac_seed(self, injection_index: int) -> np.ndarray:
        """Return a copy of one AC power seed.

        :param injection_index: Row of the injection device.
        :return: Complex NABC power vector.
        """
        return self._ac_power[injection_index, :].copy()

    def get_ac_current_seed(self, injection_index: int) -> np.ndarray:
        """Return a copy of one AC current seed.

        :param injection_index: Row of the injection device.
        :return: Complex NABC current vector.
        """
        return self._ac_current[injection_index, :].copy()

    def get_dc_seed(self, injection_index: int) -> float:
        """Return one DC active-power seed.

        :param injection_index: Row of the injection device.
        :return: Active power on the system power base.
        """
        return float(self._dc_power[injection_index])


def _get_balanced_device_power_pu(
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


def _balanced_voltage_vector(bus_voltage: complex) -> np.ndarray:
    """Expand one positive-sequence voltage into NABC phasors.

    :param bus_voltage: Positive-sequence phase-A voltage phasor.
    :return: Complex voltage vector in NABC order.
    """
    voltage_vector: np.ndarray = np.zeros(4, dtype=np.complex128)
    phase_shift: complex = complex(np.exp(-2.0j * np.pi / 3.0))
    voltage_vector[0] = 0.0 + 0.0j
    voltage_vector[1] = bus_voltage
    voltage_vector[2] = bus_voltage * phase_shift
    voltage_vector[3] = bus_voltage * phase_shift * phase_shift
    return voltage_vector


def build_balanced_emt_injection_operating_point(
        grid: MultiCircuit,
        power_flow_results: PowerFlowResults,
        bus_dict: Dict[Bus, int],
        injection_devices: List[INJECTION_DEVICE_TYPES],
) -> EmtInjectionOperatingPoint:
    """Adapt balanced PF results to the per-device EMT contract.

    The function mirrors the established RMS initialization semantics. Most
    importantly, it consumes ``gen_p/gen_q`` and ``battery_p/battery_q`` and
    never reconstructs slack dispatch from aggregate ``Sbus`` or ``Snom``.

    :param grid: Static network model.
    :param power_flow_results: Converged balanced PF results.
    :param bus_dict: Mapping from static buses to result positions.
    :param injection_devices: Fixed-order injection-device collection.
    :return: Fixed-size per-device EMT operating point.
    """
    operating_point: EmtInjectionOperatingPoint = EmtInjectionOperatingPoint(len(injection_devices))
    generator_index: int = 0
    battery_index: int = 0
    injection_index: int = 0

    while injection_index < len(injection_devices):
        injection: INJECTION_DEVICE_TYPES = injection_devices[injection_index]
        selected_generator_index: int = generator_index if injection.device_type == DeviceType.GeneratorDevice else -1
        selected_battery_index: int = battery_index if injection.device_type == DeviceType.BatteryDevice else -1
        device_power: complex = _get_balanced_device_power_pu(
            grid=grid,
            power_flow_results=power_flow_results,
            injection=injection,
            bus_dict=bus_dict,
            generator_index=selected_generator_index,
            battery_index=selected_battery_index,
        )

        # Indices advance in the same family order as the existing PF arrays.
        if injection.device_type == DeviceType.GeneratorDevice:
            generator_index += 1
        else:
            pass
        if injection.device_type == DeviceType.BatteryDevice:
            battery_index += 1
        else:
            pass

        if injection.bus.is_dc:
            operating_point.set_dc_seed(
                injection_index=injection_index,
                power_value=float(np.real(device_power)),
            )
        else:
            phase_power: np.ndarray = np.zeros(4, dtype=np.complex128)
            phase_power[1:4] = device_power / 3.0
            operating_point.set_ac_seed(
                injection_index=injection_index,
                phase_power=phase_power,
            )

            # Balanced PF does not expose conductor currents. Derive the exact
            # current associated with the authoritative per-device power.
            bus_index: int = int(bus_dict[injection.bus])
            voltage_vector: np.ndarray = _balanced_voltage_vector(
                bus_voltage=complex(power_flow_results.voltage[bus_index])
            )
            phase_current: np.ndarray = np.zeros(4, dtype=np.complex128)
            phase_index: int = 1
            while phase_index < 4:
                if abs(voltage_vector[phase_index]) > 1.0e-12:
                    phase_current[phase_index] = 3.0 * np.conj(
                        phase_power[phase_index] / voltage_vector[phase_index]
                    )
                else:
                    phase_current[phase_index] = 0.0 + 0.0j
                phase_index += 1
            phase_current[0] = -(phase_current[1] + phase_current[2] + phase_current[3])
            operating_point.set_ac_current_seed(
                injection_index=injection_index,
                phase_current=phase_current,
                authoritative=False,
            )

        injection_index += 1

    return operating_point
