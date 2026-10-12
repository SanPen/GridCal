from __future__ import annotations
from VeraGridEngine.enumerations import InterfaceType

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from VeraGridEngine.IO.fmu.interface import export_model_as_fmu
from VeraGridEngine.IO.fmu.CosimulationInterface.build import host_build_capable
from VeraGridEngine.IO.fmu.config import ExportConfig as CsExportConfig, detect_target_platform as detect_cs_target_platform
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.IO.fmu.config import ExportConfig as MeExportConfig, detect_target_platform as detect_me_target_platform
from VeraGridEngine.IO.fmu.Elements.bindings import (
    FmuBindingDirection,
    FmiThreeFloat64ConfigurationValue,
    FmiThreeUInt64ConfigurationValue,
    FmuImportConfig,
    FmuRefBinding,
    FmuVariableBinding,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    attach_emt_fmu_cs_device,
    attach_emt_fmu_me_device,
    attach_rms_fmu_cs_device,
    attach_rms_fmu_me_device,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    FmuCsDeviceConfigRecord,
    FmuMeDeviceConfigRecord,
    dump_fmu_cs_device_config,
    dump_fmu_me_device_config,
    load_fmu_cs_device_config,
    load_fmu_me_device_config,
    restore_fmu_cs_spec_from_record,
)
from VeraGridEngine.IO.fmu.co_simulation import (
    FmuCsDeviceSpec,
    FmuCsDomain,
    register_emt_fmu_cs_device,
    register_rms_fmu_cs_device,
)
from VeraGridEngine.IO.fmu.model_exchange import (
    FmuMeDomain,
    register_emt_fmu_me_device,
    register_rms_fmu_me_device,
)
from VeraGridEngine.IO.fmu.worker_host import (
    FmiThreeWorkerHostLimits,
)

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import (
    DeviceType,
    DynamicIntegrationMethod,
    FmuInterfaceMode,
    VarPowerFlowReferenceType,
)


def build_simple_output_fmu_block() -> Block:
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


def build_simple_me_output_fmu_block() -> Block:
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


class FakeProblem:
    def __init__(self, block: Block):
        self.uid2idx_event_params = {var.uid: index for index, var in enumerate(block.event_dict.keys())}
        self._fmu_cs_adapters = list()
        self._fmu_me_adapters = list()
        self.options = SimpleNamespace(
            integration_method=DynamicIntegrationMethod.DaeBackEuler,
            fmi_me_newton_absolute_tolerance=1.0e-8,
            fmi_me_newton_relative_tolerance=1.0e-8,
            fmi_me_newton_max_iterations=20,
            fmi_me_max_continuous_states=128,
        )


def test_fmi_three_configuration_declarations_validate_public_values() -> None:
    """Reject invalid declarations and revalidate mutable data before dumping.

    :return: None.
    """

    with pytest.raises(ValueError, match="flat index"):
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.Vm,
            fmu_variable_name="control_input",
            flat_index=-1,
        )
    with pytest.raises(ValueError, match="variable name is empty"):
        FmiThreeFloat64ConfigurationValue(variable_name=" ", values=(1.0,))
    with pytest.raises(ValueError, match="must be numeric"):
        FmiThreeFloat64ConfigurationValue(
            variable_name="structural_gain",
            values=(True,),
        )
    with pytest.raises(ValueError, match="must be finite"):
        FmiThreeFloat64ConfigurationValue(
            variable_name="structural_gain",
            values=(float("inf"),),
        )
    with pytest.raises(ValueError, match="outside UInt64"):
        FmiThreeUInt64ConfigurationValue(
            variable_name="structural_size",
            value=-1,
        )

    float64_configuration: FmiThreeFloat64ConfigurationValue = (
        FmiThreeFloat64ConfigurationValue(
            variable_name="structural_gain",
            values=(1.0,),
        )
    )
    record: FmuCsDeviceConfigRecord = FmuCsDeviceConfigRecord(
        domain=FmuCsDomain.RMS,
        fmu_path="mutable-configuration.fmu",
        preferred_mode=FmuInterfaceMode.CO_SIMULATION.value,
        input_bindings=tuple(),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_names=dict(),
        configuration_float64_values=(float64_configuration,),
    )
    float64_configuration.values = (float("nan"),)
    with pytest.raises(ValueError, match="must be finite"):
        dump_fmu_cs_device_config(record)

    duplicate_float64_configuration: FmiThreeFloat64ConfigurationValue = (
        FmiThreeFloat64ConfigurationValue(
            variable_name="shared_structural_value",
            values=(1.0,),
        )
    )
    with pytest.raises(
        ValueError,
        match="Duplicate FMI 3 Configuration Mode variable name",
    ):
        FmuCsDeviceConfigRecord(
            domain=FmuCsDomain.RMS,
            fmu_path="invalid-duplicate-provider.fmu",
            preferred_mode=FmuInterfaceMode.CO_SIMULATION.value,
            input_bindings=tuple(),
            output_bindings=tuple(),
            output_defaults=dict(),
            output_param_names=dict(),
            configuration_float64_values=(duplicate_float64_configuration,),
            configuration_uint64_values=(
                FmiThreeUInt64ConfigurationValue(
                    variable_name="shared_structural_value",
                    value=1,
                ),
            ),
        )


def test_fmi_three_v3_payload_rejects_malformed_values() -> None:
    """Reject malformed primitive declarations at the version-three boundary.

    :return: None.
    """

    record: FmuCsDeviceConfigRecord = FmuCsDeviceConfigRecord(
        domain=FmuCsDomain.RMS,
        fmu_path="malformed-provider.fmu",
        preferred_mode=FmuInterfaceMode.CO_SIMULATION.value,
        input_bindings=tuple(),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_names=dict(),
    )
    payload: dict[str, object] = json.loads(dump_fmu_cs_device_config(record))
    payload["configuration_float64_values"] = (
        ("structural_gain", (True,)),
    )
    with pytest.raises(ValueError, match="Invalid FMI 3 Float64"):
        load_fmu_cs_device_config(json.dumps(payload))

    payload["configuration_float64_values"] = list()
    payload["configuration_uint64_values"] = (
        ("structural_size", True),
    )
    with pytest.raises(ValueError, match="Invalid FMI 3 UInt64"):
        load_fmu_cs_device_config(json.dumps(payload))


def test_fmi_three_worker_limits_roundtrip_in_cs_device_config() -> None:
    """Preserve explicit FMI 3 worker limits through CS persistence versions.

    :return: None.
    """

    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=65536,
        maximum_float64_values_per_request=128,
        response_timeout_seconds=20.0,
        graceful_join_timeout_seconds=6.0,
        terminate_join_timeout_seconds=3.0,
        kill_join_timeout_seconds=1.0,
    )
    float64_configuration: FmiThreeFloat64ConfigurationValue = (
        FmiThreeFloat64ConfigurationValue(
            variable_name="structural_gain",
            values=(1.0, 2.0, 3.0, 4.0),
        )
    )
    uint64_configuration: FmiThreeUInt64ConfigurationValue = (
        FmiThreeUInt64ConfigurationValue(
            variable_name="structural_size",
            value=4,
        )
    )
    record: FmuCsDeviceConfigRecord = FmuCsDeviceConfigRecord(
        domain=FmuCsDomain.RMS,
        fmu_path="explicit-cs-worker-policy.fmu",
        preferred_mode=FmuInterfaceMode.CO_SIMULATION.value,
        input_bindings=(
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.Vm,
                fmu_variable_name="control_input",
                flat_index=3,
            ),
        ),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_names=dict(),
        worker_limits=worker_limits,
        configuration_float64_values=(float64_configuration,),
        configuration_uint64_values=(uint64_configuration,),
    )

    serialized_record: str = dump_fmu_cs_device_config(record)
    current_payload: dict[str, object] = json.loads(serialized_record)
    assert current_payload["version"] == 4
    loaded_record: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
        serialized_record
    )
    if loaded_record is not None:
        loaded_limits: FmiThreeWorkerHostLimits | None = loaded_record.worker_limits
    else:
        raise AssertionError("Serialized FMI CS device config did not reload")
    if loaded_limits is not None:
        assert loaded_limits.maximum_frame_size == 65536
        assert loaded_limits.maximum_float64_values_per_request == 128
        assert loaded_limits.response_timeout_seconds == 20.0
        assert loaded_limits.graceful_join_timeout_seconds == 6.0
        assert loaded_limits.terminate_join_timeout_seconds == 3.0
        assert loaded_limits.kill_join_timeout_seconds == 1.0
    else:
        raise AssertionError("Serialized FMI 3 CS worker limits were not restored")
    assert loaded_record.input_bindings[0].flat_index == 3
    assert loaded_record.configuration_float64_values[0].values == (
        1.0,
        2.0,
        3.0,
        4.0,
    )
    assert loaded_record.configuration_uint64_values[0].value == 4

    # Version 2 records retain worker supervision but predate array providers.
    current_payload["version"] = 2
    del current_payload["configuration_float64_values"]
    del current_payload["configuration_uint64_values"]
    current_payload["input_bindings"] = list()
    version_two_record: FmuCsDeviceConfigRecord | None = (
        load_fmu_cs_device_config(json.dumps(current_payload))
    )
    if version_two_record is not None:
        assert version_two_record.worker_limits is not None
        assert version_two_record.configuration_float64_values == tuple()
        assert version_two_record.configuration_uint64_values == tuple()
    else:
        raise AssertionError("Version 2 FMI CS device config did not reload")

    # Version 1 CS records remain valid without inventing a supervision policy.
    del current_payload["worker_limits"]
    current_payload["version"] = 1
    legacy_record: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
        json.dumps(current_payload)
    )
    if legacy_record is not None:
        assert legacy_record.worker_limits is None
    else:
        raise AssertionError("Version 1 FMI CS device config did not reload")


def test_fmi_three_worker_limits_roundtrip_in_me_device_config() -> None:
    """Preserve every explicit FMI 3 worker limit through ME persistence.

    :return: None.
    """

    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=131072,
        maximum_float64_values_per_request=256,
        response_timeout_seconds=30.0,
        graceful_join_timeout_seconds=8.0,
        terminate_join_timeout_seconds=4.0,
        kill_join_timeout_seconds=2.0,
    )
    float64_configuration: FmiThreeFloat64ConfigurationValue = (
        FmiThreeFloat64ConfigurationValue(
            variable_name="matrix_gain",
            values=(0.5, 1.5),
        )
    )
    uint64_configuration: FmiThreeUInt64ConfigurationValue = (
        FmiThreeUInt64ConfigurationValue(
            variable_name="matrix_width",
            value=2,
        )
    )
    record: FmuMeDeviceConfigRecord = FmuMeDeviceConfigRecord(
        domain=FmuMeDomain.RMS,
        fmu_path="explicit-worker-policy.fmu",
        preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE.value,
        input_bindings=tuple(),
        output_bindings=(
            FmuRefBinding(
                reference=VarPowerFlowReferenceType.P,
                fmu_variable_name="observed_output",
                flat_index=1,
            ),
        ),
        output_defaults=dict(),
        output_param_names=dict(),
        worker_limits=worker_limits,
        maximum_event_iterations=17,
        configuration_float64_values=(float64_configuration,),
        configuration_uint64_values=(uint64_configuration,),
    )

    serialized_record: str = dump_fmu_me_device_config(record)
    current_payload: dict[str, object] = json.loads(serialized_record)
    assert current_payload["version"] == 5
    loaded_record: FmuMeDeviceConfigRecord | None = load_fmu_me_device_config(
        serialized_record
    )
    if loaded_record is not None:
        loaded_limits: FmiThreeWorkerHostLimits | None = loaded_record.worker_limits
    else:
        raise AssertionError("Serialized FMI ME device config did not reload")
    if loaded_limits is not None:
        assert loaded_limits.maximum_frame_size == 131072
        assert loaded_limits.maximum_float64_values_per_request == 256
        assert loaded_limits.response_timeout_seconds == 30.0
        assert loaded_limits.graceful_join_timeout_seconds == 8.0
        assert loaded_limits.terminate_join_timeout_seconds == 4.0
        assert loaded_limits.kill_join_timeout_seconds == 2.0
    else:
        raise AssertionError("Serialized FMI 3 worker limits were not restored")
    assert loaded_record.output_bindings[0].flat_index == 1
    assert loaded_record.configuration_float64_values[0].values == (0.5, 1.5)
    assert loaded_record.configuration_uint64_values[0].value == 2
    assert loaded_record.maximum_event_iterations == 17
    # Native restoration is covered with a compiled ME array fixture in the
    # user API suite; this persistence-only record deliberately names no file.

    # Version 3 records predate the persisted Event Mode convergence bound.
    current_payload["version"] = 3
    del current_payload["maximum_event_iterations"]
    version_three_record: FmuMeDeviceConfigRecord | None = (
        load_fmu_me_device_config(json.dumps(current_payload))
    )
    if version_three_record is not None:
        assert version_three_record.maximum_event_iterations == 32
    else:
        raise AssertionError("Version 3 FMI ME device config did not reload")

    # Version 2 ME records retain worker supervision but no array declarations.
    current_payload["version"] = 2
    del current_payload["configuration_float64_values"]
    del current_payload["configuration_uint64_values"]
    current_payload["output_bindings"] = list()
    version_two_record: FmuMeDeviceConfigRecord | None = (
        load_fmu_me_device_config(json.dumps(current_payload))
    )
    if version_two_record is not None:
        assert version_two_record.worker_limits is not None
        assert version_two_record.configuration_float64_values == tuple()
        assert version_two_record.configuration_uint64_values == tuple()
        assert version_two_record.maximum_event_iterations == 32
    else:
        raise AssertionError("Version 2 FMI ME device config did not reload")

    # Version 1 records predate worker isolation. They remain loadable but do
    # not acquire invented policy values during migration.
    del current_payload["worker_limits"]
    current_payload["version"] = 1
    legacy_record: FmuMeDeviceConfigRecord | None = load_fmu_me_device_config(
        json.dumps(current_payload)
    )
    if legacy_record is not None:
        assert legacy_record.worker_limits is None
        assert legacy_record.maximum_event_iterations == 32
    else:
        raise AssertionError("Version 1 FMI ME device config did not reload")


def test_fmi_three_v4_me_config_requires_strict_event_iteration_bound() -> None:
    """Reject malformed v4 bounds and preserve only exact accepted integers."""

    accepted_bound: int
    for accepted_bound in (1, 1024):
        accepted_record: FmuMeDeviceConfigRecord = FmuMeDeviceConfigRecord(
            domain=FmuMeDomain.RMS,
            fmu_path="strict-event-bound.fmu",
            preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE.value,
            input_bindings=tuple(),
            output_bindings=tuple(),
            output_defaults=dict(),
            output_param_names=dict(),
            maximum_event_iterations=accepted_bound,
        )
        accepted_payload: str = dump_fmu_me_device_config(accepted_record)
        restored_record: FmuMeDeviceConfigRecord | None = (
            load_fmu_me_device_config(accepted_payload)
        )
        if restored_record is not None:
            assert restored_record.maximum_event_iterations == accepted_bound
        else:
            raise AssertionError("Accepted FMI ME event bound did not reload")

    rejected_bound: object
    for rejected_bound in (True, False, 0, 1025):
        with pytest.raises(ValueError, match="between 1 and 1024"):
            FmuMeDeviceConfigRecord(
                domain=FmuMeDomain.RMS,
                fmu_path="strict-event-bound.fmu",
                preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE.value,
                input_bindings=tuple(),
                output_bindings=tuple(),
                output_defaults=dict(),
                output_param_names=dict(),
                maximum_event_iterations=rejected_bound,
            )

    valid_record: FmuMeDeviceConfigRecord = FmuMeDeviceConfigRecord(
        domain=FmuMeDomain.RMS,
        fmu_path="strict-event-bound.fmu",
        preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE.value,
        input_bindings=tuple(),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_names=dict(),
        maximum_event_iterations=32,
    )
    valid_payload: dict[str, object] = json.loads(
        dump_fmu_me_device_config(valid_record)
    )
    malformed_bound: object
    for malformed_bound in ("32", 32.0, None, True, False, 0, 1025):
        malformed_payload: dict[str, object] = dict(valid_payload)
        malformed_payload["maximum_event_iterations"] = malformed_bound
        with pytest.raises(ValueError):
            load_fmu_me_device_config(json.dumps(malformed_payload))

    missing_payload: dict[str, object] = dict(valid_payload)
    del missing_payload["maximum_event_iterations"]
    with pytest.raises(ValueError, match="requires maximum Event Mode iterations"):
        load_fmu_me_device_config(json.dumps(missing_payload))

    legacy_version: int
    for legacy_version in (1, 2, 3):
        legacy_payload: dict[str, object] = dict(valid_payload)
        legacy_payload["version"] = legacy_version
        legacy_payload["maximum_event_iterations"] = 1025
        if legacy_version in (1, 2):
            del legacy_payload["configuration_float64_values"]
            del legacy_payload["configuration_uint64_values"]
        else:
            pass
        restored_legacy: FmuMeDeviceConfigRecord | None = (
            load_fmu_me_device_config(json.dumps(legacy_payload))
        )
        if restored_legacy is not None:
            assert restored_legacy.maximum_event_iterations == 32
        else:
            raise AssertionError("Legacy FMI ME event bound did not default")


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_rms_device_config_can_restore_runtime_spec(tmp_path: Path) -> None:
    """Restore one RMS CS runtime specification from persisted configuration.

    :param tmp_path: Isolated build and archive directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")

    output_root: Path = tmp_path
    fmu_path = output_root / "restore_rms.fmu"
    try:
        exported_fmu = export_model_as_fmu(
            build_simple_output_fmu_block(),
            CsExportConfig(
                model_name="RestoreRmsDevice",
                output_path=fmu_path,
                target_platform=detect_cs_target_platform(),
                compile_binary=True,
                keep_build_dir=False,
            ),
        )

        device = SimpleNamespace(device_type=DeviceType.LoadDevice, rms_model=Block(), rms_fmu_import_config="")
        attach_rms_fmu_cs_device(
            device=device,
            vfactory=VarFactory(name="restore_rms_var_factory"),
            config=FmuImportConfig(fmu_path=exported_fmu, extraction_root=output_root),
            input_bindings=tuple(),
            output_bindings=(FmuRefBinding(VarPowerFlowReferenceType.P, "y"),),
            output_defaults={VarPowerFlowReferenceType.P: 0.0},
            name="restore_rms_template",
        )

        loaded_block = device.rms_model.copy()
        loaded_device = SimpleNamespace(
            device_type=device.device_type,
            rms_model=loaded_block,
            rms_fmu_import_config=device.rms_fmu_import_config,
            bus=SimpleNamespace(rms_model=Block()),
            idtag="loaded-rms-device",
        )
        problem = FakeProblem(loaded_block)
        register_rms_fmu_cs_device(problem, loaded_device, loaded_block)
        assert len(problem._fmu_cs_adapters) == 1
    finally:
        fmu_path.unlink(missing_ok=True)


def test_fmu_parameter_mapping_round_trip_does_not_duplicate_numeric_values() -> None:
    """Persist parameter identity without creating a second numeric owner.

    :return: None.
    """

    parameter_binding: FmuVariableBinding = FmuVariableBinding(
        signal_name="fixed_gain_block",
        variable_name="fixed_gain",
        direction=FmuBindingDirection.PARAMETER,
    )
    record: FmuCsDeviceConfigRecord = FmuCsDeviceConfigRecord(
        domain=FmuCsDomain.RMS,
        fmu_path="parameter-identity-only.fmu",
        preferred_mode=FmuInterfaceMode.CO_SIMULATION.value,
        input_bindings=tuple(),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_names=dict(),
        parameter_bindings=(parameter_binding,),
    )
    serialized_record: str = dump_fmu_cs_device_config(record)
    payload: dict[str, object] = json.loads(serialized_record)
    assert payload["parameter_bindings"] == [
        ["fixed_gain_block", "fixed_gain"]
    ]
    assert "parameter_values" not in payload
    loaded_record: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
        serialized_record
    )
    if loaded_record is not None:
        pass
    else:
        raise AssertionError("Current CS parameter mapping did not reload")
    assert loaded_record.parameter_bindings[0].signal_name == "fixed_gain_block"
    assert loaded_record.parameter_bindings[0].variable_name == "fixed_gain"


def test_fmu_parameter_restore_uses_current_block_const(
    compiled_fmi_three_parameterized_configurable_array_fmu: Path,
) -> None:
    """Resolve the live Block constant and reject malformed identity mappings.

    :param compiled_fmi_three_parameterized_configurable_array_fmu: Native
        FMI 3 fixture supplying authoritative parameter metadata.
    :return: None.
    """

    fixed_gain_var: Var = Var("fixed_gain_block")
    block: Block = Block(parameters={fixed_gain_var: Const(9.25)})
    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    valid_binding: FmuVariableBinding = FmuVariableBinding(
        signal_name="fixed_gain_block",
        variable_name="fixed_gain",
        direction=FmuBindingDirection.PARAMETER,
    )
    valid_record: FmuCsDeviceConfigRecord = FmuCsDeviceConfigRecord(
        domain=FmuCsDomain.RMS,
        fmu_path=str(compiled_fmi_three_parameterized_configurable_array_fmu),
        preferred_mode=FmuInterfaceMode.CO_SIMULATION.value,
        input_bindings=tuple(),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_names=dict(),
        worker_limits=worker_limits,
        configuration_uint64_values=(
            FmiThreeUInt64ConfigurationValue(
                variable_name="structural_size",
                value=2,
            ),
        ),
        parameter_bindings=(valid_binding,),
    )
    restored_spec: FmuCsDeviceSpec = restore_fmu_cs_spec_from_record(
        record=valid_record,
        block=block,
        device_tpe=DeviceType.LoadDevice,
    )
    assert restored_spec.parameter_values[0].value == pytest.approx(9.25)
    block.parameters[fixed_gain_var] = Const(4.5)
    edited_spec: FmuCsDeviceSpec = restore_fmu_cs_spec_from_record(
        record=valid_record,
        block=block,
        device_tpe=DeviceType.LoadDevice,
    )
    assert edited_spec.parameter_values[0].value == pytest.approx(4.5)

    missing_binding: FmuVariableBinding = FmuVariableBinding(
        signal_name="missing_block_parameter",
        variable_name="fixed_gain",
        direction=FmuBindingDirection.PARAMETER,
    )
    missing_record: FmuCsDeviceConfigRecord = FmuCsDeviceConfigRecord(
        domain=valid_record.domain,
        fmu_path=valid_record.fmu_path,
        preferred_mode=valid_record.preferred_mode,
        input_bindings=tuple(),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_names=dict(),
        worker_limits=worker_limits,
        parameter_bindings=(missing_binding,),
    )
    with pytest.raises(ValueError, match="exactly one Block"):
        restore_fmu_cs_spec_from_record(
            record=missing_record,
            block=block,
            device_tpe=DeviceType.LoadDevice,
        )

    transformed_binding: FmuVariableBinding = FmuVariableBinding(
        signal_name="fixed_gain_block",
        variable_name="fixed_gain",
        direction=FmuBindingDirection.PARAMETER,
        scale=2.0,
    )
    transformed_record: FmuCsDeviceConfigRecord = FmuCsDeviceConfigRecord(
        domain=valid_record.domain,
        fmu_path=valid_record.fmu_path,
        preferred_mode=valid_record.preferred_mode,
        input_bindings=tuple(),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_names=dict(),
        worker_limits=worker_limits,
        parameter_bindings=(valid_binding,),
    )
    transformed_record.parameter_bindings = (transformed_binding,)
    with pytest.raises(ValueError, match="transform must be identity"):
        restore_fmu_cs_spec_from_record(
            record=transformed_record,
            block=block,
            device_tpe=DeviceType.LoadDevice,
        )


def test_historical_fmu_device_configs_restore_empty_parameter_bindings() -> None:
    """Treat CS v1-v3 and ME v1-v4 as pre-parameter-mapping schemas.

    :return: None.
    """

    parameter_binding: FmuVariableBinding = FmuVariableBinding(
        signal_name="fixed_gain_block",
        variable_name="fixed_gain",
        direction=FmuBindingDirection.PARAMETER,
    )
    cs_record: FmuCsDeviceConfigRecord = FmuCsDeviceConfigRecord(
        domain=FmuCsDomain.RMS,
        fmu_path="historical-cs.fmu",
        preferred_mode=FmuInterfaceMode.CO_SIMULATION.value,
        input_bindings=tuple(),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_names=dict(),
        parameter_bindings=(parameter_binding,),
    )
    cs_payload: dict[str, object] = json.loads(dump_fmu_cs_device_config(cs_record))
    historical_cs_version: int
    for historical_cs_version in (3, 2, 1):
        cs_payload["version"] = historical_cs_version
        if historical_cs_version in (1, 2):
            cs_payload.pop("configuration_float64_values", None)
            cs_payload.pop("configuration_uint64_values", None)
        else:
            pass
        historical_cs: FmuCsDeviceConfigRecord | None = (
            load_fmu_cs_device_config(json.dumps(cs_payload))
        )
        if historical_cs is not None:
            assert historical_cs.parameter_bindings == tuple()
        else:
            raise AssertionError("Historical CS config did not reload")

    me_record: FmuMeDeviceConfigRecord = FmuMeDeviceConfigRecord(
        domain=FmuMeDomain.RMS,
        fmu_path="historical-me.fmu",
        preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE.value,
        input_bindings=tuple(),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_names=dict(),
        parameter_bindings=(parameter_binding,),
    )
    me_payload: dict[str, object] = json.loads(dump_fmu_me_device_config(me_record))
    historical_me_version: int
    for historical_me_version in (4, 3, 2, 1):
        me_payload["version"] = historical_me_version
        if historical_me_version in (1, 2):
            me_payload.pop("configuration_float64_values", None)
            me_payload.pop("configuration_uint64_values", None)
        else:
            pass
        historical_me: FmuMeDeviceConfigRecord | None = (
            load_fmu_me_device_config(json.dumps(me_payload))
        )
        if historical_me is not None:
            assert historical_me.parameter_bindings == tuple()
        else:
            raise AssertionError("Historical ME config did not reload")


def test_current_cs_v4_and_me_v5_parameter_mappings_round_trip() -> None:
    """Round-trip current parameter identity schemas for both import modes.

    :return: None.
    """

    parameter_binding: FmuVariableBinding = FmuVariableBinding(
        signal_name="tunable_bias_block",
        variable_name="tunable_bias",
        direction=FmuBindingDirection.PARAMETER,
    )
    cs_record: FmuCsDeviceConfigRecord = FmuCsDeviceConfigRecord(
        domain=FmuCsDomain.RMS,
        fmu_path="current-cs.fmu",
        preferred_mode=FmuInterfaceMode.CO_SIMULATION.value,
        input_bindings=tuple(),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_names=dict(),
        parameter_bindings=(parameter_binding,),
    )
    me_record: FmuMeDeviceConfigRecord = FmuMeDeviceConfigRecord(
        domain=FmuMeDomain.RMS,
        fmu_path="current-me.fmu",
        preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE.value,
        input_bindings=tuple(),
        output_bindings=tuple(),
        output_defaults=dict(),
        output_param_names=dict(),
        parameter_bindings=(parameter_binding,),
    )
    cs_payload: dict[str, object] = json.loads(dump_fmu_cs_device_config(cs_record))
    me_payload: dict[str, object] = json.loads(dump_fmu_me_device_config(me_record))
    assert cs_payload["version"] == 4
    assert me_payload["version"] == 5
    loaded_cs: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
        json.dumps(cs_payload)
    )
    loaded_me: FmuMeDeviceConfigRecord | None = load_fmu_me_device_config(
        json.dumps(me_payload)
    )
    if loaded_cs is not None and loaded_me is not None:
        pass
    else:
        raise AssertionError("Current parameter mappings did not reload")
    assert loaded_cs.parameter_bindings[0].signal_name == "tunable_bias_block"
    assert loaded_me.parameter_bindings[0].signal_name == "tunable_bias_block"


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_emt_device_config_can_restore_runtime_spec(tmp_path: Path) -> None:
    """Restore one EMT CS runtime specification from persisted configuration.

    :param tmp_path: Isolated build and archive directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")

    output_root: Path = tmp_path
    fmu_path = output_root / "restore_emt.fmu"
    try:
        exported_fmu = export_model_as_fmu(
            build_simple_output_fmu_block(),
            CsExportConfig(
                model_name="RestoreEmtDevice",
                output_path=fmu_path,
                target_platform=detect_cs_target_platform(),
                compile_binary=True,
                keep_build_dir=False,
            ),
        )

        device = SimpleNamespace(device_type=DeviceType.LoadDevice, emt_model=Block(), emt_fmu_import_config="")
        attach_emt_fmu_cs_device(
            device=device,
            vfactory=VarFactory(name="restore_emt_var_factory"),
            config=FmuImportConfig(fmu_path=exported_fmu, extraction_root=output_root),
            input_bindings=tuple(),
            output_bindings=(FmuRefBinding(VarPowerFlowReferenceType.i_A, "y"),),
            output_defaults={VarPowerFlowReferenceType.i_A: 0.0},
            name="restore_emt_template",
        )

        loaded_block = device.emt_model.copy()
        loaded_device = SimpleNamespace(
            device_type=device.device_type,
            emt_model=loaded_block,
            emt_fmu_import_config=device.emt_fmu_import_config,
            bus=SimpleNamespace(emt_model=Block()),
            idtag="loaded-emt-device",
        )
        problem = FakeProblem(loaded_block)
        register_emt_fmu_cs_device(problem, loaded_device, loaded_block)
        assert len(problem._fmu_cs_adapters) == 1
    finally:
        fmu_path.unlink(missing_ok=True)


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_rms_me_device_config_can_restore_runtime_spec(tmp_path: Path) -> None:
    """Restore one RMS ME runtime specification from persisted configuration.

    :param tmp_path: Isolated build and archive directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")

    output_root: Path = tmp_path
    fmu_path = output_root / "restore_rms_me.fmu"
    try:
        exported_fmu = export_model_as_fmu(
            build_simple_me_output_fmu_block(),
            MeExportConfig(interface_type=InterfaceType.MODEL_EXCHANGE, 
                model_name="RestoreRmsMeDevice",
                output_path=fmu_path,
                target_platform=detect_me_target_platform(),
                compile_binary=True,
                keep_build_dir=False,
            ),
        )

        device = SimpleNamespace(device_type=DeviceType.LoadDevice, rms_model=Block(), rms_fmu_me_import_config="")
        attach_rms_fmu_me_device(
            device=device,
            vfactory=VarFactory(name="restore_rms_me_var_factory"),
            config=FmuImportConfig(fmu_path=exported_fmu, extraction_root=output_root),
            input_bindings=(FmuRefBinding(VarPowerFlowReferenceType.Vm, "u"),),
            output_bindings=(FmuRefBinding(VarPowerFlowReferenceType.P, "y"),),
            output_defaults={VarPowerFlowReferenceType.P: 0.0},
            name="restore_rms_me_template",
        )

        loaded_block = device.rms_model.copy()
        loaded_device = SimpleNamespace(
            device_type=device.device_type,
            rms_model=loaded_block,
            rms_fmu_me_import_config=device.rms_fmu_me_import_config,
            bus=SimpleNamespace(rms_model=Block()),
            idtag="loaded-rms-me-device",
        )
        problem = FakeProblem(loaded_block)
        register_rms_fmu_me_device(problem, loaded_device, loaded_block)
        assert len(problem._fmu_me_adapters) == 1
    finally:
        fmu_path.unlink(missing_ok=True)


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_emt_me_device_config_can_restore_runtime_spec(tmp_path: Path) -> None:
    """Restore one EMT ME runtime specification from persisted configuration.

    :param tmp_path: Isolated build and archive directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")

    output_root: Path = tmp_path
    fmu_path = output_root / "restore_emt_me.fmu"
    try:
        exported_fmu = export_model_as_fmu(
            build_simple_me_output_fmu_block(),
            MeExportConfig(interface_type=InterfaceType.MODEL_EXCHANGE, 
                model_name="RestoreEmtMeDevice",
                output_path=fmu_path,
                target_platform=detect_me_target_platform(),
                compile_binary=True,
                keep_build_dir=False,
            ),
        )

        device = SimpleNamespace(device_type=DeviceType.LoadDevice, emt_model=Block(), emt_fmu_me_import_config="")
        attach_emt_fmu_me_device(
            device=device,
            vfactory=VarFactory(name="restore_emt_me_var_factory"),
            config=FmuImportConfig(fmu_path=exported_fmu, extraction_root=output_root),
            input_bindings=tuple(),
            output_bindings=(FmuRefBinding(reference=VarPowerFlowReferenceType.i_A, fmu_variable_name="y"),),
            output_defaults={VarPowerFlowReferenceType.i_A: 0.0},
            name="restore_emt_me_template",
        )

        loaded_block = device.emt_model.copy()
        loaded_device = SimpleNamespace(
            device_type=device.device_type,
            emt_model=loaded_block,
            emt_fmu_me_import_config=device.emt_fmu_me_import_config,
            bus=SimpleNamespace(emt_model=Block()),
            idtag="loaded-emt-me-device",
        )
        problem = FakeProblem(loaded_block)
        register_emt_fmu_me_device(problem, loaded_device, loaded_block)
        assert len(problem._fmu_me_adapters) == 1
    finally:
        fmu_path.unlink(missing_ok=True)
