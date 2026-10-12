# SPDX-License-Identifier: MPL-2.0
"""Context-aware completion for the Dynamic Editor DAE source language."""

from __future__ import annotations

from io import StringIO
import re
import tokenize
from typing import Dict, List, Mapping, Sequence

from VeraGridEngine.Utils.Symbolic.symbolic import (
    Expr,
    get_symbolic_parser_function_arity,
    get_symbolic_parser_function_names,
)
from VeraGridEngine.enumerations import ProceduralFieldType, ProceduralLogicType
from VeraGridEngine.Templates.ProceduralLogicCatalog import (
    ProceduralBlockTemplateDescriptor,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_library import (
    get_dynamic_library_procedural_descriptors,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.dynamic_procedural_logic import (
    build_procedural_logic_call_lines,
    get_procedural_code_field_type,
    get_procedural_logic_help,
    get_procedural_logic_summary,
    get_procedural_logic_signature,
)


class DaeCompletionEntry:
    """One safe source fragment offered by the DAE completion popup."""

    __slots__ = (
        "_name",
        "_display_text",
        "_insertion_text",
        "_description",
        "_cursor_backtrack",
        "_selection_length",
        "_tooltip",
    )

    def __init__(self,
                 name: str,
                 display_text: str,
                 insertion_text: str,
                 description: str,
                 cursor_backtrack: int = 0,
                 selection_length: int = 0,
                 tooltip: str = "") -> None:
        """Store one completion without retaining mutable editor state.

        :param name: Identifier matched against the source prefix.
        :param display_text: Label rendered in the popup.
        :param insertion_text: Source fragment inserted after selection.
        :param description: Short explanation rendered beside the label.
        :param cursor_backtrack: Characters moved left after insertion.
        :param selection_length: Characters selected immediately before the final cursor.
        :param tooltip: Extended contextual documentation.
        :return: None.
        """
        self._name: str = name
        self._display_text: str = display_text
        self._insertion_text: str = insertion_text
        self._description: str = description
        self._cursor_backtrack: int = max(0, cursor_backtrack)
        self._selection_length: int = max(0, selection_length)
        self._tooltip: str = tooltip if len(tooltip) > 0 else description

    def get_name(self) -> str:
        """Return the identifier used for prefix matching.

        :return: Completion identifier.
        """
        return self._name

    def get_display_text(self) -> str:
        """Return the primary popup label.

        :return: Human-readable completion label.
        """
        return self._display_text

    def get_insertion_text(self) -> str:
        """Return the source fragment inserted by the editor.

        :return: Safe DAE source fragment.
        """
        return self._insertion_text

    def get_description(self) -> str:
        """Return the short contextual explanation.

        :return: Completion description.
        """
        return self._description

    def get_cursor_backtrack(self) -> int:
        """Return how far the cursor moves left after insertion.

        :return: Non-negative cursor displacement.
        """
        return self._cursor_backtrack

    def get_selection_length(self) -> int:
        """Return how many characters are selected before the final cursor.

        :return: Non-negative selection length.
        """
        return self._selection_length

    def get_tooltip(self) -> str:
        """Return extended popup or hover documentation.

        :return: Tooltip text, falling back to the short description.
        """
        return self._tooltip


class DaeLanguageContext:
    """Immutable completion view of one equation owner's staged symbols."""

    __slots__ = (
        "_namespace",
        "_symbol_entries",
        "_initializable_names",
        "_state_names",
        "_algebraic_names",
        "_differential_names",
        "_mode_names",
        "_runtime_parameter_names",
        "_variable_names",
    )

    def __init__(self,
                 namespace: Mapping[str, Expr],
                 symbol_entries: Sequence[DaeCompletionEntry],
                 initializable_names: Sequence[str],
                 state_names: Sequence[str],
                 algebraic_names: Sequence[str],
                 differential_names: Sequence[str],
                 mode_names: Sequence[str] | None = None,
                 runtime_parameter_names: Sequence[str] | None = None,
                 variable_names: Sequence[str] | None = None) -> None:
        """Capture the exact symbols valid for one editable DAE buffer.

        :param namespace: Symbolic identities accepted by the safe parser.
        :param symbol_entries: Typed descriptions for popup presentation.
        :param initializable_names: Variables valid as initialization-equation keys.
        :param state_names: State variables owned by the active block.
        :param algebraic_names: Algebraic variables owned by the active block.
        :param differential_names: Differential variables owned by the active block.
        :param mode_names: Retained modes writable by procedural entries.
        :param runtime_parameter_names: Dynamic parameters available to runtime logic.
        :param variable_names: DAE variables available to typed procedural references.
        :return: None.
        """
        self._namespace: Dict[str, Expr] = dict(namespace)
        self._symbol_entries: List[DaeCompletionEntry] = list(symbol_entries)
        self._initializable_names: List[str] = list(initializable_names)
        self._state_names: List[str] = list(state_names)
        self._algebraic_names: List[str] = list(algebraic_names)
        self._differential_names: List[str] = list(differential_names)
        self._mode_names: List[str] = list() if mode_names is None else list(mode_names)
        self._runtime_parameter_names: List[str] = (
            list() if runtime_parameter_names is None else list(runtime_parameter_names)
        )
        self._variable_names: List[str] = (
            list(namespace.keys()) if variable_names is None else list(variable_names)
        )

    def get_namespace(self) -> Dict[str, Expr]:
        """Return the safe parser namespace represented by this context.

        :return: Detached symbol-name lookup.
        """
        return dict(self._namespace)

    def get_symbol_entries(self) -> List[DaeCompletionEntry]:
        """Return all variables and parameters visible to expressions.

        :return: Detached ordered symbol completions.
        """
        return list(self._symbol_entries)

    def get_initializable_names(self) -> List[str]:
        """Return variables that may own initialization equations.

        :return: Ordered initialization-equation key names.
        """
        return list(self._initializable_names)

    def get_state_names(self) -> List[str]:
        """Return state-variable names in equation order.

        :return: Ordered state-variable names.
        """
        return list(self._state_names)

    def get_algebraic_names(self) -> List[str]:
        """Return algebraic-variable names in equation order.

        :return: Ordered algebraic-variable names.
        """
        return list(self._algebraic_names)

    def get_differential_names(self) -> List[str]:
        """Return differential-variable names in table order.

        :return: Ordered differential-variable names.
        """
        return list(self._differential_names)

    def get_mode_names(self) -> List[str]:
        """Return retained modes accepted as procedural outputs.

        :return: Ordered retained-mode names.
        """
        return list(self._mode_names)

    def get_runtime_parameter_names(self) -> List[str]:
        """Return dynamic parameter names accepted by runtime references.

        :return: Ordered dynamic-parameter names.
        """
        return list(self._runtime_parameter_names)

    def get_variable_names(self) -> List[str]:
        """Return DAE variable names accepted by typed variable references.

        :return: Ordered variable names.
        """
        return list(self._variable_names)


def build_generic_dae_language_context(
        namespace: Mapping[str, Expr]) -> DaeLanguageContext:
    """Build a safe context when detailed block roles are unavailable.

    Standalone editor tests and transitional callers can provide only the
    parser namespace. Every identity remains completable, while an owning Block
    Properties dialogue can later replace this context with richer role data.

    :param namespace: Symbolic identities accepted by the safe parser.
    :return: Completion context with generic symbol descriptions.
    """
    entries: List[DaeCompletionEntry] = list()
    symbol_name: str
    for symbol_name in namespace:
        entries.append(
            DaeCompletionEntry(
                name=symbol_name,
                display_text=symbol_name,
                insertion_text=symbol_name,
                description="Symbolic variable or parameter",
            )
        )
    return DaeLanguageContext(
        namespace=namespace,
        symbol_entries=entries,
        initializable_names=list(namespace.keys()),
        state_names=list(),
        algebraic_names=list(),
        differential_names=list(),
        mode_names=list(namespace.keys()),
        runtime_parameter_names=list(namespace.keys()),
        variable_names=list(namespace.keys()),
    )


class DaeCompletionPosition:
    """Lexical context at one source cursor position."""

    __slots__ = (
        "_prefix",
        "_section_name",
        "_expects_mapping_key",
        "_mapping_key_names",
        "_suppressed",
        "_line_indentation",
        "_procedural_logic_tpe",
        "_procedural_argument",
    )

    def __init__(self,
                 prefix: str,
                 section_name: str | None,
                 expects_mapping_key: bool,
                 mapping_key_names: Sequence[str],
                 suppressed: bool,
                 line_indentation: str,
                 procedural_logic_tpe: ProceduralLogicType | None,
                 procedural_argument: str | None) -> None:
        """Capture the minimum context required to filter suggestions.

        :param prefix: Identifier fragment directly before the cursor.
        :param section_name: Active top-level DAE section, if any.
        :param expects_mapping_key: Whether a dictionary key is being written.
        :param mapping_key_names: Keys already present in the active dictionary.
        :param suppressed: Whether completion is inside a comment or string.
        :param line_indentation: Leading whitespace of the cursor line.
        :param procedural_logic_tpe: Procedural call surrounding the cursor.
        :param procedural_argument: Named procedural argument currently being edited.
        :return: None.
        """
        self._prefix: str = prefix
        self._section_name: str | None = section_name
        self._expects_mapping_key: bool = expects_mapping_key
        self._mapping_key_names: List[str] = list(mapping_key_names)
        self._suppressed: bool = suppressed
        self._line_indentation: str = line_indentation
        self._procedural_logic_tpe: ProceduralLogicType | None = procedural_logic_tpe
        self._procedural_argument: str | None = procedural_argument

    def get_prefix(self) -> str:
        """Return the identifier fragment directly before the cursor.

        :return: Current completion prefix.
        """
        return self._prefix

    def get_section_name(self) -> str | None:
        """Return the active DAE section.

        :return: Section name or ``None`` at top level.
        """
        return self._section_name

    def expects_mapping_key(self) -> bool:
        """Return whether the current dictionary entry expects a key.

        :return: Whether key-only completions are appropriate.
        """
        return self._expects_mapping_key

    def get_mapping_key_names(self) -> List[str]:
        """Return keys already written in the active mapping section.

        :return: Ordered existing mapping-key names.
        """
        return list(self._mapping_key_names)

    def is_suppressed(self) -> bool:
        """Return whether suggestions must remain hidden.

        :return: Whether the cursor is inside non-code text.
        """
        return self._suppressed

    def get_line_indentation(self) -> str:
        """Return leading whitespace for indentation-aware snippets.

        :return: Current line indentation.
        """
        return self._line_indentation

    def get_procedural_logic_tpe(self) -> ProceduralLogicType | None:
        """Return the procedural call containing the cursor.

        :return: Concrete type or ``None`` outside a procedural call.
        """
        return self._procedural_logic_tpe

    def get_procedural_argument(self) -> str | None:
        """Return the named procedural argument being edited.

        :return: Public keyword or ``None`` outside an argument value.
        """
        return self._procedural_argument


def get_dae_section_names() -> tuple[str, ...]:
    """Return the complete set of assignments accepted by the DAE parser.

    :return: Ordered top-level DAE section names.
    """
    return (
        "state_vars",
        "algebraic_vars",
        "diff_vars",
        "state_eqs",
        "algebraic_eqs",
        "init_eqs",
        "diff_init_eqs",
        "retained_modes",
        "procedural_logic",
    )


def get_symbolic_function_description(function_name: str) -> str:
    """Return concise mathematical help for one symbolic function.

    :param function_name: Name supplied by the Engine symbolic catalogue.
    :return: Human-readable function purpose.
    """
    if function_name in ("sin", "cos", "tan", "asin", "acos", "atan", "atan2"):
        result: str = "Trigonometric symbolic function"
    elif function_name in ("sinh", "cosh", "tanh"):
        result = "Hyperbolic symbolic function"
    elif function_name in ("exp", "log", "log10", "sqrt"):
        result = "Exponential or radical symbolic function"
    elif function_name in ("real", "imag", "conj", "angle"):
        result = "Complex-value symbolic function"
    elif function_name in ("min", "max"):
        result = "Two-argument symbolic limiter function"
    elif function_name == "heaviside":
        result = "Unit-step symbolic function"
    elif function_name == "rand":
        result = "Symbolic random-value function"
    elif function_name in ("floor", "ceil", "round"):
        result = "Symbolic rounding function"
    elif function_name == "abs":
        result = "Symbolic absolute value"
    else:
        result = "Engine symbolic function"
    return result


def build_symbolic_function_entries() -> List[DaeCompletionEntry]:
    """Build completions exclusively from the Engine symbolic catalogue.

    :return: Ordered function completions with signatures and insertion text.
    """
    result: List[DaeCompletionEntry] = list()
    function_names: List[str] = get_symbolic_parser_function_names()
    function_name: str
    for function_name in function_names:
        arity: int | None = get_symbolic_parser_function_arity(function_name)
        if arity == 1:
            signature: str = f"{function_name}(x)"
            insertion_text: str = f"{function_name}()"
            cursor_backtrack: int = 1
        elif arity == 2:
            if function_name == "atan2":
                signature = "atan2(y, x)"
            else:
                signature = f"{function_name}(a, b)"
            insertion_text = f"{function_name}(, )"
            cursor_backtrack = 3
        else:
            # A catalogue entry without an arity cannot be inserted safely.
            signature = function_name
            insertion_text = function_name
            cursor_backtrack = 0
        result.append(
            DaeCompletionEntry(
                name=function_name,
                display_text=signature,
                insertion_text=insertion_text,
                description=get_symbolic_function_description(function_name),
                cursor_backtrack=cursor_backtrack,
            )
        )
    return result


def build_procedural_function_entries(
        line_indentation: str,
) -> List[DaeCompletionEntry]:
    """Build completion entries for every editable procedural logic type.

    :param line_indentation: Leading whitespace already present before the function name.
    :return: Ordered procedural call completions.
    """
    result: List[DaeCompletionEntry] = list()
    descriptor: ProceduralBlockTemplateDescriptor
    for descriptor in get_dynamic_library_procedural_descriptors():
        logic_tpe: ProceduralLogicType = descriptor.logic_tpe
        relative_lines: List[str]
        first_placeholder: str | None
        relative_lines, first_placeholder = build_procedural_logic_call_lines(
            logic_tpe
        )
        insertion_parts: List[str] = list((relative_lines[0],))
        relative_line: str
        for relative_line in relative_lines[1:]:
            insertion_parts.append(f"\n{line_indentation}{relative_line}")
        insertion_text: str = "".join(insertion_parts)
        if first_placeholder is not None:
            placeholder_start: int = insertion_text.find(first_placeholder)
        else:
            placeholder_start = -1
        if placeholder_start >= 0 and first_placeholder is not None:
            cursor_backtrack: int = (
                len(insertion_text)
                - placeholder_start
                - len(first_placeholder)
            )
            selection_length: int = len(first_placeholder)
        else:
            cursor_backtrack = 0
            selection_length = 0
        result.append(DaeCompletionEntry(
            name=logic_tpe.value,
            display_text=get_procedural_logic_signature(logic_tpe),
            insertion_text=insertion_text,
            description=get_procedural_logic_summary(logic_tpe),
            cursor_backtrack=cursor_backtrack,
            selection_length=selection_length,
            tooltip=get_procedural_logic_help(logic_tpe),
        ))
    return result

def extract_dae_identifier_prefix(source: str, cursor_position: int) -> str:
    """Return the Python-identifier fragment immediately before the cursor.

    :param source: Complete visible DAE source.
    :param cursor_position: Absolute cursor offset in ``source``.
    :return: Identifier prefix, possibly empty.
    """
    bounded_position: int = min(max(0, cursor_position), len(source))
    start_position: int = bounded_position
    prefix_complete: bool = False
    while start_position > 0 and not prefix_complete:
        character: str = source[start_position - 1]
        if character.isalnum() or character == "_":
            start_position -= 1
        else:
            prefix_complete = True
    return source[start_position:bounded_position]


def cursor_is_in_dae_non_code_text(source: str, cursor_position: int) -> bool:
    """Detect comments and quoted text on the cursor's current line.

    DAE expressions do not accept string literals. Suppressing completion in
    quoted text still prevents a half-written invalid string from producing an
    unrelated symbol popup before the linter explains the syntax problem.

    :param source: Complete visible DAE source.
    :param cursor_position: Absolute cursor offset in ``source``.
    :return: Whether completion should remain hidden.
    """
    bounded_position: int = min(max(0, cursor_position), len(source))
    line_start: int = source.rfind("\n", 0, bounded_position) + 1
    line_prefix: str = source[line_start:bounded_position]
    quote_character: str | None = None
    escaped: bool = False
    character: str
    for character in line_prefix:
        if escaped:
            escaped = False
        elif character == "\\" and quote_character is not None:
            escaped = True
        elif quote_character is not None and character == quote_character:
            quote_character = None
        elif quote_character is None and character in ("'", '"'):
            quote_character = character
        elif quote_character is None and character == "#":
            return True
        else:
            pass
    return quote_character is not None


def cursor_is_in_dae_number(source: str, cursor_position: int) -> bool:
    """Detect whether the cursor ends a numeric token being edited.

    The exact token end is required so whitespace following a completed number
    remains a valid place for manual completion. Tokenization also handles
    decimal, exponent, imaginary, and underscored Python numeric syntax without
    maintaining a second number grammar in the GUI.

    :param source: Complete visible DAE source.
    :param cursor_position: Absolute cursor offset in ``source``.
    :return: Whether the cursor is immediately inside a numeric token.
    """
    bounded_position: int = min(max(0, cursor_position), len(source))
    source_prefix: str = source[:bounded_position]
    cursor_line: int = source_prefix.count("\n") + 1
    last_newline_position: int = source_prefix.rfind("\n")
    cursor_column: int = bounded_position if last_newline_position < 0 else (
        bounded_position - last_newline_position - 1
    )
    cursor_coordinates: tuple[int, int] = (cursor_line, cursor_column)
    result: bool = False
    try:
        source_token: tokenize.TokenInfo
        for source_token in tokenize.generate_tokens(StringIO(source_prefix).readline):
            if (source_token.type == tokenize.NUMBER
                    and source_token.end == cursor_coordinates):
                result = True
            else:
                pass
    except (IndentationError, tokenize.TokenError):
        # Tokens completed before an unfinished expression remain usable.
        pass
    return result


def get_dae_mapping_key_names(source: str, section_name: str) -> List[str]:
    """Collect direct dictionary keys already written in one DAE section.

    The token walk deliberately tolerates an unfinished new key. This lets the
    completer remove existing keys while the current prefix is not yet valid
    Python and therefore cannot be inspected through :mod:`ast`.

    :param source: Complete visible DAE source.
    :param section_name: Top-level dictionary assignment being inspected.
    :return: Ordered direct variable-name keys found in the section.
    """
    result: List[str] = list()
    source_tokens: List[tokenize.TokenInfo] = list()
    try:
        source_token: tokenize.TokenInfo
        for source_token in tokenize.generate_tokens(StringIO(source).readline):
            source_tokens.append(source_token)
    except (IndentationError, tokenize.TokenError):
        # An unfinished key does not invalidate keys tokenized before it.
        pass

    insignificant_types: set[int] = set((
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.COMMENT,
    ))
    bracket_depth: int = 0
    waiting_for_assignment: bool = False
    waiting_for_dictionary: bool = False
    dictionary_depth: int = -1
    pending_key_name: str | None = None
    for source_token in source_tokens:
        token_text: str = source_token.string
        if dictionary_depth >= 0:
            if (bracket_depth == dictionary_depth
                    and source_token.type == tokenize.NAME):
                pending_key_name = token_text
            elif (bracket_depth == dictionary_depth
                  and source_token.type == tokenize.OP
                  and token_text == ":"):
                if pending_key_name is not None and pending_key_name not in result:
                    result.append(pending_key_name)
                else:
                    pass
                pending_key_name = None
            elif (bracket_depth == dictionary_depth
                  and source_token.type == tokenize.OP
                  and token_text == ","):
                pending_key_name = None
            else:
                pass

            if source_token.type == tokenize.OP and token_text in ("(", "[", "{"):
                bracket_depth += 1
            elif source_token.type == tokenize.OP and token_text in (")", "]", "}"):
                closes_dictionary: bool = (
                    token_text == "}" and bracket_depth == dictionary_depth
                )
                bracket_depth = max(0, bracket_depth - 1)
                if closes_dictionary:
                    dictionary_depth = -1
                    pending_key_name = None
                else:
                    pass
            else:
                pass
        elif waiting_for_dictionary:
            if source_token.type in insignificant_types:
                pass
            elif source_token.type == tokenize.OP and token_text == "{":
                bracket_depth += 1
                dictionary_depth = bracket_depth
                waiting_for_dictionary = False
            else:
                waiting_for_dictionary = False
        elif waiting_for_assignment:
            if source_token.type in insignificant_types:
                pass
            elif source_token.type == tokenize.OP and token_text == "=":
                waiting_for_assignment = False
                waiting_for_dictionary = True
            else:
                waiting_for_assignment = False
        else:
            if (bracket_depth == 0
                    and source_token.type == tokenize.NAME
                    and token_text == section_name):
                waiting_for_assignment = True
            else:
                pass
            if source_token.type == tokenize.OP and token_text in ("(", "[", "{"):
                bracket_depth += 1
            elif source_token.type == tokenize.OP and token_text in (")", "]", "}"):
                bracket_depth = max(0, bracket_depth - 1)
            else:
                pass
    return result


def get_procedural_call_context(
        source_tokens: Sequence[tokenize.TokenInfo],
        line_prefix: str,
) -> tuple[ProceduralLogicType | None, str | None]:
    """Find an unclosed procedural call and its active named argument.

    The token walk remains useful while the complete model source is invalid or
    unfinished, which is the normal state between keystrokes.

    :param source_tokens: Tokens emitted before the current cursor.
    :param line_prefix: Visible text from the current line start to the cursor.
    :return: Active procedural type and argument keyword, when detectable.
    """
    active_tpe: ProceduralLogicType | None = None
    active_depth: int = -1
    bracket_depth: int = 0
    pending_name: str | None = None
    insignificant_types: set[int] = set((
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.COMMENT,
    ))
    source_token: tokenize.TokenInfo
    for source_token in source_tokens:
        token_text: str = source_token.string
        if source_token.type == tokenize.NAME:
            pending_name = token_text
        elif source_token.type == tokenize.OP and token_text == "(":
            bracket_depth += 1
            matched_tpe: ProceduralLogicType | None = None
            descriptor: ProceduralBlockTemplateDescriptor
            for descriptor in get_dynamic_library_procedural_descriptors():
                logic_tpe: ProceduralLogicType = descriptor.logic_tpe
                if logic_tpe.value == pending_name:
                    matched_tpe = logic_tpe
                else:
                    pass
            if matched_tpe is not None:
                active_tpe = matched_tpe
                active_depth = bracket_depth
            else:
                pass
            pending_name = None
        elif source_token.type == tokenize.OP and token_text in ("[", "{"):
            bracket_depth += 1
            pending_name = None
        elif source_token.type == tokenize.OP and token_text in (")", "]", "}"):
            closes_active_call: bool = (
                active_tpe is not None
                and token_text == ")"
                and bracket_depth == active_depth
            )
            bracket_depth = max(0, bracket_depth - 1)
            if closes_active_call:
                active_tpe = None
                active_depth = -1
            else:
                pass
            pending_name = None
        elif source_token.type in insignificant_types:
            pass
        else:
            pending_name = None

    argument_match: re.Match[str] | None = re.search(
        r"\b([A-Za-z_]\w*)\s*=\s*[^,]*$",
        line_prefix,
    )
    if active_tpe is not None and argument_match is not None:
        active_argument: str | None = argument_match.group(1)
    else:
        active_argument = None
    return active_tpe, active_argument


def analyze_dae_completion_position(source: str,
                                    cursor_position: int) -> DaeCompletionPosition:
    """Determine the active DAE section and dictionary side at the cursor.

    Tokenization tolerates incomplete source by retaining every token emitted
    before ``TokenError``. Bracket depth then identifies the top-level section
    without treating nested function calls as new dictionary entries.

    :param source: Complete visible DAE source.
    :param cursor_position: Absolute cursor offset in ``source``.
    :return: Lexical completion context for candidate filtering.
    """
    bounded_position: int = min(max(0, cursor_position), len(source))
    prefix: str = extract_dae_identifier_prefix(source, bounded_position)
    line_start: int = source.rfind("\n", 0, bounded_position) + 1
    line_prefix: str = source[line_start:bounded_position]
    indentation_match: re.Match[str] | None = re.match(r"[ \t]*", line_prefix)
    if indentation_match is None:
        line_indentation: str = ""
    else:
        line_indentation = indentation_match.group(0)
    suppressed: bool = (
        cursor_is_in_dae_non_code_text(source, bounded_position)
        or cursor_is_in_dae_number(source, bounded_position)
    )
    if suppressed:
        return DaeCompletionPosition(
            prefix=prefix,
            section_name=None,
            expects_mapping_key=False,
            mapping_key_names=list(),
            suppressed=True,
            line_indentation=line_indentation,
            procedural_logic_tpe=None,
            procedural_argument=None,
        )
    else:
        pass

    source_prefix: str = source[:bounded_position]
    source_tokens: List[tokenize.TokenInfo] = list()
    try:
        source_token: tokenize.TokenInfo
        for source_token in tokenize.generate_tokens(StringIO(source_prefix).readline):
            source_tokens.append(source_token)
    except (IndentationError, tokenize.TokenError):
        # Incomplete expressions are the normal state while typing. Tokens
        # emitted before the unfinished tail still describe the active section.
        pass

    procedural_logic_tpe: ProceduralLogicType | None
    procedural_argument: str | None
    procedural_logic_tpe, procedural_argument = get_procedural_call_context(
        source_tokens=source_tokens,
        line_prefix=line_prefix,
    )

    section_names: tuple[str, ...] = get_dae_section_names()
    bracket_depth: int = 0
    pending_section: str | None = None
    waiting_for_assignment: bool = False
    active_section: str | None = None
    active_section_depth: int = -1
    expects_mapping_key: bool = False
    insignificant_types: set[int] = set((
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.COMMENT,
    ))

    for source_token in source_tokens:
        token_text: str = source_token.string
        if source_token.type == tokenize.NAME and bracket_depth == 0:
            if token_text in section_names:
                pending_section = token_text
                waiting_for_assignment = True
            else:
                pending_section = None
                waiting_for_assignment = False
        elif waiting_for_assignment and source_token.type in insignificant_types:
            pass
        elif waiting_for_assignment and source_token.type == tokenize.OP and token_text == "=":
            waiting_for_assignment = False
        elif pending_section is not None and source_token.type in insignificant_types:
            pass
        elif (pending_section is not None
              and source_token.type == tokenize.OP
              and token_text in ("[", "{")):
            bracket_depth += 1
            active_section = pending_section
            active_section_depth = bracket_depth
            expects_mapping_key = token_text == "{"
            pending_section = None
        else:
            if source_token.type == tokenize.OP and token_text in ("(", "[", "{"):
                bracket_depth += 1
            elif source_token.type == tokenize.OP and token_text in (")", "]", "}"):
                bracket_depth = max(0, bracket_depth - 1)
                if active_section is not None and bracket_depth < active_section_depth:
                    active_section = None
                    active_section_depth = -1
                    expects_mapping_key = False
                else:
                    pass
            else:
                pass

            if (active_section in ("state_eqs", "init_eqs", "diff_init_eqs")
                    and bracket_depth == active_section_depth
                    and source_token.type == tokenize.OP):
                if token_text == ",":
                    expects_mapping_key = True
                elif token_text == ":":
                    expects_mapping_key = False
                else:
                    pass
            else:
                pass
    if active_section in ("state_eqs", "init_eqs", "diff_init_eqs"):
        mapping_key_names: List[str] = get_dae_mapping_key_names(
            source,
            active_section,
        )
    else:
        mapping_key_names = list()
    return DaeCompletionPosition(
        prefix=prefix,
        section_name=active_section,
        expects_mapping_key=expects_mapping_key,
        mapping_key_names=mapping_key_names,
        suppressed=False,
        line_indentation=line_indentation,
        procedural_logic_tpe=procedural_logic_tpe,
        procedural_argument=procedural_argument,
    )


def build_entries_for_names(names: Sequence[str],
                            symbol_entries: Sequence[DaeCompletionEntry],
                            append_mapping_separator: bool,
                            excluded_names: Sequence[str]) -> List[DaeCompletionEntry]:
    """Select symbol entries by name and adapt dictionary-key insertion.

    :param names: Symbol names permitted by the active DAE section.
    :param symbol_entries: All typed symbols visible to the equation owner.
    :param append_mapping_separator: Whether selection inserts ``": "``.
    :param excluded_names: Existing mapping keys that must not be repeated.
    :return: Ordered context-specific symbol completions.
    """
    entry_lookup: Dict[str, DaeCompletionEntry] = dict()
    symbol_entry: DaeCompletionEntry
    for symbol_entry in symbol_entries:
        entry_lookup[symbol_entry.get_name()] = symbol_entry

    result: List[DaeCompletionEntry] = list()
    excluded_name_set: set[str] = set(excluded_names)
    name: str
    for name in names:
        if name in excluded_name_set:
            pass
        else:
            existing_entry: DaeCompletionEntry | None = entry_lookup.get(name, None)
            if existing_entry is None:
                description: str = "Symbolic variable"
            else:
                description = existing_entry.get_description()
            if append_mapping_separator:
                insertion_text: str = f"{name}: "
            else:
                insertion_text = name
            result.append(
                DaeCompletionEntry(
                    name=name,
                    display_text=name,
                    insertion_text=insertion_text,
                    description=description,
                )
            )
    return result


def build_dae_completion_entries(context: DaeLanguageContext,
                                 position: DaeCompletionPosition) -> List[DaeCompletionEntry]:
    """Return candidates valid for one section, cursor side, and prefix.

    :param context: Current staged symbol and variable-role context.
    :param position: Lexical cursor position produced from visible source.
    :return: Ordered prefix-filtered completion entries.
    """
    if position.is_suppressed():
        return list()
    else:
        pass

    section_name: str | None = position.get_section_name()
    symbol_entries: List[DaeCompletionEntry] = context.get_symbol_entries()
    candidates: List[DaeCompletionEntry]
    if section_name is None:
        candidates = list()
        dae_section_name: str
        for dae_section_name in get_dae_section_names():
            candidates.append(
                DaeCompletionEntry(
                    name=dae_section_name,
                    display_text=dae_section_name,
                    insertion_text=dae_section_name,
                    description="DAE model section",
                )
            )
    elif section_name == "state_vars":
        candidates = build_entries_for_names(
            context.get_state_names(), symbol_entries, False, list()
        )
    elif section_name == "algebraic_vars":
        candidates = build_entries_for_names(
            context.get_algebraic_names(), symbol_entries, False, list()
        )
    elif section_name == "diff_vars":
        candidates = build_entries_for_names(
            context.get_differential_names(), symbol_entries, False, list()
        )
    elif section_name == "state_eqs" and position.expects_mapping_key():
        candidates = build_entries_for_names(
            context.get_state_names(),
            symbol_entries,
            True,
            position.get_mapping_key_names(),
        )
    elif section_name == "diff_init_eqs" and position.expects_mapping_key():
        candidates = build_entries_for_names(
            context.get_differential_names(),
            symbol_entries,
            True,
            position.get_mapping_key_names(),
        )
    elif section_name == "init_eqs" and position.expects_mapping_key():
        candidates = build_entries_for_names(
            context.get_initializable_names(),
            symbol_entries,
            True,
            position.get_mapping_key_names(),
        )
    elif section_name == "procedural_logic":
        procedural_logic_tpe: ProceduralLogicType | None = (
            position.get_procedural_logic_tpe()
        )
        procedural_argument: str | None = position.get_procedural_argument()
        if procedural_logic_tpe is None:
            candidates = build_procedural_function_entries(
                position.get_line_indentation()
            )
        elif procedural_argument is None:
            candidates = list()
        else:
            field_tpe: ProceduralFieldType | None = get_procedural_code_field_type(
                procedural_logic_tpe,
                procedural_argument,
            )
            if field_tpe == ProceduralFieldType.MODE_REFERENCE:
                candidates = build_entries_for_names(
                    context.get_mode_names(), symbol_entries, False, list()
                )
            elif field_tpe == ProceduralFieldType.VARIABLE_REFERENCE:
                candidates = build_entries_for_names(
                    context.get_variable_names(), symbol_entries, False, list()
                )
            elif field_tpe == ProceduralFieldType.RUNTIME_REFERENCE:
                candidates = build_entries_for_names(
                    context.get_runtime_parameter_names(), symbol_entries, False, list()
                )
            elif field_tpe == ProceduralFieldType.TARGET_REFERENCE:
                candidates = list(symbol_entries)
            elif field_tpe == ProceduralFieldType.EXPRESSION:
                candidates = list(symbol_entries)
                candidates.extend(build_symbolic_function_entries())
            elif field_tpe == ProceduralFieldType.BOOLEAN:
                candidates = list((
                    DaeCompletionEntry(
                        name="True",
                        display_text="True",
                        insertion_text="True",
                        description="Boolean true value",
                    ),
                    DaeCompletionEntry(
                        name="False",
                        display_text="False",
                        insertion_text="False",
                        description="Boolean false value",
                    ),
                ))
            else:
                candidates = list()
    else:
        candidates = symbol_entries
        candidates.extend(build_symbolic_function_entries())

    prefix: str = position.get_prefix().lower()
    filtered: List[DaeCompletionEntry] = list()
    names_seen: set[str] = set()
    candidate: DaeCompletionEntry
    for candidate in candidates:
        normalized_name: str = candidate.get_name().lower()
        prefix_matches: bool = len(prefix) == 0 or normalized_name.startswith(prefix)
        if prefix_matches and candidate.get_name() not in names_seen:
            names_seen.add(candidate.get_name())
            filtered.append(candidate)
        else:
            pass
    return filtered
