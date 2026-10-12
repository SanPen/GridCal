# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Independent FMI fixture builders used only by product integration tests."""
from __future__ import annotations
from VeraGridEngine.enumerations import InterfaceType

from pathlib import Path
import uuid

from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.fmu.interface import export_model_as_fmu
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import CmpOp, Comparison, Const, Var
from VeraGridEngine.IO.fmu.config import ExportConfig as CsExportConfig, detect_target_platform as detect_cs_target_platform
from VeraGridEngine.IO.fmu.config import ExportConfig as MeExportConfig, detect_target_platform as detect_me_target_platform
from VeraGridEngine.IO.fmu.Elements.bindings import FmuRefBinding
from VeraGridEngine.IO.fmu.model_description import FmuInterfaceMode
from VeraGridEngine.IO.fmu.worker_host import (
    FmiThreeWorkerHostLimits,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    FmuDeviceAttachmentRequest,
    FmuDeviceDomain,
    FmuReferenceValue,
    attach_fmu_to_device,
)
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model, set_rms_model
from VeraGridEngine.Utils.procedural_logic import flipflop
from VeraGridEngine.enumerations import (
    BranchImpedanceMode,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    FmiVersion,
    ParamPowerFlowReferenceType,
    SolverType,
    VarPowerFlowReferenceType,
)


def _build_test_rms_cs_source_block() -> Block:
    """Build the self-contained source block used to export an example RMS CS FMU.

    :return: Example RMS CS FMU block.
    """

    x: Var = Var("x")
    dx: Var = Var("dx", base_var=x)
    p_out: Var = Var("p_out")
    q_out: Var = Var("q_out")
    return Block(
        state_vars=list((x,)),
        state_eqs=list((Const(1.0),)),
        algebraic_vars=list((p_out, q_out)),
        algebraic_eqs=list((
            p_out - (Const(-0.1) - Const(0.02) * x),
            q_out - Const(-0.01),
        )),
        diff_vars=list((dx,)),
        init_values=dict((
            (x, Const(0.0)),
            (p_out, Const(-0.1)),
            (q_out, Const(-0.01)),
        )),
        init_eqs=dict((
            (p_out, Const(-0.1)),
            (q_out, Const(-0.01)),
        )),
        out_vars=list((p_out, q_out)),
    )


def _build_test_rms_me_source_block() -> Block:
    """Build the self-contained source block used to export an example RMS ME FMU.

    :return: Example RMS ME FMU block.
    """

    x: Var = Var("x")
    dx: Var = Var("dx", base_var=x)
    p_out: Var = Var("p_out")
    q_out: Var = Var("q_out")
    u: Var = Var("u")
    return Block(
        state_vars=list((x,)),
        # Keep the accepted initialization voltage as a state so the native
        # fixture exposes current-point voltage coupling without internal lag.
        state_eqs=list((Const(0.0),)),
        algebraic_vars=list((p_out, q_out)),
        # Both powers respond directly to the current voltage input. This makes
        # a stale previous-iterate input distinguishable in the native test.
        algebraic_eqs=list((
            p_out - (Const(-0.1) - Const(2.0) * (u - x)),
            q_out - (Const(-0.01) - (u - x)),
        )),
        diff_vars=list((dx,)),
        init_values=dict((
            (x, Const(0.0)),
            (p_out, Const(-0.1)),
            (q_out, Const(-0.01)),
        )),
        init_eqs=dict((
            (x, u),
            (p_out, Const(-0.1)),
            (q_out, Const(-0.01)),
        )),
        in_vars=list((u,)),
        out_vars=list((p_out, q_out)),
    )


def _build_test_emt_cs_source_block() -> Block:
    """Build the self-contained source block used to export an example EMT CS FMU.

    :return: Example EMT CS FMU block.
    """

    x: Var = Var("x")
    dx: Var = Var("dx", base_var=x)
    i_a: Var = Var("i_a_out")
    i_b: Var = Var("i_b_out")
    i_c: Var = Var("i_c_out")
    v_a: Var = Var("v_a_in")
    v_b: Var = Var("v_b_in")
    v_c: Var = Var("v_c_in")
    return Block(
        state_vars=list((x,)),
        state_eqs=list((Const(1.0),)),
        algebraic_vars=list((i_a, i_b, i_c)),
        algebraic_eqs=list((
            i_a - (Const(-0.01) * x),
            i_b - (Const(0.005) * x),
            i_c - (Const(0.005) * x),
        )),
        diff_vars=list((dx,)),
        init_values=dict((
            (x, Const(0.0)),
            (i_a, Const(0.0)),
            (i_b, Const(0.0)),
            (i_c, Const(0.0)),
        )),
        init_eqs=dict((
            (i_a, Const(0.0)),
            (i_b, Const(0.0)),
            (i_c, Const(0.0)),
        )),
        in_vars=list((v_a, v_b, v_c)),
        out_vars=list((i_a, i_b, i_c)),
    )


def _build_test_emt_me_source_block() -> Block:
    """Build the self-contained source block used to export an example EMT ME FMU.

    :return: Example EMT ME FMU block.
    """

    x: Var = Var("x")
    dx: Var = Var("dx", base_var=x)
    i_a: Var = Var("i_a_out")
    i_b: Var = Var("i_b_out")
    i_c: Var = Var("i_c_out")
    u: Var = Var("u")
    v_b: Var = Var("v_b_in")
    v_c: Var = Var("v_c_in")
    return Block(
        state_vars=list((x,)),
        state_eqs=list((Const(1.0) + u,)),
        algebraic_vars=list((i_a, i_b, i_c)),
        algebraic_eqs=list((
            i_a - x,
            i_b - (Const(-0.5) * x),
            i_c - (Const(-0.5) * x),
        )),
        diff_vars=list((dx,)),
        init_values=dict((
            (x, Const(0.0)),
            (i_a, Const(0.0)),
            (i_b, Const(0.0)),
            (i_c, Const(0.0)),
        )),
        init_eqs=dict((
            (i_a, Const(0.0)),
            (i_b, Const(0.0)),
            (i_c, Const(0.0)),
        )),
        in_vars=list((u, v_b, v_c)),
        out_vars=list((i_a, i_b, i_c)),
    )


def export_test_fmi_three_external_discontinuity_cs_fmu(output_dir: Path) -> Path:
    """Export the FMI 3 CS fixture driven by one external input discontinuity.

    :param output_dir: Isolated output directory for the generated FMU.
    :return: Path to the compiled FMI 3 Co-Simulation FMU.
    """
    state: Var = Var("x")
    derivative: Var = Var("dx", base_var=state)
    input_value: Var = Var("u")
    source_block: Block = Block(
        state_vars=list((state,)),
        state_eqs=list((input_value,)),
        diff_vars=list((derivative,)),
        init_values=dict(((state, Const(0.0)),)),
        in_vars=list((input_value,)),
        out_vars=list((state,)),
        name="FmiThreeExternalDiscontinuityCs",
    )
    unique_name: str = f"FmiThreeExternalDiscontinuityCs_{uuid.uuid4().hex[:8]}"
    return export_model_as_fmu(
        source_block,
        CsExportConfig(
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_cs_target_platform(),
            compile_binary=True,
            keep_build_dir=False,
            fixed_step=1.0e-3,
            fmi_version=FmiVersion.FMI_3_0,
        ),
    )


def export_test_fmi_three_time_event_me_fmu(output_dir: Path) -> Path:
    """Export the FMI 3 ME fixture with a scheduled ordinary time event.

    :param output_dir: Isolated output directory for the generated FMU.
    :return: Path to the compiled FMI 3 Model Exchange FMU.
    """
    state: Var = Var("x")
    derivative: Var = Var("dx", base_var=state)
    event_mode: Var = Var("event_mode")
    global_time: Var = Var("glob_time")
    source_block: Block = Block(
        state_vars=list((state,)),
        state_eqs=list((event_mode,)),
        diff_vars=list((derivative,)),
        init_values=dict(((state, Const(0.0)),)),
        mode_dict=dict(((event_mode, Const(0.0)),)),
        out_vars=list((state, event_mode)),
        name="FmiThreeTimeEventMe",
    )
    source_block.procedural_logic = list((
        flipflop(
            boolset=Comparison(global_time, CmpOp.GE, Const(0.01)),
            boolreset=Const(0.0),
            output=event_mode,
            name="time_event_latch",
        ),
    ))
    unique_name: str = f"FmiThreeTimeEventMe_{uuid.uuid4().hex[:8]}"
    return export_model_as_fmu(
        source_block,
        MeExportConfig(interface_type=InterfaceType.MODEL_EXCHANGE, 
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_me_target_platform(),
            compile_binary=True,
            keep_build_dir=False,
            fixed_step=1.0e-3,
            fmi_version=FmiVersion.FMI_3_0,
        ),
    )


def export_test_fmi_three_state_event_me_fmu(output_dir: Path) -> Path:
    """Export the FMI 3 ME fixture with an importer-located zero crossing.

    :param output_dir: Isolated output directory for the generated FMU.
    :return: Path to the compiled FMI 3 Model Exchange FMU.
    """
    state: Var = Var("x")
    derivative: Var = Var("dx", base_var=state)
    event_mode: Var = Var("event_mode")
    source_block: Block = Block(
        state_vars=list((state,)),
        state_eqs=list((Const(1.0),)),
        diff_vars=list((derivative,)),
        init_values=dict(((state, Const(0.0)),)),
        mode_dict=dict(((event_mode, Const(0.0)),)),
        out_vars=list((state, event_mode)),
        name="FmiThreeStateEventMe",
    )
    source_block.procedural_logic = list((
        flipflop(
            boolset=Comparison(state, CmpOp.GE, Const(0.015)),
            boolreset=Const(0.0),
            output=event_mode,
            name="state_event_latch",
        ),
    ))
    unique_name: str = f"FmiThreeStateEventMe_{uuid.uuid4().hex[:8]}"
    return export_model_as_fmu(
        source_block,
        MeExportConfig(interface_type=InterfaceType.MODEL_EXCHANGE, 
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_me_target_platform(),
            compile_binary=True,
            keep_build_dir=False,
            fixed_step=1.0e-3,
            fmi_version=FmiVersion.FMI_3_0,
        ),
    )

def export_test_rms_cs_fmu(
    output_dir: Path,
    fmi_version: FmiVersion = FmiVersion.FMI_2_0,
) -> Path:
    """Export the self-contained RMS CS device FMU used by the example scripts.

    :param output_dir: Output directory for the generated FMU.
    :param fmi_version: FMI generation selected for the fixture.
    :return: Generated FMU path.
    """

    unique_name: str = f"TestRmsCsDevice_{uuid.uuid4().hex[:8]}"
    return export_model_as_fmu(
        _build_test_rms_cs_source_block(),
        CsExportConfig(
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_cs_target_platform(),
            compile_binary=True,
            keep_build_dir=False,
            fmi_version=fmi_version,
        ),
    )


def export_test_rms_me_fmu(
    output_dir: Path,
    fmi_version: FmiVersion = FmiVersion.FMI_2_0,
) -> Path:
    """Export the self-contained RMS ME device FMU used by the example scripts.

    :param output_dir: Output directory for the generated FMU.
    :param fmi_version: FMI generation selected for the fixture.
    :return: Generated FMU path.
    """

    unique_name: str = f"TestRmsMeDevice_{uuid.uuid4().hex[:8]}"
    return export_model_as_fmu(
        _build_test_rms_me_source_block(),
        MeExportConfig(interface_type=InterfaceType.MODEL_EXCHANGE, 
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_me_target_platform(),
            compile_binary=True,
            keep_build_dir=False,
            fmi_version=fmi_version,
        ),
    )


def export_test_emt_cs_fmu(
    output_dir: Path,
    fmi_version: FmiVersion = FmiVersion.FMI_2_0,
) -> Path:
    """Export the self-contained EMT CS device FMU used by the example scripts.

    :param output_dir: Output directory for the generated FMU.
    :param fmi_version: FMI generation selected for the fixture.
    :return: Generated FMU path.
    """

    unique_name: str = f"TestEmtCsDevice_{uuid.uuid4().hex[:8]}"
    return export_model_as_fmu(
        _build_test_emt_cs_source_block(),
        CsExportConfig(
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_cs_target_platform(),
            compile_binary=True,
            keep_build_dir=False,
            fmi_version=fmi_version,
        ),
    )


def export_test_emt_me_fmu(
    output_dir: Path,
    fmi_version: FmiVersion = FmiVersion.FMI_2_0,
) -> Path:
    """Export the self-contained EMT ME device FMU used by the example scripts.

    :param output_dir: Output directory for the generated FMU.
    :param fmi_version: FMI generation selected for the fixture.
    :return: Generated FMU path.
    """

    unique_name: str = f"TestEmtMeDevice_{uuid.uuid4().hex[:8]}"
    return export_model_as_fmu(
        _build_test_emt_me_source_block(),
        MeExportConfig(interface_type=InterfaceType.MODEL_EXCHANGE, 
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_me_target_platform(),
            compile_binary=True,
            keep_build_dir=False,
            fmi_version=fmi_version,
        ),
    )


def build_test_power_flow_options() -> PowerFlowOptions:
    """Build the power-flow options reused by the FMU import examples.

    :return: Power-flow options.
    """

    return PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=True,
        apply_temperature_correction=False,
        branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )


def build_test_rms_grid() -> tuple[MultiCircuit, Load]:
    """Build the minimal RMS demo grid used by the RMS FMU import examples.

    :return: Grid and imported device.
    """

    grid: MultiCircuit = MultiCircuit(Sbase=100.0, fbase=50.0)
    bus_slack: Bus = Bus(name="Bus0", Vnom=10.0, is_slack=True)
    bus_load: Bus = Bus(name="Bus1", Vnom=10.0)
    grid.add_bus(bus_slack)
    grid.add_bus(bus_load)

    # RMS buses need their symbolic shell before attaching dynamic devices.
    initialize_bus_rms(bus_slack, vf=grid.var_factory)
    initialize_bus_rms(bus_load, vf=grid.var_factory)

    line: Line = Line(name="line_0_1", bus_from=bus_slack, bus_to=bus_load, r=0.03, x=0.07, b=0.03, rate=900.0)
    generator: Generator = Generator(
        name="Gen0",
        P=10.0,
        vset=1.0,
        Snom=900.0,
        x1=0.86138701,
        r1=0.3,
        freq=50.0,
    )
    load: Load = Load(name="ImportedLoad", P=10.0, Q=1.0)
    disturbance_load: Load = Load(name="DisturbanceLoad", P=5.0, Q=1.0)

    grid.add_line(line)
    grid.add_generator(bus=bus_slack, api_obj=generator)
    grid.add_load(bus=bus_load, api_obj=load)
    grid.add_load(bus=bus_load, api_obj=disturbance_load)
    line.rms_template = get_line_rms_template(grid.var_factory)
    generator.rms_template = get_complete_generator_template_rms(grid.var_factory)
    disturbance_model: Block = get_load_rms_template(grid.var_factory).block
    set_rms_model(
        device=disturbance_load,
        model=disturbance_model,
        var_factory=grid.var_factory,
    )
    event_group: RmsEventsGroup = RmsEventsGroup(name="default_rms_example_group")
    grid.add_rms_events_group(event_group)
    active_power_parameter: Var | None = disturbance_model.children[0].api_obj_mapping.get(
        ParamPowerFlowReferenceType.Pl0,
        None,
    )
    if active_power_parameter is not None:
        pass
    else:
        raise AssertionError("The RMS disturbance load has no Pl0 parameter")
    grid.add_rms_event(RmsEvent(
        device=disturbance_load,
        parameter=active_power_parameter,
        time=2.0e-3,
        value=-0.15,
        group=event_group,
        force_step_alignment=True,
    ))
    return grid, load


def build_test_emt_grid() -> tuple[MultiCircuit, Load]:
    """Build the minimal EMT demo grid used by the EMT FMU import examples.

    :return: Grid and imported device.
    """

    grid: MultiCircuit = MultiCircuit(Sbase=100.0, fbase=50.0)
    bus: Bus = Bus(name="Bus0", Vnom=10.0, is_slack=True)
    grid.add_bus(bus)

    generator: Generator = Generator(name="Gen0", P=0.0, vset=1.0, Snom=900.0, x1=0.2, r1=0.01)
    generator_template: EmtModelTemplate = (
        get_generator_thevenin_rl_emt_template_with_ref(
            vf=grid.var_factory,
            name="emt_thevenin_source",
        )
    )
    load: Load = Load(name="ImportedLoad", P=0.0, Q=0.0)

    grid.add_generator(bus=bus, api_obj=generator)
    grid.add_load(bus=bus, api_obj=load)

    # Materialize the canonical ABC bus shell after the complete one-bus
    # topology is known, matching the established EMT scripting lifecycle.
    get_bus_emt_template(grid=grid, bus=bus)

    # The public setter propagates the bus voltage identities into the source
    # model before the real EMT problem compiles its equations.
    set_emt_model(
        device=generator,
        model=generator_template.block,
        var_factory=grid.var_factory,
    )
    return grid, load


def execute_test_rms_fmu_case(
        output_dir: Path,
        mode: FmuInterfaceMode,
        source_fmu_path: Path | None = None,
        me_input_variable_name: str = "u",
        active_power_output_name: str = "p_out",
        reactive_power_output_name: str | None = "q_out",
        worker_limits: FmiThreeWorkerHostLimits | None = None,
        static_active_power_mw: float = 10.0,
        static_reactive_power_mvar: float = 1.0,
        rms_tolerance: float = 1.0e-6,
        fmi_version: FmiVersion = FmiVersion.FMI_2_0,
) -> tuple[RmsSimulationDriver, Load, Path]:
    """Execute one RMS FMU integration case through the product API.

    This test-only orchestration is intentionally independent from external
    benchmark packages so product tests depend only on owned fixtures.

    :param output_dir: Isolated directory for the FMU and native staging files.
    :param mode: FMI interface mode exercised by the integration test.
    :param source_fmu_path: Optional prebuilt FMU used instead of local export.
    :param me_input_variable_name: Model Exchange voltage-input variable name.
    :param active_power_output_name: Active-power output variable name.
    :param reactive_power_output_name: Optional reactive-power output variable
        name. ``None`` leaves reactive power outside the imported shell.
    :param worker_limits: Explicit FMI 3 native-worker supervision policy.
    :param static_active_power_mw: Load active power used by the initial power flow.
    :param static_reactive_power_mvar: Load reactive power used by the initial power flow.
    :param rms_tolerance: RMS nonlinear convergence tolerance for this fixture.
    :param fmi_version: FMI generation used by a locally exported fixture.
    :return: Completed RMS driver, attached load, and generated FMU path.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    input_bindings: tuple[FmuRefBinding, ...]
    if mode == FmuInterfaceMode.CO_SIMULATION:
        if source_fmu_path is None:
            fmu_path: Path = export_test_rms_cs_fmu(output_dir, fmi_version)
        else:
            fmu_path = source_fmu_path.resolve()
        input_bindings = tuple()
    elif mode == FmuInterfaceMode.MODEL_EXCHANGE:
        if source_fmu_path is None:
            fmu_path = export_test_rms_me_fmu(output_dir, fmi_version)
        else:
            fmu_path = source_fmu_path.resolve()
        input_bindings = (
            FmuRefBinding(
                VarPowerFlowReferenceType.Vm,
                me_input_variable_name,
            ),
        )
    else:
        raise ValueError(f"Unsupported RMS FMI test mode: {mode.value}")

    grid: MultiCircuit
    load: Load
    grid, load = build_test_rms_grid()
    load.P = float(static_active_power_mw)
    load.Q = float(static_reactive_power_mvar)
    power_flow_driver: PowerFlowDriver = PowerFlowDriver(
        grid=grid,
        options=build_test_power_flow_options(),
    )
    power_flow_driver.run()
    if power_flow_driver.results.converged:
        pass
    else:
        raise RuntimeError("The RMS FMU integration test power flow did not converge")

    # The FMU replaces one load, so its pre-runtime fallback must represent
    # that device alone.  Using Sbus here would also include the disturbance
    # load connected to the same bus and would double-count its contribution.
    device_active_power: float = -float(load.P) / float(grid.Sbase)
    device_reactive_power: float = -float(load.Q) / float(grid.Sbase)
    output_bindings: tuple[FmuRefBinding, ...]
    output_defaults: tuple[FmuReferenceValue, ...]
    if reactive_power_output_name is None:
        # A scalar FMU is a single physical signal. Keep it bound once instead
        # of duplicating one native value as unrelated active and reactive power.
        output_bindings = (
            FmuRefBinding(
                VarPowerFlowReferenceType.P,
                active_power_output_name,
            ),
        )
        output_defaults = (
            FmuReferenceValue(
                VarPowerFlowReferenceType.P,
                device_active_power,
            ),
        )
    else:
        output_bindings = (
            FmuRefBinding(
                VarPowerFlowReferenceType.P,
                active_power_output_name,
            ),
            FmuRefBinding(
                VarPowerFlowReferenceType.Q,
                reactive_power_output_name,
            ),
        )
        output_defaults = (
            FmuReferenceValue(
                VarPowerFlowReferenceType.P,
                device_active_power,
            ),
            FmuReferenceValue(
                VarPowerFlowReferenceType.Q,
                device_reactive_power,
            ),
        )

    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=fmu_path,
        domain=FmuDeviceDomain.RMS,
        mode=mode,
        input_bindings=input_bindings,
        output_bindings=output_bindings,
        output_defaults=output_defaults,
        extraction_root=output_dir,
        worker_limits=worker_limits,
    )
    attach_fmu_to_device(load, grid, request)

    rms_driver: RmsSimulationDriver = RmsSimulationDriver(
        grid=grid,
        options=RmsOptions(
            time_step=1.0e-3,
            simulation_time=5.0e-3,
            tolerance=rms_tolerance,
            integration_method=DynamicIntegrationMethod.DaeBackEuler,
            max_iter=50,
        ),
        pf_results=power_flow_driver.results,
    )
    rms_driver.run()
    return rms_driver, load, fmu_path


def execute_test_emt_fmu_case(
        output_dir: Path,
        mode: FmuInterfaceMode,
        solver_tpe: EmtSolverTypes = EmtSolverTypes.Symbolic,
        fmi_version: FmiVersion = FmiVersion.FMI_2_0,
        emt_tolerance: float = 1.0e-6,
) -> tuple[EmtSimulationDriver, Load, Path]:
    """Execute one EMT FMU integration case through the product API.

    :param output_dir: Isolated directory for the FMU and native staging files.
    :param mode: FMI interface mode exercised by the integration test.
    :param solver_tpe: EMT Jacobian backend exercised by the integration test.
    :param fmi_version: FMI generation exported and reimported by the test.
    :param emt_tolerance: Outer EMT residual tolerance; existing callers retain 1e-6.
    :return: Completed EMT driver, attached load, and generated FMU path.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    phase_a_input_name: str
    if mode == FmuInterfaceMode.CO_SIMULATION:
        fmu_path: Path = export_test_emt_cs_fmu(output_dir, fmi_version)
        phase_a_input_name = "v_a_in"
    elif mode == FmuInterfaceMode.MODEL_EXCHANGE:
        fmu_path = export_test_emt_me_fmu(output_dir, fmi_version)
        phase_a_input_name = "u"
    else:
        raise ValueError(f"Unsupported EMT FMI test mode: {mode.value}")

    grid: MultiCircuit
    load: Load
    grid, load = build_test_emt_grid()
    grid.add_emt_events_group(EmtEventsGroup(name="default_emt_test_group"))
    power_flow_driver: PowerFlowDriver = PowerFlowDriver(
        grid=grid,
        options=build_test_power_flow_options(),
    )
    power_flow_driver.run()
    if power_flow_driver.results.converged:
        pass
    else:
        raise RuntimeError("The EMT FMU integration test power flow did not converge")

    # FMI 3 native calls stay inside the supervised worker envelope, while
    # the legacy FMI 1/2 runtimes retain their in-process lifecycle.
    worker_limits: FmiThreeWorkerHostLimits | None
    if fmi_version == FmiVersion.FMI_3_0:
        worker_limits = FmiThreeWorkerHostLimits(
            maximum_frame_size=262144,
            maximum_float64_values_per_request=64,
            response_timeout_seconds=60.0,
            graceful_join_timeout_seconds=10.0,
            terminate_join_timeout_seconds=5.0,
            kill_join_timeout_seconds=5.0,
        )
    elif fmi_version in (FmiVersion.FMI_1_0, FmiVersion.FMI_2_0):
        worker_limits = None
    else:
        raise ValueError(f"Unsupported EMT FMI test version: {fmi_version.value}")

    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=fmu_path,
        domain=FmuDeviceDomain.EMT,
        mode=mode,
        input_bindings=(
            FmuRefBinding(VarPowerFlowReferenceType.v_A, phase_a_input_name),
            FmuRefBinding(VarPowerFlowReferenceType.v_B, "v_b_in"),
            FmuRefBinding(VarPowerFlowReferenceType.v_C, "v_c_in"),
        ),
        output_bindings=(
            FmuRefBinding(VarPowerFlowReferenceType.i_A, "i_a_out"),
            FmuRefBinding(VarPowerFlowReferenceType.i_B, "i_b_out"),
            FmuRefBinding(VarPowerFlowReferenceType.i_C, "i_c_out"),
        ),
        output_defaults=(
            FmuReferenceValue(VarPowerFlowReferenceType.i_A, 0.0),
            FmuReferenceValue(VarPowerFlowReferenceType.i_B, 0.0),
            FmuReferenceValue(VarPowerFlowReferenceType.i_C, 0.0),
        ),
        extraction_root=output_dir,
        worker_limits=worker_limits,
    )
    attach_fmu_to_device(load, grid, request)

    if mode == FmuInterfaceMode.MODEL_EXCHANGE:
        integration_method: DynamicIntegrationMethod = (
            DynamicIntegrationMethod.DaeBackEuler
        )
    else:
        integration_method = DynamicIntegrationMethod.DaeTrapezoidal
    emt_driver: EmtSimulationDriver = EmtSimulationDriver(
        grid=grid,
        options=EmtOptions(
            time_step=5.0e-6,
            simulation_time=1.0e-3,
            tolerance=emt_tolerance,
            solver_type=solver_tpe,
            integration_method=integration_method,
            initialization_method=EmtInitializationMethod.Auto,
            verbose=0,
        ),
        pf_results=power_flow_driver.results,
        pf_results_3ph=None,
    )
    emt_driver.run()
    return emt_driver, load, fmu_path
