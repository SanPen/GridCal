from __future__ import annotations

import copy
import math
from typing import Dict, Iterable, List, Set, Tuple

from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import (
    Block,
    build_name_to_vars_lookup,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import (
    DeviceType,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
)


def _find_named_var_recursive(block: Block, var_name: str) -> Var | None:
    """
    Find one exact symbolic variable in a block hierarchy.

    :param block: Root symbolic block.
    :param var_name: Exact DGS signal name.
    :return: Matching variable or ``None``.
    """
    variable_groups: List[Iterable[Var]] = list([
        block.in_vars,
        block.out_vars,
        block.algebraic_vars,
        block.state_vars,
        block.diff_vars,
        list(block.event_dict.keys()),
        list(block.parameters.keys()),
    ])
    variable_group: Iterable[Var]
    variable: Var
    child_block: Block
    child_result: Var | None

    # Search every explicit ownership/interface collection before descending.
    for variable_group in variable_groups:
        for variable in variable_group:
            if variable.name == var_name:
                return variable
            else:
                pass

    for child_block in block.children:
        child_result = _find_named_var_recursive(
            block=child_block,
            var_name=var_name,
        )
        if child_result is None:
            pass
        else:
            return child_result

    return None


def _append_unique_var(variables: List[Var], variable: Var) -> None:
    """
    Append one symbolic variable when its UID is not present.

    :param variables: Mutable ordered variable list.
    :param variable: Candidate symbolic variable.
    :return: None.
    """
    existing_variable: Var

    for existing_variable in variables:
        if existing_variable.uid == variable.uid:
            return
        else:
            pass
    variables.append(variable)


def _find_first_named_var_recursive(
        block: Block,
        candidate_names: Iterable[str],
) -> Var | None:
    """
    Resolve the first available signal from an ordered native alias set.

    :param block: Root symbolic block.
    :param candidate_names: PowerFactory-version signal aliases in priority order.
    :return: First matching variable or ``None``.
    """
    candidate_name: str
    candidate_var: Var | None

    for candidate_name in candidate_names:
        candidate_var = _find_named_var_recursive(
            block=block,
            var_name=candidate_name,
        )
        if candidate_var is None:
            pass
        else:
            return candidate_var
    return None


def _find_named_produced_var_recursive(
        block: Block,
        var_name: str,
) -> Var | None:
    """
    Find a named signal that is computed by the imported controller.

    :param block: Imported composite root.
    :param var_name: Exact exported signal label.
    :return: First algebraic/state producer, or ``None``.
    """
    produced_var: Var
    child_block: Block
    child_result: Var | None

    for produced_var in block.algebraic_vars:
        if produced_var.name == var_name:
            return produced_var
        else:
            pass
    for produced_var in block.state_vars:
        if produced_var.name == var_name:
            return produced_var
        else:
            pass
    for child_block in block.children:
        child_result = _find_named_produced_var_recursive(
            block=child_block,
            var_name=var_name,
        )
        if child_result is None:
            pass
        else:
            return child_result
    return None


def _connect_all_named_signal_vars(
        block: Block,
        signal_name: str,
        canonical_var: Var,
) -> None:
    """
    Consolidate every occurrence of one exported cable onto one UID.

    This includes variables referenced only by ``inc()`` equations. Such
    temporary occurrences are not necessarily promoted to a block interface,
    but they still belong to the same exact BlkSig cable.

    :param block: Imported composite root.
    :param signal_name: Exact exported cable label.
    :param canonical_var: Computed or physical variable owning the signal.
    :return: None.
    """
    vars_by_name: Dict[str, List[Var]] = build_name_to_vars_lookup(block=block)
    matching_vars: List[Var] | None = vars_by_name.get(signal_name, None)
    if matching_vars is None:
        pass
    else:
        candidate_var: Var
        for candidate_var in matching_vars:
            if candidate_var.uid == canonical_var.uid:
                pass
            else:
                block.update_model(candidate_var, canonical_var)


def _connect_all_named_input_vars(
        block: Block,
        signal_name: str,
        canonical_var: Var,
) -> int:
    """
    Connect exact named consumer ports without replacing named producers.

    PowerFactory controller frames may expose a raw equipment input such as
    ``idc_in`` and a filtered controller output named ``idc``. Restricting the
    substitution to declared inputs preserves that two-stage signal path.

    :param block: Imported composite hierarchy updated in place.
    :param signal_name: Exact consumer-port name.
    :param canonical_var: Physical equipment variable feeding the consumers.
    :return: Number of distinct input UIDs connected.
    """
    matching_inputs: List[Var] = list()
    matching_uids: Set[int] = set()
    candidate_block: Block
    input_var: Var

    # Collect first because ``update_model`` mutates interface lists throughout
    # the hierarchy and must not invalidate the traversal in progress.
    for candidate_block in block.get_all_blocks():
        for input_var in candidate_block.in_vars:
            if input_var.name == signal_name and input_var.uid not in matching_uids:
                matching_inputs.append(input_var)
                matching_uids.add(input_var.uid)
            else:
                pass

    for input_var in matching_inputs:
        block.update_model(input_var, canonical_var)

    if len(matching_inputs) > 0:
        _remove_connected_input_runtime_aliases(
            block=block,
            canonical_var=canonical_var,
        )
    else:
        pass

    return len(matching_inputs)


def _remove_connected_input_runtime_aliases(
        block: Block,
        canonical_var: Var,
) -> None:
    """
    Remove parameter ownership inherited from a connected input placeholder.

    ``Block.update_model()`` correctly substitutes an input UID in equations and
    interfaces, but it also replaces dictionary keys.  When the replacement is
    a physical algebraic output, retaining that same UID in ``event_dict`` or
    ``mode_dict`` makes the runtime-parameter compiler overwrite the algebraic
    variable mapping.  The connected physical signal must have exactly one
    storage owner, while every consumer keeps reading that UID from its input.

    :param block: Imported composite hierarchy updated in place.
    :param canonical_var: Physical algebraic variable that owns the signal.
    :return: None.
    """
    candidate_block: Block
    runtime_dictionaries: Tuple[Dict[Var, Expr | Const], ...]
    runtime_dictionary: Dict[Var, Expr | Const]
    dictionary_var: Var
    matching_keys: List[Var]

    # Remove only keys with the exact connected UID. Expressions are left
    # untouched because their consumers now intentionally reference the
    # physical algebraic variable through the normal symbolic substitution.
    for candidate_block in block.get_all_blocks():
        runtime_dictionaries = (
            candidate_block.event_dict,
            candidate_block.mode_dict,
            candidate_block.init_eqs,
        )
        for runtime_dictionary in runtime_dictionaries:
            matching_keys = list()
            for dictionary_var in runtime_dictionary.keys():
                if dictionary_var.uid == canonical_var.uid:
                    matching_keys.append(dictionary_var)
                else:
                    pass

            for dictionary_var in matching_keys:
                runtime_dictionary.pop(dictionary_var, None)


def _normalize_unowned_interface_initializers(block: Block) -> None:
    """Normalize startup equations without a solved variable owner.

    Imported ``inc()`` equations may initialize a held controller input that
    has no algebraic, state or differential owner. Such an input belongs to the
    runtime parameter store. A target absent from every interface is dead
    import residue and must not enter the explicit initialization graph.

    :param block: Adapted converter block hierarchy.
    :return: None.
    """
    owned_var_uids: Set[int] = set()
    candidate_block: Block
    owned_var: Var

    for candidate_block in block.get_all_blocks():
        for owned_var in candidate_block.algebraic_vars:
            owned_var_uids.add(owned_var.uid)
        for owned_var in candidate_block.state_vars:
            owned_var_uids.add(owned_var.uid)
        for owned_var in candidate_block.diff_vars:
            owned_var_uids.add(owned_var.uid)

    initial_var: Var
    initial_expr: Expr
    interface_var: Var
    for candidate_block in block.get_all_blocks():
        initial_items: List[Tuple[Var, Expr]] = list(
            candidate_block.init_eqs.items()
        )
        for initial_var, initial_expr in initial_items:
            is_declared_interface: bool = False
            interface_groups: List[List[Var]] = list([
                candidate_block.in_vars,
                candidate_block.out_vars,
            ])
            interface_group: List[Var]
            for interface_group in interface_groups:
                for interface_var in interface_group:
                    if interface_var is initial_var:
                        is_declared_interface = True
                    else:
                        pass
            is_unowned: bool = initial_var.uid not in owned_var_uids
            if is_unowned:
                candidate_block.init_eqs.pop(initial_var, None)
                if is_declared_interface:
                    candidate_block.event_dict[initial_var] = initial_expr
                else:
                    pass
            else:
                pass


def _get_dgs_terminal_signal_name(variable: Var) -> str:
    """
    Return the terminal DSL name without its humanized block prefix.

    :param variable: Imported symbolic variable.
    :return: Terminal signal or parameter name.
    """
    name_parts: List[str] = variable.name.rsplit("__", 1)
    if len(name_parts) == 2:
        terminal_name: str = name_parts[1]
    else:
        terminal_name = variable.name
    return terminal_name


def _find_modulation_initialization_dependencies(
        block: Block,
        modulation_output: Var,
        voltage_component_name: str,
) -> Tuple[Var, Var, Var, Var] | None:
    """
    Resolve the variables in a native modulation-factor ``inc()`` equation.

    The lookup is anchored on the exact output UID and then classifies only the
    dependencies of that exported equation. This avoids choosing an unrelated
    equal-named signal from another operating-mode branch.

    :param block: Imported controller hierarchy.
    :param modulation_output: Exact ``Pmr`` or ``Pmi`` equipment input.
    :param voltage_component_name: Expected Cartesian controller signal name.
    :return: ``(uconv, udc_ltd, Uacn, Udcn)`` or ``None``.
    """
    candidate_block: Block
    initial_var: Var
    initial_expr: Expr

    for candidate_block in block.get_all_blocks():
        for initial_var, initial_expr in candidate_block.init_eqs.items():
            if initial_var.uid == modulation_output.uid:
                variables_by_terminal_name: Dict[str, Var] = dict()
                expression_var: Var
                for expression_var in initial_expr.get_vars():
                    terminal_name: str = _get_dgs_terminal_signal_name(
                        variable=expression_var,
                    )
                    if terminal_name in variables_by_terminal_name:
                        pass
                    else:
                        variables_by_terminal_name[terminal_name] = expression_var
                voltage_component: Var | None = variables_by_terminal_name.get(
                    voltage_component_name,
                    None,
                )
                limited_dc_voltage: Var | None = variables_by_terminal_name.get(
                    "udc_ltd",
                    None,
                )
                ac_nominal_voltage: Var | None = variables_by_terminal_name.get(
                    "Uacn",
                    None,
                )
                dc_nominal_voltage: Var | None = variables_by_terminal_name.get(
                    "Udcn",
                    None,
                )
                dependencies_ready: bool = (
                        voltage_component is not None
                        and limited_dc_voltage is not None
                        and ac_nominal_voltage is not None
                        and dc_nominal_voltage is not None
                )
                if dependencies_ready:
                    return (
                        voltage_component,
                        limited_dc_voltage,
                        ac_nominal_voltage,
                        dc_nominal_voltage,
                    )
                else:
                    pass
            else:
                pass
    return None


def _find_equal_named_initialization_sources(
        block: Block,
        target_var: Var,
) -> List[Var]:
    """
    Find equal-named branch variables feeding one exact initialized output.

    PowerFactory operating-mode selectors commonly choose between islanded and
    non-islanded signals that intentionally share the exported terminal name.
    The target UID anchors the search to the correct selector equation; source
    UIDs are then collected only from that equation, never from the wider model.

    :param block: Imported controller hierarchy.
    :param target_var: Exact selector output variable.
    :return: Distinct equal-named source variables in expression order.
    """
    result: List[Var] = list()
    target_terminal_name: str = _get_dgs_terminal_signal_name(
        variable=target_var,
    )
    candidate_block: Block
    initial_var: Var
    initial_expr: Expr

    for candidate_block in block.get_all_blocks():
        for initial_var, initial_expr in candidate_block.init_eqs.items():
            if initial_var.uid == target_var.uid:
                expression_var: Var
                for expression_var in initial_expr.get_vars():
                    source_terminal_name: str = _get_dgs_terminal_signal_name(
                        variable=expression_var,
                    )
                    is_equal_named_source: bool = (
                            expression_var.uid != target_var.uid
                            and source_terminal_name == target_terminal_name
                    )
                    if is_equal_named_source:
                        _append_unique_var(
                            variables=result,
                            variable=expression_var,
                        )
                    else:
                        pass
                return result
            else:
                pass
    return result


def _find_direct_initialization_assignments(
        block: Block,
        target_name: str,
        source_name: str,
) -> List[Tuple[Var, Expr]]:
    """
    Find exported direct ``inc(target)=source`` assignments by exact UID.

    Composite controllers can initialize a connected cable from its consumer
    side. When the producer also exports a circular ``inc()`` equation, the
    physical consumer assignment must be retained at the equipment shell so it
    wins deterministically while the hierarchy is flattened.

    :param block: Imported controller hierarchy.
    :param target_name: Terminal name of the initialized cable.
    :param source_name: Terminal name of its physical measurement source.
    :return: Matching target variables and their exported expressions.
    """
    result: List[Tuple[Var, Expr]] = list()
    candidate_block: Block
    initial_var: Var
    initial_expr: Expr

    for candidate_block in block.get_all_blocks():
        for initial_var, initial_expr in candidate_block.init_eqs.items():
            initial_terminal_name: str = _get_dgs_terminal_signal_name(
                variable=initial_var,
            )
            expression_vars: List[Var] = initial_expr.get_vars()
            is_direct_assignment: bool = (
                    initial_terminal_name == target_name
                    and len(expression_vars) == 1
                    and _get_dgs_terminal_signal_name(
                variable=expression_vars[0],
            ) == source_name
            )
            if is_direct_assignment:
                result.append((initial_var, initial_expr))
            else:
                pass
    return result


def _bind_direct_initialization_alias_to_equipment_signal(
        block: Block,
        target_var: Var,
        equipment_signal: Expr,
) -> int:
    """
    Replace exact ``inc(target)`` runtime aliases with an equipment signal.

    PowerFactory exports ``inc(mdc)`` as a controller-side initialization
    cable.  When the simplified MMC branch is active, the generated runtime
    selector reads that cable back and would otherwise reduce to ``mdc=mdc``.
    The native ``ElmVsc`` equipment supplies the missing operating quantity
    from its physical DC terminals.  Binding only the exact ``*_inc`` alias
    preserves detailed controller branches while closing the simplified one.

    :param block: Imported controller hierarchy updated in place.
    :param target_var: Exact equipment input initialized by the DGS cable.
    :param equipment_signal: Physical replacement expression.
    :return: Number of exact aliases bound.
    """
    bound_count: int = 0
    runtime_block: Block
    event_var: Var
    event_expr: Expr

    # Inspect each retained DGS block because ``inc()`` aliases belong to the
    # precise child that declared them, not necessarily to the composite root.
    for runtime_block in block.get_all_blocks():
        for event_var, event_expr in runtime_block.event_dict.items():
            terminal_name: str = _get_dgs_terminal_signal_name(event_var)
            is_exact_initialization_alias: bool = (
                    terminal_name.endswith("_inc")
                    and isinstance(event_expr, Var)
                    and event_expr.uid == target_var.uid
            )
            if is_exact_initialization_alias:
                runtime_block.event_dict[event_var] = equipment_signal
                bound_count += 1
            else:
                pass
    return bound_count


def is_dgs_elmvsc_slot_contract(block: Block) -> bool:
    """
    Detect the native PowerFactory ``ElmVsc`` composite-slot contract.

    This helper validates one already isolated equipment boundary. It never
    searches children: unrelated controller signals cannot establish a VSC
    contract. The automatic DGS path additionally proves the boundary's typed
    BlkSlot and equipment FID before invoking the runtime adapter.

    :param block: Imported DGS composite root.
    :return: ``True`` when one direct slot exposes the supported ElmVsc shell.
    """
    input_names: List[str] = list()
    output_names: List[str] = list()
    boundary_var: Var
    for boundary_var in block.in_vars:
        input_names.append(boundary_var.name)
    for boundary_var in block.out_vars:
        output_names.append(boundary_var.name)
    input_name_set: Set[str] = set(input_names)
    output_name_set: Set[str] = set(output_names)
    dc_current_count: int = int("iDC" in output_name_set) + int(
        "idc" in output_name_set
    )
    cell_voltage_count: int = int("yUcell" in output_name_set) + int(
        "Ucap" in output_name_set
    )
    return (
        len(input_names) == len(input_name_set)
        and len(output_names) == len(output_name_set)
        and input_name_set.isdisjoint(output_name_set)
        and {"Pmr", "Pmi", "mdc"}.issubset(input_name_set)
        and dc_current_count == 1
        and cell_voltage_count == 1
    )


def _get_dgs_elmvscmono_angle_signal_names(
        block: Block,
) -> Tuple[str, str] | None:
    """
    Resolve the angle-vector port names declared by the native VSC slot.

    PowerFactory DGS versions expose the same unit-vector contract as either
    ``cosphi/sinphi`` or ``cosref/sinref``. The exact host FID and the remaining
    bridge ports disambiguate the structural match.

    :param block: Imported DGS composite root.
    :return: Exact cosine/sine port-name pair, or ``None``.
    """
    required_names: Tuple[str, ...] = ("Pmd", "Pmq", "id", "iq", "uDC")
    required_name: str
    for required_name in required_names:
        if _find_named_var_recursive(block=block, var_name=required_name) is None:
            return None
        else:
            pass

    cosphi: Var | None = _find_named_var_recursive(block=block, var_name="cosphi")
    sinphi: Var | None = _find_named_var_recursive(block=block, var_name="sinphi")
    if cosphi is not None and sinphi is not None:
        result: Tuple[str, str] | None = "cosphi", "sinphi"
    else:
        cosref: Var | None = _find_named_var_recursive(block=block, var_name="cosref")
        sinref: Var | None = _find_named_var_recursive(block=block, var_name="sinref")
        if cosref is not None and sinref is not None:
            result = "cosref", "sinref"
        else:
            result = None
    return result


def is_dgs_elmvscmono_slot_contract(block: Block) -> bool:
    """
    Detect the native monopolar ``VSC_Frame`` equipment-slot contract.

    The contract is intentionally directional and local to this boundary. No
    recursive child search, project, object or template display name
    participates in the decision.

    :param block: Imported DGS composite root.
    :return: ``True`` for a complete native monopolar converter slot.
    """
    input_names: List[str] = list()
    output_names: List[str] = list()
    boundary_var: Var
    for boundary_var in block.in_vars:
        input_names.append(boundary_var.name)
    for boundary_var in block.out_vars:
        output_names.append(boundary_var.name)
    input_name_set: Set[str] = set(input_names)
    output_name_set: Set[str] = set(output_names)
    has_angle_inputs: bool = bool(
        {"cosphi", "sinphi"}.issubset(input_name_set)
        or {"cosref", "sinref"}.issubset(input_name_set)
    )
    return (
        len(input_names) == len(input_name_set)
        and len(output_names) == len(output_name_set)
        and input_name_set.isdisjoint(output_name_set)
        and {"Pmd", "Pmq"}.issubset(input_name_set)
        and {"id", "iq", "uDC"}.issubset(output_name_set)
        and has_angle_inputs
    )


def build_dgs_elmvscmono_rms_runtime_template(
        control_template: RmsModelTemplate,
        clone_control_block: bool = True,
) -> RmsModelTemplate | None:
    """
    Wrap a native monopolar controller with its exported VSC bridge model.

    ``Pmd`` and ``Pmq`` are modulation-voltage orders. The bridge converts them
    to an internal dq voltage, solves the exported ``Pcu``/``uk`` reactor, and
    returns the physical ``id``/``iq`` measurements consumed by the controller.
    This prevents the invalid shortcut of treating modulation as current.

    :param control_template: Imported DGS composite template.
    :param clone_control_block: Clone reusable GUI input before adaptation.
    :return: Assignable monopolar VSC template, or ``None`` if incomplete.
    """
    control_block: Block
    if clone_control_block:
        control_block = copy.deepcopy(control_template.block)
    else:
        control_block = control_template.block
    angle_signal_names: Tuple[str, str] | None = (
        _get_dgs_elmvscmono_angle_signal_names(block=control_block)
    )
    pmd: Var | None = _find_named_produced_var_recursive(control_block, "Pmd")
    pmq: Var | None = _find_named_produced_var_recursive(control_block, "Pmq")
    if angle_signal_names is None:
        cosref: Var | None = None
        sinref: Var | None = None
    else:
        cosref = _find_named_var_recursive(control_block, angle_signal_names[0])
        sinref = _find_named_var_recursive(control_block, angle_signal_names[1])
    current_d_port: Var | None = _find_named_var_recursive(control_block, "id")
    current_q_port: Var | None = _find_named_var_recursive(control_block, "iq")
    controller_dc_voltage_port: Var | None = _find_named_var_recursive(
        control_block,
        "uDC",
    )
    required_vars_ready: bool = (
            pmd is not None
            and pmq is not None
            and cosref is not None
            and sinref is not None
            and current_d_port is not None
            and current_q_port is not None
            and controller_dc_voltage_port is not None
    )
    if not required_vars_ready:
        return None
    else:
        pass

    # The explicit contract check makes every physical port non-optional here.
    pmd_var: Var = pmd
    pmq_var: Var = pmq
    cosref_var: Var = cosref
    sinref_var: Var = sinref
    current_d_var: Var = Var(name="id")
    current_q_var: Var = Var(name="iq")
    controller_dc_voltage_var: Var = Var(name="uDC")

    _connect_all_named_signal_vars(
        block=control_block,
        signal_name="Pmd",
        canonical_var=pmd_var,
    )
    _connect_all_named_signal_vars(
        block=control_block,
        signal_name="Pmq",
        canonical_var=pmq_var,
    )
    _connect_all_named_signal_vars(
        block=control_block,
        signal_name=angle_signal_names[0],
        canonical_var=cosref_var,
    )
    _connect_all_named_signal_vars(
        block=control_block,
        signal_name=angle_signal_names[1],
        canonical_var=sinref_var,
    )

    # A native equipment output fans out to several controller input ports.
    # Consolidate those exact named consumers onto the one physical bridge
    # variable before adding equations, so initialization and runtime share UID.
    _connect_all_named_signal_vars(
        block=control_block,
        signal_name="id",
        canonical_var=current_d_var,
    )
    _connect_all_named_signal_vars(
        block=control_block,
        signal_name="iq",
        canonical_var=current_q_var,
    )
    _connect_all_named_signal_vars(
        block=control_block,
        signal_name="uDC",
        canonical_var=controller_dc_voltage_var,
    )

    dc_voltage: Var = Var(
        name="Vdc_monopolar",
        reference=VarPowerFlowReferenceType.Vf_dc,
    )
    ac_voltage_magnitude: Var = Var(
        name="Vac_magnitude",
        reference=VarPowerFlowReferenceType.Vmt,
    )
    ac_voltage_angle: Var = Var(
        name="Vac_angle",
        reference=VarPowerFlowReferenceType.Vat,
    )
    dc_power: Var = Var(name="Pdc", reference=VarPowerFlowReferenceType.Pf)
    dc_conversion_power: Var = Var(name="Pdc_conversion")
    ac_active_power: Var = Var(name="Pac", reference=VarPowerFlowReferenceType.Pt)
    ac_reactive_power: Var = Var(name="Qac", reference=VarPowerFlowReferenceType.Qt)
    ac_current_magnitude: Var = Var(name="Iac", reference=VarPowerFlowReferenceType.Im)
    network_dc_current: Var = Var(
        name="Idc_network",
        reference=VarPowerFlowReferenceType.Idc,
    )
    resistance: Var = Var(name="elmvscmono_reactor_r_pu")
    reactance: Var = Var(name="elmvscmono_reactor_x_pu")
    modulation_gain: Var = Var(name="elmvscmono_modulation_gain")
    dc_bus_to_controller_gain: Var = Var(name="elmvscmono_dc_voltage_gain")
    converter_to_system_power_gain: Var = Var(
        name="elmvscmono_converter_to_system_power_gain",
    )
    epsilon: Var = Var(name="elmvscmono_epsilon")

    # Rotate the network voltage into the exact reference frame exported by
    # PowerFactory. cosref/sinref are controller outputs, not inferred angles.
    ac_voltage_real = ac_voltage_magnitude * sym.cos(ac_voltage_angle)
    ac_voltage_imag = ac_voltage_magnitude * sym.sin(ac_voltage_angle)
    voltage_d = ac_voltage_real * cosref_var + ac_voltage_imag * sinref_var
    voltage_q = -ac_voltage_real * sinref_var + ac_voltage_imag * cosref_var
    converter_voltage_d = (
            modulation_gain * controller_dc_voltage_var * pmd_var
    )
    converter_voltage_q = (
            modulation_gain * controller_dc_voltage_var * pmq_var
    )
    converter_active_power = voltage_d * current_d_var + voltage_q * current_q_var
    converter_reactive_power = voltage_q * current_d_var - voltage_d * current_q_var
    voltage_squared = (
            voltage_d * voltage_d + voltage_q * voltage_q + epsilon
    )
    # The load-flow P/Q solution is the physical equipment operating point.
    # Resolve its dq current in the controller reference frame instead of
    # guessing current from not-yet-initialized controller modulation orders.
    initialized_current_d = (
                                    -voltage_d * ac_active_power - voltage_q * ac_reactive_power
                            ) / (converter_to_system_power_gain * voltage_squared)
    initialized_current_q = (
                                    -voltage_q * ac_active_power + voltage_d * ac_reactive_power
                            ) / (converter_to_system_power_gain * voltage_squared)
    initialized_modulation_d = (
                                       voltage_d
                                       + resistance * current_d_var
                                       - reactance * current_q_var
                               ) / (modulation_gain * controller_dc_voltage_var + epsilon)
    initialized_modulation_q = (
                                       voltage_q
                                       + reactance * current_d_var
                                       + resistance * current_q_var
                               ) / (modulation_gain * controller_dc_voltage_var + epsilon)
    # PowerFactory's no-load conduction term is a shunt loss at the aggregate
    # cell voltage, so its power scales with Ucap squared. The current-based
    # linear and quadratic terms retain their exported ElmVsc definitions.
    converter_loss = (
            resistance
            * (current_d_var * current_d_var + current_q_var * current_q_var)
            * converter_to_system_power_gain
    )

    wrapper_inputs: List[Var] = list([
        dc_voltage,
        ac_voltage_magnitude,
        ac_voltage_angle,
    ])
    controller_input: Var
    for controller_input in control_block.in_vars:
        _append_unique_var(wrapper_inputs, controller_input)

    wrapper_outputs: List[Var] = list()
    controller_output: Var
    for controller_output in control_block.out_vars:
        _append_unique_var(wrapper_outputs, controller_output)
    _append_unique_var(wrapper_outputs, current_d_var)
    _append_unique_var(wrapper_outputs, current_q_var)
    _append_unique_var(wrapper_outputs, controller_dc_voltage_var)

    wrapper_block: Block = Block(
        name=control_template.name,
        children=list([control_block]),
        in_vars=wrapper_inputs,
        out_vars=wrapper_outputs,
        algebraic_vars=list([
            current_d_var,
            current_q_var,
            controller_dc_voltage_var,
            dc_power,
            dc_conversion_power,
            ac_active_power,
            ac_reactive_power,
            ac_current_magnitude,
            network_dc_current,
        ]),
        algebraic_eqs=list([
            # Vconv - Vgrid = (R + jX) I on the converter equipment base.
            converter_voltage_d
            - voltage_d
            - resistance * current_d_var
            + reactance * current_q_var,
            converter_voltage_q
            - voltage_q
            - reactance * current_d_var
            - resistance * current_q_var,
            controller_dc_voltage_var - dc_voltage * dc_bus_to_controller_gain,
            ac_active_power
            + converter_active_power * converter_to_system_power_gain,
            ac_reactive_power
            + converter_reactive_power * converter_to_system_power_gain,
            ac_current_magnitude
            - sym.sqrt(
                current_d_var * current_d_var
                + current_q_var * current_q_var
                + epsilon
            ) * converter_to_system_power_gain,
            # The adapter mappings use power injected into the surrounding AC
            # and DC networks. Their sum therefore equals the positive copper
            # loss: Pdc + Pac - Ploss = 0. This reproduces both transfer
            # directions of the exported m:P:busdc/m:P:busac convention.
            dc_conversion_power + ac_active_power - converter_loss,
            # During device-local initialization the terminal and conversion
            # powers coincide.  The global RMS compiler replaces this observer
            # equation with Pterminal = Pconversion + Cdc*Vdc*dVdc/dt after it
            # has assembled the complete nodal DC power balance.
            dc_power - dc_conversion_power,
            network_dc_current - dc_power / (dc_voltage + epsilon),
        ]),
        event_dict=dict([
            (resistance, Const(0.0)),
            (reactance, Const(0.0)),
            (modulation_gain, Const(1.0)),
            (dc_bus_to_controller_gain, Const(1.0)),
            (converter_to_system_power_gain, Const(1.0)),
            (epsilon, Const(1.0e-9)),
        ]),
        external_mapping=dict([
            (VarPowerFlowReferenceType.Vf_dc, dc_voltage),
            (VarPowerFlowReferenceType.Vmt, ac_voltage_magnitude),
            (VarPowerFlowReferenceType.Vat, ac_voltage_angle),
            (VarPowerFlowReferenceType.Pf, dc_power),
            (VarPowerFlowReferenceType.Pt, ac_active_power),
            (VarPowerFlowReferenceType.Qt, ac_reactive_power),
            (VarPowerFlowReferenceType.Idc, network_dc_current),
            (VarPowerFlowReferenceType.Im, ac_current_magnitude),
        ]),
        init_eqs=dict([
            (
                controller_dc_voltage_var,
                dc_voltage * dc_bus_to_controller_gain,
            ),
            # PowerFactory initializes the controller orders consistently with
            # the solved equipment current. These equations reproduce that
            # bridge contract from DGS topology, parameters and the load flow.
            (pmd_var, initialized_modulation_d),
            (pmq_var, initialized_modulation_q),
            (current_d_var, initialized_current_d),
            (current_q_var, initialized_current_q),
            # Terminal P/Q/current and network-side DC power/current are loaded
            # from the power-flow references before explicit initialization.
            # Keeping a second initialization equation for those same owners
            # would close an artificial Pac/Qac <-> id/iq dependency cycle.
            (dc_conversion_power, -ac_active_power + converter_loss),
        ]),
    )
    _normalize_unowned_interface_initializers(block=wrapper_block)
    result: RmsModelTemplate = RmsModelTemplate(name=control_template.name)
    result.name = control_template.name
    result.tpe = DeviceType.VscDevice
    result.block = wrapper_block
    return result


def configure_dgs_elmvscmono_runtime_template_for_device(
        template: RmsModelTemplate,
        device: VSC,
        system_base_mva: float,
) -> bool:
    """
    Configure a monopolar bridge from the exact imported equipment parameters.

    :param template: Adapted reusable RMS template.
    :param device: Exact DGS-associated VSC host.
    :param system_base_mva: Circuit power base in MVA.
    :return: ``True`` when every physical bridge parameter was configured.
    """
    resistance_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvscmono_reactor_r_pu",
    )
    reactance_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvscmono_reactor_x_pu",
    )
    modulation_gain_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvscmono_modulation_gain",
    )
    dc_voltage_gain_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvscmono_dc_voltage_gain",
    )
    power_gain_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvscmono_converter_to_system_power_gain",
    )
    if (
            resistance_var is None
            or reactance_var is None
            or modulation_gain_var is None
            or dc_voltage_gain_var is None
            or power_gain_var is None
    ):
        return False
    else:
        pass
    resistance_uid: int = resistance_var.uid
    reactance_uid: int = reactance_var.uid
    modulation_gain_uid: int = modulation_gain_var.uid
    dc_voltage_gain_uid: int = dc_voltage_gain_var.uid
    power_gain_uid: int = power_gain_var.uid

    ac_voltage_base_kv: float = float(device.bus_to.Vnom)
    dc_bus_voltage_base_kv: float = float(device.bus_from.Vnom)
    dc_converter_voltage_base_kv: float = float(device.dc_voltage_base)
    converter_power_base_mva: float = float(device.rate)
    physical_values_ready: bool = (
            device.bus_dc_n is None
            and ac_voltage_base_kv > 0.0
            and dc_bus_voltage_base_kv > 0.0
            and dc_converter_voltage_base_kv > 0.0
            and converter_power_base_mva > 0.0
            and system_base_mva > 0.0
            and float(device.r_series) >= 0.0
            and float(device.x_series) > 0.0
    )
    if physical_values_ready:
        pass
    else:
        return False

    modulation_gain: float = (
            math.sqrt(3.0)
            * dc_converter_voltage_base_kv
            / (2.0 * math.sqrt(2.0) * ac_voltage_base_kv)
    )
    dc_voltage_gain: float = (
            dc_bus_voltage_base_kv / dc_converter_voltage_base_kv
    )
    converter_to_system_power_gain: float = (
            converter_power_base_mva / system_base_mva
    )
    values_by_uid: Dict[int, float] = dict([
        (resistance_uid, float(device.r_series)),
        (reactance_uid, float(device.x_series)),
        (modulation_gain_uid, modulation_gain),
        (dc_voltage_gain_uid, dc_voltage_gain),
        (power_gain_uid, converter_to_system_power_gain),
    ])
    configured_uids: Set[int] = set()
    event_var: Var
    event_value: object
    for event_var, event_value in template.block.event_dict.items():
        configured_value: float | None = values_by_uid.get(event_var.uid, None)
        if isinstance(event_value, Const) and configured_value is not None:
            template.block.event_dict[event_var] = Const(configured_value)
            configured_uids.add(event_var.uid)
        else:
            pass
    return len(configured_uids) == len(values_by_uid)


def build_dgs_elmvsc_rms_runtime_template(
        control_template: RmsModelTemplate,
        clone_control_block: bool = True,
) -> RmsModelTemplate | None:
    """
    Wrap one imported controller with PowerFactory's RMS ElmVsc shell.

    ``Pmr`` and ``Pmi`` define the AC voltage phasor, ``mdc`` maps the
    pole-to-pole DC voltage to cell voltage, and the electrical network solves
    the resulting AC active/reactive power. The documented equivalent MMC
    capacitor stores any transient AC/DC power imbalance, while its steady
    state reduces to the same loss-aware power balance.

    :param control_template: Imported RMS controller root.
    :param clone_control_block: Clone reusable GUI input before adaptation.
    :return: Assignable VSC template or ``None`` for an incomplete contract.
    """
    control_block: Block
    if clone_control_block:
        control_block = copy.deepcopy(control_template.block)
    else:
        control_block = control_template.block
    pmr: Var | None = _find_named_var_recursive(control_block, "Pmr")
    pmi: Var | None = _find_named_var_recursive(control_block, "Pmi")
    mdc: Var | None = _find_named_var_recursive(control_block, "mdc")
    idc: Var | None = _find_first_named_var_recursive(
        block=control_block,
        candidate_names=("iDC", "idc"),
    )
    cell_voltage: Var | None = _find_first_named_var_recursive(
        block=control_block,
        candidate_names=("yUcell", "Ucap"),
    )
    required_vars_ready: bool = (
            pmr is not None
            and pmi is not None
            and mdc is not None
            and idc is not None
            and cell_voltage is not None
    )

    if not required_vars_ready:
        return None
    else:
        pass

    # The explicit state check above makes these assignments type-safe.
    pmr_var: Var = pmr
    pmi_var: Var = pmi
    mdc_var: Var = mdc
    # Equipment outputs can fan out through several direct ElmComp children.
    # Give each physical output one canonical UID, then replace every exact
    # equal-named slot occurrence before adding the electrical equations. This
    # is the same native-slot contract used by the monopolar adapter above.
    idc_var: Var = Var(name=idc.name)
    cell_voltage_var: Var = Var(name=cell_voltage.name)
    idc_input_connection_count: int = _connect_all_named_input_vars(
        block=control_block,
        signal_name=f"{idc.name}_in",
        canonical_var=idc_var,
    )
    if idc_input_connection_count == 0:
        # Simpler native frames expose the raw equipment output directly and
        # have no same-named filtered producer. Connect only their input ports.
        filtered_idc: Var | None = _find_named_produced_var_recursive(
            block=control_block,
            var_name=idc.name,
        )
        if filtered_idc is None:
            _connect_all_named_input_vars(
                block=control_block,
                signal_name=idc.name,
                canonical_var=idc_var,
            )
        else:
            pass
    else:
        pass
    _connect_all_named_input_vars(
        block=control_block,
        signal_name=cell_voltage.name,
        canonical_var=cell_voltage_var,
    )

    dc_positive_voltage: Var = Var(
        name="Vdc_positive",
        reference=VarPowerFlowReferenceType.Vf_dc,
    )
    dc_negative_voltage: Var = Var(
        name="Vdc_negative",
        reference=VarPowerFlowReferenceType.Vt_dc,
    )
    ac_voltage_magnitude: Var = Var(
        name="Vac_magnitude",
        reference=VarPowerFlowReferenceType.Vmt,
    )
    ac_voltage_angle: Var = Var(
        name="Vac_angle",
        reference=VarPowerFlowReferenceType.Vat,
    )
    dc_power: Var = Var(name="Pdc", reference=VarPowerFlowReferenceType.Pf)
    ac_active_power: Var = Var(name="Pac", reference=VarPowerFlowReferenceType.Pt)
    ac_reactive_power: Var = Var(name="Qac", reference=VarPowerFlowReferenceType.Qt)
    ac_current_magnitude: Var = Var(name="Iac", reference=VarPowerFlowReferenceType.Im)
    network_dc_current: Var = Var(
        name="Idc_network",
        reference=VarPowerFlowReferenceType.Idc,
    )
    # Keep a uniquely named observer at the physical ElmVsc boundary. DGS
    # composites may contain several legitimate ``idc`` variables and cable
    # consolidation can replace their original UIDs. This algebraic alias
    # therefore provides a stable, human-readable result channel without
    # changing the controller or network current equations.
    equipment_dc_current_observer: Var = Var(name="ElmVsc_iDC_equipment")
    idle_loss: Var = Var(name="elmvsc_idle_loss")
    linear_loss: Var = Var(name="elmvsc_linear_loss")
    quadratic_loss: Var = Var(name="elmvsc_quadratic_loss")
    ac_nominal_voltage: Var = Var(name="elmvsc_ac_nominal_voltage_kv")
    dc_positive_nominal_voltage: Var = Var(
        name="elmvsc_dc_positive_nominal_voltage_kv",
    )
    dc_negative_nominal_voltage: Var = Var(
        name="elmvsc_dc_negative_nominal_voltage_kv",
    )
    controller_current_power_gain: Var = Var(
        name="elmvsc_controller_current_power_gain",
    )
    reactor_resistance: Var = Var(name="elmvsc_reactor_r_system_pu")
    reactor_reactance: Var = Var(name="elmvsc_reactor_x_system_pu")
    nominal_cell_voltage: Var = Var(
        name="elmvsc_nominal_cell_voltage_kv",
    )
    equivalent_capacitance: Var = Var(
        name="elmvsc_equivalent_capacitance_uf",
    )
    system_power_base: Var = Var(
        name="elmvsc_system_power_base_mva",
    )
    epsilon: Var = Var(name="elmvsc_epsilon")
    dc_span = dc_positive_voltage - dc_negative_voltage
    physical_dc_span = (
            dc_positive_voltage * dc_positive_nominal_voltage
            - dc_negative_voltage * dc_negative_nominal_voltage
    )
    # The built-in ElmVsc initializes its aggregate cell voltage at the
    # converter nominal DC voltage.  Its physical terminal span supplies the
    # corresponding insertion index to an exported ``inc(mdc)`` cable.  This
    # is the native device/control boundary missing from the ElmDsl equations.
    _bind_direct_initialization_alias_to_equipment_signal(
        block=control_block,
        target_var=mdc_var,
        equipment_signal=physical_dc_span / nominal_cell_voltage,
    )
    converter_loss = (
            idle_loss
            * cell_voltage_var
            * cell_voltage_var
            / (nominal_cell_voltage * nominal_cell_voltage + epsilon)
            + linear_loss * ac_current_magnitude
            + quadratic_loss * ac_current_magnitude * ac_current_magnitude
    )
    # PowerFactory's fundamental-frequency MMC model stores the six arm
    # capacitor banks in one physical state. With Ceq in uF, Ucell in kV and
    # network powers in system p.u., the factor 1e6 converts the energy balance
    # to kV/s. The sign follows VeraGrid's branch convention: positive Pac and
    # Pdc enter the converter, so their surplus charges the internal capacitor.
    cell_voltage_derivative: Expr = (
            (dc_power + ac_active_power - converter_loss)
            * system_power_base
            * 1.0e6
            / (equivalent_capacitance * cell_voltage_var + epsilon)
    )
    terminal_voltage_real: Expr = (
            ac_voltage_magnitude * sym.cos(ac_voltage_angle)
    )
    terminal_voltage_imaginary: Expr = (
            ac_voltage_magnitude * sym.sin(ac_voltage_angle)
    )
    terminal_voltage_squared: Expr = (
            ac_voltage_magnitude * ac_voltage_magnitude + epsilon
    )
    converter_current_real: Expr = (
                                           ac_active_power * terminal_voltage_real
                                           + ac_reactive_power * terminal_voltage_imaginary
                                   ) / terminal_voltage_squared
    converter_current_imaginary: Expr = (
                                                ac_active_power * terminal_voltage_imaginary
                                                - ac_reactive_power * terminal_voltage_real
                                        ) / terminal_voltage_squared
    internal_voltage_real: Expr = (
            terminal_voltage_real
            - reactor_resistance * converter_current_real
            + reactor_reactance * converter_current_imaginary
    )
    internal_voltage_imaginary: Expr = (
            terminal_voltage_imaginary
            - reactor_reactance * converter_current_real
            - reactor_resistance * converter_current_imaginary
    )

    wrapper_inputs: List[Var] = list([
        dc_positive_voltage,
        dc_negative_voltage,
        ac_voltage_magnitude,
        ac_voltage_angle,
    ])
    controller_input: Var
    for controller_input in control_block.in_vars:
        _append_unique_var(wrapper_inputs, controller_input)

    wrapper_outputs: List[Var] = list()
    controller_output: Var
    for controller_output in control_block.out_vars:
        _append_unique_var(wrapper_outputs, controller_output)
    _append_unique_var(wrapper_outputs, idc_var)
    _append_unique_var(wrapper_outputs, cell_voltage_var)
    _append_unique_var(wrapper_outputs, equipment_dc_current_observer)

    wrapper_block: Block = Block(
        name=control_template.name,
        children=list([control_block]),
        in_vars=wrapper_inputs,
        out_vars=wrapper_outputs,
        algebraic_vars=list([
            idc_var,
            equipment_dc_current_observer,
            network_dc_current,
            dc_power,
            ac_active_power,
            ac_reactive_power,
            ac_current_magnitude,
        ]),
        state_vars=list([cell_voltage_var]),
        state_eqs=list([cell_voltage_derivative]),
        algebraic_eqs=list([
            # The two Cartesian equations preserve angle quadrants without an
            # atan2 primitive and implement sqrt(3/8)*Ucell*(Pmr+j*Pmi).
            # VeraGrid branch power is positive from the converter towards the
            # AC grid, while the imported dq controller current is positive in
            # the opposite direction.  Therefore the controller reactor drop
            # is subtracted from the network-oriented current phasor.
            internal_voltage_real
            - math.sqrt(3.0 / 8.0)
            * cell_voltage_var
            * pmr_var
            / ac_nominal_voltage,
            internal_voltage_imaginary
            - math.sqrt(3.0 / 8.0)
            * cell_voltage_var
            * pmi_var
            / ac_nominal_voltage,
            # PowerFactory exposes yUcell/Ucap in kV. During initialization it
            # starts from the converter nominal DC voltage, while at runtime
            # the inserted cell voltage follows the physical pole-to-pole DC
            # span. The insertion index therefore closes the native equipment
            # boundary as mdc * Ucell = Udc_positive - Udc_negative. Keeping
            # this relation algebraic lets every imported controller drive mdc
            # while the separate physical energy equation advances Ucell.
            mdc_var * cell_voltage_var - physical_dc_span,
            ac_current_magnitude
            - sym.sqrt(
                ac_active_power * ac_active_power
                + ac_reactive_power * ac_reactive_power
                + epsilon
            ) / (ac_voltage_magnitude + epsilon),
            # The network current remains on the VeraGrid pole-current base.
            # The native ElmVsc iDC signal instead uses the fixed converter
            # current base Snom/Udc_nom. Converting between those bases uses
            # (Sbase/Snom)*(Udc_nom/Vpole_nom); this is two only for a symmetric
            # bipolar converter. Using the network current is essential here:
            # deriving iDC through mdc would make its base vary spuriously with
            # the internal capacitor voltage.
            network_dc_current - dc_power / (dc_span + epsilon),
            idc_var
            + network_dc_current
            * controller_current_power_gain
            * nominal_cell_voltage
            / (dc_positive_nominal_voltage + epsilon),
            # A dedicated result alias prevents downstream validation and GUI
            # tools from guessing which equal-named ``idc`` belongs to ElmVsc.
            equipment_dc_current_observer - idc_var,
        ]),
        parameters={
            idle_loss: Const(0.0),
            linear_loss: Const(0.0),
            quadratic_loss: Const(0.0),
        },
        event_dict={
            ac_nominal_voltage: Const(1.0),
            dc_positive_nominal_voltage: Const(1.0),
            dc_negative_nominal_voltage: Const(1.0),
            controller_current_power_gain: Const(1.0),
            reactor_resistance: Const(0.0),
            reactor_reactance: Const(0.0),
            nominal_cell_voltage: Const(1.0),
            equivalent_capacitance: Const(1.0),
            system_power_base: Const(1.0),
            epsilon: Const(1.0e-9),
        },
        init_eqs={
            # The native equipment solves its modulation inputs from the
            # initialized AC terminal voltage before controller inc() equations
            # back-calculate uconv_r/uconv_i. Seeding the same physical values
            # breaks that otherwise circular controller/equipment contract.
            pmr_var: (
                    internal_voltage_real
                    * ac_nominal_voltage
                    / (math.sqrt(3.0 / 8.0) * nominal_cell_voltage)
            ),
            pmi_var: (
                    internal_voltage_imaginary
                    * ac_nominal_voltage
                    / (math.sqrt(3.0 / 8.0) * nominal_cell_voltage)
            ),
            # ElmVsc initializes its capacitor-voltage equipment output from
            # the converter nominal DC voltage. The controller then derives
            # mdc from that physical equipment seed, avoiding an underdetermined
            # Ucap/mdc initialization cycle while keeping the runtime equation.
            cell_voltage_var: nominal_cell_voltage,
            ac_current_magnitude: sym.sqrt(
                ac_active_power * ac_active_power
                + ac_reactive_power * ac_reactive_power
                + epsilon
            ) / (ac_voltage_magnitude + epsilon),
            dc_power: converter_loss - ac_active_power,
            network_dc_current: dc_power / (dc_span + epsilon),
            idc_var: (
                    -network_dc_current
                    * controller_current_power_gain
                    * nominal_cell_voltage
                    / (dc_positive_nominal_voltage + epsilon)
            ),
            equipment_dc_current_observer: idc_var,
        },
        external_mapping={
            VarPowerFlowReferenceType.Vf_dc: dc_positive_voltage,
            VarPowerFlowReferenceType.Vt_dc: dc_negative_voltage,
            VarPowerFlowReferenceType.Vmt: ac_voltage_magnitude,
            VarPowerFlowReferenceType.Vat: ac_voltage_angle,
            VarPowerFlowReferenceType.Pf: dc_power,
            VarPowerFlowReferenceType.Pt: ac_active_power,
            VarPowerFlowReferenceType.Qt: ac_reactive_power,
            VarPowerFlowReferenceType.Idc: network_dc_current,
            VarPowerFlowReferenceType.Im: ac_current_magnitude,
        },
        api_obj_mapping={
            ParamPowerFlowReferenceType.alpha1: idle_loss,
            ParamPowerFlowReferenceType.alpha2: linear_loss,
            ParamPowerFlowReferenceType.alpha3: quadratic_loss,
        },
    )
    # A current controller commonly anchors the limiter output cable with
    # ``inc(i1d_ref)=i1d`` and ``inc(i1q_ref)=i1q``. Preserve those exact
    # exported UID assignments at the outer shell. Otherwise an earlier,
    # circular limiter ``inc()`` wins during flattening and starts the PI with
    # a fictitious current error even though the DGS contains the correct
    # load-flow current measurement.
    current_initialization_names: Tuple[Tuple[str, str], ...] = (
        ("i1d_ref", "i1d"),
        ("i1q_ref", "i1q"),
    )
    current_target_name: str
    current_source_name: str
    current_assignments: List[Tuple[Var, Expr]]
    current_target_var: Var
    current_initial_expr: Expr
    for current_target_name, current_source_name in current_initialization_names:
        current_assignments = _find_direct_initialization_assignments(
            block=control_block,
            target_name=current_target_name,
            source_name=current_source_name,
        )
        for current_target_var, current_initial_expr in current_assignments:
            wrapper_block.init_eqs[current_target_var] = current_initial_expr

    real_modulation_dependencies: Tuple[Var, Var, Var, Var] | None = (
        _find_modulation_initialization_dependencies(
            block=control_block,
            modulation_output=pmr_var,
            voltage_component_name="uconv_r",
        )
    )
    imaginary_modulation_dependencies: Tuple[Var, Var, Var, Var] | None = (
        _find_modulation_initialization_dependencies(
            block=control_block,
            modulation_output=pmi_var,
            voltage_component_name="uconv_i",
        )
    )
    if (
            real_modulation_dependencies is not None
            and imaginary_modulation_dependencies is not None
    ):
        real_controller_voltage: Var = real_modulation_dependencies[0]
        real_limited_dc_voltage: Var = real_modulation_dependencies[1]
        real_ac_nominal_voltage: Var = real_modulation_dependencies[2]
        real_dc_nominal_voltage: Var = real_modulation_dependencies[3]
        imaginary_controller_voltage: Var = imaginary_modulation_dependencies[0]
        imaginary_limited_dc_voltage: Var = imaginary_modulation_dependencies[1]
        imaginary_ac_nominal_voltage: Var = imaginary_modulation_dependencies[2]
        imaginary_dc_nominal_voltage: Var = imaginary_modulation_dependencies[3]
        inverse_modulation_factor: float = math.sqrt(3.0) / (
                2.0 * math.sqrt(2.0)
        )

        # Seed the exact cable variables consumed by the modulation block. A
        # composite may contain several equal-named operating-mode candidates,
        # so these UIDs come from the Pmr/Pmi equations rather than name lookup.
        wrapper_block.init_eqs[real_controller_voltage] = (
                pmr_var
                * real_limited_dc_voltage
                * inverse_modulation_factor
                * real_dc_nominal_voltage
                / real_ac_nominal_voltage
        )
        wrapper_block.init_eqs[imaginary_controller_voltage] = (
                pmi_var
                * imaginary_limited_dc_voltage
                * inverse_modulation_factor
                * imaginary_dc_nominal_voltage
                / imaginary_ac_nominal_voltage
        )

        # Native operating-mode blocks select between equal-named islanded and
        # non-islanded voltage orders. Their exported ``inc()`` equations are
        # circular identities until the equipment voltage is known. Seed every
        # exact source UID referenced by the selector from the same physical
        # target; the runtime selector equations remain unchanged and choose the
        # DGS-declared branch normally after initialization.
        real_selector_sources: List[Var] = (
            _find_equal_named_initialization_sources(
                block=control_block,
                target_var=real_controller_voltage,
            )
        )
        imaginary_selector_sources: List[Var] = (
            _find_equal_named_initialization_sources(
                block=control_block,
                target_var=imaginary_controller_voltage,
            )
        )
        selector_source: Var
        for selector_source in real_selector_sources:
            wrapper_block.init_eqs[selector_source] = real_controller_voltage
        for selector_source in imaginary_selector_sources:
            wrapper_block.init_eqs[selector_source] = imaginary_controller_voltage
    else:
        # Other ElmVsc controller families remain valid without this optional
        # native modulation-factor initialization contract.
        pass
    _normalize_unowned_interface_initializers(block=wrapper_block)
    result: RmsModelTemplate = RmsModelTemplate(name=control_template.name)
    result.name = control_template.name
    result.tpe = DeviceType.VscDevice
    result.block = wrapper_block
    return result


def configure_dgs_elmvsc_runtime_template_for_device(
        template: RmsModelTemplate,
        device: VSC,
        system_base_mva: float,
) -> bool:
    """
    Configure one ElmVsc shell for the associated bus voltage bases.

    :param template: Adapted reusable RMS template.
    :param device: Exact VSC host selected by DGS FID.
    :param system_base_mva: VeraGrid system power base in MVA.
    :return: ``True`` when all physical adapter bases were configured.
    """
    ac_nominal_voltage_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvsc_ac_nominal_voltage_kv",
    )
    dc_positive_nominal_voltage_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvsc_dc_positive_nominal_voltage_kv",
    )
    dc_negative_nominal_voltage_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvsc_dc_negative_nominal_voltage_kv",
    )
    controller_current_power_gain_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvsc_controller_current_power_gain",
    )
    nominal_cell_voltage_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvsc_nominal_cell_voltage_kv",
    )
    equivalent_capacitance_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvsc_equivalent_capacitance_uf",
    )
    system_power_base_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvsc_system_power_base_mva",
    )
    reactor_resistance_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvsc_reactor_r_system_pu",
    )
    reactor_reactance_var: Var | None = _find_named_var_recursive(
        block=template.block,
        var_name="elmvsc_reactor_x_system_pu",
    )
    if (
            ac_nominal_voltage_var is None
            or dc_positive_nominal_voltage_var is None
            or dc_negative_nominal_voltage_var is None
            or controller_current_power_gain_var is None
            or nominal_cell_voltage_var is None
            or equivalent_capacitance_var is None
            or system_power_base_var is None
            or reactor_resistance_var is None
            or reactor_reactance_var is None
    ):
        return False
    else:
        pass
    ac_nominal_voltage_uid: int = ac_nominal_voltage_var.uid
    dc_positive_nominal_voltage_uid: int = dc_positive_nominal_voltage_var.uid
    dc_negative_nominal_voltage_uid: int = dc_negative_nominal_voltage_var.uid
    controller_current_power_gain_uid: int = (
        controller_current_power_gain_var.uid
    )
    nominal_cell_voltage_uid: int = nominal_cell_voltage_var.uid
    equivalent_capacitance_uid: int = equivalent_capacitance_var.uid
    system_power_base_uid: int = system_power_base_var.uid
    reactor_resistance_uid: int = reactor_resistance_var.uid
    reactor_reactance_uid: int = reactor_reactance_var.uid

    ac_nominal_voltage_kv: float = float(device.bus_to.Vnom)
    dc_positive_nominal_voltage_kv: float = float(device.bus_from.Vnom)
    dc_converter_voltage_base_kv: float = float(device.dc_voltage_base)
    if device.bus_dc_n is None:
        return False
    else:
        dc_negative_nominal_voltage_kv: float = float(device.bus_dc_n.Vnom)

    if (
            ac_nominal_voltage_kv <= 0.0
            or dc_positive_nominal_voltage_kv <= 0.0
            or dc_negative_nominal_voltage_kv <= 0.0
            or dc_converter_voltage_base_kv <= 0.0
            or system_base_mva <= 0.0
            or float(device.rate) <= 0.0
            or float(device.r_series) < 0.0
            or float(device.x_series) <= 0.0
            or float(device.mmc_arm_capacitance_uf) <= 0.0
            or bool(device.mmc_consider_arm_reactor_dc)
    ):
        return False
    else:
        pass

    # The controller current is normalized on the converter rating, whereas
    # electrical powers compiled by VeraGrid use the circuit system base.
    controller_current_power_gain: float = system_base_mva / float(device.rate)
    # The fundamental-frequency MMC represents the six physical arm capacitor
    # banks through Ceq = 6 * Carm.  Requiring the canonical arm capacitance avoids
    # silently replacing internal energy storage with an algebraic power balance.
    equivalent_capacitance_uf: float = (
            6.0
            * float(device.mmc_arm_capacitance_uf)
    )
    # The static VSC conversion has already reconstructed PowerFactory's exact
    # equipment impedance ``Zsr + Zarm / 2`` from the same DGS. Controller-side
    # R/X values are feed-forward tuning parameters and may use template-specific
    # units, so they must never replace the physical equipment parameters.
    reactor_resistance_converter_pu: float = float(device.r_series)
    reactor_reactance_converter_pu: float = float(device.x_series)
    reactor_resistance_system_pu: float = (
            reactor_resistance_converter_pu * system_base_mva / float(device.rate)
    )
    reactor_reactance_system_pu: float = (
            reactor_reactance_converter_pu * system_base_mva / float(device.rate)
    )
    configured_uids: Set[int] = set()
    event_var: Var
    event_value: object
    for event_var, event_value in template.block.event_dict.items():
        if not isinstance(event_value, Const):
            pass
        else:
            if event_var.uid == ac_nominal_voltage_uid:
                template.block.event_dict[event_var] = Const(ac_nominal_voltage_kv)
                configured_uids.add(event_var.uid)
            else:
                if event_var.uid == dc_positive_nominal_voltage_uid:
                    template.block.event_dict[event_var] = Const(
                        dc_positive_nominal_voltage_kv,
                    )
                    configured_uids.add(event_var.uid)
                else:
                    if event_var.uid == dc_negative_nominal_voltage_uid:
                        template.block.event_dict[event_var] = Const(
                            dc_negative_nominal_voltage_kv,
                        )
                        configured_uids.add(event_var.uid)
                    else:
                        if event_var.uid == controller_current_power_gain_uid:
                            template.block.event_dict[event_var] = Const(
                                controller_current_power_gain,
                            )
                            configured_uids.add(event_var.uid)
                        else:
                            if event_var.uid == nominal_cell_voltage_uid:
                                template.block.event_dict[event_var] = Const(
                                    dc_converter_voltage_base_kv,
                                )
                                configured_uids.add(event_var.uid)
                            else:
                                if event_var.uid == reactor_resistance_uid:
                                    template.block.event_dict[event_var] = Const(
                                        reactor_resistance_system_pu,
                                    )
                                    configured_uids.add(event_var.uid)
                                else:
                                    if event_var.uid == reactor_reactance_uid:
                                        template.block.event_dict[event_var] = Const(
                                            reactor_reactance_system_pu,
                                        )
                                        configured_uids.add(event_var.uid)
                                    else:
                                        if event_var.uid == equivalent_capacitance_uid:
                                            template.block.event_dict[event_var] = Const(
                                                equivalent_capacitance_uf,
                                            )
                                            configured_uids.add(event_var.uid)
                                        else:
                                            if event_var.uid == system_power_base_uid:
                                                template.block.event_dict[event_var] = Const(
                                                    system_base_mva,
                                                )
                                                configured_uids.add(event_var.uid)
                                            else:
                                                pass
    return len(configured_uids) == 9
