# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Modelica to VeraGrid XML Parser (Comprehensive AST Transpiler).

This module provides a strictly typed, zero-dependency XML parser.
It translates flattened Modelica AST exported as XML directly into
VeraGrid Symbolic Blocks, including variables, advanced math operators,
initial equations, and experiment settings.

Architectural rules applied:
- Zero external dependencies (uses native xml.etree.ElementTree).
- Strict static typing and structural Pattern Matching (match-case).
- No dynamic reflection (no hasattr, no getattr).
- Deterministic memory footprint via __slots__.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as Element_tree
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# VeraGrid Engine Imports
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Func, Expr, BinOp
from VeraGridEngine.Utils.Symbolic.block import Block


def _escape_omc_xml_attributes(match: re.Match) -> str:
    """
    Regex substitution callback to escape invalid XML characters.

    :param match: The regex match object.
    :type match: re.Match
    :return: Escaped XML attribute string.
    :rtype: str
    """
    attr_name: str = match.group(1)
    attr_val: str = match.group(2)

    attr_val = attr_val.replace("<", "&lt;")
    attr_val = attr_val.replace(">", "&gt;")
    attr_val = re.sub(r'&(?![A-Za-z0-9#]+;)', '&amp;', attr_val)

    return f'{attr_name}="{attr_val}"'


def _sanitize_xml_content(xml_string: str) -> str:
    """
    Pre-processes the XML string to fix OpenModelica formatting bugs.

    :param xml_string: The raw XML content.
    :type xml_string: str
    :return: Sanitized XML string.
    :rtype: str
    """
    # 1. Clean attributes where OpenModelica injects raw illegal code
    sanitized: str = re.sub(r'(description|info|revisions|message)="([^"]*)"', _escape_omc_xml_attributes, xml_string)

    # 2. Fix unescaped ampersands globally (e.g., '&&' -> '&amp;&amp;')
    sanitized = re.sub(r'&(?![A-Za-z0-9#]+;)', '&amp;', sanitized)

    # 3. Fix unescaped Modelica 'Not Equal' operators which XML sees as empty tags
    sanitized = sanitized.replace("<>", "&lt;&gt;")

    # 4. Fix loose less-than signs that simulate broken opening tags
    sanitized = re.sub(r'<\s', '&lt; ', sanitized)
    sanitized = re.sub(r'<(?=[\d=])', '&lt;', sanitized)

    match: re.Match | None = re.search(r'<(fun:Algorithm|fun:RecordsList|fun:FunctionsList)[\s>]', sanitized)
    if match is not None:
        sanitized = sanitized[:match.start()] + "\n</OpenModelicaModelDescription>"
    else:
        pass

    return sanitized

def safe_float(val_in: str) -> float | None:
    """
    Safely converts a string to a float, handling booleans.

    :param val_in: String value to convert.
    :type val_in: str
    :return: Float representation or None if invalid.
    :rtype: float | None
    """
    clean: str = val_in.strip().lower()
    if clean == "true":
        return 1.0
    elif clean == "false":
        return 0.0
    else:
        try:
            return float(clean)
        except ValueError:
            return None

class LogicExpr(Expr):
    """Custom container for logical and conditional expressions to bypass symbolic.py limits."""
    __slots__ = ['op', 'args']

    def __init__(self, op: str, args: tuple) -> None:
        """Create a logical expression retained by the declarative Modelica parser.

        :param op: Logical or conditional operator name from the validated XML.
        :param args: Ordered symbolic operands associated with the operator.
        :return: None.
        """
        super().__init__()
        self.op = op
        self.args = args

class ExternalFunc(Expr):
    """Custom container for external Modelica functions to bypass symbolic.py Func limits."""
    __slots__ = ['name', 'args']

    def __init__(self, name: str, args: tuple) -> None:
        """Create a declaration for one externally named Modelica function.

        :param name: Validated external function name from the source model.
        :param args: Ordered symbolic arguments retained as declarative data.
        :return: None.
        """
        super().__init__()
        self.name = name
        self.args = args

class ModelicaXMLParser:
    """
    Parses a flattened Modelica XML file into a VeraGrid Block.
    """
    __slots__ = [
        'xml_root',
        'symbol_table',
        'state_vars',
        'algebraic_vars',
        'parameters',
        'equations',
        'initial_equations',
        'when_equations',
        'initial_guesses',
        'fixed_initial_values',
        'experiment_settings',
        'variable_limits'
    ]

    def __init__(self, xml_source: str, is_file: bool = True) -> None:
        """
        Initialize the parser from an XML file path or XML text.

        The source is sanitized before parsing to repair known OpenModelica
        formatting defects without evaluating generated code.

        :param xml_source: XML file path or complete XML document text.
        :param is_file: Whether ``xml_source`` identifies a file on disk.
        :return: ``None``.
        """
        raw_xml: str = ""

        if is_file:
            xml_path: Path = Path(xml_source)
            if not xml_path.is_file():
                raise FileNotFoundError(f"XML file not found: {xml_path}")

            with open(xml_path, "r", encoding="utf-8") as file_obj:
                raw_xml = file_obj.read()
        else:
            raw_xml = xml_source

        clean_xml: str = _sanitize_xml_content(raw_xml)

        self.xml_root = Element_tree.fromstring(clean_xml)

        self.symbol_table: Dict[str, Expr] = dict()
        self.state_vars: List[Var] = list()
        self.algebraic_vars: List[Var] = list()
        self.parameters: Dict[Var, Const] = dict()
        self.equations: List[Expr] = list()
        self.initial_equations: List[Expr] = list()
        self.when_equations: Dict[Expr, List[Expr]] = dict()
        self.initial_guesses: Dict[int, float] = dict()
        self.fixed_initial_values: Dict[int, bool] = dict()
        self.experiment_settings: Dict[str, float] = dict()
        self.variable_limits: Dict[int, Tuple[float, float]] = dict()

    def parse_and_build(self, block_name: str = "ImportedModelicaBlock") -> Block:
        """
        Execute the parsing pipeline and build one declarative VeraGrid block.

        :param block_name: Name assigned to the reconstructed block.
        :return: Populated VeraGrid symbolic block.
        """
        self._parse_experiment_settings()
        self._parse_variables()
        self._parse_equations("ModelEquations", self.equations)
        self._parse_equations("InitialEquations", self.initial_equations)

        return Block(
            name=block_name,
            state_vars=self.state_vars,
            state_eqs=self.equations,
            algebraic_vars=self.algebraic_vars,
            algebraic_eqs=list(),
            parameters=self.parameters
        )

    def _parse_experiment_settings(self) -> None:
        """
        Extract ``DefaultExperiment`` attributes into typed parser state.

        :return: ``None``.
        """
        experiment_node: Element_tree.Element | None = self.xml_root.find(".//DefaultExperiment")
        if experiment_node is not None:
            for key in ("startTime", "stopTime", "stepSize", "tolerance"):
                val_str = experiment_node.attrib.get(key)
                if val_str is not None:
                    self.experiment_settings[key] = float(val_str)
                else:
                    pass
        else:
            pass

    def _parse_variables(self) -> None:
        """
        Parse variables from both supported declarative XML dialects.

        Causality, variability, starting guesses, and aliases are retained so
        redundant variables do not produce singular Jacobians.

        :return: ``None``.
        """
        node_collections = (self.xml_root.findall(".//ScalarVariable"), self.xml_root.findall(".//component"))

        for node_list in node_collections:
            for sv_node in node_list:
                var_name: str = str(sv_node.attrib.get("name", ""))
                causality: str = str(sv_node.attrib.get("causality", "local"))
                variability: str = str(sv_node.attrib.get("variability", "continuous"))
                alias_val: str = str(sv_node.attrib.get("alias", "noAlias"))

                # --- 1. ALIAS ROUTING (The Jacobian shrinker) ---
                if alias_val != "noAlias" and alias_val != "":
                    is_negated: bool = alias_val.startswith("-")
                    base_alias_name: str = alias_val[1:] if is_negated else alias_val

                    # If the base variable hasn't been parsed yet, create a placeholder
                    base_expr_opt: Expr | None = self.symbol_table.get(base_alias_name, None)
                    if base_expr_opt is None:
                        base_expr = Var(base_alias_name)
                        self.symbol_table[base_alias_name] = base_expr
                    else:
                        base_expr = base_expr_opt

                    # Map the alias directly to the base expression (or its mathematical negation)
                    self.symbol_table[var_name] = -base_expr if is_negated else base_expr

                # --- 2. STANDARD VARIABLE PARSING ---
                else:
                    real_node: Element_tree.Element | None = None
                    for child_tag in ("Real", "real", "Integer", "integer", "Boolean", "boolean", "builtin"):
                        real_node = sv_node.find(child_tag)
                        if real_node is not None:
                            break
                        else:
                            pass

                    start_val_str: str | None = None
                    min_val_str: str | None = None
                    max_val_str: str | None = None
                    is_fixed_str: str | None = None

                    if real_node is not None:
                        start_val_str = real_node.attrib.get("start") or real_node.attrib.get("value")
                        min_val_str = real_node.attrib.get("min")
                        max_val_str = real_node.attrib.get("max")
                        is_fixed_str = real_node.attrib.get("fixed")
                    else:
                        pass

                    if start_val_str is None:
                        start_val_str = sv_node.attrib.get("start") or sv_node.attrib.get("value")
                    else:
                        pass

                    if min_val_str is None:
                        min_val_str = sv_node.attrib.get("min")
                    else:
                        pass

                    if max_val_str is None:
                        max_val_str = sv_node.attrib.get("max")
                    else:
                        pass

                    if is_fixed_str is None:
                        is_fixed_str = sv_node.attrib.get("fixed")
                    else:
                        pass

                    if causality == "parameter" or variability == "constant":
                        # Reuse placeholder if it was created by a forward-referencing alias earlier
                        existing_param: Expr | None = self.symbol_table.get(var_name, None)
                        if existing_param is not None and isinstance(existing_param, Var):
                            param_var: Var = existing_param
                        else:
                            param_var = Var(var_name)
                            self.symbol_table[var_name] = param_var

                        if start_val_str is not None:
                            parsed_val: float | None = safe_float(start_val_str)
                            if parsed_val is not None:
                                self.initial_guesses[param_var.uid] = parsed_val
                                if is_fixed_str is not None and is_fixed_str.lower() == "true":
                                    self.fixed_initial_values[param_var.uid] = True
                                else:
                                    self.fixed_initial_values[param_var.uid] = False
                            else:
                                pass
                        else:
                            pass
                    else:
                        # Reuse placeholder if it was created by a forward-referencing alias earlier
                        existing_state: Expr | None = self.symbol_table.get(var_name, None)
                        if existing_state is not None and isinstance(existing_state, Var):
                            vg_var: Var = existing_state
                        else:
                            vg_var = Var(var_name)
                            self.symbol_table[var_name] = vg_var

                        self.state_vars.append(vg_var)

                        if start_val_str is not None:
                            parsed_val_state: float | None = safe_float(start_val_str)
                            if parsed_val_state is not None:
                                self.initial_guesses[vg_var.uid] = parsed_val_state
                                if is_fixed_str is not None and is_fixed_str.lower() == "true":
                                    self.fixed_initial_values[vg_var.uid] = True
                                else:
                                    self.fixed_initial_values[vg_var.uid] = False
                            else:
                                pass
                        else:
                            pass

                        if min_val_str is not None and max_val_str is not None:
                            min_v: float | None = safe_float(min_val_str)
                            max_v: float | None = safe_float(max_val_str)
                            if min_v is not None and max_v is not None:
                                self.variable_limits[vg_var.uid] = (min_v, max_v)
                            else:
                                pass
                        else:
                            pass

    def _parse_equations(self, section_name: str, target_list: List[Expr]) -> None:
        """
        Extracts equations from the XML, handling both simple and nested structures.

        :param section_name: The name of the XML section (e.g., 'ModelEquations').
        :type section_name: str
        :param target_list: The list to be populated with parsed expressions.
        :type target_list: List[Expr]
        :return: None
        :rtype: None
        """
        section_node: Optional[Element_tree.Element] = None
        for node in self.xml_root.iter():
            clean_tag: str = node.tag.split("}")[-1].lower()
            if section_name == "ModelEquations" and clean_tag in ("modelequations", "dynamicequations", "equations"):
                section_node = node
                break
            elif section_name == "InitialEquations" and clean_tag in ("initialequations", "initialization"):
                section_node = node
                break
            else:
                pass

        if section_node is not None:
            self._recursive_equation_extract(section_node, target_list)
        else:
            # MXML places one ``equation`` container directly below the root
            # ``class`` instead of wrapping it in ``ModelEquations``. Parse
            # every expression in that container while keeping initial-equation
            # discovery exclusive to its explicit section.
            if section_name == "ModelEquations":
                root_child: Element_tree.Element
                for root_child in self.xml_root:
                    root_child_tag: str = root_child.tag.split("}")[-1].lower()
                    if root_child_tag == "equation":
                        expression_node: Element_tree.Element
                        for expression_node in root_child:
                            target_list.append(self._parse_ast_node(expression_node))
                        else:
                            pass
                    else:
                        pass
            else:
                pass

    def _recursive_equation_extract(self, parent: Element_tree.Element, target_list: List[Expr]) -> None:
        """
        Recursively traverses the XML to flatten nested systems of equations.
        Traps <equ:When> blocks and redirects their contents to the discrete event dictionary
        to prevent them from being evaluated as continuous DAE residuals.

        :param parent: The current parent node to scan for equation tags.
        :type parent: Element_tree.Element
        :param target_list: The list where continuous expressions are being collected.
        :type target_list: List[Expr]
        :return: None
        :rtype: None
        """
        for child in parent:
            clean_tag: str = child.tag.split("}")[-1].lower()

            if clean_tag == "when":
                # --- Extract WHEN blocks for discrete event handling ---
                cond_expr: Optional[Expr] = None
                statements: List[Expr] = list()

                # 1. Search for the condition and the equations inside the WHEN block
                for when_child in child:
                    w_tag: str = when_child.tag.split("}")[-1].lower()
                    if w_tag in ("condition", "cond"):
                        w_children = list(when_child)
                        if len(w_children) > 0:
                            cond_expr = self._parse_ast_node(w_children[0])
                        else:
                            # OMC translates 'when initial()' to empty condition blocks.
                            cond_expr = Var("INITIALIZATION_EVENT")
                    elif w_tag in ("equation", "statements", "then"):
                        # DO NOT recurse! The children here are the actual math operators (Sub, Reinit, Assign).
                        for stmt_node in when_child:
                            expr: Expr = self._parse_ast_node(stmt_node)
                            statements.append(expr)
                    else:
                        pass

                # 2. Fallback for 'when initial()' without a condition tag
                cond_expr2: Expr = Var("INITIALIZATION_EVENT") if cond_expr is None else cond_expr

                # 3. Store it in the event dictionary
                if statements:
                    if self.when_equations.get(cond_expr2, None) is None:
                        self.when_equations[cond_expr2] = list()
                    else:
                        pass
                    self.when_equations[cond_expr2].extend(statements)
                else:
                    pass

            elif clean_tag == "equation":
                children: List[Element_tree.Element] = list(child)
                if len(children) > 0:
                    root_node: Element_tree.Element = children[0]
                    is_block: bool = any(c.tag.split("}")[-1].lower() in ("equation", "when") for c in root_node)

                    if is_block:
                        self._recursive_equation_extract(root_node, target_list)
                    else:
                        expr: Expr = self._parse_ast_node(root_node)
                        target_list.append(expr)

                else:
                    pass
            else:
                self._recursive_equation_extract(child, target_list)

    def _parse_ast_node(self, node: Element_tree.Element) -> Expr:
        """
        Reconstruct one symbolic expression from a declarative XML AST node.

        :param node: OMC or JModelica/FMI XML element to parse.
        :return: Explicit VeraGrid symbolic expression represented by the element.
        """
        raw_tag: str = node.tag

        clean_tag = raw_tag.split("}", 1)[1] if "}" in raw_tag else raw_tag
        tag = clean_tag.lower()

        children: List[Element_tree.Element] = list(node)

        # MXML represents operators and functions through a typed ``builtin``
        # attribute. Normalize that declarative spelling to the same tags used
        # by the OpenModelica branch below, without evaluating source text.
        if tag == "call" or tag == "operator":
            builtin_name: str = str(node.attrib.get("builtin", "")).strip().lower()
            if builtin_name == "+":
                tag = "add"
            elif builtin_name == "-":
                tag = "sub"
            elif builtin_name == "*":
                tag = "mult"
            elif builtin_name == "/":
                tag = "div"
            elif builtin_name == "^":
                tag = "power"
            else:
                tag = builtin_name
        else:
            pass

        match tag:  # TODO: probably too new
            # ---------------------------------------------------------
            # Terminals (Variables, Constants, Arrays)
            # ---------------------------------------------------------
            case "cref" | "local" | "identifier" | "time":
                if tag == "time":
                    var_name: str = "time"
                elif tag == "identifier":
                    parts: List[str] = list()
                    for p in node:
                        if p.tag.endswith("QualifiedNamePart"):
                            part_name: str = str(p.attrib.get("name", ""))

                            # --- FIX: Extract array indices if present ---
                            indices: List[str] = list()
                            for child in p.iter():
                                if child.tag.endswith("IntegerLiteral") and child.text:
                                    indices.append(child.text)

                            if len(indices) > 0:
                                idx_str: str = ",".join(indices)
                                part_name += f"[{idx_str}]"
                            else:
                                pass

                            parts.append(part_name)
                        else:
                            pass

                    if parts:
                        var_name = ".".join(parts)
                    else:
                        var_name: str = str(node.text).strip() if node.text is not None else ""
                else:
                    var_name: str = str(node.attrib.get("name", ""))

                # Fetch or create the variable in the symbol table
                existing_var: Expr | None = self.symbol_table.get(var_name, None)
                if existing_var is not None:
                    return existing_var
                else:
                    new_var = Var(var_name)
                    self.symbol_table[var_name] = new_var
                    return new_var

            case "real" | "integer" | "realliteral" | "integerliteral":
                val_str = node.attrib.get("value")
                if val_str is None and node.text is not None:
                    val_str = node.text.strip()
                return Const(float(val_str or "0.0"))

            case "boolean" | "booleanliteral":
                val_str = str(node.attrib.get("value") or node.text or "false").strip().lower()
                return Const(1.0 if val_str in ("true", "1", "1.0") else 0.0)

            case "true":
                return Const(1.0)
            case "false":
                return Const(0.0)

            # ---------------------------------------------------------
            # Binary Mathematical Operators
            # ---------------------------------------------------------
            case "add" | "sub" | "mult" | "mul" | "div" | "equal" | "power" | "assign":
                if len(children) == 0:
                    # OpenModelica artifact: empty equations (e.g., <exp:Sub></exp:Sub>)
                    return Const(0.0)
                elif len(children) != 2:
                    # Fallback for malformed nodes
                    print(f"WARNING: Binary operator '{raw_tag}' expects exactly 2 children but got {len(children)}.")
                    return Const(0.0)
                else:
                    left: Expr = self._parse_ast_node(children[0])
                    right: Expr = self._parse_ast_node(children[1])

                    match tag:  # TODO: probably too new
                        case "add":
                            return left + right
                        case "sub":
                            return left - right
                        case "mult" | "mul":
                            return left * right
                        case "div":
                            return left / right
                        case "power":
                            return left ** right
                        case "equal" | "assign":
                            return left - right

            # ---------------------------------------------------------
            # Unary Operators and Functions
            # ---------------------------------------------------------
            case "neg" | "sin" | "cos" | "tan" | "exp" | "log" | "log10" | "sqrt" | "abs" | "der" | "asin" | \
                 "acos" | "atan" | "sinh" | "cosh" | "tanh" | "sign" | "not" | "pre":
                if len(children) != 1:
                    print(f"WARNING: Operator '{raw_tag}' expects exactly 1 child.")
                    return Const(0.0)
                else:
                    operand: Expr = self._parse_ast_node(children[0])

                    if tag == "neg":
                        return -operand
                    elif tag == "not":
                        return LogicExpr(op="not", args=(operand,))
                    elif tag == "pre":
                        return ExternalFunc(name="pre", args=(operand,))
                    elif tag == "der":
                        if isinstance(operand, Var):
                            return Var(name=f"d_{operand.name}", base_var=operand)
                        else:
                            print("WARNING: 'der' operator applied to a non-variable.")
                            return Const(0.0)
                    else:
                        return Func(op=tag, arg=operand)

            # ---------------------------------------------------------
            # Conditional Logic (If-Then-Else)
            # ---------------------------------------------------------
            case "if":
                cond_node = then_node = else_node = None

                # Flexible search for logical blocks
                for child in children:
                    ctag = child.tag.split("}", 1)[1].lower() if "}" in child.tag else child.tag.lower()
                    if ctag in ("cond", "condition"):
                        cond_node = child
                    elif ctag in ("then", "statements"):
                        then_node = child
                    elif ctag == "else":
                        else_node = child
                    else:
                        pass

                if cond_node is not None and then_node is not None and else_node is not None:
                    cond_expr = self._parse_ast_node(list(cond_node)[0])
                    then_expr = self._parse_ast_node(list(then_node)[0])
                    else_expr = self._parse_ast_node(list(else_node)[0])
                    return LogicExpr(op="if_else", args=(cond_expr, then_expr, else_expr))
                else:
                    print("WARNING: Incomplete '<if>' block.")
                    return Const(0.0)

            # ---------------------------------------------------------
            # Relational and Comparators (Discrete logic)
            # ---------------------------------------------------------
            case "greater" | "less" | "greaterorequal" | "lessorequal" | "loglt" | "loggt" | "loggeq":
                if len(children) != 2:
                    print(f"WARNING: Relational operator '{raw_tag}' expects exactly 2 children.")
                    return Const(0.0)
                else:
                    left = self._parse_ast_node(children[0])
                    right = self._parse_ast_node(children[1])

                    # Mapping JModelica/FMI to VeraGrid operators
                    op_map = {
                        "loglt": "less", "loggt": "greater", "loggeq": "greaterOrEqual",
                        "greaterorequal": "greaterOrEqual", "lessorequal": "lessOrEqual"
                    }
                    final_op = op_map.get(tag, tag)
                    return LogicExpr(op=final_op, args=(left, right))

            # ---------------------------------------------------------
            # Binary Logical Operators
            # ---------------------------------------------------------
            case "and" | "or" | "min" | "max" | "atan2":
                if len(children) != 2:
                    print(f"WARNING: Operator '{raw_tag}' expects exactly 2 children.")
                    return Const(0.0)
                else:
                    left_arg = self._parse_ast_node(children[0])
                    right_arg = self._parse_ast_node(children[1])
                    return LogicExpr(op=tag, args=(left_arg, right_arg))

            # ---------------------------------------------------------
            # Discrete State Reinitialization (Reinit)
            # ---------------------------------------------------------
            case "reinit":
                if len(children) != 2:
                    print("WARNING: Reinit operator expects exactly 2 children.")
                    return Const(0.0)
                else:
                    left_var = self._parse_ast_node(children[0])
                    right_val = self._parse_ast_node(children[1])
                    return BinOp(op="-", left=left_var, right=right_val)

            # ---------------------------------------------------------
            # External / Modelica Function Calls
            # ---------------------------------------------------------
            case "functioncall":
                func_name: str = "unknown_func"
                for child in children:
                    ctag: str = child.tag.split("}")[-1].lower()
                    if ctag == "name":
                        parts = [p.attrib.get("name", "") for p in child if p.tag.endswith("QualifiedNamePart")]
                        if len(parts) > 0:
                            func_name = parts[-1]
                        else:
                            pass
                        break
                    else:
                        pass

                parsed_args: List[Expr] = list()
                for child in children:
                    ctag: str = child.tag.split("}")[-1].lower()
                    if ctag == "arguments":
                        for arg_node in child:
                            parsed_args.append(self._parse_ast_node(arg_node))
                        break
                    else:
                        pass

                return ExternalFunc(name=func_name, args=tuple(parsed_args))

            # ---------------------------------------------------------
            # Fallback (Crash protection)
            # ---------------------------------------------------------
            case _:
                print(f"WARNING: XML tag not supported by VeraGrid: '{raw_tag}' (Clean: '{tag}')")
                return Const(0.0)
