"""Tests for DAE linting and context-aware source completion."""

from __future__ import annotations

from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.dae_code_completion import (
    DaeCompletionEntry,
    DaeCompletionPosition,
    DaeLanguageContext,
    analyze_dae_completion_position,
    build_dae_completion_entries,
    build_symbolic_function_entries,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.dae_code_linter import (
    DaeCodeDiagnostic,
    build_dae_code_diagnostics,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.dynamic_procedural_logic import (
    build_procedural_logic_call_lines,
    get_procedural_logic_help,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_library import (
    get_dynamic_library_procedural_descriptors,
)
from VeraGridEngine.Templates.ProceduralLogicCatalog import ProceduralBlockTemplateDescriptor
from VeraGridEngine.Utils.Symbolic.symbolic import (
    Comparison,
    Expr,
    Func2,
    Var,
    get_symbolic_parser_function_arity,
    get_symbolic_parser_function_names,
    string_to_symbolic,
)
from VeraGridEngine.enumerations import ProceduralLogicType


def build_language_context() -> DaeLanguageContext:
    """Build a representative typed DAE completion context.

    :return: Context containing variables from every important equation role.
    """
    voltage: Var = Var("Vm")
    angle: Var = Var("Va")
    speed: Var = Var("omega")
    speed_derivative: Var = Var("d_omega")
    power: Var = Var("P_g")
    namespace: dict[str, Expr] = dict((
        (voltage.name, voltage),
        (angle.name, angle),
        (speed.name, speed),
        (speed_derivative.name, speed_derivative),
        (power.name, power),
    ))
    entries: list[DaeCompletionEntry] = list((
        DaeCompletionEntry("Vm", "Vm", "Vm", "Input variable"),
        DaeCompletionEntry("Va", "Va", "Va", "Input variable"),
        DaeCompletionEntry("omega", "omega", "omega", "State variable"),
        DaeCompletionEntry(
            "d_omega",
            "d_omega",
            "d_omega",
            "Differential variable",
        ),
        DaeCompletionEntry("P_g", "P_g", "P_g", "Algebraic variable"),
    ))
    return DaeLanguageContext(
        namespace=namespace,
        symbol_entries=entries,
        initializable_names=list(("omega", "P_g")),
        state_names=list(("omega",)),
        algebraic_names=list(("P_g",)),
        differential_names=list(("d_omega",)),
    )


def get_completion_names(entries: list[DaeCompletionEntry]) -> list[str]:
    """Return candidate identifiers while preserving popup order.

    :param entries: Completion entries returned by the language service.
    :return: Ordered completion identifiers.
    """
    result: list[str] = list()
    entry: DaeCompletionEntry
    for entry in entries:
        result.append(entry.get_name())
    return result


def test_symbolic_catalog_is_the_only_function_completion_source() -> None:
    """Every completed function must come from the Engine symbolic catalogue.

    :return: None.
    """
    completion_names: list[str] = get_completion_names(
        build_symbolic_function_entries()
    )
    assert completion_names == get_symbolic_parser_function_names()
    assert "print" not in completion_names
    assert "eval" not in completion_names


def test_every_catalogued_symbolic_function_is_accepted_by_the_parser() -> None:
    """The authoritative catalogue must never advertise an invalid function.

    :return: None.
    """
    first: Var = Var("first")
    second: Var = Var("second")
    namespace: dict[str, Expr] = dict((("first", first), ("second", second)))
    function_name: str
    for function_name in get_symbolic_parser_function_names():
        arity: int | None = get_symbolic_parser_function_arity(function_name)
        if arity == 1:
            source: str = f"{function_name}(first)"
        elif arity == 2:
            source = f"{function_name}(first, second)"
        else:
            raise AssertionError(f"Missing parser arity for '{function_name}'")
        parsed: Expr | Comparison = string_to_symbolic(source, namespace)
        assert isinstance(parsed, Expr)
        if function_name == "max":
            assert isinstance(parsed, Func2)
        else:
            pass


def test_state_equation_keys_only_offer_state_variables() -> None:
    """A state-equation dictionary key must not offer unrelated symbols.

    :return: None.
    """
    context: DaeLanguageContext = build_language_context()
    source: str = "state_eqs = {\n    om"
    position: DaeCompletionPosition = analyze_dae_completion_position(
        source,
        len(source),
    )
    entries: list[DaeCompletionEntry] = build_dae_completion_entries(
        context,
        position,
    )
    assert get_completion_names(entries) == list(("omega",))
    assert entries[0].get_insertion_text() == "omega: "


def test_expression_completion_offers_symbols_and_engine_functions() -> None:
    """An equation right-hand side must expose symbols and safe functions.

    :return: None.
    """
    context: DaeLanguageContext = build_language_context()
    source: str = "algebraic_eqs = [\n    0 = s"
    position: DaeCompletionPosition = analyze_dae_completion_position(
        source,
        len(source),
    )
    entries: list[DaeCompletionEntry] = build_dae_completion_entries(
        context,
        position,
    )
    completion_names: list[str] = get_completion_names(entries)
    assert "sin" in completion_names
    assert "sqrt" in completion_names
    assert "state_eqs" not in completion_names


def test_procedural_completion_inserts_complete_documented_call() -> None:
    """A procedural completion must insert every required named argument.

    :return: None.
    """
    context: DaeLanguageContext = build_language_context()
    source: str = "procedural_logic = [\n    tim"
    position: DaeCompletionPosition = analyze_dae_completion_position(
        source,
        len(source),
    )

    entries: list[DaeCompletionEntry] = build_dae_completion_entries(
        context,
        position,
    )

    assert get_completion_names(entries) == list((ProceduralLogicType.TimeDelay.value,))
    entry: DaeCompletionEntry = entries[0]
    assert "output=None" in entry.get_insertion_text()
    assert "source=0.0" in entry.get_insertion_text()
    assert "delay=0.0" in entry.get_insertion_text()
    assert "name='time delay'" in entry.get_insertion_text()
    assert "output=..." in entry.get_display_text()
    assert "Non-negative delay" in entry.get_tooltip()
    assert entry.get_selection_length() == len("None")


def test_procedural_output_completion_only_offers_retained_modes() -> None:
    """An output argument must not offer ordinary DAE variables or parameters.

    :return: None.
    """
    held: Var = Var("held")
    source_variable: Var = Var("source_signal")
    delay_parameter: Var = Var("delay_parameter")
    namespace: dict[str, Expr] = dict((
        (held.name, held),
        (source_variable.name, source_variable),
        (delay_parameter.name, delay_parameter),
    ))
    symbol_entries: list[DaeCompletionEntry] = list((
        DaeCompletionEntry("held", "held", "held", "Retained mode"),
        DaeCompletionEntry(
            "source_signal", "source_signal", "source_signal", "Algebraic variable"
        ),
        DaeCompletionEntry(
            "delay_parameter", "delay_parameter", "delay_parameter", "Event parameter"
        ),
    ))
    context: DaeLanguageContext = DaeLanguageContext(
        namespace=namespace,
        symbol_entries=symbol_entries,
        initializable_names=list(),
        state_names=list(),
        algebraic_names=list(("source_signal",)),
        differential_names=list(),
        mode_names=list(("held",)),
        runtime_parameter_names=list(("delay_parameter",)),
        variable_names=list(("source_signal",)),
    )
    source: str = (
        "procedural_logic = [\n"
        "    time_delay(\n"
        "        output="
    )
    position: DaeCompletionPosition = analyze_dae_completion_position(
        source,
        len(source),
    )

    entries: list[DaeCompletionEntry] = build_dae_completion_entries(
        context,
        position,
    )

    assert get_completion_names(entries) == list(("held",))


def test_every_user_authorable_procedural_type_has_a_complete_template_and_help() -> None:
    """Every user-authorable type must expose arguments and contextual help.

    :return: None.
    """
    # The Library descriptor inventory is the authoring boundary shared by
    # completion, lint, help, and the graphical editor.
    descriptor: ProceduralBlockTemplateDescriptor
    for descriptor in get_dynamic_library_procedural_descriptors():
        logic_tpe: ProceduralLogicType = descriptor.logic_tpe
        lines: list[str]
        first_placeholder: str | None
        lines, first_placeholder = build_procedural_logic_call_lines(logic_tpe)
        source: str = "\n".join(lines)
        help_text: str = get_procedural_logic_help(logic_tpe)

        assert lines[0] == f"{logic_tpe.value}("
        assert lines[-1] == "),"
        assert "name=" in source
        assert "Named arguments:" in help_text
        if first_placeholder is not None:
            assert first_placeholder in source
        else:
            pass


def test_init_equation_keys_exclude_inputs_events_and_existing_keys() -> None:
    """Initialization completion must offer only unused DAE unknowns.

    :return: None.
    """
    voltage: Var = Var("Vm")
    angle: Var = Var("Va")
    direct_voltage: Var = Var("v_d")
    quadrature_voltage: Var = Var("v_q")
    field_voltage: Var = Var("vf")
    missing_voltage: Var = Var("v_missing")
    namespace: dict[str, Expr] = dict((
        (voltage.name, voltage),
        (angle.name, angle),
        (direct_voltage.name, direct_voltage),
        (quadrature_voltage.name, quadrature_voltage),
        (field_voltage.name, field_voltage),
        (missing_voltage.name, missing_voltage),
    ))
    entries: list[DaeCompletionEntry] = list((
        DaeCompletionEntry("Vm", "Vm", "Vm", "Input variable"),
        DaeCompletionEntry("Va", "Va", "Va", "Input variable"),
        DaeCompletionEntry("v_d", "v_d", "v_d", "Algebraic variable"),
        DaeCompletionEntry("v_q", "v_q", "v_q", "Algebraic variable"),
        DaeCompletionEntry("vf", "vf", "vf", "Event parameter"),
        DaeCompletionEntry(
            "v_missing",
            "v_missing",
            "v_missing",
            "Algebraic variable",
        ),
    ))
    context: DaeLanguageContext = DaeLanguageContext(
        namespace=namespace,
        symbol_entries=entries,
        initializable_names=list(("v_d", "v_q", "v_missing")),
        state_names=list(),
        algebraic_names=list(("v_d", "v_q", "v_missing")),
        differential_names=list(),
    )
    source_with_prefix: str = (
        "init_eqs = {\n"
        "    v_d: Vm,\n"
        "    v_q: Va,\n"
        "    v"
    )
    prefix_position: DaeCompletionPosition = analyze_dae_completion_position(
        source_with_prefix,
        len(source_with_prefix),
    )
    prefix_entries: list[DaeCompletionEntry] = build_dae_completion_entries(
        context,
        prefix_position,
    )
    assert get_completion_names(prefix_entries) == list(("v_missing",))

    source_without_prefix: str = (
        "init_eqs = {\n"
        "    v_d: Vm,\n"
        "    v_q: Va,\n"
        "    "
    )
    empty_position: DaeCompletionPosition = analyze_dae_completion_position(
        source_without_prefix,
        len(source_without_prefix),
    )
    empty_entries: list[DaeCompletionEntry] = build_dae_completion_entries(
        context,
        empty_position,
    )
    assert get_completion_names(empty_entries) == list(("v_missing",))


def test_completion_is_suppressed_inside_comments_and_strings() -> None:
    """Non-code text must not display unrelated symbolic candidates.

    :return: None.
    """
    context: DaeLanguageContext = build_language_context()
    comment_source: str = "algebraic_eqs = [\n    # om"
    comment_position: DaeCompletionPosition = analyze_dae_completion_position(
        comment_source,
        len(comment_source),
    )
    assert build_dae_completion_entries(context, comment_position) == list()

    string_source: str = "algebraic_eqs = [\n    'om"
    string_position: DaeCompletionPosition = analyze_dae_completion_position(
        string_source,
        len(string_source),
    )
    assert build_dae_completion_entries(context, string_position) == list()

    number_source: str = "algebraic_eqs = [\n    0 = 12.5"
    number_position: DaeCompletionPosition = analyze_dae_completion_position(
        number_source,
        len(number_source),
    )
    assert build_dae_completion_entries(context, number_position) == list()


def test_linter_marks_a_complete_function_call_with_wrong_arity() -> None:
    """Function-arity diagnostics must select the complete invalid call.

    :return: None.
    """
    variable: Var = Var("x")
    code: str = (
        "state_vars = []\n"
        "state_eqs = {}\n"
        "algebraic_eqs = [0 = sin(x, x)]\n"
        "init_eqs = {}\n"
        "diff_init_eqs = {}"
    )
    diagnostics: list[DaeCodeDiagnostic] = build_dae_code_diagnostics(
        code,
        dict((("x", variable),)),
    )
    assert len(diagnostics) == 1
    diagnostic: DaeCodeDiagnostic = diagnostics[0]
    assert diagnostic.get_line() == 3
    assert diagnostic.get_length() == len("sin(x, x)")
    assert "expects 1 argument" in diagnostic.get_message()


def test_linter_rejects_functions_outside_the_symbolic_catalogue() -> None:
    """Unknown Python callables must be diagnosed as unsupported DAE functions.

    :return: None.
    """
    variable: Var = Var("x")
    code: str = (
        "state_vars = []\n"
        "state_eqs = {}\n"
        "algebraic_eqs = [0 = print(x)]\n"
        "init_eqs = {}\n"
        "diff_init_eqs = {}"
    )
    diagnostics: list[DaeCodeDiagnostic] = build_dae_code_diagnostics(
        code,
        dict((("x", variable),)),
    )
    assert len(diagnostics) == 1
    diagnostic: DaeCodeDiagnostic = diagnostics[0]
    assert diagnostic.get_length() == len("print")
    assert diagnostic.get_message() == "Unsupported symbolic function 'print'"
