# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Model and grid builders for repository FMI comparison examples."""
from __future__ import annotations

import math
from pathlib import Path
import uuid

from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.fmu.interface import export_model_as_fmu
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.IO.fmu.config import ExportConfig, InterfaceType
from VeraGridEngine.IO.fmu.config import detect_target_platform
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model, set_rms_model
from VeraGridEngine.enumerations import BranchImpedanceMode, ParamPowerFlowReferenceType, SolverType
from examples.fmi.event_scenario import (
    RmsLoadPowerStepScenario,
    build_default_rms_load_power_step_scenario,
)

def _build_rms_cs_source_block() -> Block:
    """Build the self-contained source block used to export an example RMS CS FMU.

    :return: Example RMS CS FMU block.
    """

    x: Var = Var("x")
    dx: Var = Var("dx", base_var=x)
    p_out: Var = Var("p_out")
    q_out: Var = Var("q_out")
    u: Var = Var("u")
    return Block(
        state_vars=list((x,)),
        # A zero derivative keeps CS and ME state integration mathematically
        # identical after initialization captures the actual voltage input.
        state_eqs=list((Const(0.0),)),
        algebraic_vars=list((p_out, q_out)),
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


def _build_rms_me_source_block() -> Block:
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
        # The state captures the actual initial voltage and then remains
        # stationary, eliminating solver truncation from this comparison.
        state_eqs=list((Const(0.0),)),
        algebraic_vars=list((p_out, q_out)),
        # Both outputs expose the same voltage-driven event response as CS.
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


def _build_emt_cs_source_block() -> Block:
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


def _build_emt_me_source_block() -> Block:
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


def export_example_rms_cs_fmu(output_dir: Path) -> Path:
    """Export the self-contained RMS CS device FMU used by the example scripts.

    :param output_dir: Output directory for the generated FMU.
    :return: Generated FMU path.
    """

    unique_name: str = f"ExampleRmsCsDevice_{uuid.uuid4().hex[:8]}"
    return export_model_as_fmu(
        _build_rms_cs_source_block(),
        ExportConfig(
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_target_platform(),
            interface_type=InterfaceType.CO_SIMULATION,
            compile_binary=True,
            keep_build_dir=False,
        ),
    )


def export_example_rms_me_fmu(output_dir: Path) -> Path:
    """Export the self-contained RMS ME device FMU used by the example scripts.

    :param output_dir: Output directory for the generated FMU.
    :return: Generated FMU path.
    """

    unique_name: str = f"ExampleRmsMeDevice_{uuid.uuid4().hex[:8]}"
    return export_model_as_fmu(
        _build_rms_me_source_block(),
        ExportConfig(
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_target_platform(),
            interface_type=InterfaceType.MODEL_EXCHANGE,
            compile_binary=True,
            keep_build_dir=False,
        ),
    )


def export_example_emt_cs_fmu(output_dir: Path) -> Path:
    """Export the self-contained EMT CS device FMU used by the example scripts.

    :param output_dir: Output directory for the generated FMU.
    :return: Generated FMU path.
    """

    unique_name: str = f"ExampleEmtCsDevice_{uuid.uuid4().hex[:8]}"
    return export_model_as_fmu(
        _build_emt_cs_source_block(),
        ExportConfig(
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_target_platform(),
            interface_type=InterfaceType.CO_SIMULATION,
            compile_binary=True,
            keep_build_dir=False,
        ),
    )


def export_example_emt_me_fmu(output_dir: Path) -> Path:
    """Export the self-contained EMT ME device FMU used by the example scripts.

    :param output_dir: Output directory for the generated FMU.
    :return: Generated FMU path.
    """

    unique_name: str = f"ExampleEmtMeDevice_{uuid.uuid4().hex[:8]}"
    return export_model_as_fmu(
        _build_emt_me_source_block(),
        ExportConfig(
            model_name=unique_name,
            output_path=output_dir / f"{unique_name}.fmu",
            target_platform=detect_target_platform(),
            interface_type=InterfaceType.MODEL_EXCHANGE,
            compile_binary=True,
            keep_build_dir=False,
        ),
    )


def build_example_power_flow_options() -> PowerFlowOptions:
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


def build_rms_example_grid(
        event_time_seconds: float,
        scenario: RmsLoadPowerStepScenario | None = None,
) -> tuple[MultiCircuit, Load]:
    """Build the minimal RMS demo grid used by the RMS FMU import examples.

    :param event_time_seconds: Exact solver-aligned disturbance boundary.
    :param scenario: Maintained comparison scenario, or None for a standalone call.
    :return: Grid and imported device.
    """

    event_time_is_valid: bool = bool(
        math.isfinite(event_time_seconds)
        and event_time_seconds > 0.0
    )
    if event_time_is_valid:
        pass
    else:
        raise ValueError("RMS example event time must be finite and positive")

    # Standalone callers retain their exact finite positive time while sharing
    # only the physical defaults. Maintained evidence supplies an explicit
    # scenario and must agree before a grid object can be created.
    active_scenario: RmsLoadPowerStepScenario
    if scenario is None:
        active_scenario = build_default_rms_load_power_step_scenario()
    elif isinstance(scenario, RmsLoadPowerStepScenario):
        active_scenario = scenario.copy_validated()
        scenario_time_matches: bool = bool(
            event_time_seconds == active_scenario.event_time_seconds
        )
        if scenario_time_matches:
            pass
        else:
            raise ValueError(
                "Explicit RMS scenario and event time must match exactly"
            )
    else:
        raise TypeError("RMS example scenario has an unsupported type")

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
    disturbance_load: Load = Load(
        name="DisturbanceLoad",
        P=active_scenario.disturbance_load_initial_active_power_mw,
        Q=active_scenario.disturbance_load_initial_reactive_power_mvar,
    )

    grid.add_line(line)
    grid.add_generator(bus=bus_slack, api_obj=generator)
    grid.add_load(bus=bus_load, api_obj=load)
    grid.add_load(bus=bus_load, api_obj=disturbance_load)
    line.rms_template = get_line_rms_template(grid.var_factory)
    generator.rms_template = get_complete_generator_template_rms(grid.var_factory)

    # Use the established product load model for the physical disturbance. A
    # separate device preserves FMU ownership of the imported load outputs.
    disturbance_model: Block = get_load_rms_template(
        vfactory=grid.var_factory,
        pl0_init=active_scenario.pre_event_active_power_pu,
        ql0_init=active_scenario.pre_event_reactive_power_pu,
    ).block
    set_rms_model(
        device=disturbance_load,
        model=disturbance_model,
        var_factory=grid.var_factory,
    )
    active_power_parameter_candidate: Var | None = disturbance_model.api_obj_mapping.get(
        ParamPowerFlowReferenceType.Pl0,
        None,
    )
    if isinstance(active_power_parameter_candidate, Var):
        active_power_parameter: Var = active_power_parameter_candidate
    else:
        raise RuntimeError("Disturbance load must expose its Pl0 event parameter through the typed API mapping")

    event_group: RmsEventsGroup = RmsEventsGroup(
        name=active_scenario.event_group_name
    )
    grid.add_rms_events_group(event_group)
    grid.add_rms_event(
        RmsEvent(
            device=disturbance_load,
            parameter=active_power_parameter,
            time=event_time_seconds,
            value=active_scenario.post_event_active_power_pu,
            group=event_group,
            force_step_alignment=active_scenario.force_step_alignment,
        )
    )
    return grid, load


def build_emt_example_grid() -> tuple[MultiCircuit, Load]:
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
