"""Physical terminal powers, mapping and solved startup of the polar Line."""

from pathlib import Path

import numpy as np
import pytest

from VeraGridEngine.api import power_flow
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import assign_static_api_object_mapping_for_device
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, VarPowerFlowReferenceType
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.IO.file_save import FileSave
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx_vectorized import BackEulerImplicitIntegrationVec
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae_vectorized import RmsProblemDaeVec
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from tests.RMS.test_rms_terminal_power_assembly import build_supported_vectorized_ac_load_case


@pytest.mark.parametrize("from_ratio,to_ratio", ((1.0, 1.0), (0.97, 1.0), (1.0, 0.97)))
@pytest.mark.parametrize("conductance", (0.0, 0.003))
@pytest.mark.parametrize("status", (0.0, 1.0))
def test_polar_line_virtual_tap_terminal_powers(from_ratio: float, to_ratio: float,
                                              conductance: float, status: float) -> None:
    """Compare every power row with a complex physical PI primitive.

    :param from_ratio: From nominal voltage relative to 132 kV.
    :param to_ratio: To nominal voltage relative to 132 kV.
    :param conductance: Total physical shunt conductance in pu.
    :param status: Retained conduction flag, including the open state.
    :return: None.
    """
    grid: MultiCircuit = MultiCircuit()
    source: Bus = grid.add_bus(Bus(Vnom=132.0 * from_ratio))
    target: Bus = grid.add_bus(Bus(Vnom=132.0 * to_ratio))
    line: Line = grid.add_line(Line(bus_from=source, bus_to=target, r=0.01, x=0.1, b=0.002, g=conductance))
    model: Block = get_line_rms_template(grid.var_factory).block
    child: Block = model.children[0]
    mapped: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(grid, line, model, mapped, None)
    voltage_f: complex = 1.03 * np.exp(0.13j)
    voltage_t: complex = 0.96 * np.exp(-0.08j)
    # Independent terminal SI bases determine the common internal voltage.
    tap_t: float = source.Vnom / target.Vnom
    internal_f: complex = voltage_f
    internal_t: complex = voltage_t / tap_t
    series: complex = (internal_f - internal_t) / complex(line.R, line.X)
    half_shunt: complex = complex(conductance, line.B) / 2.0
    sf: complex = voltage_f * np.conj(series + half_shunt * internal_f)
    st: complex = voltage_t * np.conj((-series + half_shunt * internal_t) / tap_t)
    bindings: dict[int, float] = dict()
    parameter: Var
    value: Const
    for parameter, value in child.parameters.items():
        assert value.value is not None
        bindings[parameter.uid] = float(value.value)
    for parameter, value in mapped.items():
        assert value.value is not None
        bindings[parameter.uid] = float(value.value)
    for parameter in child.event_dict:
        bindings[parameter.uid] = status
    variable: Var
    for variable in child.algebraic_vars:
        bindings[variable.uid] = 0.0
    bindings[model.E(VarPowerFlowReferenceType.Vmf).uid] = abs(voltage_f)
    bindings[model.E(VarPowerFlowReferenceType.Vaf).uid] = float(np.angle(voltage_f))
    bindings[model.E(VarPowerFlowReferenceType.Vmt).uid] = abs(voltage_t)
    bindings[model.E(VarPowerFlowReferenceType.Vat).uid] = float(np.angle(voltage_t))
    observed: np.ndarray = np.array(tuple(-float(eq.eval_uid(bindings)) for eq in child.algebraic_eqs))
    np.testing.assert_allclose(observed, status * np.array((sf.real, sf.imag, st.real, st.imag)), rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("generic", (False, True))
@pytest.mark.parametrize("subset", (0, 1, 2, 3))
def test_line_virtual_tap_mapping_subsets(generic: bool, subset: int) -> None:
    """Map only requested owner-local slots, also through generic metadata.

    :param generic: Use the supported Line object with legacy branch metadata.
    :param subset: Bit mask selecting from/to tap declarations.
    :return: None.
    """
    grid: MultiCircuit = MultiCircuit()
    line: Line = Line(bus_from=Bus(Vnom=128.04), bus_to=Bus(Vnom=132.0), r=0.01, x=0.1)
    if generic:
        line.device_type = DeviceType.BranchDevice
    else:
        pass
    block: Block = Block()
    # The recognized legacy dispatcher selects Line by its existing matrix
    # contract. A tap-only generic adapter is outside that supported route.
    matrix_parameter: Var = grid.var_factory.add_var("Raa")
    block.parameters[matrix_parameter] = grid.var_factory.add_const(0.0)
    block.api_obj_mapping[ParamPowerFlowReferenceType.Raa] = matrix_parameter
    keys: tuple[ParamPowerFlowReferenceType, ...] = (ParamPowerFlowReferenceType.vtap_f, ParamPowerFlowReferenceType.vtap_t)
    bit: int
    key: ParamPowerFlowReferenceType
    for bit, key in enumerate(keys):
        if subset & (1 << bit):
            parameter: Var = grid.var_factory.add_var(key.name)
            block.parameters[parameter] = grid.var_factory.add_const(1.0)
            block.api_obj_mapping[key] = parameter
        else:
            pass
    mapped: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(grid, line, block, mapped, None)
    assert len(mapped) == len(block.parameters)
    for key in keys:
        requested_parameter: Var | None = block.api_obj_mapping.get(key, None)
        if requested_parameter is None:
            pass
        else:
            expected: float = 1.0 if key == ParamPowerFlowReferenceType.vtap_f else 0.97
            assert mapped[requested_parameter].value == pytest.approx(expected)
            assert block.parameters[requested_parameter].value == 1.0


@pytest.mark.parametrize("from_ratio,to_ratio", ((1.0, 1.0), (0.97, 1.0), (1.0, 0.97)))
@pytest.mark.parametrize("conductance", (0.0, 0.003))
def test_polar_line_virtual_tap_pf_initialization(from_ratio: float, to_ratio: float, conductance: float) -> None:
    """Preserve a solved PF seed through real RMS projection and first step.

    :param from_ratio: From nominal voltage relative to the fixture base.
    :param to_ratio: To nominal voltage relative to the fixture base.
    :param conductance: Total physical line shunt conductance in pu.
    :return: None.
    """
    grid: MultiCircuit
    ignored_pf: PowerFlowResults
    grid, ignored_pf = build_supported_vectorized_ac_load_case(physical_conductance=conductance)
    grid.buses[0].Vnom *= from_ratio
    grid.buses[1].Vnom *= to_ratio
    pf: PowerFlowResults = power_flow(grid=grid)
    assert pf.converged
    line: Line = grid.lines[0]
    child: Block = line.rms_model.children[0]
    mapped: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(grid, line, line.rms_model, mapped, None)
    bindings: dict[int, float] = dict()
    parameter: Var
    constant: Const
    for parameter, constant in mapped.items():
        assert constant.value is not None
        bindings[parameter.uid] = float(constant.value)
    for parameter, constant in child.event_dict.items():
        assert constant.value is not None
        bindings[parameter.uid] = float(constant.value)
    bindings[line.rms_model.E(VarPowerFlowReferenceType.Vmf).uid] = abs(pf.voltage[0])
    bindings[line.rms_model.E(VarPowerFlowReferenceType.Vaf).uid] = float(np.angle(pf.voltage[0]))
    bindings[line.rms_model.E(VarPowerFlowReferenceType.Vmt).uid] = abs(pf.voltage[1])
    bindings[line.rms_model.E(VarPowerFlowReferenceType.Vat).uid] = float(np.angle(pf.voltage[1]))
    references: tuple[VarPowerFlowReferenceType, ...] = (VarPowerFlowReferenceType.Pf, VarPowerFlowReferenceType.Qf,
                                                        VarPowerFlowReferenceType.Pt, VarPowerFlowReferenceType.Qt)
    expected: np.ndarray = np.array((pf.Sf[0].real, pf.Sf[0].imag, pf.St[0].real, pf.St[0].imag)) / grid.Sbase
    index: int
    reference: VarPowerFlowReferenceType
    for index, reference in enumerate(references):
        bindings[line.rms_model.E(reference).uid] = float(expected[index])
    # Check the untouched solved PF seed before any native projection can move it.
    assert max(abs(float(equation.eval_uid(bindings))) for equation in child.algebraic_eqs) <= 1.0e-10
    problem: RmsProblemDaeVec = RmsProblemDaeVec(grid=grid, options=RmsOptions(), pf_results=pf)
    problem.set_events_group(rms_events_group=RmsEventsGroup())
    solver: BackEulerImplicitIntegrationVec = BackEulerImplicitIntegrationVec(
        problem=problem, t0=0.0, t_end=0.001, h=0.001, max_iter=25)
    times: np.ndarray
    values: np.ndarray
    initialized: bool
    converged: bool
    times, values, initialized, converged = solver.simulate()
    assert initialized and converged and times.size >= 2
    assert np.all(np.isfinite(values))
    observed: np.ndarray = np.array(tuple(values[0, problem._uid2idx_vars[line.rms_model.E(ref).uid]] for ref in references))
    np.testing.assert_allclose(observed, expected, rtol=1e-6, atol=1e-6)
    projected: np.ndarray = np.array(tuple(
        values[0, problem._uid2idx_vars[bus.rms_model.E(VarPowerFlowReferenceType.Vm).uid]]
        * np.exp(1j * values[0, problem._uid2idx_vars[bus.rms_model.E(VarPowerFlowReferenceType.Va).uid]])
        for bus in grid.buses))
    np.testing.assert_allclose(projected, pf.voltage, rtol=1e-6, atol=1e-6)
    differentials: np.ndarray = np.zeros(problem.get_diff_var_number())
    problem.update_input_matrices_by_model(x=values[0], dx=differentials)
    assert np.max(np.abs(problem.rhs_algebraic_vec(x=values[0], dx=differentials))) <= 1.0e-6
    step_derivatives: np.ndarray = (values[-1] - values[-2]) / (times[-1] - times[-2])
    problem.update_input_matrices_by_model(x=values[-1], dx=step_derivatives)
    assert np.max(np.abs(problem.rhs_algebraic_vec(x=values[-1], dx=step_derivatives))) <= 1.0e-6
    problem.close_fmu_cs_devices()
    problem.close_fmu_me_devices()


def test_polar_line_virtual_tap_persistence(tmp_path: Path) -> None:
    """Retain modern template identity and the immutable legacy equations.

    :param tmp_path: Native archive output directory.
    :return: None.
    """
    grid: MultiCircuit = MultiCircuit()
    source: Bus = grid.add_bus(Bus(Vnom=128.04))
    target: Bus = grid.add_bus(Bus(Vnom=132.0))
    template: RmsModelTemplate = get_line_rms_template(grid.var_factory)
    grid.add_rms_model(template)
    line: Line = grid.add_line(Line(bus_from=source, bus_to=target, r=0.01, x=0.1))
    line.rms_template = template
    path: Path = tmp_path / "tapped-polar.veragrid"
    FileSave(circuit=grid, file_name=str(path)).save()
    restored: MultiCircuit = FileOpen(str(path)).open()
    loaded: Line = restored.lines[0]
    assert loaded.rms_template is restored.rms_models[0]
    assert loaded.rms_template.idtag == template.idtag
    circuit: MultiCircuit
    for circuit in (restored, restored.copy()):
        model: Block = circuit.lines[0].rms_model
        mapped: dict[Var, Const] = dict()
        assign_static_api_object_mapping_for_device(circuit, circuit.lines[0], model, mapped, None)
        child: Block = model.children[0]
        assert mapped[child.api_obj_mapping[ParamPowerFlowReferenceType.vtap_t]].value == pytest.approx(0.97)
        circuit.lines[0].rms_template = circuit.lines[0].rms_template
        assert len(circuit.lines[0].rms_model.children[0].parameters) == 6
    fixture: Path = Path(__file__).resolve().parents[1] / "data" / "dynamics" / "legacy_polar_line_virtual_taps.veragrid"
    old: MultiCircuit = FileOpen(str(fixture)).open()
    equations: tuple[str, ...] = tuple(str(eq) for eq in old.lines[0].rms_model.children[0].algebraic_eqs)
    FileSave(circuit=old, file_name=str(path)).save()
    reread: MultiCircuit = FileOpen(str(path)).open()
    assert tuple(str(eq) for eq in reread.lines[0].rms_model.children[0].algebraic_eqs) == equations
    assert ParamPowerFlowReferenceType.vtap_t not in reread.lines[0].rms_model.children[0].api_obj_mapping
