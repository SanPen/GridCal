# SPDX-License-Identifier: MPL-2.0
"""Pure source diagnostics for the Dynamic Editor DAE language."""

from __future__ import annotations

import ast
from io import StringIO
import re
import tokenize
from typing import List, Mapping

from VeraGridEngine.Utils.Symbolic.symbolic import (
    Expr,
    get_symbolic_parser_function_arity,
    get_symbolic_parser_function_names,
)
from VeraGridEngine.enumerations import ProceduralLogicType
from VeraGridEngine.Templates.ProceduralLogicCatalog import (
    ProceduralBlockTemplateDescriptor,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_library import (
    get_dynamic_library_procedural_descriptors,
)


class DaeCodeDiagnostic:
    """One source-local validation error rendered by the DAE editor."""

    __slots__ = ("_line", "_column", "_length", "_message")

    def __init__(self, line: int, column: int, length: int, message: str) -> None:
        """Store one source span and its actionable explanation.

        :param line: One-based source line.
        :param column: Zero-based source column.
        :param length: Number of source characters associated with the error.
        :param message: User-facing validation explanation.
        :return: None.
        """
        self._line: int = max(1, line)
        self._column: int = max(0, column)
        self._length: int = max(1, length)
        self._message: str = message

    def get_line(self) -> int:
        """Return the one-based source line.

        :return: Diagnostic source line.
        """
        return self._line

    def get_column(self) -> int:
        """Return the zero-based source column.

        :return: Diagnostic source column.
        """
        return self._column

    def get_length(self) -> int:
        """Return the highlighted source length.

        :return: Positive diagnostic span length.
        """
        return self._length

    def get_message(self) -> str:
        """Return the user-facing validation explanation.

        :return: Diagnostic message.
        """
        return self._message


def find_text_diagnostic(code: str, token: str, message: str) -> DaeCodeDiagnostic:
    """Locate a semantic-error token and build a best-effort diagnostic.

    :param code: Complete DAE source.
    :param token: Identifier or section associated with the error.
    :param message: Validation explanation.
    :return: Located diagnostic, falling back to the first source character.
    """
    lines: List[str] = code.splitlines()
    line_index: int
    for line_index in range(len(lines)):
        column: int = lines[line_index].find(token)
        if column >= 0:
            return DaeCodeDiagnostic(line_index + 1, column, len(token), message)
        else:
            pass
    return DaeCodeDiagnostic(1, 0, 1, message)


def brackets_match(opening_bracket: str, closing_bracket: str) -> bool:
    """Return whether two punctuation tokens form one bracket pair.

    :param opening_bracket: Candidate opening token.
    :param closing_bracket: Candidate closing token.
    :return: Whether the pair uses matching punctuation.
    """
    if opening_bracket == "(" and closing_bracket == ")":
        result: bool = True
    elif opening_bracket == "[" and closing_bracket == "]":
        result = True
    elif opening_bracket == "{" and closing_bracket == "}":
        result = True
    else:
        result = False
    return result


def normalize_algebraic_equality_syntax(code: str) -> str:
    """Translate visible algebraic equality signs into a parse-only marker.

    A mathematical equality inside a Python list is not valid Python syntax.
    Tokenization replaces only equality signs inside ``algebraic_eqs`` with an
    unsupported bitwise-or marker. The single-character replacement preserves
    all source lines and columns used by diagnostics and the DAE parser.

    :param code: User-visible DAE source containing mathematical equalities.
    :return: Temporary Python-parseable source with identical coordinates.
    :raises ValueError: If the reserved marker is written directly by the user.
    """
    normalized_tokens: List[tokenize.TokenInfo] = list()
    bracket_depth: int = 0
    waiting_for_assignment: bool = False
    waiting_for_list: bool = False
    algebraic_list_depth: int | None = None
    equality_was_replaced: bool = False
    insignificant_token_types: set[int] = set((
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.COMMENT,
    ))

    try:
        source_token: tokenize.TokenInfo
        for source_token in tokenize.generate_tokens(StringIO(code).readline):
            token_text: str = source_token.string
            replacement_token: tokenize.TokenInfo = source_token
            if algebraic_list_depth is not None:
                if source_token.type == tokenize.OP and token_text == "=":
                    replacement_token = source_token._replace(string="|")
                    equality_was_replaced = True
                elif source_token.type == tokenize.OP and token_text == "|":
                    raise ValueError(
                        "The '|' operator is not supported inside algebraic_eqs; "
                        "use one '=' to separate the two equation sides"
                    )
                else:
                    pass
            else:
                pass
            normalized_tokens.append(replacement_token)

            if algebraic_list_depth is not None:
                if source_token.type == tokenize.OP and token_text in ("(", "[", "{"):
                    bracket_depth += 1
                elif source_token.type == tokenize.OP and token_text in (")", "]", "}"):
                    closes_algebraic_list: bool = (
                        token_text == "]" and bracket_depth == algebraic_list_depth
                    )
                    bracket_depth = max(0, bracket_depth - 1)
                    if closes_algebraic_list:
                        algebraic_list_depth = None
                    else:
                        pass
                else:
                    pass
            elif waiting_for_list:
                if source_token.type in insignificant_token_types:
                    pass
                elif source_token.type == tokenize.OP and token_text == "[":
                    bracket_depth += 1
                    algebraic_list_depth = bracket_depth
                    waiting_for_list = False
                else:
                    waiting_for_list = False
            elif waiting_for_assignment:
                if source_token.type in insignificant_token_types:
                    pass
                elif source_token.type == tokenize.OP and token_text == "=":
                    waiting_for_assignment = False
                    waiting_for_list = True
                else:
                    waiting_for_assignment = False
            else:
                if (bracket_depth == 0
                        and source_token.type == tokenize.NAME
                        and token_text == "algebraic_eqs"):
                    waiting_for_assignment = True
                else:
                    pass
                if source_token.type == tokenize.OP and token_text in ("(", "[", "{"):
                    bracket_depth += 1
                elif source_token.type == tokenize.OP and token_text in (")", "]", "}"):
                    bracket_depth = max(0, bracket_depth - 1)
                else:
                    pass
        normalized_code: str = tokenize.untokenize(normalized_tokens)
    except (IndentationError, tokenize.TokenError):
        # Preserve all completed replacements so the AST parser reaches the
        # actionable unmatched token rather than the visible equality syntax.
        if equality_was_replaced:
            normalized_code = tokenize.untokenize(normalized_tokens)
        else:
            normalized_code = code
    return normalized_code


def build_unmatched_opening_bracket_diagnostic(
        code: str,
        message: str,
        fallback_line: int) -> DaeCodeDiagnostic | None:
    """Locate the opening bracket named by one Python syntax error.

    :param code: Complete DAE source.
    :param message: Message produced by :func:`ast.parse`.
    :param fallback_line: Syntax-error line when Python omits the opening line.
    :return: Opening-bracket diagnostic or ``None`` when it cannot be located.
    """
    opening_match: re.Match[str] | None = re.search(
        r"opening parenthesis '([\(\[\{])'(?: on line (\d+))?",
        message,
    )
    if opening_match is None:
        return None
    else:
        opening_symbol: str = opening_match.group(1)
        opening_line_text: str | None = opening_match.group(2)
        if opening_line_text is None:
            opening_line: int = fallback_line
        else:
            opening_line = int(opening_line_text)

    opening_stack: List[tuple[str, int, int]] = list()
    try:
        token_entry: tokenize.TokenInfo
        for token_entry in tokenize.generate_tokens(StringIO(code).readline):
            if token_entry.type == tokenize.OP:
                punctuation: str = token_entry.string
                if punctuation in ("(", "[", "{"):
                    opening_stack.append(
                        (punctuation, token_entry.start[0], token_entry.start[1])
                    )
                elif punctuation in (")", "]", "}"):
                    if (len(opening_stack) > 0
                            and brackets_match(opening_stack[-1][0], punctuation)):
                        opening_stack.pop()
                    else:
                        pass
                else:
                    pass
            else:
                pass
    except (IndentationError, tokenize.TokenError):
        pass

    stack_entry: tuple[str, int, int]
    for stack_entry in opening_stack:
        if stack_entry[0] == opening_symbol and stack_entry[1] == opening_line:
            diagnostic_message: str = (
                f"{message}. Fix this unmatched opening bracket, then validate "
                "again to inspect the remaining code"
            )
            return DaeCodeDiagnostic(
                stack_entry[1],
                stack_entry[2],
                1,
                diagnostic_message,
            )
        else:
            pass
    return None


def build_missing_algebraic_comma_diagnostic(
        code: str,
        syntax_error_line: int) -> DaeCodeDiagnostic | None:
    """Mark an algebraic equality following an unseparated list entry.

    :param code: Original user-visible DAE source.
    :param syntax_error_line: One-based line reported by the AST parser.
    :return: Missing-comma diagnostic, or ``None`` when the pattern is absent.
    """
    source_lines: List[str] = code.splitlines()
    if syntax_error_line <= 1 or syntax_error_line > len(source_lines):
        return None
    else:
        pass
    current_line: str = source_lines[syntax_error_line - 1]
    previous_line_index: int = syntax_error_line - 2
    while (previous_line_index >= 0
           and len(source_lines[previous_line_index].strip()) == 0):
        previous_line_index -= 1
    if previous_line_index < 0:
        previous_line: str = ""
    else:
        previous_line = source_lines[previous_line_index].rstrip()

    source_prefix: str = "\n".join(source_lines[:syntax_error_line])
    algebraic_start: int = source_prefix.rfind("algebraic_eqs")
    algebraic_end: int = source_prefix.rfind("]")
    inside_algebraic_section: bool = algebraic_start >= 0 and algebraic_start > algebraic_end
    previous_entry_is_open: bool = (
        len(previous_line) > 0
        and not previous_line.endswith(",")
        and not previous_line.endswith("[")
    )
    reported_line_starts_equation: bool = "=" in current_line
    if (inside_algebraic_section
            and reported_line_starts_equation
            and previous_entry_is_open):
        first_source_column: int = len(current_line) - len(current_line.lstrip())
        return DaeCodeDiagnostic(
            syntax_error_line,
            first_source_column,
            max(1, len(current_line.strip())),
            "Possible missing comma before this algebraic equation",
        )
    else:
        pass

    following_line_number: int = syntax_error_line + 1
    if following_line_number <= len(source_lines):
        following_line: str = source_lines[following_line_number - 1]
        current_entry_is_open: bool = (
            len(current_line.rstrip()) > 0
            and not current_line.rstrip().endswith(",")
            and not current_line.rstrip().endswith("[")
        )
        following_line_starts_equation: bool = "=" in following_line
        if (inside_algebraic_section
                and current_entry_is_open
                and following_line_starts_equation):
            following_source_column: int = len(following_line) - len(following_line.lstrip())
            return DaeCodeDiagnostic(
                following_line_number,
                following_source_column,
                max(1, len(following_line.strip())),
                "Possible missing comma before this algebraic equation",
            )
        else:
            pass
    else:
        pass
    return None


def build_dae_code_diagnostics(code: str,
                               namespace: Mapping[str, Expr]) -> List[DaeCodeDiagnostic]:
    """Lint syntax, function calls, and unresolved symbolic names.

    :param code: Complete Python-like DAE source.
    :param namespace: Symbols currently valid in the dialogue draft.
    :return: Source-local diagnostics ordered by line and column.
    """
    result: List[DaeCodeDiagnostic] = list()
    try:
        normalized_code: str = normalize_algebraic_equality_syntax(code)
        module: ast.Module = ast.parse(normalized_code, mode="exec")
    except ValueError as error:
        result.append(find_text_diagnostic(code, "|", str(error)))
        return result
    except SyntaxError as error:
        line: int = 1 if error.lineno is None else int(error.lineno)
        column: int = 0 if error.offset is None else max(0, int(error.offset) - 1)
        error_text: str = error.msg if len(error.msg) > 0 else str(error)
        opening_diagnostic: DaeCodeDiagnostic | None = (
            build_unmatched_opening_bracket_diagnostic(code, error_text, line)
        )
        missing_comma_diagnostic: DaeCodeDiagnostic | None = (
            build_missing_algebraic_comma_diagnostic(code, line)
        )
        if opening_diagnostic is not None:
            result.append(opening_diagnostic)
        elif missing_comma_diagnostic is not None:
            result.append(missing_comma_diagnostic)
        else:
            result.append(DaeCodeDiagnostic(line, column, 1, error_text))
        return result

    callable_names: set[str] = set(get_symbolic_parser_function_names())
    procedural_callable_names: set[str] = set()
    descriptor: ProceduralBlockTemplateDescriptor
    for descriptor in get_dynamic_library_procedural_descriptors():
        procedural_callable_names.add(descriptor.logic_tpe.value)
    allowed_names: set[str] = set(namespace.keys())
    allowed_names.update(callable_names)
    allowed_names.update(procedural_callable_names)
    allowed_names.update(set((
        "state_vars",
        "algebraic_vars",
        "diff_vars",
        "state_eqs",
        "algebraic_eqs",
        "init_eqs",
        "diff_init_eqs",
        "retained_modes",
        "procedural_logic",
    )))
    handled_name_positions: set[tuple[int, int]] = set()
    ast_node: ast.AST
    for ast_node in ast.walk(module):
        if isinstance(ast_node, ast.Call):
            if isinstance(ast_node.func, ast.Name):
                function_name: str = ast_node.func.id
                function_arity: int | None = get_symbolic_parser_function_arity(
                    function_name
                )
            else:
                function_name = ""
                function_arity = None
            procedural_function: bool = function_name in procedural_callable_names
            known_function: bool = function_name in callable_names
            valid_function_call: bool = (
                known_function
                and function_arity == len(ast_node.args)
                and len(ast_node.keywords) == 0
            )
            if procedural_function:
                # Typed procedural signatures are validated by the model-code
                # parser, which can report missing and unknown keyword names.
                pass
            elif valid_function_call:
                pass
            elif known_function and function_arity is not None:
                argument_word: str = "argument" if function_arity == 1 else "arguments"
                call_length: int = max(
                    1,
                    int(ast_node.end_col_offset) - int(ast_node.col_offset),
                )
                result.append(
                    DaeCodeDiagnostic(
                        int(ast_node.lineno),
                        int(ast_node.col_offset),
                        call_length,
                        f"Function '{function_name}' expects {function_arity} {argument_word}",
                    )
                )
            elif isinstance(ast_node.func, ast.Name):
                # A named call that is outside the symbolic parser catalogue is
                # an unsupported DAE function, not an accidental Python call.
                function_position: tuple[int, int] = (
                    int(ast_node.func.lineno),
                    int(ast_node.func.col_offset),
                )
                handled_name_positions.add(function_position)
                result.append(
                    DaeCodeDiagnostic(
                        function_position[0],
                        function_position[1],
                        len(function_name),
                        f"Unsupported symbolic function '{function_name}'",
                    )
                )
            elif len(ast_node.args) > 0:
                # Adjacent parenthesized entries are parsed as a call. Mark the
                # called expression as the likely location of a missing comma.
                called_argument: ast.AST = ast_node.args[0]
                argument_length: int = max(
                    1,
                    int(called_argument.end_col_offset) - int(called_argument.col_offset),
                )
                result.append(
                    DaeCodeDiagnostic(
                        int(called_argument.lineno),
                        int(called_argument.col_offset),
                        argument_length,
                        "Possible missing comma before this expression",
                    )
                )
            else:
                result.append(
                    DaeCodeDiagnostic(
                        int(ast_node.lineno),
                        int(ast_node.col_offset),
                        1,
                        "Unsupported function call in DAE code",
                    )
                )
        elif isinstance(ast_node, ast.Name) and isinstance(ast_node.ctx, ast.Load):
            name_position: tuple[int, int] = (
                int(ast_node.lineno),
                int(ast_node.col_offset),
            )
            if name_position in handled_name_positions:
                pass
            elif ast_node.id not in allowed_names:
                result.append(
                    DaeCodeDiagnostic(
                        int(ast_node.lineno),
                        int(ast_node.col_offset),
                        len(ast_node.id),
                        f"Unknown symbol '{ast_node.id}'",
                    )
                )
            else:
                pass
        else:
            pass
    result.sort(key=build_diagnostic_sort_key)
    return result


def build_diagnostic_sort_key(diagnostic: DaeCodeDiagnostic) -> tuple[int, int]:
    """Return deterministic source order for one diagnostic.

    :param diagnostic: Diagnostic being ordered.
    :return: Line and column tuple.
    """
    return diagnostic.get_line(), diagnostic.get_column()


def build_semantic_dae_diagnostic(code: str, message: str) -> DaeCodeDiagnostic:
    """Infer the most useful source span for one parser or count error.

    :param code: Complete DAE source.
    :param message: Semantic parser explanation.
    :return: Best-effort source-local diagnostic.
    """
    quoted_match: re.Match[str] | None = re.search(r"'(\w+)'", message)
    if quoted_match is not None:
        token: str = quoted_match.group(1)
    elif "state variables" in message:
        token = "state_eqs"
    elif "algebraic variables" in message:
        token = "algebraic_eqs"
    else:
        token = code.strip().split(maxsplit=1)[0] if len(code.strip()) > 0 else ""
    return find_text_diagnostic(code, token, message)
