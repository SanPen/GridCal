# SPDX-License-Identifier: MPL-2.0
"""Declarative FMU device configuration and its existing versioned codecs."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, cast

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import FmuDeviceDomain, VarPowerFlowReferenceType
from VeraGridEngine.IO.fmu.Elements.bindings import (
    FmiThreeFloat64ConfigurationValue, FmiThreeUInt64ConfigurationValue,
    FmuBindingDirection, FmuFloat64ParameterValue, FmuImportConfig,
    FmuRefBinding, FmuVariableBinding, _validate_fmi_three_configuration_values,
    validate_fmu_float64_parameter_values,
)
from VeraGridEngine.IO.fmu.model_description import FmuInterfaceMode
from VeraGridEngine.IO.fmu.worker_host import FmiThreeWorkerHostLimits


def _validate_parameter_binding_identities(
    parameter_bindings: tuple[FmuVariableBinding, ...],
) -> None:
    """Validate persisted parameter identities independently from Block data.

    :param parameter_bindings: Ordered Block-symbol to FMU-name mappings.
    :return: None.
    :raises ValueError: If ownership, identity, uniqueness, or transform is invalid.
    """

    observed_signal_names: set[str] = set()
    observed_variable_names: set[str] = set()
    binding: FmuVariableBinding
    for binding in parameter_bindings:
        if isinstance(binding, FmuVariableBinding):
            pass
        else:
            raise ValueError("FMU parameter mapping has an invalid owner")
        signal_name_is_valid: bool = (
            isinstance(binding.signal_name, str)
            and len(binding.signal_name.strip()) > 0
        )
        variable_name_is_valid: bool = (
            isinstance(binding.variable_name, str)
            and len(binding.variable_name.strip()) > 0
        )
        if signal_name_is_valid and variable_name_is_valid:
            pass
        else:
            raise ValueError("FMU parameter mapping names must be non-empty")
        if (
            binding.signal_name in observed_signal_names
            or binding.variable_name in observed_variable_names
        ):
            raise ValueError("FMU parameter mappings must be unique")
        else:
            observed_signal_names.add(binding.signal_name)
            observed_variable_names.add(binding.variable_name)
        if binding.direction == FmuBindingDirection.PARAMETER:
            pass
        else:
            raise ValueError("FMU parameter mapping direction must be PARAMETER")
        transform_is_identity: bool = (
            math.isfinite(binding.scale)
            and math.isfinite(binding.offset)
            and binding.scale == 1.0
            and binding.offset == 0.0
        )
        if transform_is_identity:
            pass
        else:
            raise ValueError("FMU parameter mapping transform must be identity")


class FmuCsDeviceConfigRecord:
    """Store the serialized configuration of one imported FMU CS device.

    :param domain: Runtime domain that will consume the FMU.
    :param fmu_path: Original FMU path.
    :param preferred_mode: Preferred FMI mode string.
    :param input_bindings: VeraGrid-to-FMU bindings.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param output_defaults: Default output values before the first FMU step.
    :param output_param_names: Runtime parameter variable names backing each output.
    :param extraction_root: Optional trusted extraction root.
    :param communication_step: Optional communication step.
    :param relative_tolerance: Optional FMI relative tolerance.
    :param debug_logging: Enable FMI debug logging.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param configuration_float64_values: Structural Float64 declarations.
    :param configuration_uint64_values: Structural UInt64 declarations.
    :param parameter_bindings: Block-symbol to FMU-parameter identities.
    """

    __slots__ = (
        "domain",
        "fmu_path",
        "preferred_mode",
        "input_bindings",
        "output_bindings",
        "output_defaults",
        "output_param_names",
        "extraction_root",
        "communication_step",
        "relative_tolerance",
        "debug_logging",
        "worker_limits",
        "configuration_float64_values",
        "configuration_uint64_values",
        "parameter_bindings",
    )

    def __init__(
        self,
        domain: Any,
        fmu_path: str,
        preferred_mode: str | None,
        input_bindings: tuple[Any, ...],
        output_bindings: tuple[Any, ...],
        output_defaults: dict[VarPowerFlowReferenceType, float],
        output_param_names: dict[VarPowerFlowReferenceType, str],
        extraction_root: str | None = None,
        communication_step: float | None = None,
        relative_tolerance: float | None = None,
        debug_logging: bool = False,
        worker_limits: FmiThreeWorkerHostLimits | None = None,
        configuration_float64_values: tuple[
            FmiThreeFloat64ConfigurationValue, ...
        ] = tuple(),
        configuration_uint64_values: tuple[
            FmiThreeUInt64ConfigurationValue, ...
        ] = tuple(),
        parameter_bindings: tuple[FmuVariableBinding, ...] = tuple(),
    ) -> None:
        """Store the serialized FMU CS device configuration.

        :param domain: Runtime domain that will consume the FMU.
        :param fmu_path: Original FMU path.
        :param preferred_mode: Preferred FMI mode string.
        :param input_bindings: VeraGrid-to-FMU bindings.
        :param output_bindings: FMU-to-VeraGrid bindings.
        :param output_defaults: Default output values.
        :param output_param_names: Persisted output parameter names.
        :param extraction_root: Optional trusted extraction root.
        :param communication_step: Optional communication step.
        :param relative_tolerance: Optional FMI relative tolerance.
        :param debug_logging: Enable FMI debug logging.
        :param worker_limits: Explicit FMI 3 worker supervision policy.
        :param configuration_float64_values: Structural Float64 declarations.
        :param configuration_uint64_values: Structural UInt64 declarations.
        :param parameter_bindings: Block-symbol to FMU-parameter identities.
        :return: None.
        """

        self.domain: Any = domain
        self.fmu_path: str = fmu_path
        self.preferred_mode: str | None = preferred_mode
        self.input_bindings: tuple[Any, ...] = input_bindings
        self.output_bindings: tuple[Any, ...] = output_bindings
        self.output_defaults: dict[VarPowerFlowReferenceType, float] = output_defaults
        self.output_param_names: dict[VarPowerFlowReferenceType, str] = output_param_names
        self.extraction_root: str | None = extraction_root
        self.communication_step: float | None = communication_step
        self.relative_tolerance: float | None = relative_tolerance
        self.debug_logging: bool = debug_logging
        self.worker_limits: FmiThreeWorkerHostLimits | None = worker_limits
        _validate_fmi_three_configuration_values(
            configuration_float64_values=configuration_float64_values,
            configuration_uint64_values=configuration_uint64_values,
        )
        self.configuration_float64_values: tuple[
            FmiThreeFloat64ConfigurationValue, ...
        ] = tuple(configuration_float64_values)
        self.configuration_uint64_values: tuple[
            FmiThreeUInt64ConfigurationValue, ...
        ] = tuple(configuration_uint64_values)
        _validate_parameter_binding_identities(parameter_bindings)
        self.parameter_bindings: tuple[FmuVariableBinding, ...] = tuple(
            parameter_bindings
        )


class FmuMeDeviceConfigRecord:
    """Store the serialized configuration of one imported FMU ME device.

    :param domain: Runtime domain that will consume the FMU.
    :param fmu_path: Original FMU path.
    :param preferred_mode: Preferred FMI mode string.
    :param input_bindings: VeraGrid-to-FMU bindings.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param output_defaults: Default output values before the first ME predictor step.
    :param output_param_names: Runtime parameter variable names backing each output.
    :param extraction_root: Optional trusted extraction root.
    :param relative_tolerance: Optional FMI relative tolerance.
    :param debug_logging: Enable FMI debug logging.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param maximum_event_iterations: Positive Event Mode convergence bound.
    :param configuration_float64_values: Structural Float64 declarations.
    :param configuration_uint64_values: Structural UInt64 declarations.
    """

    __slots__ = (
        "domain",
        "fmu_path",
        "preferred_mode",
        "input_bindings",
        "output_bindings",
        "output_defaults",
        "output_param_names",
        "extraction_root",
        "relative_tolerance",
        "debug_logging",
        "worker_limits",
        "maximum_event_iterations",
        "configuration_float64_values",
        "configuration_uint64_values",
        "parameter_bindings",
    )

    def __init__(
        self,
        domain: Any,
        fmu_path: str,
        preferred_mode: str | None,
        input_bindings: tuple[Any, ...],
        output_bindings: tuple[Any, ...],
        output_defaults: dict[VarPowerFlowReferenceType, float],
        output_param_names: dict[VarPowerFlowReferenceType, str],
        extraction_root: str | None = None,
        relative_tolerance: float | None = None,
        debug_logging: bool = False,
        worker_limits: FmiThreeWorkerHostLimits | None = None,
        maximum_event_iterations: int = 32,
        configuration_float64_values: tuple[
            FmiThreeFloat64ConfigurationValue, ...
        ] = tuple(),
        configuration_uint64_values: tuple[
            FmiThreeUInt64ConfigurationValue, ...
        ] = tuple(),
        parameter_bindings: tuple[FmuVariableBinding, ...] = tuple(),
    ) -> None:
        """Store the serialized FMU ME device configuration.

        :param domain: Runtime domain that will consume the FMU.
        :param fmu_path: Original FMU path.
        :param preferred_mode: Preferred FMI mode string.
        :param input_bindings: VeraGrid-to-FMU bindings.
        :param output_bindings: FMU-to-VeraGrid bindings.
        :param output_defaults: Default output values.
        :param output_param_names: Persisted output parameter names.
        :param extraction_root: Optional trusted extraction root.
        :param relative_tolerance: Optional FMI relative tolerance.
        :param debug_logging: Enable FMI debug logging.
        :param worker_limits: Explicit FMI 3 worker supervision policy.
        :param maximum_event_iterations: Positive Event Mode convergence bound.
        :param configuration_float64_values: Structural Float64 declarations.
        :param configuration_uint64_values: Structural UInt64 declarations.
        :param parameter_bindings: Block-symbol to FMU-parameter identities.
        :return: None.
        """

        self.domain: Any = domain
        self.fmu_path: str = fmu_path
        self.preferred_mode: str | None = preferred_mode
        self.input_bindings: tuple[Any, ...] = input_bindings
        self.output_bindings: tuple[Any, ...] = output_bindings
        self.output_defaults: dict[VarPowerFlowReferenceType, float] = output_defaults
        self.output_param_names: dict[VarPowerFlowReferenceType, str] = output_param_names
        self.extraction_root: str | None = extraction_root
        self.relative_tolerance: float | None = relative_tolerance
        self.debug_logging: bool = debug_logging
        self.worker_limits: FmiThreeWorkerHostLimits | None = worker_limits
        if (
            isinstance(maximum_event_iterations, int)
            and not isinstance(maximum_event_iterations, bool)
            and 1 <= maximum_event_iterations <= 1024
        ):
            self.maximum_event_iterations: int = maximum_event_iterations
        else:
            raise ValueError(
                "FMI ME maximum Event Mode iterations must be an integer between 1 and 1024"
            )
        _validate_fmi_three_configuration_values(
            configuration_float64_values=configuration_float64_values,
            configuration_uint64_values=configuration_uint64_values,
        )
        self.configuration_float64_values: tuple[
            FmiThreeFloat64ConfigurationValue, ...
        ] = tuple(configuration_float64_values)
        self.configuration_uint64_values: tuple[
            FmiThreeUInt64ConfigurationValue, ...
        ] = tuple(configuration_uint64_values)
        _validate_parameter_binding_identities(parameter_bindings)
        self.parameter_bindings: tuple[FmuVariableBinding, ...] = tuple(
            parameter_bindings
        )


def _reference_to_text(reference: VarPowerFlowReferenceType) -> str:
    """Convert one VeraGrid power-flow reference enum into text.

    :param reference: VeraGrid reference enum.
    :return: Serialized enum value.
    """

    return reference.value


def _reference_from_text(value: str) -> VarPowerFlowReferenceType:
    """Restore one VeraGrid power-flow reference enum from text.

    :param value: Serialized enum value.
    :return: VeraGrid reference enum.
    """

    return VarPowerFlowReferenceType(value)


def _dump_fmi_three_configuration_values(
    configuration_float64_values: tuple[
        FmiThreeFloat64ConfigurationValue, ...
    ],
    configuration_uint64_values: tuple[
        FmiThreeUInt64ConfigurationValue, ...
    ],
) -> tuple[
    list[tuple[str, tuple[float, ...]]],
    list[tuple[str, int]],
]:
    """Build the shared declarative Configuration Mode persistence payload.

    :param configuration_float64_values: Structural Float64 declarations.
    :param configuration_uint64_values: Structural UInt64 declarations.
    :return: Ordered Float64 and UInt64 primitive payload arrays.
    """

    # Revalidate at the persistence boundary so mutations of the light public
    # declaration objects cannot introduce invalid source data into the file.
    _validate_fmi_three_configuration_values(
        configuration_float64_values=configuration_float64_values,
        configuration_uint64_values=configuration_uint64_values,
    )
    float64_payload: list[tuple[str, tuple[float, ...]]] = [
        ("", tuple())
    ] * len(configuration_float64_values)
    uint64_payload: list[tuple[str, int]] = [("", 0)] * len(
        configuration_uint64_values
    )
    configuration_index: int
    for configuration_index in range(len(configuration_float64_values)):
        float64_configuration: FmiThreeFloat64ConfigurationValue = (
            configuration_float64_values[configuration_index]
        )
        float64_payload[configuration_index] = (
            float64_configuration.variable_name,
            float64_configuration.values,
        )
    for configuration_index in range(len(configuration_uint64_values)):
        uint64_configuration: FmiThreeUInt64ConfigurationValue = (
            configuration_uint64_values[configuration_index]
        )
        uint64_payload[configuration_index] = (
            uint64_configuration.variable_name,
            uint64_configuration.value,
        )
    return float64_payload, uint64_payload


def _load_fmi_three_configuration_values(
    float64_payload: object,
    uint64_payload: object,
) -> tuple[
    tuple[FmiThreeFloat64ConfigurationValue, ...],
    tuple[FmiThreeUInt64ConfigurationValue, ...],
]:
    """Parse the shared Configuration Mode persistence payload fail-closed.

    :param float64_payload: Parsed JSON value for Float64 declarations.
    :param uint64_payload: Parsed JSON value for UInt64 declarations.
    :return: Validated typed Float64 and UInt64 declaration tuples.
    """

    if isinstance(float64_payload, list):
        configuration_float64_values: list[
            FmiThreeFloat64ConfigurationValue | None
        ] = [None] * len(float64_payload)
        configuration_index: int
        for configuration_index in range(len(float64_payload)):
            configuration_entry: object = float64_payload[configuration_index]
            if isinstance(configuration_entry, list) and len(configuration_entry) == 2:
                variable_name_payload: object = configuration_entry[0]
                values_payload: object = configuration_entry[1]
                if (
                    isinstance(variable_name_payload, str)
                    and isinstance(values_payload, list)
                ):
                    normalized_values: list[float] = [0.0] * len(values_payload)
                    value_index: int
                    for value_index in range(len(values_payload)):
                        raw_value: object = values_payload[value_index]
                        if (
                            isinstance(raw_value, (int, float))
                            and not isinstance(raw_value, bool)
                        ):
                            normalized_values[value_index] = float(raw_value)
                        else:
                            raise ValueError(
                                "Invalid FMI 3 Float64 configuration value"
                            )
                    configuration_float64_values[configuration_index] = (
                        FmiThreeFloat64ConfigurationValue(
                            variable_name=variable_name_payload,
                            values=tuple(normalized_values),
                        )
                    )
                else:
                    raise ValueError(
                        "Invalid FMI 3 Float64 configuration declaration"
                    )
            else:
                raise ValueError(
                    "Invalid FMI 3 Float64 configuration declaration"
                )
    else:
        raise ValueError(
            "FMI 3 Float64 configuration declarations must be an array"
        )

    if isinstance(uint64_payload, list):
        configuration_uint64_values: list[
            FmiThreeUInt64ConfigurationValue | None
        ] = [None] * len(uint64_payload)
        for configuration_index in range(len(uint64_payload)):
            configuration_entry = uint64_payload[configuration_index]
            if (
                isinstance(configuration_entry, list)
                and len(configuration_entry) == 2
                and isinstance(configuration_entry[0], str)
                and isinstance(configuration_entry[1], int)
                and not isinstance(configuration_entry[1], bool)
            ):
                configuration_uint64_values[configuration_index] = (
                    FmiThreeUInt64ConfigurationValue(
                        variable_name=configuration_entry[0],
                        value=configuration_entry[1],
                    )
                )
            else:
                raise ValueError(
                    "Invalid FMI 3 UInt64 configuration declaration"
                )
    else:
        raise ValueError(
            "FMI 3 UInt64 configuration declarations must be an array"
        )

    typed_float64_values: tuple[FmiThreeFloat64ConfigurationValue, ...] = cast(
        tuple[FmiThreeFloat64ConfigurationValue, ...],
        tuple(configuration_float64_values),
    )
    typed_uint64_values: tuple[FmiThreeUInt64ConfigurationValue, ...] = cast(
        tuple[FmiThreeUInt64ConfigurationValue, ...],
        tuple(configuration_uint64_values),
    )
    _validate_fmi_three_configuration_values(
        configuration_float64_values=typed_float64_values,
        configuration_uint64_values=typed_uint64_values,
    )
    return typed_float64_values, typed_uint64_values


def _build_output_parameter_name(output_var_name: str) -> str:
    """
    Build the event-parameter variable name associated with one FMU output variable.

    :param output_var_name: Symbolic output variable name.
    :return: Event-parameter variable name.
    """

    if output_var_name.startswith("fmu_"):
        return output_var_name.replace("fmu_", "fmu_param_", 1)
    else:
        return f"fmu_param_{output_var_name}"


def _dump_fmi_three_worker_limits(
    worker_limits: FmiThreeWorkerHostLimits | None,
) -> dict[str, int | float] | None:
    """Build the declarative payload for one optional worker policy.

    :param worker_limits: Validated FMI 3 worker supervision policy.
    :return: Primitive persistence payload, or ``None`` when no policy exists.
    """

    if worker_limits is None:
        return None
    else:
        # Persistence owns only declarative values. Runtime validation remains
        # centralized in the worker-limit constructor during restoration.
        worker_limits_payload: dict[str, int | float] = dict()
        worker_limits_payload["maximum_frame_size"] = (
            worker_limits.maximum_frame_size
        )
        worker_limits_payload["maximum_float64_values_per_request"] = (
            worker_limits.maximum_float64_values_per_request
        )
        worker_limits_payload["response_timeout_seconds"] = (
            worker_limits.response_timeout_seconds
        )
        worker_limits_payload["graceful_join_timeout_seconds"] = (
            worker_limits.graceful_join_timeout_seconds
        )
        worker_limits_payload["terminate_join_timeout_seconds"] = (
            worker_limits.terminate_join_timeout_seconds
        )
        worker_limits_payload["kill_join_timeout_seconds"] = (
            worker_limits.kill_join_timeout_seconds
        )
        return worker_limits_payload


def _load_fmi_three_worker_limits(
    worker_limits_payload: object,
) -> FmiThreeWorkerHostLimits | None:
    """Restore one optional worker policy from declarative persistence data.

    :param worker_limits_payload: Parsed JSON value for the worker policy.
    :return: Validated worker limits, or ``None`` for legacy/absent policies.
    :raises ValueError: If the payload is neither an object nor ``null``.
    """

    if worker_limits_payload is None:
        return None
    else:
        if isinstance(worker_limits_payload, dict):
            return FmiThreeWorkerHostLimits(
                maximum_frame_size=int(
                    worker_limits_payload["maximum_frame_size"]
                ),
                maximum_float64_values_per_request=int(
                    worker_limits_payload[
                        "maximum_float64_values_per_request"
                    ]
                ),
                response_timeout_seconds=float(
                    worker_limits_payload["response_timeout_seconds"]
                ),
                graceful_join_timeout_seconds=float(
                    worker_limits_payload["graceful_join_timeout_seconds"]
                ),
                terminate_join_timeout_seconds=float(
                    worker_limits_payload["terminate_join_timeout_seconds"]
                ),
                kill_join_timeout_seconds=float(
                    worker_limits_payload["kill_join_timeout_seconds"]
                ),
            )
        else:
            raise ValueError("FMI device worker_limits must be an object or null")


def dump_fmu_cs_device_config(record: FmuCsDeviceConfigRecord) -> str:
    """Serialize one imported FMU CS device configuration.

    :param record: Device configuration record.
    :return: JSON payload.
    """

    _validate_parameter_binding_identities(record.parameter_bindings)
    input_bindings_payload: list[dict[str, str | int | None]] = list()
    output_bindings_payload: list[dict[str, str | int | None]] = list()
    output_defaults_payload: dict[str, float] = dict()
    output_param_names_payload: dict[str, str] = dict()
    parameter_bindings_payload: list[tuple[str, str]] = [
        ("", "")
    ] * len(record.parameter_bindings)

    binding: Any
    for binding in record.input_bindings:
        input_bindings_payload.append(
            {
                "reference": _reference_to_text(binding.reference),
                "fmu_variable_name": binding.fmu_variable_name,
                "flat_index": binding.flat_index,
            }
        )

    for binding in record.output_bindings:
        output_bindings_payload.append(
            {
                "reference": _reference_to_text(binding.reference),
                "fmu_variable_name": binding.fmu_variable_name,
                "flat_index": binding.flat_index,
            }
        )

    parameter_binding_index: int
    for parameter_binding_index in range(len(record.parameter_bindings)):
        parameter_binding: FmuVariableBinding = record.parameter_bindings[
            parameter_binding_index
        ]
        parameter_bindings_payload[parameter_binding_index] = (
            parameter_binding.signal_name,
            parameter_binding.variable_name,
        )

    # Persist structural providers before their future consumers so restore can
    # rebuild Configuration Mode declarations without inferring runtime state.
    configuration_float64_payload: list[tuple[str, tuple[float, ...]]]
    configuration_uint64_payload: list[tuple[str, int]]
    (
        configuration_float64_payload,
        configuration_uint64_payload,
    ) = _dump_fmi_three_configuration_values(
        configuration_float64_values=record.configuration_float64_values,
        configuration_uint64_values=record.configuration_uint64_values,
    )

    reference: VarPowerFlowReferenceType
    for reference, value in record.output_defaults.items():
        output_defaults_payload[_reference_to_text(reference)] = float(value)

    for reference, value in record.output_param_names.items():
        output_param_names_payload[_reference_to_text(reference)] = value

    worker_limits_payload: dict[str, int | float] | None = (
        _dump_fmi_three_worker_limits(record.worker_limits)
    )

    payload: dict[str, Any] = dict()
    payload["version"] = 4
    payload["domain"] = record.domain.value
    payload["fmu_path"] = record.fmu_path
    payload["preferred_mode"] = record.preferred_mode
    payload["configuration_float64_values"] = configuration_float64_payload
    payload["configuration_uint64_values"] = configuration_uint64_payload
    payload["parameter_bindings"] = parameter_bindings_payload
    payload["input_bindings"] = input_bindings_payload
    payload["output_bindings"] = output_bindings_payload
    payload["output_defaults"] = output_defaults_payload
    payload["output_param_names"] = output_param_names_payload
    payload["extraction_root"] = record.extraction_root
    payload["communication_step"] = record.communication_step
    payload["relative_tolerance"] = record.relative_tolerance
    payload["debug_logging"] = record.debug_logging
    payload["worker_limits"] = worker_limits_payload
    return json.dumps(payload, sort_keys=True)


def load_fmu_cs_device_config(data: str | None) -> FmuCsDeviceConfigRecord | None:
    """Deserialize one imported FMU CS device configuration.

    :param data: Serialized JSON payload.
    :return: Parsed configuration record when available.
    """

    if data is None:
        return None
    else:
        text: str = data.strip()
        if len(text) == 0:
            return None
        else:
            payload: dict[str, Any] = json.loads(text)
            config_version: int = int(payload.get("version", 1))
            if config_version in (2, 3, 4):
                worker_limits_payload: object = payload.get("worker_limits", None)
            else:
                worker_limits_payload = None
            worker_limits: FmiThreeWorkerHostLimits | None = (
                _load_fmi_three_worker_limits(worker_limits_payload)
            )
            if config_version in (1, 2, 3, 4):
                input_bindings: list[Any] = list()
                output_bindings: list[Any] = list()
                item: dict[str, Any]
                for item in payload.get("input_bindings", list()):
                    if config_version in (3, 4):
                        flat_index_payload: object = item["flat_index"]
                    else:
                        flat_index_payload = None
                    input_bindings.append(
                        FmuRefBinding(
                            reference=_reference_from_text(str(item["reference"])),
                            fmu_variable_name=str(item["fmu_variable_name"]),
                            flat_index=cast(int | None, flat_index_payload),
                        )
                    )
                for item in payload.get("output_bindings", list()):
                    if config_version in (3, 4):
                        flat_index_payload = item["flat_index"]
                    else:
                        flat_index_payload = None
                    output_bindings.append(
                        FmuRefBinding(
                            reference=_reference_from_text(str(item["reference"])),
                            fmu_variable_name=str(item["fmu_variable_name"]),
                            flat_index=cast(int | None, flat_index_payload),
                        )
                    )

                if config_version in (3, 4):
                    float64_payload: object = payload[
                        "configuration_float64_values"
                    ]
                    uint64_payload: object = payload[
                        "configuration_uint64_values"
                    ]
                else:
                    float64_payload = list()
                    uint64_payload = list()
                configuration_float64_values: tuple[
                    FmiThreeFloat64ConfigurationValue, ...
                ]
                configuration_uint64_values: tuple[
                    FmiThreeUInt64ConfigurationValue, ...
                ]
                (
                    configuration_float64_values,
                    configuration_uint64_values,
                ) = _load_fmi_three_configuration_values(
                    float64_payload=float64_payload,
                    uint64_payload=uint64_payload,
                )

                parameter_bindings: list[FmuVariableBinding] = list()
                if config_version == 4:
                    parameter_bindings_payload: object = payload[
                        "parameter_bindings"
                    ]
                    if isinstance(parameter_bindings_payload, list):
                        parameter_binding_payload: object
                        for parameter_binding_payload in parameter_bindings_payload:
                            if (
                                isinstance(parameter_binding_payload, list)
                                and len(parameter_binding_payload) == 2
                                and isinstance(parameter_binding_payload[0], str)
                                and isinstance(parameter_binding_payload[1], str)
                            ):
                                parameter_bindings.append(
                                    FmuVariableBinding(
                                        signal_name=parameter_binding_payload[0],
                                        variable_name=parameter_binding_payload[1],
                                        direction=FmuBindingDirection.PARAMETER,
                                    )
                                )
                            else:
                                raise ValueError(
                                    "FMI CS parameter binding must contain two names"
                                )
                    else:
                        raise ValueError(
                            "FMI CS parameter_bindings must be an array"
                        )
                else:
                    pass

                output_defaults: dict[VarPowerFlowReferenceType, float] = dict()
                output_param_names: dict[VarPowerFlowReferenceType, str] = dict()
                key: str
                for key, value in payload.get("output_defaults", dict()).items():
                    output_defaults[_reference_from_text(key)] = float(value)
                for key, value in payload.get("output_param_names", dict()).items():
                    output_param_names[_reference_from_text(key)] = str(value)

                return FmuCsDeviceConfigRecord(
                    domain=FmuDeviceDomain(str(payload["domain"])),
                    fmu_path=str(payload["fmu_path"]),
                    preferred_mode=payload.get("preferred_mode", None),
                    input_bindings=tuple(input_bindings),
                    output_bindings=tuple(output_bindings),
                    output_defaults=output_defaults,
                    output_param_names=output_param_names,
                    extraction_root=payload.get("extraction_root", None),
                    communication_step=payload.get("communication_step", None),
                    relative_tolerance=payload.get("relative_tolerance", None),
                    debug_logging=bool(payload.get("debug_logging", False)),
                    worker_limits=worker_limits,
                    configuration_float64_values=configuration_float64_values,
                    configuration_uint64_values=configuration_uint64_values,
                    parameter_bindings=tuple(parameter_bindings),
                )
            else:
                raise ValueError(
                    "Unsupported FMI CS device config version: "
                    f"{payload.get('version')}"
                )


def build_import_config_from_record(record: FmuCsDeviceConfigRecord) -> FmuImportConfig:
    """Build the runtime import config from one serialized device record.

    :param record: Stored FMU CS device record.
    :return: Runtime import configuration.
    """

    preferred_mode: FmuInterfaceMode | None
    if record.preferred_mode is None:
        preferred_mode = None
    else:
        preferred_mode = FmuInterfaceMode(record.preferred_mode)

    extraction_root: Path | None
    if record.extraction_root is None:
        extraction_root = None
    else:
        extraction_root = Path(record.extraction_root)

    return FmuImportConfig(
        fmu_path=Path(record.fmu_path),
        preferred_mode=preferred_mode,
        communication_step=record.communication_step,
        relative_tolerance=record.relative_tolerance,
        extraction_root=extraction_root,
        debug_logging=record.debug_logging,
    )


def build_record_from_device_arguments(
    domain: Any,
    config: FmuImportConfig,
    input_bindings: tuple[Any, ...],
    output_bindings: tuple[Any, ...],
    output_defaults: dict[VarPowerFlowReferenceType, float],
    block: Block,
    worker_limits: FmiThreeWorkerHostLimits | None = None,
    configuration_float64_values: tuple[
        FmiThreeFloat64ConfigurationValue, ...
    ] = tuple(),
    configuration_uint64_values: tuple[
        FmiThreeUInt64ConfigurationValue, ...
    ] = tuple(),
    parameter_bindings: tuple[FmuVariableBinding, ...] = tuple(),
) -> FmuCsDeviceConfigRecord:
    """Build a serializable FMU device record from runtime arguments.

    :param domain: Runtime domain consuming the FMU.
    :param config: Runtime import configuration.
    :param input_bindings: VeraGrid-to-FMU bindings.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param output_defaults: Default output values.
    :param block: Device block carrying the output parameter variables.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param configuration_float64_values: Structural Float64 declarations.
    :param configuration_uint64_values: Structural UInt64 declarations.
    :param parameter_bindings: Block-symbol to FMU-parameter identities.
    :return: Serialized FMU device record.
    """

    _resolve_parameter_values_from_block(
        parameter_bindings=parameter_bindings,
        block=block,
    )
    output_param_names: dict[VarPowerFlowReferenceType, str] = dict()
    binding: Any
    for binding in output_bindings:
        output_var = block.external_mapping[binding.reference]
        event_parameter_name: str = _build_output_parameter_name(str(output_var.name))
        output_param_names[binding.reference] = event_parameter_name

    extraction_root_text: str | None
    if config.extraction_root is None:
        extraction_root_text = None
    else:
        extraction_root_text = str(config.extraction_root)

    preferred_mode_text: str | None
    if config.preferred_mode is None:
        preferred_mode_text = None
    else:
        preferred_mode_text = config.preferred_mode.value

    return FmuCsDeviceConfigRecord(
        domain=domain,
        fmu_path=str(config.fmu_path),
        preferred_mode=preferred_mode_text,
        input_bindings=input_bindings,
        output_bindings=output_bindings,
        output_defaults=dict(output_defaults),
        output_param_names=output_param_names,
        extraction_root=extraction_root_text,
        communication_step=config.communication_step,
        relative_tolerance=config.relative_tolerance,
        debug_logging=config.debug_logging,
        worker_limits=worker_limits,
        configuration_float64_values=configuration_float64_values,
        configuration_uint64_values=configuration_uint64_values,
        parameter_bindings=parameter_bindings,
    )


def _resolve_parameter_values_from_block(
    parameter_bindings: tuple[FmuVariableBinding, ...],
    block: Block,
) -> tuple[FmuFloat64ParameterValue, ...]:
    """Resolve current Block constants through strict persisted identities.

    Persisted mappings are untrusted data. Every field and every current Block
    owner is validated before any runtime specification can be constructed.

    :param parameter_bindings: Persisted Block-symbol to FMU-name mappings.
    :param block: Current canonical Block owning parameter constants.
    :return: Ephemeral ordered runtime parameter values.
    :raises ValueError: If a mapping or current Block value is ambiguous or invalid.
    """

    _validate_parameter_binding_identities(parameter_bindings)
    parameter_values: list[FmuFloat64ParameterValue | None] = [None] * len(
        parameter_bindings
    )
    binding_index: int
    for binding_index in range(len(parameter_bindings)):
        binding: FmuVariableBinding = parameter_bindings[binding_index]
        matching_value: Const | None = None
        matching_count: int = 0
        parameter_var: Var
        parameter_const: Const
        for parameter_var, parameter_const in block.parameters.items():
            if parameter_var.name == binding.signal_name:
                matching_count += 1
                if isinstance(parameter_const, Const):
                    matching_value = parameter_const
                else:
                    raise ValueError(
                        "FMU parameter Block value must be a Const"
                    )
            else:
                pass
        if matching_count == 1 and matching_value is not None:
            pass
        else:
            raise ValueError(
                "FMU parameter mapping must resolve exactly one Block Var-to-Const"
            )
        source_value: object = matching_value.value
        source_value_is_numeric: bool = (
            isinstance(source_value, (int, float))
            and not isinstance(source_value, bool)
        )
        if source_value_is_numeric and math.isfinite(float(source_value)):
            parameter_values[binding_index] = FmuFloat64ParameterValue(
                variable_name=binding.variable_name,
                value=float(source_value),
            )
        else:
            raise ValueError("FMU parameter Block value must be a finite scalar")
    resolved_values: list[FmuFloat64ParameterValue] = list()
    parameter_value: FmuFloat64ParameterValue | None
    for parameter_value in parameter_values:
        if parameter_value is not None:
            resolved_values.append(parameter_value)
        else:
            raise RuntimeError("FMU parameter resolution is incomplete")
    return tuple(resolved_values)


def dump_fmu_me_device_config(record: FmuMeDeviceConfigRecord) -> str:
    """Serialize one imported FMU ME device configuration.

    :param record: Device configuration record.
    :return: JSON payload.
    """

    _validate_parameter_binding_identities(record.parameter_bindings)
    input_bindings_payload: list[dict[str, str | int | None]] = list()
    output_bindings_payload: list[dict[str, str | int | None]] = list()
    output_defaults_payload: dict[str, float] = dict()
    output_param_names_payload: dict[str, str] = dict()
    parameter_bindings_payload: list[tuple[str, str]] = [
        ("", "")
    ] * len(record.parameter_bindings)
    worker_limits_payload: dict[str, int | float] | None

    binding: Any
    for binding in record.input_bindings:
        input_bindings_payload.append(
            {
                "reference": _reference_to_text(binding.reference),
                "fmu_variable_name": binding.fmu_variable_name,
                "flat_index": binding.flat_index,
            }
        )

    for binding in record.output_bindings:
        output_bindings_payload.append(
            {
                "reference": _reference_to_text(binding.reference),
                "fmu_variable_name": binding.fmu_variable_name,
                "flat_index": binding.flat_index,
            }
        )

    parameter_binding_index: int
    for parameter_binding_index in range(len(record.parameter_bindings)):
        parameter_binding: FmuVariableBinding = record.parameter_bindings[
            parameter_binding_index
        ]
        parameter_bindings_payload[parameter_binding_index] = (
            parameter_binding.signal_name,
            parameter_binding.variable_name,
        )

    # Keep structural providers explicit and ordered before future consumers;
    # the runtime session will remain the sole vector owner in a later commit.
    configuration_float64_payload: list[tuple[str, tuple[float, ...]]]
    configuration_uint64_payload: list[tuple[str, int]]
    (
        configuration_float64_payload,
        configuration_uint64_payload,
    ) = _dump_fmi_three_configuration_values(
        configuration_float64_values=record.configuration_float64_values,
        configuration_uint64_values=record.configuration_uint64_values,
    )

    reference: VarPowerFlowReferenceType
    for reference, value in record.output_defaults.items():
        output_defaults_payload[_reference_to_text(reference)] = float(value)
    for reference, value in record.output_param_names.items():
        output_param_names_payload[_reference_to_text(reference)] = value

    worker_limits_payload = _dump_fmi_three_worker_limits(record.worker_limits)

    payload: dict[str, Any] = dict()
    payload["version"] = 5
    payload["domain"] = record.domain.value
    payload["fmu_path"] = record.fmu_path
    payload["preferred_mode"] = record.preferred_mode
    payload["configuration_float64_values"] = configuration_float64_payload
    payload["configuration_uint64_values"] = configuration_uint64_payload
    payload["parameter_bindings"] = parameter_bindings_payload
    payload["input_bindings"] = input_bindings_payload
    payload["output_bindings"] = output_bindings_payload
    payload["output_defaults"] = output_defaults_payload
    payload["output_param_names"] = output_param_names_payload
    # Keep the historical field as inert downgrade metadata.  Current
    # simulation options, never persisted attachment data, own the solver.
    payload["integration_method"] = "explicit_euler"
    payload["extraction_root"] = record.extraction_root
    payload["relative_tolerance"] = record.relative_tolerance
    payload["debug_logging"] = record.debug_logging
    payload["worker_limits"] = worker_limits_payload
    payload["maximum_event_iterations"] = record.maximum_event_iterations
    return json.dumps(payload, sort_keys=True)


def load_fmu_me_device_config(data: str | None) -> FmuMeDeviceConfigRecord | None:
    """Deserialize one imported FMU ME device configuration.

    :param data: Serialized JSON payload.
    :return: Parsed configuration record when available.
    """

    if data is None:
        return None
    else:
        text: str = data.strip()
        if len(text) == 0:
            return None
        else:
            payload: dict[str, Any] = json.loads(text)
            config_version: int = int(payload.get("version", 1))
            if config_version in (2, 3, 4, 5):
                worker_limits_payload: object = payload.get("worker_limits", None)
            else:
                worker_limits_payload = None
            worker_limits: FmiThreeWorkerHostLimits | None = (
                _load_fmi_three_worker_limits(worker_limits_payload)
            )

            if config_version in (1, 2, 3, 4, 5):
                if "integration_method" in payload:
                    integration_method_payload: object = payload[
                        "integration_method"
                    ]
                else:
                    raise ValueError(
                        "FMI ME device config requires integration_method "
                        "compatibility metadata"
                    )
                if (
                    isinstance(integration_method_payload, str)
                    and integration_method_payload == "explicit_euler"
                ):
                    pass
                else:
                    raise ValueError(
                        "FMI ME integration_method compatibility metadata must "
                        "be the exact string 'explicit_euler'"
                    )

                input_bindings: list[Any] = list()
                output_bindings: list[Any] = list()
                item: dict[str, Any]
                for item in payload.get("input_bindings", list()):
                    if config_version in (3, 4, 5):
                        flat_index_payload: object = item["flat_index"]
                    else:
                        flat_index_payload = None
                    input_bindings.append(
                        FmuRefBinding(
                            reference=_reference_from_text(str(item["reference"])),
                            fmu_variable_name=str(item["fmu_variable_name"]),
                            flat_index=cast(int | None, flat_index_payload),
                        )
                    )
                for item in payload.get("output_bindings", list()):
                    if config_version in (3, 4, 5):
                        flat_index_payload = item["flat_index"]
                    else:
                        flat_index_payload = None
                    output_bindings.append(
                        FmuRefBinding(
                            reference=_reference_from_text(str(item["reference"])),
                            fmu_variable_name=str(item["fmu_variable_name"]),
                            flat_index=cast(int | None, flat_index_payload),
                        )
                    )

                if config_version in (3, 4, 5):
                    float64_payload: object = payload[
                        "configuration_float64_values"
                    ]
                    uint64_payload: object = payload[
                        "configuration_uint64_values"
                    ]
                else:
                    float64_payload = list()
                    uint64_payload = list()
                configuration_float64_values: tuple[
                    FmiThreeFloat64ConfigurationValue, ...
                ]
                configuration_uint64_values: tuple[
                    FmiThreeUInt64ConfigurationValue, ...
                ]
                (
                    configuration_float64_values,
                    configuration_uint64_values,
                ) = _load_fmi_three_configuration_values(
                    float64_payload=float64_payload,
                    uint64_payload=uint64_payload,
                )

                parameter_bindings: list[FmuVariableBinding] = list()
                if config_version == 5:
                    parameter_bindings_payload: object = payload[
                        "parameter_bindings"
                    ]
                    if isinstance(parameter_bindings_payload, list):
                        parameter_binding_payload: object
                        for parameter_binding_payload in parameter_bindings_payload:
                            if (
                                isinstance(parameter_binding_payload, list)
                                and len(parameter_binding_payload) == 2
                                and isinstance(parameter_binding_payload[0], str)
                                and isinstance(parameter_binding_payload[1], str)
                            ):
                                parameter_bindings.append(
                                    FmuVariableBinding(
                                        signal_name=parameter_binding_payload[0],
                                        variable_name=parameter_binding_payload[1],
                                        direction=FmuBindingDirection.PARAMETER,
                                    )
                                )
                            else:
                                raise ValueError(
                                    "FMI ME parameter binding must contain two names"
                                )
                    else:
                        raise ValueError(
                            "FMI ME parameter_bindings must be an array"
                        )
                else:
                    pass

                output_defaults: dict[VarPowerFlowReferenceType, float] = dict()
                output_param_names: dict[VarPowerFlowReferenceType, str] = dict()
                key: str
                for key, value in payload.get("output_defaults", dict()).items():
                    output_defaults[_reference_from_text(key)] = float(value)
                for key, value in payload.get("output_param_names", dict()).items():
                    output_param_names[_reference_from_text(key)] = str(value)

                # Version 4 owns this resource limit explicitly and rejects
                # coercible or missing values.  Older schemas alone retain the
                # compatibility default that predates the persisted field.
                if config_version in (4, 5):
                    if "maximum_event_iterations" in payload:
                        maximum_event_iterations_payload: object = payload[
                            "maximum_event_iterations"
                        ]
                    else:
                        raise ValueError(
                            "FMI ME current schema requires maximum Event Mode iterations"
                        )
                    if (
                        isinstance(maximum_event_iterations_payload, int)
                        and not isinstance(maximum_event_iterations_payload, bool)
                        and 1 <= maximum_event_iterations_payload <= 1024
                    ):
                        maximum_event_iterations: int = (
                            maximum_event_iterations_payload
                        )
                    else:
                        raise ValueError(
                            "FMI ME current-schema maximum Event Mode iterations "
                            "must be an integer between 1 and 1024"
                        )
                else:
                    maximum_event_iterations = 32

                return FmuMeDeviceConfigRecord(
                    domain=FmuDeviceDomain(str(payload["domain"])),
                    fmu_path=str(payload["fmu_path"]),
                    preferred_mode=payload.get("preferred_mode", None),
                    input_bindings=tuple(input_bindings),
                    output_bindings=tuple(output_bindings),
                    output_defaults=output_defaults,
                    output_param_names=output_param_names,
                    extraction_root=payload.get("extraction_root", None),
                    relative_tolerance=payload.get("relative_tolerance", None),
                    debug_logging=bool(payload.get("debug_logging", False)),
                    worker_limits=worker_limits,
                    maximum_event_iterations=maximum_event_iterations,
                    configuration_float64_values=configuration_float64_values,
                    configuration_uint64_values=configuration_uint64_values,
                    parameter_bindings=tuple(parameter_bindings),
                )
            else:
                raise ValueError(
                    "Unsupported FMI ME device config version: "
                    f"{payload.get('version')}"
                )


def build_me_record_from_device_arguments(
    domain: Any,
    config: FmuImportConfig,
    input_bindings: tuple[Any, ...],
    output_bindings: tuple[Any, ...],
    output_defaults: dict[VarPowerFlowReferenceType, float],
    block: Block,
    worker_limits: FmiThreeWorkerHostLimits | None = None,
    maximum_event_iterations: int = 32,
    configuration_float64_values: tuple[
        FmiThreeFloat64ConfigurationValue, ...
    ] = tuple(),
    configuration_uint64_values: tuple[
        FmiThreeUInt64ConfigurationValue, ...
    ] = tuple(),
    parameter_bindings: tuple[FmuVariableBinding, ...] = tuple(),
) -> FmuMeDeviceConfigRecord:
    """Build a serializable FMU ME device record from runtime arguments.

    :param domain: Runtime domain consuming the FMU.
    :param config: Runtime import configuration.
    :param input_bindings: VeraGrid-to-FMU bindings.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param output_defaults: Default output values.
    :param block: Device block carrying the output parameter variables.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param maximum_event_iterations: Positive Event Mode convergence bound.
    :param configuration_float64_values: Structural Float64 declarations.
    :param configuration_uint64_values: Structural UInt64 declarations.
    :param parameter_bindings: Block-symbol to FMU-parameter identities.
    :return: Serialized FMU ME device record.
    """

    _resolve_parameter_values_from_block(
        parameter_bindings=parameter_bindings,
        block=block,
    )
    output_param_names: dict[VarPowerFlowReferenceType, str] = dict()
    binding: Any
    for binding in output_bindings:
        output_var = block.external_mapping[binding.reference]
        event_parameter_name: str = _build_output_parameter_name(str(output_var.name))
        output_param_names[binding.reference] = event_parameter_name

    extraction_root_text: str | None
    if config.extraction_root is None:
        extraction_root_text = None
    else:
        extraction_root_text = str(config.extraction_root)

    preferred_mode_text: str | None
    if config.preferred_mode is None:
        preferred_mode_text = None
    else:
        preferred_mode_text = config.preferred_mode.value

    return FmuMeDeviceConfigRecord(
        domain=domain,
        fmu_path=str(config.fmu_path),
        preferred_mode=preferred_mode_text,
        input_bindings=input_bindings,
        output_bindings=output_bindings,
        output_defaults=dict(output_defaults),
        output_param_names=output_param_names,
        extraction_root=extraction_root_text,
        relative_tolerance=config.relative_tolerance,
        debug_logging=config.debug_logging,
        worker_limits=worker_limits,
        maximum_event_iterations=maximum_event_iterations,
        configuration_float64_values=configuration_float64_values,
        configuration_uint64_values=configuration_uint64_values,
        parameter_bindings=parameter_bindings,
    )
