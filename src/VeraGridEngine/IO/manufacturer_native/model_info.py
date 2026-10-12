# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import hashlib
import json
from typing import Tuple

from VeraGridEngine.enumerations import (
    IeeeCigreDllDataType,
    IeeeCigreDllModelMode,
    NativeModelInterface,
    NativeSampleTimeSource,
)
from VeraGridEngine.Utils.procedural_logic import (
    IeeeCigreDllParameterOverride,
    IeeeCigreDllSignalBinding,
    ManufacturerNativeControllerLogic,
    ManufacturerNativeRebindPlan,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Var


class ManufacturerNativeSignalInfo:
    """Platform-neutral description of one manufacturer signal port."""

    __slots__ = (
        "name", "description", "unit", "data_type", "width", "source_path", "semantic_type",
    )

    def __init__(self,
                 name: str,
                 description: str,
                 unit: str,
                 data_type: IeeeCigreDllDataType,
                 width: int,
                 source_path: str = "",
                 semantic_type: int = 0) -> None:
        """Create one signal description.

        :param name: Stable signal name supplied by the manufacturer.
        :param description: Human-readable signal description.
        :param unit: Engineering unit text.
        :param data_type: Primitive canonical data type.
        :param width: Number of scalar elements in the signal.
        :param source_path: Optional source-model block path.
        :param semantic_type: Optional legacy signal semantic identifier.
        :return: None.
        """

        self.name: str = name
        self.description: str = description
        self.unit: str = unit
        self.data_type: IeeeCigreDllDataType = data_type
        self.width: int = width
        self.source_path: str = source_path
        self.semantic_type: int = semantic_type


class ManufacturerNativeParameterInfo:
    """Platform-neutral description of one manufacturer parameter."""

    __slots__ = (
        "name", "group_name", "description", "unit", "data_type", "fixed_value",
        "default_value", "minimum_value", "maximum_value",
    )

    def __init__(self,
                 name: str,
                 group_name: str,
                 description: str,
                 unit: str,
                 data_type: IeeeCigreDllDataType,
                 fixed_value: bool,
                 default_value: int | float | str,
                 minimum_value: int | float | str | None,
                 maximum_value: int | float | str | None) -> None:
        """Create one scalar parameter description.

        :param name: Stable parameter name supplied by the manufacturer.
        :param group_name: Manufacturer parameter group.
        :param description: Human-readable parameter description.
        :param unit: Engineering unit text.
        :param data_type: Primitive canonical data type.
        :param fixed_value: Whether initialization fixes the value.
        :param default_value: Declared default value.
        :param minimum_value: Declared numeric minimum, or ``None`` for text.
        :param maximum_value: Declared numeric maximum, or ``None`` for text.
        :return: None.
        """

        self.name: str = name
        self.group_name: str = group_name
        self.description: str = description
        self.unit: str = unit
        self.data_type: IeeeCigreDllDataType = data_type
        self.fixed_value: bool = fixed_value
        self.default_value: int | float | str = default_value
        self.minimum_value: int | float | str | None = minimum_value
        self.maximum_value: int | float | str | None = maximum_value


class ManufacturerNativeModelInfo:
    """Canonical metadata shared by all supported manufacturer ABIs."""

    __slots__ = (
        "native_interface", "interface_version", "model_name", "model_version",
        "model_description", "version_control_info", "general_information", "model_created",
        "model_creator", "model_last_modified_date", "model_last_modified_by",
        "model_modified_comment", "model_modified_history", "code_generated_on",
        "included_solver", "fixed_step_base_sample_time", "effective_sample_time",
        "sample_time_source", "model_mode", "input_ports", "output_ports", "parameters",
        "num_cont_states", "sizeof_misc_states", "loadflow_flag", "num_int_states",
        "num_float_states", "num_double_states",
    )

    def __init__(self,
                 interface_version: Tuple[int, int, int, int],
                 model_name: str,
                 model_version: str,
                 model_description: str,
                 general_information: str,
                 model_created: str,
                 model_creator: str,
                 model_last_modified_date: str,
                 model_last_modified_by: str,
                 model_modified_comment: str,
                 model_modified_history: str,
                 fixed_step_base_sample_time: float,
                 model_mode: IeeeCigreDllModelMode,
                 input_ports: Tuple[ManufacturerNativeSignalInfo, ...],
                 output_ports: Tuple[ManufacturerNativeSignalInfo, ...],
                 parameters: Tuple[ManufacturerNativeParameterInfo, ...],
                 num_int_states: int,
                 num_float_states: int,
                 num_double_states: int,
                 native_interface: NativeModelInterface = NativeModelInterface.IEEE_CIGRE_V1_1,
                 version_control_info: str = "",
                 code_generated_on: str = "",
                 included_solver: str = "",
                 effective_sample_time: float | None = None,
                 sample_time_source: NativeSampleTimeSource = NativeSampleTimeSource.MANUFACTURER_DECLARED,
                 num_cont_states: int = 0,
                 sizeof_misc_states: int = 0,
                 loadflow_flag: bool = False) -> None:
        """Create one immutable-shape canonical metadata snapshot.

        :param interface_version: Four-byte manufacturer ABI version.
        :param model_name: Manufacturer model name.
        :param model_version: Manufacturer model version.
        :param model_description: Model description.
        :param general_information: General model information.
        :param model_created: Creation date text.
        :param model_creator: Model creator text.
        :param model_last_modified_date: Last modification date text.
        :param model_last_modified_by: Last modifier text.
        :param model_modified_comment: Last modification comment.
        :param model_modified_history: Modification history.
        :param fixed_step_base_sample_time: Sample time declared by ModelInfo.
        :param model_mode: Supported RMS/EMT domain.
        :param input_ports: Ordered input port descriptions.
        :param output_ports: Ordered output port descriptions.
        :param parameters: Ordered scalar parameter descriptions.
        :param num_int_states: Host-visible signed 32-bit state count.
        :param num_float_states: Host-visible float32 state count.
        :param num_double_states: Host-visible float64 state count.
        :param native_interface: Exact persisted ABI family.
        :param version_control_info: Optional source version-control description.
        :param code_generated_on: Optional code-generation date.
        :param included_solver: Optional solver declaration.
        :param effective_sample_time: Runtime sample time, or the declared value when omitted.
        :param sample_time_source: Origin of the effective sample time.
        :param num_cont_states: Continuous-state count.
        :param sizeof_misc_states: Opaque miscellaneous-state byte count.
        :param loadflow_flag: Whether the ABI advertises a load-flow function.
        :return: None.
        """

        resolved_sample_time: float
        if effective_sample_time is None:
            resolved_sample_time = fixed_step_base_sample_time
        else:
            resolved_sample_time = effective_sample_time
        self.native_interface: NativeModelInterface = native_interface
        self.interface_version: Tuple[int, int, int, int] = interface_version
        self.model_name: str = model_name
        self.model_version: str = model_version
        self.model_description: str = model_description
        self.version_control_info: str = version_control_info
        self.general_information: str = general_information
        self.model_created: str = model_created
        self.model_creator: str = model_creator
        self.model_last_modified_date: str = model_last_modified_date
        self.model_last_modified_by: str = model_last_modified_by
        self.model_modified_comment: str = model_modified_comment
        self.model_modified_history: str = model_modified_history
        self.code_generated_on: str = code_generated_on
        self.included_solver: str = included_solver
        self.fixed_step_base_sample_time: float = fixed_step_base_sample_time
        self.effective_sample_time: float = resolved_sample_time
        self.sample_time_source: NativeSampleTimeSource = sample_time_source
        self.model_mode: IeeeCigreDllModelMode = model_mode
        self.input_ports: Tuple[ManufacturerNativeSignalInfo, ...] = input_ports
        self.output_ports: Tuple[ManufacturerNativeSignalInfo, ...] = output_ports
        self.parameters: Tuple[ManufacturerNativeParameterInfo, ...] = parameters
        self.num_cont_states: int = num_cont_states
        self.sizeof_misc_states: int = sizeof_misc_states
        self.loadflow_flag: bool = loadflow_flag
        self.num_int_states: int = num_int_states
        self.num_float_states: int = num_float_states
        self.num_double_states: int = num_double_states

def build_manufacturer_native_rebind_plan(
        consumer_idtag: str,
        source_provider_idtag: str,
        destination_provider_idtag: str,
        source_model_info_sha256: str,
        destination_model_info_sha256: str,
        source_model_info: ManufacturerNativeModelInfo,
        destination_model_info: ManufacturerNativeModelInfo,
        occurrences: Tuple[
            Tuple[IeeeCigreDllModelMode, ManufacturerNativeControllerLogic], ...
        ],
        input_port_mapping: Tuple[int, ...],
        output_port_mapping: Tuple[int, ...],
        parameter_mapping: Tuple[int, ...],
) -> ManufacturerNativeRebindPlan:
    """Validate and build one complete different-digest consumer rebind.

    Mappings are explicit permutations from each source ordinal to one
    destination ordinal. Signal names are deliberately irrelevant.

    :param consumer_idtag: Stable identity of the affected template.
    :param source_provider_idtag: Current provider identity.
    :param destination_provider_idtag: Replacement provider identity.
    :param source_model_info_sha256: Current canonical metadata digest.
    :param destination_model_info_sha256: Replacement metadata digest.
    :param source_model_info: Decoded current metadata.
    :param destination_model_info: Decoded replacement metadata.
    :param occurrences: Every affected logic occurrence and its template domain.
    :param input_port_mapping: Complete source-to-destination input permutation.
    :param output_port_mapping: Complete source-to-destination output permutation.
    :param parameter_mapping: Complete source-to-destination parameter permutation.
    :return: Transient plan containing only primitive preconditions and replacements.
    """
    if len(occurrences) == 0:
        raise ValueError("Different-digest rebind requires at least one occurrence")
    else:
        pass
    if (
            len(source_model_info.input_ports) != len(destination_model_info.input_ports)
            or len(source_model_info.output_ports) != len(destination_model_info.output_ports)
            or len(source_model_info.parameters) != len(destination_model_info.parameters)
    ):
        raise ValueError("Different-digest rebind requires equal metadata cardinality")
    else:
        pass
    if (
            len(input_port_mapping) != len(source_model_info.input_ports)
            or set(input_port_mapping) != set(range(len(destination_model_info.input_ports)))
    ):
        raise ValueError("Input mapping must be a complete collision-free permutation")
    else:
        pass
    if (
            len(output_port_mapping) != len(source_model_info.output_ports)
            or set(output_port_mapping) != set(range(len(destination_model_info.output_ports)))
    ):
        raise ValueError("Output mapping must be a complete collision-free permutation")
    else:
        pass
    if (
            len(parameter_mapping) != len(source_model_info.parameters)
            or set(parameter_mapping) != set(range(len(destination_model_info.parameters)))
    ):
        raise ValueError("Parameter mapping must be a complete collision-free permutation")
    else:
        pass

    source_ordinal: int
    destination_ordinal: int
    for source_ordinal, destination_ordinal in enumerate(input_port_mapping):
        source_signal: ManufacturerNativeSignalInfo = source_model_info.input_ports[source_ordinal]
        destination_signal: ManufacturerNativeSignalInfo = (
            destination_model_info.input_ports[destination_ordinal]
        )
        if (
                source_signal.data_type != destination_signal.data_type
                or source_signal.width != destination_signal.width
        ):
            raise ValueError("Mapped input DataType or Width is incompatible")
        else:
            pass
    for source_ordinal, destination_ordinal in enumerate(output_port_mapping):
        source_signal = source_model_info.output_ports[source_ordinal]
        destination_signal = destination_model_info.output_ports[destination_ordinal]
        if (
                source_signal.data_type != destination_signal.data_type
                or source_signal.width != destination_signal.width
        ):
            raise ValueError("Mapped output DataType or Width is incompatible")
        else:
            pass
    for source_ordinal, destination_ordinal in enumerate(parameter_mapping):
        source_parameter: ManufacturerNativeParameterInfo = (
            source_model_info.parameters[source_ordinal]
        )
        destination_parameter: ManufacturerNativeParameterInfo = (
            destination_model_info.parameters[destination_ordinal]
        )
        if (
                source_parameter.data_type != destination_parameter.data_type
                or source_parameter.fixed_value != destination_parameter.fixed_value
        ):
            raise ValueError("Mapped parameter DataType or FixedValue is incompatible")
        else:
            pass

    fingerprints: list[str] = list()
    signal_record_groups: list[Tuple[Tuple[bool, int, int, str, int], ...]] = list()
    override_record_groups: list[
        Tuple[Tuple[int, int, bool, int | float | str], ...]
    ] = list()
    occurrence_mode: IeeeCigreDllModelMode
    logic: ManufacturerNativeControllerLogic
    for occurrence_mode, logic in occurrences:
        if occurrence_mode not in (IeeeCigreDllModelMode.RMS, IeeeCigreDllModelMode.EMT):
            raise ValueError("Rebind occurrence domain must be RMS or EMT")
        else:
            pass
        if (
                source_model_info.model_mode
                not in (occurrence_mode, IeeeCigreDllModelMode.EMT_AND_RMS)
                or destination_model_info.model_mode
                not in (occurrence_mode, IeeeCigreDllModelMode.EMT_AND_RMS)
        ):
            raise ValueError("Source or destination model mode does not support the consumer")
        else:
            pass
        if (
                logic.provider_idtag != source_provider_idtag
                or logic.model_info_sha256 != source_model_info_sha256
        ):
            raise ValueError("Rebind occurrence does not match the source provider")
        else:
            pass

        expected_bindings: set[Tuple[bool, int, int]] = set()
        for source_ordinal, source_signal in enumerate(source_model_info.input_ports):
            element_ordinal: int
            for element_ordinal in range(source_signal.width):
                expected_bindings.add((True, source_ordinal, element_ordinal))
        for source_ordinal, source_signal in enumerate(source_model_info.output_ports):
            for element_ordinal in range(source_signal.width):
                expected_bindings.add((False, source_ordinal, element_ordinal))
        actual_bindings: set[Tuple[bool, int, int]] = set()
        signal_records: list[Tuple[bool, int, int, str, int]] = list()
        binding: IeeeCigreDllSignalBinding
        for binding in logic.signal_bindings:
            binding_variable: Var = binding.get_variable()
            binding_key: Tuple[bool, int, int] = (
                binding.is_input,
                binding.port_ordinal,
                binding.element_ordinal,
            )
            if binding_key in actual_bindings:
                raise ValueError("Rebind occurrence contains a duplicate signal binding")
            else:
                actual_bindings.add(binding_key)
            if binding.is_input:
                if binding.port_ordinal < 0 or binding.port_ordinal >= len(input_port_mapping):
                    raise ValueError("Input binding ordinal is outside source ModelInfo")
                else:
                    mapped_port: int = input_port_mapping[binding.port_ordinal]
            else:
                if binding.port_ordinal < 0 or binding.port_ordinal >= len(output_port_mapping):
                    raise ValueError("Output binding ordinal is outside source ModelInfo")
                else:
                    mapped_port = output_port_mapping[binding.port_ordinal]
            signal_records.append((
                binding.is_input,
                mapped_port,
                binding.element_ordinal,
                binding_variable.name,
                binding_variable.non_mutable_uid,
            ))
        if actual_bindings != expected_bindings:
            raise ValueError("Rebind occurrence does not bind every signal element exactly once")
        else:
            pass

        override_records: list[Tuple[int, int, bool, int | float | str]] = list()
        override: IeeeCigreDllParameterOverride
        seen_parameters: set[int] = set()
        for override in logic.parameter_overrides:
            if (
                    override.parameter_ordinal < 0
                    or override.parameter_ordinal >= len(parameter_mapping)
                    or override.parameter_ordinal in seen_parameters
            ):
                raise ValueError("Rebind occurrence has an invalid parameter override ordinal")
            else:
                seen_parameters.add(override.parameter_ordinal)
                mapped_parameter_ordinal: int = parameter_mapping[
                    override.parameter_ordinal
                ]
                destination_parameter = destination_model_info.parameters[
                    mapped_parameter_ordinal
                ]
            if (
                    override.data_type != int(destination_parameter.data_type.value)
                    or override.fixed_value != destination_parameter.fixed_value
            ):
                raise ValueError("Rebind override type or FixedValue is incompatible")
            else:
                pass
            override_value: int | float | str = override.value
            if destination_parameter.data_type == IeeeCigreDllDataType.C_STRING:
                if not isinstance(override_value, str):
                    raise ValueError("Rebind string override must remain text")
                else:
                    pass
            else:
                if isinstance(override_value, str):
                    raise ValueError("Rebind numeric override cannot become text")
                else:
                    numeric_value: float = float(override_value)
                minimum_value: int | float | str | None = destination_parameter.minimum_value
                maximum_value: int | float | str | None = destination_parameter.maximum_value
                if (
                        not isinstance(minimum_value, (int, float))
                        or not isinstance(maximum_value, (int, float))
                        or numeric_value < float(minimum_value)
                        or numeric_value > float(maximum_value)
                ):
                    raise ValueError("Rebind override is outside destination minimum or maximum")
                else:
                    pass
            override_records.append((
                mapped_parameter_ordinal,
                override.data_type,
                override.fixed_value,
                override_value,
            ))

        fingerprint_payload: tuple[object, ...] = (
            int(occurrence_mode.value),
            logic.provider_idtag,
            logic.model_info_sha256,
            tuple(
                (
                    binding.is_input,
                    binding.port_ordinal,
                    binding.element_ordinal,
                    binding.get_variable().name,
                    binding.get_variable().non_mutable_uid,
                )
                for binding in logic.signal_bindings
            ),
            tuple(
                (
                    override.parameter_ordinal,
                    override.data_type,
                    override.fixed_value,
                    override.value,
                )
                for override in logic.parameter_overrides
            ),
        )
        fingerprint_bytes: bytes = json.dumps(
            fingerprint_payload,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        fingerprints.append(hashlib.sha256(fingerprint_bytes).hexdigest())
        signal_record_groups.append(tuple(signal_records))
        override_record_groups.append(tuple(override_records))

    return ManufacturerNativeRebindPlan(
        consumer_idtag=consumer_idtag,
        source_provider_idtag=source_provider_idtag,
        destination_provider_idtag=destination_provider_idtag,
        source_model_info_sha256=source_model_info_sha256,
        destination_model_info_sha256=destination_model_info_sha256,
        source_occurrence_fingerprints=tuple(fingerprints),
        replacement_signal_records=tuple(signal_record_groups),
        replacement_override_records=tuple(override_record_groups),
    )
