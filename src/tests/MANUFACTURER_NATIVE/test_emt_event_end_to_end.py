# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
import struct
import subprocess
import sys
from pathlib import Path
from typing import Tuple, cast

import numpy as np
import pytest
from scipy.sparse import csc_matrix

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Dynamic.manufacturer_native_model import ManufacturerNativeModel
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    IeeeCigreDllPlatform,
    NativeModelInterface,
)
from VeraGridEngine.IO.manufacturer_native.importer import import_manufacturer_native_model
from VeraGridEngine.IO.manufacturer_native.model_info import ManufacturerNativeModelInfo
from VeraGridEngine.IO.manufacturer_native.model_info_codec import decode_manufacturer_native_model_info
from VeraGridEngine.IO.manufacturer_native.runtime_session import ManufacturerNativeRuntimeSession
from VeraGridEngine.IO.manufacturer_native.worker_artifact import prepare_manufacturer_native_runtime
from VeraGridEngine.IO.native_compiler.compiler_interface import NativeCompilerSelection, NativeCompilerToolset
from VeraGridEngine.IO.native_compiler.selected_interface import (
    load_saved_local_llvm_selection,
    resolve_native_compiler_toolset,
)
from VeraGridEngine.IO.native_runtime import NativeWorkerLimits
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import (
    EmtBoundaryUpdateProtocol,
    EmtProblemTemplate,
)
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import (
    JitAdSolver,
    SparseADJacobian,
)
from VeraGridEngine.Utils.procedural_logic import (
    BlockProceduralLogicUpdater,
    IeeeCigreDllSignalBinding,
    ManufacturerNativeControllerLogic,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var


class _IdentityJacobian:
    """Constant one-state Jacobian for the event-response test problem."""

    __slots__ = tuple()

    def __call__(
            self,
            states: np.ndarray,
            params: np.ndarray,
            history: np.ndarray,
            d_history: np.ndarray,
            h: float,
            history2: np.ndarray | None = None,
    ) -> csc_matrix:
        """Return the exact Jacobian of the one-state residual.

        :param states: Current Newton iterate.
        :param params: Full runtime parameter vector.
        :param history: Previous accepted state.
        :param d_history: Previous derivative state.
        :param h: Effective aligned step.
        :param history2: Optional second history state.
        :return: One-by-one identity matrix.
        """
        unused_values: Tuple[np.ndarray, np.ndarray, np.ndarray | None] = (
            states,
            d_history,
            history2,
        )
        if len(unused_values) == 0:
            raise RuntimeError("Unreachable Jacobian guard")
        else:
            time_constant: float = float(params[-1])
            if time_constant > 0.0:
                jacobian_value: float = (1.0 / h) + (1.0 / time_constant)
            else:
                jacobian_value = 1.0
            return csc_matrix([[jacobian_value]], dtype=np.float64)


def _native_output_residual(
        x_iter: np.ndarray,
        full_params: np.ndarray,
        x_prev: np.ndarray,
        dx_prev: np.ndarray,
        h: float,
        residual: np.ndarray,
        x_prev2: np.ndarray,
) -> None:
    """Drive the test network state from the first held native output.

    :param x_iter: Current Newton iterate.
    :param full_params: Runtime parameters with input first and output second.
    :param x_prev: Previous accepted state.
    :param dx_prev: Previous derivative state.
    :param h: Effective aligned step.
    :param residual: Mutable residual vector.
    :param x_prev2: Optional second history state.
    :return: None.
    """
    unused_values: Tuple[np.ndarray, np.ndarray] = (dx_prev, x_prev2)
    if len(unused_values) == 0:
        raise RuntimeError("Unreachable residual guard")
    else:
        time_constant: float = float(full_params[-1])
        if time_constant > 0.0:
            residual[0] = (
                (x_iter[0] - x_prev[0]) / h
                - (full_params[1] - x_iter[0]) / time_constant
            )
        else:
            residual[0] = x_iter[0] - full_params[1]


class _NativeEventProblem(EmtProblemTemplate):
    """Minimal EMT network bound to one real manufacturer-native runtime."""

    __slots__ = (
        "_x0",
        "_dx0",
        "_input_parameter_index",
        "_event_time",
        "_native_updater",
    )

    def __init__(
            self,
            provider: ManufacturerNativeModel,
            model_info: ManufacturerNativeModelInfo,
            response_time_constant: float,
            initial_state: float,
    ) -> None:
        """Build one state driven by the first held DLL output.

        :param provider: Qualified circuit-owned manufacturer provider.
        :param model_info: Canonical decoded manufacturer metadata.
        :param response_time_constant: First-order voltage time constant in seconds, or zero for direct coupling.
        :param initial_state: Initial terminal-voltage state in per unit.
        :return: None.
        """
        variable_factory: VarFactory = VarFactory()
        state_var: Var = variable_factory.add_var("terminal_voltage_magnitude")
        diff_var: Var = variable_factory.add_diff_var("network_state_dot", base_var=state_var)
        input_parameter: Var = Var("native_event_input")
        response_time_constant_parameter: Var = Var("voltage_response_time_constant")

        output_count: int = sum(signal.width for signal in model_info.output_ports)
        output_parameters: list[Var] = [
            Var("native_output_" + str(index)) for index in range(output_count)
        ]

        signal_bindings: list[IeeeCigreDllSignalBinding] = list()
        port_ordinal: int
        signal = None
        for port_ordinal, signal in enumerate(model_info.input_ports):
            element_ordinal: int
            for element_ordinal in range(signal.width):
                signal_bindings.append(IeeeCigreDllSignalBinding(
                    is_input=True,
                    port_ordinal=port_ordinal,
                    element_ordinal=element_ordinal,
                    variable=input_parameter,
                ))

        output_index: int = 0
        for port_ordinal, signal in enumerate(model_info.output_ports):
            for element_ordinal in range(signal.width):
                output_parameter: Var = output_parameters[output_index]
                signal_bindings.append(IeeeCigreDllSignalBinding(
                    is_input=False,
                    port_ordinal=port_ordinal,
                    element_ordinal=element_ordinal,
                    variable=output_parameter,
                ))
                output_index += 1

        controller_logic: ManufacturerNativeControllerLogic = ManufacturerNativeControllerLogic(
            provider_idtag=provider.idtag,
            model_info_sha256=provider.model_info_sha256,
            signal_bindings=tuple(signal_bindings),
            parameter_overrides=tuple(),
            name=model_info.model_name,
        )
        root_block: Block = Block(
            children=list(),
            in_vars=list(),
            procedural_logic=(controller_logic,),
            name="native-event-e2e",
        )
        root_block.state_vars = [state_var]
        root_block.algebraic_vars = list()
        root_block.diff_vars = [diff_var]
        root_block.state_eqs = [Const(0.0)]
        root_block.algebraic_eqs = list()
        root_block.parameters = {
            response_time_constant_parameter: Const(response_time_constant)
        }
        root_block.event_dict = {input_parameter: Const(1.0)}
        root_block.mode_dict = {
            output_parameter: Const(0.0) for output_parameter in output_parameters
        }

        global_time: Var = Var(self.TIME_NAME)
        super().__init__(
            sys_block=root_block,
            static_parameter_values_mapping=dict(),
            glob_time=global_time,
        )

        self._x0: np.ndarray = np.full(1, initial_state, dtype=np.float64)
        self._dx0: np.ndarray = np.zeros(1, dtype=np.float64)
        self._input_parameter_index: int = int(
            self.uid2idx_event_params[input_parameter.uid]
        )
        self._event_time: float = model_info.effective_sample_time

        runtime_session: ManufacturerNativeRuntimeSession = ManufacturerNativeRuntimeSession(
            providers=(provider,),
            platform=None,
            limits=NativeWorkerLimits(),
            logger=Logger(),
        )
        self._native_updater: BlockProceduralLogicUpdater = BlockProceduralLogicUpdater(
            problem=self,
            logic_entries=[controller_logic],
            runtime_session=runtime_session,
            model_mode=1,
        )

        first_output_index: int = int(
            self.uid2idx_event_params[output_parameters[0].uid]
        )
        if first_output_index != 1:
            raise RuntimeError("Native event test requires input/output runtime ordering")
        else:
            pass

    @property
    def boundary_update(self) -> EmtBoundaryUpdateProtocol | None:
        """Return the real manufacturer-native boundary updater.

        :return: Bound native updater.
        """
        return self._native_updater

    def get_x0(self) -> np.ndarray:
        """Return the deterministic initial network state.

        :return: Initial state vector.
        """
        return self._x0.copy()

    def get_dx0(self) -> np.ndarray:
        """Return the deterministic initial derivative.

        :return: Initial derivative vector.
        """
        return self._dx0.copy()

    def def_event_params_fn(
            self,
            ev_params: np.ndarray,
            t: float,
            defer_unavailable_dependencies: bool = False,
    ) -> np.ndarray:
        """Apply one input event while retaining native held outputs.

        :param ev_params: Previous runtime parameter values.
        :param t: Current aligned solver time.
        :param defer_unavailable_dependencies: Preserve values whose runtime
            dependencies are not available during problem construction.
        :return: Updated runtime parameter values.
        """
        updated_params: np.ndarray = super().def_event_params_fn(
            ev_params,
            t,
            defer_unavailable_dependencies=defer_unavailable_dependencies,
        )
        if defer_unavailable_dependencies:
            pass
        else:
            # Apply the user event only after the base constructor has built
            # the stable runtime-parameter indices used by the simulation.
            if t < self._event_time:
                updated_params[self._input_parameter_index] = 1.0
            else:
                updated_params[self._input_parameter_index] = 2.0
        return updated_params

    def get_newton_trace_collector(self) -> object | None:
        """Disable optional Newton diagnostics for the focused test.

        :return: None.
        """
        return None

    def close(self) -> None:
        """Release the isolated worker owned by this test problem.

        :return: None.
        """
        self._native_updater.close()


def _host_target() -> Tuple[IeeeCigreDllPlatform, str, Tuple[str, ...]]:
    """Return the supported host target for compiling a synthetic library.

    :return: Platform, extension and extra compiler arguments.
    """
    if struct.calcsize("P") != 8:
        pytest.skip("Manufacturer-native event evidence requires a 64-bit host")
    else:
        pass
    if os.name == "nt":
        return IeeeCigreDllPlatform.WINDOWS_X64, ".dll", tuple()
    else:
        if sys.platform.startswith("linux"):
            return IeeeCigreDllPlatform.LINUX_X64, ".so", ("-fPIC",)
        else:
            pytest.skip("Manufacturer-native execution is not supported on this host")


def _compile_fixture(
        source_path: Path,
        output_path: Path,
        defines: Tuple[str, ...],
        extra_arguments: Tuple[str, ...],
) -> None:
    """Compile one public synthetic manufacturer library.

    :param source_path: C fixture source.
    :param output_path: Destination library.
    :param defines: Required preprocessor definitions.
    :param extra_arguments: Host-specific compiler arguments.
    :return: None.
    """
    selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
    if selection is None:
        pytest.skip("External LLVM is not configured")
    else:
        toolset: NativeCompilerToolset = resolve_native_compiler_toolset(selection)
    arguments: list[str] = [
        str(toolset.compiler_path),
        *toolset.compiler_prefix_arguments,
        "-std=c11",
        "-O2",
        "-shared",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Wno-unused-command-line-argument",
    ]
    compiler_argument: str
    for compiler_argument in extra_arguments:
        arguments.append(compiler_argument)
    definition: str
    for definition in defines:
        arguments.append("-D" + definition + "=1")
    arguments.extend(["-o", str(output_path), str(source_path)])

    completed: subprocess.CompletedProcess[str] = subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    assert completed.returncode == 0, completed.stderr

class NativeEventValidationResult:
    """Retained numerical result from one native-contract EMT event run."""

    __slots__ = (
        "times",
        "states",
        "derivatives",
        "sample_time",
        "event_time",
        "response_time_constant",
        "aligned_substeps",
        "well_initialized",
        "converged",
    )

    def __init__(
            self,
            times: np.ndarray,
            states: np.ndarray,
            derivatives: np.ndarray,
            sample_time: float,
            event_time: float,
            response_time_constant: float,
            aligned_substeps: float,
            well_initialized: bool,
            converged: bool,
    ) -> None:
        """Store an immutable-size copy of the simulation evidence.

        :param times: Accepted simulation times in seconds.
        :param states: Accepted network-state trajectory.
        :param derivatives: Accepted state-derivative trajectory.
        :param sample_time: Native model sample period in seconds.
        :param event_time: Applied input-event time in seconds.
        :param response_time_constant: Terminal-voltage response time constant in seconds.
        :param aligned_substeps: Number of solver steps forced by alignment.
        :param well_initialized: Whether the EMT problem initialized correctly.
        :param converged: Whether every accepted solver step converged.
        :return: None.
        """
        self.times: np.ndarray = times.copy()
        self.states: np.ndarray = states.copy()
        self.derivatives: np.ndarray = derivatives.copy()
        self.sample_time: float = sample_time
        self.event_time: float = event_time
        self.response_time_constant: float = response_time_constant
        self.aligned_substeps: float = aligned_substeps
        self.well_initialized: bool = well_initialized
        self.converged: bool = converged

def run_native_contract_event_case(
        tmp_path: Path,
        fixture_directory: str,
        native_interface: NativeModelInterface,
        defines: Tuple[str, ...],
        solver_step_ratio: float,
        response_time_constant_ratio: float,
        initial_state: float,
        simulation_duration_ratio: float,
) -> NativeEventValidationResult:
    """Execute one real native-library event through the EMT solver.

    :param tmp_path: Private compilation directory.
    :param fixture_directory: Public fixture directory name.
    :param native_interface: Exact manufacturer ABI contract.
    :param defines: Fixture qualification definitions.
    :param solver_step_ratio: Solver step divided by the native sample period.
    :param response_time_constant_ratio: First-order time constant divided by the native sample period; zero preserves direct coupling.
    :param initial_state: Initial terminal-voltage magnitude in per unit.
    :param simulation_duration_ratio: Simulation duration divided by the native sample period.
    :return: Retained numerical evidence from the accepted trajectory.
    """
    if solver_step_ratio <= 0.0 or solver_step_ratio > 2.0:
        raise ValueError("solver_step_ratio must be in the interval (0, 2]")
    else:
        pass
    if response_time_constant_ratio < 0.0:
        raise ValueError("response_time_constant_ratio must not be negative")
    else:
        pass
    if simulation_duration_ratio < 2.0:
        raise ValueError("simulation_duration_ratio must be at least two")
    else:
        pass

    platform: IeeeCigreDllPlatform
    extension: str
    extra_arguments: Tuple[str, ...]
    platform, extension, extra_arguments = _host_target()

    # Runtime selection only resolves prepared artifacts; the event test owns this prerequisite.
    if load_saved_local_llvm_selection() is None:
        pytest.skip("External LLVM is not configured")
    else:
        prepare_manufacturer_native_runtime()

    fixture_root: Path = (
        Path(__file__).resolve().parents[1] / "data" / "manufacturer_native"
    )
    source_path: Path = fixture_root / fixture_directory / "fixture.c"
    binary_path: Path = tmp_path / ("event_model" + extension)
    _compile_fixture(
        source_path=source_path,
        output_path=binary_path,
        defines=defines,
        extra_arguments=extra_arguments,
    )

    grid: MultiCircuit = MultiCircuit()
    provider: ManufacturerNativeModel
    provider, _, _ = import_manufacturer_native_model(
        assets=grid,
        source_path=binary_path,
        platform=platform,
        native_interface=native_interface,
        vendor_declares_no_late_loading=True,
        vendor_declares_instance_isolation=True,
    )
    model_info: ManufacturerNativeModelInfo = decode_manufacturer_native_model_info(
        provider.model_info
    )
    response_time_constant: float = (
        response_time_constant_ratio * model_info.effective_sample_time
    )
    problem: _NativeEventProblem = _NativeEventProblem(
        provider=provider,
        model_info=model_info,
        response_time_constant=response_time_constant,
        initial_state=initial_state,
    )
    method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeBackEuler
    simulation_end: float = (
        simulation_duration_ratio * model_info.effective_sample_time
    )
    solver: JitAdSolver = JitAdSolver(
        problem=problem,
        t0=0.0,
        t_end=simulation_end,
        h=solver_step_ratio * model_info.effective_sample_time,
        method=method,
        dense_threshold=100,
        verbose=False,
    )
    solver.jit_kernels_ad[method] = [_native_output_residual]
    solver.jit_jacobian_ad[method] = cast(
        SparseADJacobian,
        _IdentityJacobian(),
    )

    try:
        times: np.ndarray
        states: np.ndarray
        derivatives: np.ndarray
        well_initialized: bool
        converged: bool
        times, states, derivatives, well_initialized, converged = solver.simulate()
    finally:
        problem.close()

    runtime_stats: dict[str, float] = solver.get_last_runtime_stats()
    return NativeEventValidationResult(
        times=times,
        states=states,
        derivatives=derivatives,
        sample_time=model_info.effective_sample_time,
        event_time=model_info.effective_sample_time,
        response_time_constant=response_time_constant,
        aligned_substeps=runtime_stats["aligned_substeps"],
        well_initialized=well_initialized,
        converged=converged,
    )




@pytest.mark.parametrize(
    (
        "fixture_directory",
        "native_interface",
        "defines",
        "expected_post_event_output",
    ),
    [
        (
            "linux_x64_v11",
            NativeModelInterface.IEEE_CIGRE_V1_1,
            ("QUALIFIED",),
            0.5,
        ),
        (
            "windows_x64_v10",
            NativeModelInterface.IEEE_CIGRE_V1_0,
            tuple(),
            6.0,
        ),
        (
            "windows_x64_iec_ese",
            NativeModelInterface.IEC_ESE,
            tuple(),
            5.0002,
        ),
    ],
    ids=("ieee-cigre-1.1", "ieee-cigre-1.0", "iec-ese"),
)
def test_native_contract_event_changes_emt_trajectory_end_to_end(
        tmp_path: Path,
        fixture_directory: str,
        native_interface: NativeModelInterface,
        defines: Tuple[str, ...],
        expected_post_event_output: float,
) -> None:
    """Run one real isolated DLL event through the EMT solver trajectory.

    :param tmp_path: Private compilation directory supplied by pytest.
    :param fixture_directory: Public fixture directory name.
    :param native_interface: Exact manufacturer ABI contract.
    :param defines: Fixture qualification definitions.
    :param expected_post_event_output: First held output after the input event.
    :return: None.
    """
    result: NativeEventValidationResult = run_native_contract_event_case(
        tmp_path=tmp_path,
        fixture_directory=fixture_directory,
        native_interface=native_interface,
        defines=defines,
        solver_step_ratio=2.0,
        response_time_constant_ratio=0.0,
        initial_state=0.0,
        simulation_duration_ratio=2.0,
    )
    replay: NativeEventValidationResult = run_native_contract_event_case(
        tmp_path=tmp_path,
        fixture_directory=fixture_directory,
        native_interface=native_interface,
        defines=defines,
        solver_step_ratio=2.0,
        response_time_constant_ratio=0.0,
        initial_state=0.0,
        simulation_duration_ratio=2.0,
    )
    assert result.well_initialized
    assert result.converged
    assert np.all(np.isfinite(result.states))
    assert np.all(np.isfinite(result.derivatives))
    assert np.isclose(result.times[-1], 2.0 * result.sample_time)
    assert np.isclose(result.states[-1, 0], expected_post_event_output)
    assert result.aligned_substeps == 1.0
    assert replay.well_initialized
    assert replay.converged
    assert np.array_equal(replay.times, result.times)
    assert np.array_equal(replay.states, result.states)
    assert np.array_equal(replay.derivatives, result.derivatives)
    assert replay.aligned_substeps == result.aligned_substeps
