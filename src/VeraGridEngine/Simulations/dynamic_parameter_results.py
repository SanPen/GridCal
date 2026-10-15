# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Dynamic-parameter snapshots shared by RMS and EMT result drivers."""

from typing import Dict, List

import numpy as np

from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import (
    StaticParameterMappingDiagnostics,
    assign_static_api_object_mapping_for_device,
)
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Parents.dynamic_bus_parent import DynamicBusDevice
from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import DynamicSimulationMode, PlotSimulationType


def _get_numeric_constant_value(expression: Expr | Const | float | int | None) -> float | None:
    """Resolve a scalar from a symbolic parameter declaration.

    Only concrete constants belong in a results snapshot. General expressions
    remain the responsibility of the compiled runtime parameter vector.

    :param expression: Candidate symbolic or numerical parameter value.
    :return: Floating-point scalar, or ``None`` when it is not concrete.
    """
    if isinstance(expression, Const):
        raw_value: float | int | None = expression.value
        if isinstance(raw_value, (int, float, np.integer, np.floating)):
            return float(raw_value)
        else:
            return None
    else:
        if isinstance(expression, (int, float, np.integer, np.floating)):
            return float(expression)
        else:
            return None


def _get_mapped_parameter_value(parameter: Var,
                                mapped_values: Dict[Var, Const]) -> float | None:
    """Resolve one statically mapped parameter by immutable symbolic UID.

    Dynamic Editor persistence can clone ``Var`` objects while preserving their
    UID, so object-identity dictionary lookup alone is insufficient.

    :param parameter: Parameter whose API-mapped value is requested.
    :param mapped_values: Values produced by the unified static mapper.
    :return: Mapped scalar, or ``None`` when the parameter is not mapped.
    """
    direct_value: Const | None = mapped_values.get(parameter, None)
    if direct_value is not None:
        return _get_numeric_constant_value(expression=direct_value)
    else:
        pass

    mapped_parameter: Var
    mapped_value: Const
    for mapped_parameter, mapped_value in mapped_values.items():
        if mapped_parameter.uid == parameter.uid:
            return _get_numeric_constant_value(expression=mapped_value)
        else:
            pass

    return None


def _store_parameter_value(parameter_values: Dict[str, float],
                           device_idtag: str,
                           parameter: Var,
                           value: float | None) -> None:
    """Store one resolved parameter under the stable results key.

    :param parameter_values: Destination result snapshot.
    :param device_idtag: Stable owner-device identifier.
    :param parameter: Symbolic parameter being exported.
    :param value: Resolved scalar, or ``None`` when unavailable.
    :return: Nothing.
    """
    if value is not None:
        parameter_key: str = str(device_idtag) + ":" + str(parameter.name)
        parameter_values[parameter_key] = float(value)
    else:
        pass


def collect_declared_dynamic_parameter_values(grid: MultiCircuit,
                                              simulation_type: PlotSimulationType,
                                              logger: Logger | None) -> Dict[str, float]:
    """Collect all concrete parameters declared by configured dynamic models.

    The result catalogue is broader than the runtime event vector: it includes
    direct static constants, constants resolved through ``api_obj_mapping``, and
    initial constants of event-capable parameters. This function reconstructs
    that declarative catalogue from the circuit without adding GUI concerns to
    the numerical problem classes.

    :param grid: Circuit containing the configured RMS and EMT models.
    :param simulation_type: Dynamic simulation family to inspect.
    :param logger: Driver logger used by the shared static mapper.
    :return: Scalar map keyed by ``device_idtag:param_name``.
    """
    parameter_values: Dict[str, float] = dict()
    simulation_mode: DynamicSimulationMode
    if simulation_type == PlotSimulationType.RMS:
        simulation_mode = DynamicSimulationMode.RMS
    else:
        if simulation_type == PlotSimulationType.EMT:
            simulation_mode = DynamicSimulationMode.EMT
        else:
            raise ValueError("Unsupported dynamic simulation type")

    mapping_diagnostics: StaticParameterMappingDiagnostics = StaticParameterMappingDiagnostics(
        logger=logger,
        simulation_mode=simulation_mode,
    )
    device: ALL_DEV_TYPES

    for device in grid.get_all_elements_iter():
        if isinstance(device, (DynamicDevice, DynamicBusDevice)):
            model: Block
            if simulation_mode == DynamicSimulationMode.RMS:
                model = device.rms_model
            else:
                model = device.emt_model

            model_blocks: List[Block] = model.get_all_blocks()
            mapped_values: Dict[Var, Const] = dict()
            block_item: Block

            # The unified mapper owns hierarchy traversal. Calling it once on
            # the model root matches RMS and EMT problem assembly and prevents
            # duplicate mapping warnings for descendant blocks.
            assign_static_api_object_mapping_for_device(
                grid=grid,
                device=device,
                mdl=model,
                problem_mapping=mapped_values,
                logger=mapping_diagnostics,
            )

            # API-mapped targets can exist without a mirrored ``parameters``
            # declaration, so export the mapper output explicitly first.
            mapped_parameter: Var
            mapped_value: Const
            for mapped_parameter, mapped_value in mapped_values.items():
                _store_parameter_value(
                    parameter_values=parameter_values,
                    device_idtag=str(device.idtag),
                    parameter=mapped_parameter,
                    value=_get_numeric_constant_value(expression=mapped_value),
                )

            # Direct constants and event-capable initial constants complete the
            # catalogue exposed by Dynamic Editor and Results.
            for block_item in model_blocks:
                direct_parameter: Var
                declared_value: Const
                for direct_parameter, declared_value in block_item.parameters.items():
                    parameter_value: float | None = _get_mapped_parameter_value(
                        parameter=direct_parameter,
                        mapped_values=mapped_values,
                    )
                    if parameter_value is None:
                        parameter_value = _get_numeric_constant_value(expression=declared_value)
                    else:
                        pass
                    _store_parameter_value(
                        parameter_values=parameter_values,
                        device_idtag=str(device.idtag),
                        parameter=direct_parameter,
                        value=parameter_value,
                    )

                runtime_parameter: Var
                runtime_expression: Expr | Const
                for runtime_parameter, runtime_expression in block_item.event_dict.items():
                    runtime_value: float | None = _get_numeric_constant_value(expression=runtime_expression)
                    if runtime_value is None:
                        initialization_expression: Expr | Const | None = block_item.init_eqs.get(
                            runtime_parameter,
                            None,
                        )
                        runtime_value = _get_numeric_constant_value(expression=initialization_expression)
                    else:
                        pass
                    _store_parameter_value(
                        parameter_values=parameter_values,
                        device_idtag=str(device.idtag),
                        parameter=runtime_parameter,
                        value=runtime_value,
                    )
        else:
            pass

    return parameter_values
