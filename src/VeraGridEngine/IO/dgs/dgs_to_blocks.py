# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import ast
import math
import re
from enum import IntEnum
from typing import Dict, Iterable, List, Sequence, Set, Tuple

import VeraGridEngine.Utils.Symbolic.symbolic as symbolic
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_discrete_event import (
    DgsDiscreteEventAction,
    DgsDiscreteEventCommand,
    parse_dgs_discrete_event_statement,
)
from VeraGridEngine.IO.dgs.dgs_objects import (
    BlkDef,
    BlkDiv,
    BlkFrom,
    BlkGoto,
    BlkMul,
    BlkRef,
    BlkSig,
    BlkSlot,
    BlkSum,
    BlkSwt,
    DGSElement,
    ElmComp,
    ElmDsl,
    StaCubic,
    StaSwitch,
)
from VeraGridEngine.Templates.BasicBlockCatalog.basic_block_catalog import (
    get_basic_block_catalog_descriptors,
)
from VeraGridEngine.Utils.procedural_logic import (
    AnalogFlipFlopLogic,
    ConditionalDiagnosticLogic,
    DelayedSwitchEventLogic,
    FixedSampleLogic,
    FlipFlopLogic,
    GradientLimiterLogic,
    MovingAverageLogic,
    ProceduralLogicCodec,
    ProceduralLogicBase,
    PickupDropoffLogic,
    ResetOnRisingEdgeLogic,
    SampledValueLogic,
    TimeDelayLogic,
    clone_procedural_logic_entries,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import (
    acos,
    CmpOp,
    Comparison,
    Const,
    Expr,
    Func2,
    Var,
    abs,
    cos,
    exp,
    hard_sat,
    heaviside,
    log,
    sin,
    sqrt,
    tan,
)
from VeraGridEngine.enumerations import BlockScopeMode, DynamicSimulationMode


class DgsGraphicalConnectorKind(IntEnum):
    """Identify the connector categories encoded by graphical ``BlkSig`` rows."""

    Input = 1
    Output = 2
    LowerLimitInput = 3
    UpperLimitInput = 4


class DgsSlotSignalDirection(IntEnum):
    """Select one declared DGS slot-signal direction."""

    Input = 1
    Output = 2


def _parse_dgs_graphical_connector_kind(
        connector_code: int,
) -> DgsGraphicalConnectorKind | None:
    """
    Convert one raw connector code without rejecting vendor extensions.

    :param connector_code: Integer stored in ``iconfrom`` or ``iconto``.
    :return: Known connector category, or ``None`` for an implicit category.
    """
    connector_kind: DgsGraphicalConnectorKind | None
    if connector_code == int(DgsGraphicalConnectorKind.Input):
        connector_kind = DgsGraphicalConnectorKind.Input
    elif connector_code == int(DgsGraphicalConnectorKind.Output):
        connector_kind = DgsGraphicalConnectorKind.Output
    elif connector_code == int(DgsGraphicalConnectorKind.LowerLimitInput):
        connector_kind = DgsGraphicalConnectorKind.LowerLimitInput
    elif connector_code == int(DgsGraphicalConnectorKind.UpperLimitInput):
        connector_kind = DgsGraphicalConnectorKind.UpperLimitInput
    else:
        connector_kind = None
    return connector_kind


def _parse_effective_graphical_connector_kind(
        connector_code: int,
        endpoint_node: object,
        is_source_endpoint: bool,
) -> DgsGraphicalConnectorKind | None:
    """
    Resolve implicit connector direction for native graphical operators.

    PowerFactory writes connector code zero for ordinary native-operator pins.
    Direction is then carried by whether the operator is ``pnodfrom`` or
    ``pnodto`` in the corresponding signal row.

    :param connector_code: Raw connector category.
    :param endpoint_node: Parsed object at the signal endpoint.
    :param is_source_endpoint: Whether this is the ``pnodfrom`` endpoint.
    :return: Effective connector category, or ``None`` when unsupported.
    """
    connector_kind: DgsGraphicalConnectorKind | None = (
        _parse_dgs_graphical_connector_kind(connector_code=connector_code)
    )
    if connector_kind is not None:
        result: DgsGraphicalConnectorKind | None = connector_kind
    elif isinstance(endpoint_node, (BlkDiv, BlkMul, BlkSum, BlkSwt)):
        if is_source_endpoint:
            result = DgsGraphicalConnectorKind.Output
        else:
            result = DgsGraphicalConnectorKind.Input
    else:
        result = None
    return result


def _resolve_graphical_runtime_output_index(
        endpoint_node: object | None,
        graphical_output_index: int,
        exported_output_base: int,
        runtime_output_count: int,
) -> int | None:
    """
    Map one exported graphical output pin to a compact runtime output.

    Native operators number their output after their input pins, while the
    runtime block stores outputs in an independent compact vector. Other node
    types retain their exported zero-based output index.

    :param endpoint_node: Parsed graphical source node.
    :param graphical_output_index: Raw ``BlkSig.inodfrom`` value.
    :param exported_output_base: First raw output-port index.
    :param runtime_output_count: Number of runtime outputs on the source block.
    :return: Compact runtime output index, or ``None`` when it is unresolved.
    """
    endpoint_is_native_operator: bool = isinstance(
        endpoint_node,
        (BlkDiv, BlkMul, BlkSum, BlkSwt),
    )
    if 0 <= graphical_output_index < runtime_output_count:
        runtime_output_index: int | None = graphical_output_index
    elif (
            endpoint_is_native_operator
            and runtime_output_count > 0
            and exported_output_base <= graphical_output_index < (
                    exported_output_base + runtime_output_count
            )
    ):
        runtime_output_index = graphical_output_index - exported_output_base
    else:
        runtime_output_index = None
    return runtime_output_index


def _get_graphical_exported_output_base(
        endpoint_node: object | None,
        input_index_by_connector: Dict[
            Tuple[DgsGraphicalConnectorKind, int],
            int,
        ],
) -> int:
    """Return the first raw output pin for one native graphical operator.

    :param endpoint_node: Parsed graphical source node.
    :param input_index_by_connector: Raw-to-runtime input connector map.
    :return: First raw output-port index, or zero for ordinary blocks.
    """
    if isinstance(endpoint_node, BlkSum):
        exported_output_base: int = 4
    elif isinstance(endpoint_node, BlkSwt):
        exported_output_base = 3
    elif isinstance(endpoint_node, (BlkDiv, BlkMul)):
        maximum_raw_input_index: int = -1
        connector_key: Tuple[DgsGraphicalConnectorKind, int]
        for connector_key in input_index_by_connector.keys():
            if (
                    connector_key[0] == DgsGraphicalConnectorKind.Input
                    and connector_key[1] > maximum_raw_input_index
            ):
                maximum_raw_input_index = connector_key[1]
            else:
                pass
        exported_output_base = maximum_raw_input_index + 1
    else:
        exported_output_base = 0
    return exported_output_base


def _build_ordinary_graphical_input_index(
        input_names: List[str],
) -> Dict[Tuple[DgsGraphicalConnectorKind, int], int]:
    """
    Map ordinary graphical input pins to compact runtime indices.

    :param input_names: Runtime input names in compact order.
    :return: Runtime indices keyed by connector category and raw port index.
    """
    input_index_by_connector: Dict[
        Tuple[DgsGraphicalConnectorKind, int],
        int,
    ] = dict()

    # Ordinary block inputs preserve their zero-based order directly.
    input_index: int
    for input_index in range(len(input_names)):
        input_index_by_connector[
            (DgsGraphicalConnectorKind.Input, input_index)
        ] = input_index
    else:
        pass
    return input_index_by_connector


def _safe_name(name: str) -> str:
    """

    :param name:
    :return:
    """
    cleaned: str = re.sub(r"[^0-9a-zA-Z_]", "_", name)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if cleaned == "":
        cleaned = "unnamed"
    if cleaned[0].isdigit():
        cleaned = f"v_{cleaned}"
    return cleaned


def _var_name_sort_key(var: Var) -> str:
    """
    Return the deterministic sort key for one symbolic variable.

    :param var: Symbolic variable.
    :returns: Variable-name sort key.
    """
    return var.name


def _strip_dgs_inline_comment(statement: str) -> str:
    """Remove a DGS ``!`` comment only when it is outside quoted data.

    Diagnostic messages legitimately contain exclamation marks, so a plain
    string split would corrupt the literal before the safe diagnostic parser
    can validate it.

    :param statement: One unsplit DGS statement surface.
    :return: Statement prefix before the first unquoted comment marker.
    """
    in_single_quote: bool = False
    in_double_quote: bool = False
    character_index: int
    character: str
    for character_index, character in enumerate(statement):
        if character == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif character == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif character == '!' and not in_single_quote and not in_double_quote:
            return statement[:character_index]
        else:
            pass
    return statement


def _find_dgs_continuation_end(
        blob: str,
        semicolon_index: int,
) -> int | None:
    """Locate the end of one exported continuation after a semicolon.

    PowerFactory may insert one or more ``!`` comment fields between the
    expression and the final ``&`` marker. Comments end at their next
    semicolon, so only that exact bounded shape is accepted as continuation.

    :param blob: Raw exported equation field.
    :param semicolon_index: Index of the semicolon ending data or a comment.
    :return: Index after ``&`` when this is a continuation, otherwise ``None``.
    """
    probe_index: int = semicolon_index + 1
    while probe_index < len(blob):
        while probe_index < len(blob) and blob[probe_index].isspace():
            probe_index += 1
        if probe_index < len(blob) and blob[probe_index] == '&':
            return probe_index + 1
        elif probe_index < len(blob) and blob[probe_index] == '!':
            comment_end_index: int = blob.find(';', probe_index + 1)
            if comment_end_index < 0:
                return None
            else:
                probe_index = comment_end_index + 1
        else:
            return None
    return None


def _remove_dgs_line_continuations(blob: str) -> str:
    """Normalize exact PowerFactory equation-continuation surfaces.

    Comments bounded by their exported semicolon are discarded only while
    joining a continued equation. The semicolon remains an ordinary statement
    delimiter everywhere else. Quoted diagnostic and metadata text is data and
    therefore never rewritten.

    :param blob: Raw exported equation field.
    :return: Equation field with exact continuation surfaces replaced by spaces.
    """
    normalized: List[str] = list()
    in_single_quote: bool = False
    in_double_quote: bool = False
    character_index: int = 0
    while character_index < len(blob):
        character: str = blob[character_index]
        if character == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            normalized.append(character)
            character_index += 1
        elif character == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            normalized.append(character)
            character_index += 1
        elif character == '!' and not in_single_quote and not in_double_quote:
            comment_end_index: int = blob.find(';', character_index + 1)
            if comment_end_index < 0:
                character_index = len(blob)
            else:
                continuation_end_index: int | None = (
                    _find_dgs_continuation_end(
                        blob=blob,
                        semicolon_index=comment_end_index,
                    )
                )
                if continuation_end_index is None:
                    normalized.append(';')
                    character_index = comment_end_index + 1
                else:
                    normalized.append(' ')
                    character_index = continuation_end_index
        elif character == ';' and not in_single_quote and not in_double_quote:
            continuation_end_index = _find_dgs_continuation_end(
                blob=blob,
                semicolon_index=character_index,
            )
            if continuation_end_index is not None:
                normalized.append(' ')
                character_index = continuation_end_index
            else:
                normalized.append(character)
                character_index += 1
        else:
            normalized.append(character)
            character_index += 1
    return ''.join(normalized)


def _split_equation_statements(raw_equations: Iterable[str]) -> List[str]:
    """

    :param raw_equations:
    :return:
    """
    source_rows: List[str] = list(raw_equations)
    joined_rows: List[str] = list()
    row_index: int = 0
    while row_index < len(source_rows):
        source_row: str = source_rows[row_index]
        stripped_row: str = source_row.lstrip()
        if stripped_row.startswith('&'):
            if len(joined_rows) == 0:
                joined_rows.append(source_row)
            else:
                joined_rows[-1] = (
                    joined_rows[-1] + ';&' + stripped_row[1:]
                )
            row_index += 1
        elif stripped_row.startswith('!'):
            comment_rows: List[str] = list()
            comment_index: int = row_index
            while (
                    comment_index < len(source_rows)
                    and source_rows[comment_index].lstrip().startswith('!')
            ):
                comment_rows.append(source_rows[comment_index].lstrip())
                comment_index += 1
            follows_continuation: bool = bool(
                comment_index < len(source_rows)
                and source_rows[comment_index].lstrip().startswith('&')
            )
            if follows_continuation and len(joined_rows) > 0:
                joined_rows[-1] = (
                    joined_rows[-1]
                    + ';'
                    + ';'.join(comment_rows)
                    + ';&'
                    + source_rows[comment_index].lstrip()[1:]
                )
                row_index = comment_index + 1
            else:
                joined_rows.extend(comment_rows)
                row_index = comment_index
        else:
            joined_rows.append(source_row)
            row_index += 1

    statements: List[str] = list()
    blob: str
    ch: str
    stmt: str

    for blob in joined_rows:
        normalized_blob: str = _remove_dgs_line_continuations(blob=blob)
        token: List[str] = list()
        in_single_quote: bool = False
        in_double_quote: bool = False

        for ch in normalized_blob:
            if ch == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                token.append(ch)
            elif ch == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                token.append(ch)
            elif ch == ';' and not in_single_quote and not in_double_quote:
                stmt = _strip_dgs_inline_comment(
                    ''.join(token)
                ).strip().strip('"')
                if stmt != "" and not stmt.startswith('!'):
                    statements.append(stmt)
                token = list()
            else:
                token.append(ch)

        stmt = _strip_dgs_inline_comment(
            ''.join(token)
        ).strip().strip('"')
        if stmt != "" and not stmt.startswith('!'):
            statements.append(stmt)

    return statements


def classify_dgs_statement(statement: str) -> tuple[str, str | None]:
    """
    Classify a single DGS equation statement.

    :param statement: One normalized statement.
    :return: Pair ``(kind, lhs_name_or_none)``.
    """
    stmt = statement.strip()

    if stmt == "" or stmt.startswith('!'):
        return 'ignored', None

    if (stmt.startswith("'") and stmt.endswith("'")) or (stmt.startswith('"') and stmt.endswith('"')):
        return 'ignored', None

    if stmt.startswith('vardef('):
        return 'ignored', None

    unit_metadata_match: re.Match[str] | None = re.match(
        r"^\[(?P<lhs>[A-Za-z_][A-Za-z0-9_]*)]\s*=\s*(?P<unit>.+)$",
        stmt,
    )
    if unit_metadata_match is not None:
        return 'unit_metadata', unit_metadata_match.group('lhs')
    else:
        pass

    parameter_limit_match: re.Match[str] | None = re.match(
        r'^limfix\((?P<lhs>[^)]+)\)\s*=\s*(?P<interval>.+)$',
        stmt,
    )
    if parameter_limit_match is not None:
        return 'parameter_limit', parameter_limit_match.group('lhs').strip()
    else:
        pass

    runtime_limit_match: re.Match[str] | None = re.match(
        r'^limits\((?P<lhs>[^)]+)\)\s*=\s*(?P<interval>.+)$',
        stmt,
    )
    if runtime_limit_match is not None:
        return 'runtime_limit', runtime_limit_match.group('lhs').strip()
    else:
        pass

    init_match = re.match(r'^(?P<kind>inc0?|inc)\((?P<lhs>[^)]+)\)\s*=\s*(?P<rhs>.+)$', stmt)
    if init_match is not None:
        return init_match.group('kind').strip(), init_match.group('lhs').strip()

    diff_match = re.match(r'^(?P<lhs>.+?)\.\s*=\s*(?P<rhs>.+)$', stmt)
    if diff_match is not None:
        return 'state', diff_match.group('lhs').strip()

    if re.match(r'^reset\s*\(.+\)\s*$', stmt) is not None:
        return 'procedural', None

    if re.match(r'^(output|outfix)\s*\(.+\)\s*$', stmt) is not None:
        return 'diagnostic', None
    else:
        pass

    if re.match(r'^event\s*\(.+\)\s*$', stmt) is not None:
        return 'discrete_event', None
    else:
        pass

    alg_match = re.match(r'^(?P<lhs>[^=]+?)\s*=\s*(?P<rhs>.+)$', stmt)
    if alg_match is not None:
        return 'algebraic', alg_match.group('lhs').strip()

    return 'unsupported', None


def _split_dgs_call_arguments(argument_text: str) -> List[str]:
    """Split one DGS call body at top-level commas.

    Parentheses and braces may nest inside a boolean condition, while commas
    inside the quoted diagnostic text remain ordinary message characters.

    :param argument_text: Text between the outer call parentheses.
    :return: Ordered stripped argument surfaces.
    """
    arguments: List[str] = list()
    token: List[str] = list()
    delimiter_stack: List[str] = list()
    quote: str | None = None
    character: str
    for character in argument_text:
        if quote is not None:
            token.append(character)
            if character == quote:
                quote = None
            else:
                pass
        elif character in {"'", '"'}:
            quote = character
            token.append(character)
        elif character in {'(', '{', '['}:
            delimiter_stack.append(character)
            token.append(character)
        elif character in {')', '}', ']'}:
            if character == ')':
                expected_opening: str = '('
            elif character == '}':
                expected_opening = '{'
            else:
                expected_opening = '['
            if (
                    len(delimiter_stack) == 0
                    or delimiter_stack[-1] != expected_opening
            ):
                raise UnsupportedDgsExpression(
                    "Malformed delimiters in DGS call arguments"
                )
            else:
                delimiter_stack.pop()
                token.append(character)
        elif character == ',' and len(delimiter_stack) == 0:
            arguments.append(''.join(token).strip())
            token = list()
        else:
            token.append(character)

    if quote is not None:
        raise UnsupportedDgsExpression("Unterminated DGS string literal")
    elif len(delimiter_stack) > 0:
        raise UnsupportedDgsExpression(
            "Unterminated delimiter in DGS call arguments"
        )
    else:
        arguments.append(''.join(token).strip())
    return arguments


def _parse_dgs_quoted_literal(literal_text: str) -> str:
    """Decode a plain DGS quoted literal without evaluating source text.

    PowerFactory documents diagnostic message strings with single-quote
    delimiters. The observed bracket-unit surface uses the same representation.
    Ambiguous embedded delimiters fail closed.

    :param literal_text: Candidate quoted source literal.
    :return: Exact text inside the matching delimiters.
    """
    text: str = literal_text.strip()
    if len(text) < 2 or text[0] != "'" or text[-1] != "'":
        raise UnsupportedDgsExpression(
            "DGS text must be a single-quoted literal"
        )
    else:
        message: str = text[1:-1]
    if "'" in message:
        raise UnsupportedDgsExpression(
            "Embedded diagnostic quote syntax is unsupported"
        )
    else:
        return message


def _parse_dgs_unit_metadata(
        statement: str,
        symbol_table: Dict[str, Var],
) -> Tuple[str, str]:
    """Parse one exact bracket-form DGS variable-unit declaration.

    :param statement: Normalized metadata statement.
    :param symbol_table: Symbols declared by the owning block definition.
    :return: Exact source symbol and unit text.
    """
    match: re.Match[str] | None = re.match(
        r"^\[(?P<lhs>[A-Za-z_][A-Za-z0-9_]*)]\s*=\s*(?P<unit>.+)$",
        statement.strip(),
    )
    if match is None:
        raise UnsupportedDgsExpression("Malformed DGS unit metadata")
    else:
        symbol_name: str = match.group('lhs')
    if symbol_name not in symbol_table:
        raise UnsupportedDgsExpression(
            f"Unknown unit-metadata symbol '{symbol_name}'"
        )
    else:
        unit_text: str = _parse_dgs_quoted_literal(match.group('unit'))
    return symbol_name, unit_text


def _build_statement_report_entry(index: int,
                                  statement: str,
                                  kind: str,
                                  lhs: str | None,
                                  status: str,
                                  detail: str) -> DgsStatementReportEntry:
    """
    Build one DGS statement report entry.

    :param index: 1-based statement index.
    :param statement: Normalized source statement.
    :param kind: Statement kind.
    :param lhs: Left-hand side symbol when available.
    :param status: Statement status.
    :param detail: Additional detail.
    :returns: Statement report entry.
    """
    return DgsStatementReportEntry(index, statement, kind, lhs, status, detail)


def _extract_rhs_text_for_support_report(kind: str, statement: str) -> str | None:
    """
    Extract the right-hand side text for one supported statement shape.

    :param kind: Statement kind.
    :param statement: Normalized source statement.
    :returns: Right-hand side text when the shape is supported.
    """
    rhs_text: str | None = None

    if kind in {'inc', 'inc0'}:
        match = re.match(r'^(?P<kind>inc0?|inc)\((?P<lhs>[^)]+)\)\s*=\s*(?P<rhs>.+)$', statement)
        if match is not None:
            rhs_text = match.group('rhs').strip()
        else:
            pass
    elif kind == 'state':
        match = re.match(r'^(?P<lhs>.+?)\.\s*=\s*(?P<rhs>.+)$', statement)
        if match is not None:
            rhs_text = match.group('rhs').strip()
        else:
            pass
    elif kind == 'algebraic':
        match = re.match(r'^(?P<lhs>[^=]+?)\s*=\s*(?P<rhs>.+)$', statement)
        if match is not None:
            rhs_text = match.group('rhs').strip()
        else:
            pass
    else:
        pass

    return rhs_text


def _ensure_support_report_lhs_symbol(lhs: str | None,
                                      blkdef: BlkDef,
                                      symbol_table: Dict[str, Var],
                                      parser: "DgsExpressionParser") -> None:
    """
    Ensure the left-hand side symbol exists in the parser symbol table.

    :param lhs: Left-hand side symbol when available.
    :param blkdef: Source block definition.
    :param symbol_table: Parser symbol table.
    :param parser: DGS expression parser.
    :returns: None.
    """
    if lhs is not None and lhs not in symbol_table:
        parser.register_symbol(
            original_name=lhs,
            variable=Var(name=f"{blkdef.loc_name}__{lhs}"),
        )
    else:
        pass


def _build_procedural_support_report_entry(index: int,
                                           statement: str,
                                           kind: str,
                                           lhs: str | None,
                                           parser: "DgsExpressionParser") -> DgsStatementReportEntry:
    """
    Build the report entry for one procedural statement.

    :param index: 1-based statement index.
    :param statement: Normalized source statement.
    :param kind: Statement kind.
    :param lhs: Left-hand side symbol when available.
    :param parser: DGS expression parser.
    :returns: Statement report entry.
    """
    try:
        parser.parse_procedural_statement(statement)
    except UnsupportedDgsExpression as exc:
        return _build_statement_report_entry(index, statement, kind, lhs, 'unsupported', str(exc))

    return _build_statement_report_entry(index, statement, kind, lhs, 'supported', 'parsed successfully')


def _build_diagnostic_support_report_entry(
        index: int,
        statement: str,
        kind: str,
        lhs: str | None,
        parser: "DgsExpressionParser",
) -> DgsStatementReportEntry:
    """Build the report entry for one conditional diagnostic declaration.

    :param index: 1-based statement index.
    :param statement: Normalized source statement.
    :param kind: Statement classification.
    :param lhs: Always ``None`` for a diagnostic declaration.
    :param parser: DGS expression parser owning the block symbols.
    :return: Statement support report entry.
    """
    try:
        parser.parse_diagnostic_statement(statement)
    except UnsupportedDgsExpression as exc:
        return _build_statement_report_entry(
            index,
            statement,
            kind,
            lhs,
            'unsupported',
            str(exc),
        )
    else:
        return _build_statement_report_entry(
            index,
            statement,
            kind,
            lhs,
            'supported',
            'preserved as a declarative conditional diagnostic',
        )


def _build_nonprocedural_support_report_entry(index: int,
                                              statement: str,
                                              kind: str,
                                              lhs: str | None,
                                              blkdef: BlkDef,
                                              symbol_table: Dict[str, Var],
                                              parser: "DgsExpressionParser",
                                              init_seen: Set[str]) -> DgsStatementReportEntry:
    """
    Build the report entry for one non-procedural statement.

    :param index: 1-based statement index.
    :param statement: Normalized source statement.
    :param kind: Statement kind.
    :param lhs: Left-hand side symbol when available.
    :param blkdef: Source block definition.
    :param symbol_table: Parser symbol table.
    :param parser: DGS expression parser.
    :param init_seen: Initialization surfaces already assigned by ``inc0`` or ``inc``.
    :returns: Statement report entry.
    """
    if kind == 'parameter_limit':
        try:
            _validate_dgs_parameter_limit(statement=statement, parser=parser)
        except UnsupportedDgsExpression as exc:
            return _build_statement_report_entry(
                index, statement, kind, lhs, 'unsupported', str(exc)
            )
        else:
            return _build_statement_report_entry(
                index, statement, kind, lhs, 'supported',
                'validated as an exact parameter-domain constraint',
            )
    else:
        pass

    rhs_text: str | None = _extract_rhs_text_for_support_report(kind, statement)

    if rhs_text is None:
        if kind in {'inc', 'inc0', 'state', 'algebraic'}:
            return _build_statement_report_entry(index, statement, kind, lhs, 'unsupported', 'could not isolate RHS')
        else:
            return _build_statement_report_entry(index, statement, kind, lhs, 'unsupported', 'statement shape unsupported')

    _ensure_support_report_lhs_symbol(lhs, blkdef, symbol_table, parser)

    try:
        parser.parse(rhs_text)
    except UnsupportedDgsExpression as exc:
        return _build_statement_report_entry(index, statement, kind, lhs, 'unsupported', str(exc))

    if kind == 'inc0' and lhs is not None and lhs in init_seen:
        return _build_statement_report_entry(index, statement, kind, lhs, 'ignored', 'inc0 skipped because init already exists')
    else:
        pass

    if kind in {'inc', 'inc0'} and lhs is not None:
        init_seen.add(lhs)
    else:
        pass

    return _build_statement_report_entry(index, statement, kind, lhs, 'supported', 'parsed successfully')


def build_blkdef_statement_support_report(blkdef: BlkDef) -> List[DgsStatementReportEntry]:
    """
    Build a line-by-line support report for one DGS block definition.

    :param blkdef: Block definition to inspect.
    :return: Ordered support report entries.
    """
    shared_signals: Dict[str, Var] = dict()
    symbol_table, _state_vars, _state_var_map, _diff_var_map, _param_var_map = _build_symbol_table(blkdef, shared_signals)
    _predeclare_statement_lhs_symbols(blkdef, symbol_table)
    parser = DgsExpressionParser(symbol_table, block_name=blkdef.loc_name)

    report: List[DgsStatementReportEntry] = list()
    init_seen: Set[str] = set()

    for idx, stmt in enumerate(_split_equation_statements(blkdef.equations_raw), start=1):
        kind, lhs = classify_dgs_statement(stmt)
        entry: DgsStatementReportEntry

        if kind == 'ignored':
            entry = _build_statement_report_entry(idx, stmt, kind, lhs, 'ignored', 'ignored by parser policy')
        elif kind == 'procedural':
            entry = _build_procedural_support_report_entry(idx, stmt, kind, lhs, parser)
        elif kind == 'diagnostic':
            entry = _build_diagnostic_support_report_entry(
                idx,
                stmt,
                kind,
                lhs,
                parser,
            )
        elif kind == 'unit_metadata':
            try:
                _parse_dgs_unit_metadata(stmt, symbol_table)
            except UnsupportedDgsExpression as exc:
                entry = _build_statement_report_entry(
                    idx,
                    stmt,
                    kind,
                    lhs,
                    'unsupported',
                    str(exc),
                )
            else:
                entry = _build_statement_report_entry(
                    idx,
                    stmt,
                    kind,
                    lhs,
                    'supported',
                    'preserved as exact variable-unit metadata',
                )
        else:
            entry = _build_nonprocedural_support_report_entry(idx, stmt, kind, lhs, blkdef, symbol_table, parser, init_seen)

        report.append(entry)

    return report


def summarize_blkdef_support_report(entries: List[DgsStatementReportEntry]) -> Dict[str, int]:
    """
    Count statuses and statement kinds from a support report.

    :param entries: Statement report entries.
    :return: Summary counters.
    """
    summary: Dict[str, int] = dict()
    summary['supported'] = 0
    summary['unsupported'] = 0
    summary['ignored'] = 0
    summary['state'] = 0
    summary['algebraic'] = 0
    summary['inc'] = 0
    summary['inc0'] = 0
    summary['procedural'] = 0
    summary['parameter_limit'] = 0

    for entry in entries:
        summary[entry.status] = summary.get(entry.status, 0) + 1
        summary[entry.kind] = summary.get(entry.kind, 0) + 1

    return summary


def _comparison_to_expr(obj: Expr | Comparison) -> Expr:
    if isinstance(obj, Comparison):
        return obj.to_expression()
    return obj


def _require_dgs_numeric_expression(
        obj: Expr | Comparison,
        context: str,
) -> Expr:
    """Return a numeric expression or reject a misplaced comparison.

    :param obj: Parsed DGS expression candidate.
    :param context: Helper name used in the fail-closed diagnostic.
    :return: Numeric symbolic expression.
    """
    if isinstance(obj, Comparison):
        raise UnsupportedDgsExpression(
            f"DGS helper '{context}' received a comparison in a numeric position"
        )
    else:
        return obj


def _split_dgs_parameter_limit_bounds(interval_body: str) -> Tuple[str, str]:
    """Split a ``limfix`` interval at its single top-level comma.

    :param interval_body: Interval text without its outer delimiters.
    :return: Stripped lower-bound and upper-bound expressions.
    """
    delimiter_stack: List[str] = list()
    separator_index: int | None = None
    character_index: int
    character: str
    for character_index, character in enumerate(interval_body):
        if character in {'(', '['}:
            delimiter_stack.append(character)
        elif character in {')', ']'}:
            if character == ')':
                expected_opening: str = '('
            else:
                expected_opening = '['
            if (
                    len(delimiter_stack) == 0
                    or delimiter_stack[-1] != expected_opening
            ):
                raise UnsupportedDgsExpression(
                    "Malformed nested delimiters in a limfix bound"
                )
            else:
                delimiter_stack.pop()
        elif character == ',' and len(delimiter_stack) == 0:
            if separator_index is None:
                separator_index = character_index
            else:
                raise UnsupportedDgsExpression(
                    "A limfix interval must contain one top-level comma"
                )
        else:
            pass

    if len(delimiter_stack) > 0:
        raise UnsupportedDgsExpression(
            "Malformed nested delimiters in a limfix bound"
        )
    elif separator_index is None:
        raise UnsupportedDgsExpression(
            "A limfix interval must contain one top-level comma"
        )
    else:
        pass

    lower_bound_text: str = interval_body[:separator_index].strip()
    upper_bound_text: str = interval_body[separator_index + 1:].strip()
    return lower_bound_text, upper_bound_text


def _validate_dgs_variable_limit(
        statement: str,
        parser: "DgsExpressionParser",
) -> List[Comparison]:
    """Build exact inequalities for one PowerFactory interval declaration.

    :param statement: Normalized DGS statement.
    :param parser: Expression parser owning the exact block symbol table.
    :return: Lower and upper inequalities declared by the interval.
    """
    limit_match: re.Match[str] | None = re.match(
        r'^(?P<helper>limfix|limits)\((?P<target>[^)]+)\)\s*=\s*(?P<interval>.+)$',
        statement.strip(),
    )
    if limit_match is None:
        raise UnsupportedDgsExpression("Malformed DGS interval declaration")
    else:
        pass

    target_name: str = limit_match.group('target').strip()
    helper_name: str = limit_match.group('helper')
    interval_text: str = limit_match.group('interval').strip()
    target_is_known: bool = target_name in parser.symbol_table
    interval_delimiters_are_valid: bool = bool(
        len(interval_text) >= 3
        and interval_text[0] in {'(', '['}
        and interval_text[-1] in {')', ']'}
    )
    if not target_is_known:
        raise UnsupportedDgsExpression(
            f"Unknown {helper_name} target '{target_name}'"
        )
    elif not interval_delimiters_are_valid:
        raise UnsupportedDgsExpression(
            f"Malformed {helper_name} interval delimiters"
        )
    else:
        pass

    interval_body: str = interval_text[1:-1]
    lower_bound_text: str
    upper_bound_text: str
    lower_bound_text, upper_bound_text = _split_dgs_parameter_limit_bounds(
        interval_body=interval_body,
    )
    bound_texts: List[str] = [lower_bound_text, upper_bound_text]
    if bound_texts[0] == "" and bound_texts[1] == "":
        raise UnsupportedDgsExpression(
            "A limfix interval must declare at least one bound"
        )
    else:
        pass

    bound_expressions: List[Expr | None] = [None, None]
    bound_index: int
    for bound_index in range(2):
        bound_text: str = bound_texts[bound_index]
        if bound_text == "":
            pass
        else:
            parsed_bound: Expr | Comparison = parser.parse(bound_text)
            if isinstance(parsed_bound, Comparison):
                raise UnsupportedDgsExpression(
                    "A limfix bound must be a scalar expression"
                )
            else:
                bound_expressions[bound_index] = parsed_bound

    # Empty endpoints denote real infinity and therefore produce no artificial
    # finite inequality. Brackets preserve inclusive PowerFactory endpoints.
    constraints: List[Comparison] = list()
    target_var: Var = parser.symbol_table[target_name]
    lower_bound: Expr | None = bound_expressions[0]
    upper_bound: Expr | None = bound_expressions[1]
    if lower_bound is None:
        pass
    elif interval_text[0] == '[':
        constraints.append(target_var >= lower_bound)
    else:
        constraints.append(target_var > lower_bound)

    if upper_bound is None:
        pass
    elif interval_text[-1] == ']':
        constraints.append(target_var <= upper_bound)
    else:
        constraints.append(target_var < upper_bound)

    return constraints

class ElmCompInstanceEntry:
    """
    One direct instance declared inside an ElmComp through pblk/pelm.

    :param slot_id: Slot identifier.
    :param slot_name: Slot display name.
    :param element_id: Instantiated element identifier.
    :param element_name: Instantiated element display name.
    :param element_kind: Element kind, for example ElmDsl or ElmComp.
    :param element_outserv: Exact dynamic-instance service flag when available.
    :param type_id: Underlying BlkDef identifier if available.
    :param type_name: Underlying BlkDef display name if available.
    :param parameter_values: Instance parameter values keyed by declared name.
    :param slot_index: Ordinal index of the paired pblk/pelm relation.
    :param slot_element: Raw BlkSlot compatible-element reference.
    :param slot_filter: Raw BlkSlot model filter text.
    :param slot_outputs: Signals produced by the typed source slot.
    :param slot_inputs: Signals consumed by the typed source slot.
    :param slot_reference_is_resolved: Whether pblk resolves to a BlkSlot.
    :param element_reference_is_resolved: Whether pelm resolves to a DGS object.
    """

    __slots__ = (
        "slot_id",
        "slot_name",
        "element_id",
        "element_name",
        "element_kind",
        "element_outserv",
        "type_id",
        "type_name",
        "parameter_values",
        "slot_index",
        "slot_element",
        "slot_filter",
        "slot_outputs",
        "slot_inputs",
        "slot_reference_is_resolved",
        "element_reference_is_resolved",
    )

    def __init__(
        self,
        slot_id: str | None,
        slot_name: str | None,
        element_id: str | None,
        element_name: str | None,
        element_kind: str | None,
        element_outserv: int | None,
        type_id: str | None,
        type_name: str | None,
        parameter_values: Dict[str, float | int | bool | str | complex | None] | None = None,
        slot_index: int | None = None,
        slot_element: str | None = None,
        slot_filter: str | None = None,
        slot_outputs: List[str] | None = None,
        slot_inputs: List[str] | None = None,
        slot_reference_is_resolved: bool = False,
        element_reference_is_resolved: bool = False,
    ) -> None:
        """Store one exact composite slot relation.

        :param slot_id: Slot identifier.
        :param slot_name: Slot display name.
        :param element_id: Instantiated element identifier.
        :param element_name: Instantiated element display name.
        :param element_kind: Instantiated DGS class.
        :param element_outserv: Dynamic-instance service flag when available.
        :param type_id: Dynamic BlkDef identifier, when applicable.
        :param type_name: Dynamic BlkDef display name, when applicable.
        :param parameter_values: Instance parameter values.
        :param slot_index: Ordinal pblk/pelm index.
        :param slot_element: Raw BlkSlot compatible-element reference.
        :param slot_filter: Raw BlkSlot model filter text.
        :param slot_outputs: Signals produced by the declared slot contract.
        :param slot_inputs: Signals consumed by the declared slot contract.
        :param slot_reference_is_resolved: Whether pblk resolves to a BlkSlot.
        :param element_reference_is_resolved: Whether pelm resolves to a DGS object.
        :return: None.
        """
        self.slot_id: str | None = slot_id
        self.slot_name: str | None = slot_name
        self.element_id: str | None = element_id
        self.element_name: str | None = element_name
        self.element_kind: str | None = element_kind
        self.element_outserv: int | None = element_outserv
        self.type_id: str | None = type_id
        self.type_name: str | None = type_name
        if parameter_values is None:
            self.parameter_values: Dict[
                str,
                float | int | bool | str | complex | None,
            ] = dict()
        else:
            self.parameter_values = dict(parameter_values)
        self.slot_index: int | None = slot_index
        self.slot_element: str | None = slot_element
        self.slot_filter: str | None = slot_filter
        if slot_outputs is None:
            self.slot_outputs: List[str] = list()
        else:
            self.slot_outputs = slot_outputs
        if slot_inputs is None:
            self.slot_inputs: List[str] = list()
        else:
            self.slot_inputs = slot_inputs
        self.slot_reference_is_resolved: bool = slot_reference_is_resolved
        self.element_reference_is_resolved: bool = (
            element_reference_is_resolved
        )

    def accepts_element_kind(self, element_kind: str) -> bool:
        """Return whether this slot contract accepts one exact DGS class.

        PowerFactory slot filters may contain wildcard class names such as
        ``ElmVsc*``. All consumers share this one parser-owned interpretation.

        :param element_kind: Exact referenced DGS element class.
        :return: ``True`` when the declared slot patterns accept the class.
        """
        element_kind_patterns: List[str] = (
            _extract_slot_contract_element_kinds(entry=self)
        )
        return _slot_contract_accepts_element_kind(
            element_kind_patterns=element_kind_patterns,
            element_kind=element_kind,
        )

    def get_slot_signal_components(
            self,
            direction: DgsSlotSignalDirection,
    ) -> List[str]:
        """Normalize one ordered DGS slot-signal declaration.

        :param direction: Exact declared input or output side to normalize.
        :return: Ordered non-empty component names.
        """
        components: List[str] = list()
        signal_groups: List[List[str]] = self.get_slot_signal_groups(
            direction=direction,
        )
        signal_group: List[str]
        signal_component: str
        for signal_group in signal_groups:
            for signal_component in signal_group:
                components.append(signal_component)
            else:
                pass
        else:
            pass
        return components

    def get_slot_signal_groups(
            self,
            direction: DgsSlotSignalDirection,
    ) -> List[List[str]]:
        """Normalize ordered DGS connector groups without losing vector width.

        Commas delimit graphical connector ordinals, while semicolons delimit
        the scalar components carried by one vector connector. Retaining both
        levels is required to translate ``BlkSig`` ordinals without confusing
        a vector group with several independent graphical pins.

        :param direction: Exact declared input or output side to normalize.
        :return: Ordered connector groups containing ordered scalar names.
        """
        if direction == DgsSlotSignalDirection.Input:
            raw_signals: List[str] = self.slot_inputs
        else:
            if direction == DgsSlotSignalDirection.Output:
                raw_signals = self.slot_outputs
            else:
                raw_signals = list()
        signal_groups: List[List[str]] = list()
        raw_signal: str
        raw_group: str
        raw_component: str
        normalized_component: str
        for raw_signal in raw_signals:
            for raw_group in raw_signal.split(","):
                group_components: List[str] = list()
                for raw_component in raw_group.split(";"):
                    normalized_component = raw_component.strip()
                    if normalized_component == "":
                        pass
                    else:
                        group_components.append(normalized_component)
                else:
                    pass
                if len(group_components) == 0:
                    pass
                else:
                    signal_groups.append(group_components)
            else:
                pass
        else:
            pass
        return signal_groups


def _resolve_direct_slot_runtime_input_indices(
        entry: ElmCompInstanceEntry,
        child_block: Block,
        graphical_input_index: int,
) -> List[int]:
    """Resolve one direct ``BlkSig`` input ordinal through its slot contract.

    A ``BlkSlot`` can expose only a subset of the instantiated ``BlkDef`` input
    vector and can order that subset differently. The cable ordinal therefore
    addresses the ordered slot contract first; the exact declared signal then
    identifies the unique runtime input variable.

    :param entry: Direct root relation owning the typed slot interface.
    :param child_block: Materialized dynamic block behind that slot.
    :param graphical_input_index: Raw ``BlkSig.inodto`` input ordinal.
    :return: Ordered runtime input indices, or an empty collection when the
        ordinal is outside the declared slot contract.
    """
    slot_input_groups: List[List[str]] = entry.get_slot_signal_groups(
        direction=DgsSlotSignalDirection.Input,
    )
    resolved_indices: List[int] = list()
    if 0 <= graphical_input_index < len(slot_input_groups):
        selected_input_names: List[str] = slot_input_groups[graphical_input_index]
        all_inputs_resolved: bool = True
        selected_input_name: str
        for selected_input_name in selected_input_names:
            if all_inputs_resolved:
                matching_runtime_indices: List[int] = list()
                runtime_input_index: int
                runtime_input_var: Var
                for runtime_input_index, runtime_input_var in enumerate(child_block.in_vars):
                    if runtime_input_var.name == selected_input_name:
                        matching_runtime_indices.append(runtime_input_index)
                    else:
                        pass
                else:
                    pass
                if len(matching_runtime_indices) == 1:
                    resolved_indices.append(matching_runtime_indices[0])
                elif len(matching_runtime_indices) == 0:
                    # Some native frames expose graphical-only vector members
                    # that the executable BlkDef intentionally omits. Existing
                    # name-based wiring remains authoritative for that cable.
                    resolved_indices = list()
                    all_inputs_resolved = False
                else:
                    raise ValueError(
                        "Direct BlkSig slot input is ambiguous in its dynamic "
                        f"BlkDef: {selected_input_name}"
                    )
            else:
                pass
        else:
            pass
    else:
        pass
    return resolved_indices


def _resolve_direct_slot_runtime_output_indices(
        entry: ElmCompInstanceEntry,
        child_block: Block,
        graphical_output_index: int,
) -> List[int]:
    """Resolve one direct output connector ordinal to scalar runtime indices.

    The instantiated block keeps the slot output order even when its private
    variable names differ from the public slot names. Connector group widths
    therefore provide the exact positional translation required for V2 FFS.

    :param entry: Direct root relation owning the typed slot interface.
    :param child_block: Materialized dynamic block behind that slot.
    :param graphical_output_index: Raw ``BlkSig.inodfrom`` output ordinal.
    :return: Ordered scalar output indices for the selected connector group.
    """
    slot_output_groups: List[List[str]] = entry.get_slot_signal_groups(
        direction=DgsSlotSignalDirection.Output,
    )
    resolved_indices: List[int] = list()
    if 0 <= graphical_output_index < len(slot_output_groups):
        scalar_offset: int = 0
        preceding_group_index: int
        for preceding_group_index in range(graphical_output_index):
            scalar_offset += len(slot_output_groups[preceding_group_index])
        else:
            pass
        selected_width: int = len(slot_output_groups[graphical_output_index])
        if scalar_offset + selected_width <= len(child_block.out_vars):
            scalar_index: int
            for scalar_index in range(scalar_offset, scalar_offset + selected_width):
                resolved_indices.append(scalar_index)
            else:
                pass
        else:
            # Graphical-only slot members can be absent from the executable
            # block. In that case the established name wiring remains active.
            pass
    else:
        pass
    return resolved_indices


def _connect_direct_root_graphical_signals(
        circuit: DgsCircuit,
        direct_entries: List[ElmCompInstanceEntry],
        child_block_by_slot_id: Dict[str, Block],
) -> None:
    """Connect exact ``BlkSig`` cables between direct dynamic root children.

    Direct ``pblk``/``pelm`` materialization establishes child ownership, while
    ``BlkSig`` remains authoritative for cross-child wiring. Connecting by the
    two slot FIDs and exported connector ordinals preserves cables whose label
    differs from the producer's private output name.

    :param circuit: Parsed DGS circuit containing the graphical cables.
    :param direct_entries: Unique direct slot relations of the selected root.
    :param child_block_by_slot_id: Materialized dynamic children by exact slot FID.
    :return: None.
    """
    entry_by_slot_id: Dict[str, ElmCompInstanceEntry] = dict()
    entry: ElmCompInstanceEntry
    for entry in direct_entries:
        if entry.slot_id is None:
            pass
        else:
            entry_by_slot_id[entry.slot_id] = entry

    # Resolve every cable against the original slot interfaces before applying
    # any substitution. ``Block.connect()`` replaces variables in ``in_vars``
    # and ``out_vars``; applying one cable while resolving the next one can
    # therefore create duplicate port names and make connector ordinals
    # ambiguous even though the DGS slot contract itself is unambiguous.
    pending_connections: List[Tuple[Block, List[Var], List[Var]]] = list()
    graphical_signal: BlkSig
    for graphical_signal in circuit.blksigs:
        source_slot_id: str = _normalize_dgs_pointer_id(
            graphical_signal.pnodfrom
        )
        consumer_slot_id: str = _normalize_dgs_pointer_id(
            graphical_signal.pnodto
        )
        source_block: Block | None = child_block_by_slot_id.get(
            source_slot_id,
            None,
        )
        consumer_block: Block | None = child_block_by_slot_id.get(
            consumer_slot_id,
            None,
        )
        consumer_entry: ElmCompInstanceEntry | None = entry_by_slot_id.get(
            consumer_slot_id,
            None,
        )
        source_entry: ElmCompInstanceEntry | None = entry_by_slot_id.get(
            source_slot_id,
            None,
        )
        if (
                source_block is None
                or consumer_block is None
                or consumer_entry is None
                or source_entry is None
        ):
            pass
        else:
            source_kind: DgsGraphicalConnectorKind | None = (
                _parse_dgs_graphical_connector_kind(
                    connector_code=int(graphical_signal.iconfrom),
                )
            )
            consumer_kind: DgsGraphicalConnectorKind | None = (
                _parse_dgs_graphical_connector_kind(
                    connector_code=int(graphical_signal.iconto),
                )
            )
            if (
                    source_kind != DgsGraphicalConnectorKind.Output
                    or consumer_kind != DgsGraphicalConnectorKind.Input
            ):
                # Non-signal graphical relations are retained by the DGS
                # parser but do not describe executable scalar data flow.
                pass
            else:
                source_output_indices: List[int] = (
                    _resolve_direct_slot_runtime_output_indices(
                        entry=source_entry,
                        child_block=source_block,
                        graphical_output_index=int(graphical_signal.inodfrom),
                    )
                )
                consumer_input_indices: List[int] = (
                    _resolve_direct_slot_runtime_input_indices(
                        entry=consumer_entry,
                        child_block=consumer_block,
                        graphical_input_index=int(graphical_signal.inodto),
                    )
                )
                if (
                        len(source_output_indices) == 0
                        or len(consumer_input_indices) == 0
                        or len(source_output_indices) != len(consumer_input_indices)
                ):
                    pass
                else:
                    connection_count: int = len(consumer_input_indices)
                    vars_to_subs: List[Var] = (
                        [consumer_block.in_vars[0]] * connection_count
                    )
                    incoming_vars: List[Var] = (
                        [source_block.out_vars[0]] * connection_count
                    )
                    connection_index: int
                    for connection_index in range(connection_count):
                        consumer_input_index: int = (
                            consumer_input_indices[connection_index]
                        )
                        source_output_index: int = (
                            source_output_indices[connection_index]
                        )
                        vars_to_subs[connection_index] = (
                            consumer_block.in_vars[consumer_input_index]
                        )
                        incoming_vars[connection_index] = (
                            source_block.out_vars[source_output_index]
                        )
                    else:
                        pass
                    pending_connections.append((
                        consumer_block,
                        vars_to_subs,
                        incoming_vars,
                    ))

    # Apply the already-resolved substitutions only after the complete cable
    # plan is stable. Stored Var identities remain valid even when an earlier
    # substitution changes the visible interface lists of the same block.
    pending_connection: Tuple[Block, List[Var], List[Var]]
    for pending_connection in pending_connections:
        pending_consumer_block: Block = pending_connection[0]
        pending_vars_to_subs: List[Var] = pending_connection[1]
        pending_incoming_vars: List[Var] = pending_connection[2]
        pending_consumer_block.connect(
            vars_to_subs=pending_vars_to_subs,
            incoming_vars=pending_incoming_vars,
        )


class DgsBlockInstanceSelection:
    """
    Selection result for a block resolved from the root ElmComp slots.

    :param instance_entry: Matched root instance entry.
    :param parsed_block: Parsed block definition associated to the entry.
    """

    __slots__ = ("instance_entry", "parsed_block")

    def __init__(
        self,
        instance_entry: ElmCompInstanceEntry,
        parsed_block: "ParsedDgsBlockDefinition",
    ) -> None:
        """Store the matched root entry and its parsed block definition.

        :param instance_entry: Matched instance entry from the root ElmComp.
        :param parsed_block: Parsed block definition selected for that entry.
        :return: None.
        """
        self.instance_entry: ElmCompInstanceEntry = instance_entry
        self.parsed_block: ParsedDgsBlockDefinition = parsed_block

class UnsupportedDgsExpression(Exception):
    pass


def _split_top_level_dsl_operator(expr: str, token: str) -> Tuple[str, str] | None:
    """Split an expression at the first matching top-level DSL operator.

    Parenthesized occurrences are ignored so that nested expressions remain
    intact. Incomplete operands are rejected instead of returning a partial
    expression.

    :param expr: DGS expression to inspect.
    :param token: Case-insensitive operator token to locate.
    :return: Stripped left and right operands, or ``None`` when no complete
        top-level occurrence exists.
    """
    depth: int = 0
    text = expr.strip()
    token_len = len(token)
    idx: int = 0

    while idx <= len(text) - token_len:
        ch = text[idx]
        if ch == '(':
            depth += 1
            idx += 1
        elif ch == ')':
            depth = max(0, depth - 1)
            idx += 1
        else:
            if depth == 0 and text[idx:idx + token_len].lower() == token:
                left = text[:idx].strip()
                right = text[idx + token_len:].strip()
                if left and right:
                    return left, right
                else:
                    return None
            else:
                idx += 1

    return None


def _predeclare_statement_lhs_symbols(blkdef: BlkDef, symbol_table: Dict[str, Var]) -> None:
    for stmt in _split_equation_statements(blkdef.equations_raw):
        kind, lhs = classify_dgs_statement(stmt)
        if kind in {'inc', 'inc0', 'state', 'algebraic'} and lhs is not None and lhs not in symbol_table:
            symbol_table[lhs] = Var(name=f"{blkdef.loc_name}__{lhs}")


class DgsExpressionParser(ast.NodeVisitor):
    __slots__ = (
        "symbol_table",
        "block_name",
        "simulation_domain",
        "_boundary_parameter_uids",
        "_boundary_expression_by_name",
        "_replacement_map",
        "_procedural_mode_defaults",
        "_procedural_logic_entries",
        "_procedural_counter",
        "_time_var",
    )

    def __init__(self,
                 symbol_table: Dict[str, Var],
                 block_name: str = "",
                 simulation_domain: DynamicSimulationMode = DynamicSimulationMode.RMS,
                 boundary_parameter_uids: Set[int] | None = None):
        self.symbol_table: Dict[str, Var] = symbol_table
        self.block_name: str = block_name
        self.simulation_domain: DynamicSimulationMode = simulation_domain
        if boundary_parameter_uids is None:
            self._boundary_parameter_uids: Set[int] = set()
        else:
            self._boundary_parameter_uids = set(boundary_parameter_uids)
        self._boundary_expression_by_name: Dict[str, Expr] = dict()
        self._replacement_map: Dict[str, str] = dict()
        original_name: str
        for original_name in symbol_table.keys():
            self._replacement_map[_safe_name(original_name)] = original_name
        self._procedural_mode_defaults: Dict[Var, Expr | Const] = dict()
        self._procedural_logic_entries: List[ProceduralLogicBase] = list()
        self._procedural_counter: int = 0
        self._time_var: Var | None = None

    def register_algebraic_boundary_expression(
            self,
            lhs_name: str,
            rhs_expr: Expr,
    ) -> None:
        """Register one algebraic expression safe for boundary evaluation.

        PowerFactory evaluates a selector from values at the target boundary.
        An algebraic helper made solely from time, parameters, and previously
        registered boundary helpers can therefore be expanded safely before the
        procedural selector samples it. Expressions that retain an ordinary
        state or algebraic dependency deliberately keep accepted-state sampling.

        :param lhs_name: DGS algebraic output receiving the expression.
        :param rhs_expr: Parsed algebraic right-hand side.
        :return: None.
        """
        expanded_rhs: Expr = rhs_expr.subs(self._boundary_expression_by_name)
        expression_is_boundary_safe: bool = True
        dependency_var: Var
        for dependency_var in expanded_rhs.get_vars():
            dependency_is_time: bool = (
                self._time_var is not None
                and dependency_var.uid == self._time_var.uid
            )
            dependency_is_parameter: bool = dependency_var.uid in self._boundary_parameter_uids
            if dependency_is_time or dependency_is_parameter:
                pass
            else:
                expression_is_boundary_safe = False

        if expression_is_boundary_safe:
            lhs_var: Var | None = self.symbol_table.get(lhs_name, None)
            if lhs_var is not None:
                self._boundary_expression_by_name[lhs_var.name] = expanded_rhs
            else:
                pass
        else:
            pass

    @property
    def procedural_mode_defaults(self) -> Dict[Var, Expr | Const]:
        return self._procedural_mode_defaults

    @property
    def procedural_logic_entries(self) -> List[ProceduralLogicBase]:
        return self._procedural_logic_entries

    def register_symbol(self, original_name: str, variable: Var) -> None:
        """
        Register one DGS symbol and its parser-safe replacement.

        :param original_name: Original DGS symbol name.
        :param variable: Symbolic variable representing the DGS symbol.
        :return: None.
        """
        self.symbol_table[original_name] = variable
        self._replacement_map[_safe_name(original_name)] = original_name

    def _new_procedural_mode_var(self, prefix: str) -> Var:
        base_name = f"{self.block_name}__proc_{prefix}_{self._procedural_counter}" if self.block_name else f"proc_{prefix}_{self._procedural_counter}"
        self._procedural_counter += 1
        var = Var(name=base_name)
        self.symbol_table[base_name] = var
        self._replacement_map[_safe_name(base_name)] = base_name
        self._procedural_mode_defaults[var] = Const(0.0)
        return var

    def _get_time_var(self) -> Var:
        if self._time_var is None:
            self._time_var = Var(name='glob_time')
        return self._time_var

    def parse_procedural_statement(self, statement: str) -> None:
        try:
            tree = ast.parse(self.preprocess(statement), mode='eval')
        except SyntaxError as exc:
            raise UnsupportedDgsExpression(str(exc)) from exc

        node = tree.body
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            raise UnsupportedDgsExpression("Unsupported procedural statement")

        if node.func.id != 'reset' or len(node.args) != 3:
            raise UnsupportedDgsExpression(f"Unsupported procedural helper '{node.func.id}'")

        target_node = node.args[0]
        if not isinstance(target_node, ast.Name):
            raise UnsupportedDgsExpression("reset target must be a DSL variable name")

        target_original = self._replacement_map.get(target_node.id)
        if target_original is None or target_original not in self.symbol_table:
            raise UnsupportedDgsExpression(f"Unknown reset target '{target_node.id}'")

        target_var = self.symbol_table[target_original]
        reset_expr: Expr = self._visit_boolean_expression(node.args[1])
        value_expr: Expr = _require_dgs_numeric_expression(
            obj=self.visit(node.args[2]),
            context='reset',
        )

        self._procedural_logic_entries.append(
            ResetOnRisingEdgeLogic(
                target_var_name=target_var.name,
                reset_expr=reset_expr,
                value_expr=value_expr,
                name=f"{target_var.name}_reset",
            )
        )

    def parse_diagnostic_statement(
            self,
            statement: str,
    ) -> ConditionalDiagnosticLogic:
        """Parse one declarative PowerFactory ``output`` or ``outfix`` call.

        The message stays inert source data. Only the condition is converted to
        the canonical boolean symbolic surface, and no import-time side effect
        is performed.

        :param statement: Exact normalized diagnostic statement.
        :return: Canonical conditional diagnostic entry.
        """
        match: re.Match[str] | None = re.match(
            r'^(?P<helper>output|outfix)\s*\((?P<body>.*)\)\s*$',
            statement.strip(),
        )
        if match is None:
            raise UnsupportedDgsExpression(
                "Malformed PowerFactory diagnostic statement"
            )
        else:
            helper_name: str = match.group('helper')
            arguments: List[str] = _split_dgs_call_arguments(
                match.group('body')
            )
        if len(arguments) != 2:
            raise UnsupportedDgsExpression(
                f"PowerFactory diagnostic '{helper_name}' requires two arguments"
            )
        else:
            condition_text: str = arguments[0]
            message: str = _parse_dgs_quoted_literal(arguments[1])
        if condition_text == "":
            raise UnsupportedDgsExpression(
                "PowerFactory diagnostic condition must not be empty"
            )
        else:
            try:
                tree: ast.Expression = ast.parse(
                    self.preprocess(condition_text),
                    mode='eval',
                )
            except SyntaxError as exc:
                raise UnsupportedDgsExpression(str(exc)) from exc
        condition_expr: Expr = self._visit_boolean_expression(tree.body)
        if self.block_name == "":
            diagnostic_name: str = (
                f"{helper_name}_{self._procedural_counter}"
            )
        else:
            diagnostic_name = (
                f"{self.block_name}__{helper_name}_{self._procedural_counter}"
            )
        self._procedural_counter += 1
        diagnostic: ConditionalDiagnosticLogic = ConditionalDiagnosticLogic(
            condition_expr=condition_expr,
            message=message,
            initialization_only=(helper_name == 'outfix'),
            name=diagnostic_name,
        )
        self._procedural_logic_entries.append(diagnostic)
        return diagnostic

    def parse_runtime_limit_statement(
            self,
            statement: str,
    ) -> List[ConditionalDiagnosticLogic]:
        """Preserve one PowerFactory ``limits`` declaration as diagnostics.

        Unlike ``limfix``, PowerFactory evaluates ``limits`` throughout the
        simulation and reports each interval violation. The valid interval is
        therefore inverted into declarative runtime diagnostic conditions
        instead of becoming a solver feasibility constraint.

        :param statement: Exact normalized ``limits`` declaration.
        :return: One diagnostic for every finite interval endpoint.
        """
        valid_constraints: List[Comparison] = _validate_dgs_variable_limit(
            statement=statement,
            parser=self,
        )
        diagnostics: List[ConditionalDiagnosticLogic] = list()
        valid_constraint: Comparison
        for valid_constraint in valid_constraints:
            if valid_constraint.op == CmpOp.GE:
                violation_condition: Comparison = (
                    valid_constraint.lhs < valid_constraint.rhs
                )
            elif valid_constraint.op == CmpOp.GT:
                violation_condition = (
                    valid_constraint.lhs <= valid_constraint.rhs
                )
            elif valid_constraint.op == CmpOp.LE:
                violation_condition = (
                    valid_constraint.lhs > valid_constraint.rhs
                )
            elif valid_constraint.op == CmpOp.LT:
                violation_condition = (
                    valid_constraint.lhs >= valid_constraint.rhs
                )
            else:
                raise UnsupportedDgsExpression(
                    "Unsupported DGS runtime interval comparison"
                )
            if self.block_name == "":
                diagnostic_name: str = f"limits_{self._procedural_counter}"
            else:
                diagnostic_name = (
                    f"{self.block_name}__limits_{self._procedural_counter}"
                )
            self._procedural_counter += 1
            diagnostic: ConditionalDiagnosticLogic = (
                ConditionalDiagnosticLogic(
                    condition_expr=violation_condition,
                    message=statement,
                    initialization_only=False,
                    name=diagnostic_name,
                )
            )
            diagnostics.append(diagnostic)
            self._procedural_logic_entries.append(diagnostic)

        return diagnostics

    def preprocess(self, expr: str) -> str:
        text: str = expr.strip()
        text = text.replace('^', '**')
        text = text.replace('<>', '!=')
        text = text.replace('.and.', ' and ')
        text = text.replace('.or.', ' or ')
        text = text.replace('.not.', ' not ')
        text = re.sub(r'(?<![<>=!])=(?!=)', '==', text)

        replacements: List[Tuple[str, str]] = list()
        for name in sorted(self.symbol_table.keys(), key=len, reverse=True):
            replacements.append((name, _safe_name(name)))

        for original, safe in replacements:
            text = re.sub(re.escape(original), safe, text)

        return text

    def parse(self, expr: str) -> Expr | Comparison:
        for token in ['.nor.', '.nand.', '.eor.']:
            split_parts = _split_top_level_dsl_operator(expr, token)
            if split_parts is not None:
                left_raw, right_raw = split_parts
                left_expr = _comparison_to_expr(self.parse(left_raw))
                right_expr = _comparison_to_expr(self.parse(right_raw))

                if token == '.nor.':
                    return (Const(1.0) - left_expr) * (Const(1.0) - right_expr)
                if token == '.nand.':
                    return Const(1.0) - left_expr * right_expr
                return left_expr + right_expr - Const(2.0) * left_expr * right_expr

        try:
            tree = ast.parse(self.preprocess(expr), mode='eval')
        except SyntaxError as exc:
            raise UnsupportedDgsExpression(str(exc)) from exc
        return self.visit(tree.body)

    def visit_Name(self, node: ast.Name) -> Expr:
        original: str | None = self._replacement_map.get(node.id)
        if original is None or original not in self.symbol_table:
            raise UnsupportedDgsExpression(f"Unknown symbol '{node.id}'")
        return self.symbol_table[original]

    def visit_Constant(self, node: ast.Constant) -> Expr:
        if isinstance(node.value, (int, float)):
            return Const(float(node.value))
        raise UnsupportedDgsExpression(f"Unsupported constant '{node.value}'")

    def visit_Set(self, node: ast.Set) -> Expr | Comparison:
        """Interpret one-element braces as PowerFactory expression grouping.

        PowerFactory uses braces to group boolean subexpressions. Python parses
        that exact surface syntax as a set literal, so cardinality must be one;
        accepting a real multi-element set would weaken the numeric DSL.

        :param node: Python AST set node produced by a braced DGS expression.
        :return: The single grouped symbolic expression.
        """
        if len(node.elts) != 1:
            raise UnsupportedDgsExpression(
                "PowerFactory expression braces must contain one expression"
            )
        else:
            return self.visit(node.elts[0])

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Expr:
        parsed_operand: Expr | Comparison = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            return Const(1.0) - _comparison_to_expr(parsed_operand)
        else:
            operand: Expr = _require_dgs_numeric_expression(
                obj=parsed_operand,
                context='unary arithmetic',
            )

        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return operand
        raise UnsupportedDgsExpression(ast.dump(node))

    def visit_BinOp(self, node: ast.BinOp) -> Expr:
        left: Expr = _require_dgs_numeric_expression(
            obj=self.visit(node.left),
            context='binary arithmetic',
        )
        right: Expr = _require_dgs_numeric_expression(
            obj=self.visit(node.right),
            context='binary arithmetic',
        )
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left ** right
        raise UnsupportedDgsExpression(ast.dump(node))

    def visit_Compare(self, node: ast.Compare) -> Expr | Comparison:
        """Convert one supported simple comparison into symbolic data.

        :param node: Python AST comparison produced from one DGS expression.
        :return: Symbolic comparison expression.
        """
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise UnsupportedDgsExpression("Only simple comparisons are supported")
        left: Expr = _require_dgs_numeric_expression(
            obj=self.visit(node.left),
            context='comparison',
        )
        right: Expr = _require_dgs_numeric_expression(
            obj=self.visit(node.comparators[0]),
            context='comparison',
        )
        op: ast.cmpop = node.ops[0]
        if isinstance(op, ast.Gt):
            return left > right
        elif isinstance(op, ast.GtE):
            return left >= right
        elif isinstance(op, ast.Lt):
            return left < right
        elif isinstance(op, ast.LtE):
            return left <= right
        elif isinstance(op, ast.Eq):
            return left == right
        elif isinstance(op, ast.NotEq):
            equality_expression: Expr = Comparison(
                lhs=left,
                op=CmpOp.EQ,
                rhs=right,
            ).to_expression()
            return Const(1.0) - equality_expression
        else:
            raise UnsupportedDgsExpression(ast.dump(node))

    def visit_BoolOp(self, node: ast.BoolOp) -> Expr:
        values = [_comparison_to_expr(self.visit(v)) for v in node.values]
        if isinstance(node.op, ast.And):
            result = values[0]
            for value in values[1:]:
                result = result * value
            return result
        if isinstance(node.op, ast.Or):
            result = values[0]
            for value in values[1:]:
                result = Const(1.0) - (Const(1.0) - result) * (Const(1.0) - value)
            return result
        raise UnsupportedDgsExpression(ast.dump(node))

    def _build_selector_expression(
            self,
            name: str,
            condition_expr: Expr,
            selected_expr: Expr,
            alternate_expr: Expr,
    ) -> Expr:
        """Build one sampled or fixed PowerFactory selector expression.

        :param name: Exact selector helper name.
        :param condition_expr: Numeric PowerFactory selector condition.
        :param selected_expr: Expression returned above the 0.5 selector threshold.
        :param alternate_expr: Expression returned at or below the threshold.
        :return: Canonical symbolic selector expression.
        """
        if isinstance(condition_expr, Const) and condition_expr.value is not None:
            result: Expr
            if float(condition_expr.value) > 0.5:
                result = selected_expr
            else:
                result = alternate_expr
        else:
            boundary_condition_expr: Expr = condition_expr.subs(
                self._boundary_expression_by_name
            )
            selector: Var = self._new_procedural_mode_var(name)
            if name in {'select', 'select_const', 'ifelse'}:
                self._procedural_logic_entries.append(
                    SampledValueLogic(
                        output_var_name=selector.name,
                        output_var_uid=selector.uid,
                        source_expr=Comparison(
                            lhs=boundary_condition_expr,
                            op=CmpOp.GT,
                            rhs=Const(0.5),
                        ).to_expression(),
                        name=selector.name,
                    )
                )
            else:
                self._procedural_logic_entries.append(
                    FixedSampleLogic(
                        output_var_name=selector.name,
                        condition_expr=condition_expr,
                        name=selector.name,
                    )
                )
            result = (
                selector * selected_expr
                + (Const(1.0) - selector) * alternate_expr
            )
        return result

    def _visit_boolean_expression(self, node: ast.AST) -> Expr:
        """Visit a comparison-capable expression in a declared boolean slot.

        Boolean-valued branches propagate only through selector helpers reached
        from a known boolean consumer. Numeric calls keep their ordinary strict
        visitor and therefore still reject misplaced comparisons.

        :param node: Python AST node produced from one DGS expression.
        :return: Canonical zero-or-one symbolic expression.
        """
        if isinstance(node, ast.Set):
            if len(node.elts) != 1:
                raise UnsupportedDgsExpression(
                    "PowerFactory boolean braces must contain one expression"
                )
            else:
                result: Expr = self._visit_boolean_expression(node.elts[0])
        elif isinstance(node, ast.BoolOp):
            values: List[Expr] = [
                self._visit_boolean_expression(value_node)
                for value_node in node.values
            ]
            result = values[0]
            value: Expr
            for value in values[1:]:
                if isinstance(node.op, ast.And):
                    result = result * value
                elif isinstance(node.op, ast.Or):
                    result = (
                        Const(1.0)
                        - (Const(1.0) - result) * (Const(1.0) - value)
                    )
                else:
                    raise UnsupportedDgsExpression(ast.dump(node))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            result = (
                Const(1.0)
                - self._visit_boolean_expression(node.operand)
            )
        elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {
                    'select',
                    'select_const',
                    'ifelse',
                    'selfix',
                    'selfix_const',
                }
                and len(node.args) == 3
        ):
            condition_expr: Expr = self._visit_boolean_expression(node.args[0])
            selected_expr: Expr = self._visit_boolean_expression(node.args[1])
            alternate_expr: Expr = self._visit_boolean_expression(node.args[2])
            result = self._build_selector_expression(
                name=node.func.id,
                condition_expr=condition_expr,
                selected_expr=selected_expr,
                alternate_expr=alternate_expr,
            )
        else:
            result = _comparison_to_expr(self.visit(node))
        return result

    def visit_Call(self, node: ast.Call) -> Expr:
        if not isinstance(node.func, ast.Name):
            raise UnsupportedDgsExpression(ast.dump(node))
        else:
            pass

        name: str = node.func.id
        # These helpers declare boolean positions explicitly. A comparison is
        # converted only there, never silently inside a numeric helper.
        if (
                name in {
                    'select',
                    'select_const',
                    'ifelse',
                    'selfix',
                    'selfix_const',
                }
                and len(node.args) == 3
        ):
            condition_expr: Expr = self._visit_boolean_expression(node.args[0])
            selected_expr: Expr = _require_dgs_numeric_expression(
                obj=self.visit(node.args[1]),
                context=name,
            )
            alternate_expr: Expr = _require_dgs_numeric_expression(
                obj=self.visit(node.args[2]),
                context=name,
            )
            return self._build_selector_expression(
                name=name,
                condition_expr=condition_expr,
                selected_expr=selected_expr,
                alternate_expr=alternate_expr,
            )
        elif name == 'flipflop' and len(node.args) == 2:
            latch: Var = self._new_procedural_mode_var(name)
            self._procedural_logic_entries.append(
                FlipFlopLogic(
                    output_var_name=latch.name,
                    set_expr=self._visit_boolean_expression(node.args[0]),
                    reset_expr=self._visit_boolean_expression(node.args[1]),
                    name=latch.name,
                )
            )
            return latch
        elif name == 'aflipflop' and len(node.args) == 3:
            latch = self._new_procedural_mode_var(name)
            self._procedural_logic_entries.append(
                AnalogFlipFlopLogic(
                    output_var_name=latch.name,
                    input_expr=_require_dgs_numeric_expression(
                        obj=self.visit(node.args[0]),
                        context=name,
                    ),
                    set_expr=self._visit_boolean_expression(node.args[1]),
                    reset_expr=self._visit_boolean_expression(node.args[2]),
                    name=latch.name,
                )
            )
            return latch
        elif name in {'picdro', 'picdro_const'} and len(node.args) == 3:
            latch = self._new_procedural_mode_var(name)
            self._procedural_logic_entries.append(
                PickupDropoffLogic(
                    output_var_name=latch.name,
                    output_var_uid=latch.uid,
                    bool_expr=self._visit_boolean_expression(node.args[0]),
                    pickup_delay_expr=_require_dgs_numeric_expression(
                        obj=self.visit(node.args[1]),
                        context=name,
                    ),
                    drop_delay_expr=_require_dgs_numeric_expression(
                        obj=self.visit(node.args[2]),
                        context=name,
                    ),
                    name=latch.name,
                )
            )
            return latch
        else:
            pass

        args: List[Expr] = [
            _require_dgs_numeric_expression(
                obj=self.visit(arg),
                context=name,
            )
            for arg in node.args
        ]

        if name == 'sin' and len(args) == 1:
            return sin(args[0])
        else:
            pass
        if name == 'cos' and len(args) == 1:
            return cos(args[0])
        else:
            pass
        if name == 'acos' and len(args) == 1:
            return acos(args[0])
        else:
            pass
        if name == 'tan' and len(args) == 1:
            return tan(args[0])
        else:
            pass
        if name == 'sqrt' and len(args) == 1:
            return sqrt(args[0])
        else:
            pass
        if name == 'abs' and len(args) == 1:
            return abs(args[0])
        if name == 'exp' and len(args) == 1:
            return exp(args[0])
        if name == 'log' and len(args) == 1:
            return log(args[0])
        if name == 'atan2' and len(args) == 2:
            return Func2('atan2', args[0], args[1])
        if name == 'max' and len(args) >= 2:
            maximum_expr: Expr = args[0]
            maximum_arg: Expr
            for maximum_arg in args[1:]:
                maximum_expr = symbolic.max(maximum_expr, maximum_arg)
            return maximum_expr
        else:
            pass
        if name == 'min' and len(args) >= 2:
            minimum_expr: Expr = args[0]
            minimum_arg: Expr
            for minimum_arg in args[1:]:
                minimum_expr = symbolic.min(minimum_expr, minimum_arg)
            return minimum_expr
        else:
            pass
        if name == 'modulo' and len(args) == 2:
            # PowerFactory uses modulo to wrap angles into a positive period;
            # retain that exact floor-based remainder as symbolic data.
            return args[0] - symbolic.floor(args[0] / args[1]) * args[1]
        else:
            pass
        if name == 'sqr' and len(args) == 1:
            return args[0] * args[0]
        if name in {'lim', 'lim_const'} and len(args) == 3:
            return hard_sat(args[0], args[1], args[2])
        if name in {'limstate', 'limstate_const'} and len(args) == 3:
            return hard_sat(args[0], args[1], args[2])
        else:
            pass
        if name == 'lastvalue' and len(args) == 1:
            sampled = self._new_procedural_mode_var(name)
            self._procedural_logic_entries.append(
                SampledValueLogic(
                    output_var_name=sampled.name,
                    output_var_uid=sampled.uid,
                    source_expr=args[0],
                    name=sampled.name,
                )
            )
            return sampled
        if name == 'delay' and len(args) == 2:
            delayed = self._new_procedural_mode_var(name)
            self._procedural_logic_entries.append(
                TimeDelayLogic(
                    output_var_name=delayed.name,
                    source_expr=args[0],
                    delay_expr=args[1],
                    name=delayed.name,
                )
            )
            return delayed
        if name == 'movingavg' and len(args) == 3:
            averaged = self._new_procedural_mode_var(name)
            self._procedural_logic_entries.append(
                MovingAverageLogic(
                    output_var_name=averaged.name,
                    source_expr=args[0],
                    delay_expr=args[1],
                    window_expr=args[2],
                    name=averaged.name,
                )
            )
            return averaged
        if name == 'gradlim_const' and len(args) == 3:
            limited = self._new_procedural_mode_var(name)
            self._procedural_logic_entries.append(
                GradientLimiterLogic(
                    output_var_name=limited.name,
                    source_expr=args[0],
                    lower_rate_expr=args[1],
                    upper_rate_expr=args[2],
                    name=limited.name,
                )
            )
            return limited
        if name == 'pi' and len(args) == 0:
            return Const(math.pi)
        if name == 'twopi' and len(args) == 0:
            return Const(2.0 * math.pi)
        if name == 'time' and len(args) == 0:
            return self._get_time_var()
        if name == 'rms' and len(args) == 0:
            if self.simulation_domain == DynamicSimulationMode.RMS:
                return Const(1.0)
            else:
                return Const(0.0)
        if name == 'balanced' and len(args) == 0:
            if self.simulation_domain == DynamicSimulationMode.RMS:
                return Const(1.0)
            else:
                return Const(0.0)
        else:
            pass

        if name in {'inc', 'reset', 'lapprox', 'vardef'}:
            raise UnsupportedDgsExpression(f"Unsupported PowerFactory helper '{name}'")

        raise UnsupportedDgsExpression(f"Unsupported function '{name}'")

    def generic_visit(self, node: ast.AST):
        raise UnsupportedDgsExpression(ast.dump(node))


class DgsVariableUnitMetadata:
    """Preserve one exact bracket-form variable-unit declaration.

    :param symbol_name: Source variable name declared by the block.
    :param unit_text: Exact unit text inside the DGS literal delimiters.
    """

    __slots__ = ("symbol_name", "unit_text")

    def __init__(self, symbol_name: str, unit_text: str) -> None:
        """Store one validated source unit declaration.

        :param symbol_name: Source variable name declared by the block.
        :param unit_text: Exact source unit text.
        :return: None.
        """
        self.symbol_name: str = symbol_name
        self.unit_text: str = unit_text


class ParsedDgsBlockDefinition:
    """
    Parsed symbolic representation of one DGS block definition.
    """

    __slots__ = (
        "blkdef",
        "symbol_table",
        "state_rhs",
        "algebraic_rhs",
        "init_rhs",
        "parameter_limits",
        "mode_dict",
        "procedural_logic",
        "discrete_event_actions",
        "variable_units",
        "unsupported_lines",
        "signal_dependencies",
    )

    def __init__(self,
                 blkdef: BlkDef,
                 symbol_table: Dict[str, Var],
                 state_rhs: Dict[str, Expr],
                 algebraic_rhs: Dict[str, Expr],
                 init_rhs: Dict[str, Expr],
                 parameter_limits: List[Comparison],
                 mode_dict: Dict[Var, Expr | Const],
                 procedural_logic: List[ProceduralLogicBase],
                 discrete_event_actions: List[DgsDiscreteEventAction],
                 variable_units: List[DgsVariableUnitMetadata],
                 unsupported_lines: List[str],
                 signal_dependencies: Dict[str, Set[str]]) -> None:
        """
        Store one parsed DGS block definition.

        :param blkdef: Source block definition.
        :param symbol_table: Symbol table used during parsing.
        :param state_rhs: Differential equations by state name.
        :param algebraic_rhs: Algebraic equations by signal name.
        :param init_rhs: Initialization equations by signal name.
        :param parameter_limits: Exact open or closed parameter-domain inequalities.
        :param mode_dict: Procedural runtime defaults.
        :param procedural_logic: Retained procedural logic entries.
        :param discrete_event_actions: Validated source switch events awaiting FID resolution.
        :param variable_units: Validated exact source variable-unit declarations.
        :param unsupported_lines: Unsupported source statements.
        :param signal_dependencies: Signal dependency graph.
        :returns: None.
        """
        self.blkdef = blkdef
        self.symbol_table = symbol_table
        self.state_rhs = state_rhs
        self.algebraic_rhs = algebraic_rhs
        self.init_rhs = init_rhs
        self.parameter_limits = parameter_limits
        self.mode_dict = mode_dict
        self.procedural_logic = procedural_logic
        self.discrete_event_actions = discrete_event_actions
        self.variable_units = variable_units
        self.unsupported_lines = unsupported_lines
        self.signal_dependencies = signal_dependencies


class DgsResolvedSwitchTarget:
    """Store one exact source switch-to-equipment resolution during import."""

    __slots__ = (
        "switch_id",
        "device_id",
        "terminal_index",
        "initial_closed",
    )

    def __init__(
        self,
        switch_id: str,
        device_id: str,
        terminal_index: int,
        initial_closed: bool,
    ) -> None:
        """Store a resolved physical switching chain.

        :param switch_id: Exact ``StaSwitch`` FID.
        :param device_id: Exact actuated equipment FID.
        :param terminal_index: Equipment terminal containing the switch.
        :param initial_closed: Exported initial switch position.
        :return: None.
        """
        self.switch_id: str = switch_id
        self.device_id: str = device_id
        self.terminal_index: int = terminal_index
        self.initial_closed: bool = initial_closed


class DgsRootBlockResult:
    """
    Root DGS block parse result.
    """

    __slots__ = (
        "root_block",
        "root_blkdef",
        "root_element",
        "parsed_blocks",
        "dependency_graph",
        "producer_map",
        "consumer_map",
    )

    def __init__(self,
                 root_block: Block,
                 root_blkdef: ParsedDgsBlockDefinition,
                 root_element: ElmComp,
                 parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
                 dependency_graph: Dict[str, Set[str]],
                 producer_map: Dict[str, Set[str]],
                 consumer_map: Dict[str, Set[str]]) -> None:
        """
        Store the root DGS parse result.

        :param root_block: Root symbolic block.
        :param root_blkdef: Root parsed block definition.
        :param root_element: Root ElmComp element.
        :param parsed_blocks: Parsed blocks by identifier.
        :param dependency_graph: Dependency graph between parsed blocks.
        :param producer_map: Producers by signal name.
        :param consumer_map: Consumers by signal name.
        :returns: None.
        """
        self.root_block = root_block
        self.root_blkdef = root_blkdef
        self.root_element = root_element
        self.parsed_blocks = parsed_blocks
        self.dependency_graph = dependency_graph
        self.producer_map = producer_map
        self.consumer_map = consumer_map


class DgsBlockSubgraphResult:
    """
    Selected DGS block subgraph result.
    """

    __slots__ = (
        "selected_block",
        "view_block",
        "node_ids",
        "dependency_graph",
        "upstream",
        "downstream",
    )

    def __init__(self,
                 selected_block: ParsedDgsBlockDefinition,
                 view_block: Block,
                 node_ids: Set[str],
                 dependency_graph: Dict[str, Set[str]],
                 upstream: Dict[str, Set[str]],
                 downstream: Dict[str, Set[str]]) -> None:
        """
        Store one selected DGS block subgraph.

        :param selected_block: Selected parsed block definition.
        :param view_block: View block built for export or analysis.
        :param node_ids: Node identifiers in the subgraph.
        :param dependency_graph: Dependency graph restricted to the subgraph.
        :param upstream: Upstream closure graph.
        :param downstream: Downstream closure graph.
        :returns: None.
        """
        self.selected_block = selected_block
        self.view_block = view_block
        self.node_ids = node_ids
        self.dependency_graph = dependency_graph
        self.upstream = upstream
        self.downstream = downstream


class GraphicConnectionInstruction:
    """
    One resolved graphical connection instruction used during template export.
    """

    __slots__ = (
        "consumer_node_id",
        "consumer_input_name",
        "source_kind",
        "consumer_input_index",
        "source_output_name",
        "source_output_index",
        "source_node_id",
        "source_root_name",
    )

    def __init__(self,
                 consumer_node_id: str,
                 consumer_input_name: str,
                 source_kind: str,
                 consumer_input_index: int | None = None,
                 source_output_name: str | None = None,
                 source_output_index: int | None = None,
                 source_node_id: str | None = None,
                 source_root_name: str | None = None) -> None:
        """
        Store one resolved graphical connection instruction.

        :param consumer_node_id: Consumer node identifier.
        :param consumer_input_name: Consumer input name.
        :param source_kind: Source-kind discriminator.
        :param consumer_input_index: Consumer input index.
        :param source_output_name: Source output name.
        :param source_output_index: Source output index.
        :param source_node_id: Source node identifier.
        :param source_root_name: Source root-input name.
        :returns: None.
        """
        self.consumer_node_id = consumer_node_id
        self.consumer_input_name = consumer_input_name
        self.source_kind = source_kind
        self.consumer_input_index = consumer_input_index
        self.source_output_name = source_output_name
        self.source_output_index = source_output_index
        self.source_node_id = source_node_id
        self.source_root_name = source_root_name


class DgsGraphicalParentBindingResult:
    """Describe how graphical children satisfy parent internal signals.

    :param resolved_internal_names: Parent internals replaced by exact child
        variables.
    :param disconnected_input_names: Parent internals bound to intentional
        zero-valued graphical inputs.
    :param unresolved_input_names: Live routed signals whose producer topology
        is absent from the DGS export.
    """

    __slots__ = (
        "resolved_internal_names",
        "disconnected_input_names",
        "unresolved_input_names",
    )

    def __init__(
        self,
        resolved_internal_names: List[str],
        disconnected_input_names: List[str],
        unresolved_input_names: List[str],
    ) -> None:
        """Store one fail-closed parent-to-child binding result.

        :param resolved_internal_names: Internals replaced by exact child
            variables.
        :param disconnected_input_names: Internals assigned the explicit DGS
            disconnected-input value.
        :param unresolved_input_names: Live internals left unresolved because
            their producer was not exported.
        :return: None.
        """
        self.resolved_internal_names: List[str] = resolved_internal_names
        self.disconnected_input_names: List[str] = disconnected_input_names
        self.unresolved_input_names: List[str] = unresolved_input_names


class DgsGraphicTreeResult:
    """
    Graphical internal tree reconstruction result.

    :param selected_block: Parsed selected block definition.
    :param view_block: Reconstructed block tree view.
    :param node_ids: Internal graphical node identifiers.
    :param adjacency: Undirected adjacency between graphical nodes.
    :param node_labels: Display label per graphical node.
    :param node_kinds: DGS object kind per graphical node.
    :param parent_bindings: Parent internal-signal binding outcome.
    """

    __slots__ = (
        "selected_block",
        "view_block",
        "node_ids",
        "adjacency",
        "node_labels",
        "node_kinds",
        "child_node_ids",
        "connections",
        "parent_bindings",
    )

    def __init__(
        self,
        selected_block: ParsedDgsBlockDefinition,
        view_block: Block,
        node_ids: Set[str],
        adjacency: Dict[str, Set[str]],
        node_labels: Dict[str, str],
        node_kinds: Dict[str, str],
        child_node_ids: List[str],
        connections: List[GraphicConnectionInstruction],
        parent_bindings: DgsGraphicalParentBindingResult | None = None,
    ) -> None:
        """Store one reconstructed graphical tree.

        :param selected_block: Selected parent block definition.
        :param view_block: Runtime graphical tree.
        :param node_ids: Selected graphical node identifiers.
        :param adjacency: Selected graphical adjacency.
        :param node_labels: Display labels keyed by node identifier.
        :param node_kinds: DGS element kinds keyed by node identifier.
        :param child_node_ids: Materialized child identifiers.
        :param connections: Resolved directed child connections.
        :param parent_bindings: Parent internal-signal binding outcome.
        :return: None.
        """
        self.selected_block = selected_block
        self.view_block = view_block
        self.node_ids = node_ids
        self.adjacency = adjacency
        self.node_labels = node_labels
        self.node_kinds = node_kinds
        self.child_node_ids = child_node_ids
        self.connections = connections
        if parent_bindings is None:
            self.parent_bindings: DgsGraphicalParentBindingResult = (
                DgsGraphicalParentBindingResult(
                    resolved_internal_names=list(),
                    disconnected_input_names=list(),
                    unresolved_input_names=list(),
                )
            )
        else:
            self.parent_bindings = parent_bindings


class DgsGraphicalIndexes:
    """Store graphical indexes shared across one DGS import.

    :param adjacency: Undirected graphical adjacency keyed by DGS identifier.
    :param node_by_id: Graphical objects keyed by DGS identifier.
    :param node_signals: Signal names attached to each graphical object.
    :param element_by_id: Parsed DGS elements keyed by identifier.
    """

    __slots__ = (
        "adjacency",
        "node_by_id",
        "node_signals",
        "element_by_id",
    )

    def __init__(
        self,
        adjacency: Dict[str, Set[str]],
        node_by_id: Dict[str, object],
        node_signals: Dict[str, Set[str]],
        element_by_id: Dict[str, object],
    ) -> None:
        """Store the indexes reused by graphical slot materialization.

        :param adjacency: Undirected graphical adjacency keyed by DGS
            identifier.
        :param node_by_id: Graphical objects keyed by DGS identifier.
        :param node_signals: Signal names attached to each graphical object.
        :param element_by_id: Parsed DGS elements keyed by identifier.
        :return: None.
        """
        self.adjacency: Dict[str, Set[str]] = adjacency
        self.node_by_id: Dict[str, object] = node_by_id
        self.node_signals: Dict[str, Set[str]] = node_signals
        self.element_by_id: Dict[str, object] = element_by_id


class DgsDirectRootBuildResult:
    """Store one direct root and its reusable slot materializations.

    :param root_block: Materialized direct root block.
    :param child_block_by_slot_id: Direct child blocks keyed by slot FID.
    :param graphical_tree_by_slot_id: Typed graphical results keyed by slot
        FID.
    :param direct_entries: Exact typed slot relations used for fail-closed
        adapter classification during this conversion only.
    """

    __slots__ = (
        "root_block",
        "child_block_by_slot_id",
        "graphical_tree_by_slot_id",
        "direct_entries",
    )

    def __init__(
        self,
        root_block: Block,
        child_block_by_slot_id: Dict[str, Block],
        graphical_tree_by_slot_id: Dict[str, DgsGraphicTreeResult],
        direct_entries: List[ElmCompInstanceEntry],
    ) -> None:
        """Store the root and exact direct-child lookup tables.

        :param root_block: Materialized direct root block.
        :param child_block_by_slot_id: Direct child blocks keyed by slot FID.
        :param graphical_tree_by_slot_id: Typed graphical results keyed by slot
            FID.
        :param direct_entries: Validated direct source-slot relations.
        :return: None.
        """
        self.root_block: Block = root_block
        self.child_block_by_slot_id: Dict[str, Block] = child_block_by_slot_id
        self.graphical_tree_by_slot_id: Dict[
            str,
            DgsGraphicTreeResult,
        ] = graphical_tree_by_slot_id
        self.direct_entries: List[ElmCompInstanceEntry] = direct_entries


class DgsStatementReportEntry:
    """
    One line-by-line parsing report entry for a DGS block statement.

    :param index: 1-based statement index.
    :type index: int
    :param statement: Original normalized statement.
    :type statement: str
    :param kind: Classified statement kind.
    :type kind: str
    :param lhs: Left-hand side symbol when available.
    :type lhs: str | None
    :param status: Parsing result status.
    :type status: str
    :param detail: Additional explanation.
    :type detail: str
    """

    __slots__ = ("index", "statement", "kind", "lhs", "status", "detail")

    def __init__(
        self,
        index: int,
        statement: str,
        kind: str,
        lhs: str | None,
        status: str,
        detail: str,
    ) -> None:
        """Store one normalized DGS statement parsing result.

        :param index: One-based statement index in the source block.
        :param statement: Original normalized statement text.
        :param kind: Classified statement kind.
        :param lhs: Left-hand symbol when the statement declares one.
        :param status: Parsing result status.
        :param detail: Additional diagnostic explanation.
        :return: None.
        """
        self.index = index
        self.statement = statement
        self.kind = kind
        self.lhs = lhs
        self.status = status
        self.detail = detail


class DgsStandaloneBlockOccurrence:
    """
    One standalone block occurrence extracted from a DGS catalog.
    """

    __slots__ = ("blkref_id", "typ_id", "blkdef_name", "sample_display_name", "connected")

    def __init__(self,
                 blkref_id: str,
                 typ_id: str,
                 blkdef_name: str,
                 sample_display_name: str,
                 connected: bool) -> None:
        """
        Store one standalone block occurrence.

        :param blkref_id: BlkRef identifier.
        :param typ_id: Referenced BlkDef identifier.
        :param blkdef_name: Referenced BlkDef display name.
        :param sample_display_name: Human-facing occurrence label.
        :param connected: Whether the occurrence belongs to a connected graphical component.
        :returns: None.
        """
        self.blkref_id = blkref_id
        self.typ_id = typ_id
        self.blkdef_name = blkdef_name
        self.sample_display_name = sample_display_name
        self.connected = connected


class DgsStandaloneBlockCatalogEntry:
    """
    Aggregated standalone block catalog entry built from DGS occurrences.
    """

    __slots__ = (
        "typ_id",
        "blkdef_name",
        "sample_display_name",
        "occurrence_count",
        "isolated_occurrence_count",
        "connected_occurrence_count",
        "unsupported_lines",
        "build_error",
    )

    def __init__(self,
                 typ_id: str,
                 blkdef_name: str,
                 sample_display_name: str,
                 occurrence_count: int,
                 isolated_occurrence_count: int,
                 connected_occurrence_count: int,
                 unsupported_lines: List[str],
                 build_error: str | None) -> None:
        """
        Store one aggregated standalone block catalog entry.

        :param typ_id: Referenced BlkDef identifier.
        :param blkdef_name: Referenced BlkDef display name.
        :param sample_display_name: Representative human-facing occurrence label.
        :param occurrence_count: Number of occurrences included in this view.
        :param isolated_occurrence_count: Number of isolated occurrences included in this view.
        :param connected_occurrence_count: Number of connected occurrences included in this view.
        :param unsupported_lines: Unsupported DGS source statements.
        :param build_error: Build error when materialization fails.
        :returns: None.
        """
        self.typ_id = typ_id
        self.blkdef_name = blkdef_name
        self.sample_display_name = sample_display_name
        self.occurrence_count = occurrence_count
        self.isolated_occurrence_count = isolated_occurrence_count
        self.connected_occurrence_count = connected_occurrence_count
        self.unsupported_lines = unsupported_lines
        self.build_error = build_error


def _append_to_string_set_map(mapping: Dict[str, Set[str]], key: str, value: str) -> None:
    """
    Append one string value into one ``dict[str, set[str]]`` map.

    :param mapping: Target mapping.
    :param key: Mapping key.
    :param value: Value to append.
    :returns: None.
    """
    if key not in mapping:
        mapping[key] = set()
    else:
        pass
    mapping[key].add(value)


def _filter_graph_edges_to_node_ids(graph: Dict[str, Set[str]], node_ids: Set[str]) -> Dict[str, Set[str]]:
    """
    Filter one graph so every adjacency set only contains nodes inside ``node_ids``.

    :param graph: Source graph.
    :param node_ids: Allowed node identifiers.
    :returns: Filtered graph.
    """
    filtered_graph: Dict[str, Set[str]] = dict()
    node_id: str
    for node_id in node_ids:
        filtered_graph[node_id] = set()
        dst: str
        for dst in graph.get(node_id, set()):
            if dst in node_ids:
                filtered_graph[node_id].add(dst)
            else:
                pass
    return filtered_graph


def _build_reverse_neighbor_subset(graph: Dict[str, Set[str]], node_id: str, node_ids: Set[str]) -> Set[str]:
    """
    Build the reverse-neighbor subset of one node restricted to ``node_ids``.

    :param graph: Source reverse graph.
    :param node_id: Node identifier.
    :param node_ids: Allowed node identifiers.
    :returns: Filtered reverse-neighbor set.
    """
    filtered_neighbors: Set[str] = set()
    src: str
    for src in graph.get(node_id, set()):
        if src in node_ids:
            filtered_neighbors.add(src)
        else:
            pass
    return filtered_neighbors


def _build_expr_signal_name_set(expr: Expr) -> Set[str]:
    """
    Build the set of variable names referenced by one expression.

    :param expr: Symbolic expression.
    :returns: Referenced variable names.
    """
    names: Set[str] = set()
    var: Var
    for var in expr.get_vars():
        names.add(var.name)
    return names


def _build_name_to_var_map(vars_list: List[Var]) -> Dict[str, Var]:
    """
    Build a variable lookup by name.

    :param vars_list: Variable list.
    :returns: Variable lookup by name.
    """
    mapping: Dict[str, Var] = dict()
    var: Var
    for var in vars_list:
        mapping[var.name] = var
    return mapping


def _build_filtered_neighbor_set(graph: Dict[str, Set[str]], node_id: str, node_ids: Set[str]) -> Set[str]:
    """
    Build the neighbor subset of one node restricted to ``node_ids``.

    :param graph: Source graph.
    :param node_id: Node identifier.
    :param node_ids: Allowed node identifiers.
    :returns: Filtered neighbor set.
    """
    filtered_neighbors: Set[str] = set()
    dst: str
    for dst in graph.get(node_id, set()):
        if dst in node_ids:
            filtered_neighbors.add(dst)
        else:
            pass
    return filtered_neighbors


def _build_instance_entry_lookup_by_slot_name(
        entries: List[ElmCompInstanceEntry],
) -> Dict[str, ElmCompInstanceEntry | None]:
    """
    Build the direct-instance lookup by slot name.

    :param entries: Direct instance entries.
    :returns: Unique instance lookup, with ``None`` marking an ambiguity.
    """
    mapping: Dict[str, ElmCompInstanceEntry | None] = dict()
    entry: ElmCompInstanceEntry
    for entry in entries:
        if entry.slot_name is not None:
            existing_entry: ElmCompInstanceEntry | None = mapping.get(
                entry.slot_name,
                None,
            )
            if existing_entry is None and entry.slot_name not in mapping:
                mapping[entry.slot_name] = entry
            else:
                mapping[entry.slot_name] = None
        else:
            pass
    return mapping


def _build_instance_entry_lookup_by_type_name(
        entries: List[ElmCompInstanceEntry],
) -> Dict[str, ElmCompInstanceEntry | None]:
    """
    Build the direct-instance lookup by type name.

    :param entries: Direct instance entries.
    :returns: Unique instance lookup, with ``None`` marking an ambiguity.
    """
    mapping: Dict[str, ElmCompInstanceEntry | None] = dict()
    entry: ElmCompInstanceEntry
    for entry in entries:
        if entry.type_name is not None:
            existing_entry: ElmCompInstanceEntry | None = mapping.get(
                entry.type_name,
                None,
            )
            if existing_entry is None and entry.type_name not in mapping:
                mapping[entry.type_name] = entry
            else:
                mapping[entry.type_name] = None
        else:
            pass
    return mapping


def _disjoint_set_find(parent: Dict[str, str], name: str) -> str:
    """
    Return the representative of one disjoint-set name.

    :param parent: Disjoint-set parent map.
    :param name: Queried element name.
    :returns: Representative name.
    """
    if name not in parent:
        parent[name] = name
    else:
        pass

    root: str = parent[name]
    while root != parent[root]:
        parent[root] = parent[parent[root]]
        root = parent[root]

    return root


def _disjoint_set_union(parent: Dict[str, str], left_name: str, right_name: str) -> None:
    """
    Union two disjoint-set names.

    :param parent: Disjoint-set parent map.
    :param left_name: Left element name.
    :param right_name: Right element name.
    :returns: None.
    """
    left_root: str = _disjoint_set_find(parent, left_name)
    right_root: str = _disjoint_set_find(parent, right_name)

    if left_root != right_root:
        parent[right_root] = left_root
    else:
        pass


def _normalize_graph_signal_name(name: str) -> str:
    text = name.strip().strip('"')
    text = re.sub(r'\(\d+\)$', '', text).strip()
    return text


def _normalize_dgs_pointer_id(pointer_value: object | None) -> str:
    """Normalize one optional DGS pointer without inventing an identifier.

    :param pointer_value: Parsed pointer value or a DGS empty placeholder.
    :return: Trimmed identifier, or an empty string when no object is linked.
    """
    if pointer_value is None:
        pointer_id: str = ""
    elif isinstance(pointer_value, str):
        stripped_pointer_id: str = pointer_value.strip()
        if stripped_pointer_id in {"", "*"}:
            pointer_id = ""
        else:
            pointer_id = stripped_pointer_id
    else:
        pointer_id = str(pointer_value).strip()
    return pointer_id


def get_blkslot_signal_interface(
        circuit: DgsCircuit,
        slot_id: str | None,
) -> Tuple[List[str], List[str]]:
    """Return the normalized signal interface attached to one DGS slot.

    Signal rows can repeat a name at several graphical pins. The catalogue and
    runtime association layers need the semantic interface, so this boundary
    deduplicates names and returns a deterministic order.

    :param circuit: Parsed DGS circuit containing the graphical signal rows.
    :param slot_id: Exact ``BlkSlot`` identifier, or ``None`` for no slot.
    :return: Pair ``(incoming_signals, outgoing_signals)``.
    """
    slot_key: str = _normalize_dgs_pointer_id(slot_id)
    incoming_names: Set[str] = set()
    outgoing_names: Set[str] = set()
    signal: BlkSig

    if slot_key == "":
        incoming_result: List[str] = list()
        outgoing_result: List[str] = list()
    else:
        # Inspect both endpoints because PowerFactory stores slot direction on
        # the signal row rather than duplicating it on the ``BlkSlot`` object.
        for signal in circuit.blksigs:
            signal_name: str = _normalize_graph_signal_name(signal.loc_name)
            if signal_name == "":
                pass
            else:
                source_id: str = _normalize_dgs_pointer_id(signal.pnodfrom)
                target_id: str = _normalize_dgs_pointer_id(signal.pnodto)
                if target_id == slot_key:
                    incoming_names.add(signal_name)
                else:
                    pass
                if source_id == slot_key:
                    outgoing_names.add(signal_name)
                else:
                    pass
        incoming_result = sorted(incoming_names)
        outgoing_result = sorted(outgoing_names)

    return incoming_result, outgoing_result


def _clone_const_or_expr_with_var_factory(value: Const | Expr, vf: VarFactory) -> Const | Expr:
    """
    Clone one expression-like value while recreating constants through the target factory.

    :param value: Source expression-like value.
    :param vf: Target variable factory.
    :returns: Cloned constant or original expression.
    """
    if isinstance(value, Const):
        return vf.add_const(value=value.value, name=value.name)
    else:
        return value


def _collect_block_vars_recursive(block: Block, vars_out: Dict[int, Var], consts_out: Dict[int, Const]) -> None:
    var_lists = [block.state_vars, block.algebraic_vars, block.diff_vars, block.in_vars, block.out_vars]
    for var_list in var_lists:
        for var in var_list:
            vars_out[var.uid] = var

    dict_like = [block.event_dict, block.mode_dict, block.init_eqs, block.diff_init_eqs, block.parameters, block.init_values]
    for mapping in dict_like:
        for key, value in mapping.items():
            if isinstance(key, Var):
                vars_out[key.uid] = key
            if isinstance(value, Var):
                vars_out[value.uid] = value
            if isinstance(value, Const):
                consts_out[value.uid] = value
            if isinstance(value, Expr):
                for var in value.get_vars():
                    vars_out[var.uid] = var

    expr_lists = [block.state_eqs, block.algebraic_eqs, block.differential_eqs]
    for expr_list in expr_lists:
        for expr in expr_list:
            if isinstance(expr, Expr):
                for var in expr.get_vars():
                    vars_out[var.uid] = var

    for child in block.children:
        _collect_block_vars_recursive(child, vars_out, consts_out)


def _clone_block_with_var_factory_recursive(block: Block,
                                            name: str,
                                            created_vars: Dict[int, Var],
                                            var_mapping: Dict[Var | Const | str, Expr | Const],
                                            vf: VarFactory) -> Block:
    """
    Clone one block recursively using the target variable factory and remapping.

    :param block: Source block.
    :param name: Runtime suffix.
    :param created_vars: Created variables by source uid.
    :param var_mapping: Symbol remapping used for substitution.
    :param vf: Target variable factory.
    :returns: Cloned block.
    """
    cloned = Block(name=f"{block.name}_{name}")
    cloned.state_vars = [created_vars[v.uid] for v in block.state_vars]
    cloned.algebraic_vars = [created_vars[v.uid] for v in block.algebraic_vars]
    cloned.diff_vars = [created_vars[v.uid] for v in block.diff_vars]
    cloned.in_vars = [created_vars[v.uid] for v in block.in_vars]
    cloned.out_vars = [created_vars[v.uid] for v in block.out_vars]

    cloned.state_eqs = [expr.subs(var_mapping) for expr in block.state_eqs]
    cloned.algebraic_eqs = [expr.subs(var_mapping) for expr in block.algebraic_eqs]
    cloned.differential_eqs = [expr.subs(var_mapping) for expr in block.differential_eqs]

    cloned.event_dict = dict()
    key_var: Var
    value_expr: Expr | Const
    for key_var, value_expr in block.event_dict.items():
        cloned.event_dict[created_vars[key_var.uid]] = _clone_const_or_expr_with_var_factory(
            value_expr.subs(var_mapping) if isinstance(value_expr, Expr) else value_expr,
            vf,
        )

    cloned.mode_dict = dict()
    for key_var, value_expr in block.mode_dict.items():
        cloned.mode_dict[created_vars[key_var.uid]] = value_expr.subs(var_mapping) if isinstance(value_expr, Expr) else value_expr

    cloned.init_eqs = dict()
    for key_var, value_expr in block.init_eqs.items():
        cloned.init_eqs[created_vars[key_var.uid]] = value_expr.subs(var_mapping)

    cloned.diff_init_eqs = dict()
    for key_var, value_expr in block.diff_init_eqs.items():
        cloned.diff_init_eqs[created_vars[key_var.uid]] = value_expr.subs(var_mapping)

    cloned.parameters = dict()
    for key_var, value_expr in block.parameters.items():
        cloned.parameters[created_vars[key_var.uid]] = _clone_const_or_expr_with_var_factory(value_expr, vf)

    cloned.init_values = dict()
    for key_var, value_expr in block.init_values.items():
        cloned.init_values[created_vars[key_var.uid]] = _clone_const_or_expr_with_var_factory(value_expr, vf)
    cloned.procedural_logic = clone_procedural_logic_entries(block.procedural_logic, var_mapping)
    cloned.children = [
        _clone_block_with_var_factory_recursive(child, name, created_vars, var_mapping, vf)
        for child in block.children
    ]
    return cloned


def materialize_block_with_var_factory(block_data: dict | Block, vf: VarFactory, name: str) -> Block:
    """
    Recreate a serialized block using the target VarFactory and a runtime suffix.

    :param block_data: Serialized block dict or an already-built Block.
    :param vf: VarFactory-like object exposing add_var/add_diff_var/add_const.
    :param name: Runtime suffix used to make names unique.
    :return: Materialized Block.
    """
    if isinstance(block_data, dict):
        source_block: Block = Block.parse(
            data=block_data,
            procedural_logic_codec=ProceduralLogicCodec(),
        )
    else:
        source_block = block_data.copy()

    vars_out: Dict[int, Var] = dict()
    consts_out: Dict[int, Const] = dict()
    _collect_block_vars_recursive(source_block, vars_out, consts_out)

    var_mapping: Dict[Var | Const | str, Expr | Const] = dict()
    created_vars: Dict[int, Var] = dict()

    non_diff_vars = [var for var in vars_out.values() if var.base_var is None]
    diff_vars = [var for var in vars_out.values() if var.base_var is not None]

    for var in sorted(non_diff_vars, key=_var_name_sort_key):
        new_var = vf.add_var(f"{var.name}_{name}")
        created_vars[var.uid] = new_var
        var_mapping[var] = new_var
        var_mapping[var.name] = new_var

    for var in sorted(diff_vars, key=_var_name_sort_key):
        base_var = created_vars[var.base_var.uid]
        new_var = vf.add_diff_var(f"{var.name}_{name}", base_var=base_var)
        created_vars[var.uid] = new_var
        var_mapping[var] = new_var
        var_mapping[var.name] = new_var

    for const in consts_out.values():
        new_const = vf.add_const(value=const.value, name=const.name)
        var_mapping[const] = new_const

    return _clone_block_with_var_factory_recursive(source_block, name, created_vars, var_mapping, vf)


def _build_symbol_table(
    blkdef: BlkDef,
    shared_signals: Dict[str, Var],
) -> Tuple[Dict[str, Var], List[Var], Dict[str, Var], Dict[str, Var], Dict[str, Var]]:
    symbol_table: Dict[str, Var] = dict()
    shared_names: Set[str] = set(blkdef.inputs + blkdef.outputs)

    # Only declared signal ports participate in the enclosing graphical
    # interface. BlkDef internals are lexically local: sharing generic names
    # such as ``o3`` or ``yi`` across unrelated controller definitions merges
    # their algebraic columns while retaining both defining equations.
    for name in shared_names:
        if name not in shared_signals:
            shared_signals[name] = Var(name=name)
        symbol_table[name] = shared_signals[name]

    internal_name: str
    for internal_name in blkdef.internals:
        if internal_name in symbol_table:
            pass
        else:
            symbol_table[internal_name] = Var(
                name=f"{blkdef.loc_name}__{internal_name}"
            )

    state_vars: List[Var] = list()
    state_var_map: Dict[str, Var] = dict()
    diff_var_map: Dict[str, Var] = dict()
    param_var_map: Dict[str, Var] = dict()

    for state_name in blkdef.states:
        state_var = Var(name=f"{blkdef.loc_name}__{state_name}")
        diff_var = Var(name=f"d_{blkdef.loc_name}__{state_name}", base_var=state_var)
        symbol_table[state_name] = state_var
        state_vars.append(state_var)
        state_var_map[state_name] = state_var
        diff_var_map[state_name] = diff_var

    for param_name in blkdef.params:
        param_var = Var(name=f"{blkdef.loc_name}__{param_name}")
        symbol_table[param_name] = param_var
        param_var_map[param_name] = param_var

    return symbol_table, state_vars, state_var_map, diff_var_map, param_var_map


def _parse_blkdef(
        blkdef: BlkDef,
        shared_signals: Dict[str, Var],
        simulation_domain: DynamicSimulationMode = DynamicSimulationMode.RMS,
) -> ParsedDgsBlockDefinition:
    """Parse one DGS block definition into its typed symbolic contract.

    :param blkdef: Source DGS block definition.
    :param shared_signals: Shared symbolic signals available to the block.
    :param simulation_domain: Dynamic simulation domain used by domain helpers.
    :return: Parsed symbolic definition and its fail-closed diagnostics.
    """
    symbol_table, state_vars, state_var_map, diff_var_map, _param_var_map = _build_symbol_table(blkdef, shared_signals)
    _predeclare_statement_lhs_symbols(blkdef, symbol_table)
    boundary_parameter_uids: Set[int] = set()
    parameter_name: str
    for parameter_name in blkdef.params:
        parameter_var: Var | None = symbol_table.get(parameter_name, None)
        if parameter_var is not None:
            boundary_parameter_uids.add(parameter_var.uid)
        else:
            pass
    parser = DgsExpressionParser(
        symbol_table,
        block_name=blkdef.loc_name,
        simulation_domain=simulation_domain,
        boundary_parameter_uids=boundary_parameter_uids,
    )

    state_rhs: Dict[str, Expr] = dict()
    algebraic_rhs: Dict[str, Expr] = dict()
    init_rhs: Dict[str, Expr] = dict()
    parameter_limits: List[Comparison] = list()
    variable_units: List[DgsVariableUnitMetadata] = list()
    discrete_event_actions: List[DgsDiscreteEventAction] = list()
    unsupported_lines: List[str] = list()
    signal_dependencies: Dict[str, Set[str]] = dict()

    for stmt in _split_equation_statements(blkdef.equations_raw):
        stmt_kind, lhs_hint = classify_dgs_statement(stmt)

        if stmt_kind == 'ignored':
            pass
        elif stmt_kind == 'parameter_limit':
            try:
                parameter_limits.extend(
                    _validate_dgs_variable_limit(
                        statement=stmt,
                        parser=parser,
                    )
                )
            except UnsupportedDgsExpression:
                unsupported_lines.append(stmt)
            else:
                pass
        elif stmt_kind == 'runtime_limit':
            try:
                runtime_limit_diagnostics: List[ConditionalDiagnosticLogic] = (
                    parser.parse_runtime_limit_statement(statement=stmt)
                )
            except UnsupportedDgsExpression:
                unsupported_lines.append(stmt)
            else:
                runtime_limit_diagnostic: ConditionalDiagnosticLogic
                for runtime_limit_diagnostic in runtime_limit_diagnostics:
                    signal_dependencies[runtime_limit_diagnostic.name] = (
                        _build_expr_signal_name_set(
                            _comparison_to_expr(
                                runtime_limit_diagnostic.condition_expr
                            )
                        )
                    )
        elif stmt_kind == 'procedural':
            try:
                parser.parse_procedural_statement(stmt)
            except UnsupportedDgsExpression:
                unsupported_lines.append(stmt)
            else:
                signal_dependencies[stmt] = set()
        elif stmt_kind == 'diagnostic':
            try:
                diagnostic: ConditionalDiagnosticLogic = (
                    parser.parse_diagnostic_statement(stmt)
                )
            except UnsupportedDgsExpression:
                unsupported_lines.append(stmt)
            else:
                signal_dependencies[stmt] = _build_expr_signal_name_set(
                    _comparison_to_expr(diagnostic.condition_expr)
                )
        elif stmt_kind == 'discrete_event':
            event_action: DgsDiscreteEventAction | None = (
                parse_dgs_discrete_event_statement(statement=stmt)
            )
            if event_action is None:
                unsupported_lines.append(stmt)
            else:
                try:
                    event_guard: Expr = _comparison_to_expr(
                        parser.parse(event_action.get_trigger_signal_name())
                    )
                    event_trigger: Expr = _comparison_to_expr(
                        parser.parse(event_action.get_trigger_expression())
                    )
                    event_delay: Expr = _comparison_to_expr(
                        parser.parse(event_action.get_delay_expression())
                    )
                except UnsupportedDgsExpression:
                    unsupported_lines.append(stmt)
                else:
                    discrete_event_actions.append(
                        event_action.with_symbolic_expressions(
                            guard_expression=event_guard,
                            trigger_expression=event_trigger,
                            delay_expression=event_delay,
                        )
                    )
                    event_dependencies: Set[str] = _build_expr_signal_name_set(
                        event_guard
                    )
                    event_dependencies.update(
                        _build_expr_signal_name_set(event_trigger)
                    )
                    event_dependencies.update(
                        _build_expr_signal_name_set(event_delay)
                    )
                    signal_dependencies[stmt] = event_dependencies
        elif stmt_kind == 'unit_metadata':
            try:
                symbol_name: str
                unit_text: str
                symbol_name, unit_text = _parse_dgs_unit_metadata(
                    stmt,
                    symbol_table,
                )
            except UnsupportedDgsExpression:
                unsupported_lines.append(stmt)
            else:
                variable_units.append(
                    DgsVariableUnitMetadata(
                        symbol_name=symbol_name,
                        unit_text=unit_text,
                    )
                )
        else:
            rhs_text: str | None = _extract_rhs_text_for_support_report(stmt_kind, stmt)

            if rhs_text is None:
                unsupported_lines.append(stmt)
            else:
                lhs_name: str | None = lhs_hint
                _ensure_support_report_lhs_symbol(lhs_name, blkdef, symbol_table, parser)

                try:
                    rhs_expr = parser.parse(rhs_text)
                except UnsupportedDgsExpression:
                    unsupported_lines.append(stmt)
                else:
                    if isinstance(rhs_expr, Comparison):
                        rhs_expr = rhs_expr.to_expression()
                    else:
                        pass

                    if stmt_kind == 'state':
                        if isinstance(rhs_expr, Expr):
                            assert lhs_name is not None
                            state_rhs[lhs_name] = rhs_expr
                            signal_dependencies[lhs_name] = _build_expr_signal_name_set(rhs_expr)
                        else:
                            unsupported_lines.append(stmt)
                    elif stmt_kind in {'inc', 'inc0'}:
                        assert lhs_name is not None
                        if stmt_kind == 'inc0' and lhs_name in init_rhs:
                            pass
                        else:
                            init_rhs[lhs_name] = rhs_expr
                            signal_dependencies[f"{stmt_kind}({lhs_name})"] = _build_expr_signal_name_set(rhs_expr)
                    elif stmt_kind == 'algebraic':
                        assert lhs_name is not None
                        algebraic_rhs[lhs_name] = rhs_expr
                        parser.register_algebraic_boundary_expression(
                            lhs_name=lhs_name,
                            rhs_expr=rhs_expr,
                        )
                        signal_dependencies[lhs_name] = _build_expr_signal_name_set(rhs_expr)
                    else:
                        unsupported_lines.append(stmt)

    return ParsedDgsBlockDefinition(
        blkdef=blkdef,
        symbol_table=dict(symbol_table),
        state_rhs=state_rhs,
        algebraic_rhs=algebraic_rhs,
        init_rhs=init_rhs,
        parameter_limits=parameter_limits,
        mode_dict=dict(parser.procedural_mode_defaults),
        procedural_logic=list(parser.procedural_logic_entries),
        discrete_event_actions=discrete_event_actions,
        variable_units=variable_units,
        unsupported_lines=unsupported_lines,
        signal_dependencies=signal_dependencies,
    )


def parse_dgs_block_definitions_from_circuit(
        circuit: DgsCircuit,
        simulation_domain: DynamicSimulationMode = DynamicSimulationMode.RMS,
) -> Dict[str, ParsedDgsBlockDefinition]:
    """
    Parse every block definition from one already loaded DGS circuit.

    All definitions share the same signal table so equal DGS signal names map
    to the same symbolic variables when blocks are composed later.

    :param circuit: Already loaded DGS circuit.
    :param simulation_domain: Explicit RMS-balanced or EMT parser context.
    :return: Parsed block definitions indexed by their exact DGS identifiers.
    """
    shared_signals: Dict[str, Var] = dict()
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition] = dict()
    blkdef: BlkDef

    for blkdef in circuit.blkdefs:
        existing_block: ParsedDgsBlockDefinition | None = parsed_blocks.get(
            blkdef.ID,
            None,
        )
        if existing_block is None:
            parsed_blocks[blkdef.ID] = _parse_blkdef(
                blkdef=blkdef,
                shared_signals=shared_signals,
                simulation_domain=simulation_domain,
            )
        else:
            raise ValueError(
                f"DGS BlkDef FID is duplicated: {blkdef.ID}"
            )

    return parsed_blocks


def _select_root_element(
    circuit: DgsCircuit,
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
    root_name: str | None,
    root_typ_id: str | None,
    root_dgs_id: str | None = None,
) -> Tuple[ElmComp, ParsedDgsBlockDefinition]:
    """Select one exact composite root from an already parsed DGS circuit.

    :param circuit: Parsed DGS circuit.
    :param parsed_blocks: Parsed block definitions keyed by DGS identifier.
    :param root_name: Optional root display name.
    :param root_typ_id: Optional root frame identifier.
    :param root_dgs_id: Optional exact root ``ElmComp`` identifier.
    :return: Selected root element and parsed frame definition.
    """
    candidates: List[ElmComp] = list(circuit.elmcomps)
    if root_name is not None:
        candidates = [elm for elm in candidates if elm.loc_name == root_name]
    else:
        pass

    if root_typ_id is not None:
        candidates = [elm for elm in candidates if str(elm.typ_id).strip() == str(root_typ_id).strip()]
    else:
        pass

    if root_dgs_id is not None:
        candidates = [elm for elm in candidates if str(elm.ID) == str(root_dgs_id)]
    else:
        pass

    if len(candidates) == 0:
        raise ValueError("No matching ElmComp root candidate found in the DGS file")
    else:
        pass

    resolved_candidates: List[
        Tuple[ElmComp, ParsedDgsBlockDefinition]
    ] = list()
    elm: ElmComp
    blk: ParsedDgsBlockDefinition | None

    for elm in candidates:
        blk = parsed_blocks.get(str(elm.typ_id).strip(), None)
        if blk is None:
            pass
        else:
            resolved_candidates.append((elm, blk))

    if len(resolved_candidates) == 0:
        raise ValueError("No ElmComp candidate could be resolved to a parsed BlkDef")
    else:
        if len(resolved_candidates) != 1:
            raise ValueError(
                "Several ElmComp roots match the available selectors; provide "
                "an exact root selector"
            )
        else:
            pass

    selected_element: ElmComp
    selected_block: ParsedDgsBlockDefinition
    selected_element, selected_block = resolved_candidates[0]
    return selected_element, selected_block


# A structural ElmComp frame must not discard executable semantics.
def _validate_structural_root_definition(
        root_blkdef: ParsedDgsBlockDefinition,
) -> None:
    """Reject a root ``BlkDef`` that is not a purely structural frame.

    Root executable behavior belongs to exact ``pblk``/``pelm`` children.  The
    root shell therefore accepts only its input, output and internal signal
    declarations; every other runtime declaration must fail closed before any
    child is materialized.

    :param root_blkdef: Parsed definition selected by the exact root FID.
    :return: None.
    """
    if len(root_blkdef.unsupported_lines) > 0:
        unsupported_syntax: str = "; ".join(root_blkdef.unsupported_lines)
        raise UnsupportedDgsExpression(
            "DGS block contains unsupported source statements: "
            f"{unsupported_syntax}"
        )
    else:
        pass

    # A structural frame cannot own declarations or source statements that
    # the root shell would otherwise omit while assembling its exact children.
    has_runtime_declarations: bool = (
        len(root_blkdef.blkdef.states) > 0
        or len(root_blkdef.blkdef.params) > 0
        or len(root_blkdef.blkdef.upper_limit_params) > 0
        or len(root_blkdef.blkdef.lower_limit_params) > 0
    )
    has_parsed_runtime_semantics: bool = (
        len(root_blkdef.state_rhs) > 0
        or len(root_blkdef.algebraic_rhs) > 0
        or len(root_blkdef.init_rhs) > 0
        or len(root_blkdef.parameter_limits) > 0
        or len(root_blkdef.mode_dict) > 0
        or len(root_blkdef.procedural_logic) > 0
        or len(root_blkdef.discrete_event_actions) > 0
    )
    if (
            has_runtime_declarations
            or has_parsed_runtime_semantics
    ):
        raise UnsupportedDgsExpression(
            "DGS root BlkDef must be a purely structural frame without "
            "runtime declarations or source statements"
        )
    else:
        pass


def _collect_internal_candidate_blocks(
    selected_block: ParsedDgsBlockDefinition,
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
) -> Dict[str, ParsedDgsBlockDefinition]:
    """
    Collect candidate internal blocks for a selected composite block using only
    signal-name overlap and dependency closure.

    :param selected_block: Selected composite parsed block.
    :param parsed_blocks: All parsed blocks.
    :return: Internal candidate blocks keyed by block identifier.
    """
    seed_signals: Set[str] = set()
    seed_signals |= set(selected_block.blkdef.inputs)
    seed_signals |= set(selected_block.blkdef.outputs)
    seed_signals |= set(selected_block.blkdef.internals)

    reachable: Dict[str, ParsedDgsBlockDefinition] = dict()
    frontier_signals: Set[str] = set(seed_signals)

    changed: bool = True
    while changed:
        changed = False

        for block_id, parsed in parsed_blocks.items():
            if block_id == selected_block.blkdef.ID:
                pass
            elif block_id in reachable:
                pass
            else:
                block_signals: Set[str] = set()
                block_signals |= set(parsed.blkdef.inputs)
                block_signals |= set(parsed.blkdef.outputs)
                block_signals |= set(parsed.blkdef.internals)

                if len(block_signals & frontier_signals) > 0:
                    reachable[block_id] = parsed
                    frontier_signals |= block_signals
                    changed = True
                else:
                    pass

    return reachable

def _score_internal_candidate(
    selected_block: ParsedDgsBlockDefinition,
    candidate_block: ParsedDgsBlockDefinition,
) -> int:
    """
    Score how likely a block is to belong to the internal structure of a selected block.

    :param selected_block: Selected composite block.
    :param candidate_block: Candidate internal block.
    :return: Integer score.
    """
    selected_inputs: Set[str] = set(selected_block.blkdef.inputs)
    selected_outputs: Set[str] = set(selected_block.blkdef.outputs)
    selected_internals: Set[str] = set(selected_block.blkdef.internals)

    candidate_inputs: Set[str] = set(candidate_block.blkdef.inputs)
    candidate_outputs: Set[str] = set(candidate_block.blkdef.outputs)
    candidate_internals: Set[str] = set(candidate_block.blkdef.internals)

    score: int = 0

    score += 4 * len(candidate_inputs & selected_inputs)
    score += 4 * len(candidate_outputs & selected_outputs)
    score += 3 * len(candidate_outputs & selected_internals)
    score += 3 * len(candidate_inputs & selected_internals)
    score += 2 * len(candidate_internals & selected_internals)
    score += 1 * len(candidate_internals & selected_inputs)
    score += 1 * len(candidate_internals & selected_outputs)

    return score

def _filter_internal_candidates(
    selected_block: ParsedDgsBlockDefinition,
    candidates: Dict[str, ParsedDgsBlockDefinition],
    min_score: int = 2,
) -> Dict[str, ParsedDgsBlockDefinition]:
    """
    Filter candidate internal blocks using signal-overlap scoring.

    :param selected_block: Selected composite block.
    :param candidates: Candidate blocks.
    :param min_score: Minimum score to keep.
    :return: Filtered candidate blocks.
    """
    filtered: Dict[str, ParsedDgsBlockDefinition] = dict()

    for block_id, parsed in candidates.items():
        score: int = _score_internal_candidate(selected_block, parsed)
        if score >= min_score:
            filtered[block_id] = parsed
        else:
            pass

    return filtered

def _parameter_values_by_type_id(
        entries: Iterable[ElmCompInstanceEntry],
) -> Dict[str, Dict[str, float | int | bool | str | complex | None]]:
    """
    Build a unique parameter lookup keyed by block-definition identifier.

    :param entries: Direct instance entries extracted from one ElmComp.
    :return: Parameter values keyed by BlkDef identifier when the type appears only once.
    """
    parameter_values_by_type: Dict[
        str,
        Dict[str, float | int | bool | str | complex | None],
    ] = dict()
    duplicated_type_ids: Set[str] = set()

    unambiguous_entries: List[ElmCompInstanceEntry] = (
        get_unambiguous_elmcomp_direct_instances(entries=entries)
    )
    entry: ElmCompInstanceEntry
    for entry in unambiguous_entries:
        # We only propagate values when one block type appears once inside the parent ElmComp.
        if entry.type_id is None or len(entry.parameter_values) == 0:
            pass
        else:
            if entry.type_id in parameter_values_by_type:
                duplicated_type_ids.add(entry.type_id)
            else:
                parameter_values_by_type[entry.type_id] = dict(entry.parameter_values)

    for type_id in duplicated_type_ids:
        parameter_values_by_type.pop(type_id, None)

    return parameter_values_by_type


def _build_block_from_parsed(
    parsed: ParsedDgsBlockDefinition,
    shared_signals: Dict[str, Var],
    parameter_values: Dict[str, float | int | bool | str | complex | None] | None = None,
    event_targets_by_slot_name: Dict[str, DgsResolvedSwitchTarget] | None = None,
    instance_dgs_id: str | None = None,
) -> Block:
    """
    Materialize one parsed DGS block into a runtime Block.

    :param parsed: Parsed DGS block definition.
    :param shared_signals: Shared signal table reused across sibling blocks.
    :param parameter_values: Optional instance values obtained from ElmDsl rows.
    :param event_targets_by_slot_name: Exact physical switch targets for this root instance.
    :param instance_dgs_id: Exact dynamic instance FID used to own event modes.
    :return: Runtime block ready to be composed or exported.
    """
    if len(parsed.unsupported_lines) > 0:
        unsupported_syntax: str = "; ".join(parsed.unsupported_lines)
        raise UnsupportedDgsExpression(
            "DGS block contains unsupported source statements: "
            f"{unsupported_syntax}"
        )
    else:
        pass

    symbol_table, state_vars, _state_map, diff_var_map, param_var_map = _build_symbol_table(parsed.blkdef, shared_signals)

    for name, old_var in parsed.symbol_table.items():
        if name not in symbol_table:
            symbol_table[name] = Var(name=old_var.name)

    var_mapping: Dict[Var | Const | str, Expr | Const] = dict()
    for name, old_var in parsed.symbol_table.items():
        new_var = symbol_table.get(name, None)
        if new_var is not None:
            var_mapping[old_var] = new_var
            var_mapping[old_var.name] = new_var

    algebraic_pairs: List[Tuple[Var, Expr]] = list()
    used_alg_names: Set[str] = set()
    for lhs_name, rhs_expr in parsed.algebraic_rhs.items():
        if lhs_name in symbol_table:
            lhs_var = symbol_table[lhs_name]
        else:
            lhs_var = Var(name=f"{parsed.blkdef.loc_name}__{lhs_name}")
            symbol_table[lhs_name] = lhs_var

        old_lhs_var = parsed.symbol_table.get(lhs_name, None)
        if old_lhs_var is not None:
            var_mapping[old_lhs_var] = lhs_var
            var_mapping[old_lhs_var.name] = lhs_var

        algebraic_pairs.append((lhs_var, lhs_var - rhs_expr.subs(var_mapping)))
        used_alg_names.add(lhs_name)

    algebraic_vars: List[Var] = [pair[0] for pair in algebraic_pairs]
    algebraic_eqs: List[Expr] = [pair[1] for pair in algebraic_pairs]

    state_eqs: List[Expr] = list()
    effective_state_vars: List[Var] = list()
    effective_diff_vars: List[Var] = list()
    for state_name in parsed.blkdef.states:
        if state_name in parsed.state_rhs:
            effective_state_vars.append(symbol_table[state_name])
            effective_diff_vars.append(diff_var_map[state_name])
            state_eqs.append(parsed.state_rhs[state_name].subs(var_mapping))

    # The BlkDef stores the parameter names, while the ElmDsl instance stores the concrete numbers.
    resolved_parameter_values: Dict[
        str,
        float | int | bool | str | complex | None,
    ] = dict(parameter_values or {})
    # PowerFactory accepts an inactive scripted step with both zero amplitude
    # and zero duration. Preserve its identically zero output while providing
    # a finite denominator to the numerical expression backend.
    amplitude_value: float | int | bool | str | complex | None = (
        resolved_parameter_values.get("Amplitude", None)
    )
    step_duration_value: float | int | bool | str | complex | None = (
        resolved_parameter_values.get("T_step", None)
    )
    inactive_zero_duration_step: bool = bool(
        isinstance(amplitude_value, (float, int))
        and not isinstance(amplitude_value, bool)
        and isinstance(step_duration_value, (float, int))
        and not isinstance(step_duration_value, bool)
        and float(amplitude_value) == 0.0
        and float(step_duration_value) == 0.0
    )
    if inactive_zero_duration_step:
        resolved_parameter_values["T_step"] = 1.0
    else:
        pass
    event_dict: Dict[Var, Const] = dict()
    param_name: str
    param_var: Var
    for param_name, param_var in param_var_map.items():
        event_dict[param_var] = Const(resolved_parameter_values.get(param_name, None), name=param_name)

    init_eqs: Dict[Var, Expr] = dict()
    for lhs_name, rhs_expr in parsed.init_rhs.items():
        lhs_var: Var
        if lhs_name in symbol_table:
            lhs_var = symbol_table[lhs_name]
        else:
            lhs_var = Var(name=f"{parsed.blkdef.loc_name}__{lhs_name}")
            symbol_table[lhs_name] = lhs_var

        old_lhs_var = parsed.symbol_table.get(lhs_name, None)
        if old_lhs_var is not None:
            var_mapping[old_lhs_var] = lhs_var
            var_mapping[old_lhs_var.name] = lhs_var

        init_eqs[lhs_var] = rhs_expr.subs(var_mapping)

    mode_dict: Dict[Var, Expr | Const] = dict()
    for mode_var, rhs_expr in parsed.mode_dict.items():
        mapped_var = var_mapping.get(mode_var, None)
        if not isinstance(mapped_var, Var):
            mapped_var = symbol_table.get(mode_var.name, None)
        if not isinstance(mapped_var, Var):
            mapped_var = Var(name=mode_var.name)
            symbol_table[mode_var.name] = mapped_var
        mode_dict[mapped_var] = rhs_expr.subs(var_mapping) if isinstance(rhs_expr, Expr) else rhs_expr

    procedural_logic = clone_procedural_logic_entries(parsed.procedural_logic, var_mapping)
    event_parameter_bindings: Dict[int, float] = dict()
    event_parameter_name: str
    event_parameter_value: float | int | bool | str | complex | None
    for event_parameter_name, event_parameter_value in resolved_parameter_values.items():
        parsed_parameter_var: Var | None = parsed.symbol_table.get(
            event_parameter_name,
            None,
        )
        if (
                parsed_parameter_var is not None
                and isinstance(event_parameter_value, (float, int, bool))
        ):
            event_parameter_bindings[parsed_parameter_var.uid] = float(
                event_parameter_value
            )
        else:
            pass

    event_index: int
    event_action: DgsDiscreteEventAction
    for event_index, event_action in enumerate(parsed.discrete_event_actions):
        guard_expression: Expr | None = event_action.get_symbolic_guard_expression()
        trigger_expression: Expr | None = event_action.get_symbolic_trigger_expression()
        delay_expression: Expr | None = event_action.get_symbolic_delay_expression()
        event_target: DgsResolvedSwitchTarget | None
        if event_targets_by_slot_name is None:
            event_target = None
        else:
            event_target = event_targets_by_slot_name.get(
                event_action.get_target_slot_name(),
                None,
            )

        if guard_expression is None or trigger_expression is None or delay_expression is None:
            raise UnsupportedDgsExpression(
                f"DGS switch event '{event_action.get_event_name()}' has incomplete expressions"
            )
        else:
            pass

        if event_target is None:
            guard_variables: List[Var] = guard_expression.get_vars()
            guard_is_static: bool = all(
                guard_variable.uid in event_parameter_bindings
                for guard_variable in guard_variables
            )
            guard_is_disabled: bool = (
                guard_is_static
                and float(guard_expression.eval_uid(event_parameter_bindings)) < 0.5
            )
            if guard_is_disabled:
                # A missing optional breaker remains valid only when the exact
                # instance parameters prove that its event can never be enabled.
                pass
            else:
                raise UnsupportedDgsExpression(
                    "DGS switch event target is unresolved or is not a StaSwitch: "
                    f"{event_action.get_target_slot_name()}"
                )
        else:
            if instance_dgs_id is None:
                raise UnsupportedDgsExpression(
                    "DGS switch event requires an exact dynamic instance FID"
                )
            else:
                pass
            switch_mode: Var = Var(
                name=(
                    f"dgs_switch_{instance_dgs_id}_"
                    f"{event_target.switch_id}_{event_index}"
                )
            )
            mode_dict[switch_mode] = Const(
                1.0 if event_target.initial_closed else 0.0
            )
            procedural_logic.append(
                DelayedSwitchEventLogic(
                    output_var_name=switch_mode.name,
                    guard_expr=guard_expression.subs(var_mapping),
                    trigger_expr=trigger_expression.subs(var_mapping),
                    delay_expr=delay_expression.subs(var_mapping),
                    target_device_idtag=event_target.device_id,
                    target_switch_idtag=event_target.switch_id,
                    target_terminal_index=event_target.terminal_index,
                    initial_closed=event_target.initial_closed,
                    command_closed=(
                        event_action.get_command()
                        == DgsDiscreteEventCommand.Close
                    ),
                    name=event_action.get_event_name(),
                )
            )
    parameter_limits: List[Comparison] = [
        parameter_limit.subs(var_mapping)
        for parameter_limit in parsed.parameter_limits
    ]

    return Block(
        name=parsed.blkdef.loc_name,
        state_vars=effective_state_vars,
        state_eqs=state_eqs,
        diff_vars=effective_diff_vars,
        algebraic_vars=algebraic_vars,
        algebraic_eqs=algebraic_eqs,
        inequalities=parameter_limits,
        in_vars=[shared_signals[name] for name in parsed.blkdef.inputs if name in shared_signals],
        out_vars=[shared_signals[name] for name in parsed.blkdef.outputs if name in shared_signals],
        event_dict=event_dict,
        mode_dict=mode_dict,
        init_eqs=init_eqs,
        procedural_logic=procedural_logic,
    )


def _internalize_initialized_dgs_slot_inputs(
    block: Block,
    parsed: ParsedDgsBlockDefinition,
    entry: ElmCompInstanceEntry,
) -> None:
    """Internalize initialized definition inputs omitted by one DGS slot.

    A ``BlkDef`` declares every symbol required to parse its equations, while
    the owning ``BlkSlot`` declares the public interface of the concrete
    instance. PowerFactory uses ``inc()`` assignments for held setpoints that
    remain definition inputs but are deliberately absent from the slot. Move
    those values to the runtime-parameter store so they retain their startup
    expression without becoming unconnected graphical ports.

    Inputs omitted by the slot without an ``inc()`` assignment remain public.
    Their semantics are not sufficient to classify them as internal values,
    and silently removing them would create an unowned equation dependency.

    :param block: Materialized formula block for the concrete slot instance.
    :param parsed: Parsed block definition supplying declarations and ``inc()``.
    :param entry: Concrete DGS slot contract supplying the public inputs.
    :return: None.
    """
    slot_input_names: Set[str] = set(
        entry.get_slot_signal_components(
            direction=DgsSlotSignalDirection.Input,
        )
    )
    definition_input_names: Set[str] = set(parsed.blkdef.inputs)
    retained_inputs: List[Var] = list()
    input_var: Var
    for input_var in block.in_vars:
        is_definition_input: bool = input_var.name in definition_input_names
        is_public_slot_input: bool = input_var.name in slot_input_names
        initial_expression: Expr | None = block.init_eqs.get(input_var, None)
        if (
                is_definition_input
                and not is_public_slot_input
                and initial_expression is not None
        ):
            # This value is sampled from the startup operating point and then
            # retained as an internal controller setpoint during simulation.
            block.event_dict[input_var] = initial_expression
            block.init_eqs.pop(input_var, None)
        else:
            # Public slot inputs and ambiguous omissions must remain visible
            # until an authoritative producer or outer interface owns them.
            retained_inputs.append(input_var)
    else:
        pass
    block.in_vars = retained_inputs


def _build_dependency_graph(parsed_blocks: Dict[str, ParsedDgsBlockDefinition]) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]], Dict[str, Set[str]]]:
    producer_map: Dict[str, Set[str]] = dict()
    consumer_map: Dict[str, Set[str]] = dict()

    for block_id, parsed in parsed_blocks.items():
        produced_names = set(parsed.blkdef.outputs) | set(parsed.algebraic_rhs.keys()) | set(parsed.state_rhs.keys())
        for name in produced_names:
            _append_to_string_set_map(producer_map, name, block_id)

        for dep_names in parsed.signal_dependencies.values():
            for name in dep_names:
                _append_to_string_set_map(consumer_map, name, block_id)

    dependency_graph: Dict[str, Set[str]] = dict()
    block_id: str
    for block_id in parsed_blocks.keys():
        dependency_graph[block_id] = set()

    for signal_name, producers in producer_map.items():
        consumers = consumer_map.get(signal_name, set())
        for producer in producers:
            for consumer in consumers:
                if producer != consumer:
                    dependency_graph[producer].add(consumer)

    return dependency_graph, producer_map, consumer_map


def dgs_to_root_block(
    path: str,
    root_name: str | None = None,
    root_typ_id: str | None = None,
    root_dgs_id: str | None = None,
) -> DgsRootBlockResult:
    """Parse one DGS file and materialize one selected composite root.

    :param path: Source DGS path.
    :param root_name: Optional root ``ElmComp`` display name.
    :param root_typ_id: Optional exact frame identifier.
    :param root_dgs_id: Optional exact root ``ElmComp`` identifier.
    :return: Parsed root hierarchy and dependency metadata.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path)
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition] = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)
    )
    return build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parsed_blocks,
        root_name=root_name,
        root_typ_id=root_typ_id,
        root_dgs_id=root_dgs_id,
    )


def build_dgs_root_block_from_circuit(
    circuit: DgsCircuit,
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
    root_name: str | None,
    root_typ_id: str | None = None,
    root_dgs_id: str | None = None,
) -> DgsRootBlockResult:
    """Build one structural root shell from an already parsed DGS circuit.

    This stage deliberately creates no executable children.  The following
    direct builder owns child selection through exact typed ``pblk``/``pelm``
    relations.

    :param circuit: Parsed DGS circuit.
    :param parsed_blocks: Parsed block definitions shared by the import.
    :param root_name: Optional root display name.
    :param root_typ_id: Optional exact frame identifier.
    :param root_dgs_id: Optional exact root ``ElmComp`` identifier.
    :return: Parsed root hierarchy and dependency metadata.
    """
    shared_signals: Dict[str, Var] = dict()
    root_element: ElmComp
    root_blkdef: ParsedDgsBlockDefinition
    root_element, root_blkdef = _select_root_element(
        circuit=circuit,
        parsed_blocks=parsed_blocks,
        root_name=root_name,
        root_typ_id=root_typ_id,
        root_dgs_id=root_dgs_id,
    )
    _validate_structural_root_definition(root_blkdef=root_blkdef)

    # Allocate the structural interface directly from the selected frame.  No
    # sibling BlkDef may become a child merely because it reuses a signal name.
    root_signal_names: List[str] = list(root_blkdef.blkdef.inputs)
    root_signal_names.extend(root_blkdef.blkdef.outputs)
    root_signal_names.extend(root_blkdef.blkdef.internals)
    signal_name: str
    for signal_name in root_signal_names:
        if signal_name not in shared_signals:
            shared_signals[signal_name] = Var(name=signal_name)
        else:
            pass

    root_block: Block = Block(
        name=root_element.loc_name,
        children=list(),
        in_vars=[shared_signals[name] for name in root_blkdef.blkdef.inputs],
        out_vars=[shared_signals[name] for name in root_blkdef.blkdef.outputs],
        algebraic_vars=[shared_signals[name] for name in root_blkdef.blkdef.internals],
    )

    # Retain the already parsed catalogue only for exact downstream lookups.
    # Executable children are selected later from typed pblk/pelm relations.
    combined_blocks: Dict[str, ParsedDgsBlockDefinition] = dict(parsed_blocks)
    dependency_graph: Dict[str, Set[str]]
    producer_map: Dict[str, Set[str]]
    consumer_map: Dict[str, Set[str]]
    dependency_graph, producer_map, consumer_map = _build_dependency_graph(
        combined_blocks
    )

    return DgsRootBlockResult(
        root_block=root_block,
        root_blkdef=root_blkdef,
        root_element=root_element,
        parsed_blocks=combined_blocks,
        dependency_graph=dependency_graph,
        producer_map=producer_map,
        consumer_map=consumer_map,
    )


# Dynamic validation: BlkSlot filters match exact classes, never substrings.
def _extract_slot_contract_element_kinds(
        entry: ElmCompInstanceEntry,
) -> List[str]:
    """Extract explicit DGS class patterns from one slot contract.

    :param entry: Direct relation carrying the source ``BlkSlot`` contract.
    :return: Declared ``Elm*`` and ``Sta*`` patterns, retaining wildcards.
    """
    element_kind_patterns: List[str] = list()
    contract_value: str | None
    for contract_value in (entry.slot_element, entry.slot_filter):
        if contract_value is None:
            pass
        else:
            matched_kinds: List[str] = re.findall(
                r"\b(?:Elm|Sta)[A-Za-z0-9_]+\*?",
                contract_value,
            )
            matched_kind: str
            for matched_kind in matched_kinds:
                if matched_kind not in element_kind_patterns:
                    element_kind_patterns.append(matched_kind)
                else:
                    pass

    return element_kind_patterns


def _slot_contract_accepts_element_kind(
        element_kind_patterns: List[str],
        element_kind: str,
) -> bool:
    """Check one resolved DGS class against explicit slot patterns.

    PowerFactory may place a generic ``ElmDsl`` or ``ElmComp`` container in a
    slot whose filter names its specialized ``Elm*`` role.  That declarative
    indirection is accepted only when an actual role pattern is present.

    :param element_kind_patterns: Declared class names or prefix wildcards.
    :param element_kind: Exact class of the resolved ``pElm`` object.
    :return: Whether one declared pattern accepts the resolved class.
    """
    accepts_element_kind: bool = False
    element_kind_pattern: str
    for element_kind_pattern in element_kind_patterns:
        if element_kind_pattern.endswith("*"):
            element_kind_prefix: str = element_kind_pattern[:-1]
            if element_kind.startswith(element_kind_prefix):
                accepts_element_kind = True
            else:
                pass
        else:
            if element_kind == element_kind_pattern:
                accepts_element_kind = True
            else:
                pass

    if (
            not accepts_element_kind
            and (element_kind == "ElmDsl" or element_kind == "ElmComp")
    ):
        # Specialized Elm filters describe the model role while pElm resolves
        # to the generic dynamic container that owns the exact BlkDef FID.
        for element_kind_pattern in element_kind_patterns:
            normalized_kind: str = element_kind_pattern.rstrip("*")
            targets_registered_kind: bool = (
                _slot_pattern_targets_registered_element_kind(
                    element_kind_pattern=element_kind_pattern,
                )
            )
            if (
                    normalized_kind.startswith("Elm")
                    and not targets_registered_kind
            ):
                accepts_element_kind = True
            else:
                pass
    else:
        pass

    return accepts_element_kind


def _slot_pattern_targets_registered_element_kind(
        element_kind_pattern: str,
) -> bool:
    """Check whether a slot pattern names a concrete parsed DGS class.

    :param element_kind_pattern: Declared literal or prefix wildcard.
    :return: Whether the DGS registry contains a matching concrete class.
    """
    normalized_kind: str = element_kind_pattern.rstrip("*")
    pattern_has_wildcard: bool = element_kind_pattern.endswith("*")
    targets_registered_kind: bool = False
    registered_element_kind: str
    for registered_element_kind in DgsCircuit.ELEMENT_CLASS_BY_KIND.keys():
        if pattern_has_wildcard:
            if registered_element_kind.startswith(normalized_kind):
                targets_registered_kind = True
            else:
                pass
        else:
            if registered_element_kind == normalized_kind:
                targets_registered_kind = True
            else:
                pass

    return targets_registered_kind


def _slot_contract_requires_dynamic_instance(
        element_kind_patterns: List[str],
) -> bool:
    """Determine whether every allowed slot class is a dynamic instance.

    :param element_kind_patterns: Declared class names or prefix wildcards.
    :return: Whether the contract requires one generic dynamic wrapper.
    """
    requires_dynamic_instance: bool = len(element_kind_patterns) > 0
    element_kind_pattern: str
    for element_kind_pattern in element_kind_patterns:
        normalized_kind: str = element_kind_pattern.rstrip("*")
        targets_registered_kind: bool = (
            _slot_pattern_targets_registered_element_kind(
                element_kind_pattern=element_kind_pattern,
            )
        )
        pattern_requires_dynamic_wrapper: bool = (
            normalized_kind == "ElmDsl"
            or normalized_kind == "ElmComp"
            or (
                normalized_kind.startswith("Elm")
                and element_kind_pattern.endswith("*")
                and not targets_registered_kind
            )
        )
        if pattern_requires_dynamic_wrapper:
            pass
        else:
            requires_dynamic_instance = False

    return requires_dynamic_instance


def _resolve_switch_event_targets(
    circuit: DgsCircuit,
    direct_entries: List[ElmCompInstanceEntry],
) -> Dict[str, DgsResolvedSwitchTarget]:
    """Resolve direct switch slots through ``StaSwitch`` and ``StaCubic`` FIDs.

    :param circuit: Parsed DGS circuit containing the authoritative references.
    :param direct_entries: Exact direct root slot relations.
    :return: Resolved switch targets keyed by slot name.
    """
    element_by_id: Dict[str, object] = _build_dgs_element_index(circuit=circuit)
    targets_by_slot_name: Dict[str, DgsResolvedSwitchTarget] = dict()
    direct_entry: ElmCompInstanceEntry

    for direct_entry in direct_entries:
        if direct_entry.slot_name is None or direct_entry.element_id is None:
            pass
        else:
            switch_element: object | None = element_by_id.get(
                direct_entry.element_id,
                None,
            )
            if isinstance(switch_element, StaSwitch):
                cubicle_element: object | None = element_by_id.get(
                    str(switch_element.fold_id),
                    None,
                )
                if isinstance(cubicle_element, StaCubic):
                    targets_by_slot_name[direct_entry.slot_name] = (
                        DgsResolvedSwitchTarget(
                            switch_id=switch_element.ID,
                            device_id=str(cubicle_element.obj_id),
                            terminal_index=int(cubicle_element.obj_bus),
                            initial_closed=bool(switch_element.on_off),
                        )
                    )
                else:
                    pass
            else:
                pass

    return targets_by_slot_name


def build_direct_root_elmcomp_block(
    circuit: DgsCircuit,
    result: DgsRootBlockResult,
    graphical_indexes: DgsGraphicalIndexes | None = None,
) -> DgsDirectRootBuildResult:
    """Build a root ElmComp block using only its direct DGS child instances.

    :param circuit: Parsed DGS circuit.
    :param result: Root selection result.
    :param graphical_indexes: Optional shared graphical indexes.
    :return: Root runtime block and exact reusable slot materializations.
    """
    shared_signals: Dict[str, Var] = dict()
    root_interface_vars: List[Var] = list(result.root_block.in_vars)
    root_interface_vars.extend(result.root_block.out_vars)
    root_interface_vars.extend(result.root_block.algebraic_vars)
    root_var: Var
    for root_var in root_interface_vars:
        existing_root_var: Var | None = shared_signals.get(root_var.name, None)
        if existing_root_var is None:
            shared_signals[root_var.name] = root_var
        else:
            if existing_root_var.uid != root_var.uid:
                raise ValueError(
                    "DGS structural root exposes conflicting variable "
                    f"identities for signal {root_var.name}"
                )
            else:
                pass

    child_blocks: List[Block] = list()
    child_block_by_slot_id: Dict[str, Block] = dict()
    graphical_tree_by_slot_id: Dict[str, DgsGraphicTreeResult] = dict()
    raw_direct_entries: List[ElmCompInstanceEntry] = (
        extract_elmcomp_direct_instances(
            circuit,
            result.root_element,
        )
    )
    direct_entries: List[ElmCompInstanceEntry] = get_unique_elmcomp_slot_entries(
        entries=raw_direct_entries,
    )
    if len(direct_entries) != len(raw_direct_entries):
        raise ValueError(
            "Direct ElmComp relations contain a missing, unresolved or duplicated BlkSlot"
        )
    else:
        pass
    event_targets_by_slot_name: Dict[str, DgsResolvedSwitchTarget] = (
        _resolve_switch_event_targets(
            circuit=circuit,
            direct_entries=direct_entries,
        )
    )

    entry: ElmCompInstanceEntry
    for entry in direct_entries:
        slot_contract_element_kinds: List[str] = (
            _extract_slot_contract_element_kinds(entry=entry)
        )
        slot_requires_dynamic_instance: bool = (
            _slot_contract_requires_dynamic_instance(
                element_kind_patterns=slot_contract_element_kinds,
            )
        )
        entry_is_dynamic_instance: bool = (
            entry.element_kind == "ElmDsl"
            or entry.element_kind == "ElmComp"
        )
        entry_matches_slot_contract: bool = False
        if entry.element_kind is None:
            pass
        else:
            entry_matches_slot_contract = _slot_contract_accepts_element_kind(
                element_kind_patterns=slot_contract_element_kinds,
                element_kind=entry.element_kind,
            )
        if slot_requires_dynamic_instance and (
                not entry.element_reference_is_resolved
                or not entry_is_dynamic_instance
        ):
            raise ValueError(
                "Direct dynamic BlkSlot has no resolved ElmDsl or ElmComp instance"
            )
        else:
            pass
        if (
                entry.element_reference_is_resolved
                and not entry_matches_slot_contract
        ):
            raise ValueError(
                "Direct instance does not satisfy its typed BlkSlot filter"
            )
        else:
            pass

        if not entry_is_dynamic_instance:
            pass
        else:
            if entry.type_id is None:
                raise ValueError(
                    "Direct dynamic instance has no resolved BlkDef FID"
                )
            else:
                pass
            parsed_block: ParsedDgsBlockDefinition | None = (
                result.parsed_blocks.get(entry.type_id, None)
            )
            if parsed_block is None:
                raise ValueError(
                    "Direct dynamic instance references a missing parsed BlkDef"
                )
            else:
                graphical_tree: DgsGraphicTreeResult | None
                if parsed_block.blkdef.isMacro == 0:
                    graphical_tree = None
                else:
                    graphical_tree = (
                        extract_root_slot_graphical_tree_from_circuit(
                            circuit=circuit,
                            result=result,
                            slot_name=str(entry.slot_name or entry.type_name or ""),
                            slot_dgs_id=entry.slot_id,
                            graphical_indexes=graphical_indexes,
                        )
                    )

                if graphical_tree is None:
                    # Formula blocks share the exact root interface variables
                    # while retaining their instance-specific parameters.
                    child_block: Block = _build_block_from_parsed(
                        parsed_block,
                        shared_signals,
                        parameter_values=entry.parameter_values,
                        event_targets_by_slot_name=event_targets_by_slot_name,
                        instance_dgs_id=entry.element_id,
                    )
                    # The type definition contains private initialized
                    # setpoints as input symbols. The concrete slot is the
                    # authoritative public interface for this occurrence.
                    _internalize_initialized_dgs_slot_inputs(
                        block=child_block,
                        parsed=parsed_block,
                        entry=entry,
                    )
                else:
                    if len(
                            graphical_tree.parent_bindings.unresolved_input_names
                    ) > 0:
                        unresolved_input_names: str = ", ".join(
                            graphical_tree.parent_bindings.unresolved_input_names
                        )
                        raise ValueError(
                            "Direct graphical dynamic instance has unresolved "
                            f"live inputs: {unresolved_input_names}"
                        )
                    else:
                        pass
                    child_block = graphical_tree.view_block
                    interface_var: Var
                    interface_vars: List[Var] = list(child_block.in_vars)
                    interface_vars.extend(child_block.out_vars)
                    for interface_var in interface_vars:
                        shared_interface_var: Var | None = shared_signals.get(
                            interface_var.name,
                            None,
                        )
                        if shared_interface_var is None:
                            pass
                        else:
                            # The root and its graphical child must expose one
                            # variable identity for every shared public port.
                            child_block.update_model(
                                interface_var,
                                shared_interface_var,
                            )

                    if entry.slot_id is None:
                        pass
                    else:
                        graphical_tree_by_slot_id[entry.slot_id] = (
                            graphical_tree
                        )

                child_blocks.append(child_block)
                if entry.slot_id is None:
                    pass
                else:
                    child_block_by_slot_id[entry.slot_id] = child_block

    # Formula children can use private port labels that differ from the cable
    # label exposed by their slots. Reproduce the authoritative direct wiring
    # before pruning structural root labels, so connected aliases do not become
    # independent solver variables.
    _connect_direct_root_graphical_signals(
        circuit=circuit,
        direct_entries=direct_entries,
        child_block_by_slot_id=child_block_by_slot_id,
    )

    # The importer completes the sole root Block without cloning its Var objects.
    if len(result.root_block.children) > 0:
        raise ValueError("DGS root Block was already materialized")
    else:
        result.root_block.children = child_blocks
    root_block: Block = result.root_block

    # The outer ElmComp frame is also a structural projection. Retain only
    # internals reached by executable child semantics so graphical cable labels
    # cannot create free solver columns after the direct children are attached.
    root_block.algebraic_vars = (
        _retain_referenced_structural_algebraic_vars(
            parent_block=root_block,
        )
    )
    return DgsDirectRootBuildResult(
        root_block=root_block,
        child_block_by_slot_id=child_block_by_slot_id,
        graphical_tree_by_slot_id=graphical_tree_by_slot_id,
        direct_entries=direct_entries,
    )

def _build_dgs_element_index(
        circuit: DgsCircuit,
        excluded_element_ids: Set[str] | None = None,
) -> dict[str, object]:
    """
    Build a flat DGS object index by identifier.

    :param circuit: Parsed DGS circuit.
    :param excluded_element_ids: Ambiguous root identifiers already rejected
        by the owning import stage.
    :return: Dictionary from identifier to object.
    """
    element_by_id: dict[str, object] = dict()
    element: DGSElement
    effective_excluded_element_ids: Set[str]
    if excluded_element_ids is None:
        effective_excluded_element_ids = set()
    else:
        effective_excluded_element_ids = excluded_element_ids

    # pElm can reference dynamic or physical objects. Preserve every exact FID
    # through the circuit's public, typed element boundary.
    for element in circuit.get_all_elements_iter():
        if (
                element.ID == ""
                or element.ID in effective_excluded_element_ids
        ):
            pass
        else:
            existing_element: object | None = element_by_id.get(
                element.ID,
                None,
            )
            if existing_element is None:
                element_by_id[element.ID] = element
            else:
                raise ValueError(
                    f"DGS element FID is duplicated: {element.ID}"
                )

    return element_by_id


def _build_blkdef_index(circuit: DgsCircuit) -> dict[str, BlkDef]:
    """
    Build a BlkDef index by identifier.

    :param circuit: Parsed DGS circuit.
    :return: Dictionary from BlkDef identifier to BlkDef.
    """
    blkdef_by_id: dict[str, BlkDef] = dict()

    for blkdef in circuit.blkdefs:
        existing_blkdef: BlkDef | None = blkdef_by_id.get(blkdef.ID, None)
        if existing_blkdef is None:
            blkdef_by_id[blkdef.ID] = blkdef
        else:
            raise ValueError(
                f"DGS BlkDef FID is duplicated: {blkdef.ID}"
            )

    return blkdef_by_id


def _build_graphic_node_index(circuit: DgsCircuit) -> dict[str, object]:
    """
    Build index of graphical-model DGS nodes by identifier.

    :param circuit: Parsed DGS circuit.
    :return: Mapping from node id to graphic object.
    """
    node_by_id: dict[str, object] = dict()

    for obj in circuit.blkdefs:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkrefs:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkslots:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkfroms:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkgotos:
        node_by_id[obj.ID] = obj
    for obj in circuit.blksums:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkdivs:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkmuls:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkswts:
        node_by_id[obj.ID] = obj

    return node_by_id


def _build_standalone_block_occurrence(blkref: BlkRef,
                                       blkdef_by_id: dict[str, BlkDef],
                                       adjacency: dict[str, set[str]]) -> DgsStandaloneBlockOccurrence | None:
    """
    Build one standalone block occurrence from one BlkRef object.

    :param blkref: Source BlkRef occurrence.
    :param blkdef_by_id: BlkDef lookup by identifier.
    :param adjacency: Graphical adjacency by node id.
    :returns: Standalone block occurrence or None when the BlkRef is invalid.
    """
    if blkref.typ_id not in blkdef_by_id:
        return None
    else:
        blkdef: BlkDef = blkdef_by_id[blkref.typ_id]
        component: set[str] = _graphic_connected_component(adjacency, blkref.ID)
        connected: bool = len(component) > 1
        sample_display_name: str = blkref.cdisName if blkref.cdisName != '' else blkdef.loc_name
        return DgsStandaloneBlockOccurrence(
            blkref_id=blkref.ID,
            typ_id=blkref.typ_id,
            blkdef_name=blkdef.loc_name,
            sample_display_name=sample_display_name,
            connected=connected,
        )


def _extract_typ_id_from_catalog_module_filename(module_filename: str) -> str | None:
    """
    Extract the typ_id prefix from one catalog module filename.

    :param module_filename: Catalog module filename.
    :returns: Extracted typ_id or None when the filename does not match the expected pattern.
    """
    match_obj = re.fullmatch(r"typ_(\d+)__.+\.py", module_filename)
    if match_obj is None:
        return None
    else:
        return match_obj.group(1)


def _build_catalog_entry_info_by_typ_id() -> Dict[str, tuple[Sequence[str], str | None]]:
    """
    Build the standalone catalog metadata lookup by typ_id from the shipped basic block catalog.

    :returns: Unsupported-lines and build-error tuple by typ_id.
    """
    info_by_typ_id: Dict[str, tuple[Sequence[str], str | None]] = dict()
    descriptor: object
    for descriptor in get_basic_block_catalog_descriptors():
        module_filename: str = descriptor.module_filename
        typ_id: str | None = _extract_typ_id_from_catalog_module_filename(module_filename)
        if typ_id is None:
            pass
        else:
            info_by_typ_id[typ_id] = (tuple(descriptor.unsupported_lines), None)

    return info_by_typ_id


def list_dgs_blkref_catalog_occurrences_from_circuit(
        circuit: DgsCircuit,
) -> List[DgsStandaloneBlockOccurrence]:
    """
    List standalone block occurrences from one already loaded DGS circuit.

    :param circuit: Already loaded DGS circuit.
    :return: Valid ``BlkRef`` occurrences with their connection state.
    """
    adjacency: Dict[str, Set[str]] = _build_blksig_adjacency(circuit=circuit)
    blkdef_by_id: Dict[str, BlkDef] = _build_blkdef_index(circuit=circuit)
    occurrences: List[DgsStandaloneBlockOccurrence] = list()
    blkref: BlkRef

    for blkref in circuit.blkrefs:
        occurrence: DgsStandaloneBlockOccurrence | None = (
            _build_standalone_block_occurrence(
                blkref=blkref,
                blkdef_by_id=blkdef_by_id,
                adjacency=adjacency,
            )
        )
        if occurrence is None:
            pass
        else:
            occurrences.append(occurrence)

    return occurrences


def list_dgs_blkref_catalog_occurrences(dgs_path: str) -> List[DgsStandaloneBlockOccurrence]:
    """
    List every BlkRef occurrence that belongs to the standalone DGS block catalog.

    :param dgs_path: Source DGS file.
    :returns: Standalone block occurrences.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(dgs_path)
    return list_dgs_blkref_catalog_occurrences_from_circuit(circuit=circuit)


def _build_standalone_catalog_entry(typ_id: str,
                                    occurrences: List[DgsStandaloneBlockOccurrence],
                                    parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
                                    catalog_info_by_typ_id: Dict[str, tuple[Sequence[str], str | None]]) -> DgsStandaloneBlockCatalogEntry:
    """
    Build one aggregated standalone block catalog entry.

    :param typ_id: Referenced BlkDef identifier.
    :param occurrences: Occurrences for the given type id.
    :param parsed_blocks: Parsed blocks by identifier.
    :returns: Aggregated catalog entry.
    """
    parsed_block: ParsedDgsBlockDefinition = parsed_blocks[typ_id]
    build_error: str | None = None
    unsupported_lines: List[str] = list(parsed_block.unsupported_lines)

    if typ_id in catalog_info_by_typ_id:
        stored_unsupported_lines, stored_build_error = catalog_info_by_typ_id[typ_id]
        unsupported_lines = list(stored_unsupported_lines)
        build_error = stored_build_error
    else:
        shared_signals: Dict[str, Var] = dict()
        try:
            _build_block_from_parsed(parsed_block, shared_signals)
        except Exception as exc:
            build_error = str(exc)

    connected_occurrence_count: int = 0
    isolated_occurrence_count: int = 0
    occurrence: DgsStandaloneBlockOccurrence
    for occurrence in occurrences:
        if occurrence.connected:
            connected_occurrence_count += 1
        else:
            isolated_occurrence_count += 1

    return DgsStandaloneBlockCatalogEntry(
        typ_id=typ_id,
        blkdef_name=parsed_block.blkdef.loc_name,
        sample_display_name=occurrences[0].sample_display_name,
        occurrence_count=len(occurrences),
        isolated_occurrence_count=isolated_occurrence_count,
        connected_occurrence_count=connected_occurrence_count,
        unsupported_lines=unsupported_lines,
        build_error=build_error,
    )


def _get_standalone_catalog_entry_numeric_type_id(
        entry: DgsStandaloneBlockCatalogEntry,
) -> int:
    """Return the numeric DGS type identifier used for catalogue ordering.

    :param entry: Standalone catalogue entry to order.
    :return: Numeric DGS type identifier.
    """
    return int(entry.typ_id)


def build_dgs_standalone_block_catalog_from_circuit(
        circuit: DgsCircuit,
        parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
        isolated_only: bool = True,
) -> List[DgsStandaloneBlockCatalogEntry]:
    """
    Build the standalone block catalogue from one already loaded DGS circuit.

    :param circuit: Already loaded DGS circuit.
    :param parsed_blocks: Definitions previously parsed from ``circuit``.
    :param isolated_only: Exclude occurrences connected to a graphical model.
    :return: Aggregated catalogue entries ordered by numeric DGS type id.
    """
    catalog_info_by_type_id: Dict[str, tuple[Sequence[str], str | None]] = (
        _build_catalog_entry_info_by_typ_id()
    )
    occurrences: List[DgsStandaloneBlockOccurrence] = (
        list_dgs_blkref_catalog_occurrences_from_circuit(circuit=circuit)
    )
    occurrences_by_type_id: Dict[str, List[DgsStandaloneBlockOccurrence]] = dict()
    occurrence: DgsStandaloneBlockOccurrence

    for occurrence in occurrences:
        if isolated_only and occurrence.connected:
            pass
        else:
            if occurrence.typ_id not in occurrences_by_type_id:
                occurrences_by_type_id[occurrence.typ_id] = list()
            else:
                pass
            occurrences_by_type_id[occurrence.typ_id].append(occurrence)

    entries: List[DgsStandaloneBlockCatalogEntry] = list()
    type_id: str
    grouped_occurrences: List[DgsStandaloneBlockOccurrence]
    for type_id, grouped_occurrences in occurrences_by_type_id.items():
        entries.append(
            _build_standalone_catalog_entry(
                typ_id=type_id,
                occurrences=grouped_occurrences,
                parsed_blocks=parsed_blocks,
                catalog_info_by_typ_id=catalog_info_by_type_id,
            )
        )

    entries.sort(key=_get_standalone_catalog_entry_numeric_type_id)
    return entries


def build_dgs_standalone_block_catalog(
        dgs_path: str,
        isolated_only: bool = True,
) -> List[DgsStandaloneBlockCatalogEntry]:
    """
    Build the aggregated standalone DGS block catalog.

    :param dgs_path: Source DGS file.
    :param isolated_only: Keep only isolated occurrences when ``True``.
    :returns: Aggregated catalog entries.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(dgs_path)
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition] = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)
    )
    return build_dgs_standalone_block_catalog_from_circuit(
        circuit=circuit,
        parsed_blocks=parsed_blocks,
        isolated_only=isolated_only,
    )


def build_standalone_blkdef_block(
        dgs_path: str,
        typ_id: str,
        block_name: str | None = None,
) -> Block:
    """
    Build one domain-neutral symbolic block from a DGS block definition.

    :param dgs_path: Source DGS file.
    :param typ_id: Exact DGS identifier of the required ``BlkDef``.
    :param block_name: Optional block name overriding the DGS name.
    :return: Materialized symbolic block.
    :raises ValueError: When the requested ``BlkDef`` does not exist.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(dgs_path)
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition] = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)
    )

    if typ_id not in parsed_blocks:
        raise ValueError(
            f"DGS block definition '{typ_id}' was not found in '{dgs_path}'."
        )

    return build_standalone_blkdef_block_from_parsed_block(
        parsed_block=parsed_blocks[typ_id],
        block_name=block_name,
    )


def build_standalone_blkdef_block_from_parsed_block(
        parsed_block: ParsedDgsBlockDefinition,
        block_name: str | None = None,
) -> Block:
    """
    Build one domain-neutral symbolic block from a parsed DGS definition.

    A standalone ``BlkDef`` contains equations but does not establish whether
    they will be used by an RMS or EMT simulation. The importer selects and
    validates that target domain after this parser boundary.

    :param parsed_block: Parsed DGS block definition.
    :param block_name: Optional block name overriding the DGS name.
    :return: Materialized symbolic block containing the parsed equations.
    :raises UnsupportedDgsExpression: When any source statement was not parsed.
    """
    if len(parsed_block.unsupported_lines) > 0:
        unsupported_syntax: str = "; ".join(parsed_block.unsupported_lines)
        raise UnsupportedDgsExpression(
            f"DGS block definition '{parsed_block.blkdef.loc_name}' contains "
            f"unsupported syntax: {unsupported_syntax}"
        )

    resolved_block_name: str
    if block_name is None:
        resolved_block_name = parsed_block.blkdef.loc_name
    else:
        resolved_block_name = str(block_name)

    runtime_block: Block = _build_block_from_parsed(
        parsed=parsed_block,
        shared_signals=dict(),
    )
    runtime_block.name = resolved_block_name
    return runtime_block


def build_graphic_node_index(circuit: DgsCircuit) -> Dict[str, object]:
    """
    Build a public index of graphical DGS nodes by identifier.

    :param circuit: Parsed DGS circuit.
    :return: Mapping from node id to graphical object.
    """
    return _build_graphic_node_index(circuit)


def _build_blksig_adjacency(circuit: DgsCircuit) -> dict[str, set[str]]:
    """
    Build undirected adjacency graph over graphical nodes connected by BlkSig.

    :param circuit: Parsed DGS circuit.
    :return: Undirected adjacency map.
    """
    adjacency: dict[str, set[str]] = dict()

    for sig in circuit.blksigs:
        src = sig.pnodfrom.strip() if isinstance(sig.pnodfrom, str) else ''
        dst = sig.pnodto.strip() if isinstance(sig.pnodto, str) else ''

        if src == '' or dst == '':
            pass
        else:
            _append_to_string_set_map(adjacency, src, dst)
            _append_to_string_set_map(adjacency, dst, src)

    return adjacency


def _graphic_connected_component(adjacency: dict[str, set[str]], root_id: str) -> set[str]:
    """
    Return the connected component of a root graphical node.

    :param adjacency: Undirected graphical adjacency.
    :param root_id: Root node identifier.
    :return: Connected component node ids.
    """
    visited: set[str] = set()
    frontier: list[str] = [root_id]

    while frontier:
        node_id = frontier.pop()
        if node_id in visited:
            pass
        else:
            visited.add(node_id)
            for nxt in adjacency.get(node_id, set()):
                if nxt not in visited:
                    frontier.append(nxt)
                else:
                    pass

    return visited


def _graphic_node_label(node: object) -> str:
    """
    Return a human-readable label for a graphical node.

    :param node: DGS graphical node.
    :return: Display label.
    """
    if isinstance(node, BlkRef):
        return node.cdisName if node.cdisName != '' else node.typ_id
    if isinstance(node, BlkSum):
        return node.loc_name
    if isinstance(node, BlkDiv):
        return node.loc_name
    if isinstance(node, BlkMul):
        return node.loc_name
    if isinstance(node, BlkSwt):
        return node.loc_name
    if isinstance(node, BlkFrom):
        return node.loc_name
    if isinstance(node, BlkGoto):
        return node.loc_name
    if isinstance(node, BlkSlot):
        return node.loc_name
    if isinstance(node, BlkDef):
        return node.loc_name
    return str(node)


def _graphic_node_kind(node: object) -> str:
    """
    Return a short kind label for a graphical node.

    :param node: DGS graphical node.
    :return: Kind label.
    """
    if isinstance(node, BlkRef):
        return 'BlkRef'
    if isinstance(node, BlkSum):
        return 'BlkSum'
    if isinstance(node, BlkDiv):
        return 'BlkDiv'
    if isinstance(node, BlkMul):
        return 'BlkMul'
    if isinstance(node, BlkSwt):
        return 'BlkSwt'
    if isinstance(node, BlkFrom):
        return 'BlkFrom'
    if isinstance(node, BlkGoto):
        return 'BlkGoto'
    if isinstance(node, BlkSlot):
        return 'BlkSlot'
    if isinstance(node, BlkDef):
        return 'BlkDef'
    return type(node).__name__


def _build_graphic_node_signal_map(circuit: DgsCircuit) -> dict[str, set[str]]:
    """
    Collect normalized signal labels attached to each graphical node through BlkSig and BlkFrom definitions.

    :param circuit: Parsed DGS circuit.
    :return: Mapping from node id to normalized signal labels.
    """
    node_signals: dict[str, set[str]] = dict()

    for sig in circuit.blksigs:
        sig_name = _normalize_graph_signal_name(sig.loc_name)
        if sig_name == '':
            pass
        else:
            if isinstance(sig.pnodfrom, str) and sig.pnodfrom.strip() != '':
                _append_to_string_set_map(node_signals, sig.pnodfrom.strip(), sig_name)
            else:
                pass

            if isinstance(sig.pnodto, str) and sig.pnodto.strip() != '':
                _append_to_string_set_map(node_signals, sig.pnodto.strip(), sig_name)
            else:
                pass

    for blk_from in circuit.blkfroms:
        for sig_name in blk_from.signals:
            clean = _normalize_graph_signal_name(sig_name)
            if clean != '':
                _append_to_string_set_map(node_signals, blk_from.ID, clean)

    for blk_goto in circuit.blkgotos:
        for sig_name in blk_goto.signals:
            clean = _normalize_graph_signal_name(sig_name)
            if clean != '':
                _append_to_string_set_map(node_signals, blk_goto.ID, clean)

    return node_signals


def build_dgs_graphical_indexes(
    circuit: DgsCircuit,
    excluded_element_ids: Set[str] | None = None,
) -> DgsGraphicalIndexes:
    """Build graphical indexes once for every slot in one DGS import.

    :param circuit: Already parsed DGS circuit.
    :param excluded_element_ids: Ambiguous roots rejected before indexing.
    :return: Immutable graphical lookup indexes.
    """
    return DgsGraphicalIndexes(
        adjacency=_build_blksig_adjacency(circuit=circuit),
        node_by_id=_build_graphic_node_index(circuit=circuit),
        node_signals=_build_graphic_node_signal_map(circuit=circuit),
        element_by_id=_build_dgs_element_index(
            circuit=circuit,
            excluded_element_ids=excluded_element_ids,
        ),
    )


def _collect_routed_graphical_source_signal_names(
    node_ids: Set[str],
    node_by_id: Dict[str, object],
    node_signals: Dict[str, Set[str]],
) -> Set[str]:
    """Collect exact signal names read by selected ``BlkFrom`` nodes.

    A blank source normally represents an intentional disconnected input. A
    selected ``BlkFrom`` reading the same signal proves instead that the
    signal is live and that its producer topology is absent from the export.

    :param node_ids: Graphical component identifiers.
    :param node_by_id: Parsed graphical objects keyed by identifier.
    :param node_signals: Normalized signal names keyed by node identifier.
    :return: Live routed signal names in the selected component.
    """
    routed_signal_names: Set[str] = set()
    node_id: str

    # Only routing nodes inside this exact component can affect its fail-closed
    # disconnected-input decision.
    for node_id in node_ids:
        if isinstance(node_by_id.get(node_id, None), BlkFrom):
            routed_signal_names.update(node_signals.get(node_id, set()))
        else:
            pass
    return routed_signal_names


def _record_unique_named_var(
    candidate_var: Var,
    var_by_name: Dict[str, Var],
    ambiguous_names: Set[str],
) -> None:
    """Record a variable only while its symbolic name identifies one UID.

    :param candidate_var: Variable discovered in the parent initialization
        surface.
    :param var_by_name: Unique variables accumulated by symbolic name.
    :param ambiguous_names: Names discarded after multiple UIDs were found.
    :return: None.
    """
    candidate_name: str = candidate_var.name
    existing_var: Var | None = var_by_name.get(candidate_name, None)

    if candidate_name in ambiguous_names:
        pass
    elif existing_var is None:
        var_by_name[candidate_name] = candidate_var
    elif existing_var.uid == candidate_var.uid:
        pass
    else:
        # Ambiguous names must remain unresolved; choosing the first matching
        # variable would reconnect models by text instead of identity.
        var_by_name.pop(candidate_name, None)
        ambiguous_names.add(candidate_name)


def _build_parent_internal_var_lookup(
    selected_block: ParsedDgsBlockDefinition,
    parent_block: Block,
) -> Dict[str, Var]:
    """Resolve parent internals from their exact initialization variables.

    The parsed definition retains the raw DGS name while the materialized
    block owns the runtime UID. Initialization keys and dependencies are the
    authoritative bridge between those representations. Duplicate runtime
    names are rejected rather than guessed.

    :param selected_block: Parsed parent block definition.
    :param parent_block: Materialized parent runtime block.
    :return: Unambiguous parent internal variables keyed by raw DGS name.
    """
    runtime_var_by_name: Dict[str, Var] = dict()
    ambiguous_runtime_names: Set[str] = set()
    init_var: Var
    init_expr: Expr
    dependency_var: Var

    # Initialization left-hand sides can themselves be graphical internals.
    for init_var in parent_block.init_eqs.keys():
        _record_unique_named_var(
            candidate_var=init_var,
            var_by_name=runtime_var_by_name,
            ambiguous_names=ambiguous_runtime_names,
        )

    # Initialization expressions expose every parent internal consumed by an
    # ``inc()`` equation without attaching dynamic metadata to Block.
    for init_expr in parent_block.init_eqs.values():
        for dependency_var in init_expr.get_vars():
            _record_unique_named_var(
                candidate_var=dependency_var,
                var_by_name=runtime_var_by_name,
                ambiguous_names=ambiguous_runtime_names,
            )

    parent_internal_vars: Dict[str, Var] = dict()
    internal_name: str
    for internal_name in selected_block.blkdef.internals:
        parsed_internal_var: Var | None = selected_block.symbol_table.get(
            internal_name,
            None,
        )
        if parsed_internal_var is None:
            pass
        else:
            runtime_internal_var: Var | None = runtime_var_by_name.get(
                parsed_internal_var.name,
                None,
            )
            if runtime_internal_var is None:
                pass
            else:
                parent_internal_vars[internal_name] = runtime_internal_var
    return parent_internal_vars


def _connect_graphical_parent_internal_signals(
    selected_block: ParsedDgsBlockDefinition,
    parent_block: Block,
    child_blocks: Dict[str, Block],
    child_input_index_by_connector: Dict[
        str,
        Dict[Tuple[DgsGraphicalConnectorKind, int], int],
    ],
    graphical_signals: List[BlkSig],
    connections: List[GraphicConnectionInstruction],
    routed_source_signal_names: Set[str],
    node_by_id: Dict[str, object],
) -> DgsGraphicalParentBindingResult:
    """Bind parent ``inc()`` dependencies to exact graphical child values.

    Concrete child outputs replace matching parent internals. A blank producer
    creates a deterministic zero only when its exact child input is otherwise
    unresolved. Signals read by ``BlkFrom`` remain unresolved when their
    producer topology is absent, preventing a fabricated zero.

    :param selected_block: Parsed parent graphical block definition.
    :param parent_block: Materialized parent block updated in place.
    :param child_blocks: Materialized graphical children keyed by identifier.
    :param child_input_index_by_connector: Runtime child input indices keyed by
        graphical connector kind and raw port.
    :param graphical_signals: Exact graphical cables from the parsed DGS.
    :param connections: Successfully resolved non-empty cable connections.
    :param routed_source_signal_names: Signals read by selected ``BlkFrom``
        nodes.
    :param node_by_id: Parsed graphical objects keyed by identifier.
    :return: Typed binding result for review and contract tests.
    """
    parent_internal_vars: Dict[str, Var] = _build_parent_internal_var_lookup(
        selected_block=selected_block,
        parent_block=parent_block,
    )
    parent_internal_names: Set[str] = set(selected_block.blkdef.internals)
    resolved_internal_names: Set[str] = set()
    disconnected_input_names: Set[str] = set()
    unresolved_input_names: Set[str] = set()
    connected_consumer_keys: Set[Tuple[str, int]] = set()
    instruction: GraphicConnectionInstruction

    # A resolved cable owns its consumer pin and cannot also be interpreted as
    # an intentionally disconnected input.
    for instruction in connections:
        if instruction.consumer_input_index is None:
            pass
        else:
            connected_consumer_keys.add((
                instruction.consumer_node_id,
                instruction.consumer_input_index,
            ))

    graphical_signal: BlkSig
    for graphical_signal in graphical_signals:
        signal_name: str = _normalize_graph_signal_name(
            name=graphical_signal.loc_name,
        )
        source_node_id: str = _normalize_dgs_pointer_id(
            pointer_value=graphical_signal.pnodfrom,
        )
        source_block: Block | None = child_blocks.get(source_node_id, None)
        source_connector_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(graphical_signal.iconfrom),
                endpoint_node=node_by_id.get(source_node_id, None),
                is_source_endpoint=True,
            )
        )
        source_input_index_by_connector: Dict[
            Tuple[DgsGraphicalConnectorKind, int],
            int,
        ] = child_input_index_by_connector.get(
            source_node_id,
            dict(),
        )
        source_output_index: int | None = (
            _resolve_graphical_runtime_output_index(
                endpoint_node=node_by_id.get(source_node_id, None),
                graphical_output_index=int(graphical_signal.inodfrom),
                exported_output_base=(
                    _get_graphical_exported_output_base(
                        endpoint_node=node_by_id.get(source_node_id, None),
                        input_index_by_connector=(
                            source_input_index_by_connector
                        ),
                    )
                ),
                runtime_output_count=(
                    0 if source_block is None else len(source_block.out_vars)
                ),
            )
        )
        parent_internal_var: Var | None = parent_internal_vars.get(
            signal_name,
            None,
        )

        # The concrete source UID is authoritative for a parent internal with
        # the same exact DGS signal identity.
        if (
            signal_name not in parent_internal_names
            or signal_name in resolved_internal_names
            or source_block is None
            or source_connector_kind != DgsGraphicalConnectorKind.Output
            or source_output_index is None
            or parent_internal_var is None
        ):
            pass
        else:
            source_output_var: Var = source_block.out_vars[source_output_index]
            parent_block.update_model(parent_internal_var, source_output_var)
            resolved_internal_names.add(signal_name)

    for graphical_signal in graphical_signals:
        signal_name = _normalize_graph_signal_name(
            name=graphical_signal.loc_name,
        )
        source_node_id = _normalize_dgs_pointer_id(
            pointer_value=graphical_signal.pnodfrom,
        )
        consumer_node_id: str = _normalize_dgs_pointer_id(
            pointer_value=graphical_signal.pnodto,
        )
        consumer_block: Block | None = child_blocks.get(
            consumer_node_id,
            None,
        )
        consumer_connector_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(graphical_signal.iconto),
                endpoint_node=node_by_id.get(consumer_node_id, None),
                is_source_endpoint=False,
            )
        )
        consumer_index_lookup: Dict[
            Tuple[DgsGraphicalConnectorKind, int],
            int,
        ] | None = child_input_index_by_connector.get(
            consumer_node_id,
            None,
        )
        if consumer_connector_kind is None or consumer_index_lookup is None:
            consumer_runtime_index: int | None = None
        else:
            consumer_runtime_index = consumer_index_lookup.get(
                (
                    consumer_connector_kind,
                    int(graphical_signal.inodto),
                ),
                None,
            )
        if consumer_runtime_index is None:
            consumer_is_connected: bool = False
        else:
            consumer_is_connected = (
                consumer_node_id,
                consumer_runtime_index,
            ) in connected_consumer_keys
        parent_internal_var = parent_internal_vars.get(signal_name, None)

        # Only one exact blank producer on a free child pin qualifies for the
        # PowerFactory disconnected-input value.
        if (
            signal_name not in parent_internal_names
            or signal_name in resolved_internal_names
            or source_node_id != ""
            or consumer_block is None
            or consumer_runtime_index is None
            or consumer_runtime_index < 0
            or consumer_runtime_index >= len(consumer_block.in_vars)
            or consumer_is_connected
            or parent_internal_var is None
        ):
            pass
        elif signal_name in routed_source_signal_names:
            # A selected From node proves this is a live route whose producer
            # class is absent, so zero would conceal missing parser coverage.
            unresolved_input_names.add(signal_name)
        else:
            consumer_input_var: Var = consumer_block.in_vars[
                consumer_runtime_index
            ]
            parent_block.update_model(parent_internal_var, consumer_input_var)
            consumer_block.event_dict[consumer_input_var] = Const(0.0)
            resolved_internal_names.add(signal_name)
            disconnected_input_names.add(signal_name)

    return DgsGraphicalParentBindingResult(
        resolved_internal_names=sorted(resolved_internal_names),
        disconnected_input_names=sorted(disconnected_input_names),
        unresolved_input_names=sorted(unresolved_input_names),
    )


def _build_graph_signal_alias_map(
    node_ids: Set[str],
    node_by_id: Dict[str, object],
    node_signals: Dict[str, Set[str]],
) -> Dict[str, Set[str]]:
    parent: Dict[str, str] = dict()

    for node_id in node_ids:
        node = node_by_id.get(node_id)
        if isinstance(node, BlkFrom):
            aliases = sorted(node_signals.get(node_id, set()))
            if len(aliases) < 2:
                pass
            else:
                head = aliases[0]
                for alias in aliases[1:]:
                    _disjoint_set_union(parent, head, alias)
        else:
            pass

    groups: Dict[str, Set[str]] = dict()
    for signal_names in node_signals.values():
        for sig in signal_names:
            root = _disjoint_set_find(parent, sig)
            _append_to_string_set_map(groups, root, sig)

    alias_map: Dict[str, Set[str]] = dict()
    for group in groups.values():
        for sig in group:
            alias_map[sig] = set(group)

    return alias_map


def _build_augmented_graphical_adjacency(
    node_ids: Set[str],
    adjacency: Dict[str, Set[str]],
    node_by_id: Dict[str, object],
    node_signals: Dict[str, Set[str]],
    alias_map: Dict[str, Set[str]],
) -> Dict[str, Set[str]]:
    expanded: Dict[str, Set[str]] = dict()
    node_id: str
    for node_id in node_ids:
        expanded[node_id] = _build_filtered_neighbor_set(adjacency, node_id, node_ids)

    routing_nodes: List[str] = [
        node_id for node_id in node_ids
        if isinstance(node_by_id.get(node_id), (BlkFrom, BlkGoto))
    ]

    for idx, left_id in enumerate(routing_nodes):
        left_aliases: Set[str] = set()
        for sig in node_signals.get(left_id, set()):
            left_aliases |= alias_map.get(sig, {sig})

        if len(left_aliases) == 0:
            pass
        else:
            for right_id in routing_nodes[idx + 1:]:
                right_aliases: Set[str] = set()
                for sig in node_signals.get(right_id, set()):
                    right_aliases |= alias_map.get(sig, {sig})

                if len(left_aliases & right_aliases) == 0:
                    pass
                else:
                    _append_to_string_set_map(expanded, left_id, right_id)
                    _append_to_string_set_map(expanded, right_id, left_id)

    return expanded


def _graph_distance(adjacency: Dict[str, Set[str]], start_node: str, target_node: str) -> int:
    if start_node == target_node:
        return 0

    visited: Set[str] = set()
    frontier: List[Tuple[str, int]] = [(start_node, 0)]

    while frontier:
        node_id, dist = frontier.pop(0)
        if node_id in visited:
            pass
        else:
            visited.add(node_id)

            for nxt in adjacency.get(node_id, set()):
                if nxt == target_node:
                    return dist + 1
                elif nxt not in visited:
                    frontier.append((nxt, dist + 1))
                else:
                    pass

    return 10**9


def _resolve_graphic_block_connections(
    selected_block: ParsedDgsBlockDefinition,
    child_node_ids: List[str],
    child_blocks: Dict[str, Block],
    child_input_specs: Dict[str, List[str]],
    child_input_index_by_connector: Dict[
        str,
        Dict[Tuple[DgsGraphicalConnectorKind, int], int],
    ],
    child_output_specs: Dict[str, List[str]],
    graphical_signals: List[BlkSig],
    adjacency: Dict[str, Set[str]],
    node_by_id: Dict[str, object],
    alias_map: Dict[str, Set[str]],
    root_runtime_block: Block,
) -> Tuple[List[GraphicConnectionInstruction], List[Var]]:
    """
    Resolve graphical connections by exact cable identity and then aliases.

    Direct ``BlkSig`` endpoints and connector-local indices are authoritative.
    Signal aliases and graph distance are used only when routing nodes or
    incomplete exports prevent a direct structural connection.

    :param selected_block: Parsed graphical macro definition.
    :param child_node_ids: Materialized graphical child identifiers.
    :param child_blocks: Runtime blocks keyed by graphical identifier.
    :param child_input_specs: Runtime input names by child identifier.
    :param child_input_index_by_connector: Compact runtime input indices keyed
        by exact connector category and raw port.
    :param child_output_specs: Runtime output names by child identifier.
    :param graphical_signals: Exact graphical cable records.
    :param adjacency: Augmented graphical adjacency.
    :param node_by_id: Parsed graphical objects keyed by identifier.
    :param alias_map: Equivalent signal labels used by routing nodes.
    :param root_runtime_block: Runtime representation of the macro boundary.
    :return: Connection instructions and resolved macro output variables.
    """
    producer_entries: List[Tuple[str, str, Var]] = list()
    root_signal_vars: Dict[str, Var] = _build_name_to_var_map(
        list(root_runtime_block.in_vars)
    )

    node_id: str
    for node_id in child_node_ids:
        block: Block = child_blocks[node_id]
        output_index: int
        output_name: str
        for output_index, output_name in enumerate(
                child_output_specs.get(node_id, list()),
        ):
            if output_index < len(block.out_vars):
                producer_entries.append((node_id, output_name, block.out_vars[output_index]))
            else:
                pass

    connections: List[GraphicConnectionInstruction] = list()
    connected_consumer_inputs: Set[Tuple[str, int]] = set()
    explicit_consumer_inputs_seen: Set[Tuple[str, int]] = set()
    explicit_root_outputs_seen: Set[int] = set()
    explicit_root_output_sources: Dict[int, Tuple[str, int]] = dict()
    root_node_id: str = str(selected_block.blkdef.ID)
    root_input_names: List[str] = list(selected_block.blkdef.inputs)
    root_output_names: List[str] = list(selected_block.blkdef.outputs)
    root_input_index_by_connector: Dict[
        Tuple[DgsGraphicalConnectorKind, int],
        int,
    ] = _build_ordinary_graphical_input_index(input_names=root_input_names)
    graphical_signal: BlkSig

    # Reproduce direct cables before considering any label-based fallback.
    for graphical_signal in graphical_signals:
        source_node_id: str = _normalize_dgs_pointer_id(
            pointer_value=graphical_signal.pnodfrom,
        )
        consumer_node_id: str = _normalize_dgs_pointer_id(
            pointer_value=graphical_signal.pnodto,
        )
        source_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(graphical_signal.iconfrom),
                endpoint_node=node_by_id.get(source_node_id, None),
                is_source_endpoint=True,
            )
        )
        consumer_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(graphical_signal.iconto),
                endpoint_node=node_by_id.get(consumer_node_id, None),
                is_source_endpoint=False,
            )
        )
        if (
                source_node_id in child_blocks
                and source_kind != DgsGraphicalConnectorKind.Output
        ):
            raise ValueError(
                "Graphical DGS cable references an invalid child source "
                f"connector: {graphical_signal.ID}"
            )
        elif (
                source_node_id == root_node_id
                and source_kind != DgsGraphicalConnectorKind.Input
        ):
            raise ValueError(
                "Graphical DGS cable references an invalid root source "
                f"connector: {graphical_signal.ID}"
            )
        elif source_node_id != "" and source_node_id not in node_by_id:
            raise ValueError(
                "Graphical DGS cable references a missing source FID: "
                f"{graphical_signal.ID}"
            )
        else:
            pass
        if consumer_node_id != "" and consumer_node_id not in node_by_id:
            raise ValueError(
                "Graphical DGS cable references a missing target FID: "
                f"{graphical_signal.ID}"
            )
        elif consumer_node_id == root_node_id:
            root_output_index: int = int(graphical_signal.inodto)
            if (
                    consumer_kind != DgsGraphicalConnectorKind.Output
                    or root_output_index < 0
                    or root_output_index >= len(root_output_names)
            ):
                raise ValueError(
                    "Graphical DGS cable targets an invalid root output: "
                    f"{graphical_signal.ID}"
                )
            elif source_node_id == "":
                raise ValueError(
                    "Graphical DGS root output cable has no exact source: "
                    f"{graphical_signal.ID}"
                )
            elif root_output_index in explicit_root_outputs_seen:
                raise ValueError(
                    "Graphical DGS root output has multiple explicit cables: "
                    f"{root_output_names[root_output_index]}"
                )
            else:
                explicit_root_outputs_seen.add(root_output_index)
                if source_node_id in child_blocks:
                    source_output_names: List[str] = child_output_specs.get(
                        source_node_id,
                        list(),
                    )
                    explicit_source_output_index: int | None = (
                        _resolve_graphical_runtime_output_index(
                            endpoint_node=node_by_id.get(
                                source_node_id,
                                None,
                            ),
                            graphical_output_index=int(
                                graphical_signal.inodfrom
                            ),
                            exported_output_base=(
                                _get_graphical_exported_output_base(
                                    endpoint_node=node_by_id.get(
                                        source_node_id,
                                        None,
                                    ),
                                    input_index_by_connector=(
                                        child_input_index_by_connector.get(
                                            source_node_id,
                                            dict(),
                                        )
                                    ),
                                )
                            ),
                            runtime_output_count=len(source_output_names),
                        )
                    )
                    if explicit_source_output_index is None:
                        raise ValueError(
                            "Graphical DGS cable references an invalid source "
                            f"output: {graphical_signal.ID}"
                        )
                    else:
                        explicit_root_output_sources[root_output_index] = (
                            source_node_id,
                            explicit_source_output_index,
                        )
                else:
                    pass
        else:
            pass
        if consumer_kind is None:
            consumer_runtime_index: int | None = None
        else:
            consumer_runtime_index = child_input_index_by_connector.get(
                consumer_node_id,
                dict(),
            ).get(
                (consumer_kind, int(graphical_signal.inodto)),
                None,
            )

        if (
                consumer_node_id in child_blocks
                and (
                    consumer_kind is None
                    or consumer_runtime_index is None
                )
        ):
            raise ValueError(
                "Graphical DGS cable targets an invalid input connector: "
                f"{graphical_signal.ID}"
            )
        else:
            pass

        if (
                consumer_node_id in child_blocks
                and consumer_runtime_index is not None
        ):
            consumer_key: Tuple[str, int] = (
                consumer_node_id,
                consumer_runtime_index,
            )
            if consumer_key in explicit_consumer_inputs_seen:
                raise ValueError(
                    "Graphical DGS input has multiple explicit cables: "
                    f"{consumer_node_id}[{consumer_runtime_index}]"
                )
            else:
                explicit_consumer_inputs_seen.add(consumer_key)
            if (
                    source_node_id in child_blocks
                    and source_kind == DgsGraphicalConnectorKind.Output
            ):
                source_output_names: List[str] = child_output_specs.get(
                    source_node_id,
                    list(),
                )
                source_output_index: int | None = (
                    _resolve_graphical_runtime_output_index(
                        endpoint_node=node_by_id.get(source_node_id, None),
                        graphical_output_index=int(graphical_signal.inodfrom),
                        exported_output_base=(
                            _get_graphical_exported_output_base(
                                endpoint_node=node_by_id.get(
                                    source_node_id,
                                    None,
                                ),
                                input_index_by_connector=(
                                    child_input_index_by_connector.get(
                                        source_node_id,
                                        dict(),
                                    )
                                ),
                            )
                        ),
                        runtime_output_count=len(source_output_names),
                    )
                )
                if source_output_index is None:
                    raise ValueError(
                        "Graphical DGS cable references an invalid source "
                        f"output: {graphical_signal.ID}"
                    )
                else:
                    consumer_input_names: List[str] = child_input_specs.get(
                        consumer_node_id,
                        list(),
                    )
                    if consumer_runtime_index >= len(consumer_input_names):
                        raise ValueError(
                            "Graphical DGS cable resolved outside the consumer "
                            f"interface: {graphical_signal.ID}"
                        )
                    else:
                        connections.append(
                            GraphicConnectionInstruction(
                                consumer_node_id=consumer_node_id,
                                consumer_input_name=consumer_input_names[
                                    consumer_runtime_index
                                ],
                                source_kind="block_output",
                                consumer_input_index=consumer_runtime_index,
                                source_output_name=source_output_names[
                                    source_output_index
                                ],
                                source_output_index=source_output_index,
                                source_node_id=source_node_id,
                            )
                        )
                        connected_consumer_inputs.add(consumer_key)
            elif (
                    source_node_id == root_node_id
                    and source_kind == DgsGraphicalConnectorKind.Input
            ):
                root_runtime_input_index: int | None = (
                    root_input_index_by_connector.get(
                        (source_kind, int(graphical_signal.inodfrom)),
                        None,
                    )
                )
                if (
                        root_runtime_input_index is None
                        or root_runtime_input_index >= len(root_input_names)
                ):
                    raise ValueError(
                        "Graphical DGS cable references an invalid root input: "
                        f"{graphical_signal.ID}"
                    )
                else:
                    source_root_name: str = root_input_names[
                        root_runtime_input_index
                    ]
                    consumer_input_names = child_input_specs.get(
                        consumer_node_id,
                        list(),
                    )
                    if consumer_runtime_index >= len(consumer_input_names):
                        raise ValueError(
                            "Graphical DGS cable resolved outside the consumer "
                            f"interface: {graphical_signal.ID}"
                        )
                    else:
                        connections.append(
                            GraphicConnectionInstruction(
                                consumer_node_id=consumer_node_id,
                                consumer_input_name=consumer_input_names[
                                    consumer_runtime_index
                                ],
                                source_kind="root_input",
                                consumer_input_index=consumer_runtime_index,
                                source_root_name=source_root_name,
                            )
                        )
                        connected_consumer_inputs.add(consumer_key)
            else:
                pass
        else:
            pass

    # Resolve routes without concrete endpoints through deterministic aliases.
    consumer_node_id: str
    for consumer_node_id in child_node_ids:
        input_index: int
        input_name: str
        for input_index, input_name in enumerate(
                child_input_specs.get(consumer_node_id, list()),
        ):
            fallback_consumer_key: Tuple[str, int] = (
                consumer_node_id,
                input_index,
            )
            if (
                    fallback_consumer_key in connected_consumer_inputs
                    or fallback_consumer_key in explicit_consumer_inputs_seen
            ):
                pass
            else:
                input_aliases: Set[str] = alias_map.get(
                    input_name,
                    {input_name},
                )
                candidates: List[Tuple[int, int, str, str]] = list()

                producer_node_id: str
                output_name: str
                _out_var: Var
                for producer_node_id, output_name, _out_var in producer_entries:
                    if producer_node_id == consumer_node_id:
                        pass
                    elif len(input_aliases & alias_map.get(output_name, {output_name})) == 0:
                        pass
                    else:
                        distance: int = _graph_distance(
                            adjacency,
                            consumer_node_id,
                            producer_node_id,
                        )
                        exact_score: int = 0 if output_name == input_name else 1
                        candidates.append((exact_score, distance, producer_node_id, output_name))

                if len(candidates) > 0:
                    candidates.sort()
                    best: Tuple[int, int, str, str] = candidates[0]
                    if len(candidates) > 1:
                        second_best: Tuple[int, int, str, str] = candidates[1]
                        if (
                                best[0] == second_best[0]
                                and best[1] == second_best[1]
                        ):
                            raise ValueError(
                                "Graphical DGS input has ambiguous producers: "
                                f"{input_name}"
                            )
                        else:
                            pass
                    else:
                        pass
                    connections.append(
                        GraphicConnectionInstruction(
                            consumer_node_id=consumer_node_id,
                            consumer_input_name=input_name,
                            source_kind="block_output",
                            consumer_input_index=input_index,
                            source_node_id=best[2],
                            source_output_name=best[3],
                            source_output_index=child_output_specs.get(best[2], list()).index(best[3]),
                        )
                    )
                else:
                    root_candidates: List[str] = list()
                    root_name: str
                    for root_name in root_signal_vars.keys():
                        root_aliases: Set[str] = alias_map.get(
                            root_name,
                            {root_name},
                        )
                        if len(root_aliases & input_aliases) > 0:
                            root_candidates.append(root_name)
                        else:
                            pass
                    if len(root_candidates) > 0:
                        exact_root_candidates: List[str] = list()
                        root_candidate_name: str
                        for root_candidate_name in root_candidates:
                            if root_candidate_name == input_name:
                                exact_root_candidates.append(root_candidate_name)
                            else:
                                pass
                        selected_root_candidate: str
                        if len(exact_root_candidates) == 1:
                            selected_root_candidate = exact_root_candidates[0]
                        else:
                            if len(root_candidates) == 1:
                                selected_root_candidate = root_candidates[0]
                            else:
                                raise ValueError(
                                    "Graphical DGS input has ambiguous root "
                                    f"aliases: {input_name}"
                                )
                        connections.append(
                            GraphicConnectionInstruction(
                                consumer_node_id=consumer_node_id,
                                consumer_input_name=input_name,
                                source_kind="root_input",
                                consumer_input_index=input_index,
                                source_root_name=selected_root_candidate,
                            )
                        )
                    else:
                        pass

    resolved_outputs: List[Var] = list()
    root_runtime_output_index: int
    output_var: Var
    for root_runtime_output_index, output_var in enumerate(
            root_runtime_block.out_vars,
    ):
        root_output_name: str = output_var.name
        explicit_output_source: Tuple[str, int] | None = (
            explicit_root_output_sources.get(
                root_runtime_output_index,
                None,
            )
        )
        if explicit_output_source is not None:
            explicit_output_block: Block = child_blocks[
                explicit_output_source[0]
            ]
            if explicit_output_source[1] >= len(explicit_output_block.out_vars):
                raise ValueError(
                    "Graphical DGS root output resolved outside the source "
                    f"block interface: {root_output_name}"
                )
            else:
                resolved_outputs.append(
                    explicit_output_block.out_vars[explicit_output_source[1]]
                )
        else:
            output_aliases: Set[str] = alias_map.get(
                root_output_name,
                {root_output_name},
            )
            output_candidates: List[
                Tuple[int, int, str, str, Var]
            ] = list()
            output_producer_node_id: str
            output_producer_name: str
            output_producer_var: Var
            for (
                    output_producer_node_id,
                    output_producer_name,
                    output_producer_var,
            ) in producer_entries:
                if len(
                        output_aliases
                        & alias_map.get(
                            output_producer_name,
                            {output_producer_name},
                        )
                ) == 0:
                    pass
                else:
                    output_distance: int = _graph_distance(
                        adjacency,
                        output_producer_node_id,
                        selected_block.blkdef.ID,
                    )
                    output_exact_score: int = (
                        0 if output_producer_name == root_output_name else 1
                    )
                    output_candidates.append(
                        (
                            output_exact_score,
                            output_distance,
                            output_producer_node_id,
                            output_producer_name,
                            output_producer_var,
                        )
                    )

            if len(output_candidates) > 0:
                output_candidates.sort()
                if len(output_candidates) > 1:
                    best_output: Tuple[
                        int,
                        int,
                        str,
                        str,
                        Var,
                    ] = output_candidates[0]
                    second_output: Tuple[
                        int,
                        int,
                        str,
                        str,
                        Var,
                    ] = output_candidates[1]
                    if (
                            best_output[0] == second_output[0]
                            and best_output[1] == second_output[1]
                    ):
                        raise ValueError(
                            "Graphical DGS macro output has ambiguous producers: "
                            f"{root_output_name}"
                        )
                    else:
                        pass
                else:
                    pass
                resolved_outputs.append(output_candidates[0][4])
            else:
                root_output_has_explicit_semantics: bool = (
                    root_output_name in selected_block.algebraic_rhs
                    or root_output_name in selected_block.state_rhs
                )
                if root_output_has_explicit_semantics:
                    resolved_outputs.append(output_var)
                else:
                    raise ValueError(
                        "Graphical DGS macro output has no producer or explicit "
                        f"equation: {root_output_name}"
                    )

    return connections, resolved_outputs


def _blk_sum_slot_raw_mode(blk_sum: BlkSum, slot: int) -> int:
    if slot == 0:
        return int(blk_sum.iInput0)
    if slot == 1:
        return int(blk_sum.iInput1)
    if slot == 2:
        return int(blk_sum.iInput2)
    if slot == 3:
        return int(blk_sum.iInput3)
    return 2


def get_blk_sum_slot_raw_mode(blk_sum: BlkSum, slot: int) -> int:
    """
    Return the raw sign/mode code stored in a BlkSum input slot.

    :param blk_sum: DGS sum block.
    :param slot: Input slot index.
    :return: Raw DGS slot mode.
    """
    return _blk_sum_slot_raw_mode(blk_sum, slot)


def _blk_sum_slot_active_mode(blk_sum: BlkSum, slot: int) -> int:
    if slot == 0:
        return int(blk_sum.iInput0_act)
    if slot == 1:
        return int(blk_sum.iInput1_act)
    if slot == 2:
        return int(blk_sum.iInput2_act)
    if slot == 3:
        return int(blk_sum.iInput3_act)
    return 2


def get_blk_sum_slot_active_mode(blk_sum: BlkSum, slot: int) -> int:
    """
    Return the active sign/mode code stored in a BlkSum input slot.

    :param blk_sum: DGS sum block.
    :param slot: Input slot index.
    :return: Active DGS slot mode.
    """
    return _blk_sum_slot_active_mode(blk_sum, slot)


def _blk_sum_slot_mode(blk_sum: BlkSum, slot: int) -> int:
    active_mode = _blk_sum_slot_active_mode(blk_sum, slot)
    if active_mode in {0, 1, 2}:
        return active_mode
    return _blk_sum_slot_raw_mode(blk_sum, slot)


def _blk_sum_signal_specs(
    blk_sum: BlkSum,
    circuit: DgsCircuit,
) -> Tuple[List[Tuple[str, float]], List[str]]:
    incoming_by_slot: Dict[int, str] = dict()
    outgoing_signals: List[str] = list()

    for sig in circuit.blksigs:
        clean = _normalize_graph_signal_name(sig.loc_name)
        if clean == '':
            pass
        else:
            if sig.pnodto == blk_sum.ID:
                incoming_by_slot[int(sig.inodto)] = clean
            else:
                pass
            if sig.pnodfrom == blk_sum.ID:
                outgoing_signals.append(clean)
            else:
                pass

    input_terms: List[Tuple[str, float]] = list()
    for slot in range(4):
        sig_name = incoming_by_slot.get(slot, None)
        if sig_name is None:
            pass
        else:
            mode = _blk_sum_slot_mode(blk_sum, slot)
            if mode == 2:
                pass
            else:
                coeff = 1.0 if mode == 0 else -1.0
                input_terms.append((sig_name, coeff))

    outputs: List[str] = list()
    for sig_name in outgoing_signals:
        if sig_name not in outputs:
            outputs.append(sig_name)

    return input_terms, outputs


def get_blk_sum_signal_specs(
    blk_sum: BlkSum,
    circuit: DgsCircuit,
) -> Tuple[List[Tuple[str, float]], List[str]]:
    """
    Return the effective input terms and outputs of a DGS sum block.

    :param blk_sum: DGS sum block.
    :param circuit: Parsed DGS circuit.
    :return: Tuple with signed input terms and output signal names.
    """
    return _blk_sum_signal_specs(blk_sum, circuit)


def _build_sum_block_from_graphic_node(blk_sum: BlkSum, circuit: DgsCircuit) -> Tuple[Block, List[str], List[str]]:
    input_terms, outputs = _blk_sum_signal_specs(blk_sum, circuit)

    if len(outputs) == 0:
        output_name = _safe_name(blk_sum.loc_name if blk_sum.loc_name != '' else blk_sum.ID)
        outputs = [output_name]

    out_var = Var(name=outputs[0])
    in_vars: List[Var] = list()
    rhs: Expr = Const(0.0)
    input_names: List[str] = list()

    for input_name, coeff in input_terms:
        in_var = Var(name=input_name)
        in_vars.append(in_var)
        input_names.append(input_name)
        rhs = rhs + (Const(coeff) * in_var)

    block = Block(
        algebraic_eqs=[out_var - rhs],
        algebraic_vars=[out_var],
        in_vars=in_vars,
        out_vars=[out_var],
        name=blk_sum.loc_name if blk_sum.loc_name != '' else 'Sum',
    )
    return block, input_names, outputs


def _build_sum_runtime_input_index_by_connector(
        blk_sum: BlkSum,
        circuit: DgsCircuit,
) -> Dict[Tuple[DgsGraphicalConnectorKind, int], int]:
    """
    Map sparse native summation ports to compact runtime inputs.

    PowerFactory retains four raw slots and can disable any of them. The
    runtime block omits disabled slots, so the connector map must compact the
    remaining indices in the same order as the summation expression.

    :param blk_sum: Native graphical summation node.
    :param circuit: Parsed DGS circuit containing its cables.
    :return: Runtime indices keyed by ordinary connector and raw slot.
    """
    incoming_slots: Set[int] = set()
    signal: BlkSig

    # Record only concrete incoming cables owned by this summation node.
    for signal in circuit.blksigs:
        if (
                _normalize_dgs_pointer_id(signal.pnodto) == str(blk_sum.ID)
                and _normalize_graph_signal_name(signal.loc_name) != ''
        ):
            incoming_slots.add(int(signal.inodto))
        else:
            pass

    input_index_by_connector: Dict[
        Tuple[DgsGraphicalConnectorKind, int],
        int,
    ] = dict()
    runtime_input_index: int = 0
    raw_slot_index: int

    # Compact active raw slots in the same deterministic order as the block.
    for raw_slot_index in range(4):
        slot_is_executable: bool = (
            raw_slot_index in incoming_slots
            and _blk_sum_slot_mode(blk_sum, raw_slot_index) != 2
        )
        if slot_is_executable:
            input_index_by_connector[
                (DgsGraphicalConnectorKind.Input, raw_slot_index)
            ] = runtime_input_index
            runtime_input_index += 1
        else:
            pass
    return input_index_by_connector


def _collect_graphical_operator_signal_specs(
        node: BlkMul | BlkDiv,
        circuit: DgsCircuit,
) -> Tuple[List[Tuple[int, str]], List[Tuple[int, str]]]:
    """
    Collect ordered inputs and outputs for one native arithmetic operator.

    Native operator records do not declare their own interface. PowerFactory
    stores the executable port indices and signal names in ``BlkSig`` rows.

    :param node: Parsed multiplication or division record.
    :param circuit: Parsed DGS circuit containing the signal rows.
    :return: Ordered input and output ``(port, signal name)`` pairs.
    """
    incoming_by_index: Dict[int, str] = dict()
    outgoing_by_index: Dict[int, str] = dict()
    node_id: str = str(node.ID)
    signal: BlkSig
    for signal in circuit.blksigs:
        signal_name: str = _normalize_graph_signal_name(signal.loc_name)
        source_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(signal.iconfrom),
                endpoint_node=node,
                is_source_endpoint=True,
            )
        )
        target_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(signal.iconto),
                endpoint_node=node,
                is_source_endpoint=False,
            )
        )
        if (
                _normalize_dgs_pointer_id(signal.pnodto) == node_id
                and target_kind == DgsGraphicalConnectorKind.Input
                and signal_name != ''
        ):
            incoming_by_index[int(signal.inodto)] = signal_name
        else:
            pass
        if (
                _normalize_dgs_pointer_id(signal.pnodfrom) == node_id
                and source_kind == DgsGraphicalConnectorKind.Output
                and signal_name != ''
        ):
            outgoing_by_index[int(signal.inodfrom)] = signal_name
        else:
            pass

    incoming_signals: List[Tuple[int, str]] = sorted(incoming_by_index.items())
    outgoing_signals: List[Tuple[int, str]] = sorted(outgoing_by_index.items())
    return incoming_signals, outgoing_signals


def build_graphical_arithmetic_block(
        node: BlkMul | BlkDiv,
        circuit: DgsCircuit,
) -> Tuple[
    Block,
    List[str],
    List[str],
    Dict[Tuple[DgsGraphicalConnectorKind, int], int],
]:
    """
    Materialize one native multiplication or left-associative division node.

    Multiplication consumes every ordered input. Division treats port zero as
    the numerator and divides successively by the remaining input ports,
    matching PowerFactory graphical-block semantics.

    :param node: Parsed native arithmetic record.
    :param circuit: Parsed DGS circuit containing its signal rows.
    :return: Symbolic block, ordered interface names and exact input-port map.
    """
    incoming_signals: List[Tuple[int, str]]
    outgoing_signals: List[Tuple[int, str]]
    incoming_signals, outgoing_signals = _collect_graphical_operator_signal_specs(
        node=node,
        circuit=circuit,
    )
    input_vars: List[Var] = list()
    input_names: List[str] = list()
    input_index_by_connector: Dict[
        Tuple[DgsGraphicalConnectorKind, int],
        int,
    ] = dict()
    input_port_index: int
    input_name: str

    # Compact runtime inputs while retaining each raw graphical port index.
    for input_port_index, input_name in incoming_signals:
        runtime_input_index: int = len(input_vars)
        input_vars.append(Var(name=input_name))
        input_names.append(input_name)
        input_index_by_connector[
            (DgsGraphicalConnectorKind.Input, input_port_index)
        ] = runtime_input_index

    # Build the deterministic arithmetic expression in exported port order.
    if len(input_vars) == 0:
        operator_rhs: Expr = Const(0.0)
    else:
        operator_rhs = input_vars[0]
        following_input: Var
        for following_input in input_vars[1:]:
            if isinstance(node, BlkMul):
                operator_rhs = operator_rhs * following_input
            else:
                operator_rhs = operator_rhs / following_input

    output_names: List[str] = list()
    output_vars: List[Var] = list()
    _output_port_index: int
    output_name: str

    # Multiple graphical output dots expose the same arithmetic result.
    for _output_port_index, output_name in outgoing_signals:
        if output_name in output_names:
            pass
        else:
            output_names.append(output_name)
            output_vars.append(Var(name=output_name))
    if len(output_vars) == 0:
        fallback_output_name: str = _safe_name(
            node.loc_name if node.loc_name != '' else node.ID
        )
        output_names.append(fallback_output_name)
        output_vars.append(Var(name=fallback_output_name))
    else:
        pass

    algebraic_equations: List[Expr] = list()
    post_init_seed_eqs: Dict[Var, Expr] = dict()
    output_var: Var

    # Seed and steady-state equations must share the exact same expression.
    for output_var in output_vars:
        algebraic_equations.append(output_var - operator_rhs)
        post_init_seed_eqs[output_var] = operator_rhs

    if node.loc_name != '':
        operator_name: str = node.loc_name
    elif isinstance(node, BlkMul):
        operator_name = 'Multiplication'
    else:
        operator_name = 'Division'
    block: Block = Block(
        algebraic_eqs=algebraic_equations,
        algebraic_vars=output_vars,
        in_vars=input_vars,
        out_vars=output_vars,
        post_init_seed_eqs=post_init_seed_eqs,
        name=operator_name,
    )
    return block, input_names, output_names, input_index_by_connector


def build_graphical_switch_block(
        node: BlkSwt,
        circuit: DgsCircuit,
) -> Tuple[
    Block,
    List[str],
    List[str],
    Dict[Tuple[DgsGraphicalConnectorKind, int], int],
]:
    """
    Materialize one native two-input graphical switch.

    A control value up to ``0.5`` retains the default input; a larger value
    selects the changed input. ``iNeg`` swaps those two positions.

    :param node: Parsed native switch record.
    :param circuit: Parsed DGS circuit containing its signal rows.
    :return: Symbolic block, ordered interface names and exact input-port map.
    """
    data_inputs_by_port: Dict[int, str] = dict()
    control_inputs_by_port: Dict[
        Tuple[DgsGraphicalConnectorKind, int],
        str,
    ] = dict()
    outputs_by_port: Dict[int, str] = dict()
    signal: BlkSig

    # Classify every cable by structural endpoint and connector category.
    for signal in circuit.blksigs:
        signal_name: str = _normalize_graph_signal_name(signal.loc_name)
        source_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(signal.iconfrom),
                endpoint_node=node,
                is_source_endpoint=True,
            )
        )
        target_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(signal.iconto),
                endpoint_node=node,
                is_source_endpoint=False,
            )
        )
        if (
                _normalize_dgs_pointer_id(signal.pnodto) == str(node.ID)
                and signal_name != ''
        ):
            if target_kind == DgsGraphicalConnectorKind.Input:
                data_inputs_by_port[int(signal.inodto)] = signal_name
            elif target_kind in {
                DgsGraphicalConnectorKind.LowerLimitInput,
                DgsGraphicalConnectorKind.UpperLimitInput,
            }:
                control_inputs_by_port[
                    (target_kind, int(signal.inodto))
                ] = signal_name
            else:
                pass
        else:
            pass
        if (
                _normalize_dgs_pointer_id(signal.pnodfrom) == str(node.ID)
                and source_kind == DgsGraphicalConnectorKind.Output
                and signal_name != ''
        ):
            outputs_by_port[int(signal.inodfrom)] = signal_name
        else:
            pass

    ordered_data_inputs: List[Tuple[int, str]] = sorted(data_inputs_by_port.items())
    if len(control_inputs_by_port) > 0:
        ordered_control_inputs: List[
            Tuple[Tuple[DgsGraphicalConnectorKind, int], str]
        ] = sorted(control_inputs_by_port.items())
        control_connector: Tuple[DgsGraphicalConnectorKind, int] = (
            ordered_control_inputs[0][0]
        )
        control_name: str = ordered_control_inputs[0][1]
    elif len(ordered_data_inputs) > 2:
        control_port: int
        control_port, control_name = ordered_data_inputs.pop()
        control_connector = (DgsGraphicalConnectorKind.Input, control_port)
    else:
        control_name = ''
        control_connector = (DgsGraphicalConnectorKind.UpperLimitInput, 0)

    input_vars: List[Var] = list()
    data_input_vars: List[Var] = list()
    input_names: List[str] = list()
    input_index_by_connector: Dict[
        Tuple[DgsGraphicalConnectorKind, int],
        int,
    ] = dict()
    data_port: int
    data_name: str

    # Preserve the raw data-pin identity while compacting runtime inputs.
    for data_port, data_name in ordered_data_inputs[:2]:
        input_index_by_connector[
            (DgsGraphicalConnectorKind.Input, data_port)
        ] = len(input_vars)
        data_input_var: Var = Var(name=data_name)
        input_vars.append(data_input_var)
        data_input_vars.append(data_input_var)
        input_names.append(data_name)
    if control_name == '':
        control_expression: Expr = Const(0.0)
    else:
        input_index_by_connector[control_connector] = len(input_vars)
        control_var: Var = Var(name=control_name)
        input_vars.append(control_var)
        input_names.append(control_name)
        control_expression = control_var

    # Missing data pins remain deterministic instead of creating a partial block.
    if len(data_input_vars) == 0:
        default_expression: Expr = Const(0.0)
        changed_expression: Expr = Const(0.0)
    else:
        default_expression = data_input_vars[0]
        if len(data_input_vars) >= 2:
            changed_expression = data_input_vars[1]
        else:
            changed_expression = default_expression
    # Inversion changes the default position without changing control polarity.
    if int(node.iNeg) == 0:
        pass
    else:
        swapped_expression: Expr = default_expression
        default_expression = changed_expression
        changed_expression = swapped_expression

    switched_position: Expr = heaviside(control_expression - Const(0.5))
    switch_rhs: Expr = (
        (Const(1.0) - switched_position) * default_expression
        + switched_position * changed_expression
    )
    ordered_outputs: List[Tuple[int, str]] = sorted(outputs_by_port.items())
    if len(ordered_outputs) == 0:
        output_name: str = _safe_name(
            node.loc_name if node.loc_name != '' else node.ID
        )
    else:
        output_name = ordered_outputs[0][1]
    output_var: Var = Var(name=output_name)
    block_name: str = node.loc_name if node.loc_name != '' else 'Switch'
    block: Block = Block(
        algebraic_eqs=list([output_var - switch_rhs]),
        algebraic_vars=list([output_var]),
        in_vars=input_vars,
        out_vars=list([output_var]),
        post_init_seed_eqs=dict([(output_var, switch_rhs)]),
        name=block_name,
    )
    return block, input_names, list([output_name]), input_index_by_connector


def _selected_block_signal_universe(parsed_block: ParsedDgsBlockDefinition) -> set[str]:
    """
    Return the relevant signal universe of a selected composite block.

    :param parsed_block: Parsed composite block definition.
    :return: Signal-name universe.
    """
    return set(parsed_block.blkdef.inputs) | set(parsed_block.blkdef.outputs) | set(parsed_block.blkdef.internals) | set(parsed_block.blkdef.states)


def _rescue_graphic_internal_nodes(
    selected_block: ParsedDgsBlockDefinition,
    node_by_id: dict[str, object],
    node_signals: dict[str, set[str]],
    explicit_component: set[str],
) -> set[str]:
    """
    Rescue disconnected graphical nodes whose signal labels belong to the selected composite universe.

    :param selected_block: Selected parsed block.
    :param node_by_id: Graphic-node index.
    :param node_signals: Signal labels per node.
    :param explicit_component: Nodes already obtained from explicit BlkSig connectivity.
    :return: Additional rescued node ids.
    """
    universe = _selected_block_signal_universe(selected_block)
    rescued: set[str] = set()

    for node_id, node in node_by_id.items():
        if node_id in explicit_component:
            pass
        elif not isinstance(
                node,
                (BlkRef, BlkFrom, BlkGoto, BlkSum, BlkDiv, BlkMul, BlkSwt),
        ):
            pass
        else:
            sigs = node_signals.get(node_id, set())
            if sigs & universe:
                rescued.add(node_id)
            else:
                pass

    return rescued

def extract_elmcomp_direct_instances(
    circuit: DgsCircuit,
    root_element: ElmComp,
) -> list[ElmCompInstanceEntry]:
    """
    Extract direct root instances from ElmComp pblk/pelm relations.

    Unpaired rows remain in the result as source evidence. Consumers must use
    :func:`get_unambiguous_elmcomp_direct_instances` before materialization.

    :param circuit: Parsed DGS circuit.
    :param root_element: Root ElmComp.
    :return: Direct instance list, including incomplete source relations.
    """
    element_by_id: dict[str, object] = _build_dgs_element_index(circuit)
    blkdef_by_id: dict[str, BlkDef] = _build_blkdef_index(circuit)

    entries: list[ElmCompInstanceEntry] = list()

    len_pblk: int = len(root_element.pblk)
    len_pelm: int = len(root_element.pelm)

    if len_pblk >= len_pelm:
        n_pairs: int = len_pblk
    else:
        n_pairs = len_pelm

    idx: int
    for idx in range(n_pairs):
        if idx < len_pblk:
            slot_id: str | None = root_element.pblk[idx]
        else:
            slot_id = None
        if idx < len_pelm:
            element_id: str | None = root_element.pelm[idx]
        else:
            element_id = None

        slot_name: str | None
        element_name: str | None
        element_kind: str | None
        element_outserv: int | None
        type_id: str | None
        type_name: str | None
        parameter_values: Dict[
            str,
            float | int | bool | str | complex | None,
        ]
        slot_element: str | None
        slot_filter: str | None
        slot_outputs: List[str]
        slot_inputs: List[str]
        slot_reference_is_resolved: bool
        element_reference_is_resolved: bool

        if slot_id is not None:
            slot_obj: object | None = element_by_id.get(slot_id, None)
            if isinstance(slot_obj, BlkSlot):
                slot_name = slot_obj.loc_name
                slot_element = slot_obj.element
                slot_filter = slot_obj.filtmod
                slot_outputs = slot_obj.outputs
                slot_inputs = slot_obj.inputs
                slot_reference_is_resolved = True
            elif isinstance(slot_obj, DGSElement):
                slot_name = slot_obj.loc_name
                slot_element = None
                slot_filter = None
                slot_outputs = list()
                slot_inputs = list()
                slot_reference_is_resolved = False
            else:
                slot_name = None
                slot_element = None
                slot_filter = None
                slot_outputs = list()
                slot_inputs = list()
                slot_reference_is_resolved = False
        else:
            slot_name = None
            slot_element = None
            slot_filter = None
            slot_outputs = list()
            slot_inputs = list()
            slot_reference_is_resolved = False

        if element_id is not None:
            element_obj: object | None = element_by_id.get(element_id, None)
            if isinstance(element_obj, ElmDsl):
                element_reference_is_resolved = True
                element_name = element_obj.loc_name
                element_kind = "ElmDsl"
                element_outserv = element_obj.outserv
                if element_obj.typ_id != "":
                    type_id = element_obj.typ_id
                else:
                    type_id = None
                parameter_values = element_obj.get_parameter_map()
            elif isinstance(element_obj, ElmComp):
                element_reference_is_resolved = True
                element_name = element_obj.loc_name
                element_kind = "ElmComp"
                element_outserv = element_obj.outserv
                if element_obj.typ_id != "":
                    type_id = element_obj.typ_id
                else:
                    type_id = None
                parameter_values = dict()
            elif isinstance(element_obj, DGSElement):
                # Physical pElm targets are provenance, not dynamic BlkDefs.
                element_reference_is_resolved = True
                element_name = element_obj.loc_name
                element_kind = element_obj.element_type
                element_outserv = None
                type_id = None
                parameter_values = dict()
            else:
                element_reference_is_resolved = False
                element_name = None
                element_kind = None
                element_outserv = None
                type_id = None
                parameter_values = dict()
        else:
            element_reference_is_resolved = False
            element_name = None
            element_kind = None
            element_outserv = None
            type_id = None
            parameter_values = dict()

        if type_id is not None:
            blkdef_obj: BlkDef | None = blkdef_by_id.get(type_id, None)
            if blkdef_obj is not None:
                type_name = blkdef_obj.loc_name
            else:
                type_name = None
        else:
            type_name = None

        if slot_name is None:
            if type_name is not None:
                slot_name = type_name
            else:
                slot_name = element_name
        else:
            pass

        entry: ElmCompInstanceEntry = ElmCompInstanceEntry(
            slot_id=slot_id,
            slot_name=slot_name,
            element_id=element_id,
            element_name=element_name,
            element_kind=element_kind,
            element_outserv=element_outserv,
            type_id=type_id,
            type_name=type_name,
            parameter_values=parameter_values,
            slot_index=idx,
            slot_element=slot_element,
            slot_filter=slot_filter,
            slot_outputs=slot_outputs,
            slot_inputs=slot_inputs,
            slot_reference_is_resolved=slot_reference_is_resolved,
            element_reference_is_resolved=element_reference_is_resolved,
        )

        entries.append(entry)

    return entries


def get_unique_elmcomp_slot_entries(
        entries: Iterable[ElmCompInstanceEntry],
) -> List[ElmCompInstanceEntry]:
    """Select relations whose pblk resolves to one unique BlkSlot.

    This slot-only envelope supports native equipment such as ``ElmPhi`` whose
    owned object can be resolved from its exact DGS topology even when ``pelm``
    is empty. It never accepts a missing, unresolved or repeated ``pblk``.

    :param entries: Extracted direct relations, including source gaps.
    :return: Relations whose resolved slot identifier occurs exactly once.
    """
    entry_list: List[ElmCompInstanceEntry] = list(entries)
    slot_occurrences: Dict[str, int] = dict()
    entry: ElmCompInstanceEntry
    for entry in entry_list:
        if entry.slot_id is None:
            pass
        else:
            previous_count: int | None = slot_occurrences.get(
                entry.slot_id,
                None,
            )
            if previous_count is None:
                slot_occurrences[entry.slot_id] = 1
            else:
                slot_occurrences[entry.slot_id] = previous_count + 1

    selected_entries: List[ElmCompInstanceEntry] = list()
    for entry in entry_list:
        if (
                entry.slot_id is None
                or not entry.slot_reference_is_resolved
        ):
            pass
        else:
            slot_count: int | None = slot_occurrences.get(entry.slot_id, None)
            if slot_count == 1:
                selected_entries.append(entry)
            else:
                pass

    return selected_entries


def get_unambiguous_elmcomp_direct_instances(
        entries: Iterable[ElmCompInstanceEntry],
) -> List[ElmCompInstanceEntry]:
    """Select complete pblk/pelm relations with one unique slot identifier.

    Incomplete relations remain available in the source catalogue, but cannot
    become executable children or provide runtime parameter values.

    :param entries: Extracted direct relations, including source gaps.
    :return: Complete relations whose slot identifier occurs exactly once.
    """
    unique_slot_entries: List[ElmCompInstanceEntry] = (
        get_unique_elmcomp_slot_entries(entries=entries)
    )
    selected_entries: List[ElmCompInstanceEntry] = list()
    entry: ElmCompInstanceEntry
    for entry in unique_slot_entries:
        if (
                entry.element_id is None
                or not entry.element_reference_is_resolved
        ):
            pass
        else:
            selected_entries.append(entry)

    return selected_entries


def select_block_instance_from_root(
    circuit: DgsCircuit,
    result: DgsRootBlockResult,
    slot_name: str,
    slot_dgs_id: str | None = None,
) -> DgsBlockInstanceSelection | None:
    """
    Resolve a parsed block from the explicit root ElmComp slot mapping.

    :param circuit: Parsed DGS circuit.
    :param result: Root block parsing result.
    :param slot_name: Slot name in the root ElmComp.
    :param slot_dgs_id: Optional exact ``BlkSlot`` identifier.
    :return: Unique block selection, or ``None`` when absent or ambiguous.
    """
    entries: list[ElmCompInstanceEntry] = (
        get_unambiguous_elmcomp_direct_instances(
            entries=extract_elmcomp_direct_instances(
                circuit,
                result.root_element,
            )
        )
    )
    matching_entries: List[ElmCompInstanceEntry] = list()
    entry: ElmCompInstanceEntry

    for entry in entries:
        if slot_dgs_id is not None:
            if entry.slot_id == slot_dgs_id:
                matching_entries.append(entry)
            else:
                pass
        else:
            if entry.slot_name == slot_name or entry.type_name == slot_name:
                matching_entries.append(entry)
            else:
                pass

    if len(matching_entries) == 1:
        selected_entry: ElmCompInstanceEntry = matching_entries[0]
    else:
        return None

    if selected_entry.type_id is None:
        return None
    else:
        pass

    parsed_block: ParsedDgsBlockDefinition | None = result.parsed_blocks.get(selected_entry.type_id, None)

    if parsed_block is None:
        return None
    else:
        selection = DgsBlockInstanceSelection(
            instance_entry=selected_entry,
            parsed_block=parsed_block,
        )
        return selection



def _reverse_dependency_graph(graph: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    reverse_graph: Dict[str, Set[str]] = dict()
    node_id: str
    for node_id in graph.keys():
        reverse_graph[node_id] = set()
    for src, dsts in graph.items():
        for dst in dsts:
            _append_to_string_set_map(reverse_graph, dst, src)
    return reverse_graph


def _closure_from_node(graph: Dict[str, Set[str]], start_node: str) -> Set[str]:
    visited: Set[str] = set()
    frontier: List[str] = [start_node]

    while frontier:
        node = frontier.pop()
        if node in visited:
            pass
        else:
            visited.add(node)
            for nxt in graph.get(node, set()):
                if nxt not in visited:
                    frontier.append(nxt)
                else:
                    pass

    return visited


def _select_named_block(
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
    block_name: str,
    block_id: str | None = None,
) -> Tuple[str, ParsedDgsBlockDefinition]:
    """Select one block by exact identifier or unique display name.

    :param parsed_blocks: Parsed block definitions keyed by DGS identifier.
    :param block_name: Expected block display name.
    :param block_id: Optional exact DGS block identifier.
    :return: Exact block identifier and parsed block definition.
    """
    if block_id is not None:
        selected: ParsedDgsBlockDefinition | None = parsed_blocks.get(
            block_id,
            None,
        )
        if selected is None:
            raise ValueError(f"Block id '{block_id}' not found")
        else:
            pass
        if selected.blkdef.loc_name != block_name:
            raise ValueError(
                f"Block id '{block_id}' does not match block name "
                f"'{block_name}'"
            )
        else:
            pass
        return block_id, selected
    else:
        candidates: List[Tuple[str, ParsedDgsBlockDefinition]] = [
            (candidate_id, parsed_block)
            for candidate_id, parsed_block in parsed_blocks.items()
            if parsed_block.blkdef.loc_name == block_name
        ]
        if len(candidates) == 0:
            raise ValueError(f"Block name '{block_name}' not found")
        else:
            pass
        if len(candidates) != 1:
            raise ValueError(
                f"Several blocks use name '{block_name}'; provide an exact "
                "block identifier"
            )
        else:
            pass
        return candidates[0]


def extract_named_block_subgraph(
    result: DgsRootBlockResult,
    block_name: str,
    block_id: str | None = None,
    mode: BlockScopeMode = BlockScopeMode.InternalOnly) -> DgsBlockSubgraphResult:

    selected_id, selected_block = _select_named_block(result.parsed_blocks, block_name, block_id)
    reverse_graph: Dict[str, Set[str]] = _reverse_dependency_graph(result.dependency_graph)

    node_ids: Set[str] = set()
    node_ids.add(selected_id)

    upstream: Dict[str, Set[str]] = dict()
    downstream: Dict[str, Set[str]] = dict()

    if mode == BlockScopeMode.DownstreamOnly:
        downstream_nodes: Set[str] = _closure_from_node(result.dependency_graph, selected_id)
        node_ids |= downstream_nodes
    elif mode == BlockScopeMode.UpstreamOnly:
        upstream_nodes: Set[str] = _closure_from_node(reverse_graph, selected_id)
        node_ids |= upstream_nodes
    elif mode == BlockScopeMode.FullDependency:
        upstream_nodes = _closure_from_node(reverse_graph, selected_id)
        downstream_nodes = _closure_from_node(result.dependency_graph, selected_id)
        node_ids |= upstream_nodes
        node_ids |= downstream_nodes
    else:
        pass

    sub_children: List[Block] = list()
    shared_signals: Dict[str, Var] = dict()
    ordered_node_ids: List[tuple[str, str]] = list()
    node_id: str
    for node_id in node_ids:
        ordered_node_ids.append((result.parsed_blocks[node_id].blkdef.loc_name, node_id))
    ordered_node_ids.sort()

    _node_label: str
    for _node_label, node_id in ordered_node_ids:
        sub_children.append(_build_block_from_parsed(result.parsed_blocks[node_id], shared_signals))

    for node_id in node_ids:
        if mode == BlockScopeMode.DownstreamOnly:
            downstream[node_id] = _build_filtered_neighbor_set(result.dependency_graph, node_id, node_ids)
        elif mode == BlockScopeMode.UpstreamOnly:
            upstream[node_id] = _build_reverse_neighbor_subset(reverse_graph, node_id, node_ids)
        elif mode == BlockScopeMode.FullDependency:
            upstream[node_id] = _build_reverse_neighbor_subset(reverse_graph, node_id, node_ids)
            downstream[node_id] = _build_filtered_neighbor_set(result.dependency_graph, node_id, node_ids)
        else:
            pass

    selected_runtime_block = _build_block_from_parsed(selected_block, shared_signals)

    if mode == BlockScopeMode.InternalOnly:
        view_block = selected_runtime_block
        view_block.name = selected_block.blkdef.loc_name
    else:
        view_block_name = f"{selected_block.blkdef.loc_name}_{str(mode)}"
        view_block = Block(
            name=view_block_name,
            children=sub_children,
            in_vars=selected_runtime_block.in_vars,
            out_vars=selected_runtime_block.out_vars,
            algebraic_vars=selected_runtime_block.algebraic_vars,
        )

    subgraph = _filter_graph_edges_to_node_ids(result.dependency_graph, node_ids)

    return DgsBlockSubgraphResult(
        selected_block=selected_block,
        view_block=view_block,
        node_ids=node_ids,
        dependency_graph=subgraph,
        upstream=upstream,
        downstream=downstream,
    )

def extract_named_block_internal_only(
    result: DgsRootBlockResult,
    block_name: str,
    block_id: str | None = None,
) -> DgsBlockSubgraphResult:
    """
    Extract only the selected block without any dependency closure.

    :param result: Root block parsing result.
    :param block_name: Target block name.
    :param block_id: Optional exact block identifier.
    :return: Minimal block subgraph result.
    """
    return extract_named_block_subgraph(
        result=result,
        block_name=block_name,
        block_id=block_id,
        mode=BlockScopeMode.InternalOnly,
    )

def extract_root_slot_block_internal_only(
    dgs_path: str,
    slot_name: str,
    root_name: str | None = None,
    root_typ_id: str | None = None,
) -> DgsBlockSubgraphResult | None:
    """
    Extract the block associated to a root ElmComp slot and keep only that block.

    :param dgs_path: Source DGS path.
    :param slot_name: Root slot name.
    :param root_name: Optional root ElmComp name.
    :param root_typ_id: Optional root type identifier.
    :return: Internal-only block subgraph or None.
    """
    circuit = DgsCircuit()
    circuit.parse_dgs(dgs_path)

    result = dgs_to_root_block(dgs_path, root_name=root_name, root_typ_id=root_typ_id)
    selection: DgsBlockInstanceSelection | None = select_block_instance_from_root(
        circuit=circuit,
        result=result,
        slot_name=slot_name,
    )

    if selection is None:
        return None
    else:
        return extract_named_block_internal_only(
            result=result,
            block_name=selection.parsed_block.blkdef.loc_name,
            block_id=selection.parsed_block.blkdef.ID,
        )

def extract_root_slot_block_internal_signal_tree(
    dgs_path: str,
    slot_name: str,
    root_name: str | None = None,
    root_typ_id: str | None = None,
) -> DgsBlockSubgraphResult | None:
    """
    Extract an internal hierarchy approximation for a selected root slot using
    signal-name matching only.

    :param dgs_path: Source DGS path.
    :param slot_name: Root slot name or type name fallback.
    :param root_name: Optional root ElmComp name.
    :param root_typ_id: Optional root type identifier.
    :return: Subgraph result or None.
    """
    circuit = DgsCircuit()
    circuit.parse_dgs(dgs_path)

    result = dgs_to_root_block(dgs_path, root_name=root_name, root_typ_id=root_typ_id)
    selection: DgsBlockInstanceSelection | None = select_block_instance_from_root(
        circuit=circuit,
        result=result,
        slot_name=slot_name,
    )

    if selection is None:
        return None
    else:
        pass

    candidates: Dict[str, ParsedDgsBlockDefinition] = _collect_internal_candidate_blocks(
        selected_block=selection.parsed_block,
        parsed_blocks=result.parsed_blocks,
    )

    filtered: Dict[str, ParsedDgsBlockDefinition] = _filter_internal_candidates(
        selected_block=selection.parsed_block,
        candidates=candidates,
        min_score=2,
    )

    node_ids: Set[str] = set()
    node_ids.add(selection.parsed_block.blkdef.ID)
    node_ids |= set(filtered.keys())

    reverse_graph: Dict[str, Set[str]] = _reverse_dependency_graph(result.dependency_graph)
    upstream: Dict[str, Set[str]] = dict()
    downstream: Dict[str, Set[str]] = dict()

    for node_id in node_ids:
        upstream[node_id] = _build_reverse_neighbor_subset(reverse_graph, node_id, node_ids)
        downstream[node_id] = _build_filtered_neighbor_set(result.dependency_graph, node_id, node_ids)

    shared_signals: Dict[str, Var] = dict()
    sub_children: List[Block] = list()
    element_by_id = _build_dgs_element_index(circuit)
    selected_element_obj = element_by_id.get(selection.instance_entry.element_id or "", None)
    nested_parameter_values_by_type_id: Dict[
        str,
        Dict[str, float | int | bool | str | complex | None],
    ] = dict()
    if isinstance(selected_element_obj, ElmComp):
        nested_parameter_values_by_type_id = _parameter_values_by_type_id(extract_elmcomp_direct_instances(circuit, selected_element_obj))

    ordered_ids: List[str] = list(node_ids)
    ordered_ids.sort()

    for node_id in ordered_ids:
        parsed = result.parsed_blocks[node_id]
        parameter_values = selection.instance_entry.parameter_values if node_id == selection.parsed_block.blkdef.ID else nested_parameter_values_by_type_id.get(parsed.blkdef.ID, None)
        sub_children.append(_build_block_from_parsed(parsed, shared_signals, parameter_values=parameter_values))

    selected_runtime_block: Block = _build_block_from_parsed(
        selection.parsed_block,
        shared_signals,
        parameter_values=selection.instance_entry.parameter_values,
    )

    view_block = Block(
        name=f"{selection.parsed_block.blkdef.loc_name}_InternalSignalTree",
        children=sub_children,
        in_vars=selected_runtime_block.in_vars,
        out_vars=selected_runtime_block.out_vars,
        algebraic_vars=selected_runtime_block.algebraic_vars,
    )

    local_graph: Dict[str, Set[str]] = _filter_graph_edges_to_node_ids(result.dependency_graph, node_ids)

    return DgsBlockSubgraphResult(
        selected_block=selection.parsed_block,
        node_ids=node_ids,
        dependency_graph=local_graph,
        upstream=upstream,
        downstream=downstream,
        view_block=view_block,
    )


def _retain_referenced_structural_algebraic_vars(
        parent_block: Block,
) -> List[Var]:
    """Keep only parent algebraic variables used by executable semantics.

    A graphical macro frame declares cable labels as DGS internals. Child
    blocks own the equations and variables carried by those cables, while the
    parent retains only initialization or external-interface dependencies.
    Registering an unused cable label as a parent algebraic variable creates a
    solver degree of freedom without a physical equation.

    :param parent_block: Parsed graphical parent before its children are added.
    :return: Parent algebraic variables referenced by executable semantics.
    """
    retained_vars: List[Var] = list()
    candidate_var: Var

    # Preserve initialization and external mappings owned by the parent, but
    # discard labels whose producer-consumer edge already lives in the child
    # graph and therefore needs no second algebraic owner in the frame.
    for candidate_var in parent_block.algebraic_vars:
        if parent_block.find_var_in_block(candidate_var):
            retained_vars.append(candidate_var)
        else:
            pass

    return retained_vars


def extract_root_slot_block_graphical_tree(
    dgs_path: str,
    slot_name: str,
    root_name: str | None = None,
    root_typ_id: str | None = None,
) -> DgsGraphicTreeResult | None:
    """
    Extract the exact graphical internal tree of a root slot.

    The materialized tree includes referenced blocks, native summations,
    arithmetic division and multiplication nodes, and threshold switches
    connected through ``BlkSig`` and ``BlkFrom``/``BlkGoto`` routes.

    :param dgs_path: Source DGS path.
    :param slot_name: Root slot name or type-name fallback.
    :param root_name: Optional root ElmComp name.
    :param root_typ_id: Optional root type identifier.
    :return: Graphical tree result or None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(dgs_path)
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition] = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)
    )
    result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parsed_blocks,
        root_name=root_name,
        root_typ_id=root_typ_id,
    )
    graphical_indexes: DgsGraphicalIndexes = (
        build_dgs_graphical_indexes(circuit=circuit)
    )
    return extract_root_slot_graphical_tree_from_circuit(
        circuit=circuit,
        result=result,
        slot_name=slot_name,
        graphical_indexes=graphical_indexes,
    )


def extract_root_slot_graphical_tree_from_circuit(
    circuit: DgsCircuit,
    result: DgsRootBlockResult,
    slot_name: str,
    slot_dgs_id: str | None = None,
    graphical_indexes: DgsGraphicalIndexes | None = None,
) -> DgsGraphicTreeResult | None:
    """Extract one graphical slot from an already parsed DGS circuit.

    :param circuit: Parsed DGS circuit.
    :param result: Parsed root selection result.
    :param slot_name: Slot name or type-name fallback.
    :param slot_dgs_id: Optional exact ``BlkSlot`` identifier.
    :param graphical_indexes: Optional shared graphical indexes.
    :return: Graphical tree result or ``None`` for a non-graphical slot.
    """
    selection: DgsBlockInstanceSelection | None = select_block_instance_from_root(
        circuit=circuit,
        result=result,
        slot_name=slot_name,
        slot_dgs_id=slot_dgs_id,
    )

    if selection is None or selection.instance_entry.type_id is None:
        return None
    else:
        if selection.parsed_block.blkdef.isMacro == 0:
            return None
        else:
            pass

    resolved_graphical_indexes: DgsGraphicalIndexes
    if graphical_indexes is None:
        resolved_graphical_indexes = build_dgs_graphical_indexes(
            circuit=circuit
        )
    else:
        resolved_graphical_indexes = graphical_indexes

    adjacency: dict[str, set[str]] = resolved_graphical_indexes.adjacency
    root_node_id: str = str(selection.instance_entry.type_id)
    explicit_component: set[str] = _graphic_connected_component(adjacency, root_node_id)

    node_by_id: dict[str, object] = resolved_graphical_indexes.node_by_id
    node_signals: dict[str, set[str]] = resolved_graphical_indexes.node_signals
    if len(explicit_component) <= 1:
        node_ids: set[str] = explicit_component
    else:
        rescued_component: set[str] = _rescue_graphic_internal_nodes(
            selection.parsed_block,
            node_by_id,
            node_signals,
            explicit_component,
        )
        node_ids = explicit_component | rescued_component
    node_labels: dict[str, str] = dict()
    node_kinds: dict[str, str] = dict()
    child_blocks: list[Block] = list()
    child_blocks_by_node: dict[str, Block] = dict()
    child_input_specs: dict[str, List[str]] = dict()
    child_input_index_by_connector: Dict[
        str,
        Dict[Tuple[DgsGraphicalConnectorKind, int], int],
    ] = dict()
    child_output_specs: dict[str, List[str]] = dict()
    child_node_ids: list[str] = list()

    alias_map: Dict[str, Set[str]] = _build_graph_signal_alias_map(
        node_ids,
        node_by_id,
        node_signals,
    )
    local_adj: Dict[str, Set[str]] = _build_augmented_graphical_adjacency(
        node_ids,
        adjacency,
        node_by_id,
        node_signals,
        alias_map,
    )
    element_by_id: Dict[str, object] = resolved_graphical_indexes.element_by_id
    selected_element_obj: object | None = element_by_id.get(
        selection.instance_entry.element_id or "",
        None,
    )
    nested_entries_by_label: Dict[
        str,
        ElmCompInstanceEntry | None,
    ] = dict()
    nested_entries_by_type_name: Dict[
        str,
        ElmCompInstanceEntry | None,
    ] = dict()
    nested_parameter_values_by_type_id: Dict[
        str,
        Dict[str, float | int | bool | str | complex | None],
    ] = dict()
    if isinstance(selected_element_obj, ElmComp):
        nested_entries: List[ElmCompInstanceEntry] = (
            get_unambiguous_elmcomp_direct_instances(
                entries=extract_elmcomp_direct_instances(
                    circuit,
                    selected_element_obj,
                )
            )
        )
        nested_entries_by_label = _build_instance_entry_lookup_by_slot_name(nested_entries)
        nested_entries_by_type_name = _build_instance_entry_lookup_by_type_name(nested_entries)
        nested_parameter_values_by_type_id = _parameter_values_by_type_id(nested_entries)
    else:
        pass

    ordered_node_ids: list[tuple[str, str]] = list()
    for node_id in node_ids:
        ordered_node_ids.append((_graphic_node_label(node_by_id.get(node_id, node_id)), node_id))
    ordered_node_ids.sort()

    selected_graphical_signals: List[BlkSig] = [
        graphical_signal
        for graphical_signal in circuit.blksigs
        if (
            _normalize_dgs_pointer_id(graphical_signal.pnodfrom) in node_ids
            or _normalize_dgs_pointer_id(graphical_signal.pnodto) in node_ids
        )
    ]

    # Exact cable endpoints are authoritative. Diagnose their direction before
    # the generic reached-node check so a malformed source cannot be reported as
    # an unrelated unsupported child.
    graphical_signal: BlkSig
    for graphical_signal in selected_graphical_signals:
        source_node_id: str = _normalize_dgs_pointer_id(
            graphical_signal.pnodfrom
        )
        target_node_id: str = _normalize_dgs_pointer_id(
            graphical_signal.pnodto
        )
        if source_node_id != "" and source_node_id not in node_by_id:
            raise ValueError(
                "Graphical DGS cable references a missing source FID: "
                f"{graphical_signal.ID}"
            )
        elif target_node_id != "" and target_node_id not in node_by_id:
            raise ValueError(
                "Graphical DGS cable references a missing target FID: "
                f"{graphical_signal.ID}"
            )
        else:
            pass

    # Validate every reached child before materializing any equation. This
    # prevents unsupported syntax in one sibling from hiding a broken exact
    # BlkRef relation elsewhere in the same macro.
    _node_label: str
    for _node_label, node_id in ordered_node_ids:
        node_obj: object | None = node_by_id.get(node_id, None)
        if node_obj is None:
            raise ValueError(
                "Graphical DGS component references a missing child FID: "
                f"{node_id}"
            )
        elif node_id == root_node_id:
            pass
        elif isinstance(node_obj, BlkRef):
            if result.parsed_blocks.get(node_obj.typ_id, None) is None:
                raise ValueError(
                    f"Graphical BlkRef {node_obj.ID} references missing "
                    f"BlkDef FID {node_obj.typ_id}"
                )
            else:
                pass
        elif isinstance(
                node_obj,
                (BlkSum, BlkDiv, BlkMul, BlkSwt, BlkFrom, BlkGoto),
        ):
            pass
        else:
            if isinstance(node_obj, DGSElement):
                unsupported_child_kind: str = node_obj.element_type
            else:
                unsupported_child_kind = "non-DGS object"
            raise ValueError(
                "Graphical DGS component contains an unsupported child "
                f"type: {node_id} ({unsupported_child_kind})"
            )

    for _node_label, node_id in ordered_node_ids:
        node_obj = node_by_id.get(node_id, None)
        if node_obj is None:
            raise ValueError(
                "Graphical DGS component references a missing child FID: "
                f"{node_id}"
            )
        else:
            node_labels[node_id] = _graphic_node_label(node_obj)
            node_kinds[node_id] = _graphic_node_kind(node_obj)

            if node_id == root_node_id:
                pass
            elif isinstance(node_obj, BlkRef):
                parsed = result.parsed_blocks.get(node_obj.typ_id, None)
                if parsed is None:
                    raise ValueError(
                        f"Graphical BlkRef {node_obj.ID} references missing "
                        f"BlkDef FID {node_obj.typ_id}"
                    )
                else:
                    label_is_ambiguous: bool = (
                        node_obj.cdisName in nested_entries_by_label
                        and nested_entries_by_label[node_obj.cdisName] is None
                    )
                    if label_is_ambiguous:
                        raise ValueError(
                            "Graphical BlkRef instance label is ambiguous: "
                            f"{node_obj.cdisName}"
                        )
                    else:
                        instance_entry: ElmCompInstanceEntry | None = (
                            nested_entries_by_label.get(
                                node_obj.cdisName,
                                None,
                            )
                        )
                    if instance_entry is None:
                        type_name_is_ambiguous: bool = (
                            parsed.blkdef.loc_name in nested_entries_by_type_name
                            and nested_entries_by_type_name[
                                parsed.blkdef.loc_name
                            ] is None
                        )
                        if type_name_is_ambiguous:
                            raise ValueError(
                                "Graphical BlkRef type-name relation is "
                                f"ambiguous: {parsed.blkdef.loc_name}"
                            )
                        else:
                            instance_entry = nested_entries_by_type_name.get(
                                parsed.blkdef.loc_name,
                                None,
                            )
                    else:
                        pass

                    if (
                            instance_entry is not None
                            and instance_entry.type_id != parsed.blkdef.ID
                    ):
                        raise ValueError(
                            f"Graphical BlkRef {node_obj.ID} resolved parameters "
                            "from a different BlkDef FID"
                        )
                    else:
                        pass

                    parameter_values = nested_parameter_values_by_type_id.get(parsed.blkdef.ID, None)
                    if instance_entry is not None and len(instance_entry.parameter_values) > 0:
                        parameter_values = instance_entry.parameter_values
                    else:
                        pass

                    blk = _build_block_from_parsed(parsed, dict(), parameter_values=parameter_values)
                    blk.name = _graphic_node_label(node_obj)
                    child_blocks.append(blk)
                    child_blocks_by_node[node_id] = blk
                    child_input_specs[node_id] = list(parsed.blkdef.inputs)
                    child_input_index_by_connector[node_id] = (
                        _build_ordinary_graphical_input_index(
                            input_names=child_input_specs[node_id],
                        )
                    )
                    child_output_specs[node_id] = list(parsed.blkdef.outputs)
                    child_node_ids.append(node_id)
            elif isinstance(node_obj, BlkSum):
                blk, input_specs, output_specs = _build_sum_block_from_graphic_node(node_obj, circuit)
                child_blocks.append(blk)
                child_blocks_by_node[node_id] = blk
                child_input_specs[node_id] = input_specs
                child_input_index_by_connector[node_id] = (
                    _build_sum_runtime_input_index_by_connector(
                        blk_sum=node_obj,
                        circuit=circuit,
                    )
                )
                child_output_specs[node_id] = output_specs
                child_node_ids.append(node_id)
            elif isinstance(node_obj, (BlkDiv, BlkMul)):
                arithmetic_input_index_by_connector: Dict[
                    Tuple[DgsGraphicalConnectorKind, int],
                    int,
                ]
                (
                    blk,
                    input_specs,
                    output_specs,
                    arithmetic_input_index_by_connector,
                ) = build_graphical_arithmetic_block(
                    node=node_obj,
                    circuit=circuit,
                )
                child_blocks.append(blk)
                child_blocks_by_node[node_id] = blk
                child_input_specs[node_id] = input_specs
                child_input_index_by_connector[node_id] = (
                    arithmetic_input_index_by_connector
                )
                child_output_specs[node_id] = output_specs
                child_node_ids.append(node_id)
            elif isinstance(node_obj, BlkSwt):
                switch_input_index_by_connector: Dict[
                    Tuple[DgsGraphicalConnectorKind, int],
                    int,
                ]
                (
                    blk,
                    input_specs,
                    output_specs,
                    switch_input_index_by_connector,
                ) = build_graphical_switch_block(
                    node=node_obj,
                    circuit=circuit,
                )
                child_blocks.append(blk)
                child_blocks_by_node[node_id] = blk
                child_input_specs[node_id] = input_specs
                child_input_index_by_connector[node_id] = (
                    switch_input_index_by_connector
                )
                child_output_specs[node_id] = output_specs
                child_node_ids.append(node_id)
            elif isinstance(node_obj, (BlkFrom, BlkGoto)):
                pass
            else:
                if isinstance(node_obj, DGSElement):
                    unsupported_child_kind: str = node_obj.element_type
                else:
                    unsupported_child_kind = "non-DGS object"
                raise ValueError(
                    "Graphical DGS component contains an unsupported child "
                    f"type: {node_id} ({unsupported_child_kind})"
                )

    selected_runtime_block = _build_block_from_parsed(
        selection.parsed_block,
        dict(),
        parameter_values=selection.instance_entry.parameter_values,
    )
    connections, resolved_outputs = _resolve_graphic_block_connections(
        selected_block=selection.parsed_block,
        child_node_ids=child_node_ids,
        child_blocks=child_blocks_by_node,
        child_input_specs=child_input_specs,
        child_input_index_by_connector=child_input_index_by_connector,
        child_output_specs=child_output_specs,
        graphical_signals=selected_graphical_signals,
        adjacency=local_adj,
        node_by_id=node_by_id,
        alias_map=alias_map,
        root_runtime_block=selected_runtime_block,
    )

    # Root-output cables identify the child variable that actually owns each
    # public result. Propagate that UID through parent initialization before
    # assembling the graphical shell, or inc() remains attached to a dead Var.
    original_root_outputs: List[Var] = list(selected_runtime_block.out_vars)
    resolved_output_count_by_uid: Dict[int, int] = dict()
    counted_resolved_output: Var
    for counted_resolved_output in resolved_outputs:
        resolved_output_count_by_uid[counted_resolved_output.uid] = (
            resolved_output_count_by_uid.get(counted_resolved_output.uid, 0)
            + 1
        )

    root_output_index: int
    for root_output_index in range(len(original_root_outputs)):
        if root_output_index >= len(resolved_outputs):
            pass
        else:
            original_root_output: Var = original_root_outputs[root_output_index]
            resolved_root_output: Var = resolved_outputs[root_output_index]
            if original_root_output.uid == resolved_root_output.uid:
                pass
            else:
                selected_runtime_block.update_model(
                    original_root_output,
                    resolved_root_output,
                )
                if resolved_output_count_by_uid.get(
                    resolved_root_output.uid,
                    0,
                ) == 1:
                    # A unique producer inherits the public macro label while
                    # retaining its executable equation and runtime identity.
                    resolved_root_output.name = original_root_output.name
                else:
                    # One producer may feed several public aliases, so its
                    # private label remains less misleading than one alias.
                    pass

    child_lookup: dict[str, Block] = dict()
    node_id: str
    for node_id in child_node_ids:
        child_lookup[node_id] = child_blocks_by_node[node_id]
    root_in_lookup = _build_name_to_var_map(list(selected_runtime_block.in_vars))
    for instruction in connections:
        consumer_block = child_lookup[instruction.consumer_node_id]
        if instruction.consumer_input_index is None or instruction.consumer_input_index >= len(consumer_block.in_vars):
            raise ValueError(
                "Graphical DGS connection resolved outside the consumer "
                f"block interface: {instruction.consumer_node_id}"
            )
        else:
            consumer_var = consumer_block.in_vars[instruction.consumer_input_index]

            if instruction.source_kind == "block_output" and instruction.source_node_id is not None and instruction.source_output_index is not None:
                producer_block = child_lookup[instruction.source_node_id]
                if instruction.source_output_index < len(producer_block.out_vars):
                    consumer_block.connect([consumer_var], [producer_block.out_vars[instruction.source_output_index]])
                else:
                    raise ValueError(
                        "Graphical DGS connection resolved outside the source "
                        f"block interface: {instruction.source_node_id}"
                    )
            elif instruction.source_kind == "root_input" and instruction.source_root_name is not None:
                root_var = root_in_lookup.get(instruction.source_root_name, None)
                if root_var is not None:
                    consumer_block.connect([consumer_var], [root_var])
                else:
                    raise ValueError(
                        "Graphical DGS connection references a missing root "
                        f"input: {instruction.source_root_name}"
                    )
            else:
                raise ValueError(
                    "Graphical DGS connection instruction is incomplete for "
                    f"consumer {instruction.consumer_node_id}"
                )

    # Parent initialization now consumes the final connected child UIDs. Only
    # exact blank-source pins become zero; live routed gaps remain unresolved.
    parent_bindings: DgsGraphicalParentBindingResult = (
        _connect_graphical_parent_internal_signals(
            selected_block=selection.parsed_block,
            parent_block=selected_runtime_block,
            child_blocks=child_lookup,
            child_input_index_by_connector=child_input_index_by_connector,
            graphical_signals=selected_graphical_signals,
            connections=connections,
            routed_source_signal_names=(
                _collect_routed_graphical_source_signal_names(
                    node_ids=node_ids,
                    node_by_id=node_by_id,
                    node_signals=node_signals,
                )
            ),
            node_by_id=node_by_id,
        )
    )

    view_block = Block(
        name=selection.parsed_block.blkdef.loc_name,
        children=child_blocks,
        in_vars=selected_runtime_block.in_vars,
        out_vars=resolved_outputs,
        algebraic_vars=_retain_referenced_structural_algebraic_vars(
            parent_block=selected_runtime_block,
        ),
        init_eqs=selected_runtime_block.init_eqs,
    )

    return DgsGraphicTreeResult(
        selected_block=selection.parsed_block,
        view_block=view_block,
        node_ids=node_ids,
        adjacency=local_adj,
        node_labels=node_labels,
        node_kinds=node_kinds,
        child_node_ids=child_node_ids,
        connections=connections,
        parent_bindings=parent_bindings,
    )
