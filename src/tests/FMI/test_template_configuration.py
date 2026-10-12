from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from VeraGridEngine.Devices.Dynamic.fmu_template import FmuTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import (
    DeviceType,
    FmuTemplateDomain,
    FmuTemplateMode,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
)
from VeraGridEngine.IO.fmu.co_simulation import (
    FmuCsDeviceAdapter,
    FmuCsDeviceSpec,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    FmuCsDeviceConfigRecord,
    load_fmu_cs_device_config,
    restore_fmu_cs_spec_from_record,
)
from VeraGridEngine.IO.fmu.profile import (
    FmiThreeWorkerFloat64Profile,
)
from VeraGridEngine.IO.fmu.worker_host import (
    FmiThreeWorkerHostLimits,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import configure_fmu_template


def _artifact_path() -> Path:
    """
    Return the path to the FMU artifact used by the template-configuration tests.

    :return: FMU artifact path.
    """

    return Path(__file__).resolve().parents[1] / "data" / "fmi" / "artifacts" / "FrequencyLoadPilot.fmu"


def test_configure_fmu_template_builds_visual_ports_and_auto_bindings() -> None:
    """
    Configuring one FMU template must expose the FMU interface as editor ports and serialized runtime bindings.

    :return: None.
    """

    template = FmuTemplate(name="")
    var_factory = VarFactory(name="RmsFmuTemplateFactory")

    configured_template = configure_fmu_template(
        template=template,
        var_factory=var_factory,
        fmu_path=_artifact_path(),
        device_tpe=DeviceType.LoadDevice,
        domain=FmuTemplateDomain.RMS,
        mode=FmuTemplateMode.CO_SIMULATION,
        template_name="",
    )

    input_names = [var.name for var in configured_template.block.in_vars]
    output_names = [var.name for var in configured_template.block.out_vars]
    parameter_names = [var.name for var in configured_template.block.parameters.keys()]

    assert "Va_" in input_names
    assert "Vm_" in input_names
    assert "P" in output_names
    assert "Q" in output_names
    assert "y_frequency_measure" in output_names
    assert "Pl0" in parameter_names
    assert "Ql0" in parameter_names
    assert configured_template.block.api_obj_mapping[ParamPowerFlowReferenceType.Pl0].name == "Pl0"
    assert configured_template.block.api_obj_mapping[ParamPowerFlowReferenceType.Ql0].name == "Ql0"

    serialized_record = load_fmu_cs_device_config(configured_template.serialized_config)
    assert serialized_record is not None
    assert {binding.reference for binding in serialized_record.input_bindings} == {
        VarPowerFlowReferenceType.Va,
        VarPowerFlowReferenceType.Vm,
    }
    assert {binding.reference for binding in serialized_record.output_bindings} == {
        VarPowerFlowReferenceType.P,
        VarPowerFlowReferenceType.Q,
    }
    assert {
        binding.variable_name for binding in serialized_record.parameter_bindings
    } >= {"Pl0", "Ql0"}


def test_configured_fmu_template_parameter_mapping_survives_edit_serialize_restore_and_execution(
    compiled_fmi_three_parameterized_configurable_array_fmu: Path,
    tmp_path: Path,
) -> None:
    """Restore an edited Block parameter and execute the configured FMU shell.

    :param compiled_fmi_three_parameterized_configurable_array_fmu: Native
        dual-interface fixture with observable parameters.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    template: FmuTemplate = FmuTemplate(name="")
    var_factory: VarFactory = VarFactory(name="ParameterizedTemplateFactory")
    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    configured_template: FmuTemplate = configure_fmu_template(
        template=template,
        var_factory=var_factory,
        fmu_path=compiled_fmi_three_parameterized_configurable_array_fmu,
        device_tpe=DeviceType.LoadDevice,
        domain=FmuTemplateDomain.RMS,
        mode=FmuTemplateMode.CO_SIMULATION,
        template_name="ParameterizedTemplate",
        worker_limits=worker_limits,
    )
    loaded_block: Block = configured_template.block.copy()
    fixed_gain_var: Var | None = None
    parameter_var: Var
    for parameter_var in loaded_block.parameters:
        if parameter_var.name == "fixed_gain":
            fixed_gain_var = parameter_var
        else:
            pass
    if fixed_gain_var is not None:
        loaded_block.parameters[fixed_gain_var] = Const(5.0)
    else:
        raise AssertionError("Configured template has no fixed_gain parameter")
    record: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
        configured_template.serialized_config
    )
    if record is not None:
        pass
    else:
        raise AssertionError("Configured template record did not reload")
    spec: FmuCsDeviceSpec = restore_fmu_cs_spec_from_record(
        record=record,
        block=loaded_block,
        device_tpe=DeviceType.LoadDevice,
    )
    assert spec.float64_profile == FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY
    assert spec.parameter_values[0].variable_name == "fixed_gain"
    assert spec.parameter_values[0].value == 5.0
    spec.config.extraction_root = tmp_path
    adapter: FmuCsDeviceAdapter = FmuCsDeviceAdapter(
        problem=SimpleNamespace(),
        device=SimpleNamespace(name="ParameterizedTemplateDevice"),
        spec=spec,
        output_param_indices=dict(),
    )
    try:
        initial_outputs: dict[VarPowerFlowReferenceType, float] = (
            adapter.initialize_outputs(
                time_value=0.0,
                x_snapshot=np.zeros(0, dtype=float),
            )
        )
        assert initial_outputs == dict()
        advanced_outputs: dict[VarPowerFlowReferenceType, float] = adapter.advance(
            current_time=0.0,
            step_size=0.25,
            x_snapshot=np.zeros(0, dtype=float),
        )
        assert advanced_outputs == dict()
    finally:
        adapter.close()
