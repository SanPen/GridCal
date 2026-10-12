from __future__ import annotations
from VeraGridEngine.enumerations import InterfaceType

import ast
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from VeraGridEngine.IO.fmu.interface import export_model_as_fmu
from VeraGridEngine.IO.fmu.CosimulationInterface.build import host_build_capable
from VeraGridEngine.IO.fmu.config import ExportConfig as CsExportConfig, detect_target_platform as detect_cs_target_platform
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.IO.fmu.Elements.bindings import (
    FmuBindingDirection,
    FmiThreeFloat64ConfigurationValue,
    FmiThreeUInt64ConfigurationValue,
    FmuFloat64ParameterValue,
    FmuImportConfig,
    FmuRefBinding,
    FmuVariableBinding,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    FmuCsDeviceConfigRecord,
    FmuMeDeviceConfigRecord,
    load_fmu_cs_device_config,
    load_fmu_me_device_config,
    restore_fmu_cs_spec_from_record,
    restore_fmu_me_spec_from_record,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import attach_rms_fmu_cs_device
from VeraGridEngine.IO.fmu.co_simulation import (
    FmuCsDeviceAdapter,
    FmuCsDeviceSpec,
    FmuCsDomain,
    build_fmu_cs_device_spec,
)
from VeraGridEngine.IO.fmu.model_exchange import (
    FmuMeDeviceAdapter,
    FmuMeDeviceSpec,
    FmuMeDomain,
    FmuMeSolverPolicy,
    RmsFmuMeDeviceAdapter,
    build_fmu_me_device_spec,
    get_next_rms_fmu_me_event_time,
    _prepare_rms_fmu_me_state_event_retry,
    resolve_rms_fmu_me_devices,
)
from VeraGridEngine.IO.fmu.model_description import (
    FmuInterfaceMode,
    read_fmu_model_description,
)
from VeraGridEngine.IO.fmu.Elements.description import (
    FmuModelDescription,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    append_fmu_parameter_entries,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    FmuDeviceAttachmentRequest,
    FmuDeviceDomain,
    FmuReferenceValue,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import attach_fmu_to_device
from VeraGridEngine.IO.fmu.worker_host import (
    FmiThreeWorkerHostLimits,
)
from VeraGridEngine.IO.fmu.profile import (
    FmuMeEvaluationBudget,
    FmiThreeWorkerFloat64Profile,
)
from VeraGridEngine.IO.fmu.config import ExportConfig as MeExportConfig, detect_target_platform as detect_me_target_platform
from VeraGridEngine.enumerations import (
    DeviceType,
    DynamicIntegrationMethod,
    VarPowerFlowReferenceType,
)
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory


class FakeGrid:
    __slots__ = ("var_factory",)

    def __init__(self) -> None:

        self.var_factory = VarFactory(name="UserApiVarFactory")


def _create_test_worker_limits() -> FmiThreeWorkerHostLimits:
    """Create the bounded worker policy shared by parameter API tests.

    :return: Explicit local-test supervision and protocol limits.
    """

    return FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )


def test_fmu_float64_parameter_value_rejects_invalid_source_data() -> None:
    """Reject empty identity, booleans, and non-finite parameter source data.

    :return: None.
    """

    with pytest.raises(ValueError, match="name is empty"):
        FmuFloat64ParameterValue(variable_name="   ", value=1.0)
    with pytest.raises(ValueError, match="real scalar"):
        FmuFloat64ParameterValue(variable_name="fixed_gain", value=True)
    with pytest.raises(ValueError, match="finite"):
        FmuFloat64ParameterValue(variable_name="fixed_gain", value=math.nan)


def test_attach_fmu_parameter_validation_rolls_back_before_device_mutation(
    compiled_fmi_three_parameterized_configurable_array_fmu: Path,
    tmp_path: Path,
) -> None:
    """Reject an unknown parameter without changing device-owned state.

    :param compiled_fmi_three_parameterized_configurable_array_fmu: Native
        dual-interface fixture with authoritative parameter metadata.
    :param tmp_path: Trusted extraction parent supplied by pytest.
    :return: None.
    """

    original_block: Block = Block()
    original_config: str = "preserve-existing-config"
    device: SimpleNamespace = SimpleNamespace(
        name="ParameterRollbackLoad",
        device_type=DeviceType.LoadDevice,
        rms_model=original_block,
        rms_fmu_import_config=original_config,
    )
    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=compiled_fmi_three_parameterized_configurable_array_fmu,
        domain=FmuDeviceDomain.RMS,
        mode=FmuInterfaceMode.CO_SIMULATION,
        input_bindings=tuple(),
        output_bindings=tuple(),
        extraction_root=tmp_path,
        worker_limits=_create_test_worker_limits(),
        configuration_uint64_values=(
            FmiThreeUInt64ConfigurationValue(
                variable_name="structural_size",
                value=2,
            ),
        ),
        parameter_values=(
            FmuFloat64ParameterValue(
                variable_name="not_a_declared_parameter",
                value=3.0,
            ),
        ),
    )
    with pytest.raises(ValueError, match="was not found"):
        attach_fmu_to_device(device, FakeGrid(), request)
    assert device.rms_model is original_block
    assert device.rms_fmu_import_config == original_config


def test_attach_fmu_parameter_binding_preserves_sanitized_block_identity(
    compiled_fmi_three_parameterized_configurable_array_fmu: Path,
) -> None:
    """Persist the actual collision-free Block name beside the FMU identity.

    :param compiled_fmi_three_parameterized_configurable_array_fmu: Native
        dual-interface fixture with scalar parameters.
    :return: None.
    """

    metadata: FmuModelDescription = read_fmu_model_description(
        compiled_fmi_three_parameterized_configurable_array_fmu
    )
    block: Block = Block()
    var_factory: VarFactory = VarFactory(name="ParameterIdentityFactory")
    parameter_bindings: tuple[FmuVariableBinding, ...] = (
        append_fmu_parameter_entries(
            block=block,
            vfactory=var_factory,
            metadata=metadata,
            used_names=set(("fixed_gain",)),
        )
    )
    fixed_gain_binding: FmuVariableBinding | None = None
    parameter_binding: FmuVariableBinding
    for parameter_binding in parameter_bindings:
        if parameter_binding.variable_name == "fixed_gain":
            fixed_gain_binding = parameter_binding
        else:
            pass
    if fixed_gain_binding is not None:
        pass
    else:
        raise AssertionError("The fixture fixed parameter was not mapped")
    assert fixed_gain_binding.direction == FmuBindingDirection.PARAMETER
    assert fixed_gain_binding.signal_name != fixed_gain_binding.variable_name
    parameter_names: tuple[str, ...] = tuple(
        parameter_var.name for parameter_var in block.parameters
    )
    assert fixed_gain_binding.signal_name in parameter_names


def _build_test_me_solver_policy() -> FmuMeSolverPolicy:
    """Build the consolidated Backward Euler policy used by FMI ME tests.

    :return: Valid solver policy with product defaults.
    """

    return FmuMeSolverPolicy(
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        absolute_tolerance=1.0e-8,
        relative_tolerance=1.0e-8,
        maximum_newton_iterations=20,
        maximum_continuous_states=128,
    )


def build_cs_output_block() -> Block:
    x = Var("x")
    dx = Var("dx", base_var=x)
    y = Var("y")
    return Block(
        state_vars=[x],
        state_eqs=[Const(1.0)],
        algebraic_vars=[y],
        algebraic_eqs=[y - x],
        diff_vars=[dx],
        init_values={x: Const(0.0), y: Const(0.0)},
        init_eqs={y: Const(0.0)},
        out_vars=[y],
    )


def build_me_output_block() -> Block:
    x = Var("x")
    dx = Var("dx", base_var=x)
    y = Var("y")
    u = Var("u")
    return Block(
        state_vars=[x],
        state_eqs=[Const(1.0) + u],
        algebraic_vars=[y],
        algebraic_eqs=[y - x],
        diff_vars=[dx],
        init_values={x: Const(0.0), y: Const(0.0)},
        init_eqs={y: Const(0.0)},
        in_vars=[u],
        out_vars=[y],
    )


def build_parameterized_output_block() -> Block:
    """Build one state model whose derivative is a scalar FMU parameter.

    :return: Exportable block with one fixed parameter and one output.
    """

    state_var: Var = Var("x")
    derivative_var: Var = Var("dx", base_var=state_var)
    output_var: Var = Var("y")
    gain_var: Var = Var("gain")
    return Block(
        state_vars=[state_var],
        state_eqs=[gain_var],
        algebraic_vars=[output_var],
        algebraic_eqs=[output_var - state_var],
        diff_vars=[derivative_var],
        parameters={gain_var: Const(2.0)},
        init_values={state_var: Const(0.0), output_var: Const(0.0)},
        init_eqs={output_var: Const(0.0)},
        out_vars=[output_var],
    )


@pytest.mark.skipif(
    not host_build_capable(),
    reason="No usable host build toolchain available",
)
def test_fmi_two_cs_and_me_parameters_are_initialize_only(tmp_path: Path) -> None:
    """Initialize FMI 2 CS/ME parameters once and retain their native values.

    :param tmp_path: Isolated build and archive directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    output_root: Path = tmp_path
    cs_fmu_path: Path = output_root / "fmi_two_parameter_initialize_only_cs.fmu"
    me_fmu_path: Path = output_root / "fmi_two_parameter_initialize_only_me.fmu"
    try:
        exported_cs_fmu: Path = export_model_as_fmu(
            build_parameterized_output_block(),
            CsExportConfig(
                model_name="FmiTwoParameterInitializeOnlyCs",
                output_path=cs_fmu_path,
                target_platform=detect_cs_target_platform(),
                compile_binary=True,
                keep_build_dir=False,
            ),
        )
        cs_parameter: FmuFloat64ParameterValue = FmuFloat64ParameterValue(
            variable_name="gain",
            value=4.0,
        )
        cs_spec: FmuCsDeviceSpec = build_fmu_cs_device_spec(
            domain=FmuCsDomain.RMS,
            config=FmuImportConfig(
                fmu_path=exported_cs_fmu,
                preferred_mode=FmuInterfaceMode.CO_SIMULATION,
                extraction_root=output_root,
            ),
            device_tpe=DeviceType.LoadDevice,
            input_bindings=tuple(),
            output_bindings=(
                FmuRefBinding(
                    reference=VarPowerFlowReferenceType.P,
                    fmu_variable_name="y",
                ),
            ),
            parameter_values=(cs_parameter,),
        )
        cs_adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
            problem=SimpleNamespace(),
            device=SimpleNamespace(),
            spec=cs_spec,
            output_param_indices=dict(),
        )
        try:
            cs_adapter.initialize_outputs(
                time_value=0.0,
                x_snapshot=np.zeros(0, dtype=float),
            )
            cs_parameter.value = 9.0
            cs_outputs: dict[VarPowerFlowReferenceType, float] = (
                cs_adapter.advance(
                    current_time=0.0,
                    step_size=0.25,
                    x_snapshot=np.zeros(0, dtype=float),
                )
            )
            assert cs_outputs[VarPowerFlowReferenceType.P] == pytest.approx(1.0)
        finally:
            cs_adapter.close()

        exported_me_fmu: Path = export_model_as_fmu(
            build_parameterized_output_block(),
            MeExportConfig(interface_type=InterfaceType.MODEL_EXCHANGE, 
                model_name="FmiTwoParameterInitializeOnlyMe",
                output_path=me_fmu_path,
                target_platform=detect_me_target_platform(),
                compile_binary=True,
                keep_build_dir=False,
            ),
        )
        me_parameter: FmuFloat64ParameterValue = FmuFloat64ParameterValue(
            variable_name="gain",
            value=4.0,
        )
        me_spec: FmuMeDeviceSpec = build_fmu_me_device_spec(
            domain=FmuMeDomain.RMS,
            config=FmuImportConfig(
                fmu_path=exported_me_fmu,
                preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
                extraction_root=output_root,
            ),
            device_tpe=DeviceType.LoadDevice,
            input_variable_names=tuple(),
            output_variable_names=("y",),
            output_bindings=(
                FmuRefBinding(
                    reference=VarPowerFlowReferenceType.P,
                    fmu_variable_name="y",
                ),
            ),
            parameter_values=(me_parameter,),
        )
        me_adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(
            me_spec,
            _build_test_me_solver_policy(),
        )
        try:
            me_adapter.initialize(start_time=0.0)
            me_parameter.value = 9.0
            derivative_values: np.ndarray = me_adapter.evaluate_derivatives(
                time_value=0.25,
                input_values=dict(),
            )
            assert derivative_values.tolist() == pytest.approx([4.0])
        finally:
            me_adapter.close()
    finally:
        cs_fmu_path.unlink(missing_ok=True)
        me_fmu_path.unlink(missing_ok=True)


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_user_api_attaches_rms_cs_device(tmp_path: Path) -> None:
    """Persist one public CS attachment request and its worker policy.

    :param tmp_path: Isolated build and archive directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")

    output_root: Path = tmp_path
    fmu_path = output_root / "user_api_rms_cs.fmu"
    try:
        exported_fmu = export_model_as_fmu(
            build_cs_output_block(),
            CsExportConfig(
                model_name="UserApiRmsCs",
                output_path=fmu_path,
                target_platform=detect_cs_target_platform(),
                compile_binary=True,
                keep_build_dir=False,
            ),
        )

        device: SimpleNamespace = SimpleNamespace(
            name="LoadA",
            device_type=DeviceType.LoadDevice,
            rms_model=Block(),
            rms_fmu_import_config="",
        )
        grid: FakeGrid = FakeGrid()
        worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
            maximum_frame_size=65536,
            maximum_float64_values_per_request=128,
            response_timeout_seconds=20.0,
            graceful_join_timeout_seconds=6.0,
            terminate_join_timeout_seconds=3.0,
            kill_join_timeout_seconds=1.0,
        )
        request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
            fmu_path=exported_fmu,
            domain=FmuDeviceDomain.RMS,
            mode=FmuInterfaceMode.CO_SIMULATION,
            input_bindings=tuple(),
            output_bindings=(
                FmuRefBinding(
                    reference=VarPowerFlowReferenceType.P,
                    fmu_variable_name="y",
                ),
            ),
            output_defaults=(FmuReferenceValue(reference=VarPowerFlowReferenceType.P, value=0.0),),
            worker_limits=worker_limits,
        )
        attach_fmu_to_device(device, grid, request)

        assert device.rms_fmu_import_config != ""
        restored_record: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
            device.rms_fmu_import_config
        )
        if restored_record is not None:
            restored_limits: FmiThreeWorkerHostLimits | None = (
                restored_record.worker_limits
            )
        else:
            raise AssertionError("Attached CS device config did not reload")
        if restored_limits is not None:
            assert restored_limits.maximum_frame_size == 65536
            assert restored_limits.maximum_float64_values_per_request == 128
        else:
            raise AssertionError("Attached CS device lost its worker limits")
        assert restored_record.output_bindings[0].flat_index is None
        assert restored_record.configuration_float64_values == tuple()
        assert restored_record.configuration_uint64_values == tuple()
    finally:
        fmu_path.unlink(missing_ok=True)


def test_user_api_persists_fmi_three_array_declarations(
    compiled_fmi_three_configurable_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Persist indexed bindings and structural values from a real FMI 3 FMU.

    :param compiled_fmi_three_configurable_array_co_simulation_fmu: Generated
        configurable-array FMI 3 fixture.
    :param tmp_path: Trusted extraction parent supplied by pytest.
    :return: None.
    """

    device: SimpleNamespace = SimpleNamespace(
        name="FmiThreeArrayLoad",
        device_type=DeviceType.LoadDevice,
        rms_model=Block(),
        rms_fmu_import_config="",
    )
    worker_limits: FmiThreeWorkerHostLimits = _create_test_worker_limits()
    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=compiled_fmi_three_configurable_array_co_simulation_fmu,
        domain=FmuDeviceDomain.RMS,
        mode=FmuInterfaceMode.CO_SIMULATION,
        input_bindings=tuple(),
        output_bindings=(
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.P,
                fmu_variable_name="array_output",
                flat_index=1,
            ),
        ),
        output_defaults=(
            FmuReferenceValue(
                reference=VarPowerFlowReferenceType.P,
                value=0.0,
            ),
        ),
        extraction_root=tmp_path,
        worker_limits=worker_limits,
        configuration_uint64_values=(
            FmiThreeUInt64ConfigurationValue(
                variable_name="structural_size",
                value=2,
            ),
        ),
    )
    attach_fmu_to_device(device, FakeGrid(), request)

    restored_record: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
        device.rms_fmu_import_config
    )
    if restored_record is not None:
        pass
    else:
        raise AssertionError("FMI 3 array attachment did not reload")
    assert restored_record.output_bindings[0].flat_index == 1
    assert restored_record.configuration_uint64_values[0].value == 2
    restored_spec: FmuCsDeviceSpec = restore_fmu_cs_spec_from_record(
        record=restored_record,
        block=device.rms_model,
        device_tpe=device.device_type,
    )
    assert (
        restored_spec.float64_profile
        == FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY
    )
    adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
        problem=SimpleNamespace(),
        device=device,
        spec=restored_spec,
        output_param_indices=dict(),
    )
    try:
        initial_outputs: dict[VarPowerFlowReferenceType, float] = (
            adapter.initialize_outputs(
                time_value=0.0,
                x_snapshot=np.zeros(0, dtype=float),
            )
        )
        assert initial_outputs[VarPowerFlowReferenceType.P] == pytest.approx(0.0)
        stepped_outputs: dict[VarPowerFlowReferenceType, float] = adapter.advance(
            current_time=0.0,
            step_size=0.25,
            x_snapshot=np.zeros(0, dtype=float),
        )
        assert stepped_outputs[VarPowerFlowReferenceType.P] == pytest.approx(
            0.35
        )
    finally:
        adapter.close()
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmu_device_attachment_preserves_existing_state_on_invalid_configuration(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Leave the destination untouched when provider validation fails.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated scalar FMI 3
        fixture.
    :param tmp_path: Trusted extraction parent supplied by pytest.
    :return: None.
    """

    original_model: Block = Block()
    device: SimpleNamespace = SimpleNamespace(
        name="AtomicFmiThreeLoad",
        device_type=DeviceType.LoadDevice,
        rms_model=original_model,
        rms_fmu_import_config="original-provider",
    )
    float64_configuration: FmiThreeFloat64ConfigurationValue = (
        FmiThreeFloat64ConfigurationValue(
            variable_name="structural_gain",
            values=(2.0,),
        )
    )
    worker_limits: FmiThreeWorkerHostLimits = _create_test_worker_limits()
    with pytest.raises(
        ValueError,
        match="Duplicate FMI 3 Configuration Mode variable name",
    ):
        attach_rms_fmu_cs_device(
            device=device,
            vfactory=FakeGrid().var_factory,
            config=FmuImportConfig(
                fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
                preferred_mode=FmuInterfaceMode.CO_SIMULATION,
                extraction_root=tmp_path,
            ),
            input_bindings=tuple(),
            output_bindings=tuple(),
            name="invalid-atomic-attachment",
            worker_limits=worker_limits,
            configuration_float64_values=(float64_configuration,),
            configuration_uint64_values=(
                FmiThreeUInt64ConfigurationValue(
                    variable_name="structural_gain",
                    value=2,
                ),
            ),
        )
    assert device.rms_model is original_model
    assert device.rms_fmu_import_config == "original-provider"

    accepted_bound: int
    for accepted_bound in (1, 1024):
        accepted_request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
            fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
            domain=FmuDeviceDomain.RMS,
            mode=FmuInterfaceMode.MODEL_EXCHANGE,
            input_bindings=tuple(),
            output_bindings=tuple(),
            maximum_event_iterations=accepted_bound,
        )
        assert accepted_request.maximum_event_iterations == accepted_bound

    rejected_bound: object
    for rejected_bound in (True, False, 0, 1025):
        with pytest.raises(ValueError, match="maximum Event Mode iterations"):
            FmuDeviceAttachmentRequest(
                fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
                domain=FmuDeviceDomain.RMS,
                mode=FmuInterfaceMode.MODEL_EXCHANGE,
                input_bindings=tuple(),
                output_bindings=tuple(),
                maximum_event_iterations=rejected_bound,
            )


def test_indexed_bindings_fail_before_any_runtime() -> None:
    """Reject indexed CS and ME bindings before FMI-version dispatch.

    :return: None.
    """

    indexed_binding: FmuRefBinding = FmuRefBinding(
        reference=VarPowerFlowReferenceType.P,
        fmu_variable_name="scalar_output",
        flat_index=0,
    )
    unopened_config: FmuImportConfig = FmuImportConfig(
        fmu_path="runtime-must-not-open.fmu",
    )
    cs_spec: FmuCsDeviceSpec = FmuCsDeviceSpec(
        domain=FmuCsDomain.RMS,
        config=unopened_config,
        device_tpe=DeviceType.LoadDevice,
        input_bindings=tuple(),
        output_bindings=(indexed_binding,),
        output_defaults=dict(),
        output_param_uids=dict(),
        worker_limits=None,
        float64_profile=None,
    )
    cs_adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=cs_spec,
        output_param_indices=dict(),
    )
    with pytest.raises(RuntimeError, match="indexed device bindings"):
        cs_adapter.initialize_outputs(
            time_value=0.0,
            x_snapshot=np.zeros(0, dtype=float),
        )

    fmi_two_configuration_spec: FmuCsDeviceSpec = FmuCsDeviceSpec(
        domain=FmuCsDomain.RMS,
        config=unopened_config,
        device_tpe=DeviceType.LoadDevice,
        input_bindings=tuple(),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_uids=dict(),
        worker_limits=None,
        float64_profile=None,
        configuration_float64_values=(
            FmiThreeFloat64ConfigurationValue(
                variable_name="structural_gain",
                values=(2.0,),
            ),
        ),
    )
    fmi_two_configuration_adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=fmi_two_configuration_spec,
        output_param_indices=dict(),
    )
    with pytest.raises(RuntimeError, match="require FMI 3"):
        fmi_two_configuration_adapter.initialize_outputs(
            time_value=0.0,
            x_snapshot=np.zeros(0, dtype=float),
        )

    me_spec: FmuMeDeviceSpec = FmuMeDeviceSpec(
        domain=FmuMeDomain.RMS,
        config=unopened_config,
        device_tpe=DeviceType.LoadDevice,
        input_variable_names=tuple(),
        output_variable_names=("scalar_output",),
        state_variable_names=tuple(),
        derivative_variable_names=tuple(),
        worker_limits=None,
        float64_profile=None,
        input_bindings=tuple(),
        output_bindings=(indexed_binding,),
        output_defaults=dict(),
        output_param_uids=dict(),
    )
    me_adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(
        me_spec,
        _build_test_me_solver_policy(),
    )
    with pytest.raises(RuntimeError, match="indexed device bindings"):
        me_adapter.initialize(start_time=0.0)


def test_fmi_three_cs_device_spec_owns_derived_worker_profile(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    compiled_fmi_three_constant_array_co_simulation_fmu: Path,
    compiled_fmi_three_configurable_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Restore one attached FMI 3 CS spec without opening its worker.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        native fixture.
    :param compiled_fmi_three_constant_array_co_simulation_fmu: Generated
        constant-array native fixture.
    :param compiled_fmi_three_configurable_array_co_simulation_fmu: Generated
        configurable-array native fixture.
    :param tmp_path: Trusted extraction parent supplied by pytest.
    :return: None.
    """

    worker_limits: FmiThreeWorkerHostLimits = _create_test_worker_limits()
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        preferred_mode=FmuInterfaceMode.CO_SIMULATION,
        extraction_root=tmp_path,
    )
    input_bindings: tuple[FmuRefBinding, ...] = (
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.Vm,
            fmu_variable_name="control_input",
        ),
    )
    output_bindings: tuple[FmuRefBinding, ...] = (
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.P,
            fmu_variable_name="observed_output",
        ),
    )
    with pytest.raises(ValueError, match="require explicit worker limits"):
        build_fmu_cs_device_spec(
            domain=FmuCsDomain.RMS,
            config=config,
            device_tpe=DeviceType.LoadDevice,
            input_bindings=input_bindings,
            output_bindings=output_bindings,
        )
    indexed_spec: FmuCsDeviceSpec = build_fmu_cs_device_spec(
        domain=FmuCsDomain.RMS,
        config=config,
        device_tpe=DeviceType.LoadDevice,
        input_bindings=tuple(),
        output_bindings=(
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.P,
                fmu_variable_name="observed_output",
                flat_index=0,
            ),
        ),
        worker_limits=worker_limits,
    )
    indexed_adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=indexed_spec,
        output_param_indices=dict(),
    )
    try:
        indexed_outputs: dict[VarPowerFlowReferenceType, float] = (
            indexed_adapter.initialize_outputs(
                time_value=0.0,
                x_snapshot=np.zeros(0, dtype=float),
            )
        )
        assert indexed_outputs[VarPowerFlowReferenceType.P] == pytest.approx(
            0.0
        )
    finally:
        indexed_adapter.close()

    with pytest.raises(RuntimeError, match="complete value provider"):
        build_fmu_cs_device_spec(
            domain=FmuCsDomain.RMS,
            config=FmuImportConfig(
                fmu_path=compiled_fmi_three_constant_array_co_simulation_fmu,
                preferred_mode=FmuInterfaceMode.CO_SIMULATION,
                extraction_root=tmp_path,
            ),
            device_tpe=DeviceType.LoadDevice,
            input_bindings=(
                FmuRefBinding(
                    reference=VarPowerFlowReferenceType.Vm,
                    fmu_variable_name="array_input",
                    flat_index=0,
                ),
            ),
            output_bindings=tuple(),
            worker_limits=worker_limits,
        )

    device: SimpleNamespace = SimpleNamespace(
        name="FmiThreeCsLoad",
        device_type=DeviceType.LoadDevice,
        rms_model=Block(),
        rms_fmu_import_config="",
    )
    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        domain=FmuDeviceDomain.RMS,
        mode=FmuInterfaceMode.CO_SIMULATION,
        input_bindings=input_bindings,
        output_bindings=output_bindings,
        output_defaults=(
            FmuReferenceValue(
                reference=VarPowerFlowReferenceType.P,
                value=0.0,
            ),
        ),
        extraction_root=tmp_path,
        worker_limits=worker_limits,
    )
    attach_fmu_to_device(device, FakeGrid(), request)

    restored_record: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
        device.rms_fmu_import_config
    )
    if restored_record is not None:
        restored_spec: FmuCsDeviceSpec = restore_fmu_cs_spec_from_record(
            record=restored_record,
            block=device.rms_model,
            device_tpe=device.device_type,
        )
    else:
        raise AssertionError("Attached FMI 3 CS device config did not reload")
    assert restored_spec.float64_profile == FmiThreeWorkerFloat64Profile.SCALAR
    assert restored_spec.worker_limits is not None
    assert restored_spec.worker_limits.maximum_frame_size == 262144

    constant_array_spec: FmuCsDeviceSpec = build_fmu_cs_device_spec(
        domain=FmuCsDomain.RMS,
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_constant_array_co_simulation_fmu,
            preferred_mode=FmuInterfaceMode.CO_SIMULATION,
            extraction_root=tmp_path,
        ),
        device_tpe=DeviceType.LoadDevice,
        input_bindings=tuple(),
        output_bindings=tuple(),
        worker_limits=worker_limits,
    )
    assert (
        constant_array_spec.float64_profile
        == FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY
    )
    constant_array_adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=constant_array_spec,
        output_param_indices=dict(),
    )
    try:
        constant_array_outputs: dict[VarPowerFlowReferenceType, float] = (
            constant_array_adapter.initialize_outputs(
                time_value=0.0,
                x_snapshot=np.zeros(0, dtype=float),
            )
        )
        assert constant_array_outputs == dict()
    finally:
        constant_array_adapter.close()
    assert constant_array_adapter.fmi_three_session is None
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()

    configurable_array_spec: FmuCsDeviceSpec = build_fmu_cs_device_spec(
        domain=FmuCsDomain.RMS,
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_configurable_array_co_simulation_fmu,
            preferred_mode=FmuInterfaceMode.CO_SIMULATION,
            extraction_root=tmp_path,
        ),
        device_tpe=DeviceType.LoadDevice,
        input_bindings=tuple(),
        output_bindings=tuple(),
        worker_limits=worker_limits,
    )
    assert (
        configurable_array_spec.float64_profile
        == FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY
    )


def test_fmi_three_cs_device_adapter_uses_isolated_session(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Run a scalar CS device lifecycle without native code in the parent.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :param tmp_path: Isolated worker staging parent supplied by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "cs-device-adapter-session"
    worker_limits: FmiThreeWorkerHostLimits = _create_test_worker_limits()
    input_binding: FmuRefBinding = FmuRefBinding(
        reference=VarPowerFlowReferenceType.Vm,
        fmu_variable_name="control_input",
    )
    output_binding: FmuRefBinding = FmuRefBinding(
        reference=VarPowerFlowReferenceType.P,
        fmu_variable_name="observed_output",
    )
    voltage_variable: Var = Var("device_voltage")
    bus_external_mapping: dict[VarPowerFlowReferenceType, Var] = dict()
    bus_external_mapping[VarPowerFlowReferenceType.Vm] = voltage_variable
    bus_block: Block = Block(external_mapping=bus_external_mapping)
    device: SimpleNamespace = SimpleNamespace(
        name="FmiThreeCsLifecycleLoad",
        device_type=DeviceType.LoadDevice,
        rms_model=Block(),
        rms_fmu_import_config="",
        bus=SimpleNamespace(rms_model=bus_block),
    )
    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        domain=FmuDeviceDomain.RMS,
        mode=FmuInterfaceMode.CO_SIMULATION,
        input_bindings=(input_binding,),
        output_bindings=(output_binding,),
        output_defaults=(
            FmuReferenceValue(
                reference=VarPowerFlowReferenceType.P,
                value=0.0,
            ),
        ),
        extraction_root=staging_parent,
        worker_limits=worker_limits,
    )
    attach_fmu_to_device(device, FakeGrid(), request)
    record: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
        device.rms_fmu_import_config
    )
    if record is not None:
        pass
    else:
        raise AssertionError("Attached FMI 3 CS device config did not reload")
    spec: FmuCsDeviceSpec = restore_fmu_cs_spec_from_record(
        record=record,
        block=device.rms_model,
        device_tpe=device.device_type,
    )
    assert spec.float64_profile == FmiThreeWorkerFloat64Profile.SCALAR
    assert spec.worker_limits is not None
    assert spec.worker_limits.maximum_frame_size == 262144

    variable_indices: dict[int, int] = dict()
    variable_indices[voltage_variable.uid] = 0
    problem: SimpleNamespace = SimpleNamespace(uid2idx_vars=variable_indices)
    output_param_indices: dict[VarPowerFlowReferenceType, int] = dict()
    output_param_indices[VarPowerFlowReferenceType.P] = 0
    adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
        problem=problem,
        device=device,
        spec=spec,
        output_param_indices=output_param_indices,
    )

    try:
        initial_outputs: dict[VarPowerFlowReferenceType, float] = (
            adapter.initialize_outputs(
                time_value=0.0,
                x_snapshot=np.array((2.0,), dtype=float),
            )
        )
        assert adapter.runtime_host is None
        assert adapter.fmi_three_session is not None
        assert initial_outputs[VarPowerFlowReferenceType.P] == pytest.approx(0.0)

        stepped_outputs: dict[VarPowerFlowReferenceType, float] = adapter.advance(
            current_time=0.0,
            step_size=0.25,
            x_snapshot=np.array((2.0,), dtype=float),
        )
        assert adapter.last_time == pytest.approx(0.25)
        assert stepped_outputs[VarPowerFlowReferenceType.P] == pytest.approx(2.25)
        target: np.ndarray = np.zeros(1, dtype=float)
        adapter.apply_outputs(target, stepped_outputs)
        assert target.tolist() == pytest.approx([2.25])

        with pytest.raises(RuntimeError, match="requested simulation termination"):
            adapter.advance(
                current_time=0.25,
                step_size=0.25,
                x_snapshot=np.array((9.0,), dtype=float),
            )
        assert adapter.last_time == pytest.approx(0.5)
        assert adapter.last_outputs[VarPowerFlowReferenceType.P] == pytest.approx(
            9.5
        )
    finally:
        adapter.close()
        adapter.close()

    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_me_selects_constant_array_device_outputs(
    compiled_fmi_three_constant_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Evaluate two selected elements from one constant ME output array.

    :param compiled_fmi_three_constant_array_co_simulation_fmu: Generated
        dual-interface constant-array FMI 3 fixture.
    :param tmp_path: Trusted extraction parent supplied by pytest.
    :return: None.
    """

    worker_limits: FmiThreeWorkerHostLimits = _create_test_worker_limits()
    output_bindings: tuple[FmuRefBinding, ...] = (
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.P,
            fmu_variable_name="array_output",
            flat_index=5,
        ),
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.Q,
            fmu_variable_name="array_output",
            flat_index=2,
        ),
    )
    spec: FmuMeDeviceSpec = build_fmu_me_device_spec(
        domain=FmuMeDomain.RMS,
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_constant_array_co_simulation_fmu,
            preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
            extraction_root=tmp_path / "me-constant-array-session",
        ),
        device_tpe=DeviceType.LoadDevice,
        input_variable_names=tuple(),
        output_variable_names=("array_output", "array_output"),
        worker_limits=worker_limits,
        output_bindings=output_bindings,
    )
    assert spec.float64_profile == FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY
    adapter: RmsFmuMeDeviceAdapter = RmsFmuMeDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=spec,
        solver_policy=_build_test_me_solver_policy(),
        output_param_indices={
            VarPowerFlowReferenceType.P: 0,
            VarPowerFlowReferenceType.Q: 1,
        },
    )
    second_adapter: RmsFmuMeDeviceAdapter = RmsFmuMeDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=spec,
        solver_policy=_build_test_me_solver_policy(),
        output_param_indices={
            VarPowerFlowReferenceType.P: 2,
            VarPowerFlowReferenceType.Q: 3,
        },
    )
    initialization_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(
        maximum_operations=100000
    )
    step_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(
        maximum_operations=100000
    )
    try:
        initial_outputs: dict[VarPowerFlowReferenceType, float] = (
            adapter.initialize_outputs(
                time_value=0.5,
                x_snapshot=np.zeros(0, dtype=float),
                evaluation_budget=initialization_budget,
            )
        )
        assert initial_outputs[VarPowerFlowReferenceType.P] == pytest.approx(2.6)
        assert initial_outputs[VarPowerFlowReferenceType.Q] == pytest.approx(1.5)
        second_adapter.initialize_outputs(
            time_value=0.5,
            x_snapshot=np.zeros(0, dtype=float),
            evaluation_budget=initialization_budget,
        )
        stepped_outputs: dict[VarPowerFlowReferenceType, float] = adapter.advance(
            current_time=0.5,
            step_size=0.25,
            x_snapshot=np.zeros(0, dtype=float),
            evaluation_budget=step_budget,
        )
        assert stepped_outputs[VarPowerFlowReferenceType.P] == pytest.approx(2.85)
        assert stepped_outputs[VarPowerFlowReferenceType.Q] == pytest.approx(1.75)
        second_adapter.advance(
            current_time=0.5,
            step_size=0.25,
            x_snapshot=np.zeros(0, dtype=float),
            evaluation_budget=step_budget,
        )
        problem: SimpleNamespace = SimpleNamespace(
            _fmu_me_adapters=[adapter, second_adapter],
            _variable_parameters_values=np.zeros(4, dtype=float),
            _last_variable_parameters_values=None,
            _fmu_me_evaluation_budget=step_budget,
        )
        resolve_rms_fmu_me_devices(problem=problem, accepted=True)
        assert problem._variable_parameters_values.tolist() == pytest.approx(
            [2.85, 1.75, 2.85, 1.75]
        )
        assert adapter.runtime_adapter.fmi_three_coordinator is not None
        assert not adapter.runtime_adapter.fmi_three_coordinator.has_pending_candidate()
        assert second_adapter.runtime_adapter.fmi_three_coordinator is not None
        assert not second_adapter.runtime_adapter.fmi_three_coordinator.has_pending_candidate()
    finally:
        adapter.close()
        adapter.close()
        second_adapter.close()
        second_adapter.close()


def test_fmi_three_me_selects_configurable_array_device_outputs(
    compiled_fmi_three_configurable_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Restore and evaluate selected ME array elements in binding order.

    :param compiled_fmi_three_configurable_array_co_simulation_fmu: Generated
        dual-interface configurable-array FMI 3 fixture.
    :param tmp_path: Trusted extraction parent supplied by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "me-configurable-array-session"
    worker_limits: FmiThreeWorkerHostLimits = _create_test_worker_limits()
    device: SimpleNamespace = SimpleNamespace(
        name="FmiThreeMeArrayLoad",
        device_type=DeviceType.LoadDevice,
        rms_model=Block(),
        rms_fmu_me_import_config="",
    )
    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=compiled_fmi_three_configurable_array_co_simulation_fmu,
        domain=FmuDeviceDomain.RMS,
        mode=FmuInterfaceMode.MODEL_EXCHANGE,
        input_bindings=tuple(),
        output_bindings=(
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.P,
                fmu_variable_name="array_output",
                flat_index=1,
            ),
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.Q,
                fmu_variable_name="array_output",
                flat_index=0,
            ),
        ),
        output_defaults=(
            FmuReferenceValue(
                reference=VarPowerFlowReferenceType.P,
                value=0.0,
            ),
            FmuReferenceValue(
                reference=VarPowerFlowReferenceType.Q,
                value=0.0,
            ),
        ),
        extraction_root=staging_parent,
        worker_limits=worker_limits,
        configuration_uint64_values=(
            FmiThreeUInt64ConfigurationValue(
                variable_name="structural_size",
                value=2,
            ),
        ),
    )
    attach_fmu_to_device(device, FakeGrid(), request)
    record: FmuMeDeviceConfigRecord | None = load_fmu_me_device_config(
        device.rms_fmu_me_import_config
    )
    if record is not None:
        pass
    else:
        raise AssertionError("Attached FMI 3 ME array config did not reload")
    spec: FmuMeDeviceSpec = restore_fmu_me_spec_from_record(
        record=record,
        block=device.rms_model,
        device_tpe=device.device_type,
    )
    assert spec.output_bindings == record.output_bindings
    assert spec.configuration_uint64_values[0].value == 2

    adapter: RmsFmuMeDeviceAdapter = RmsFmuMeDeviceAdapter(
        problem=SimpleNamespace(),
        device=device,
        spec=spec,
        solver_policy=_build_test_me_solver_policy(),
        output_param_indices=dict(),
    )
    initialization_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(
        maximum_operations=100000
    )
    step_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(
        maximum_operations=100000
    )
    try:
        initial_outputs: dict[VarPowerFlowReferenceType, float] = (
            adapter.initialize_outputs(
                time_value=0.25,
                x_snapshot=np.zeros(0, dtype=float),
                evaluation_budget=initialization_budget,
            )
        )
        assert initial_outputs[VarPowerFlowReferenceType.P] == pytest.approx(0.35)
        assert initial_outputs[VarPowerFlowReferenceType.Q] == pytest.approx(0.25)
        stepped_outputs: dict[VarPowerFlowReferenceType, float] = adapter.advance(
            current_time=0.25,
            step_size=0.25,
            x_snapshot=np.zeros(0, dtype=float),
            evaluation_budget=step_budget,
        )
        assert stepped_outputs[VarPowerFlowReferenceType.P] == pytest.approx(0.6)
        assert stepped_outputs[VarPowerFlowReferenceType.Q] == pytest.approx(0.5)
        resolved_outputs: dict[VarPowerFlowReferenceType, float] = (
            adapter.resolve_step(
                accepted=True,
                evaluation_budget=step_budget,
            )
        )
        assert resolved_outputs[VarPowerFlowReferenceType.P] == pytest.approx(0.6)
        assert resolved_outputs[VarPowerFlowReferenceType.Q] == pytest.approx(0.5)
        assert adapter.runtime_adapter.get_state_vector().size == 0
    finally:
        adapter.close()
        adapter.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_user_api_attaches_emt_me_device(tmp_path: Path) -> None:
    """Persist one public EMT ME attachment request.

    :param tmp_path: Isolated build and archive directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")

    output_root: Path = tmp_path
    fmu_path = output_root / "user_api_emt_me.fmu"
    try:
        exported_fmu = export_model_as_fmu(
            build_me_output_block(),
            MeExportConfig(interface_type=InterfaceType.MODEL_EXCHANGE, 
                model_name="UserApiEmtMe",
                output_path=fmu_path,
                target_platform=detect_me_target_platform(),
                compile_binary=True,
                keep_build_dir=False,
            ),
        )

        device = SimpleNamespace(name="LoadB", device_type=DeviceType.LoadDevice, emt_model=Block(), emt_fmu_me_import_config="")
        grid = FakeGrid()
        worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
            maximum_frame_size=65536,
            maximum_float64_values_per_request=128,
            response_timeout_seconds=20.0,
            graceful_join_timeout_seconds=6.0,
            terminate_join_timeout_seconds=3.0,
            kill_join_timeout_seconds=1.0,
        )
        request = FmuDeviceAttachmentRequest(
            fmu_path=exported_fmu,
            domain=FmuDeviceDomain.EMT,
            mode=FmuInterfaceMode.MODEL_EXCHANGE,
            input_bindings=tuple(),
            output_bindings=(FmuRefBinding(reference=VarPowerFlowReferenceType.i_A, fmu_variable_name="y"),),
            output_defaults=(FmuReferenceValue(reference=VarPowerFlowReferenceType.i_A, value=0.0),),
            worker_limits=worker_limits,
            maximum_event_iterations=19,
        )
        attach_fmu_to_device(device, grid, request)

        assert device.emt_fmu_me_import_config != ""
        restored_record: FmuMeDeviceConfigRecord | None = load_fmu_me_device_config(
            device.emt_fmu_me_import_config
        )
        if restored_record is not None:
            restored_limits: FmiThreeWorkerHostLimits | None = (
                restored_record.worker_limits
            )
        else:
            raise AssertionError("Attached ME device config did not reload")
        if restored_limits is not None:
            assert restored_limits.maximum_frame_size == 65536
            assert restored_limits.maximum_float64_values_per_request == 128
            assert restored_limits.response_timeout_seconds == 20.0
            assert restored_limits.graceful_join_timeout_seconds == 6.0
            assert restored_limits.terminate_join_timeout_seconds == 3.0
            assert restored_limits.kill_join_timeout_seconds == 1.0
        else:
            raise AssertionError("Attached ME device lost its FMI 3 worker limits")
        assert restored_record.maximum_event_iterations == 19
        restored_spec: FmuMeDeviceSpec = restore_fmu_me_spec_from_record(
            record=restored_record,
            block=device.emt_model,
            device_tpe=device.device_type,
        )
        runtime_adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(restored_spec, _build_test_me_solver_policy())
        step_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(
            maximum_operations=100000
        )
        try:
            runtime_adapter.initialize(start_time=0.0, input_values=dict())
            candidate_outputs: dict[VarPowerFlowReferenceType, float] = (
                runtime_adapter._prepare_bound_step(
                    current_time=0.0,
                    step_size=1.0,
                    input_values=dict(),
                    evaluation_budget=step_budget,
                )
            )
            assert candidate_outputs[VarPowerFlowReferenceType.i_A] == pytest.approx(
                1.0
            )
            assert runtime_adapter.get_state_vector().tolist() == pytest.approx(
                [1.0]
            )
            accepted_values: tuple[float, ...] | None = (
                runtime_adapter.resolve_pending_step(
                    accepted=True,
                    evaluation_budget=step_budget,
                )
            )
            assert accepted_values == pytest.approx((1.0,), abs=1.0e-9)
            assert runtime_adapter.get_state_vector().tolist() == pytest.approx(
                [1.0]
            )
        finally:
            runtime_adapter.close()
    finally:
        fmu_path.unlink(missing_ok=True)


def test_fmi_three_me_device_spec_owns_derived_worker_profile(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    compiled_fmi_three_constant_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Build one FMI 3 ME device spec without opening its isolated worker.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        native fixture.
    :param compiled_fmi_three_constant_array_co_simulation_fmu: Generated
        constant-array dual-interface fixture.
    :param tmp_path: Isolated future staging parent provided by pytest.
    :return: None.
    """

    worker_limits: FmiThreeWorkerHostLimits = _create_test_worker_limits()
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
        extraction_root=tmp_path,
    )
    with pytest.raises(ValueError, match="require explicit worker limits"):
        build_fmu_me_device_spec(
            domain=FmuMeDomain.RMS,
            config=config,
            device_tpe=DeviceType.LoadDevice,
            input_variable_names=("control_input",),
            output_variable_names=("observed_output",),
        )
    output_binding: FmuRefBinding = FmuRefBinding(
        reference=VarPowerFlowReferenceType.P,
        fmu_variable_name="observed_output",
        flat_index=0,
    )
    spec: FmuMeDeviceSpec = build_fmu_me_device_spec(
        domain=FmuMeDomain.RMS,
        config=config,
        device_tpe=DeviceType.LoadDevice,
        input_variable_names=("control_input",),
        output_variable_names=("observed_output",),
        worker_limits=worker_limits,
        output_bindings=(output_binding,),
    )

    assert spec.float64_profile == FmiThreeWorkerFloat64Profile.SCALAR
    assert spec.worker_limits is worker_limits
    assert spec.state_variable_names == ("continuous_state",)
    assert spec.derivative_variable_names == ("state_derivative",)
    assert spec.output_bindings == (output_binding,)
    assert spec.maximum_event_iterations == 32

    accepted_event_bound: int
    for accepted_event_bound in (1, 1024):
        accepted_spec: FmuMeDeviceSpec = build_fmu_me_device_spec(
            domain=FmuMeDomain.RMS,
            config=config,
            device_tpe=DeviceType.LoadDevice,
            input_variable_names=("control_input",),
            output_variable_names=("observed_output",),
            worker_limits=worker_limits,
            maximum_event_iterations=accepted_event_bound,
        )
        assert accepted_spec.maximum_event_iterations == accepted_event_bound

    rejected_event_bound: object
    for rejected_event_bound in (True, False, 0, 1025):
        with pytest.raises(ValueError, match="maximum Event Mode iterations"):
            build_fmu_me_device_spec(
                domain=FmuMeDomain.RMS,
                config=config,
                device_tpe=DeviceType.LoadDevice,
                input_variable_names=("control_input",),
                output_variable_names=("observed_output",),
                worker_limits=worker_limits,
                maximum_event_iterations=rejected_event_bound,
            )

    with pytest.raises(RuntimeError, match="array inputs require a complete"):
        build_fmu_me_device_spec(
            domain=FmuMeDomain.RMS,
            config=FmuImportConfig(
                fmu_path=compiled_fmi_three_constant_array_co_simulation_fmu,
                preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
                extraction_root=tmp_path / "rejected-me-array-input",
            ),
            device_tpe=DeviceType.LoadDevice,
            input_variable_names=("array_input",),
            output_variable_names=("array_output",),
            worker_limits=worker_limits,
            output_bindings=(
                FmuRefBinding(
                    reference=VarPowerFlowReferenceType.P,
                    fmu_variable_name="array_output",
                    flat_index=0,
                ),
            ),
        )


def test_fmi_three_me_device_adapter_uses_isolated_session(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Evaluate one FMI 3 ME device without loading native code in the parent.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "device-adapter-session"
    worker_limits: FmiThreeWorkerHostLimits = _create_test_worker_limits()
    device: SimpleNamespace = SimpleNamespace(
        name="FmiThreeLoad",
        device_type=DeviceType.LoadDevice,
        rms_model=Block(),
        rms_fmu_me_import_config="",
    )
    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        domain=FmuDeviceDomain.RMS,
        mode=FmuInterfaceMode.MODEL_EXCHANGE,
        input_bindings=(
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.Vm,
                fmu_variable_name="control_input",
            ),
        ),
        output_bindings=(
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.P,
                fmu_variable_name="observed_output",
            ),
        ),
        output_defaults=(
            FmuReferenceValue(
                reference=VarPowerFlowReferenceType.P,
                value=0.0,
            ),
        ),
        extraction_root=staging_parent,
        worker_limits=worker_limits,
        maximum_event_iterations=11,
        configuration_float64_values=(
            FmiThreeFloat64ConfigurationValue(
                variable_name="structural_gain",
                values=(2.0,),
            ),
        ),
    )
    attach_fmu_to_device(device, FakeGrid(), request)
    record: FmuMeDeviceConfigRecord | None = load_fmu_me_device_config(
        device.rms_fmu_me_import_config
    )
    if record is not None:
        pass
    else:
        raise AssertionError("Attached FMI 3 ME device config did not reload")
    spec: FmuMeDeviceSpec = restore_fmu_me_spec_from_record(
        record=record,
        block=device.rms_model,
        device_tpe=device.device_type,
    )
    assert spec.float64_profile == FmiThreeWorkerFloat64Profile.SCALAR
    assert spec.worker_limits is not None
    assert spec.worker_limits.maximum_frame_size == 262144
    assert spec.maximum_event_iterations == 11
    assert spec.configuration_float64_values[0].values == (2.0,)
    adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(spec, _build_test_me_solver_policy())
    with pytest.raises(ValueError, match="unbound input"):
        adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=2.0),
            start_values=dict(unbound_parameter=1.0),
        )
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


    try:
        adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=2.0),
        )
        assert adapter.runtime_host is None
        assert adapter.fmi_three_coordinator is not None
        assert adapter.get_state_vector().tolist() == pytest.approx([1.0])
        derivative_values: list[float] = adapter.evaluate_derivatives(
            time_value=0.25,
            input_values=dict(control_input=2.0),
        ).tolist()
        assert derivative_values == pytest.approx([1.0])
        output_values: dict[str, float] = adapter.evaluate_outputs(
            time_value=0.25,
            input_values=dict(control_input=2.0),
        )
        assert output_values == pytest.approx(dict(observed_output=0.0))
        step_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(
            maximum_operations=100000
        )
        prepared_outputs: dict[VarPowerFlowReferenceType, float] = (
            adapter._prepare_bound_step(
                current_time=0.0,
                step_size=0.25,
                input_values=dict(control_input=2.0),
                evaluation_budget=step_budget,
            )
        )
        assert prepared_outputs == pytest.approx(
            {VarPowerFlowReferenceType.P: 0.0}
        )
        assert adapter.fmi_three_coordinator.has_pending_candidate()
        assert adapter.get_state_vector().tolist() == pytest.approx([1.2])
        rejected_values: tuple[float, ...] | None = (
            adapter.resolve_pending_step(
                accepted=False,
                evaluation_budget=step_budget,
            )
        )
        assert rejected_values == pytest.approx((0.0,))
        assert not adapter.fmi_three_coordinator.has_pending_candidate()
        assert adapter.get_state_vector().tolist() == pytest.approx([1.0])
        stepped_outputs: dict[str, float] = adapter.prepare_step(
            current_time=0.0,
            step_size=0.25,
            input_values=dict(control_input=2.0),
        )
        assert adapter.get_state_vector().tolist() == pytest.approx([1.2])
        assert stepped_outputs == pytest.approx(dict(observed_output=0.0))
        assert not adapter.fmi_three_coordinator.has_pending_candidate()
    finally:
        adapter.close()
        adapter.close()

    direct_state_event_adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(spec, _build_test_me_solver_policy())
    try:
        direct_state_event_adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=5.0),
        )
        with pytest.raises(
            RuntimeError,
            match="solver-owned localization path",
        ):
            direct_state_event_adapter.prepare_step(
                current_time=0.0,
                step_size=1.0,
                input_values=dict(control_input=5.0),
            )
        assert direct_state_event_adapter.get_state_vector().tolist() == pytest.approx(
            [1.0]
        )
        assert not direct_state_event_adapter.fmi_three_coordinator.has_pending_candidate()
    finally:
        direct_state_event_adapter.close()

    time_event_adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(spec, _build_test_me_solver_policy())
    try:
        time_event_adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=7.0),
        )
        assert time_event_adapter.get_next_event_time() == pytest.approx(0.25)
        time_event_problem: SimpleNamespace = SimpleNamespace(
            _fmu_me_adapters=[
                SimpleNamespace(runtime_adapter=time_event_adapter)
            ]
        )
        assert get_next_rms_fmu_me_event_time(
            problem=time_event_problem,
            t_prev=0.0,
            t_target=0.5,
        ) == pytest.approx(0.25)
        time_event_adapter.prepare_step(
            current_time=0.0,
            step_size=0.25,
            input_values=dict(control_input=7.0),
        )
        assert time_event_adapter.get_next_event_time() is None
        assert time_event_adapter.get_state_vector().tolist() == pytest.approx(
            [2.2]
        )
    finally:
        time_event_adapter.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_me_state_events_use_global_earliest_retry(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Localize three crossings, group simultaneous roots, and retry the first.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        native fixture with one continuous state and one event indicator.
    :param tmp_path: Isolated worker staging parent provided by pytest.
    :return: None.
    """

    worker_limits: FmiThreeWorkerHostLimits = _create_test_worker_limits()
    output_binding: FmuRefBinding = FmuRefBinding(
        reference=VarPowerFlowReferenceType.P,
        fmu_variable_name="observed_output",
    )
    spec: FmuMeDeviceSpec = build_fmu_me_device_spec(
        domain=FmuMeDomain.RMS,
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
            preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
            extraction_root=tmp_path / "state-event-global-retry",
        ),
        device_tpe=DeviceType.LoadDevice,
        input_variable_names=("control_input",),
        output_variable_names=("observed_output",),
        worker_limits=worker_limits,
        output_bindings=(output_binding,),
    )
    first_output_indices: dict[VarPowerFlowReferenceType, int] = dict()
    first_output_indices[VarPowerFlowReferenceType.P] = 0
    second_output_indices: dict[VarPowerFlowReferenceType, int] = dict()
    second_output_indices[VarPowerFlowReferenceType.P] = 1
    third_output_indices: dict[VarPowerFlowReferenceType, int] = dict()
    third_output_indices[VarPowerFlowReferenceType.P] = 2
    first_wrapper: RmsFmuMeDeviceAdapter = RmsFmuMeDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=spec,
        solver_policy=_build_test_me_solver_policy(),
        output_param_indices=first_output_indices,
    )
    second_wrapper: RmsFmuMeDeviceAdapter = RmsFmuMeDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=spec,
        solver_policy=_build_test_me_solver_policy(),
        output_param_indices=second_output_indices,
    )
    third_wrapper: RmsFmuMeDeviceAdapter = RmsFmuMeDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(),
        spec=spec,
        solver_policy=_build_test_me_solver_policy(),
        output_param_indices=third_output_indices,
    )
    problem: SimpleNamespace = SimpleNamespace(
        _fmu_me_adapters=[first_wrapper, second_wrapper, third_wrapper],
        _variable_parameters_values=np.zeros(3, dtype=float),
        _last_variable_parameters_values=None,
        _fmu_me_evaluation_budget=FmuMeEvaluationBudget(
            maximum_operations=100000
        ),
    )

    try:
        first_wrapper.runtime_adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=5.0),
        )
        assert first_wrapper.runtime_adapter.fmi_three_coordinator.supports_rollback()
        second_wrapper.runtime_adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=5.000000001),
        )
        third_wrapper.runtime_adapter.initialize(
            start_time=0.0,
            input_values=dict(control_input=4.5),
        )
        first_wrapper.last_outputs = (
            first_wrapper.runtime_adapter._prepare_bound_step(
                current_time=0.0,
                step_size=1.0,
                input_values=dict(control_input=5.0),
                evaluation_budget=problem._fmu_me_evaluation_budget,
            )
        )
        second_wrapper.last_outputs = (
            second_wrapper.runtime_adapter._prepare_bound_step(
                current_time=0.0,
                step_size=1.0,
                input_values=dict(control_input=5.000000001),
                evaluation_budget=problem._fmu_me_evaluation_budget,
            )
        )
        third_wrapper.last_outputs = (
            third_wrapper.runtime_adapter._prepare_bound_step(
                current_time=0.0,
                step_size=1.0,
                input_values=dict(control_input=4.5),
                evaluation_budget=problem._fmu_me_evaluation_budget,
            )
        )

        with pytest.raises(
            RuntimeError,
            match="localization bound cannot meet its tolerance",
        ):
            first_wrapper.runtime_adapter.get_pending_state_event_time(
                time_tolerance=1.0e-12,
                maximum_iterations=1,
                evaluation_budget=problem._fmu_me_evaluation_budget,
            )

        retry_time: float | None = _prepare_rms_fmu_me_state_event_retry(
            problem=problem,
            state_event_time_tolerance=1.0e-9,
            state_event_max_iterations=40,
        )
        assert retry_time == pytest.approx(0.6, abs=1.0e-9)
        assert first_wrapper.runtime_adapter.get_next_event_time() == pytest.approx(
            0.6,
            abs=1.0e-9,
        )
        assert second_wrapper.runtime_adapter.get_next_event_time() == pytest.approx(
            float(retry_time),
            abs=1.0e-12,
        )
        assert third_wrapper.runtime_adapter.get_next_event_time() is None
        assert first_wrapper.runtime_adapter.get_state_vector().tolist() == pytest.approx(
            [1.0]
        )
        assert second_wrapper.runtime_adapter.get_state_vector().tolist() == pytest.approx(
            [1.0]
        )
        assert third_wrapper.runtime_adapter.get_state_vector().tolist() == pytest.approx(
            [1.0]
        )

        post_event_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(
            maximum_operations=100000
        )
        post_event_outputs: dict[VarPowerFlowReferenceType, float] = (
            first_wrapper.runtime_adapter._prepare_bound_step(
                current_time=0.0,
                step_size=float(retry_time),
                input_values=dict(control_input=5.0),
                evaluation_budget=post_event_budget,
            )
        )
        expected_post_event_outputs: dict[VarPowerFlowReferenceType, float] = dict()
        expected_post_event_outputs[VarPowerFlowReferenceType.P] = 0.0
        assert post_event_outputs == pytest.approx(expected_post_event_outputs)
        first_wrapper.runtime_adapter.resolve_pending_step(
            accepted=True,
            evaluation_budget=post_event_budget,
        )
        assert not first_wrapper.runtime_adapter.fmi_three_coordinator.has_pending_candidate()
        assert first_wrapper.runtime_adapter.get_next_event_time() is None
        assert first_wrapper.runtime_adapter.get_state_vector().tolist() == pytest.approx(
            [2.5],
            abs=1.0e-8,
        )
    finally:
        first_wrapper.close()
        second_wrapper.close()
        third_wrapper.close()
    staging_parent: Path = tmp_path / "state-event-global-retry"
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()
