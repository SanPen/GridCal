# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.BasicBlockCatalog.Functions import BasicBlockCatalogTemplateBuilder
from VeraGridEngine.Templates.BasicBlockCatalog.Functions import get_basic_block_catalog_template_builder_by_module_name
from VeraGridEngine.Templates.BasicBlockCatalog.basic_block_catalog import BasicBlockTemplateDescriptor
from VeraGridEngine.Templates.BasicBlockCatalog.basic_block_catalog import get_basic_block_catalog_descriptors
from VeraGridEngine.Templates.BasicBlockCatalog.basic_block_catalog import get_basic_block_catalog_descriptor_by_key
from VeraGridEngine.Templates.BasicBlockCatalog.basic_block_catalog import get_basic_block_catalog_templates_dir
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import CmpOp
from VeraGridEngine.Utils.Symbolic.symbolic import Comparison
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from VeraGridEngine.Utils.Symbolic.symbolic import Func2
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.procedural_logic import AnalogFlipFlopLogic
from VeraGridEngine.Utils.procedural_logic import FixedSampleLogic
from VeraGridEngine.Utils.procedural_logic import FlipFlopLogic
from VeraGridEngine.Utils.procedural_logic import GradientLimiterLogic
from VeraGridEngine.Utils.procedural_logic import MovingAverageLogic
from VeraGridEngine.Utils.procedural_logic import PickupDropoffLogic
from VeraGridEngine.Utils.procedural_logic import ResetOnRisingEdgeLogic
from VeraGridEngine.Utils.procedural_logic import SampledValueLogic
from VeraGridEngine.Utils.procedural_logic import TimeDelayLogic


def build_basic_block_catalog_default_name_builder_name(module_name: str) -> str:
    """
    Build the unique helper name that returns one module default template name.

    :param module_name: Standalone module stem.
    :returns: Unique helper name.
    """
    return f"build_{module_name}_default_template_name"


def build_basic_block_catalog_template_builder_name(module_name: str) -> str:
    """
    Build the unique helper name that materializes one standalone template.

    :param module_name: Standalone module stem.
    :returns: Unique builder name.
    """
    return f"build_{module_name}_template"


class _TemplateVariableGroups:
    """
    Explicit variable groups used by the standalone module emitter.
    """

    __slots__ = ("param_vars", "state_vars", "algebraic_vars", "diff_vars")

    def __init__(self,
                 param_vars: Sequence[Var],
                 state_vars: Sequence[Var],
                 algebraic_vars: Sequence[Var],
                 diff_vars: Sequence[Var]) -> None:
        """
        Store the variable groups used by one emitted template module.

        :param param_vars: Runtime parameter variables.
        :param state_vars: State variables.
        :param algebraic_vars: Algebraic and shared variables.
        :param diff_vars: Differential variables.
        :returns: None.
        """
        self.param_vars = tuple(param_vars)
        self.state_vars = tuple(state_vars)
        self.algebraic_vars = tuple(algebraic_vars)
        self.diff_vars = tuple(diff_vars)


class BasicBlockStandaloneModuleEmitter:
    """
    Emit one clean standalone catalog module from one materialized template block.
    """

    __slots__ = (
        "_block",
        "_display_name",
        "_module_name",
        "_default_template_name",
        "_referenced_vars_by_uid",
        "_identifier_map",
        "_variable_groups",
    )

    def __init__(self,
                  block: Block,
                  display_name: str,
                  module_name: str,
                  default_template_name: str) -> None:
        """
        Build the standalone module emitter for one materialized template.

        :param block: Materialized template block.
        :param display_name: Human-facing template name.
        :param module_name: Standalone module stem used to build unique function names.
        :param default_template_name: Default runtime template name.
        :returns: None.
        :raises ValueError: Raised when the block contains child blocks.
        """
        if len(block.children) > 0:
            raise ValueError("The standalone catalog emitter only supports leaf blocks")
        else:
            pass

        self._block = block
        self._display_name = display_name
        self._module_name = module_name
        self._default_template_name = default_template_name
        self._referenced_vars_by_uid: dict[int, Var] = dict()
        self._collect_referenced_variables(self._referenced_vars_by_uid)
        self._identifier_map = self._build_identifier_map()
        self._variable_groups = self._build_variable_groups()

    def render(self) -> str:
        """
        Render the full standalone Python module.

        :returns: Python module text.
        """
        lines: list[str] = list()

        self._append_module_license_header(lines)
        self._append_module_docstring(lines)
        self._append_imports(lines)
        self._append_default_name_function(lines)
        self._append_template_builder_function(lines)

        return "\n".join(lines) + "\n"

    def _append_module_license_header(self, lines: list[str]) -> None:
        """
        Append the standard MPL header used by the repository.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("# This Source Code Form is subject to the terms of the Mozilla Public")
        lines.append("# License, v. 2.0. If a copy of the MPL was not distributed with this")
        lines.append("# file, You can obtain one at https://mozilla.org/MPL/2.0/.")
        lines.append("# SPDX-License-Identifier: MPL-2.0")
        lines.append("")

    def _append_module_docstring(self, lines: list[str]) -> None:
        """
        Append the module docstring.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append('"""')
        lines.append(f"Standalone EMT template for the basic catalog block '{self._display_name}'.")
        lines.append("")
        lines.append("This module is generated from the shipped VeraGrid catalog artifacts and keeps the")
        lines.append("symbolic surface explicit so both humans and tools can inspect it directly.")
        lines.append('"""')
        lines.append("")

    def _append_imports(self, lines: list[str]) -> None:
        """
        Append the import block.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("from __future__ import annotations")
        lines.append("")
        lines.append("from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate")
        lines.append("from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory")
        lines.append("from VeraGridEngine.Utils.Symbolic.block import Block")
        lines.append("from VeraGridEngine.Utils.Symbolic import symbolic as sym")
        lines.append("from VeraGridEngine.Utils.Symbolic.symbolic import Const")
        lines.append("from VeraGridEngine.Utils.Symbolic.symbolic import Expr")
        lines.append("from VeraGridEngine.Utils.Symbolic.symbolic import Var")
        logic_import_names: Sequence[str] = self._build_procedural_logic_import_names()

        if len(logic_import_names) > 0:
            lines.append("from VeraGridEngine.Utils.procedural_logic import " + ", ".join(logic_import_names))
        else:
            pass

        lines.append("from VeraGridEngine.enumerations import DeviceType")
        lines.append("")

    def _append_default_name_function(self, lines: list[str]) -> None:
        """
        Append the default-name helper.

        :param lines: Output line buffer.
        :returns: None.
        """
        default_name_builder_name: str = build_basic_block_catalog_default_name_builder_name(self._module_name)

        # Each generated helper name must be unique so the package can import every
        # module explicitly without relying on wildcard exports or name shadowing.
        lines.append(f"def {default_name_builder_name}() -> str:")
        lines.append("    \"\"\"")
        lines.append("    Return the canonical runtime name for this standalone template.")
        lines.append("")
        lines.append("    :returns: Default template name.")
        lines.append("    \"\"\"")
        lines.append(f"    return {repr(self._default_template_name)}")
        lines.append("")

    def _append_template_builder_function(self, lines: list[str]) -> None:
        """
        Append the template builder function.

        :param lines: Output line buffer.
        :returns: None.
        """
        default_name_builder_name: str = build_basic_block_catalog_default_name_builder_name(self._module_name)
        template_builder_name: str = build_basic_block_catalog_template_builder_name(self._module_name)

        # The explicit builder name becomes the stable import target used by the
        # package registry, so no runtime module probing is needed anymore.
        lines.append(f"def {template_builder_name}(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:")
        lines.append("    \"\"\"")
        lines.append("    Materialize the standalone EMT template.")
        lines.append("")
        lines.append("    :param vf: Variable factory used to allocate the symbolic surface.")
        lines.append("    :param name: Optional explicit runtime template name.")
        lines.append("    :returns: Materialized EMT template.")
        lines.append("    \"\"\"")
        lines.append("    template_name: str")
        lines.append("    if name is None:")
        lines.append(f"        template_name = {default_name_builder_name}()")
        lines.append("    else:")
        lines.append("        template_name = name")
        lines.append("")
        lines.append("    # Allocate the template container before building the symbolic surface.")
        lines.append("    template: EmtModelTemplate = EmtModelTemplate()")
        lines.append("    template.tpe = DeviceType.NoDevice")
        lines.append("    template.name = template_name")
        lines.append("")
        self._append_variable_declarations(lines)
        self._append_block_collection_builders(lines)
        self._append_block_constructor(lines)
        lines.append("")
        lines.append("    return template")
        lines.append("")

    def _append_variable_declarations(self, lines: list[str]) -> None:
        """
        Append the variable declarations grouped by their runtime role.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("    # Declare every variable explicitly before the equations reference it.")
        self._append_group_variable_declarations(lines, "runtime parameter", self._variable_groups.param_vars, False)
        self._append_group_variable_declarations(lines, "state", self._variable_groups.state_vars, False)
        self._append_group_variable_declarations(lines, "algebraic/shared", self._variable_groups.algebraic_vars, False)
        self._append_group_variable_declarations(lines, "differential", self._variable_groups.diff_vars, True)
        lines.append("")

    def _append_group_variable_declarations(self,
                                            lines: list[str],
                                            group_label: str,
                                            group_vars: Sequence[Var],
                                            differential_group: bool) -> None:
        """
        Append the declarations for one variable group.

        :param lines: Output line buffer.
        :param group_label: Human-facing group label.
        :param group_vars: Variables in the group.
        :param differential_group: ``True`` when the variables are differential variables.
        :returns: None.
        """
        lines.append(f"    # Declare the {group_label} variables used by the template.")
        sorted_vars: list[Var] = list(group_vars)
        sorted_vars.sort(key=self._var_sort_key)
        var_obj: Var

        for var_obj in sorted_vars:
            identifier: str = self._identifier_map[var_obj.uid]
            # The generated symbolic name is source code in the equation editor,
            # so catalogue display punctuation cannot be preserved in this part.
            raw_var_name: str = self._safe_name(self._build_runtime_free_var_name(var_obj.name))
            if differential_group:
                base_identifier: str = self._identifier_map[var_obj.base_var.uid]
                lines.append(
                    f"    {identifier}: Var = vf.add_diff_var({repr(raw_var_name + '_')} + template_name, base_var={base_identifier})"
                )
            else:
                lines.append(f"    {identifier}: Var = vf.add_var({repr(raw_var_name + '_')} + template_name)")

    def _append_block_collection_builders(self, lines: list[str]) -> None:
        """
        Append the typed collection builders used by the block constructor.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("    # Build explicit typed collections so the symbolic surface is easy to inspect.")
        self._append_expression_list(lines, "state_equations", list(self._block.state_eqs))
        self._append_var_list(lines, "state_variables", list(self._block.state_vars))
        self._append_expression_list(lines, "algebraic_equations", list(self._block.algebraic_eqs))
        self._append_var_list(lines, "algebraic_variables", list(self._block.algebraic_vars))
        self._append_var_list(lines, "differential_variables", list(self._block.diff_vars))
        self._append_var_list(lines, "input_variables", list(self._block.in_vars))
        self._append_var_list(lines, "output_variables", list(self._block.out_vars))
        self._append_expression_mapping(lines, "event_parameters", self._block.event_dict)
        self._append_expression_mapping(lines, "mode_parameters", self._block.mode_dict)
        self._append_expression_mapping(lines, "initial_equations", self._block.init_eqs)
        self._append_expression_mapping(lines, "differential_initial_equations", self._block.diff_init_eqs)
        self._append_procedural_logic_list(lines)

    def _append_expression_list(self,
                                lines: list[str],
                                list_name: str,
                                expressions: Sequence[Expr]) -> None:
        """
        Append one typed expression list.

        :param lines: Output line buffer.
        :param list_name: Target variable name.
        :param expressions: Expressions to append.
        :returns: None.
        """
        lines.append(f"    {list_name}: list[Expr] = list()")
        expr_obj: Expr
        for expr_obj in expressions:
            lines.append(f"    {list_name}.append({self._expr_to_python(expr_obj)})")

    def _append_var_list(self,
                         lines: list[str],
                         list_name: str,
                         vars_list: Sequence[Var]) -> None:
        """
        Append one typed variable list.

        :param lines: Output line buffer.
        :param list_name: Target variable name.
        :param vars_list: Variables to append.
        :returns: None.
        """
        lines.append(f"    {list_name}: list[Var] = list()")
        var_obj: Var
        for var_obj in vars_list:
            lines.append(f"    {list_name}.append({self._identifier_map[var_obj.uid]})")

    def _append_expression_mapping(self,
                                   lines: list[str],
                                   mapping_name: str,
                                   mapping: dict[Var, Expr | Const]) -> None:
        """
        Append one typed expression mapping.

        :param lines: Output line buffer.
        :param mapping_name: Target variable name.
        :param mapping: Mapping to append.
        :returns: None.
        """
        lines.append(f"    {mapping_name}: dict[Var, Expr | Const] = dict()")
        key_obj: Var
        value_obj: Expr | Const
        for key_obj, value_obj in mapping.items():
            lines.append(
                f"    {mapping_name}[{self._identifier_map[key_obj.uid]}] = {self._expr_or_const_to_python(value_obj)}"
            )

    def _append_procedural_logic_list(self, lines: list[str]) -> None:
        """
        Append the typed procedural-logic list.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("    procedural_logic_entries: list[object] = list()")
        logic_obj: object
        for logic_obj in self._block.procedural_logic:
            lines.append(f"    procedural_logic_entries.append({self._procedural_logic_entry_to_python(logic_obj)})")

    def _append_block_constructor(self, lines: list[str]) -> None:
        """
        Append the final block constructor.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("")
        lines.append("    # Assemble the final block from the explicit typed collections above.")
        lines.append("    template.block = Block(")
        lines.append("        state_vars=state_variables,")
        lines.append("        state_eqs=state_equations,")
        lines.append("        algebraic_vars=algebraic_variables,")
        lines.append("        algebraic_eqs=algebraic_equations,")
        lines.append("        diff_vars=differential_variables,")
        lines.append("        init_eqs=initial_equations,")
        lines.append("        diff_init_eqs=differential_initial_equations,")
        lines.append("        in_vars=input_variables,")
        lines.append("        out_vars=output_variables,")
        lines.append("        event_dict=event_parameters,")
        lines.append("        mode_dict=mode_parameters,")
        lines.append("        procedural_logic=procedural_logic_entries,")
        lines.append("        name=template_name,")
        lines.append("    )")

    def _build_identifier_map(self) -> dict[int, str]:
        """
        Build the deterministic Python identifier map for the block surface.

        :returns: Identifier by variable uid.
        """
        used_identifiers: dict[str, int] = dict()
        identifier_map: dict[int, str] = dict()
        ordered_vars: list[Var] = list(self._referenced_vars_by_uid.values())
        ordered_vars.sort(key=self._var_sort_key)
        var_obj: Var

        for var_obj in ordered_vars:
            base_identifier: str = self._safe_name(self._build_runtime_free_var_name(var_obj.name))
            current_count: int = used_identifiers.get(base_identifier, 0)
            used_identifiers[base_identifier] = current_count + 1
            if current_count == 0:
                identifier_map[var_obj.uid] = base_identifier
            else:
                identifier_map[var_obj.uid] = f"{base_identifier}_{current_count}"

        return identifier_map

    def _build_variable_groups(self) -> _TemplateVariableGroups:
        """
        Build the declaration groups used by the emitted module.

        :returns: Variable groups.
        """
        all_vars: list[Var] = list(self._referenced_vars_by_uid.values())
        state_uids: set[int] = {var_obj.uid for var_obj in self._block.state_vars}
        diff_uids: set[int] = {var_obj.uid for var_obj in self._block.diff_vars}
        param_uids: set[int] = {var_obj.uid for var_obj in self._block.event_dict.keys()}
        param_uids |= {var_obj.uid for var_obj in self._block.parameters.keys()}

        param_vars: list[Var] = list()
        state_vars: list[Var] = list()
        algebraic_vars: list[Var] = list()
        diff_vars: list[Var] = list()
        var_obj: Var

        for var_obj in all_vars:
            if var_obj.uid in diff_uids:
                diff_vars.append(var_obj)
            elif var_obj.uid in state_uids:
                state_vars.append(var_obj)
            elif var_obj.uid in param_uids:
                param_vars.append(var_obj)
            else:
                algebraic_vars.append(var_obj)

        return _TemplateVariableGroups(
            param_vars=param_vars,
            state_vars=state_vars,
            algebraic_vars=algebraic_vars,
            diff_vars=diff_vars,
        )

    def _collect_referenced_variables(self, vars_found: dict[int, Var]) -> None:
        """
        Collect every variable referenced by the emitted leaf block.

        :param vars_found: Output mapping by variable uid.
        :returns: None.
        """
        self._collect_var_sequence(self._block.state_vars, vars_found)
        self._collect_var_sequence(self._block.algebraic_vars, vars_found)
        self._collect_var_sequence(self._block.diff_vars, vars_found)
        self._collect_var_sequence(self._block.in_vars, vars_found)
        self._collect_var_sequence(self._block.out_vars, vars_found)
        self._collect_mapping_variables(self._block.event_dict, vars_found)
        self._collect_mapping_variables(self._block.mode_dict, vars_found)
        self._collect_mapping_variables(self._block.init_eqs, vars_found)
        self._collect_mapping_variables(self._block.diff_init_eqs, vars_found)
        self._collect_expr_sequence(self._block.state_eqs, vars_found)
        self._collect_expr_sequence(self._block.algebraic_eqs, vars_found)
        self._collect_procedural_logic_variables(vars_found)

    def _collect_var_sequence(self,
                              vars_list: Sequence[Var],
                              vars_found: dict[int, Var]) -> None:
        """
        Collect one variable sequence into the uid map.

        :param vars_list: Variable sequence.
        :param vars_found: Output mapping by variable uid.
        :returns: None.
        """
        var_obj: Var
        for var_obj in vars_list:
            vars_found[var_obj.uid] = var_obj

    def _collect_mapping_variables(self,
                                   mapping: dict[Var, Expr | Const],
                                   vars_found: dict[int, Var]) -> None:
        """
        Collect the variables referenced by one mapping.

        :param mapping: Mapping to inspect.
        :param vars_found: Output mapping by variable uid.
        :returns: None.
        """
        key_obj: Var
        value_obj: Expr | Const
        for key_obj, value_obj in mapping.items():
            vars_found[key_obj.uid] = key_obj
            self._collect_expr_variables(value_obj, vars_found)

    def _collect_expr_sequence(self,
                               expressions: Sequence[Expr],
                               vars_found: dict[int, Var]) -> None:
        """
        Collect the variables referenced by one expression sequence.

        :param expressions: Expression sequence.
        :param vars_found: Output mapping by variable uid.
        :returns: None.
        """
        expr_obj: Expr
        for expr_obj in expressions:
            self._collect_expr_variables(expr_obj, vars_found)

    def _collect_expr_variables(self,
                                expr_obj: Expr | Const | Comparison,
                                vars_found: dict[int, Var]) -> None:
        """
        Collect the variables referenced by one expression-like object.

        :param expr_obj: Expression-like object.
        :param vars_found: Output mapping by variable uid.
        :returns: None.
        """
        expression: Expr
        if isinstance(expr_obj, Comparison):
            expression = expr_obj.to_expression()
        elif isinstance(expr_obj, Expr):
            expression = expr_obj
        else:
            expression = expr_obj

        if isinstance(expression, Var):
            vars_found[expression.uid] = expression
        elif isinstance(expression, Expr):
            var_obj: Var
            for var_obj in expression.get_vars():
                vars_found[var_obj.uid] = var_obj
        else:
            pass

    def _collect_procedural_logic_variables(self, vars_found: dict[int, Var]) -> None:
        """
        Collect variables referenced by the procedural logic entries.

        :param vars_found: Output mapping by variable uid.
        :returns: None.
        """
        logic_obj: object
        for logic_obj in self._block.procedural_logic:
            if isinstance(logic_obj, FixedSampleLogic):
                self._collect_expr_variables(logic_obj.condition_expr, vars_found)
                output_var: Var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, SampledValueLogic):
                self._collect_expr_variables(logic_obj.source_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, FlipFlopLogic):
                self._collect_expr_variables(logic_obj.set_expr, vars_found)
                self._collect_expr_variables(logic_obj.reset_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, AnalogFlipFlopLogic):
                self._collect_expr_variables(logic_obj.input_expr, vars_found)
                self._collect_expr_variables(logic_obj.set_expr, vars_found)
                self._collect_expr_variables(logic_obj.reset_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, PickupDropoffLogic):
                self._collect_expr_variables(logic_obj.bool_expr, vars_found)
                self._collect_expr_variables(logic_obj.pickup_delay_expr, vars_found)
                self._collect_expr_variables(logic_obj.drop_delay_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, TimeDelayLogic):
                self._collect_expr_variables(logic_obj.source_expr, vars_found)
                self._collect_expr_variables(logic_obj.delay_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, MovingAverageLogic):
                self._collect_expr_variables(logic_obj.source_expr, vars_found)
                self._collect_expr_variables(logic_obj.delay_expr, vars_found)
                self._collect_expr_variables(logic_obj.window_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, GradientLimiterLogic):
                self._collect_expr_variables(logic_obj.source_expr, vars_found)
                self._collect_expr_variables(logic_obj.lower_rate_expr, vars_found)
                self._collect_expr_variables(logic_obj.upper_rate_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, ResetOnRisingEdgeLogic):
                self._collect_expr_variables(logic_obj.reset_expr, vars_found)
                self._collect_expr_variables(logic_obj.value_expr, vars_found)
                target_var: Var = self._find_var_by_name_from_candidates(logic_obj.target_var_name, vars_found)
                vars_found[target_var.uid] = target_var
            else:
                raise TypeError(f"Unsupported procedural logic export type: {type(logic_obj).__name__}")

    def _build_procedural_logic_import_names(self) -> Sequence[str]:
        """
        Build the deterministic procedural-logic import list.

        :returns: Sorted import-name tuple.
        """
        names: set[str] = set()
        logic_obj: object
        for logic_obj in self._block.procedural_logic:
            if isinstance(logic_obj, FixedSampleLogic):
                names.add("selfix")
            elif isinstance(logic_obj, SampledValueLogic):
                if logic_obj.output_var_name.startswith("proc_select_") or "__proc_select_" in logic_obj.output_var_name:
                    names.add("sampled_value")
                else:
                    names.add("lastvalue")
            elif isinstance(logic_obj, FlipFlopLogic):
                names.add("flipflop")
            elif isinstance(logic_obj, AnalogFlipFlopLogic):
                names.add("aflipflop")
            elif isinstance(logic_obj, PickupDropoffLogic):
                names.add("picdro")
            elif isinstance(logic_obj, TimeDelayLogic):
                names.add("delay")
            elif isinstance(logic_obj, MovingAverageLogic):
                names.add("movingavg")
            elif isinstance(logic_obj, GradientLimiterLogic):
                names.add("gradlim_const")
            elif isinstance(logic_obj, ResetOnRisingEdgeLogic):
                names.add("reset")
            else:
                raise TypeError(f"Unsupported procedural logic export type: {type(logic_obj).__name__}")

        return tuple(sorted(names))

    def _procedural_logic_entry_to_python(self, logic_obj: object) -> str:
        """
        Convert one procedural-logic entry to Python code.

        :param logic_obj: Procedural-logic entry.
        :returns: Python expression text.
        """
        if isinstance(logic_obj, FixedSampleLogic):
            output_var: Var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return f"selfix({self._expr_like_to_python(logic_obj.condition_expr)}, output={self._identifier_map[output_var.uid]})"
        elif isinstance(logic_obj, SampledValueLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            if logic_obj.output_var_name.startswith("proc_select_") or "__proc_select_" in logic_obj.output_var_name:
                return f"sampled_value(output={self._identifier_map[output_var.uid]}, source={self._expr_like_to_python(logic_obj.source_expr)})"
            else:
                return f"lastvalue({self._expr_like_to_python(logic_obj.source_expr)}, output={self._identifier_map[output_var.uid]})"
        elif isinstance(logic_obj, FlipFlopLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return (
                f"flipflop({self._expr_like_to_python(logic_obj.set_expr)}, "
                f"{self._expr_like_to_python(logic_obj.reset_expr)}, output={self._identifier_map[output_var.uid]})"
            )
        elif isinstance(logic_obj, AnalogFlipFlopLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return (
                f"aflipflop({self._expr_like_to_python(logic_obj.input_expr)}, "
                f"{self._expr_like_to_python(logic_obj.set_expr)}, "
                f"{self._expr_like_to_python(logic_obj.reset_expr)}, output={self._identifier_map[output_var.uid]})"
            )
        elif isinstance(logic_obj, PickupDropoffLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return (
                f"picdro({self._expr_like_to_python(logic_obj.bool_expr)}, "
                f"{self._expr_like_to_python(logic_obj.pickup_delay_expr)}, "
                f"{self._expr_like_to_python(logic_obj.drop_delay_expr)}, output={self._identifier_map[output_var.uid]})"
            )
        elif isinstance(logic_obj, TimeDelayLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return (
                f"delay({self._expr_like_to_python(logic_obj.source_expr)}, "
                f"{self._expr_like_to_python(logic_obj.delay_expr)}, output={self._identifier_map[output_var.uid]})"
            )
        elif isinstance(logic_obj, MovingAverageLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return (
                f"movingavg({self._expr_like_to_python(logic_obj.source_expr)}, "
                f"{self._expr_like_to_python(logic_obj.delay_expr)}, "
                f"{self._expr_like_to_python(logic_obj.window_expr)}, output={self._identifier_map[output_var.uid]})"
            )
        elif isinstance(logic_obj, GradientLimiterLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return (
                f"gradlim_const({self._expr_like_to_python(logic_obj.source_expr)}, "
                f"{self._expr_like_to_python(logic_obj.lower_rate_expr)}, "
                f"{self._expr_like_to_python(logic_obj.upper_rate_expr)}, output={self._identifier_map[output_var.uid]})"
            )
        elif isinstance(logic_obj, ResetOnRisingEdgeLogic):
            target_var: Var = self._find_referenced_var_by_name(logic_obj.target_var_name)
            return (
                f"reset({self._identifier_map[target_var.uid]}, "
                f"{self._expr_like_to_python(logic_obj.reset_expr)}, "
                f"{self._expr_like_to_python(logic_obj.value_expr)})"
            )
        else:
            raise TypeError(f"Unsupported procedural logic export type: {type(logic_obj).__name__}")

    def _expr_like_to_python(self, expr_obj: Expr | Comparison) -> str:
        """
        Convert one expression-like object to Python code.

        :param expr_obj: Expression-like object.
        :returns: Python expression text.
        """
        if isinstance(expr_obj, Comparison):
            rhs_text: str
            if isinstance(expr_obj.rhs, Expr):
                rhs_text = self._expr_to_python_natural(expr_obj.rhs)
            else:
                rhs_text = repr(expr_obj.rhs)

            cmp_name_by_op: dict[CmpOp, str] = dict()
            cmp_name_by_op[CmpOp.EQ] = "EQ"
            cmp_name_by_op[CmpOp.LE] = "LE"
            cmp_name_by_op[CmpOp.GE] = "GE"
            cmp_name_by_op[CmpOp.LT] = "LT"
            cmp_name_by_op[CmpOp.GT] = "GT"

            return (
                f"sym.Comparison(lhs={self._expr_to_python_natural(expr_obj.lhs)}, "
                f"op=sym.CmpOp.{cmp_name_by_op[expr_obj.op]}, rhs={rhs_text})"
            )
        else:
            return self._expr_to_python_natural(expr_obj)

    def _expr_or_const_to_python(self, expr_obj: Expr | Const) -> str:
        """
        Convert one expression-or-constant object to Python code.

        :param expr_obj: Expression-or-constant object.
        :returns: Python expression text.
        """
        if isinstance(expr_obj, Const):
            return f"vf.add_const({repr(expr_obj.value)}, name={repr(expr_obj.name)})"
        else:
            return self._expr_to_python(expr_obj)

    def _expr_to_python(self, expr_obj: Expr) -> str:
        """
        Convert one symbolic expression to Python code.

        :param expr_obj: Symbolic expression.
        :returns: Python expression text.
        """
        if isinstance(expr_obj, Var):
            return self._identifier_map[expr_obj.uid]
        elif isinstance(expr_obj, Const):
            return f"sym.Const({repr(expr_obj.value)})"
        elif isinstance(expr_obj, Func2):
            return f"sym.{expr_obj.name}({self._expr_to_python(expr_obj.arg1)}, {self._expr_to_python(expr_obj.arg2)})"
        else:
            pass

        from VeraGridEngine.Utils.Symbolic.symbolic import BinOp
        from VeraGridEngine.Utils.Symbolic.symbolic import Func
        from VeraGridEngine.Utils.Symbolic.symbolic import UnOp

        if isinstance(expr_obj, BinOp):
            return f"({self._expr_to_python(expr_obj.left)} {expr_obj.op} {self._expr_to_python(expr_obj.right)})"
        elif isinstance(expr_obj, UnOp):
            return f"({expr_obj.op}{self._expr_to_python(expr_obj.operand)})"
        elif isinstance(expr_obj, Func):
            return f"sym.{expr_obj.op}({self._expr_to_python(expr_obj.arg)})"
        else:
            raise TypeError(f"Unsupported expression type for catalog export: {type(expr_obj).__name__}")

    def _expr_to_python_natural(self, expr_obj: Expr) -> str:
        """
        Convert one symbolic expression to more compact Python code.

        :param expr_obj: Symbolic expression.
        :returns: Python expression text.
        """
        if isinstance(expr_obj, Var):
            return self._identifier_map[expr_obj.uid]
        elif isinstance(expr_obj, Const):
            return repr(expr_obj.value)
        elif isinstance(expr_obj, (bool, float, int)):
            return repr(expr_obj)
        elif isinstance(expr_obj, Func2):
            return f"sym.{expr_obj.name}({self._expr_to_python_natural(expr_obj.arg1)}, {self._expr_to_python_natural(expr_obj.arg2)})"
        else:
            pass

        from VeraGridEngine.Utils.Symbolic.symbolic import BinOp
        from VeraGridEngine.Utils.Symbolic.symbolic import Func
        from VeraGridEngine.Utils.Symbolic.symbolic import UnOp

        if isinstance(expr_obj, BinOp):
            return f"({self._expr_to_python_natural(expr_obj.left)} {expr_obj.op} {self._expr_to_python_natural(expr_obj.right)})"
        elif isinstance(expr_obj, UnOp):
            return f"({expr_obj.op}{self._expr_to_python_natural(expr_obj.operand)})"
        elif isinstance(expr_obj, Func):
            return f"sym.{expr_obj.op}({self._expr_to_python_natural(expr_obj.arg)})"
        else:
            raise TypeError(f"Unsupported expression type for natural catalog export: {type(expr_obj).__name__}")

    def _find_local_var_by_name(self, var_name: str) -> Var:
        """
        Return the local variable that matches one emitted variable name.

        :param var_name: Expected variable name.
        :returns: Matching variable.
        :raises KeyError: Raised when the variable is not found.
        """
        vars_list: list[Var] = list()
        vars_list.extend(list(self._block.state_vars))
        vars_list.extend(list(self._block.algebraic_vars))
        vars_list.extend(list(self._block.diff_vars))
        vars_list.extend(list(self._block.in_vars))
        vars_list.extend(list(self._block.out_vars))
        vars_list.extend(list(self._block.event_dict.keys()))
        vars_list.extend(list(self._block.mode_dict.keys()))
        var_obj: Var

        for var_obj in vars_list:
            if var_obj.name == var_name:
                return var_obj
            else:
                pass

        raise KeyError(f"Variable '{var_name}' not found in emitted block '{self._block.name}'")

    def _find_var_by_name_from_candidates(self,
                                          var_name: str,
                                          vars_found: dict[int, Var]) -> Var:
        """
        Return one referenced variable from the partially collected uid map or local surface.

        :param var_name: Expected variable name.
        :param vars_found: Partially collected referenced variables.
        :returns: Matching variable.
        :raises KeyError: Raised when the variable cannot be resolved.
        """
        candidate_var: Var
        for candidate_var in vars_found.values():
            if candidate_var.name == var_name:
                return candidate_var
            else:
                pass

        return self._find_local_var_by_name(var_name)

    def _find_referenced_var_by_name(self, var_name: str) -> Var:
        """
        Return one referenced variable from the final referenced-variable map.

        :param var_name: Expected variable name.
        :returns: Matching variable.
        :raises KeyError: Raised when the variable cannot be resolved.
        """
        return self._find_var_by_name_from_candidates(var_name, self._referenced_vars_by_uid)

    def _safe_name(self, name: str) -> str:
        """
        Convert one symbolic variable name into a safe Python identifier.

        :param name: Raw symbolic name.
        :returns: Safe Python identifier.
        """
        cleaned_name: str = re.sub(r"[^0-9a-zA-Z_]", "_", name)
        cleaned_name = re.sub(r"_+", "_", cleaned_name).strip("_")

        if cleaned_name == "":
            cleaned_name = "unnamed"
        else:
            pass

        if cleaned_name[0].isdigit():
            cleaned_name = f"v_{cleaned_name}"
        else:
            pass

        return cleaned_name

    def _build_runtime_free_var_name(self, var_name: str) -> str:
        """
        Remove the current runtime suffix from one materialized variable name.

        :param var_name: Materialized variable name.
        :returns: Runtime-free variable name.
        """
        suffix: str = f"_{self._default_template_name}"

        if var_name.endswith(suffix):
            return var_name[: -len(suffix)]
        else:
            return var_name

    def _var_sort_key(self, var_obj: Var) -> str:
        """
        Build the deterministic sort key for one symbolic variable.

        :param var_obj: Symbolic variable.
        :returns: Sort key.
        """
        return self._build_runtime_free_var_name(var_obj.name)


def _build_template_from_descriptor(descriptor: BasicBlockTemplateDescriptor) -> EmtModelTemplate:
    """
    Materialize one EMT template from the static generated package registry.

    :param descriptor: Catalog descriptor for the requested module.
    :returns: Materialized EMT template.
    :raises KeyError: Raised when the generated package registry does not expose the descriptor module.
    """
    template_builder: BasicBlockCatalogTemplateBuilder | None = (
        get_basic_block_catalog_template_builder_by_module_name(descriptor.module_name)
    )

    if template_builder is None:
        raise KeyError(f"Could not resolve standalone template builder for module '{descriptor.module_name}'")
    else:
        return template_builder(VarFactory())


def _sanitize_display_name(default_template_name: str) -> str:
    """
    Remove the imported type suffix from one default template name.

    :param default_template_name: Default runtime template name.
    :returns: Clean display name.
    """
    return re.sub(r"__\d+$", "", default_template_name).strip()


def render_basic_block_catalog_functions_package_init() -> str:
    """
    Render the static package registry for every generated basic-block builder.

    :returns: ``Functions/__init__.py`` source text.
    """
    lines: list[str] = list()
    descriptors: Sequence[BasicBlockTemplateDescriptor] = get_basic_block_catalog_descriptors()
    descriptor: BasicBlockTemplateDescriptor

    lines.append("# This Source Code Form is subject to the terms of the Mozilla Public")
    lines.append("# License, v. 2.0. If a copy of the MPL was not distributed with this")
    lines.append("# file, You can obtain one at https://mozilla.org/MPL/2.0/.")
    lines.append("# SPDX-License-Identifier: MPL-2.0")
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from functools import lru_cache")
    lines.append("from typing import Callable")
    lines.append("")
    lines.append("from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate")
    lines.append("from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory")

    for descriptor in descriptors:
        template_builder_name: str = build_basic_block_catalog_template_builder_name(descriptor.module_name)
        lines.append(
            "from VeraGridEngine.Templates.BasicBlockCatalog.Functions."
            f"{descriptor.module_name} import {template_builder_name}"
        )

    lines.append("")
    lines.append("BasicBlockCatalogTemplateBuilder = Callable[[VarFactory, str | None], EmtModelTemplate]")
    lines.append("")
    lines.append("@lru_cache(maxsize=1)")
    lines.append("def get_basic_block_catalog_template_builders_by_module_name() -> dict[str, BasicBlockCatalogTemplateBuilder]:")
    lines.append("    \"\"\"")
    lines.append("    Return the static template-builder lookup indexed by standalone module name.")
    lines.append("")
    lines.append("    :returns: Template-builder lookup.")
    lines.append("    \"\"\"")
    lines.append("    builders_by_module_name: dict[str, BasicBlockCatalogTemplateBuilder] = dict()")
    lines.append("")
    lines.append("    # The package imports each generated builder explicitly so the catalog runtime")
    lines.append("    # can resolve templates without wildcard imports or filesystem probing.")

    for descriptor in descriptors:
        template_builder_name = build_basic_block_catalog_template_builder_name(descriptor.module_name)
        lines.append(f"    builders_by_module_name['{descriptor.module_name}'] = {template_builder_name}")

    lines.append("")
    lines.append("    return builders_by_module_name")
    lines.append("")
    lines.append("def get_basic_block_catalog_template_builder_by_module_name(")
    lines.append("    module_name: str,")
    lines.append(") -> BasicBlockCatalogTemplateBuilder | None:")
    lines.append("    \"\"\"")
    lines.append("    Return one generated template builder by standalone module name.")
    lines.append("")
    lines.append("    :param module_name: Standalone module stem.")
    lines.append("    :returns: Matching template builder or ``None`` when the registry does not expose it.")
    lines.append("    \"\"\"")
    lines.append("    builders_by_module_name: dict[str, BasicBlockCatalogTemplateBuilder] = (")
    lines.append("        get_basic_block_catalog_template_builders_by_module_name()")
    lines.append("    )")
    lines.append("    template_builder: BasicBlockCatalogTemplateBuilder | None = builders_by_module_name.get(module_name, None)")
    lines.append("")
    lines.append("    if template_builder is None:")
    lines.append("        return None")
    lines.append("    else:")
    lines.append("        return template_builder")
    lines.append("")

    return "\n".join(lines) + "\n"


def rewrite_basic_block_catalog_functions_package_init(output_directory: Path | None = None) -> Path:
    """
    Rewrite the static package registry that exposes every generated basic-block builder.

    :param output_directory: Optional destination directory.
    :returns: Path to the rewritten package init file.
    """
    target_directory: Path

    if output_directory is None:
        target_directory = get_basic_block_catalog_templates_dir()
    else:
        target_directory = output_directory

    target_directory.mkdir(parents=True, exist_ok=True)
    target_path: Path = target_directory / "__init__.py"
    target_path.write_text(render_basic_block_catalog_functions_package_init(), encoding="utf-8")
    return target_path


def rewrite_basic_block_catalog_template_module(template_key: str,
                                                       output_directory: Path | None = None) -> Path:
    """
    Rewrite one standalone catalog module using the clean emitter.

    :param template_key: Stable catalog template key.
    :param output_directory: Optional destination directory.
    :returns: Path to the rewritten module.
    """
    descriptor: BasicBlockTemplateDescriptor = get_basic_block_catalog_descriptor_by_key()[template_key]
    template: EmtModelTemplate = _build_template_from_descriptor(descriptor)
    emitter: BasicBlockStandaloneModuleEmitter = BasicBlockStandaloneModuleEmitter(
        block=template.block,
        display_name=_sanitize_display_name(template.name),
        module_name=descriptor.module_name,
        default_template_name=template.name,
    )
    target_directory: Path

    if output_directory is None:
        target_directory = get_basic_block_catalog_templates_dir()
    else:
        target_directory = output_directory

    target_directory.mkdir(parents=True, exist_ok=True)
    target_path: Path = target_directory / descriptor.module_filename
    target_path.write_text(emitter.render(), encoding="utf-8")
    return target_path


def rewrite_basic_block_catalog_standalone_modules(output_directory: Path | None = None) -> Sequence[Path]:
    """
    Rewrite every standalone catalog module using the clean emitter.

    :param output_directory: Optional destination directory.
    :returns: Written module paths.
    """
    target_directory: Path
    descriptors: Sequence[BasicBlockTemplateDescriptor] = get_basic_block_catalog_descriptors()
    descriptor: BasicBlockTemplateDescriptor
    written_paths: list[Path] = list()

    if output_directory is None:
        target_directory = get_basic_block_catalog_templates_dir()
    else:
        target_directory = output_directory

    # The modules must be rewritten before the package registry so the final
    # explicit imports always point at builders that already exist on disk.
    for descriptor in descriptors:
        written_paths.append(rewrite_basic_block_catalog_template_module(descriptor.template_key, target_directory))

    written_paths.append(rewrite_basic_block_catalog_functions_package_init(target_directory))
    return tuple(written_paths)
