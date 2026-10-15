# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import math
from typing import Tuple, List

from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod, SubObjectType, RmsProblemTypes
from VeraGridEngine.Simulations.options_template import OptionsTemplate
from VeraGridEngine.Devices.Parents.editable_device import GCProp
from VeraGridEngine.Utils.Symbolic.symbolic import Var



class RmsOptions(OptionsTemplate):
    """
    Rms simulation options
    """

    __slots__ = (
        "integration_method",
        "initialization_method",
        "problem_type",
        "time_step",
        "simulation_time",
        "tolerance",
        "use_init_values",
        "max_iter",
        "init_fix_pf_bus_voltages",
        "fmi_state_event_time_tolerance",
        "fmi_state_event_max_iterations",
        "fmi_me_newton_absolute_tolerance",
        "fmi_me_newton_relative_tolerance",
        "fmi_me_newton_max_iterations",
        "fmi_me_max_continuous_states",
        "fmi_me_max_runtime_evaluations_per_step",
        "verbose",
        "rms_event_groups",
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(key="integration_method", tpe=DynamicIntegrationMethod),
        GCProp(key="initialization_method", tpe=RmsInitializationMethod),
        GCProp(key="problem_type", tpe=RmsProblemTypes),
        GCProp(key="time_step", tpe=float),
        GCProp(key="simulation_time", tpe=float),
        GCProp(key="tolerance", tpe=float),
        GCProp(key="use_init_values", tpe=bool),
        GCProp(key="max_iter", tpe=int),
        GCProp(key="init_fix_pf_bus_voltages", tpe=bool),
        GCProp(key="fmi_state_event_time_tolerance", tpe=float),
        GCProp(key="fmi_state_event_max_iterations", tpe=int),
        GCProp(key="fmi_me_newton_absolute_tolerance", tpe=float),
        GCProp(key="fmi_me_newton_relative_tolerance", tpe=float),
        GCProp(key="fmi_me_newton_max_iterations", tpe=int),
        GCProp(key="fmi_me_max_continuous_states", tpe=int),
        GCProp(key="fmi_me_max_runtime_evaluations_per_step", tpe=int),
        GCProp(key="rms_event_groups", tpe=SubObjectType.ObjectsList),
    )

    def __init__(self,
                 time_step: float = 0.001,
                 simulation_time: float = 5,
                 tolerance: float = 1e-6,
                 integration_method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeBackEuler,
                 initialization_method: RmsInitializationMethod = RmsInitializationMethod.Explicit,
                 problem_type: RmsProblemTypes = RmsProblemTypes.PowerBalance,
                 use_init_values: bool = False,
                 max_iter: int = 1000,
                 init_fix_pf_bus_voltages: bool = False,
                 verbose: int = 0,
                 fmi_state_event_time_tolerance: float = 1e-9,
                 fmi_state_event_max_iterations: int = 32,
                 fmi_me_newton_absolute_tolerance: float = 1e-8,
                 fmi_me_newton_relative_tolerance: float = 1e-8,
                 fmi_me_newton_max_iterations: int = 20,
                 fmi_me_max_continuous_states: int = 128,
                 fmi_me_max_runtime_evaluations_per_step: int = 100000) -> None:
        """
        RmsOptions
        :param time_step: time step of the simulations (s)
        :param simulation_time: simulation time (s)
        :param max_iter: max number of iterations
        :param init_fix_pf_bus_voltages: Keep RMS bus voltages fixed at their power-flow seeds during consistent initialization.
        :param tolerance: Integration tolerance
        :param integration_method: Integration method (default Backward Euler)
        :param fmi_state_event_time_tolerance: Absolute FMI ME event-time tolerance in seconds.
        :param fmi_state_event_max_iterations: Maximum FMI ME event bisections.
        :param fmi_me_newton_absolute_tolerance: Absolute scale used by the FMI ME Newton residual.
        :param fmi_me_newton_relative_tolerance: Relative scale used by the FMI ME Newton residual.
        :param fmi_me_newton_max_iterations: Maximum FMI ME Backward Euler Newton updates.
        :param fmi_me_max_continuous_states: Maximum dense FMI ME state dimension.
        :param fmi_me_max_runtime_evaluations_per_step: Shared runtime-call limit for one FMI ME step.
        :return: None.
        """

        OptionsTemplate.__init__(self, name='RmsSimulationOptions')

        self.integration_method: DynamicIntegrationMethod = integration_method
        self.initialization_method: RmsInitializationMethod = initialization_method
        self.problem_type: RmsProblemTypes = problem_type
        self.time_step: float = time_step
        self.simulation_time: float = simulation_time
        self.tolerance: float = tolerance
        self.use_init_values: bool = use_init_values
        self.max_iter: int = max_iter
        self.init_fix_pf_bus_voltages: bool = init_fix_pf_bus_voltages
        if (
            math.isfinite(fmi_state_event_time_tolerance)
            and fmi_state_event_time_tolerance > 0.0
        ):
            self.fmi_state_event_time_tolerance: float = (
                fmi_state_event_time_tolerance
            )
        else:
            raise ValueError(
                "RMS FMI state-event time tolerance must be finite and positive"
            )
        if (
            isinstance(fmi_state_event_max_iterations, int)
            and not isinstance(fmi_state_event_max_iterations, bool)
            and fmi_state_event_max_iterations > 0
        ):
            self.fmi_state_event_max_iterations: int = (
                fmi_state_event_max_iterations
            )
        else:
            raise ValueError(
                "RMS FMI state-event maximum iterations must be a positive integer"
            )
        if (
            math.isfinite(fmi_me_newton_absolute_tolerance)
            and fmi_me_newton_absolute_tolerance > 0.0
        ):
            self.fmi_me_newton_absolute_tolerance: float = (
                fmi_me_newton_absolute_tolerance
            )
        else:
            raise ValueError(
                "RMS FMI ME Newton absolute tolerance must be finite and positive"
            )
        if (
            math.isfinite(fmi_me_newton_relative_tolerance)
            and fmi_me_newton_relative_tolerance > 0.0
        ):
            self.fmi_me_newton_relative_tolerance: float = (
                fmi_me_newton_relative_tolerance
            )
        else:
            raise ValueError(
                "RMS FMI ME Newton relative tolerance must be finite and positive"
            )
        if (
            isinstance(fmi_me_newton_max_iterations, int)
            and not isinstance(fmi_me_newton_max_iterations, bool)
            and 1 <= fmi_me_newton_max_iterations <= 100
        ):
            self.fmi_me_newton_max_iterations: int = fmi_me_newton_max_iterations
        else:
            raise ValueError(
                "RMS FMI ME Newton iteration limit must be an integer between 1 and 100"
            )
        if (
            isinstance(fmi_me_max_continuous_states, int)
            and not isinstance(fmi_me_max_continuous_states, bool)
            and 1 <= fmi_me_max_continuous_states <= 128
        ):
            self.fmi_me_max_continuous_states: int = fmi_me_max_continuous_states
        else:
            raise ValueError(
                "RMS FMI ME state limit must be an integer between 1 and 128"
            )
        if (
            isinstance(fmi_me_max_runtime_evaluations_per_step, int)
            and not isinstance(fmi_me_max_runtime_evaluations_per_step, bool)
            and 1 <= fmi_me_max_runtime_evaluations_per_step <= 10_000_000
        ):
            self.fmi_me_max_runtime_evaluations_per_step: int = (
                fmi_me_max_runtime_evaluations_per_step
            )
        else:
            raise ValueError(
                "RMS FMI ME runtime evaluation limit must be an integer between "
                "1 and 10000000"
            )
        self.verbose: int = verbose
