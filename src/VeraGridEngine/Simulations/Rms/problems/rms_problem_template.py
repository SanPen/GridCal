# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from abc import ABC
from typing import Dict, List, Tuple
import numpy as np
import scipy.sparse as sp
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Simulations.Rms.initialization_rms import (
    project_initial_algebraic_state, solve_rms_newton_correction,
)
from VeraGridEngine.Simulations.driver_template import DummySignal
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.genqec_phasor_rms_template import get_complete_generator_template_phasor
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.shunt_template import get_shunt_template
from VeraGridEngine.Templates.Rms.transformer_rms_template import initialize_trafo_rms
from VeraGridEngine.Templates.Rms.vsc_gfl_dclinked import build_vsc_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model


def rectangular_current_from_power(
        power: complex,
        voltage: complex,
) -> Tuple[float, float]:
    """
    Convert one complex-power operating point to rectangular current.

    The RMS injection convention is ``S = V * conj(I)``. This helper supplies
    the exact current seed associated with an already-converged power-flow
    voltage and avoids an artificial first-step residual in models that expose
    both power and current variables.

    :param power: Complex injected power in per unit.
    :param voltage: Complex terminal voltage in per unit.
    :return: Real and imaginary current components in per unit.
    """
    voltage_squared: float = float(
        voltage.real * voltage.real + voltage.imag * voltage.imag
    )
    if voltage_squared > 1.0e-18:
        current_real: float = float(
            (power.real * voltage.real + power.imag * voltage.imag)
            / voltage_squared
        )
        current_imaginary: float = float(
            (power.real * voltage.imag - power.imag * voltage.real)
            / voltage_squared
        )
    else:
        current_real = 0.0
        current_imaginary = 0.0
    return current_real, current_imaginary


class RmsProblemTemplate(ABC):
    """
    Abstract base class for RMS dynamic simulation problems.
    """
    __slots__ = (
        "_is_initialized",
        "progress_signal",
        "progress_text",
        "grid",
        "power_flow_results",
    )

    def __init__(self,
                 progress_signal: DummySignal | None = None,
                 progress_text: DummySignal | None = None) -> None:

        self._is_initialized = False
        self.progress_signal =  DummySignal() if progress_signal is None else progress_signal
        self.progress_text = DummySignal(str) if progress_text is None else progress_text

    def set_initialize_flag(self):
        self._is_initialized = True

    def is_initialized(self) -> bool:
        return self._is_initialized

    def get_vars_info(self) -> Dict[ALL_DEV_TYPES, List[Var]]:
        raise NotImplementedError("get_device_vars_dict")

    def get_all_vars_number(self) -> int:
        return 0

    def get_diff_var_number(self) -> int:
        return 0

    def get_algebraic_var_number(self) -> int:
        return 0

    def get_algebraic_vars(self) -> List:
        return list()

    def get_states_number(self) -> int:
        return 0

    def get_variable_parameter_number(self) -> int:
        return 0

    def algebraic_vars(self) -> List:
        return list()

    def state_vars(self):
        return list()

    # def get_constant_parameters(self) -> Vec:
    #     raise NotImplementedError("get_constant_parameters")

    def get_x0(self) -> Vec:
        raise NotImplementedError("get_x0")

    # def compute_event_params(self, parameters: Vec, time_value: float) -> Vec:
    #     raise NotImplementedError("compute_event_params")

    def update_variable_params(self, t: float, x_snapshot: Vec | None = None):
        raise NotImplementedError("update_variable_params")

    def get_dx(self, x: Vec, xn: Vec, dx: Vec, h: float) -> Vec:
        raise NotImplementedError("derivative")

    def rhs_state(self, x: Vec, dx: Vec) -> Vec:
        raise NotImplementedError("rhs_state")

    def rhs_algebraic(self, values: Vec, diff_values: Vec) -> Vec:
        raise NotImplementedError("rhs_algebraic")

    def get_j11(self, x: Vec, dx: Vec, h: float):
        raise NotImplementedError("get_j11")

    def get_j12(self, x: Vec, dx: Vec, h: float):
        raise NotImplementedError("get_j12")

    def get_j21(self, x: Vec, dx: Vec, h: float):
        raise NotImplementedError("get_j21")

    def get_j22(self, x: Vec, dx: Vec, h: float):
        raise NotImplementedError("get_j22")

    def get_E_matrix(self, x:Vec, dx:Vec):
        raise NotImplementedError("get_E_matrix")

    def get_static_state_matrix(self, x: Vec, dx: Vec):
        raise NotImplementedError("get_static_state_matrix")

    def get_small_signal_reference_indices(self) -> tuple[int, int] | None:
        """
        Return the augmented-Jacobian row and column used to fix the angle gauge.

        Problems without an explicit electrical angle reference do not require
        a small-signal gauge constraint and return ``None``.

        :return: Reference row and column, or ``None`` when not applicable.
        """
        return None
    
    def get_dt_value(self):
        return NotImplementedError("get_dt_value")

    def get_generator_injection_data(self, i: int, elm: ALL_DEV_TYPES) -> complex:
        if elm.active:
            # The power-flow worker already allocates the solved slack-bus
            # active and reactive power among its individual generators (and
            # batteries) in gen_p/gen_q.  Using the aggregate Sbus here would
            # assign the complete net bus injection to every generator on a
            # multi-generator slack bus and would also include any load or
            # shunt connected to that bus.
            return complex(
                self.power_flow_results.gen_p[i],
                self.power_flow_results.gen_q[i],
            ) / self.grid.Sbase
        else:
            return complex(0.0, 0.0)

    def get_battery_injection_data(self, i: int, elm: ALL_DEV_TYPES) -> complex:
        if elm.active:
            return complex(self.power_flow_results.battery_p[i], self.power_flow_results.battery_q[i]) / self.grid.Sbase
        else:
            return complex(0.0, 0.0)

    def get_load_injection_data(self, elm: ALL_DEV_TYPES, bus_dict: Dict[Bus, int]) -> complex:
        if elm.active:
            bus_index = bus_dict[elm.bus]
            Vm = abs(self.power_flow_results.voltage[bus_index])
            scale = 1000.0 if elm.use_kw else 1.0
            S0 = -elm.get_S_at(None) / scale / self.grid.Sbase
            I0 = -elm.get_I_at(None) / scale / self.grid.Sbase
            Y0 = -elm.get_Y_at(None) / scale / self.grid.Sbase
            return S0 + np.conj(I0 + Y0 * Vm) * Vm
        else:
            return complex(0.0, 0.0)

    def get_external_grid_injection_data(self, elm: ALL_DEV_TYPES) -> complex:
        if elm.active:
            scale = 1000.0 if elm.use_kw else 1.0
            return -elm.get_S_at(None) / scale / self.grid.Sbase
        else:
            return complex(0.0, 0.0)

    def get_static_generator_injection_data(self, elm: ALL_DEV_TYPES) -> complex:
        if elm.active:
            scale = 1000.0 if elm.use_kw else 1.0
            return elm.get_S_at(None) / scale / self.grid.Sbase
        else:
            return complex(0.0, 0.0)

    def get_shunt_injection_data(self, elm: ALL_DEV_TYPES, bus_dict: Dict[Bus, int]) -> complex:
        if elm.active:
            bus_index = bus_dict[elm.bus]
            Vbus = self.power_flow_results.voltage[bus_index]
            scale = 1000.0 if elm.use_kw else 1.0
            # The RMS problem stores power injected into the bus. A shunt
            # admittance consumes ``V * conj(Y * V)``, so its network injection
            # is the negative of that consumed complex power.
            return -Vbus * np.conj((elm.get_Y_at(None) / scale / self.grid.Sbase) * Vbus)
        else:
            return complex(0.0, 0.0)

    def get_controllable_shunt_injection_data(self, elm: ALL_DEV_TYPES, bus_dict: Dict[Bus, int]) -> complex:
        return self.get_shunt_injection_data(elm=elm, bus_dict=bus_dict)

    def get_current_injection_data(self, elm: ALL_DEV_TYPES, bus_dict: Dict[Bus, int]) -> complex:
        if elm.active:
            bus_index = bus_dict[elm.bus]
            Vbus = self.power_flow_results.voltage[bus_index]
            scale = 1000.0 if elm.use_kw else 1.0
            return -Vbus * np.conj(elm.get_I_at(None) / scale / self.grid.Sbase)
        else:
            return complex(0.0, 0.0)

    def get_injection_init_data(self, bus_dict: Dict[Bus, int]) -> Dict[str, complex]:
        injection_init_data: Dict[str, complex] = dict()

        for i, elm in enumerate(self.grid.get_generators()):
            Sdev = self.get_generator_injection_data(i=i, elm=elm)
            injection_init_data[elm.idtag] = Sdev

        for i, elm in enumerate(self.grid.get_batteries()):
            Sdev = self.get_battery_injection_data(i=i, elm=elm)
            injection_init_data[elm.idtag] = Sdev

        for elm in self.grid.get_loads():
            Sdev = self.get_load_injection_data(elm=elm, bus_dict=bus_dict)
            injection_init_data[elm.idtag] = Sdev

        for elm in self.grid.get_external_grids():
            Sdev = self.get_external_grid_injection_data(elm=elm)
            injection_init_data[elm.idtag] = Sdev

        for elm in self.grid.get_static_generators():
            Sdev = self.get_static_generator_injection_data(elm=elm)
            injection_init_data[elm.idtag] = Sdev

        for elm in self.grid.get_shunts():
            Sdev = self.get_shunt_injection_data(elm=elm, bus_dict=bus_dict)
            injection_init_data[elm.idtag] = Sdev

        for elm in self.grid.get_controllable_shunts():
            Sdev = self.get_controllable_shunt_injection_data(elm=elm, bus_dict=bus_dict)
            injection_init_data[elm.idtag] = Sdev

        for elm in self.grid.get_current_injections():
            Sdev = self.get_current_injection_data(elm=elm, bus_dict=bus_dict)
            injection_init_data[elm.idtag] = Sdev

        return injection_init_data

    def report_progress(self, val: float) -> None:
        """
        Emit one absolute RMS progress update.

        :param val: Progress value in percent.
        :type val: float
        :return: None
        :rtype: None
        """
        if self.progress_signal is not None:
            self.progress_signal.emit(val)
        else:
            pass

    def report_progress2(self, current: int, total: int) -> None:
        """
        Emit one RMS progress update from a zero-based iteration index.

        :param current: Zero-based iteration index.
        :type current: int
        :param total: Total number of iterations.
        :type total: int
        :return: None
        :rtype: None
        """
        if self.progress_signal is not None:
            val: float = ((current + 1) / total) * 100
            self.progress_signal.emit(val)
        else:
            pass

    def report_text(self, text: str) -> None:
        """
        Emit a textual update describing the current RMS simulation stage.

        :param text: Human-readable progress message.
        :type text: str
        :return: None
        :rtype: None
        """
        if self.progress_text is not None:
            self.progress_text.emit(text)
        else:
            pass
