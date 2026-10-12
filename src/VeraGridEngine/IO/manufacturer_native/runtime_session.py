# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import math
import struct
import sys
from typing import Iterable, Tuple

from VeraGridEngine.basic_structures import Logger, Vec
from VeraGridEngine.Devices.Dynamic.manufacturer_native_model import (
    ManufacturerNativeBinarySource,
    ManufacturerNativeBinaryVariant,
    ManufacturerNativeModel,
)
from VeraGridEngine.enumerations import (
    IeeeCigreDllDataType,
    IeeeCigreDllModelMode,
    IeeeCigreDllPlatform,
    IeeeCigreDllVerificationStatus,
    NativeModelInterface,
)
from VeraGridEngine.IO.manufacturer_native.model_info import ManufacturerNativeModelInfo
from VeraGridEngine.IO.manufacturer_native.model_info_codec import decode_manufacturer_native_model_info
from VeraGridEngine.IO.manufacturer_native.runtime_host import (
    ManufacturerNativeWorkerHost,
    prepare_manufacturer_native_worker_host,
)
from VeraGridEngine.IO.manufacturer_native.worker_artifact import ManufacturerNativeWorkerArtifact
from VeraGridEngine.IO.native_runtime import NativeWorkerLimits
from VeraGridEngine.Utils.procedural_logic import ManufacturerNativeControllerLogic, ProceduralProblem
from VeraGridEngine.Utils.Symbolic.symbolic import Var


class _RuntimeBinding:
    """Resolved numerical mapping for one native Block instance."""

    __slots__ = (
        "instance_id", "logic", "model_info", "group", "model_mode", "input_sources",
        "output_indices", "overrides", "sample_time", "next_sample_index",
    )

    def __init__(self,
                 instance_id: str,
                 logic: ManufacturerNativeControllerLogic,
                 model_info: ManufacturerNativeModelInfo,
                 group: "_RuntimeWorkerGroup",
                 model_mode: IeeeCigreDllModelMode,
                 input_sources: Tuple[Tuple[int, int], ...],
                 output_indices: Tuple[int, ...],
                 overrides: Tuple[Tuple[int, int, bool, int | float | str], ...]) -> None:
        """Store a complete fixed mapping before any instance allocation.

        :param instance_id: Deterministic session-local instance identity.
        :param logic: Declarative provider reference.
        :param model_info: Separately validated provider metadata.
        :param group: Exact binary worker owner.
        :param model_mode: RMS or EMT call mode.
        :param input_sources: Source-kind and vector-index pairs in ABI order.
        :param output_indices: Mutable parameter indexes in ABI order.
        :param overrides: Typed parameter override tuples.
        :return: None.
        """
        self.instance_id: str = instance_id
        self.logic: ManufacturerNativeControllerLogic = logic
        self.model_info: ManufacturerNativeModelInfo = model_info
        self.group: _RuntimeWorkerGroup = group
        self.model_mode: IeeeCigreDllModelMode = model_mode
        self.input_sources: Tuple[Tuple[int, int], ...] = input_sources
        self.output_indices: Tuple[int, ...] = output_indices
        self.overrides: Tuple[Tuple[int, int, bool, int | float | str], ...] = overrides
        self.sample_time: float = model_info.effective_sample_time
        self.next_sample_index: int = 1


class _RuntimeWorkerGroup:
    """One worker keyed only by exact binary SHA, platform and ABI."""

    __slots__ = ("binary_sha256", "platform", "interface", "host", "bindings", "buffer_bytes")

    def __init__(self,
                 binary_sha256: str,
                 platform: IeeeCigreDllPlatform,
                 interface: NativeModelInterface,
                 host: ManufacturerNativeWorkerHost) -> None:
        """Create one empty deterministic worker group.

        :param binary_sha256: Selected platform binary content identity.
        :param platform: Exact host platform.
        :param interface: Exact ABI identity.
        :param host: Started isolated worker.
        :return: None.
        """
        self.binary_sha256: str = binary_sha256
        self.platform: IeeeCigreDllPlatform = platform
        self.interface: NativeModelInterface = interface
        self.host: ManufacturerNativeWorkerHost = host
        self.bindings: list[_RuntimeBinding] = list()
        self.buffer_bytes: int = 0


def _host_platform() -> IeeeCigreDllPlatform:
    """Return the supported exact platform of this process.

    :return: Windows x64 or Linux x64 parent platform.
    """
    if struct.calcsize("P") != 8:
        raise RuntimeError("IEEE/CIGRE execution needs a matching 64-bit native worker")
    else:
        pass
    if sys.platform == "win32":
        return IeeeCigreDllPlatform.WINDOWS_X64
    else:
        if sys.platform.startswith("linux"):
            return IeeeCigreDllPlatform.LINUX_X64
        else:
            raise RuntimeError("IEEE/CIGRE runtime supports Windows x64 and Linux x64")


def _data_size(data_type: IeeeCigreDllDataType) -> int:
    """Return one conservative ABI primitive storage size.

    :param data_type: IEEE/CIGRE primitive type.
    :return: Storage bound in bytes for worker-owned values.
    """
    if data_type in (IeeeCigreDllDataType.CHAR, IeeeCigreDllDataType.INT8, IeeeCigreDllDataType.UINT8):
        return 1
    elif data_type in (IeeeCigreDllDataType.INT16, IeeeCigreDllDataType.UINT16):
        return 2
    elif data_type in (IeeeCigreDllDataType.INT32, IeeeCigreDllDataType.UINT32, IeeeCigreDllDataType.REAL32):
        return 4
    else:
        return 8


def _estimate_instance_bytes(model_info: ManufacturerNativeModelInfo) -> int:
    """Conservatively estimate all host-owned ABI buffers before allocation.

    :param model_info: Validated canonical metadata.
    :return: Conservative byte count.
    """
    total: int = 0
    signal = None
    for signal in model_info.input_ports:
        total += _data_size(signal.data_type) * signal.width + 8
    for signal in model_info.output_ports:
        total += _data_size(signal.data_type) * signal.width + 8
    parameter = None
    for parameter in model_info.parameters:
        total += _data_size(parameter.data_type) + 8
        if isinstance(parameter.default_value, str):
            total += len(parameter.default_value.encode("utf-8", errors="strict")) + 1
        else:
            pass
    total += 4 * model_info.num_int_states
    total += 4 * model_info.num_float_states
    total += 8 * model_info.num_double_states
    return total


def _scheduled_sample_time(next_sample_index: int, sample_time: float) -> float:
    """Calculate one finite, strictly positive indexed sample boundary.

    Integer indexes keep the schedule anchored to the model period instead of
    accumulating repeated floating-point additions. Conversion and
    multiplication can still exceed binary64, so both stages fail explicitly.

    :param next_sample_index: Positive one-based sample index.
    :param sample_time: Finite, strictly positive model period in seconds.
    :return: Finite scheduled boundary in seconds.
    """
    if next_sample_index < 1:
        raise ValueError("IEEE/CIGRE sample index must be positive")
    else:
        pass
    if not math.isfinite(sample_time) or sample_time <= 0.0:
        raise ValueError("IEEE/CIGRE sample period must be finite and positive")
    else:
        pass
    try:
        sample_index_float: float = float(next_sample_index)
    except OverflowError as ex:
        raise OverflowError("IEEE/CIGRE sample index exceeds binary64") from ex
    if not math.isfinite(sample_index_float):
        raise OverflowError("IEEE/CIGRE sample index exceeds binary64")
    else:
        scheduled: float = sample_index_float * sample_time
    if not math.isfinite(scheduled):
        raise OverflowError("IEEE/CIGRE fixed sample schedule overflowed")
    else:
        return scheduled


class ManufacturerNativeRuntimeSession:
    """Driver-owned event-group session for qualified manufacturer libraries."""

    __slots__ = (
        "_providers", "_platform", "_limits", "_logger", "_problem", "_groups",
        "_bindings", "_preflighted", "_initialized", "_closed", "_model_mode",
        "_worker_artifact",
    )

    def __init__(self,
                 providers: Iterable[ManufacturerNativeModel],
                 platform: IeeeCigreDllPlatform | None,
                 limits: NativeWorkerLimits,
                 logger: Logger,
                 worker_artifact: ManufacturerNativeWorkerArtifact | None = None) -> None:
        """Create an empty session without loading vendor code.

        :param providers: Circuit-owned canonical provider catalogue.
        :param platform: Exact execution platform or host-preferred automatic selection.
        :param limits: Finite worker and aggregate limits.
        :param logger: Simulation diagnostics.
        :param worker_artifact: Exact prepared worker selected for this session.
        :return: None.
        """
        self._providers: Tuple[ManufacturerNativeModel, ...] = tuple(providers)
        self._platform: IeeeCigreDllPlatform = _host_platform() if platform is None else platform
        self._limits: NativeWorkerLimits = limits
        self._logger: Logger = logger
        self._worker_artifact: ManufacturerNativeWorkerArtifact | None = worker_artifact
        self._problem: ProceduralProblem | None = None
        self._groups: list[_RuntimeWorkerGroup] = list()
        self._bindings: list[_RuntimeBinding] = list()
        self._preflighted: bool = False
        self._initialized: bool = False
        self._closed: bool = False
        self._model_mode: IeeeCigreDllModelMode | None = None

    def _provider(self, idtag: str) -> ManufacturerNativeModel:
        """Resolve one provider without a duplicate registry.

        :param idtag: Stable provider identity from the Block.
        :return: Matching circuit provider.
        """
        provider: ManufacturerNativeModel
        for provider in self._providers:
            if provider.idtag == idtag:
                return provider
            else:
                pass
        raise ValueError(f"Manufacturer native provider is missing: {idtag}")

    def _existing_group(self,
                        binary_sha256: str,
                        platform: IeeeCigreDllPlatform) -> _RuntimeWorkerGroup | None:
        """Find one exact worker key in the bounded group list.

        :param binary_sha256: Selected platform content identity.
        :param platform: Exact platform executed by the worker.
        :return: Existing group or ``None``.
        """
        group: _RuntimeWorkerGroup
        for group in self._groups:
            if (group.binary_sha256 == binary_sha256 and group.platform == platform
                    and group.interface == NativeModelInterface.IEEE_CIGRE_V1_1):
                return group
            else:
                pass
        return None

    def _resolve_mapping(self,
                         problem: ProceduralProblem,
                         logic: ManufacturerNativeControllerLogic,
                         model_info: ManufacturerNativeModelInfo) -> Tuple[Tuple[Tuple[int, int], ...], Tuple[int, ...]]:
        """Resolve every persisted ordinal and Var UID to compiled vector indexes.

        :param problem: Compiled numerical problem.
        :param logic: Declarative Block binding.
        :param model_info: Canonical provider metadata.
        :return: ABI-ordered input sources and output parameter indexes.
        """
        input_count: int = sum(signal.width for signal in model_info.input_ports)
        output_count: int = sum(signal.width for signal in model_info.output_ports)
        input_sources: list[Tuple[int, int] | None] = [None] * input_count
        output_indices: list[int | None] = [None] * output_count
        input_offsets: list[int] = list()
        output_offsets: list[int] = list()
        offset: int = 0
        signal = None
        for signal in model_info.input_ports:
            input_offsets.append(offset)
            offset += signal.width
        offset = 0
        for signal in model_info.output_ports:
            output_offsets.append(offset)
            offset += signal.width
        binding = None
        for binding in logic.signal_bindings:
            binding_variable: Var = binding.get_variable()
            signals = model_info.input_ports if binding.is_input else model_info.output_ports
            if binding.port_ordinal >= len(signals) or binding.element_ordinal >= signals[binding.port_ordinal].width:
                raise ValueError("IEEE/CIGRE Block signal ordinal is stale")
            else:
                pass
            if binding.is_input:
                flat_index: int = input_offsets[binding.port_ordinal] + binding.element_ordinal
                state_index: int | None = problem.uid2idx_vars.get(binding_variable.uid, None)
                event_index: int | None = problem.uid2idx_event_params.get(binding_variable.uid, None)
                const_index: int | None = problem.uid2idx_params.get(binding_variable.uid, None)
                if state_index is not None:
                    input_sources[flat_index] = (0, int(state_index))
                elif event_index is not None:
                    input_sources[flat_index] = (1, int(event_index))
                elif const_index is not None:
                    input_sources[flat_index] = (2, int(const_index))
                else:
                    raise ValueError("IEEE/CIGRE input binding cannot resolve its Var UID")
            else:
                flat_index = output_offsets[binding.port_ordinal] + binding.element_ordinal
                event_index = problem.uid2idx_event_params.get(binding_variable.uid, None)
                if event_index is None:
                    raise ValueError("IEEE/CIGRE output must map to a mutable runtime parameter")
                else:
                    output_indices[flat_index] = int(event_index)
        if any(source is None for source in input_sources) or any(index is None for index in output_indices):
            raise ValueError("IEEE/CIGRE Block must bind every declared signal element exactly once")
        else:
            return (
                tuple(source for source in input_sources if source is not None),
                tuple(index for index in output_indices if index is not None),
            )

    def preflight(self,
                  problem: ProceduralProblem,
                  logic_entries: Iterable[object],
                  model_mode: int) -> None:
        """Resolve all providers and start exact content-keyed workers.

        :param problem: Numerical problem exposing procedural maps.
        :param logic_entries: Runtime procedural entries.
        :param model_mode: Exact EMT or RMS ABI mode value.
        :return: None.
        """
        if self._preflighted or self._closed:
            raise RuntimeError("IEEE/CIGRE session preflight can run exactly once")
        else:
            pass

        if not isinstance(model_mode, int) or isinstance(model_mode, bool):
            raise TypeError("IEEE/CIGRE model mode must be an integer")
        else:
            selected_mode: IeeeCigreDllModelMode = IeeeCigreDllModelMode(model_mode)
        if selected_mode not in (IeeeCigreDllModelMode.EMT, IeeeCigreDllModelMode.RMS):
            raise ValueError("IEEE/CIGRE session mode must be EMT or RMS")
        else:
            self._model_mode = selected_mode
        typed_problem: ProceduralProblem = problem
        native_entries: list[ManufacturerNativeControllerLogic] = list()
        entry: object
        for entry in logic_entries:
            if isinstance(entry, ManufacturerNativeControllerLogic):
                native_entries.append(entry)
            else:
                pass
        if len(native_entries) > self._limits.maximum_instances_per_session:
            raise ValueError("IEEE/CIGRE session instance count exceeds its limit")
        else:
            pass
        session_bytes: int = 0
        logic: ManufacturerNativeControllerLogic
        for logic in native_entries:
            provider: ManufacturerNativeModel = self._provider(logic.provider_idtag)
            if provider.model_info_sha256 != logic.model_info_sha256:
                raise ValueError("IEEE/CIGRE Block ModelInfo digest is stale")
            else:
                model_info: ManufacturerNativeModelInfo = decode_manufacturer_native_model_info(provider.model_info)
            if model_info.model_mode not in (selected_mode, IeeeCigreDllModelMode.EMT_AND_RMS):
                raise ValueError("IEEE/CIGRE provider does not support this simulation domain")
            else:
                pass
            execution_platform: IeeeCigreDllPlatform = self._platform
            variant: ManufacturerNativeBinaryVariant | None = (
                provider.get_platform_variant(execution_platform)
            )
            source: ManufacturerNativeBinarySource | None = (
                provider.get_binary_source(execution_platform)
            )
            if (variant is None or source is None) and (
                    execution_platform == IeeeCigreDllPlatform.WINDOWS_X64):
                # A 64-bit Windows parent can run the reviewed PE32 worker when
                # the provider does not offer a native x64 variant.
                execution_platform = IeeeCigreDllPlatform.WINDOWS_X86
                variant = provider.get_platform_variant(execution_platform)
                source = provider.get_binary_source(execution_platform)
            else:
                pass
            if variant is None or source is None:
                raise ValueError("Manufacturer provider has no binary for the selected host")
            else:
                pass
            if variant.verification_status != IeeeCigreDllVerificationStatus.DECLARED_AND_QUALIFIED:
                raise ValueError("IEEE/CIGRE provider variant is not declared and qualified")
            else:
                pass
            group: _RuntimeWorkerGroup | None
            if provider.native_interface == NativeModelInterface.IEEE_CIGRE_V1_1:
                group = self._existing_group(
                    variant.content_sha256,
                    execution_platform,
                )
            else:
                # IEEE/CIGRE 1.0 and IEC ESE binaries may keep mutable globals.
                # One worker per Block makes that state process-local and deterministic.
                group = None
            if group is None:
                if len(self._groups) >= self._limits.maximum_workers:
                    raise ValueError("IEEE/CIGRE session worker count exceeds its limit")
                else:
                    host: ManufacturerNativeWorkerHost = prepare_manufacturer_native_worker_host(
                        source=source,
                        variant=variant,
                        canonical_model_info=provider.model_info,
                        limits=self._limits,
                        logger=self._logger,
                        worker_artifact=self._worker_artifact,
                    )
                    group = _RuntimeWorkerGroup(
                        binary_sha256=variant.content_sha256,
                        platform=execution_platform,
                        interface=provider.native_interface,
                        host=host,
                    )
                    self._groups.append(group)
            else:
                pass
            if len(group.bindings) >= self._limits.maximum_instances_per_worker:
                raise ValueError("IEEE/CIGRE worker instance count exceeds its limit")
            else:
                pass
            instance_bytes: int = _estimate_instance_bytes(model_info)
            if instance_bytes > self._limits.maximum_instance_buffer_bytes:
                raise ValueError("IEEE/CIGRE instance buffers exceed their limit")
            else:
                group.buffer_bytes += instance_bytes
                session_bytes += instance_bytes
            if group.buffer_bytes > self._limits.maximum_worker_buffer_bytes:
                raise ValueError("IEEE/CIGRE worker buffers exceed their aggregate limit")
            elif session_bytes > self._limits.maximum_session_buffer_bytes:
                raise ValueError("IEEE/CIGRE session buffers exceed their aggregate limit")
            else:
                pass
            input_sources: Tuple[Tuple[int, int], ...]
            output_indices: Tuple[int, ...]
            input_sources, output_indices = self._resolve_mapping(typed_problem, logic, model_info)
            overrides: list[Tuple[int, int, bool, int | float | str]] = list()
            override = None
            for override in logic.parameter_overrides:
                overrides.append((override.parameter_ordinal, override.data_type, override.fixed_value, override.value))
            instance_id: str = provider.idtag + ":" + f"{len(self._bindings):08d}"
            runtime_binding: _RuntimeBinding = _RuntimeBinding(
                instance_id=instance_id,
                logic=logic,
                model_info=model_info,
                group=group,
                model_mode=selected_mode,
                input_sources=input_sources,
                output_indices=output_indices,
                overrides=tuple(overrides),
            )
            group.bindings.append(runtime_binding)
            self._bindings.append(runtime_binding)
        self._problem = typed_problem
        self._preflighted = True

    def _inputs(self, binding: _RuntimeBinding, x: Vec, params: Vec) -> Tuple[int | float, ...]:
        """Copy one complete finite accepted input sample.

        :param binding: Resolved instance mapping.
        :param x: State and algebraic vector.
        :param params: Runtime parameter vector.
        :return: ABI-ordered input values.
        """
        problem: ProceduralProblem | None = self._problem
        if problem is None:
            raise RuntimeError("IEEE/CIGRE session has no bound problem")
        else:
            constants = problem.get_parameters_values()
        values: list[int | float] = list()
        source_kind: int
        source_index: int
        for source_kind, source_index in binding.input_sources:
            if source_kind == 0:
                value: int | float = float(x[source_index])
            elif source_kind == 1:
                value = float(params[source_index])
            else:
                value = float(constants[source_index].value)
            if not math.isfinite(float(value)):
                raise ValueError("IEEE/CIGRE controller input is not finite")
            else:
                values.append(value)
        return tuple(values)

    def _publish(self,
                 binding: _RuntimeBinding,
                 outputs: Tuple[int | float, ...],
                 params: Vec) -> None:
        """Publish one complete held output vector into mutable parameters.

        :param binding: Resolved instance mapping.
        :param outputs: ABI-ordered native outputs.
        :param params: Mutable runtime parameter vector.
        :return: None.
        """
        if len(outputs) != len(binding.output_indices):
            raise ValueError("IEEE/CIGRE output count differs from its Block binding")
        else:
            output_index: int
            output_value: int | float
            for output_index, output_value in zip(binding.output_indices, outputs):
                params[output_index] = float(output_value)

    def initialize(self, t: float, x: Vec, params: Vec) -> None:
        """Call startup once using the complete finite t0 input guess.

        :param t: Required zero startup time.
        :param x: Complete initialization state.
        :param params: Mutable runtime parameters receiving held outputs.
        :return: None.
        """
        if not self._preflighted or self._initialized or self._closed or abs(t) > 1e-12:
            raise RuntimeError("IEEE/CIGRE session initialization order or time is invalid")
        else:
            pass
        group: _RuntimeWorkerGroup
        for group in self._groups:
            specifications = list()
            binding: _RuntimeBinding
            for binding in group.bindings:
                specifications.append((
                    binding.instance_id,
                    binding.model_mode,
                    self._inputs(binding, x, params),
                    binding.overrides,
                ))
            results = group.host.initialize_instances(tuple(specifications))
            result_index: int
            result_id: str
            outputs: Tuple[int | float, ...]
            for result_index, (result_id, outputs) in enumerate(results):
                binding = group.bindings[result_index]
                if result_id != binding.instance_id:
                    raise ValueError("IEEE/CIGRE initialization response identity differs")
                else:
                    self._publish(binding, outputs, params)
        self._initialized = True

    def get_next_sample_time(self, t_prev: float, t_target: float) -> float | None:
        """Return the earliest representable pending fixed sample boundary.

        :param t_prev: Previous accepted time.
        :param t_target: Proposed solver target.
        :return: Earliest due boundary or ``None``.
        """
        candidate: float | None = None
        binding: _RuntimeBinding
        for binding in self._bindings:
            # Compute from the integer index so accepted boundaries never
            # accumulate step-by-step rounding drift.
            sample_time: float = _scheduled_sample_time(
                binding.next_sample_index, binding.sample_time,
            )
            if sample_time <= t_prev:
                raise RuntimeError("IEEE/CIGRE fixed sample schedule did not advance")
            else:
                pass
            # Selection is exact and directional. An absolute tolerance here
            # would silently suppress fast converter periods and subnormals.
            if sample_time <= t_target:
                candidate = sample_time if candidate is None else min(candidate, sample_time)
            else:
                pass
        return candidate

    def commit_boundary(self, t: float, x: Vec, params: Vec) -> None:
        """Advance due instances exactly once after an accepted network boundary.

        :param t: Accepted network time.
        :param x: Accepted state vector.
        :param params: Mutable runtime parameters receiving next-interval outputs.
        :return: None.
        """
        if not self._initialized or self._closed:
            raise RuntimeError("IEEE/CIGRE session is not active")
        else:
            pass
        if not math.isfinite(t):
            raise ValueError("Accepted IEEE/CIGRE boundary time must be finite")
        else:
            pass
        group: _RuntimeWorkerGroup
        for group in self._groups:
            due: list[_RuntimeBinding] = list()
            binding: _RuntimeBinding
            for binding in group.bindings:
                # Reuse the same indexed schedule used to force the solver
                # target, keeping selection and irreversible commit aligned.
                scheduled: float = _scheduled_sample_time(
                    binding.next_sample_index, binding.sample_time,
                )
                if t < scheduled:
                    # Earlier accepted work must never call manufacturer code.
                    pass
                else:
                    forward_difference: float = t - scheduled
                    forward_allowance: float = 4.0 * max(math.ulp(t), math.ulp(scheduled))
                    if forward_difference <= forward_allowance:
                        due.append(binding)
                    else:
                        raise RuntimeError("Solver passed an IEEE/CIGRE forced sample boundary")
            if len(due) > 0:
                samples = list()
                for binding in due:
                    samples.append((binding.instance_id, self._inputs(binding, x, params)))
                results = group.host.sample_batch(t, tuple(samples))
                result_index: int
                result_id: str
                outputs: Tuple[int | float, ...]
                for result_index, (result_id, outputs) in enumerate(results):
                    binding = due[result_index]
                    if result_id != binding.instance_id:
                        raise ValueError("IEEE/CIGRE sample response identity differs")
                    else:
                        self._publish(binding, outputs, params)
                        binding.next_sample_index += 1
            else:
                pass

    def close(self) -> None:
        """Close all workers even when one cooperative cleanup reports failure.

        :return: None.
        """
        if self._closed:
            pass
        else:
            first_error: BaseException | None = None
            group: _RuntimeWorkerGroup
            for group in self._groups:
                try:
                    group.host.close()
                except BaseException as ex:
                    if first_error is None:
                        first_error = ex
                    else:
                        pass
            self._closed = True
            if first_error is not None:
                raise RuntimeError("One IEEE/CIGRE worker could not close") from first_error
            else:
                pass
