# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Modal editor for one symbolic block in the Dynamic Model Editor."""

from __future__ import annotations

import ast
import keyword
from enum import Enum
from io import StringIO
import re
import tokenize
from typing import Dict, List, Mapping, Sequence

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal

import VeraGrid.Gui.gui_functions as gf
from VeraGrid.Gui.base_python_code_editor import BasePythonCodeEditor
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.dae_code_completion import (
    DaeCompletionEntry,
    DaeCompletionPosition,
    DaeLanguageContext,
    analyze_dae_completion_position,
    build_dae_completion_entries,
    build_generic_dae_language_context,
    get_dae_section_names,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.dae_code_linter import (
    DaeCodeDiagnostic,
    build_dae_code_diagnostics,
    build_semantic_dae_diagnostic,
    normalize_algebraic_equality_syntax,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.dynamic_block_properties_gui import (
    Ui_DynamicBlockPropertiesDialog,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.add_symbol_dialog import (
    AddSymbolDialog,
    AddSymbolSelection,
)
from VeraGrid.Gui.toast_widget import ToastManager
from VeraGrid.Gui.dialog_lifecycle import (
    exec_dialog_safely,
)
from VeraGridEngine.enumerations import (
    BlockType,
    BlockSymbolCategory,
    BlockSymbolKind,
    EquationExportSection,
    ParamPowerFlowReferenceType,
    ProceduralLogicType,
    ShuntConnectionType,
    VarPowerFlowReferenceType,
    WindingType,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.dynamic_equation_pdf import (
    EquationExportEntry,
    build_equation_pdf_suggested_name,
    build_latex_source,
    build_list_equation_entries,
    build_mapping_equation_entries,
    build_state_equation_entries,
    order_state_differential_variables,
    write_equation_pdf,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.dynamic_procedural_logic import (
    RuntimeLogicDraftCollection,
    RuntimeLogicValidationResult,
    RuntimeModeDraft,
    build_procedural_logic_call_lines,
    build_runtime_code_signature,
    build_runtime_logic_code,
    build_runtime_logic_drafts_from_code,
    get_model_code_assignment,
    get_procedural_expression_variables,
    get_procedural_logic_help_by_code_name,
    parse_model_code_module,
)
from VeraGridEngine.Utils.procedural_logic import ProceduralLogicBase
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.ProceduralLogicCatalog import (
    ProceduralBlockTemplateDescriptor,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_library import (
    get_dynamic_library_procedural_descriptors,
)
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import (
    BinOp,
    Comparison,
    Const,
    Expr,
    UnOp,
    Var,
    get_expression_vars,
    get_symbolic_parser_function_arity,
    get_symbolic_parser_function_names,
    string_to_symbolic,
    symbolic_to_string,
)


class BlockEquationDraft:
    """Validated, detached set of equations waiting to be applied to a block."""

    __slots__ = (
        "_state_eqs",
        "_algebraic_eqs",
        "_init_eqs",
        "_diff_init_eqs",
        "_variable_declarations",
    )

    def __init__(self,
                 state_eqs: Sequence[Expr],
                 algebraic_eqs: Sequence[Expr],
                 init_eqs: Mapping[Var, Expr],
                 diff_init_eqs: Mapping[Var, Expr],
                 variable_declarations: Mapping[str, Sequence[Var]] | None = None) -> None:
        """
        Create a detached draft from already parsed symbolic expressions.

        :param state_eqs: Value supplied for ``state_eqs``.
        :param algebraic_eqs: Value supplied for ``algebraic_eqs``.
        :param init_eqs: Value supplied for ``init_eqs``.
        :param diff_init_eqs: Value supplied for ``diff_init_eqs``.
        :param variable_declarations: Informative ordered DAE variable lists.
        :return: None.
        """
        self._state_eqs: List[Expr] = list(state_eqs)
        self._algebraic_eqs: List[Expr] = list(algebraic_eqs)
        self._init_eqs: Dict[Var, Expr] = dict(init_eqs)
        self._diff_init_eqs: Dict[Var, Expr] = dict(diff_init_eqs)
        self._variable_declarations: Dict[str, List[Var]] = dict()
        if variable_declarations is not None:
            declaration_name: str
            declaration_variables: Sequence[Var]
            for declaration_name, declaration_variables in variable_declarations.items():
                self._variable_declarations[declaration_name] = list(declaration_variables)
        else:
            pass

    def get_state_eqs(self) -> List[Expr]:
        """
        :return: A copy of the state equations.
        """
        return list(self._state_eqs)

    def get_algebraic_eqs(self) -> List[Expr]:
        """
        :return: A copy of the algebraic equations.
        """
        return list(self._algebraic_eqs)

    def get_init_eqs(self) -> Dict[Var, Expr]:
        """
        :return: A copy of the initialization equations.
        """
        return dict(self._init_eqs)

    def get_diff_init_eqs(self) -> Dict[Var, Expr]:
        """
        :return: A copy of the derivative initialization equations.
        """
        return dict(self._diff_init_eqs)

    def get_variable_declaration(self, section_name: str) -> List[Var] | None:
        """Return one optional generated variable-order declaration.

        :param section_name: One of ``state_vars``, ``algebraic_vars`` or ``diff_vars``.
        :return: Declared variables, or ``None`` when older source omitted the section.
        """
        variables: List[Var] | None = self._variable_declarations.get(section_name, None)
        if variables is not None:
            return list(variables)
        else:
            return None


def is_finite_real_number_text(value: object) -> bool:
    """Return whether a value can be parsed as a finite real number.

    :param value: Edited value supplied by Qt.
    :return: ``True`` when the value is a finite real number.
    """
    value_text: str = str(value).strip()
    if len(value_text) == 0:
        result: bool = False
    else:
        try:
            numeric_value: float = float(value_text)
            result = (
                numeric_value != float("inf")
                and numeric_value != float("-inf")
                and numeric_value == numeric_value
            )
        except (TypeError, ValueError):
            result = False
    return result


class ParameterDraftRow:
    """One static value or event expression staged without mutating its block."""

    __slots__ = (
        "_category",
        "_owner",
        "_variable",
        "_expression",
        "_kind",
        "_original_text",
        "_draft_text",
    )

    def __init__(self,
                 category: str,
                 owner: Block,
                 variable: Var,
                 expression: Expr,
                 kind: BlockSymbolKind) -> None:
        """Capture one parameter mapping as an editable textual draft.

        Static parameters retain their numeric-only contract. Event parameters
        retain their complete symbolic expression so initialization references
        are not hidden or flattened to artificial constants by the dialogue.

        :param category: User-facing parameter category.
        :param owner: Block containing the parameter mapping.
        :param variable: Parameter variable used as the mapping key.
        :param expression: Current static value or event initialization expression.
        :param kind: Static or event parameter role.
        :return: None.
        """
        self._category: str = category
        self._owner: Block = owner
        self._variable: Var = variable
        self._expression: Expr = expression
        self._kind: BlockSymbolKind = kind
        if isinstance(expression, Const):
            expression_text: str = str(expression.value)
        else:
            expression_text = symbolic_to_string(expression)
        self._original_text: str = expression_text
        self._draft_text: str = expression_text

    def get_category(self) -> str:
        """
        :return: The user-facing parameter category.
        """
        return self._category

    def get_variable(self) -> Var:
        """
        :return: The parameter variable.
        """
        return self._variable

    def get_owner(self) -> Block:
        """
        :return: Block containing the staged parameter mapping.
        """
        return self._owner

    def get_kind(self) -> BlockSymbolKind:
        """
        :return: Static or event parameter role represented by the row.
        """
        return self._kind

    def get_expression(self) -> Expr:
        """
        :return: Original expression represented by the row.
        """
        return self._expression

    def get_draft_text(self) -> str:
        """
        :return: The pending textual value.
        """
        return self._draft_text

    def set_draft_text(self, value: str) -> None:
        """
        Set the pending textual value without touching the source block.

        :param value: Value supplied for ``value``.
        :return: None.
        """
        self._draft_text = value

    def rename_identifier(self, old_name: str, new_name: str) -> None:
        """Rename one symbol in both the draft and its applied baseline.

        Existing-symbol renames are applied immediately by the owning Dynamic
        Editor. Updating both texts preserves any independent value edit while
        preventing the already-applied rename from becoming a false dirty
        state in Block Properties.

        :param old_name: Identifier that was present before the central rename.
        :param new_name: Authoritative identifier after the rename.
        :return: None.
        """
        self._draft_text = replace_dae_identifier(
            self._draft_text,
            old_name,
            new_name,
        )
        self._original_text = replace_dae_identifier(
            self._original_text,
            old_name,
            new_name,
        )

    def parse_value(self) -> float | complex:
        """
        Parse the pending value as a finite real or complex number.

        :return: Pending value parsed as a finite real or complex number.
        """
        value_text: str = self._draft_text.strip()
        if len(value_text) == 0:
            raise ValueError(f"Parameter '{self._variable.name}' cannot be empty")
        else:
            pass

        if "j" in value_text.lower():
            parsed_value: float | complex = complex(value_text)
        else:
            parsed_value = float(value_text)

        if isinstance(parsed_value, complex):
            if parsed_value.real == float("inf") or parsed_value.real == float("-inf"):
                raise ValueError(f"Parameter '{self._variable.name}' must be finite")
            elif parsed_value.imag == float("inf") or parsed_value.imag == float("-inf"):
                raise ValueError(f"Parameter '{self._variable.name}' must be finite")
            elif parsed_value.real != parsed_value.real or parsed_value.imag != parsed_value.imag:
                raise ValueError(f"Parameter '{self._variable.name}' must be finite")
            else:
                pass
        else:
            if parsed_value == float("inf") or parsed_value == float("-inf") or parsed_value != parsed_value:
                raise ValueError(f"Parameter '{self._variable.name}' must be finite")
            else:
                pass
        return parsed_value

    def parse_event_expression(self, namespace: Mapping[str, Expr]) -> Expr:
        """Parse one event-parameter value or symbolic initialization expression.

        :param namespace: Explicit symbolic identities accepted in the expression.
        :return: Parsed scalar symbolic expression.
        :raises ValueError: If the text is empty, unset, boolean, comparative, or non-real.
        """
        value_text: str = self._draft_text.strip()
        if len(value_text) == 0:
            raise ValueError(f"Event parameter '{self._variable.name}' cannot be empty")
        elif value_text.lower() == "none":
            raise ValueError(
                f"Event parameter '{self._variable.name}' requires a numeric value, "
                "an expression, or an unchanged external initialization mapping"
            )
        else:
            parsed_expression: Expr | Comparison = string_to_symbolic(value_text, namespace)

        # Python represents a negative numeric literal as a unary operation.
        # Normalize that parser detail so a signed scalar remains a Const and
        # follows the same event-parameter contract as an unsigned scalar.
        if isinstance(parsed_expression, UnOp):
            parsed_expression = parsed_expression.simplify()
        else:
            pass

        if isinstance(parsed_expression, Comparison):
            raise ValueError(
                f"Event parameter '{self._variable.name}' requires a scalar expression"
            )
        elif isinstance(parsed_expression, Const):
            constant_value: object = parsed_expression.value
            if isinstance(constant_value, bool) or not isinstance(constant_value, (int, float)):
                raise ValueError(
                    f"Event parameter '{self._variable.name}' requires a real numeric value"
                )
            else:
                numeric_value: float = float(constant_value)
            if numeric_value == float("inf") or numeric_value == float("-inf") or numeric_value != numeric_value:
                raise ValueError(f"Event parameter '{self._variable.name}' must be finite")
            else:
                pass
        else:
            pass
        return parsed_expression

    def has_changes(self) -> bool:
        """
        :return: Whether the staged text differs from the loaded expression.
        """
        return self._draft_text.strip() != self._original_text.strip()

    def is_unchanged_unset(self) -> bool:
        """Return whether an originally unset constant remains unset.

        :return: ``True`` for an unchanged ``Const(None)`` draft.
        """
        return (
            isinstance(self._expression, Const)
            and self._expression.value is None
            and self._draft_text.strip().lower() == "none"
        )


class BlockStructuralEditRequest:
    """Synchronous request for an editor-owned structural block rebuild."""

    __slots__ = (
        "_block",
        "_block_type",
        "_builder",
        "_parameter_values",
        "_success",
        "_error_message",
    )

    def __init__(self,
                 block: Block,
                 block_type: BlockType,
                 builder: TemplateDefinition,
                 parameter_values: Sequence[tuple[str, float | complex]]) -> None:
        """Capture the candidate builder and mutable operation result.

        :param block: Existing working-tree block to rebuild in place.
        :param block_type: Native type controlling the builder.
        :param builder: Builder containing the validated draft options.
        :param parameter_values: Numeric values to transfer by semantic name.
        :return: None.
        """
        self._block: Block = block
        self._block_type: BlockType = block_type
        self._builder: TemplateDefinition = builder
        self._parameter_values: List[tuple[str, float | complex]] = list(parameter_values)
        self._success: bool = False
        self._error_message: str = ""

    def get_block(self) -> Block:
        """
        :return: The existing block targeted by the rebuild.
        """
        return self._block

    def get_block_type(self) -> BlockType:
        """
        :return: The native builder type.
        """
        return self._block_type

    def get_builder(self) -> TemplateDefinition:
        """
        :return: The configured template builder.
        """
        return self._builder

    def get_parameter_values(self) -> List[tuple[str, float | complex]]:
        """
        :return: Numeric parameter values that must survive reconstruction.
        """
        return list(self._parameter_values)

    def set_result(self, success: bool, error_message: str) -> None:
        """Store the result produced synchronously by the owning editor.

        :param success: Whether reconstruction completed.
        :param error_message: User-facing failure detail.
        :return: None.
        """
        self._success = success
        self._error_message = error_message

    def is_successful(self) -> bool:
        """
        Return whether the owning editor completed the rebuild.

        :return: Whether the owning editor completed the rebuild.
        """
        return self._success

    def get_error_message(self) -> str:
        """
        Return the editor-provided failure detail.

        :return: The editor-provided failure detail.
        """
        return self._error_message


class BlockVariableRenameRequest:
    """Synchronous request for an editor-owned complete variable rename."""

    __slots__ = (
        "_variable",
        "_requested_name",
        "_success",
        "_new_name",
    )

    def __init__(self, variable: Var, requested_name: str) -> None:
        """Create a pending rename request for one existing symbolic variable.

        :param variable: Existing variable selected in Block Properties.
        :param requested_name: Candidate name entered directly in the property tree.
        :return: None.
        """
        self._variable: Var = variable
        self._requested_name: str = requested_name
        self._success: bool = False
        self._new_name: str = variable.name

    def get_variable(self) -> Var:
        """
        :return: Existing variable targeted by the rename.
        """
        return self._variable

    def get_requested_name(self) -> str:
        """Return the candidate entered in the inline Name editor.

        :return: Candidate symbolic name requested by Block Properties.
        """
        return self._requested_name

    def set_result(self, success: bool, new_name: str) -> None:
        """Store the synchronous result produced by the owning editor.

        :param success: Whether the complete rename was applied.
        :param new_name: Final accepted variable name.
        :return: None.
        """
        self._success = success
        self._new_name = new_name

    def is_successful(self) -> bool:
        """
        :return: Whether the complete rename was applied.
        """
        return self._success

    def get_new_name(self) -> str:
        """
        :return: Final accepted variable name.
        """
        return self._new_name


class BlockStructuralSettingsModel(QtCore.QAbstractTableModel):
    """Editable draft of builder inputs that alter generated block structure."""

    __slots__ = ("_properties", "_original_values")

    def __init__(self,
                 properties: Sequence[TemplateProp],
                 parent: QtCore.QObject | None = None) -> None:
        """Capture visible structural properties without touching the block.

        :param properties: Builder properties shown in this table.
        :param parent: Owning Qt object.
        :return: None.
        """
        super().__init__(parent)
        self._properties: List[TemplateProp] = list(properties)
        self._original_values: List[str] = [repr(prop.value) for prop in self._properties]

    def reload(self, properties: Sequence[TemplateProp]) -> None:
        """Refresh builder values and their clean baseline after a successful Apply.

        :param properties: Current general or special properties of the builder.
        :return: None.
        """
        self.beginResetModel()
        self._properties = list(properties)
        self._original_values = list(repr(prop.value) for prop in self._properties)
        self.endResetModel()

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """
        :param parent: Owning Qt widget.
        :return: The number of structural settings.
        """
        if parent.isValid():
            return 0
        else:
            return len(self._properties)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """
        :param parent: Owning Qt widget.
        :return: Setting and value columns.
        """
        if parent.isValid():
            return 0
        else:
            return 2

    def data(self, index: QtCore.QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        """
        :param index: Value supplied for ``index``.
        :param role: Value supplied for ``role``.
        :return: One setting name or draft value.
        """
        if not index.isValid() or index.row() >= len(self._properties):
            return None
        else:
            prop: TemplateProp = self._properties[index.row()]
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if index.column() == 0:
                return prop.name
            elif index.column() == 1:
                if isinstance(prop.value, Enum):
                    return prop.value.name
                else:
                    return repr(prop.value)
            else:
                return None
        elif role == Qt.ItemDataRole.ToolTipRole:
            return prop.descr
        else:
            return None

    def setData(self,
                index: QtCore.QModelIndex,
                value: object,
                role: int = Qt.ItemDataRole.EditRole) -> bool:
        """
        Parse one edited builder value according to its current type.

        :param index: Value supplied for ``index``.
        :param value: Value supplied for ``value``.
        :param role: Value supplied for ``role``.
        :return: True when the edited value was accepted; otherwise False.
        """
        if not index.isValid() or index.column() != 1 or role != Qt.ItemDataRole.EditRole:
            return False
        else:
            prop: TemplateProp = self._properties[index.row()]
            value_text: str = str(value).strip()
        try:
            parsed_value: object = parse_structural_setting_value(prop, value_text)
        except (SyntaxError, TypeError, ValueError):
            return False
        else:
            prop.value = parsed_value
            self.dataChanged.emit(index, index, list((role, Qt.ItemDataRole.DisplayRole,)))
            return True

    def flags(self, index: QtCore.QModelIndex) -> Qt.ItemFlag:
        """
        Make only the value column editable.

        :param index: Value supplied for ``index``.
        :return: Item flags that make only the value column editable.
        """
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        elif index.column() == 1:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        else:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def headerData(self,
                   section: int,
                   orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> object:
        """
        :param section: Value supplied for ``section``.
        :param orientation: Value supplied for ``orientation``.
        :param role: Value supplied for ``role``.
        :return: Structural-settings headers.
        """
        headers: tuple[str, ...] = ("Setting", "Value")
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(headers):
                return self.tr(headers[section])
            else:
                return None
        else:
            return None

    def has_changes(self) -> bool:
        """
        :return: Whether any displayed builder value differs from its baseline.
        """
        result: bool = False
        row_index: int
        for row_index in range(len(self._properties)):
            if repr(self._properties[row_index].value) != self._original_values[row_index]:
                result = True
            else:
                pass
        return result

    def get_property(self, row_index: int) -> TemplateProp | None:
        """Return one structural property for delegate editor selection.

        :param row_index: Source row index.
        :return: Matching property or ``None``.
        """
        if 0 <= row_index < len(self._properties):
            return self._properties[row_index]
        else:
            return None


class StructuralSettingDelegate(QtWidgets.QStyledItemDelegate):
    """Typed Qt editor delegate for structural builder values."""

    __slots__ = ()

    def createEditor(self,
                     parent: QtWidgets.QWidget,
                     option: QtWidgets.QStyleOptionViewItem,
                     index: QtCore.QModelIndex) -> QtWidgets.QWidget:
        """Create a combo, spin box, or text editor for one setting.

        :param parent: Owning view widget.
        :param option: Qt style option.
        :param index: Edited model index.
        :return: Typed editor widget.
        """
        _unused_option: QtWidgets.QStyleOptionViewItem = option
        model: QtCore.QAbstractItemModel | None = index.model()
        if isinstance(model, BlockStructuralSettingsModel):
            prop: TemplateProp | None = model.get_property(index.row())
        else:
            prop = None
        if prop is None:
            return QtWidgets.QLineEdit(parent)
        elif isinstance(prop.value, bool):
            bool_combo: QtWidgets.QComboBox = QtWidgets.QComboBox(parent)
            bool_combo.addItems(list(("True", "False",)))
            return bool_combo
        elif isinstance(prop.value, int):
            integer_editor: QtWidgets.QSpinBox = QtWidgets.QSpinBox(parent)
            integer_editor.setRange(0, 1000000)
            return integer_editor
        elif isinstance(prop.value, Enum):
            enum_combo: QtWidgets.QComboBox = QtWidgets.QComboBox(parent)
            enum_options: tuple[Enum, ...] = (
                tuple(prop.value.__class__)
                if prop.allowed_values is None
                else prop.allowed_values
            )
            enum_member: Enum
            for enum_member in enum_options:
                enum_combo.addItem(enum_member.name)
            return enum_combo
        elif prop.name == "connection_type" and prop.value is None:
            connection_combo: QtWidgets.QComboBox = QtWidgets.QComboBox(parent)
            connection_combo.addItem("None")
            shunt_member: ShuntConnectionType
            for shunt_member in ShuntConnectionType:
                connection_combo.addItem(shunt_member.name)
            return connection_combo
        else:
            return QtWidgets.QLineEdit(parent)

    def setEditorData(self, editor: QtWidgets.QWidget, index: QtCore.QModelIndex) -> None:
        """Load the current setting into its typed editor.

        :param editor: Active delegate editor.
        :param index: Edited model index.
        :return: None.
        """
        value_text: str = str(index.data(Qt.ItemDataRole.EditRole))
        if isinstance(editor, QtWidgets.QComboBox):
            editor.setCurrentText(value_text)
        elif isinstance(editor, QtWidgets.QSpinBox):
            editor.setValue(int(value_text))
        elif isinstance(editor, QtWidgets.QLineEdit):
            editor.setText(value_text)
        else:
            pass

    def setModelData(self,
                     editor: QtWidgets.QWidget,
                     model: QtCore.QAbstractItemModel,
                     index: QtCore.QModelIndex) -> None:
        """Commit the typed editor value into the structural draft.

        :param editor: Active delegate editor.
        :param model: Structural settings model.
        :param index: Edited model index.
        :return: None.
        """
        if isinstance(editor, QtWidgets.QComboBox):
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)
        elif isinstance(editor, QtWidgets.QSpinBox):
            model.setData(index, str(editor.value()), Qt.ItemDataRole.EditRole)
        elif isinstance(editor, QtWidgets.QLineEdit):
            model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)
        else:
            pass


def parse_structural_setting_value(prop: TemplateProp, value_text: str) -> object:
    """Parse a structural setting using its live default as the type contract.

    :param prop: Builder property being edited.
    :param value_text: User-entered text.
    :return: Typed builder value.
    """
    current_value: object = prop.value
    if prop.name == "connection_type" and current_value is None:
        if value_text.lower() == "none":
            return None
        else:
            connection_member: Enum
            for connection_member in ShuntConnectionType:
                if value_text == connection_member.name or value_text == str(connection_member.value):
                    return connection_member
                else:
                    pass
            for connection_member in WindingType:
                if value_text == connection_member.name or value_text == str(connection_member.value):
                    return connection_member
                else:
                    pass
            raise ValueError(f"Unknown connection type '{value_text}'")
    elif isinstance(current_value, bool):
        normalized: str = value_text.lower()
        if normalized == "true":
            return True
        elif normalized == "false":
            return False
        else:
            raise ValueError(f"'{value_text}' is not a boolean")
    elif isinstance(current_value, int):
        return int(value_text)
    elif isinstance(current_value, float):
        return float(value_text)
    elif isinstance(current_value, Enum):
        enum_options: tuple[Enum, ...] = (
            tuple(current_value.__class__)
            if prop.allowed_values is None
            else prop.allowed_values
        )
        enum_member: Enum
        for enum_member in enum_options:
            if value_text == enum_member.name or value_text == str(enum_member.value):
                return enum_member
            else:
                pass
        raise ValueError(f"Unknown option '{value_text}' for {prop.name}")
    elif isinstance(current_value, (tuple, list)):
        parsed_literal: object = ast.literal_eval(value_text)
        if isinstance(parsed_literal, (tuple, list)):
            return parsed_literal
        else:
            raise ValueError(f"'{prop.name}' requires a sequence")
    elif isinstance(current_value, str):
        return value_text
    else:
        raise ValueError(f"Unsupported structural setting '{prop.name}'")


def disconnect_qobject_from_receiver(sender: QtCore.QObject | None,
                                     receiver: QtCore.QObject) -> None:
    """Disconnect all signals from one sender to one receiver when possible.

    :param sender: Qt signal owner.
    :param receiver: Qt object that owns the receiving slots.
    :return: None.
    """
    if sender is not None:
        try:
            sender.disconnect(receiver)
        except (RuntimeError, TypeError):
            pass
    else:
        pass


def split_structural_template_properties(builder: TemplateDefinition) -> tuple[List[TemplateProp], List[TemplateProp]]:
    """Split simple general options from complex special settings.

    Numeric parameter values are intentionally excluded because the General
    Options parameter table is their single authoritative editor.

    :param builder: Builder whose inputs are classified.
    :return: Pair of simple and complex structural property lists.
    """
    general_properties: List[TemplateProp] = list()
    special_properties: List[TemplateProp] = list()
    dedicated_special_tab: bool = "jmarti" in builder.__class__.__name__.lower()
    prop: TemplateProp
    for prop in builder.params:
        value: object = prop.value
        if prop.name == "name" or isinstance(value, (complex, dict)):
            pass
        elif dedicated_special_tab:
            # JMarti's former creation dialog contained boolean, integer,
            # floating-point, enum and file-path fields. They all belong to the
            # dedicated tab, not only its phase switches.
            special_properties.append(prop)
        elif prop.name == "connection_type" and value is None:
            general_properties.append(prop)
        elif value is None:
            pass
        elif isinstance(value, (tuple, list)):
            special_properties.append(prop)
        elif isinstance(value, (bool, int, Enum)):
            general_properties.append(prop)
        else:
            pass
    return general_properties, special_properties


class BlockSymbolDraftRow:
    """Detached description of one existing or newly requested block symbol."""

    __slots__ = (
        "_owner",
        "_variable",
        "_name",
        "_kind",
        "_original_kind",
        "_exported",
        "_value_text",
        "_original_value_text",
        "_external_reference",
        "_static_reference",
        "_original_external_reference",
        "_original_static_reference",
        "_derivative_base_row",
    )

    def __init__(self,
                 owner: Block,
                 variable: Var | None,
                 name: str,
                 kind: BlockSymbolKind,
                 exported: bool,
                 value_text: str,
                 external_reference: VarPowerFlowReferenceType | None = None,
                 static_reference: ParamPowerFlowReferenceType | None = None,
                 derivative_base_row: "BlockSymbolDraftRow | None" = None) -> None:
        """
        Capture a symbol row without modifying its owner block.

        :param owner: Value supplied for ``owner``.
        :param variable: Symbolic variable used by the operation.
        :param name: Value supplied for ``name``.
        :param kind: Value supplied for ``kind``.
        :param exported: Value supplied for ``exported``.
        :param value_text: Value supplied for ``value_text``.
        :param external_reference: Value supplied for ``external_reference``.
        :param static_reference: Value supplied for ``static_reference``.
        :param derivative_base_row: Value supplied for ``derivative_base_row``.
        :return: None.
        """
        self._owner: Block = owner
        self._variable: Var | None = variable
        self._name: str = name
        self._kind: BlockSymbolKind = kind
        self._original_kind: BlockSymbolKind = kind
        self._exported: bool = exported and kind != BlockSymbolKind.INPUT
        self._value_text: str = value_text
        self._original_value_text: str = value_text
        self._derivative_base_row: BlockSymbolDraftRow | None = derivative_base_row
        if static_reference is not None:
            # Keep every API-parameter mapping visible even when its current
            # symbol role is invalid. Validation can then distinguish supported
            # runtime references from misplaced parent/child static mappings.
            self._external_reference: VarPowerFlowReferenceType | None = None
            self._static_reference: ParamPowerFlowReferenceType | None = static_reference
        elif self.supports_external_reference():
            self._external_reference = external_reference
            self._static_reference = None
        elif self.supports_static_reference():
            self._external_reference = None
            self._static_reference = static_reference
        else:
            self._external_reference = None
            self._static_reference = None
        # Mapping edits are transactional. Preserve their opening values so a
        # structural rebuild cannot silently discard an independently staged
        # interface change.
        self._original_external_reference: VarPowerFlowReferenceType | None = self._external_reference
        self._original_static_reference: ParamPowerFlowReferenceType | None = self._static_reference

    def get_owner(self) -> Block:
        """
        :return: The block that owns this symbol.
        """
        return self._owner

    def get_variable(self) -> Var | None:
        """
        :return: The existing variable or ``None`` for a staged addition.
        """
        return self._variable

    def set_variable(self, variable: Var) -> None:
        """Bind the authoritative variable created when the draft is applied.

        :param variable: Variable identity registered by ``VarFactory``.
        :return: None.
        """
        self._variable = variable

    def get_name(self) -> str:
        """
        Return the symbol name.

        :return: The symbol name.
        """
        return self._name

    def set_name(self, name: str) -> None:
        """
        Set the name of a staged new symbol.

        :param name: Value supplied for ``name``.
        :return: None.
        """
        self._name = name

    def get_kind(self) -> BlockSymbolKind:
        """
        Return the selected primary symbol role.

        :return: The selected primary symbol role.
        """
        return self._kind

    def set_kind(self, kind: BlockSymbolKind) -> None:
        """
        Set the selected primary symbol role.

        :param kind: Value supplied for ``kind``.
        :return: None.
        """
        self._kind = kind
        if self.supports_external_reference():
            self._static_reference = None
        elif self.supports_static_reference():
            self._external_reference = None
        else:
            self._external_reference = None
            self._static_reference = None

    def get_original_kind(self) -> BlockSymbolKind:
        """
        Return the primary role captured when the dialogue opened.

        :return: The primary role captured when the dialogue opened.
        """
        return self._original_kind

    def is_exported(self) -> bool:
        """
        Return whether the variable is independently exposed as an output.

        :return: Whether the variable is independently exposed as an output.
        """
        return self._exported

    def set_exported(self, exported: bool) -> None:
        """
        Set the staged output-export role.

        :param exported: Value supplied for ``exported``.
        :return: None.
        """
        self._exported = exported

    def is_new(self) -> bool:
        """
        Return whether the row represents a symbol not yet in VarFactory.

        :return: Whether the row represents a symbol not yet in VarFactory.
        """
        return self._variable is None

    def get_derivative_name(self) -> str:
        """
        Return the conventional derivative name for a staged state.

        :return: The conventional derivative name for a staged state.
        """
        return f"d_{self._name}"

    def get_derivative_base_row(self) -> "BlockSymbolDraftRow | None":
        """Return the staged state row associated with this derivative.

        :return: State draft used as the derivative's ``base_var``.
        """
        return self._derivative_base_row

    def get_static_reference(self) -> ParamPowerFlowReferenceType | None:
        """
        :return: The selected device static-parameter mapping, if any.
        """
        return self._static_reference

    def set_static_reference(self, reference: ParamPowerFlowReferenceType | None) -> None:
        """Stage one device static-parameter mapping.

        :param reference: Static mapping or ``None``.
        :return: None.
        """
        self._static_reference = reference
        if reference is not None:
            self._external_reference = None
        else:
            pass

    def get_external_reference(self) -> VarPowerFlowReferenceType | None:
        """
        Return the staged power-flow initialization mapping.

        :return: The staged power-flow initialization mapping.
        """
        return self._external_reference

    def set_external_reference(self, reference: VarPowerFlowReferenceType | None) -> None:
        """Stage one power-flow initialization mapping.

        :param reference: Power-flow mapping or ``None``.
        :return: None.
        """
        self._external_reference = reference
        if reference is not None:
            self._static_reference = None
        else:
            pass

    def supports_static_reference(self) -> bool:
        """
        :return: Whether this parameter can receive a device-backed initial value.
        """
        return self._kind in (
            BlockSymbolKind.PARAMETER,
            BlockSymbolKind.EVENT_PARAMETER,
        )

    def supports_external_reference(self) -> bool:
        """
        :return: Whether this row can be initialized from power-flow data.
        """
        return self._kind not in (
            BlockSymbolKind.PARAMETER,
            BlockSymbolKind.EVENT_PARAMETER,
            BlockSymbolKind.MODE_PARAMETER,
            BlockSymbolKind.INPUT,
        )

    def kind_supports_export(self) -> bool:
        """
        :return: Whether this primary role can also be an output.
        """
        # Inputs already belong to the incoming interface. Exposing the same
        # identity in the outgoing interface is ambiguous in both the table and
        # the graphics connection model, so only block-owned variables can be
        # exported.
        return self._kind not in (
            BlockSymbolKind.PARAMETER,
            BlockSymbolKind.EVENT_PARAMETER,
            BlockSymbolKind.MODE_PARAMETER,
            BlockSymbolKind.INPUT,
        )

    def kind_supports_value(self) -> bool:
        """
        :return: Whether this role stores a numeric constant.
        """
        return self._kind in (BlockSymbolKind.PARAMETER, BlockSymbolKind.EVENT_PARAMETER)

    def has_mapping_changes(self) -> bool:
        """Return whether either staged mapping differs from its opening value.

        :return: Whether the user changed a variable or static-parameter mapping.
        """
        return (
            self._external_reference != self._original_external_reference
            or self._static_reference != self._original_static_reference
        )

    def has_value_changes(self) -> bool:
        """Return whether the staged parameter value differs from its source.

        :return: Whether the textual parameter value changed.
        """
        return self._value_text.strip() != self._original_value_text.strip()

    def has_changes(self) -> bool:
        """Return whether this row differs from its authoritative block state.

        :return: ``True`` for a new symbol or a changed role, value, mapping or
            output exposure.
        """
        if self.is_new():
            result: bool = True
        elif self._kind != self._original_kind:
            result = True
        elif self.has_value_changes():
            result = True
        elif self.has_mapping_changes():
            result = True
        else:
            variable: Var | None = self._variable
            if variable is not None:
                result = self._exported != (variable in self._owner.out_vars)
            else:
                result = True
        return result

    def parse_value(self) -> float:
        """
        Parse a finite numeric parameter value.

        :return: Parameter value parsed as a finite floating-point number.
        """
        if self.kind_supports_value():
            value: float = float(self._value_text)
            if value == float("inf") or value == float("-inf") or value != value:
                raise ValueError(f"Parameter '{self._name}' must be finite")
            else:
                return value
        else:
            return 0.0

    def get_value_text(self) -> str:
        """Return the unapplied parameter expression.

        :return: Text supplied when adding or editing this symbol.
        """
        return self._value_text

    def set_value_text(self, value: str) -> None:
        """Stage parameter text without changing the underlying block.

        :param value: Numeric or symbolic initialization expression.
        :return: None.
        """
        self._value_text = value

    def parse_dynamic_expression(self, namespace: Mapping[str, Expr]) -> Expr:
        """Validate a new dynamic parameter with the existing expression parser.

        :param namespace: Complete draft or applied symbol identities.
        :return: Scalar numeric or symbolic initialization expression.
        :raises ValueError: If the parameter identity or expression is invalid.
        """
        variable: Expr | None = namespace.get(self._name, None)
        if not isinstance(variable, Var):
            raise ValueError(f"Unknown dynamic parameter '{self._name}'")
        else:
            draft: ParameterDraftRow = ParameterDraftRow(
                category="Dynamic parameter", owner=self._owner, variable=variable,
                expression=Const(0.0), kind=BlockSymbolKind.EVENT_PARAMETER,
            )
            draft.set_draft_text(self._value_text)
            return draft.parse_event_expression(namespace)


def get_symbol_kind(block: Block, variable: Var) -> BlockSymbolKind:
    """
    :param block: Symbolic block used by the operation.
    :param variable: Symbolic variable used by the operation.
    :return: The primary role currently owned by one variable.
    """
    if variable in block.in_vars:
        return BlockSymbolKind.INPUT
    elif variable in block.algebraic_vars:
        return BlockSymbolKind.ALGEBRAIC
    elif variable in block.state_vars:
        return BlockSymbolKind.STATE
    elif variable in block.diff_vars:
        return BlockSymbolKind.DIFFERENTIAL
    elif variable in block.parameters:
        return BlockSymbolKind.PARAMETER
    elif variable in block.event_dict:
        return BlockSymbolKind.EVENT_PARAMETER
    elif variable in block.mode_dict:
        return BlockSymbolKind.MODE_PARAMETER
    else:
        return BlockSymbolKind.OUTPUT_ONLY


def get_symbol_value_text(block: Block, variable: Var, kind: BlockSymbolKind) -> str:
    """
    :param block: Symbolic block used by the operation.
    :param variable: Symbolic variable used by the operation.
    :param kind: Value supplied for ``kind``.
    :return: The numeric text associated with a parameter-like symbol.
    """
    expression: Expr | None = None
    if kind == BlockSymbolKind.PARAMETER:
        expression = block.parameters.get(variable, None)
    elif kind == BlockSymbolKind.EVENT_PARAMETER:
        expression = block.event_dict.get(variable, None)
    else:
        pass
    if isinstance(expression, Const):
        return str(expression.value)
    else:
        return "0.0"


def get_ordered_block_symbols(block: Block) -> List[Var]:
    """Return each directly owned or initialized symbol once in semantic order.

    External initialization mappings may legitimately retain a variable that
    is not an input, equation unknown, or output. Including those identities is
    essential: otherwise the dialogue could hide a power-flow dependency that
    will still be consumed by runtime initialization.

    :param block: Direct block whose symbols are requested.
    :return: Stable list containing every visible or mapped identity.
    """
    result: List[Var] = list()
    groups: tuple[Sequence[Var], ...] = (
        block.in_vars,
        block.algebraic_vars,
        block.state_vars,
        block.diff_vars,
        tuple(block.parameters.keys()),
        tuple(block.event_dict.keys()),
        block.out_vars,
    )
    group: Sequence[Var]
    variable: Var
    for group in groups:
        for variable in group:
            if variable not in result:
                result.append(variable)
            else:
                pass

    mapped_variable: Var | None
    for mapped_variable in block.external_mapping.values():
        if isinstance(mapped_variable, Var) and mapped_variable not in result:
            result.append(mapped_variable)
        else:
            pass

    mapped_parameter: Var
    for mapped_parameter in block.api_obj_mapping.values():
        if mapped_parameter not in result:
            result.append(mapped_parameter)
        else:
            pass
    return result


def get_variable_external_reference(block: Block,
                                    variable: Var) -> VarPowerFlowReferenceType | None:
    """Return the power-flow initialization key mapped to one variable.

    :param block: Direct symbol owner.
    :param variable: Variable whose mapping is requested.
    :return: Matching initialization key or ``None``.
    """
    result: VarPowerFlowReferenceType | None = None
    reference: VarPowerFlowReferenceType
    mapped_variable: Var | None
    for reference, mapped_variable in block.external_mapping.items():
        if mapped_variable is variable and result is None:
            result = reference
        else:
            pass
    return result


def get_variable_static_reference(block: Block,
                                  variable: Var) -> ParamPowerFlowReferenceType | None:
    """Return the device static-parameter key mapped to one variable.

    :param block: Direct symbol owner.
    :param variable: Parameter variable whose mapping is requested.
    :return: Matching static key or ``None``.
    """
    result: ParamPowerFlowReferenceType | None = None
    reference: ParamPowerFlowReferenceType
    mapped_variable: Var
    for reference, mapped_variable in block.api_obj_mapping.items():
        if mapped_variable is variable and result is None:
            result = reference
        else:
            pass
    return result


class BlockSymbolDraftModel(QtCore.QAbstractTableModel):
    """Editable staged table of recursive variables and parameters."""

    __slots__ = ("_rows", "_removed_rows")

    def __init__(self, block: Block, parent: QtCore.QObject | None = None) -> None:
        """
        Capture all directly owned symbols across the selected block tree.

        :param block: Symbolic block used by the operation.
        :param parent: Owning Qt widget.
        :return: None.
        """
        super().__init__(parent)
        self._rows: List[BlockSymbolDraftRow] = list()
        self._removed_rows: List[BlockSymbolDraftRow] = list()
        self._append_block_rows(block)

    def _append_block_rows(self, block: Block) -> None:
        """Append authoritative symbol rows from one recursive block tree.

        :param block: Root block whose current symbols must populate the draft.
        :return: None.
        """
        owner: Block
        for owner in block.get_all_blocks():
            variable: Var
            for variable in get_ordered_block_symbols(owner):
                kind: BlockSymbolKind = get_symbol_kind(owner, variable)
                if kind == BlockSymbolKind.MODE_PARAMETER:
                    # RuntimeLogicDraftCollection is the sole retained-mode
                    # transaction owner. Keeping a hidden second symbol row
                    # would apply the same Engine identity through two models.
                    pass
                else:
                    value_text: str = get_symbol_value_text(owner, variable, kind)
                    external_reference: VarPowerFlowReferenceType | None = get_variable_external_reference(
                        owner,
                        variable,
                    )
                    static_reference: ParamPowerFlowReferenceType | None = get_variable_static_reference(
                        owner,
                        variable,
                    )
                    self._rows.append(
                        BlockSymbolDraftRow(
                            owner,
                            variable,
                            variable.name,
                            kind,
                            variable in owner.out_vars,
                            value_text,
                            external_reference,
                            static_reference,
                        )
                    )

    def reload(self, block: Block) -> None:
        """Replace staged rows with identities currently owned by the block.

        Applying a newly staged symbol creates its authoritative ``Var``. The
        table must bind to that identity immediately; otherwise a later Delete
        in the same open dialogue would discard only the stale temporary row.

        :param block: Root block whose applied symbols must be reloaded.
        :return: None.
        """
        self.beginResetModel()
        self._rows.clear()
        self._removed_rows.clear()
        self._append_block_rows(block)
        self.endResetModel()

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """
        Return the number of recursive symbol rows.

        :param parent: Owning Qt widget.
        :return: The number of recursive symbol rows.
        """
        if parent.isValid():
            return 0
        else:
            return len(self._rows)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """
        Return owner, name, type, output, and initialization mapping columns.

        :param parent: Owning Qt widget.
        :return: Owner, name, type, output, and initialization mapping columns.
        """
        if parent.isValid():
            return 0
        else:
            return 5

    def get_row(self, row_index: int) -> BlockSymbolDraftRow | None:
        """Return one source row for proxy filtering and selection mapping.

        :param row_index: Source-model row index.
        :return: Symbol draft row or ``None`` when outside the model.
        """
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]
        else:
            return None

    def data(self, index: QtCore.QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        """
        :param index: Value supplied for ``index``.
        :param role: Value supplied for ``role``.
        :return: Staged symbol data and checkbox state.
        """
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        else:
            row: BlockSymbolDraftRow = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if index.column() == 0:
                return row.get_owner().name
            elif index.column() == 1:
                return row.get_name()
            elif index.column() == 2:
                return row.get_kind().value
            elif index.column() == 4:
                external_reference: VarPowerFlowReferenceType | None = row.get_external_reference()
                static_reference: ParamPowerFlowReferenceType | None = row.get_static_reference()
                if external_reference is not None:
                    return f"VarPowerFlowReferenceType.{external_reference.name}"
                elif static_reference is not None:
                    return f"ParamPowerFlowReferenceType.{static_reference.name}"
                else:
                    return ""
            else:
                return None
        elif role == Qt.ItemDataRole.CheckStateRole and index.column() == 3 and row.kind_supports_export():
            if row.is_exported():
                return Qt.CheckState.Checked
            else:
                return Qt.CheckState.Unchecked
        else:
            return None

    def setData(self,
                index: QtCore.QModelIndex,
                value: object,
                role: int = Qt.ItemDataRole.EditRole) -> bool:
        """Update a staged symbol field without mutating the symbolic block.

        :param index: Source-model cell being edited.
        :param value: New edit or checkbox value supplied by Qt.
        :param role: Qt data role describing the edit operation.
        :return: Whether the staged value was accepted.
        """
        if not index.isValid() or index.row() >= len(self._rows):
            return False
        else:
            row: BlockSymbolDraftRow = self._rows[index.row()]
        if (
            role == Qt.ItemDataRole.CheckStateRole
            and index.column() == 3
            and row.kind_supports_export()
        ):
            # Output exposure is independent from the primary DAE role. Existing
            # algebraic/state variables therefore need the same staged checkbox
            # behavior as newly declared symbols.
            row.set_exported(value == Qt.CheckState.Checked.value or value == Qt.CheckState.Checked)
            self.dataChanged.emit(index, index, list((role,)))
            return True
        elif role == Qt.ItemDataRole.EditRole and index.column() == 1 and row.is_new():
            row.set_name(str(value).strip())
            self.dataChanged.emit(index, index, list((role,)))
            return True
        elif role == Qt.ItemDataRole.EditRole and index.column() == 2 and row.is_new():
            selected_kind: BlockSymbolKind | None = get_block_symbol_kind_from_text(str(value))
            if selected_kind is not None:
                row.set_kind(selected_kind)
                if not row.kind_supports_export():
                    row.set_exported(False)
                else:
                    pass
                self.dataChanged.emit(self.index(index.row(), 2), self.index(index.row(), 3))
                return True
            else:
                return False
        elif (
                role == Qt.ItemDataRole.EditRole
                and index.column() == 4
                and (row.supports_external_reference() or row.supports_static_reference())
        ):
            return self._set_mapping_text(index, row, str(value))
        else:
            return False

    def _set_mapping_text(self,
                          index: QtCore.QModelIndex,
                          row: BlockSymbolDraftRow,
                          mapping_text: str) -> bool:
        """Parse one typed mapping label selected by the table delegate.

        :param index: Edited mapping cell.
        :param row: Symbol draft row receiving the mapping.
        :param mapping_text: Delegate display text.
        :return: Whether the mapping text was accepted.
        """
        normalized: str = mapping_text.strip()
        accepted: bool = False
        if normalized == "None" or len(normalized) == 0:
            if row.supports_static_reference():
                # Removing the mapping keeps the storage role unchanged. A
                # constant parameter must then retain a concrete local value.
                row.set_static_reference(None)
                accepted = True
            else:
                row.set_external_reference(None)
                row.set_static_reference(None)
                accepted = True
        elif normalized.startswith("VarPowerFlowReferenceType.") and row.supports_external_reference():
            reference_name: str = normalized.removeprefix("VarPowerFlowReferenceType.")
            if reference_name in VarPowerFlowReferenceType.__members__:
                row.set_external_reference(VarPowerFlowReferenceType[reference_name])
                accepted = True
            else:
                pass
        elif normalized.startswith("ParamPowerFlowReferenceType.") and row.supports_static_reference():
            static_name: str = normalized.removeprefix("ParamPowerFlowReferenceType.")
            if static_name in ParamPowerFlowReferenceType.__members__:
                row.set_static_reference(ParamPowerFlowReferenceType[static_name])
                accepted = True
            else:
                pass
        else:
            pass
        if accepted:
            self.dataChanged.emit(index, index, list((Qt.ItemDataRole.EditRole, Qt.ItemDataRole.DisplayRole,)))
        else:
            pass
        return accepted

    def flags(self, index: QtCore.QModelIndex) -> Qt.ItemFlag:
        """Expose only semantically valid edits for each symbol column.

        :param index: Source-model cell queried by the view.
        :return: Qt item flags permitted for the staged symbol cell.
        """
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        else:
            row: BlockSymbolDraftRow = self._rows[index.row()]
            flags: Qt.ItemFlag = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 1 and row.is_new():
            flags |= Qt.ItemFlag.ItemIsEditable
        elif index.column() == 2 and row.is_new():
            flags |= Qt.ItemFlag.ItemIsEditable
        elif index.column() == 3 and row.kind_supports_export():
            # Applying the checkbox later preserves transactional editor behavior:
            # closing the host still leaves the source block untouched.
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        elif index.column() == 4 and (
                row.supports_external_reference() or row.supports_static_reference()):
            flags |= Qt.ItemFlag.ItemIsEditable
        else:
            pass
        return flags

    def headerData(self,
                   section: int,
                   orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> object:
        """
        Return symbol table headers.

        :param section: Value supplied for ``section``.
        :param orientation: Value supplied for ``orientation``.
        :param role: Value supplied for ``role``.
        :return: Symbol table headers.
        """
        headers: tuple[str, ...] = (
            "Block",
            "Name",
            "Type",
            "Output",
            "Mapping",
        )
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(headers):
                return self.tr(headers[section])
            else:
                return None
        else:
            return None

    def add_symbol(self,
                   owner: Block,
                   name: str,
                   kind: BlockSymbolKind,
                   exported: bool,
                   value: float | None,
                   create_derivative: bool = False,
                   external_reference: VarPowerFlowReferenceType | None = None,
                   static_reference: ParamPowerFlowReferenceType | None = None) -> None:
        """Append a detached new symbol and its requested derivative row.

        :param owner: Concrete block that will own the new symbol after Apply.
        :param name: Valid symbolic name.
        :param kind: Primary DAE role.
        :param exported: Independent output-port role.
        :param value: Local initial value, or ``None`` for device initialization.
        :param create_derivative: Whether a state also stages ``d_<name>``.
        :param external_reference: Optional variable power-flow mapping.
        :param static_reference: Optional static-device parameter mapping.
        :return: None.
        """
        insertion_row: int = len(self._rows)
        stages_derivative: bool = kind == BlockSymbolKind.STATE and create_derivative
        if stages_derivative:
            final_insertion_row: int = insertion_row + 1
        else:
            final_insertion_row = insertion_row
        self.beginInsertRows(QtCore.QModelIndex(), insertion_row, final_insertion_row)
        state_row: BlockSymbolDraftRow = BlockSymbolDraftRow(
            owner,
            None,
            name,
            kind,
            exported,
            str(value),
            external_reference,
            static_reference,
        )
        self._rows.append(state_row)
        if stages_derivative:
            # A derivative is a first-class block variable. Staging it as its
            # own row makes the pending model structure visible before Apply,
            # while retaining the state identity required by ``base_var``.
            self._rows.append(
                BlockSymbolDraftRow(
                    owner,
                    None,
                    state_row.get_derivative_name(),
                    BlockSymbolKind.DIFFERENTIAL,
                    False,
                    "0.0",
                    None,
                    None,
                    state_row,
                )
            )
        else:
            pass
        self.endInsertRows()

    def remove_symbol(self, row_index: int) -> bool:
        """Stage deletion of one symbol and any derivative owned by a state.

        Existing objects remain untouched until Apply. Validation immediately
        excludes deleted names so dependent equations must be corrected first.
        State deletion is directional: associated differential rows are also
        removed, while deleting a differential row never removes its base state.

        :param row_index: Source-model row selected through a proxy table.
        :return: Whether the selected row was staged for deletion.
        """
        if 0 <= row_index < len(self._rows):
            selected_row: BlockSymbolDraftRow = self._rows[row_index]
            removal_indexes: List[int] = list((row_index,))
            if selected_row.get_kind() == BlockSymbolKind.STATE:
                selected_variable: Var | None = selected_row.get_variable()
                candidate_index: int
                candidate_row: BlockSymbolDraftRow
                for candidate_index, candidate_row in enumerate(self._rows):
                    if (candidate_index != row_index
                            and candidate_row.get_owner() is selected_row.get_owner()
                            and candidate_row.get_kind() == BlockSymbolKind.DIFFERENTIAL):
                        staged_base_matches: bool = (
                            candidate_row.get_derivative_base_row() is selected_row
                        )
                        candidate_variable: Var | None = candidate_row.get_variable()
                        if candidate_variable is not None:
                            candidate_base_variable: Var | None = candidate_variable.base_var
                        else:
                            candidate_base_variable = None
                        if selected_variable is not None and candidate_base_variable is not None:
                            existing_base_matches: bool = (
                                candidate_base_variable.non_mutable_uid
                                == selected_variable.non_mutable_uid
                            )
                        else:
                            existing_base_matches = False
                        if staged_base_matches or existing_base_matches:
                            removal_indexes.append(candidate_index)
                        else:
                            pass
                    else:
                        pass
            else:
                pass

            # Remove from the end so every source-model row index remains valid
            # while Qt receives one precise removal notification per row.
            removal_indexes.sort(reverse=True)
            removal_index: int
            for removal_index in removal_indexes:
                self.beginRemoveRows(QtCore.QModelIndex(), removal_index, removal_index)
                removed_row: BlockSymbolDraftRow = self._rows.pop(removal_index)
                if not removed_row.is_new():
                    self._removed_rows.append(removed_row)
                else:
                    pass
                self.endRemoveRows()
            return True
        else:
            return False

    def build_validation_namespace(self, base_namespace: Mapping[str, Expr]) -> Dict[str, Expr]:
        """
        Build a namespace that includes temporary identities for staged additions.

        :param base_namespace: Value supplied for ``base_namespace``.
        :return: Validation namespace including temporary identities for staged additions.
        """
        namespace: Dict[str, Expr] = dict(base_namespace)
        removed_row: BlockSymbolDraftRow
        for removed_row in self._removed_rows:
            namespace.pop(removed_row.get_name(), None)
        names_seen: set[str] = set(namespace.keys())
        row: BlockSymbolDraftRow
        for row in self._rows:
            name: str = row.get_name()
            if len(name) == 0 or not name.isidentifier():
                raise ValueError(f"Invalid symbol name '{name}'")
            elif row.is_new() and name in names_seen:
                raise ValueError(f"Symbol '{name}' already exists")
            else:
                pass
            if row.is_new():
                namespace[name] = Var(name)
                names_seen.add(name)
            else:
                pass
            if (row.is_new()
                    and row.kind_supports_value()
                    and row.get_kind() != BlockSymbolKind.EVENT_PARAMETER
                    and row.get_static_reference() is None):
                row.parse_value()
            else:
                pass
        # New expressions can reference symbols added later in the form, so
        # parse them only once every temporary identity is in the namespace.
        self.get_new_event_expressions(namespace)
        self._validate_symbol_mappings()
        return namespace

    def build_editing_namespace(self, base_namespace: Mapping[str, Expr]) -> Dict[str, Expr]:
        """Build a permissive namespace for editing an incomplete model draft.

        This namespace exists only to keep completion and highlighting current
        while the user assembles related declarations and code. It deliberately
        does not parse values, enforce uniqueness, or validate mappings; those
        semantic checks belong to Validate model and Apply changes.

        :param base_namespace: Symbols currently owned by the Engine block tree.
        :return: Namespace with removed symbols excluded and valid staged names included.
        """
        namespace: Dict[str, Expr] = dict(base_namespace)
        removed_row: BlockSymbolDraftRow
        for removed_row in self._removed_rows:
            namespace.pop(removed_row.get_name(), None)

        # Invalid intermediate cell contents are omitted from editor assistance
        # instead of blocking an unrelated staging action. Strict validation
        # reports those names before the draft can be applied to the Engine.
        row: BlockSymbolDraftRow
        for row in self._rows:
            name: str = row.get_name()
            usable_name: bool = (
                row.is_new()
                and len(name) > 0
                and name.isidentifier()
                and not keyword.iskeyword(name)
            )
            if usable_name:
                namespace[name] = Var(name)
            else:
                pass
        return namespace

    def get_new_event_expressions(self, namespace: Mapping[str, Expr]) -> List[tuple[Block, Var, Expr]]:
        """Include new dynamic parameters in pre-Apply dependency validation.

        :param namespace: Complete namespace including pending symbols.
        :return: New owner, parameter and parsed-expression triples.
        """
        expressions: List[tuple[Block, Var, Expr]] = list()
        row: BlockSymbolDraftRow
        for row in self._rows:
            if row.is_new() and row.get_kind() == BlockSymbolKind.EVENT_PARAMETER:
                variable: Expr | None = namespace.get(row.get_name(), None)
                if isinstance(variable, Var):
                    if row.get_static_reference() is None:
                        expressions.append((row.get_owner(), variable, row.parse_dynamic_expression(namespace)))
                    else:
                        expressions.append((row.get_owner(), variable, Const(None)))
                else:
                    pass
            else:
                pass
        return expressions

    def _validate_symbol_mappings(self) -> None:
        """Validate typed parameter mappings and duplicate owner-local keys.

        :return: None.
        """
        external_owners: set[tuple[int, VarPowerFlowReferenceType]] = set()
        static_owners: set[tuple[int, ParamPowerFlowReferenceType]] = set()
        row: BlockSymbolDraftRow
        for row in self._rows:
            external_reference: VarPowerFlowReferenceType | None = row.get_external_reference()
            static_reference: ParamPowerFlowReferenceType | None = row.get_static_reference()
            if row.get_kind() == BlockSymbolKind.PARAMETER:
                if static_reference is None:
                    # An immutable parameter may use a local literal or a
                    # device mapping, but it must always have one real source.
                    row.parse_value()
                else:
                    pass
            elif row.get_kind() == BlockSymbolKind.EVENT_PARAMETER:
                # Event parameters may optionally obtain their baseline from a
                # static-device attribute while remaining runtime mutable.
                pass
            elif static_reference is not None:
                raise ValueError(
                    f"Device initialization mapping '{static_reference.name}' in block "
                    + f"'{row.get_owner().name}' targets '{row.get_name()}', which is not "
                    + "declared in the same block's parameters or event_dict"
                )
            else:
                pass
            if external_reference is not None:
                external_key: tuple[int, VarPowerFlowReferenceType] = (
                    row.get_owner().uid,
                    external_reference,
                )
                if external_key in external_owners:
                    raise ValueError(
                        f"Power-flow mapping '{external_reference.name}' is assigned more than once "
                        f"in block '{row.get_owner().name}'"
                    )
                else:
                    external_owners.add(external_key)
            else:
                pass
            if static_reference is not None:
                static_key: tuple[int, ParamPowerFlowReferenceType] = (
                    row.get_owner().uid,
                    static_reference,
                )
                if static_key in static_owners:
                    raise ValueError(
                        f"Device static mapping '{static_reference.name}' is assigned more than once "
                        f"in block '{row.get_owner().name}'"
                    )
                else:
                    static_owners.add(static_key)
            else:
                pass

    def apply_to_blocks(self, var_factory: VarFactory) -> None:
        """
        Apply staged roles and create requested variables after validation.

        :param var_factory: Factory that owns symbolic variables.
        :return: None.
        """
        removed_row: BlockSymbolDraftRow
        for removed_row in self._removed_rows:
            removed_variable: Var | None = removed_row.get_variable()
            if removed_variable is not None:
                remove_block_symbol(removed_row.get_owner(), removed_variable)
            else:
                pass

        new_event_rows: List[BlockSymbolDraftRow] = list()
        row: BlockSymbolDraftRow
        for row in self._rows:
            variable: Var | None = row.get_variable()
            if variable is None:
                if row.get_kind() == BlockSymbolKind.EVENT_PARAMETER:
                    new_event_rows.append(row)
                    initial_value: float | None = None
                elif row.get_static_reference() is not None:
                    initial_value = None
                else:
                    initial_value = row.parse_value()
                if row.get_kind() == BlockSymbolKind.DIFFERENTIAL:
                    derivative_base_row: BlockSymbolDraftRow | None = row.get_derivative_base_row()
                    if derivative_base_row is not None:
                        derivative_base_variable: Var | None = derivative_base_row.get_variable()
                    else:
                        derivative_base_variable = None
                    variable = var_factory.add_diff_var(
                        name=row.get_name(),
                        base_var=derivative_base_variable,
                    )
                else:
                    variable = var_factory.add_var(name=row.get_name())
                # Later staged rows may depend on this exact identity. Bind it
                # before continuing so a derivative can preserve ``base_var``.
                row.set_variable(variable)
                reclassify_block_symbol(
                    row.get_owner(), variable, row.get_kind(), initial_value, var_factory
                )
            else:
                if row.get_kind() != row.get_original_kind():
                    if row.get_static_reference() is None:
                        reclassified_value: float | None = row.parse_value()
                    else:
                        reclassified_value = None
                    reclassify_block_symbol(
                        row.get_owner(), variable, row.get_kind(), reclassified_value, var_factory
                    )
                elif (row.get_kind() == BlockSymbolKind.PARAMETER
                      and row.get_static_reference() is not None
                      and row.has_mapping_changes()):
                    # Selecting the device as source removes the competing local
                    # literal while keeping immutable storage ownership.
                    row.get_owner().parameters[variable] = Const(None)
                elif (row.get_kind() == BlockSymbolKind.EVENT_PARAMETER
                      and row.get_static_reference() is not None
                      and row.has_mapping_changes()):
                    # The event remains mutable; only its initial source changes.
                    row.get_owner().event_dict[variable] = Const(None)
                elif (row.get_kind() == BlockSymbolKind.PARAMETER
                      and row.get_static_reference() is None
                      and row.has_value_changes()):
                    declared_value: Expr | None = row.get_owner().parameters.get(variable, None)
                    if isinstance(declared_value, Const):
                        declared_value.value = row.parse_value()
                    else:
                        raise ValueError(
                            f"Static parameter '{row.get_name()}' does not have a numeric declaration"
                        )
                else:
                    pass
            if row.is_exported() and variable not in row.get_owner().out_vars:
                row.get_owner().out_vars.append(variable)
            elif not row.is_exported() and variable in row.get_owner().out_vars:
                row.get_owner().out_vars.remove(variable)
            else:
                pass
            apply_symbol_mapping(row.get_owner(), variable, row)

        # All new identities now exist. Rebind expressions to those exact
        # Vars rather than retaining the temporary validation namespace.
        applied_namespace: Dict[str, Expr] = dict()
        for row in self._rows:
            variable = row.get_variable()
            if variable is not None:
                applied_namespace[row.get_name()] = variable
            else:
                pass
        for row in new_event_rows:
            variable = row.get_variable()
            if variable is not None:
                if row.get_static_reference() is None:
                    row.get_owner().event_dict[variable] = row.parse_dynamic_expression(applied_namespace)
                else:
                    row.get_owner().event_dict[variable] = Const(None)
            else:
                pass

    def has_new_symbols(self) -> bool:
        """
        Return whether the draft contains unapplied symbol additions.

        :return: Whether the draft contains unapplied symbol additions.
        """
        result: bool = False
        row: BlockSymbolDraftRow
        for row in self._rows:
            if row.is_new():
                result = True
            else:
                pass
        return result

    def has_symbol_changes(self) -> bool:
        """
        Return whether additions or deletions are staged in the table.

        :return: Whether additions or deletions are staged in the table.
        """
        if len(self._removed_rows) > 0:
            result: bool = True
        else:
            result = self.has_new_symbols()
        return result

    def get_output_export_changes(self) -> List[tuple[Block, Var, bool]]:
        """Return staged output-role changes for existing variables.

        The owning graphics editor consumes removals before ``out_vars`` is
        mutated so it can unregister any wires through their still-valid ports.

        :return: Owner, existing variable, and requested output state tuples.
        """
        changes: List[tuple[Block, Var, bool]] = list()
        row: BlockSymbolDraftRow
        for row in self._rows:
            variable: Var | None = row.get_variable()
            if variable is not None:
                currently_exported: bool = variable in row.get_owner().out_vars
                if currently_exported != row.is_exported():
                    changes.append((row.get_owner(), variable, row.is_exported()))
                else:
                    pass
            else:
                pass
        removed_row: BlockSymbolDraftRow
        for removed_row in self._removed_rows:
            removed_variable: Var | None = removed_row.get_variable()
            if removed_variable is not None and removed_variable in removed_row.get_owner().out_vars:
                changes.append((removed_row.get_owner(), removed_variable, False))
            else:
                pass
        return changes

    def get_existing_symbol_removals(self) -> List[tuple[Block, Var]]:
        """Return existing symbols whose deletion is staged for Apply.

        The Dynamic Editor consumes this snapshot before the owning block is
        mutated so it can remove any direct interface-wrapper child and its
        persisted wires while the deleted port is still identifiable.

        :return: Direct owner and existing variable pairs staged for deletion.
        """
        removals: List[tuple[Block, Var]] = list()
        removed_row: BlockSymbolDraftRow
        for removed_row in self._removed_rows:
            removed_variable: Var | None = removed_row.get_variable()
            if removed_variable is not None:
                removals.append((removed_row.get_owner(), removed_variable))
            else:
                pass
        return removals

    def get_role_count(self, owner: Block, kind: BlockSymbolKind) -> int:
        """Return the staged number of symbols with one primary DAE role.

        :param owner: Block whose staged rows are counted.
        :param kind: Primary symbol role to count.
        :return: Number of matching staged symbols.
        """
        result: int = 0
        row: BlockSymbolDraftRow
        for row in self._rows:
            if row.get_owner() is owner and row.get_kind() == kind:
                result += 1
            else:
                pass
        return result

    def get_role_names(self, owner: Block, kind: BlockSymbolKind) -> List[str]:
        """Return staged symbol names in their authoritative table order.

        :param owner: Block whose staged symbols are requested.
        :param kind: Primary DAE role to collect.
        :return: Ordered staged names for the selected role.
        """
        result: List[str] = list()
        row: BlockSymbolDraftRow
        for row in self._rows:
            if row.get_owner() is owner and row.get_kind() == kind:
                result.append(row.get_name())
            else:
                pass
        return result

    def has_changes(self) -> bool:
        """Return whether any staged symbol property differs from the block.

        :return: Whether a symbol was added, removed, reclassified, remapped,
            assigned a different value, or exposed through a different output.
        """
        if len(self._removed_rows) > 0:
            result: bool = True
        else:
            result = False
            row: BlockSymbolDraftRow
            for row in self._rows:
                if row.has_changes():
                    result = True
                else:
                    pass
        return result

    def has_mapping_changes(self) -> bool:
        """Return whether an existing or new row changed its typed mapping.

        New symbols are already reported by :meth:`has_symbol_changes`; keeping
        this query separate makes structural-rebuild conflict checks explicit.

        :return: Whether at least one row has a staged mapping change.
        """
        result: bool = False
        row: BlockSymbolDraftRow
        for row in self._rows:
            if row.has_mapping_changes():
                result = True
            else:
                pass
        return result

    def get_initializable_names(self, owner: Block) -> List[str]:
        """Return variables permitted to own ordinary initialization equations.

        State and algebraic variables are always block-owned initialization
        targets. A legacy output-only identity is also valid when it is a real
        outgoing port; mapping-only synthetic rows remain excluded.

        :param owner: Direct block whose staged initialization keys are requested.
        :return: Ordered names accepted as keys of ``init_eqs``.
        """
        result: List[str] = list()
        row: BlockSymbolDraftRow
        for row in self._rows:
            initializable: bool = row.get_kind() in (
                BlockSymbolKind.STATE,
                BlockSymbolKind.ALGEBRAIC,
            )
            output_only: bool = (
                row.get_kind() == BlockSymbolKind.OUTPUT_ONLY
                and row.is_exported()
            )
            if row.get_owner() is owner and (initializable or output_only):
                result.append(row.get_name())
            else:
                pass
        return result

    def refresh_existing_names(self) -> None:
        """Refresh detached row labels after an editor-owned variable rename.

        Existing rows retain their staged role, mapping, and output changes. Only
        their displayed names follow the authoritative ``Var`` objects changed by
        the central editor rename operation. A data-only notification deliberately
        avoids resetting the source model because tree leaves hold persistent
        indexes into this model.

        :return: None.
        """
        first_changed_row: int | None = None
        last_changed_row: int | None = None
        row_index: int
        row: BlockSymbolDraftRow
        for row_index, row in enumerate(self._rows):
            variable: Var | None = row.get_variable()
            if variable is not None and row.get_name() != variable.name:
                row.set_name(variable.name)
                if first_changed_row is None:
                    first_changed_row = row_index
                else:
                    pass
                last_changed_row = row_index
            else:
                pass
        if first_changed_row is not None and last_changed_row is not None:
            self.dataChanged.emit(
                self.index(first_changed_row, 1),
                self.index(last_changed_row, 1),
                list((Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole,)),
            )
        else:
            pass


def get_block_symbol_kind_from_text(text: str) -> BlockSymbolKind | None:
    """
    Resolve a displayed role label to its enum member.

    :param text: User-entered text.
    :return: Enum member matching the displayed role label, or ``None`` when unmatched.
    """
    kind: BlockSymbolKind
    for kind in BlockSymbolKind:
        if kind.value == text:
            return kind
        else:
            pass
    return None


def apply_symbol_mapping(block: Block,
                         variable: Var,
                         row: BlockSymbolDraftRow) -> None:
    """Replace external/static mappings for one staged symbol row.

    :param block: Direct owner of the symbol and mapping dictionaries.
    :param variable: Applied authoritative variable identity.
    :param row: Draft containing the requested typed mappings.
    :return: None.
    """
    external_keys_to_remove: List[VarPowerFlowReferenceType] = list()
    external_key: VarPowerFlowReferenceType
    mapped_external_variable: Var | None
    for external_key, mapped_external_variable in block.external_mapping.items():
        if mapped_external_variable is variable:
            external_keys_to_remove.append(external_key)
        else:
            pass
    for external_key in external_keys_to_remove:
        del block.external_mapping[external_key]

    external_reference: VarPowerFlowReferenceType | None = row.get_external_reference()
    if external_reference is not None:
        block.external_mapping[external_reference] = variable
    else:
        pass

    # Reclassification away from a mapped parameter must remove its former
    # mapping. Both immutable and event-capable parameters may own one.
    manages_static_mapping: bool = (
        row.get_kind() in (BlockSymbolKind.PARAMETER, BlockSymbolKind.EVENT_PARAMETER)
        or row.get_original_kind() in (BlockSymbolKind.PARAMETER, BlockSymbolKind.EVENT_PARAMETER)
    )
    if manages_static_mapping:
        static_keys_to_remove: List[ParamPowerFlowReferenceType] = list()
        static_key: ParamPowerFlowReferenceType
        mapped_static_variable: Var
        for static_key, mapped_static_variable in block.api_obj_mapping.items():
            if mapped_static_variable is variable:
                static_keys_to_remove.append(static_key)
            else:
                pass
        for static_key in static_keys_to_remove:
            del block.api_obj_mapping[static_key]

        static_reference: ParamPowerFlowReferenceType | None = row.get_static_reference()
        if (static_reference is not None
                and row.get_kind() in (BlockSymbolKind.PARAMETER, BlockSymbolKind.EVENT_PARAMETER)):
            block.api_obj_mapping[static_reference] = variable
        else:
            pass
    else:
        pass


def remove_block_symbol(block: Block, variable: Var) -> None:
    """Remove one symbol identity from every direct ownership collection.

    Equation text is validated before this mutation, so no applied expression
    can still reference the deleted identity. Device mappings are also removed
    to avoid leaving an invisible static or power-flow parameter binding.

    :param block: Direct owner of the symbol.
    :param variable: Existing symbolic identity staged for deletion.
    :return: None.
    """
    sequence_groups: tuple[List[Var], ...] = (
        block.in_vars,
        block.algebraic_vars,
        block.state_vars,
        block.diff_vars,
        block.reformulated_vars,
        block.out_vars,
    )
    sequence: List[Var]
    for sequence in sequence_groups:
        if variable in sequence:
            sequence.remove(variable)
        else:
            pass

    mapping_groups: tuple[dict, ...] = (
        block.parameters,
        block.event_dict,
        block.mode_dict,
        block.init_values,
        block.init_eqs,
        block.diff_init_eqs,
        block.discrete_eqs,
        block.boolean_guards,
    )
    mapping: dict
    for mapping in mapping_groups:
        mapping.pop(variable, None)

    external_key: object
    external_keys_to_remove: List[object] = list()
    for external_key, mapped_variable in block.external_mapping.items():
        if mapped_variable is variable:
            external_keys_to_remove.append(external_key)
        else:
            pass
    for external_key in external_keys_to_remove:
        del block.external_mapping[external_key]

    parameter_key: ParamPowerFlowReferenceType
    parameter_keys_to_remove: List[ParamPowerFlowReferenceType] = list()
    for parameter_key, mapped_parameter in block.api_obj_mapping.items():
        if mapped_parameter is variable:
            parameter_keys_to_remove.append(parameter_key)
        else:
            pass
    for parameter_key in parameter_keys_to_remove:
        del block.api_obj_mapping[parameter_key]


def reclassify_block_symbol(block: Block,
                            variable: Var,
                            kind: BlockSymbolKind,
                            numeric_value: float | None,
                            var_factory: VarFactory) -> None:
    """
    Move one existing identity to exactly one primary block role.

    :param block: Symbolic block used by the operation.
    :param variable: Symbolic variable used by the operation.
    :param kind: Value supplied for ``kind``.
    :param numeric_value: Local value, or ``None`` for device initialization.
    :param var_factory: Factory that owns symbolic variables.
    :return: None.
    """
    previous_constant: Const | None = None
    parameter_expression: Expr | None = block.parameters.get(variable, None)
    event_expression: Expr | None = block.event_dict.get(variable, None)
    if isinstance(parameter_expression, Const):
        previous_constant = parameter_expression
    elif isinstance(event_expression, Const):
        previous_constant = event_expression
    else:
        pass
    sequence_groups: tuple[List[Var], ...] = (block.in_vars, block.algebraic_vars, block.state_vars, block.diff_vars)
    sequence: List[Var]
    for sequence in sequence_groups:
        if variable in sequence:
            sequence.remove(variable)
        else:
            pass
    if variable in block.parameters:
        del block.parameters[variable]
    else:
        pass
    if variable in block.event_dict:
        del block.event_dict[variable]
    else:
        pass
    if kind == BlockSymbolKind.INPUT:
        block.in_vars.append(variable)
    elif kind == BlockSymbolKind.ALGEBRAIC:
        block.algebraic_vars.append(variable)
    elif kind == BlockSymbolKind.STATE:
        block.state_vars.append(variable)
    elif kind == BlockSymbolKind.DIFFERENTIAL:
        block.diff_vars.append(variable)
    elif kind == BlockSymbolKind.PARAMETER:
        block.parameters[variable] = build_reclassified_constant(
            previous_constant, numeric_value, variable.name, var_factory
        )
    elif kind == BlockSymbolKind.EVENT_PARAMETER:
        block.event_dict[variable] = build_reclassified_constant(
            previous_constant, numeric_value, variable.name, var_factory
        )
    elif kind == BlockSymbolKind.OUTPUT_ONLY:
        pass
    else:
        pass


def build_reclassified_constant(previous_constant: Const | None,
                                numeric_value: float | None,
                                name: str,
                                var_factory: VarFactory) -> Const:
    """
    Reuse an existing Const identity or register a new one in VarFactory.

    :param previous_constant: Value supplied for ``previous_constant``.
    :param numeric_value: Local value, or ``None`` for device initialization.
    :param name: Value supplied for ``name``.
    :param var_factory: Factory that owns symbolic variables.
    :return: Existing constant identity, or the newly registered replacement constant.
    """
    if previous_constant is not None:
        previous_constant.value = numeric_value
        return previous_constant
    else:
        return var_factory.add_const(value=numeric_value, name=name)


class BlockParameterDraftModel(QtCore.QAbstractTableModel):
    """Stage dynamic-parameter expressions from ``event_dict`` until Apply.

    Fixed ``block.parameters`` remain part of the symbolic compiler contract
    and are edited through the Parameters branch in General options. Dynamic
    parameter expressions use this backing model so the tree remains detached
    from the Engine until Apply.
    """

    __slots__ = ("_rows",)

    def __init__(self, block: Block, parent: QtCore.QObject | None = None) -> None:
        """
        Build staged rows recursively from dynamic-parameter expressions.

        :param block: Symbolic block used by the operation.
        :param parent: Owning Qt widget.
        :return: None.
        """
        super().__init__(parent)
        self._rows: List[ParameterDraftRow] = list()
        self._load_rows(block)

    def _load_rows(self, block: Block) -> None:
        """Load every user-editable parameter from a recursive block tree.

        :param block: Root block whose parameter tree is displayed.
        :return: None.
        """
        all_blocks: List[Block] = block.get_all_blocks()
        child_block: Block
        for child_block in all_blocks:
            owner_label: str = child_block.name if child_block is not block else block.name
            self._append_event_parameter_rows(
                category=f"Dynamic parameter - {owner_label}",
                owner=child_block,
                values=child_block.event_dict,
            )
            # Retained modes may have symbolic initialization expressions and
            # execution dependencies. Python code owns them together with the
            # ordered procedural calls that read or write those modes.

    def reload(self, block: Block) -> None:
        """Refresh rows after staged parameter symbols become real constants.

        :param block: Updated root block.
        :return: None.
        """
        self.beginResetModel()
        self._rows.clear()
        self._load_rows(block)
        self.endResetModel()

    def find_value_index(self, owner: Block, variable: Var | None) -> QtCore.QModelIndex:
        """Resolve a symbol to its existing expression draft by identity.

        :param owner: Block owning the parameter, including composite exposures.
        :param variable: Existing symbolic identity, or None for a pending symbol.
        :return: Value cell, or an invalid index for a newly added parameter.
        """
        row_index: int
        row: ParameterDraftRow
        for row_index, row in enumerate(self._rows):
            if row.get_owner() is owner and row.get_variable() is variable:
                return self.index(row_index, 2)
            else:
                pass
        return QtCore.QModelIndex()

    def rename_draft_identifiers(self, renames: Sequence[tuple[str, str]]) -> None:
        """Keep edited expressions aligned with the editor-owned symbol rename.

        :param renames: Old and new identifier pairs propagated by the editor.
        :return: None.
        """
        row_index: int
        row: ParameterDraftRow
        for row_index, row in enumerate(self._rows):
            old_name: str
            new_name: str
            for old_name, new_name in renames:
                row.rename_identifier(old_name, new_name)
            if len(renames) > 0:
                value_index: QtCore.QModelIndex = self.index(row_index, 2)
                self.dataChanged.emit(
                    value_index,
                    value_index,
                    list((Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole,)),
                )
            else:
                pass

    def has_changes(self) -> bool:
        """Return whether an editable parameter expression is unapplied.

        :return: Whether at least one parameter draft differs from its baseline.
        """
        result: bool = False
        row: ParameterDraftRow
        for row in self._rows:
            if row.has_changes():
                result = True
            else:
                pass
        return result

    def _append_event_parameter_rows(self,
                                     category: str,
                                     owner: Block,
                                     values: Mapping[Var, Expr]) -> None:
        """Append editable dynamic parameters from one ``event_dict``.

        :param category: User-facing dynamic-parameter category and owner label.
        :param owner: Block containing the supplied ``event_dict``.
        :param values: Dynamic parameter-to-expression mapping owned by the block.
        :return: None.
        """
        variable: Var
        expression: Expr
        for variable, expression in values.items():
            self._rows.append(
                ParameterDraftRow(
                    category=category,
                    owner=owner,
                    variable=variable,
                    expression=expression,
                    kind=BlockSymbolKind.EVENT_PARAMETER,
                )
            )

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """
        Return the number of staged parameter rows.

        :param parent: Owning Qt widget.
        :return: The number of staged parameter rows.
        """
        if parent.isValid():
            return 0
        else:
            return len(self._rows)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """
        Return the category, name, and value column count.

        :param parent: Owning Qt widget.
        :return: The category, name, and value column count.
        """
        if parent.isValid():
            return 0
        else:
            return 3

    def data(self, index: QtCore.QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        """
        Return one cell value or presentation role.

        :param index: Value supplied for ``index``.
        :param role: Value supplied for ``role``.
        :return: One cell value or presentation role.
        """
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        else:
            row: ParameterDraftRow = self._rows[index.row()]

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if index.column() == 0:
                return row.get_category()
            elif index.column() == 1:
                return row.get_variable().name
            elif index.column() == 2:
                return row.get_draft_text()
            else:
                return None
        elif role == Qt.ItemDataRole.ToolTipRole and index.column() == 2:
            if row.get_kind() == BlockSymbolKind.EVENT_PARAMETER:
                return self.tr(
                    "Real value or symbolic initialization expression. "
                    "Changes are staged until Apply changes is pressed."
                )
            else:
                return self.tr("Numeric value. Changes are staged until Apply changes is pressed.")
        else:
            return None

    def setData(self,
                index: QtCore.QModelIndex,
                value: object,
                role: int = Qt.ItemDataRole.EditRole) -> bool:
        """
        Stage one edited numeric value as text.

        :param index: Value supplied for ``index``.
        :param value: Value supplied for ``value``.
        :param role: Value supplied for ``role``.
        :return: True when the edited value was accepted; otherwise False.
        """
        if (
            not index.isValid()
            or index.row() >= len(self._rows)
            or index.column() != 2
            or role != Qt.ItemDataRole.EditRole
        ):
            return False
        else:
            row: ParameterDraftRow = self._rows[index.row()]
            expression: Expr = row.get_expression()
            requires_numeric_value: bool = False
            if isinstance(expression, Const):
                expression_value: object = expression.value
                requires_numeric_value = (
                    isinstance(expression_value, (int, float))
                    and not isinstance(expression_value, bool)
                )
            else:
                pass
            if requires_numeric_value and not is_finite_real_number_text(value):
                return False
            else:
                row.set_draft_text(str(value))
                self.dataChanged.emit(index, index, list((role,)))
                return True

    def flags(self, index: QtCore.QModelIndex) -> Qt.ItemFlag:
        """
        Make only the value column editable.

        :param index: Value supplied for ``index``.
        :return: Item flags that make only the value column editable.
        """
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        else:
            result: Qt.ItemFlag = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            if index.column() == 2:
                result |= Qt.ItemFlag.ItemIsEditable
            else:
                pass
            return result

    def headerData(self,
                   section: int,
                   orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> object:
        """
        Return horizontal table headers.

        :param section: Value supplied for ``section``.
        :param orientation: Value supplied for ``orientation``.
        :param role: Value supplied for ``role``.
        :return: Horizontal table headers.
        """
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        elif section == 0:
            return self.tr("Type")
        elif section == 1:
            return self.tr("Name")
        elif section == 2:
            return self.tr("Value")
        else:
            return None

    def get_pending_static_values(self) -> List[tuple[Const, float | complex]]:
        """Validate and return staged updates for numeric static parameters.

        :return: Original constants and their staged numeric values.
        """
        result: List[tuple[Const, float | complex]] = list()
        row: ParameterDraftRow
        for row in self._rows:
            expression: Expr = row.get_expression()
            if row.get_kind() != BlockSymbolKind.PARAMETER:
                pass
            elif isinstance(expression, Const) and row.is_unchanged_unset():
                # ``None`` means the value is supplied later by a mapping. It
                # remains visible in the table but does not become a fake zero.
                pass
            elif isinstance(expression, Const):
                result.append((expression, row.parse_value()))
            else:
                pass
        return result

    def get_pending_event_expressions(
            self,
            namespace: Mapping[str, Expr]) -> List[tuple[Block, Var, Expr]]:
        """Validate changed event-parameter expressions against one namespace.

        Unchanged ``Const(None)`` values remain available for external power-flow
        seeding. Every edited event row must instead become an explicit scalar
        value or expression.

        :param namespace: Explicit symbolic identities accepted in expressions.
        :return: Changed owner, variable, and parsed expression triples.
        """
        result: List[tuple[Block, Var, Expr]] = list()
        row: ParameterDraftRow
        for row in self._rows:
            if row.get_kind() != BlockSymbolKind.EVENT_PARAMETER or not row.has_changes():
                pass
            else:
                parsed_expression: Expr = row.parse_event_expression(namespace)
                result.append((row.get_owner(), row.get_variable(), parsed_expression))
        return result

    def get_pending_named_values(
            self,
            namespace: Mapping[str, Expr]) -> List[tuple[str, float | complex]]:
        """Validate and return transferable numeric values by semantic name.

        Structural regeneration can transfer scalar parameter values by name.
        Symbolic event expressions remain the builder's responsibility and are
        therefore omitted from this numeric transfer list.

        :param namespace: Explicit symbolic identities accepted in event expressions.
        :return: Staged constants by semantic variable name.
        """
        result: List[tuple[str, float | complex]] = list()
        row: ParameterDraftRow
        for row in self._rows:
            if row.is_unchanged_unset():
                pass
            elif row.get_kind() == BlockSymbolKind.PARAMETER:
                result.append((row.get_variable().name, row.parse_value()))
            else:
                event_expression: Expr = row.parse_event_expression(namespace)
                if isinstance(event_expression, Const):
                    event_value: object = event_expression.value
                    if isinstance(event_value, (int, float)) and not isinstance(event_value, bool):
                        result.append((row.get_variable().name, float(event_value)))
                    else:
                        pass
                elif row.has_changes():
                    raise ValueError(
                        f"Apply the symbolic expression for event parameter "
                        f"'{row.get_variable().name}' separately from structural changes"
                    )
                else:
                    pass
        return result


def validate_event_parameter_expression_dependencies(
        root_block: Block,
        pending_expressions: Sequence[tuple[Block, Var, Expr]]) -> None:
    """Reject cyclic initialization dependencies between event parameters.

    Event expressions may depend on state, algebraic, static, or other event
    variables. Only dependencies whose targets are also event parameters belong
    to this local graph; the complete initialization solver resolves the other
    DAE dependencies. A cycle between event parameters has no deterministic
    explicit initialization order and must be rejected before mutation.

    :param root_block: Complete edited block tree.
    :param pending_expressions: Changed event expressions staged by the dialogue.
    :return: None.
    :raises ValueError: If event expressions contain a cyclic dependency.
    """
    expressions_by_uid: Dict[int, Expr] = dict()
    names_by_uid: Dict[int, str] = dict()
    owner: Block
    event_variable: Var
    event_expression: Expr
    for owner in root_block.get_all_blocks():
        for event_variable, event_expression in owner.event_dict.items():
            expressions_by_uid[event_variable.uid] = event_expression
            names_by_uid[event_variable.uid] = event_variable.name

    pending_owner: Block
    for pending_owner, event_variable, event_expression in pending_expressions:
        _unused_pending_owner: Block = pending_owner
        expressions_by_uid[event_variable.uid] = event_expression
        names_by_uid[event_variable.uid] = event_variable.name

    dependent_uids: Dict[int, List[int]] = dict()
    in_degree: Dict[int, int] = dict()
    event_uid: int
    for event_uid in expressions_by_uid:
        dependent_uids[event_uid] = list()
        in_degree[event_uid] = 0

    for event_uid, event_expression in expressions_by_uid.items():
        dependency_uids_seen: set[int] = set()
        dependency_variable: Var
        for dependency_variable in get_expression_vars(event_expression):
            dependency_uid: int = dependency_variable.uid
            if dependency_uid not in expressions_by_uid or dependency_uid in dependency_uids_seen:
                pass
            else:
                dependency_uids_seen.add(dependency_uid)
                dependent_uids[dependency_uid].append(event_uid)
                in_degree[event_uid] += 1

    ready_uids: List[int] = list()
    for event_uid, degree in in_degree.items():
        if degree == 0:
            ready_uids.append(event_uid)
        else:
            pass

    ready_index: int = 0
    resolved_count: int = 0
    while ready_index < len(ready_uids):
        resolved_uid: int = ready_uids[ready_index]
        ready_index += 1
        resolved_count += 1
        dependent_uid: int
        for dependent_uid in dependent_uids[resolved_uid]:
            in_degree[dependent_uid] -= 1
            if in_degree[dependent_uid] == 0:
                ready_uids.append(dependent_uid)
            else:
                pass

    if resolved_count == len(expressions_by_uid):
        pass
    else:
        cyclic_names: List[str] = list()
        for event_uid, degree in in_degree.items():
            if degree > 0:
                cyclic_names.append(names_by_uid[event_uid])
            else:
                pass
        cyclic_names.sort()
        raise ValueError(
            "Cyclic event-parameter initialization: " + ", ".join(cyclic_names)
        )


def configure_interactive_table_header(header: QtWidgets.QHeaderView,
                                       initial_widths: Sequence[int]) -> None:
    """Make every column divider user-resizable and set readable initial widths.

    :param header: Horizontal table or tree header being configured.
    :param initial_widths: Initial pixel width for each available column.
    :return: None.
    """
    # Interactive mode is required on every section: Stretch and
    # ResizeToContents silently lock their dividers after the initial layout.
    header.setStretchLastSection(False)
    column_index: int
    for column_index in range(header.count()):
        header.setSectionResizeMode(
            column_index,
            QtWidgets.QHeaderView.ResizeMode.Interactive,
        )
        if column_index < len(initial_widths):
            header.resizeSection(column_index, initial_widths[column_index])
        else:
            pass


class BlockCodeBuffer:
    """Detached complete model source for one block in a recursive tree."""

    __slots__ = ("_block", "_code", "_original_code", "_original_runtime_signature")

    def __init__(self, block: Block) -> None:
        """
        Capture the initial equation source of one block.

        :param block: Symbolic block used by the operation.
        :return: None.
        """
        self._block: Block = block
        self._code: str = build_equation_code(block)
        self._original_code: str = self._code
        self._original_runtime_signature: str = build_runtime_code_signature(self._code)

    def get_block(self) -> Block:
        """
        Return the block that owns this source buffer.

        :return: The block that owns this source buffer.
        """
        return self._block

    def get_code(self) -> str:
        """
        Return the current detached source text.

        :return: The current detached source text.
        """
        return self._code

    def set_code(self, code: str) -> None:
        """
        Replace the detached source text.

        :param code: Value supplied for ``code``.
        :return: None.
        """
        self._code = code

    def has_changes(self) -> bool:
        """
        Return whether the user changed this equation buffer.

        :return: Whether the user changed this equation buffer.
        """
        return self._code != self._original_code

    def has_runtime_changes(self) -> bool:
        """Return whether retained modes or procedural calls changed semantically.

        :return: Whether either runtime section differs from the accepted baseline.
        """
        return build_runtime_code_signature(self._code) != self._original_runtime_signature

    def rename_identifier(self, old_name: str, new_name: str) -> None:
        """Propagate an editor-owned rename through draft and baseline source.

        Renaming an existing Engine variable is applied immediately by the
        Dynamic Editor. Updating both source versions keeps independent code
        edits dirty without treating the already-authoritative rename itself
        as an unapplied Block Properties change.

        :param old_name: Identifier replaced by the central editor.
        :param new_name: New authoritative identifier.
        :return: None.
        """
        self._code = replace_dae_identifier(self._code, old_name, new_name)
        self._original_code = replace_dae_identifier(
            self._original_code,
            old_name,
            new_name,
        )
        self._original_runtime_signature = build_runtime_code_signature(
            self._original_code
        )

    def accept_source(self, code: str) -> None:
        """Keep accepted source text as the baseline for subsequent edits.

        :param code: Validated source, including the user's comments and formatting.
        :return: None.
        """
        self._code = code
        self._original_code = code
        self._original_runtime_signature = build_runtime_code_signature(code)


class DaeCodeHighlighter(QtGui.QSyntaxHighlighter):
    """Small Python-like syntax highlighter specialized for DAE assignments."""

    __slots__ = (
        "_keyword_format",
        "_number_format",
        "_string_format",
        "_comment_format",
        "_symbol_format",
        "_function_format",
        "_symbol_names",
    )

    def __init__(
            self,
            document: QtGui.QTextDocument,
            symbol_names: Sequence[str],
            dark_theme: bool = False,
    ) -> None:
        """
        Create highlighting formats for DAE sections and known symbols.

        :param document: Value supplied for ``document``.
        :param symbol_names: Value supplied for ``symbol_names``.
        :param dark_theme: Whether to initialise formats for a dark background.
        :return: None.
        """
        super().__init__(document)
        self._keyword_format: QtGui.QTextCharFormat = QtGui.QTextCharFormat()
        self._number_format: QtGui.QTextCharFormat = QtGui.QTextCharFormat()
        self._string_format: QtGui.QTextCharFormat = QtGui.QTextCharFormat()
        self._comment_format: QtGui.QTextCharFormat = QtGui.QTextCharFormat()
        self._symbol_format: QtGui.QTextCharFormat = QtGui.QTextCharFormat()
        self._function_format: QtGui.QTextCharFormat = QtGui.QTextCharFormat()
        self._symbol_names: tuple[str, ...] = tuple(symbol_names)
        self.apply_theme(dark_theme=dark_theme)

    def apply_theme(self, dark_theme: bool) -> None:
        """Apply token colours with sufficient contrast for one editor theme.

        :param dark_theme: Whether the text document uses a dark background.
        :return: None.
        """
        # DAE categories keep the same visual roles in both themes. Only their
        # luminance changes, so users do not need to relearn the source colours
        # when switching the application appearance.
        if dark_theme:
            keyword_color: QtGui.QColor = QtGui.QColor("#C792EA")
            number_color: QtGui.QColor = QtGui.QColor("#C3E88D")
            string_color: QtGui.QColor = QtGui.QColor("#F07178")
            comment_color: QtGui.QColor = QtGui.QColor("#94A3B8")
            symbol_color: QtGui.QColor = QtGui.QColor("#FFCB6B")
            function_color: QtGui.QColor = QtGui.QColor("#82AAFF")
        else:
            keyword_color = QtGui.QColor("#7C3AED")
            number_color = QtGui.QColor("#0369A1")
            string_color = QtGui.QColor("#15803D")
            comment_color = QtGui.QColor("#64748B")
            symbol_color = QtGui.QColor("#B45309")
            function_color = QtGui.QColor("#0369A1")

        self._keyword_format.setForeground(keyword_color)
        self._keyword_format.setFontWeight(QtGui.QFont.Weight.Bold)
        self._number_format.setForeground(number_color)
        self._string_format.setForeground(string_color)
        self._comment_format.setForeground(comment_color)
        self._comment_format.setFontItalic(True)
        self._symbol_format.setForeground(symbol_color)
        self._function_format.setForeground(function_color)
        self._function_format.setFontWeight(QtGui.QFont.Weight.Bold)
        self.rehighlight()

    def set_dark_mode(self) -> None:
        """Apply syntax colours intended for a dark source editor.

        :return: None.
        """
        self.apply_theme(dark_theme=True)

    def set_light_mode(self) -> None:
        """Apply syntax colours intended for a light source editor.

        :return: None.
        """
        self.apply_theme(dark_theme=False)

    def set_symbol_names(self, symbol_names: Sequence[str]) -> None:
        """
        Replace known identifiers and rehighlight the complete document.

        :param symbol_names: Value supplied for ``symbol_names``.
        :return: None.
        """
        self._symbol_names = tuple(symbol_names)
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        """
        Apply deterministic formats to one visible source line.

        :param text: User-entered text.
        :return: None.
        """
        section_names: tuple[str, ...] = get_dae_section_names()
        section_name: str
        for section_name in section_names:
            self._apply_pattern(text, rf"\b{re.escape(section_name)}\b", self._keyword_format)

        self._apply_pattern(text, r"\b(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?j?\b", self._number_format)
        self._apply_pattern(text, r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", self._string_format)

        symbol_name: str
        for symbol_name in self._symbol_names:
            self._apply_pattern(text, rf"\b{re.escape(symbol_name)}\b", self._symbol_format)

        # The Engine catalogue is the only accepted source of symbolic
        # function names, so highlighting cannot drift from lint or completion.
        function_name: str
        for function_name in get_symbolic_parser_function_names():
            self._apply_pattern(
                text,
                rf"\b{re.escape(function_name)}\b(?=\s*\()",
                self._function_format,
            )
        descriptor: ProceduralBlockTemplateDescriptor
        for descriptor in get_dynamic_library_procedural_descriptors():
            self._apply_pattern(
                text,
                rf"\b{re.escape(descriptor.logic_tpe.value)}\b(?=\s*\()",
                self._function_format,
            )

        comment_index: int = text.find("#")
        if comment_index >= 0:
            self.setFormat(comment_index, len(text) - comment_index, self._comment_format)
        else:
            pass

    def _apply_pattern(self, text: str, pattern_text: str, text_format: QtGui.QTextCharFormat) -> None:
        """
        Apply one regular-expression format to all matches in a line.

        :param text: User-entered text.
        :param pattern_text: Value supplied for ``pattern_text``.
        :param text_format: Value supplied for ``text_format``.
        :return: None.
        """
        pattern: re.Pattern[str] = re.compile(pattern_text)
        match: re.Match[str]
        for match in pattern.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), text_format)


class DaeCodeEditor(BasePythonCodeEditor):
    """Symbolic DAE editor with lint feedback, search, and safe completion."""

    __slots__ = (
        "_diagnostics",
        "_search_ranges",
        "_active_search_index",
        "_symbol_namespace",
        "_language_context",
        "_highlighter",
        "_qt_completer",
        "_completion_model",
        "_completion_shortcut",
        "_completion_entries",
        "_last_completion_prefix",
        "_prepared_to_delete",
    )

    def __init__(
            self,
            parent: QtWidgets.QWidget | None = None,
            symbol_namespace: Mapping[str, Expr] | None = None,
            dark_theme: bool | None = None,
    ) -> None:
        """Create the DAE-specific parser state and visual overlays.

        :param parent: Optional owning Qt widget.
        :param symbol_namespace: Symbols accepted by the safe DAE parser.
        :param dark_theme: Explicit initial theme, or ``None`` to inherit it from Qt.
        :return: None.
        """
        self._qt_completer: QtWidgets.QCompleter | None = None
        self._prepared_to_delete: bool = False
        if dark_theme is None:
            # Standalone uses inherit Qt's active palette. Block properties
            # supplies an explicit value from DynamicBlockEditorGUI, while this
            # fallback keeps reusable or test-created DAE editors theme-neutral.
            editor_palette: QtGui.QPalette
            if parent is not None:
                editor_palette = parent.palette()
            else:
                application: QtCore.QCoreApplication | None = QtWidgets.QApplication.instance()
                if isinstance(application, QtWidgets.QApplication):
                    editor_palette = application.palette()
                else:
                    editor_palette = QtGui.QPalette()
            window_color: QtGui.QColor = editor_palette.color(
                QtGui.QPalette.ColorRole.Window
            )
            resolved_dark_theme: bool = window_color.lightness() < 128
        else:
            resolved_dark_theme = dark_theme
        super().__init__(parent, dark_theme=resolved_dark_theme)
        self._diagnostics: List[DaeCodeDiagnostic] = list()
        self._search_ranges: List[tuple[int, int]] = list()
        self._active_search_index: int = -1
        if symbol_namespace is None:
            self._symbol_namespace: Dict[str, Expr] = dict()
        else:
            self._symbol_namespace = dict(symbol_namespace)
        self._language_context: DaeLanguageContext = build_generic_dae_language_context(
            self._symbol_namespace
        )
        # The syntax highlighter belongs to the source editor whose document it
        # formats. Keeping both palettes here guarantees that surface and token
        # colours always change together.
        self._highlighter: DaeCodeHighlighter = DaeCodeHighlighter(
            self.document(),
            tuple(self._symbol_namespace.keys()),
            dark_theme=resolved_dark_theme,
        )

        # QCompleter only presents entries generated by the restricted DAE
        # language service. It never evaluates symbolic objects or exposes the
        # Python builtins available to the executable Scripting editor.
        self._qt_completer = QtWidgets.QCompleter(self)
        self._qt_completer.setWidget(self)
        self._qt_completer.setCompletionMode(
            QtWidgets.QCompleter.CompletionMode.PopupCompletion
        )
        self._qt_completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self._qt_completer.setFilterMode(QtCore.Qt.MatchFlag.MatchStartsWith)
        self._qt_completer.setMaxVisibleItems(12)
        self._completion_model: QtGui.QStandardItemModel = QtGui.QStandardItemModel(self)
        self._qt_completer.setModel(self._completion_model)
        self._qt_completer.activated[QtCore.QModelIndex].connect(
            self._insert_completion
        )
        self._completion_entries: List[DaeCompletionEntry] = list()
        self._last_completion_prefix: str = ""
        # QCompleter installs an event filter on the editor and its popup. On
        # some Windows Qt builds that filter consumes Tab before keyPressEvent
        # reaches this class. Installing the editor's filter last guarantees
        # that accepting a completion is independent of mouse interaction.
        self.installEventFilter(self)
        self.viewport().installEventFilter(self)
        self._qt_completer.popup().installEventFilter(self)
        self._qt_completer.popup().viewport().installEventFilter(self)
        self._completion_shortcut: QtGui.QShortcut = QtGui.QShortcut(
            QtGui.QKeySequence("Ctrl+Space"),
            self,
        )
        self._completion_shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        self._completion_shortcut.activated.connect(self._trigger_manual_completion)

    def prepare_to_delete(self) -> None:
        """Detach completion event filters before Qt destroys the editor.

        ``QCompleter`` owns a popup outside the text editor's ordinary widget
        subtree. Both that popup and its viewport retain event-filter pointers
        to this Python-backed editor. Removing those pointers while every
        QObject is still valid prevents queued events from reaching a deleted
        Shiboken wrapper during a later event-loop pass.

        :return: None.
        """
        if self._prepared_to_delete:
            return
        else:
            pass

        self._prepared_to_delete = True
        self._highlighter.setDocument(None)
        completer: QtWidgets.QCompleter | None = self._qt_completer
        if completer is not None:
            popup: QtWidgets.QAbstractItemView = completer.popup()
            popup_viewport: QtWidgets.QWidget = popup.viewport()

            # Remove the Python event filter before detaching the completer.
            # The popup may otherwise receive a queued Qt event after this
            # editor's native object has already been released.
            self.removeEventFilter(self)
            self.viewport().removeEventFilter(self)
            popup.removeEventFilter(self)
            popup_viewport.removeEventFilter(self)
            popup.hide()

            try:
                completer.activated[QtCore.QModelIndex].disconnect(
                    self._insert_completion
                )
            except (RuntimeError, TypeError):
                pass
            completer.setWidget(None)
            completer.setModel(None)
            self._qt_completer = None
        else:
            pass

        try:
            self._completion_shortcut.activated.disconnect(
                self._trigger_manual_completion
            )
        except (RuntimeError, TypeError):
            pass
        self._completion_shortcut.setEnabled(False)

        # Clear Python-side references only after the Qt completer no longer
        # observes the model or editor. The parent widget will subsequently
        # destroy the child QObjects in Qt's normal ownership order.
        self._completion_model.clear()
        self._completion_entries.clear()
        self._search_ranges.clear()

    def set_language_context(self, language_context: DaeLanguageContext) -> None:
        """Synchronize validation and completion with one staged block context.

        :param language_context: Current symbols and owner-specific DAE roles.
        :return: None.
        """
        self._language_context = language_context
        self._symbol_namespace = language_context.get_namespace()
        self._highlighter.set_symbol_names(tuple(self._symbol_namespace.keys()))
        self._hide_completion_popup()

    def set_dark_mode(self) -> None:
        """Apply dark surface and DAE syntax palettes as one operation.

        :return: None.
        """
        BasePythonCodeEditor.set_dark_mode(self)
        self._highlighter.set_dark_mode()

    def set_light_mode(self) -> None:
        """Apply light surface and DAE syntax palettes as one operation.

        :return: None.
        """
        BasePythonCodeEditor.set_light_mode(self)
        self._highlighter.set_light_mode()

    def get_language_context(self) -> DaeLanguageContext:
        """Return the immutable completion context currently in use.

        :return: Active DAE language context.
        """
        return self._language_context

    def get_completion_entries(self) -> List[DaeCompletionEntry]:
        """Return the candidates currently presented by the popup.

        :return: Detached current completion entries.
        """
        return list(self._completion_entries)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Coordinate popup navigation and automatic identifier completion.

        :param event: Incoming keyboard event.
        :return: None.
        """
        completer: QtWidgets.QCompleter | None = self._qt_completer
        if completer is None:
            BasePythonCodeEditor.keyPressEvent(self, event)
            return
        else:
            pass
        popup: QtWidgets.QAbstractItemView = completer.popup()
        popup_visible: bool = popup.isVisible()
        pressed_key: int = event.key()
        pressed_text: str = event.text()
        completion_keys: tuple[QtCore.Qt.Key, ...] = (
            QtCore.Qt.Key.Key_Tab,
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.Key.Key_Enter,
        )
        navigation_keys: tuple[QtCore.Qt.Key, ...] = (
            QtCore.Qt.Key.Key_Up,
            QtCore.Qt.Key.Key_Down,
            QtCore.Qt.Key.Key_PageUp,
            QtCore.Qt.Key.Key_PageDown,
        )
        editing_keys: tuple[QtCore.Qt.Key, ...] = (
            QtCore.Qt.Key.Key_Backspace,
            QtCore.Qt.Key.Key_Delete,
        )
        inserts_printable_text: bool = (
            len(pressed_text) > 0
            and pressed_text.isprintable()
            and pressed_key not in completion_keys
            and pressed_key != QtCore.Qt.Key.Key_Escape
        )

        if popup_visible and pressed_key in completion_keys:
            self._accept_current_completion()
            event.accept()
        elif popup_visible and pressed_key == QtCore.Qt.Key.Key_Escape:
            self._hide_completion_popup()
            event.accept()
        elif popup_visible and pressed_key in navigation_keys:
            # QCompleter owns popup navigation while its event filter is active.
            QtWidgets.QPlainTextEdit.event(self, event)
        elif inserts_printable_text:
            # Text is inserted before recalculating the prefix. This order is
            # required for Windows layouts that generate symbols through AltGr.
            BasePythonCodeEditor.keyPressEvent(self, event)
            if pressed_text[-1].isalnum() or pressed_text[-1] == "_":
                self._trigger_automatic_completion()
            else:
                self._hide_completion_popup()
        elif pressed_key in editing_keys:
            BasePythonCodeEditor.keyPressEvent(self, event)
            self._trigger_automatic_completion()
        else:
            self._hide_completion_popup()
            BasePythonCodeEditor.keyPressEvent(self, event)

    def eventFilter(self,
                    watched: QtCore.QObject,
                    event: QtCore.QEvent) -> bool:
        """Accept popup completion before Qt consumes Tab or Enter.

        The filter is limited to the editor and its completion view. Normal
        tabulation therefore continues through :class:`BasePythonCodeEditor`
        whenever the completion popup is closed.

        :param watched: Qt object currently receiving the event.
        :param event: Event offered to the installed filter.
        :return: ``True`` only when the popup consumes an acceptance key.
        """
        procedural_help_requested: bool = (
            watched is self.viewport()
            and event.type() == QtCore.QEvent.Type.ToolTip
            and isinstance(event, QtGui.QHelpEvent)
        )
        if procedural_help_requested and isinstance(event, QtGui.QHelpEvent):
            help_cursor: QtGui.QTextCursor = self.cursorForPosition(event.pos())
            help_cursor.select(QtGui.QTextCursor.SelectionType.WordUnderCursor)
            code_name: str = help_cursor.selectedText()
            help_text: str | None = get_procedural_logic_help_by_code_name(code_name)
            if help_text is not None:
                QtWidgets.QToolTip.showText(
                    event.globalPos(),
                    help_text,
                    self.viewport(),
                )
                return True
            else:
                pass
        else:
            pass

        completer: QtWidgets.QCompleter | None = self._qt_completer
        if completer is None:
            return BasePythonCodeEditor.eventFilter(self, watched, event)
        else:
            pass
        popup: QtWidgets.QAbstractItemView = completer.popup()
        completion_target: bool = (
            watched is self
            or watched is popup
            or watched is popup.viewport()
        )
        completion_accept_keys: tuple[QtCore.Qt.Key, ...] = (
            QtCore.Qt.Key.Key_Tab,
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.Key.Key_Enter,
        )
        consumes_completion_key: bool = (
            completion_target
            and popup.isVisible()
            and event.type() == QtCore.QEvent.Type.KeyPress
            and isinstance(event, QtGui.QKeyEvent)
            and event.key() in completion_accept_keys
        )
        if consumes_completion_key and isinstance(event, QtGui.QKeyEvent):
            self._accept_current_completion()
            event.accept()
            result: bool = True
        else:
            result = BasePythonCodeEditor.eventFilter(self, watched, event)
        return result

    def event(self, event: QtCore.QEvent) -> bool:
        """Preserve AltGr text while reserving Ctrl+Space for completion.

        :param event: Qt event routed to the editor.
        :return: ``True`` when the event is completely handled.
        """
        if (event.type() == QtCore.QEvent.Type.ShortcutOverride
                and isinstance(event, QtGui.QKeyEvent)):
            pressed_text: str = event.text()
            is_ctrl_space: bool = (
                event.key() == QtCore.Qt.Key.Key_Space
                and event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier
            )
            if is_ctrl_space:
                result: bool = BasePythonCodeEditor.event(self, event)
            elif len(pressed_text) > 0 and pressed_text.isprintable():
                event.accept()
                result = True
            else:
                result = BasePythonCodeEditor.event(self, event)
        else:
            result = BasePythonCodeEditor.event(self, event)
        return result

    @QtCore.Slot()
    def _trigger_manual_completion(self) -> None:
        """Show every context-valid candidate matching the current prefix.

        :return: None.
        """
        self._show_completion(require_minimum_prefix=False)

    def _trigger_automatic_completion(self) -> None:
        """Show candidates after two identifier characters are present.

        :return: None.
        """
        self._show_completion(require_minimum_prefix=True)

    def _show_completion(self, require_minimum_prefix: bool) -> None:
        """Populate and position the popup for the current lexical context.

        :param require_minimum_prefix: Whether fewer than two characters hide the popup.
        :return: None.
        """
        source: str = self.toPlainText()
        source_cursor: QtGui.QTextCursor = self.textCursor()
        if source_cursor.hasSelection():
            # Completion replaces an explicitly selected placeholder. Analyze
            # the surrounding source as if that selection were already gone,
            # otherwise a selected ``None`` would incorrectly become the
            # filtering prefix and hide every valid model symbol.
            selection_start: int = min(
                source_cursor.anchor(),
                source_cursor.position(),
            )
            selection_end: int = max(
                source_cursor.anchor(),
                source_cursor.position(),
            )
            completion_source: str = source[:selection_start] + source[selection_end:]
            cursor_position: int = selection_start
        else:
            completion_source = source
            cursor_position = source_cursor.position()
        position: DaeCompletionPosition = analyze_dae_completion_position(
            completion_source,
            cursor_position,
        )
        prefix: str = position.get_prefix()
        if require_minimum_prefix and len(prefix) < 2:
            self._hide_completion_popup()
            return
        else:
            pass

        entries: List[DaeCompletionEntry] = build_dae_completion_entries(
            self._language_context,
            position,
        )
        if len(entries) == 0:
            self._hide_completion_popup()
            return
        elif (require_minimum_prefix
              and len(entries) == 1
              and entries[0].get_name().lower() == prefix.lower()):
            self._hide_completion_popup()
            return
        else:
            pass

        self._completion_entries = entries
        self._last_completion_prefix = prefix
        self._completion_model.clear()
        popup: QtWidgets.QAbstractItemView = self._qt_completer.popup()
        entry_index: int
        entry: DaeCompletionEntry
        for entry_index, entry in enumerate(entries):
            label: str = f"{entry.get_display_text()}    {entry.get_description()}"
            item: QtGui.QStandardItem = QtGui.QStandardItem(label)
            item.setEditable(False)
            item.setToolTip(entry.get_tooltip())
            item.setData(entry_index, QtCore.Qt.ItemDataRole.UserRole)
            self._completion_model.appendRow(item)
        self._qt_completer.setCompletionPrefix(prefix)
        completion_rectangle: QtCore.QRect = self.cursorRect()
        popup_width: int = (
            popup.sizeHintForColumn(0)
            + popup.verticalScrollBar().sizeHint().width()
        )
        completion_rectangle.setWidth(min(max(260, popup_width), 620))
        self._qt_completer.complete(completion_rectangle)
        completion_model: QtCore.QAbstractItemModel | None = popup.model()
        if completion_model is not None and completion_model.rowCount() > 0:
            first_index: QtCore.QModelIndex = completion_model.index(0, 0)
            popup.setCurrentIndex(first_index)
        else:
            pass

    def _accept_current_completion(self) -> bool:
        """Insert the selected popup entry, falling back to its first row.

        :return: Whether a valid completion entry was inserted.
        """
        popup: QtWidgets.QAbstractItemView = self._qt_completer.popup()
        completion_index: QtCore.QModelIndex = popup.currentIndex()
        completion_model: QtCore.QAbstractItemModel | None = popup.model()
        if (not completion_index.isValid()
                and completion_model is not None
                and completion_model.rowCount() > 0):
            completion_index = completion_model.index(0, 0)
            popup.setCurrentIndex(completion_index)
        else:
            pass
        if completion_index.isValid():
            self._insert_completion(completion_index)
            result: bool = True
        else:
            self._hide_completion_popup()
            result = False
        return result

    @QtCore.Slot(QtCore.QModelIndex)
    def _insert_completion(self, completion_index: QtCore.QModelIndex) -> None:
        """Replace the current identifier prefix with one selected candidate.

        :param completion_index: Popup model index carrying the source entry index.
        :return: None.
        """
        entry_data: object = completion_index.data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(entry_data, int) and 0 <= entry_data < len(self._completion_entries):
            entry: DaeCompletionEntry = self._completion_entries[entry_data]
            text_cursor: QtGui.QTextCursor = self.textCursor()
            text_cursor.beginEditBlock()
            if text_cursor.hasSelection():
                # The selected placeholder or user selection is already the
                # exact source range that completion must replace.
                pass
            else:
                text_cursor.movePosition(
                    QtGui.QTextCursor.MoveOperation.Left,
                    QtGui.QTextCursor.MoveMode.KeepAnchor,
                    len(self._last_completion_prefix),
                )
            text_cursor.removeSelectedText()
            text_cursor.insertText(entry.get_insertion_text())
            cursor_backtrack: int = entry.get_cursor_backtrack()
            if cursor_backtrack > 0:
                text_cursor.movePosition(
                    QtGui.QTextCursor.MoveOperation.Left,
                    QtGui.QTextCursor.MoveMode.MoveAnchor,
                    cursor_backtrack,
                )
            else:
                pass
            selection_length: int = entry.get_selection_length()
            if selection_length > 0:
                text_cursor.movePosition(
                    QtGui.QTextCursor.MoveOperation.Left,
                    QtGui.QTextCursor.MoveMode.KeepAnchor,
                    selection_length,
                )
            else:
                pass
            text_cursor.endEditBlock()
            self.setTextCursor(text_cursor)
        else:
            pass
        self._hide_completion_popup()

    def _hide_completion_popup(self) -> None:
        """Hide the popup and discard entries tied to an obsolete prefix.

        :return: None.
        """
        self._qt_completer.popup().hide()
        self._completion_entries.clear()
        self._last_completion_prefix = ""

    def build_current_diagnostics(self) -> List[DaeCodeDiagnostic]:
        """Analyze the visible source against the symbolic namespace.

        :return: Syntax and unknown-symbol diagnostics in source order.
        """
        return build_dae_code_diagnostics(self.toPlainText(), self._symbol_namespace)

    def parse_current_code(self) -> BlockEquationDraft:
        """Parse the visible source using the safe assignment-only DAE parser.

        :return: Parsed equation draft retaining the namespace identities.
        :raises ValueError: If the DAE source is unsupported or invalid.
        """
        return parse_equation_code(self.toPlainText(), self._symbol_namespace)

    def get_diagnostics(self) -> List[DaeCodeDiagnostic]:
        """Return diagnostics currently rendered by the editor.

        :return: Current diagnostic collection.
        """
        return list(self._diagnostics)

    def set_diagnostics(self, diagnostics: Sequence[DaeCodeDiagnostic]) -> None:
        """Underline every invalid source span and attach its local explanation.

        :param diagnostics: Complete diagnostics for the visible equation owner.
        :return: None.
        """
        self._diagnostics = list(diagnostics)
        self._refresh_extra_selections()

    def set_search_text(self, search_text: str) -> int:
        """Highlight every case-insensitive source-code match.

        :param search_text: Text requested by the user.
        :return: Number of matches in the current equation buffer.
        """
        source_text: str = self.toPlainText()
        normalized_query: str = search_text.strip().lower()
        self._search_ranges.clear()
        self._active_search_index = -1

        if len(normalized_query) > 0:
            normalized_source: str = source_text.lower()
            start_position: int = normalized_source.find(normalized_query)
            while start_position >= 0:
                self._search_ranges.append((start_position, len(normalized_query)))
                start_position = normalized_source.find(
                    normalized_query,
                    start_position + max(1, len(normalized_query)),
                )
            if len(self._search_ranges) > 0:
                self._active_search_index = 0
            else:
                pass
        else:
            pass

        self._activate_current_search_match()
        return len(self._search_ranges)

    def move_to_search_match(self, offset: int) -> tuple[int, int]:
        """Move to the previous or next highlighted source-code match.

        :param offset: Relative match offset, normally ``-1`` or ``1``.
        :return: One-based active match and total match count.
        """
        match_count: int = len(self._search_ranges)
        if match_count > 0:
            self._active_search_index = (self._active_search_index + offset) % match_count
        else:
            self._active_search_index = -1
        self._activate_current_search_match()
        return self._active_search_index + 1, match_count

    def get_search_position(self) -> tuple[int, int]:
        """Return the one-based active match and total match count.

        :return: Current search position and match count.
        """
        return self._active_search_index + 1, len(self._search_ranges)

    def _activate_current_search_match(self) -> None:
        """Select the active source-code match and refresh all overlays.

        :return: None.
        """
        if 0 <= self._active_search_index < len(self._search_ranges):
            start_position: int
            match_length: int
            start_position, match_length = self._search_ranges[self._active_search_index]
            cursor: QtGui.QTextCursor = self.textCursor()
            cursor.setPosition(start_position)
            cursor.setPosition(start_position + match_length, QtGui.QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)
            self.centerCursor()
        else:
            pass
        self._refresh_extra_selections()

    def _refresh_extra_selections(self) -> None:
        """Paint diagnostics and searches without either hiding the other.

        :return: None.
        """
        selections: List[QtWidgets.QTextEdit.ExtraSelection] = list()
        diagnostic: DaeCodeDiagnostic
        for diagnostic in self._diagnostics:
            text_block: QtGui.QTextBlock = self.document().findBlockByNumber(
                diagnostic.get_line() - 1
            )
            if text_block.isValid():
                line_length: int = max(0, text_block.length() - 1)
                if line_length > 0:
                    start_column: int = min(diagnostic.get_column(), line_length - 1)
                    selection_length: int = min(
                        diagnostic.get_length(),
                        line_length - start_column,
                    )
                else:
                    start_column = 0
                    selection_length = 1
                cursor: QtGui.QTextCursor = QtGui.QTextCursor(text_block)
                cursor.setPosition(text_block.position() + start_column)
                cursor.setPosition(
                    min(
                        text_block.position() + text_block.length() - 1,
                        cursor.position() + selection_length,
                    ),
                    QtGui.QTextCursor.MoveMode.KeepAnchor,
                )
                selection: QtWidgets.QTextEdit.ExtraSelection = QtWidgets.QTextEdit.ExtraSelection()
                selection.cursor = cursor
                selection.format.setForeground(QtGui.QColor("#b42318"))
                selection.format.setBackground(QtGui.QColor("#fee2e2"))
                selection.format.setUnderlineColor(QtGui.QColor("#dc2626"))
                selection.format.setUnderlineStyle(QtGui.QTextCharFormat.UnderlineStyle.WaveUnderline)
                selection.format.setToolTip(diagnostic.get_message())
                selections.append(selection)
            else:
                pass

        search_index: int
        search_range: tuple[int, int]
        for search_index, search_range in enumerate(self._search_ranges):
            search_start: int
            search_length: int
            search_start, search_length = search_range
            search_cursor: QtGui.QTextCursor = QtGui.QTextCursor(self.document())
            search_cursor.setPosition(search_start)
            search_cursor.setPosition(
                search_start + search_length,
                QtGui.QTextCursor.MoveMode.KeepAnchor,
            )
            search_selection: QtWidgets.QTextEdit.ExtraSelection = QtWidgets.QTextEdit.ExtraSelection()
            search_selection.cursor = search_cursor
            if search_index == self._active_search_index:
                search_selection.format.setBackground(QtGui.QColor("#fbbf24"))
            else:
                search_selection.format.setBackground(QtGui.QColor("#fef3c7"))
            selections.append(search_selection)
        self.setExtraSelections(selections)
        if len(self._diagnostics) > 0:
            summary: str = "\n".join(
                f"Line {diagnostic.get_line()}: {diagnostic.get_message()}"
                for diagnostic in self._diagnostics
            )
            self.setToolTip(summary)
        else:
            self.setToolTip("")


def build_block_symbol_namespace(block: Block) -> Dict[str, Expr]:
    """
    Build a complete safe parser namespace from one selected block tree.

    :param block: Symbolic block used by the operation.
    :return: Complete safe-parser namespace for the selected block tree.
    """
    namespace: Dict[str, Expr] = dict()
    child: Block
    variable: Var
    for child in block.get_all_blocks():
        variable_groups: tuple[Sequence[Var], ...] = (
            child.algebraic_vars,
            child.state_vars,
            child.diff_vars,
            child.in_vars,
            child.out_vars,
            tuple(child.parameters.keys()),
            tuple(child.event_dict.keys()),
            tuple(child.mode_dict.keys()),
            tuple(child.init_values.keys()),
            tuple(child.init_eqs.keys()),
            tuple(child.diff_init_eqs.keys()),
            tuple(child.discrete_eqs.keys()),
            tuple(child.boolean_guards.keys()),
            tuple(child.external_mapping.values()),
            tuple(child.api_obj_mapping.values()),
        )
        group: Sequence[Var]
        for group in variable_groups:
            for variable in group:
                if isinstance(variable, Var):
                    namespace[variable.name] = variable
                else:
                    pass

        # Some valid templates intentionally keep mapped or intermediate Vars
        # only inside expressions. Collecting those leaves the parser aligned
        # with the actual symbolic model instead of only its display lists.
        expression_groups: tuple[Sequence[Expr], ...] = (
            child.state_eqs,
            child.algebraic_eqs,
            tuple(child.init_eqs.values()),
            tuple(child.diff_init_eqs.values()),
            tuple(child.discrete_eqs.values()),
            tuple(child.event_dict.values()),
            tuple(child.mode_dict.values()),
        )
        expression_group: Sequence[Expr]
        expression: Expr
        expression_variable: Var
        for expression_group in expression_groups:
            for expression in expression_group:
                if isinstance(expression, Expr):
                    for expression_variable in get_expression_vars(expression):
                        namespace[expression_variable.name] = expression_variable
                else:
                    pass

        # Runtime logic can read simulation-owned symbols, such as the global
        # time variable, which intentionally do not belong to a DAE display
        # list. Include those identities so an existing catalogue block can be
        # opened, validated and reapplied without rewriting its expressions.
        procedural_entry: ProceduralLogicBase
        procedural_variable: Var
        for procedural_entry in child.procedural_logic:
            for procedural_variable in get_procedural_expression_variables(procedural_entry):
                namespace[procedural_variable.name] = procedural_variable
    return namespace


def get_dae_symbol_completion_description(kind: BlockSymbolKind) -> str:
    """Return a concise DAE role description for one symbol-table kind.

    :param kind: Primary role shown by the Variables or Parameters table.
    :return: User-facing completion description.
    """
    if kind == BlockSymbolKind.INPUT:
        result: str = "Input variable"
    elif kind == BlockSymbolKind.STATE:
        result = "State variable"
    elif kind == BlockSymbolKind.ALGEBRAIC:
        result = "Algebraic variable"
    elif kind == BlockSymbolKind.DIFFERENTIAL:
        result = "Differential variable"
    elif kind == BlockSymbolKind.EVENT_PARAMETER:
        result = "Event parameter"
    elif kind == BlockSymbolKind.PARAMETER:
        result = "Static parameter"
    elif kind == BlockSymbolKind.MODE_PARAMETER:
        result = "Runtime mode parameter"
    elif kind == BlockSymbolKind.OUTPUT_ONLY:
        result = "Legacy output variable"
    else:
        result = "Symbolic variable or parameter"
    return result


def build_dialogue_dae_language_context(
        namespace: Mapping[str, Expr],
        symbol_model: BlockSymbolDraftModel,
        root_block: Block,
        equation_owner: Block,
        retained_mode_names: Sequence[str]) -> DaeLanguageContext:
    """Build the shared parser/completion context from staged dialogue rows.

    :param namespace: Joint DAE and runtime-logic validation namespace.
    :param symbol_model: Detached Variables and Parameters table model.
    :param root_block: Complete edited block tree containing external mappings.
    :param equation_owner: Block owning the currently visible equation buffer.
    :param retained_mode_names: Staged retained modes available to procedural outputs.
    :return: Synchronized language context for the DAE editor.
    """
    entries: List[DaeCompletionEntry] = list()
    initializable_names: List[str] = list()
    names_seen: set[str] = set()
    entry_indices: Dict[str, int] = dict()
    procedural_variable_names: List[str] = list()
    runtime_parameter_names: List[str] = list()
    power_flow_initialized_variables: set[Var] = set()
    procedural_variable_kinds: tuple[BlockSymbolKind, ...] = (
        BlockSymbolKind.INPUT,
        BlockSymbolKind.STATE,
        BlockSymbolKind.ALGEBRAIC,
        BlockSymbolKind.DIFFERENTIAL,
        BlockSymbolKind.OUTPUT_ONLY,
    )
    mapped_owner: Block
    for mapped_owner in root_block.get_all_blocks():
        mapped_variable: Var | None
        for mapped_variable in mapped_owner.external_mapping.values():
            if isinstance(mapped_variable, Var):
                power_flow_initialized_variables.add(mapped_variable)
            else:
                pass
    row_index: int
    for row_index in range(symbol_model.rowCount()):
        row: BlockSymbolDraftRow | None = symbol_model.get_row(row_index)
        if row is not None:
            symbol_name: str = row.get_name()
        else:
            symbol_name = ""
        if row is not None and symbol_name in namespace:
            completion_entry: DaeCompletionEntry = DaeCompletionEntry(
                name=symbol_name,
                display_text=symbol_name,
                insertion_text=symbol_name,
                description=get_dae_symbol_completion_description(row.get_kind()),
            )
            existing_entry_index: int | None = entry_indices.get(symbol_name, None)
            if existing_entry_index is None:
                names_seen.add(symbol_name)
                entry_indices[symbol_name] = len(entries)
                entries.append(completion_entry)
            elif row.get_owner() is equation_owner:
                # Shared wrapper identities may appear before their equation
                # owner. The active block's DAE role is the useful popup type.
                entries[existing_entry_index] = completion_entry
            else:
                pass
            generally_initializable_kinds: tuple[BlockSymbolKind, ...] = (
                BlockSymbolKind.STATE,
                BlockSymbolKind.ALGEBRAIC,
            )
            row_variable: Var | None = row.get_variable()
            is_initializable_unknown: bool = (
                row.get_owner() is equation_owner
                and row.get_kind() in generally_initializable_kinds
                and (
                    row_variable is None
                    or row_variable not in power_flow_initialized_variables
                )
            )
            if (is_initializable_unknown
                    and symbol_name not in initializable_names):
                initializable_names.append(symbol_name)
            else:
                pass
            if (
                    row.get_kind() in procedural_variable_kinds
                    and symbol_name not in procedural_variable_names
            ):
                procedural_variable_names.append(symbol_name)
            else:
                pass
            if (
                    row.get_kind() == BlockSymbolKind.EVENT_PARAMETER
                    and symbol_name not in runtime_parameter_names
            ):
                runtime_parameter_names.append(symbol_name)
            else:
                pass
        else:
            pass

    # Runtime modes and expression-only variables may be absent from the table
    # while remaining valid parser identities. They are still offered with a
    # deliberately generic description instead of being silently omitted.
    namespace_name: str
    for namespace_name in namespace:
        if namespace_name not in names_seen:
            names_seen.add(namespace_name)
            entries.append(
                DaeCompletionEntry(
                    name=namespace_name,
                    display_text=namespace_name,
                    insertion_text=namespace_name,
                    description="Symbolic variable or runtime value",
                )
            )
        else:
            pass

    return DaeLanguageContext(
        namespace=namespace,
        symbol_entries=entries,
        initializable_names=initializable_names,
        state_names=symbol_model.get_role_names(
            equation_owner,
            BlockSymbolKind.STATE,
        ),
        algebraic_names=symbol_model.get_role_names(
            equation_owner,
            BlockSymbolKind.ALGEBRAIC,
        ),
        differential_names=symbol_model.get_role_names(
            equation_owner,
            BlockSymbolKind.DIFFERENTIAL,
        ),
        mode_names=retained_mode_names,
        runtime_parameter_names=runtime_parameter_names,
        variable_names=procedural_variable_names,
    )


def build_equation_code(block: Block) -> str:
    """
    Serialize informative variable order and editable equations as safe code.

    :param block: Symbolic block used by the operation.
    :return: Ordered variable declarations and editable DAE sections.
    """
    lines: List[str] = list()
    lines.append(_serialize_variable_list("state_vars", block.state_vars))
    lines.append(_serialize_variable_list("algebraic_vars", block.algebraic_vars))
    lines.append(_serialize_variable_list("diff_vars", block.diff_vars))
    lines.append("")
    lines.extend(_serialize_state_equation_dict(
        state_variables=block.state_vars,
        state_equations=block.state_eqs,
        comments=list((
            "Map every state variable to the right-hand side of its differential equation.",
            "Example: for d_x = -x / T, write: x: -x / T,",
        )),
    ))
    lines.append("")
    lines.extend(_serialize_algebraic_equation_list(
        expressions=block.algebraic_eqs,
        comments=list((
            "Write each complete equation with one single '=' between its two sides.",
            "Examples: 0 = y - K * x, or y = K * x,",
        )),
    ))
    lines.append("")
    lines.extend(_serialize_expression_dict(
        name="init_eqs",
        expressions=block.init_eqs,
        comments=list(("Map each variable to its initial expression. Example: x: x0,",)),
    ))
    lines.append("")
    lines.extend(_serialize_expression_dict(
        name="diff_init_eqs",
        expressions=block.diff_init_eqs,
        comments=list(("Map each derivative to its initial expression. Example: d_x: 0.0,",)),
    ))
    lines.append("")
    lines.extend(build_runtime_logic_code(block))
    return "\n".join(lines)


def _serialize_variable_list(name: str, variables: Sequence[Var]) -> str:
    """Serialize one informative variable declaration on a single line.

    :param name: Declaration section name.
    :param variables: Ordered variables shown in the declaration.
    :return: One-line Python-like variable list.
    """
    variable_names: List[str] = list()
    variable: Var
    for variable in variables:
        variable_names.append(variable.name)
    return f"{name} = [{', '.join(variable_names)}]"


def synchronize_dae_variable_declarations(code: str,
                                          state_names: Sequence[str],
                                          algebraic_names: Sequence[str],
                                          differential_names: Sequence[str]) -> str:
    """Synchronize the three table-owned variable declarations in DAE code.

    Variable declarations are managed projections of the Variables table. A
    declaration may still be multiline while the user is editing, so each
    complete assignment is replaced as one unit without touching equations or
    any other source text. Missing declarations are restored at the beginning
    for compatibility with older hand-written buffers.

    :param code: Current detached DAE source.
    :param state_names: Ordered state-variable names from the table draft.
    :param algebraic_names: Ordered algebraic-variable names from the table draft.
    :param differential_names: Ordered differential-variable names from the table draft.
    :return: DAE source with synchronized one-line variable declarations.
    """
    sections: tuple[tuple[str, Sequence[str]], ...] = (
        ("state_vars", state_names),
        ("algebraic_vars", algebraic_names),
        ("diff_vars", differential_names),
    )
    updated_code: str = code
    missing_declarations: List[str] = list()
    section_name: str
    section_names: Sequence[str]
    for section_name, section_names in sections:
        declaration: str = f"{section_name} = [{', '.join(section_names)}]"
        declaration_pattern: str = (
            rf"(?ms)^[ \t]*{re.escape(section_name)}[ \t]*=[ \t]*\[[^\]]*\]"
        )
        replacement_count: int
        updated_code, replacement_count = re.subn(
            declaration_pattern,
            declaration,
            updated_code,
            count=1,
        )
        if replacement_count == 0:
            missing_declarations.append(declaration)
        else:
            pass

    if len(missing_declarations) > 0:
        if "\n" in updated_code:
            newline: str = "\n"
        else:
            newline = "\n"
        declaration_prefix: str = newline.join(missing_declarations)
        if len(updated_code) > 0:
            updated_code = declaration_prefix + newline + newline + updated_code
        else:
            updated_code = declaration_prefix
    else:
        pass
    return updated_code


def replace_dae_identifier(code: str, old_name: str, new_name: str) -> str:
    """Replace one Python identifier without altering partial symbol names.

    The DAE editor can contain an incomplete draft while a rename is requested.
    Token-aware replacement preserves normal source formatting; a word-boundary
    fallback still keeps that incomplete draft aligned with the renamed model.

    :param code: Current detached DAE source.
    :param old_name: Exact identifier used before the rename.
    :param new_name: Exact identifier accepted by the central editor rename.
    :return: Source using ``new_name`` for every matching identifier token.
    """
    if old_name == new_name:
        return code
    else:
        pass

    replaced_tokens: List[tokenize.TokenInfo] = list()
    try:
        source_token: tokenize.TokenInfo
        for source_token in tokenize.generate_tokens(StringIO(code).readline):
            if source_token.type == tokenize.NAME and source_token.string == old_name:
                replaced_tokens.append(source_token._replace(string=new_name))
            else:
                replaced_tokens.append(source_token)
        result: str = tokenize.untokenize(replaced_tokens)
    except (IndentationError, tokenize.TokenError):
        identifier_pattern: str = rf"\b{re.escape(old_name)}\b"
        result = re.sub(identifier_pattern, new_name, code)
    return result


def insert_source_before_section_closing_line(
        code: str,
        section_name: str,
        insertion_lines: Sequence[str],
) -> str:
    """Insert source immediately before a top-level list or dictionary closing line.

    :param code: Complete model-code buffer.
    :param section_name: Existing list or dictionary assignment to extend.
    :param insertion_lines: Fully indented lines inserted in source order.
    :return: Updated complete source.
    """
    _normalized_code: str
    module: ast.Module
    _normalized_code, module = parse_model_code_module(code)
    assignment: ast.Assign = get_model_code_assignment(module, section_name)
    if not isinstance(assignment.value, (ast.Dict, ast.List)):
        raise ValueError(f"Section '{section_name}' must be a list or dictionary")
    else:
        source_lines: List[str] = code.splitlines()
        closing_line_index: int = int(assignment.value.end_lineno) - 1
    insertion_index: int
    for insertion_index in range(len(insertion_lines)):
        source_lines.insert(
            closing_line_index + insertion_index,
            insertion_lines[insertion_index],
        )
    return "\n".join(source_lines)


def remove_source_dictionary_entries(code: str,
                                     section_name: str,
                                     entry_names: Sequence[str]) -> str:
    """Remove selected named entries from one top-level source dictionary.

    The edit uses AST locations only to identify dictionary entries. Unrelated
    expressions, comments, and formatting remain byte-for-byte unchanged. Both
    the normal multiline editor format and compact inline dictionaries are
    supported.

    :param code: Complete model-code buffer.
    :param section_name: Dictionary assignment containing managed entries.
    :param entry_names: Exact identifier keys to remove.
    :return: Source without the selected dictionary entries.
    """
    if len(entry_names) == 0:
        return code
    else:
        pass

    _normalized_code: str
    module: ast.Module
    _normalized_code, module = parse_model_code_module(code)
    assignment: ast.Assign = get_model_code_assignment(module, section_name)
    if not isinstance(assignment.value, ast.Dict):
        raise ValueError(f"Section '{section_name}' must be a dictionary")
    else:
        pass

    source_lines: List[str] = code.splitlines(keepends=True)
    line_offsets: List[int] = list()
    source_offset: int = 0
    source_line: str
    for source_line in source_lines:
        line_offsets.append(source_offset)
        source_offset += len(source_line)

    requested_names: set[str] = set(entry_names)
    removal_spans: List[tuple[int, int]] = list()
    entry_index: int
    for entry_index in range(len(assignment.value.keys)):
        key_node: ast.expr | None = assignment.value.keys[entry_index]
        value_node: ast.expr = assignment.value.values[entry_index]
        removable: bool = isinstance(key_node, ast.Name) and key_node.id in requested_names
        if removable and key_node is not None:
            entry_start: int = line_offsets[int(key_node.lineno) - 1] + int(key_node.col_offset)
            entry_end: int = line_offsets[int(value_node.end_lineno) - 1] + int(value_node.end_col_offset)

            # Include indentation when an entry owns its complete source line.
            entry_line_start: int = line_offsets[int(key_node.lineno) - 1]
            line_prefix: str = code[entry_line_start:entry_start]
            if len(line_prefix.strip()) == 0:
                entry_start = entry_line_start
            else:
                pass

            # Prefer consuming a following comma. If this is the final compact
            # entry, consume its preceding comma instead so the dictionary stays
            # syntactically valid.
            following_offset: int = entry_end
            while following_offset < len(code) and code[following_offset] in (" ", "\t"):
                following_offset += 1
            if following_offset < len(code) and code[following_offset] == ",":
                following_offset += 1
                line_end_offset: int = code.find("\n", following_offset)
                if line_end_offset < 0:
                    line_end_offset = len(code)
                else:
                    line_end_offset += 1
                trailing_source: str = code[following_offset:line_end_offset].strip()
                if len(trailing_source) == 0 or trailing_source.startswith("#"):
                    entry_end = line_end_offset
                else:
                    entry_end = following_offset
            else:
                preceding_offset: int = entry_start - 1
                while preceding_offset >= 0 and code[preceding_offset] in (" ", "\t"):
                    preceding_offset -= 1
                if preceding_offset >= 0 and code[preceding_offset] == ",":
                    entry_start = preceding_offset
                else:
                    pass
            removal_spans.append((entry_start, entry_end))
        else:
            pass

    removal_spans.sort(reverse=True)
    updated_code: str = code
    removal_start: int
    removal_end: int
    for removal_start, removal_end in removal_spans:
        updated_code = updated_code[:removal_start] + updated_code[removal_end:]
    return updated_code


def synchronize_retained_mode_source(
        code: str,
        owner: Block,
        modes: Sequence[RuntimeModeDraft],
) -> str:
    """Replace one owner's retained-mode dictionary from detached drafts.

    Only the managed runtime section is normalized. Equations, procedural
    calls, and their comments remain untouched, which keeps inline tree edits
    local and reviewable.

    :param code: Complete model-code buffer for ``owner``.
    :param owner: Direct block whose retained modes are serialized.
    :param modes: Active retained-mode drafts from the dialogue transaction.
    :return: Source with a synchronized ``retained_modes`` dictionary.
    """
    _normalized_code: str
    module: ast.Module
    _normalized_code, module = parse_model_code_module(code)
    assignment: ast.Assign = get_model_code_assignment(module, "retained_modes")
    replacement_lines: List[str] = list((
        "retained_modes = {",
        "    # Map each retained mode to its symbolic initialization expression.",
        "    # Example: latched_value: 0.0,",
    ))
    mode: RuntimeModeDraft
    for mode in modes:
        if mode.get_owner() is owner and not mode.is_removed():
            replacement_lines.append(
                f"    {mode.get_name()}: {mode.get_initial_expression()},"
            )
        else:
            pass
    replacement_lines.append("}")

    source_lines: List[str] = code.splitlines()
    first_line_index: int = int(assignment.lineno) - 1
    final_line_index: int = int(assignment.end_lineno)
    source_lines[first_line_index:final_line_index] = replacement_lines
    return "\n".join(source_lines)


def serialize_dae_expression(expression: Expr | Comparison) -> str:
    """Serialize one DAE expression without a redundant root pair.

    ``symbolic_to_string`` deliberately parenthesizes every binary expression
    to preserve its complete tree. At the top level of a list or dictionary
    value, that outermost pair has no effect. Inner pairs are retained because
    they can still be required for Python operator precedence.

    :param expression: Symbolic expression shown in the DAE source editor.
    :return: Parsable expression text without redundant root parentheses.
    """
    expression_text: str = symbolic_to_string(expression)
    if isinstance(expression, (BinOp, Comparison)):
        return expression_text[1:-1]
    else:
        return expression_text


def _serialize_algebraic_equation_list(
        expressions: Sequence[Expr],
        comments: Sequence[str] | None = None) -> List[str]:
    """Serialize Engine residuals as complete GUI algebraic equalities.

    The Engine stores each algebraic expression as a residual that must be
    zero. Placing zero on the visible left side preserves that expression
    exactly when the GUI parser converts the equality back to a residual.

    :param expressions: Ordered Engine algebraic residual expressions.
    :param comments: Explanatory lines inserted inside the generated list.
    :return: Complete algebraic equations serialized as readable source lines.
    """
    lines: List[str] = list(("algebraic_eqs = [",))
    if comments is not None:
        comment: str
        for comment in comments:
            lines.append(f"    # {comment}")
    else:
        pass
    expression: Expr
    for expression in expressions:
        lines.append(f"    0 = {serialize_dae_expression(expression)},")
    lines.append("]")
    return lines


def _serialize_state_equation_dict(
        state_variables: Sequence[Var],
        state_equations: Sequence[Expr],
        comments: Sequence[str] | None = None) -> List[str]:
    """Serialize state-variable/RHS associations as an editable dictionary.

    The Engine stores right-hand sides as a positional list. The GUI exposes
    the association explicitly so users never need to count list entries to
    identify a state equation. Inconsistent legacy models remain visible as
    comments and fail validation until the user repairs the missing pairing.

    :param state_variables: Ordered Engine state variables.
    :param state_equations: Ordered Engine right-hand-side expressions.
    :param comments: Explanatory lines inserted inside the generated mapping.
    :return: State equation mapping serialized as readable source lines.
    """
    lines: List[str] = list(("state_eqs = {",))
    if comments is not None:
        comment: str
        for comment in comments:
            lines.append(f"    # {comment}")
    else:
        pass

    paired_count: int = min(len(state_variables), len(state_equations))
    equation_index: int
    for equation_index in range(paired_count):
        state_variable: Var = state_variables[equation_index]
        state_equation: Expr = state_equations[equation_index]
        lines.append(
            f"    {state_variable.name}: {serialize_dae_expression(state_equation)},"
        )

    missing_index: int
    for missing_index in range(paired_count, len(state_variables)):
        lines.append(
            f"    # Missing equation for state variable: {state_variables[missing_index].name}"
        )

    extra_index: int
    for extra_index in range(paired_count, len(state_equations)):
        extra_equation: Expr = state_equations[extra_index]
        lines.append(
            f"    # Unassigned state equation: {serialize_dae_expression(extra_equation)}"
        )
    lines.append("}")
    return lines


def _serialize_expression_dict(name: str,
                               expressions: Mapping[Var, Expr],
                               comments: Sequence[str] | None = None) -> List[str]:
    """
    Serialize one variable-to-expression mapping.

    :param name: Value supplied for ``name``.
    :param expressions: Value supplied for ``expressions``.
    :param comments: Explanatory lines inserted inside the generated dictionary.
    :return: Variable-to-expression mapping serialized as source lines.
    """
    lines: List[str] = list((f"{name} = {{",))
    if comments is not None:
        comment: str
        for comment in comments:
            lines.append(f"    # {comment}")
    else:
        pass
    variable: Var
    expression: Expr
    for variable, expression in expressions.items():
        lines.append(f"    {variable.name}: {serialize_dae_expression(expression)},")
    lines.append("}")
    return lines


def parse_equation_code(code: str, namespace: Mapping[str, Expr]) -> BlockEquationDraft:
    """
    Parse the supported assignment-only DAE language without executing code.

    :param code: Value supplied for ``code``.
    :param namespace: Value supplied for ``namespace``.
    :return: Detached equation draft parsed without executing the supplied code.
    """
    normalized_code: str = normalize_algebraic_equality_syntax(code)
    try:
        module: ast.Module = ast.parse(normalized_code, mode="exec")
    except SyntaxError as error:
        raise ValueError(str(error)) from error

    parsed_lists: Dict[str, List[Expr]] = dict()
    parsed_dicts: Dict[str, Dict[Var, Expr]] = dict()
    parsed_variable_lists: Dict[str, List[Var]] = dict()
    statement: ast.stmt
    for statement in module.body:
        _parse_equation_statement(
            statement=statement,
            namespace=namespace,
            parsed_lists=parsed_lists,
            parsed_dicts=parsed_dicts,
            parsed_variable_lists=parsed_variable_lists,
        )

    required_lists: tuple[str, ...] = ("algebraic_eqs",)
    required_dicts: tuple[str, ...] = ("state_eqs", "init_eqs", "diff_init_eqs")
    required_variable_lists: tuple[str, ...] = ("state_vars",)
    _validate_required_sections(required_lists, parsed_lists)
    _validate_required_sections(required_dicts, parsed_dicts)
    _validate_required_sections(required_variable_lists, parsed_variable_lists)

    # The GUI mapping is converted back to the Engine's positional list only
    # after proving that every declared state owns exactly one right-hand side.
    state_variables: List[Var] = parsed_variable_lists["state_vars"]
    state_equation_mapping: Dict[Var, Expr] = parsed_dicts["state_eqs"]
    missing_state_names: List[str] = list()
    state_variable: Var
    for state_variable in state_variables:
        if state_variable not in state_equation_mapping:
            missing_state_names.append(state_variable.name)
        else:
            pass
    unexpected_state_names: List[str] = list()
    mapped_state: Var
    for mapped_state in state_equation_mapping:
        if mapped_state not in state_variables:
            unexpected_state_names.append(mapped_state.name)
        else:
            pass
    if len(missing_state_names) > 0 or len(unexpected_state_names) > 0:
        raise ValueError(
            "Section 'state_eqs' must map every state_vars entry exactly once; "
            f"missing={missing_state_names}, unexpected={unexpected_state_names}"
        )
    else:
        ordered_state_equations: List[Expr] = list()
        for state_variable in state_variables:
            ordered_state_equations.append(state_equation_mapping[state_variable])
    return BlockEquationDraft(
        ordered_state_equations,
        parsed_lists["algebraic_eqs"],
        parsed_dicts["init_eqs"],
        parsed_dicts["diff_init_eqs"],
        parsed_variable_lists,
    )


def _parse_equation_statement(statement: ast.stmt,
                              namespace: Mapping[str, Expr],
                              parsed_lists: Dict[str, List[Expr]],
                              parsed_dicts: Dict[str, Dict[Var, Expr]],
                              parsed_variable_lists: Dict[str, List[Var]]) -> None:
    """
    Parse one assignment statement from the DAE editor.

    :param statement: Value supplied for ``statement``.
    :param namespace: Value supplied for ``namespace``.
    :param parsed_lists: Value supplied for ``parsed_lists``.
    :param parsed_dicts: Value supplied for ``parsed_dicts``.
    :param parsed_variable_lists: Parsed informative variable-order sections.
    :return: None.
    """
    if not isinstance(statement, ast.Assign):
        raise ValueError("Only assignments to supported DAE sections are allowed")
    elif len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
        raise ValueError("Each DAE section must use one simple assignment")
    else:
        section_name: str = statement.targets[0].id

    if (section_name in parsed_lists
            or section_name in parsed_dicts
            or section_name in parsed_variable_lists):
        raise ValueError(f"Section '{section_name}' is assigned more than once")
    elif section_name == "algebraic_eqs":
        parsed_lists[section_name] = _parse_algebraic_equation_list(
            statement.value,
            namespace,
        )
    elif section_name in ("state_eqs", "init_eqs", "diff_init_eqs"):
        parsed_dicts[section_name] = _parse_expression_dict(statement.value, namespace, section_name)
    elif section_name in ("state_vars", "algebraic_vars", "diff_vars"):
        parsed_variable_lists[section_name] = _parse_variable_list(
            node=statement.value,
            namespace=namespace,
            section_name=section_name,
        )
    elif section_name in ("retained_modes", "procedural_logic"):
        # Runtime sections are parsed by the typed procedural-language layer
        # after all owners have contributed their retained-mode namespace.
        pass
    else:
        raise ValueError(f"Unsupported DAE section '{section_name}'")


def _parse_variable_list(node: ast.expr,
                         namespace: Mapping[str, Expr],
                         section_name: str) -> List[Var]:
    """Parse one informative ordered variable declaration.

    These declarations expose the block's current DAE ordering but do not create,
    delete, or reclassify symbols. Structural symbol edits remain owned by the
    Variables and Parameters tables.

    :param node: Assignment value expected to be a list or tuple.
    :param namespace: Allowed symbolic identities by name.
    :param section_name: Declaration section being parsed.
    :return: Ordered existing variables referenced by the declaration.
    """
    if not isinstance(node, (ast.List, ast.Tuple)):
        raise ValueError(f"Section '{section_name}' must be a list")
    else:
        result: List[Var] = list()

    element: ast.expr
    for element in node.elts:
        if not isinstance(element, ast.Name):
            raise ValueError(f"Entries in '{section_name}' must be variable names")
        else:
            symbol: Expr | None = namespace.get(element.id, None)
        if not isinstance(symbol, Var):
            raise ValueError(f"Unknown variable '{element.id}' in '{section_name}'")
        elif symbol in result:
            raise ValueError(f"Variable '{element.id}' is repeated in '{section_name}'")
        else:
            result.append(symbol)
    return result


def _parse_algebraic_equation_list(node: ast.expr,
                                   namespace: Mapping[str, Expr]) -> List[Expr]:
    """Parse complete GUI equalities into Engine algebraic residuals.

    The normalization layer represents the visible equality with a root
    bitwise-or AST node. Exactly one such marker is required per list entry.
    ``right - left`` follows the GUI convention ``0 = residual``; an explicit
    zero on either side is simplified so opening and applying an unchanged
    block preserves its existing symbolic expression.

    :param node: Assignment value expected to be a list.
    :param namespace: Allowed symbolic identities by name.
    :return: Ordered algebraic residual expressions for the Engine.
    """
    if not isinstance(node, ast.List):
        raise ValueError("Section 'algebraic_eqs' must be a list")
    else:
        result: List[Expr] = list()
        element: ast.expr
        for element in node.elts:
            equality_marker_count: int = 0
            child_node: ast.AST
            for child_node in ast.walk(element):
                if isinstance(child_node, ast.BinOp) and isinstance(child_node.op, ast.BitOr):
                    equality_marker_count += 1
                else:
                    pass

            if not isinstance(element, ast.BinOp):
                raise ValueError(
                    "Every entry in 'algebraic_eqs' must contain exactly one '=' "
                    "between two complete symbolic expressions"
                )
            elif not isinstance(element.op, ast.BitOr) or equality_marker_count != 1:
                raise ValueError(
                    "Every entry in 'algebraic_eqs' must contain exactly one '=' "
                    "between two complete symbolic expressions"
                )
            else:
                left_expression: Expr | Comparison = _parse_symbolic_ast_node(
                    element.left,
                    namespace,
                )
                right_expression: Expr | Comparison = _parse_symbolic_ast_node(
                    element.right,
                    namespace,
                )

            if not isinstance(left_expression, Expr) or not isinstance(right_expression, Expr):
                raise ValueError("Algebraic equality sides must be symbolic expressions")
            elif isinstance(left_expression, Const) and left_expression.value == 0:
                residual_expression: Expr = right_expression
            elif isinstance(right_expression, Const) and right_expression.value == 0:
                residual_expression = left_expression
            else:
                residual_expression = right_expression - left_expression
            result.append(residual_expression)
        return result


def _parse_expression_dict(node: ast.expr,
                           namespace: Mapping[str, Expr],
                           section_name: str) -> Dict[Var, Expr]:
    """
    Parse a variable-to-expression mapping with identity-preserving keys.

    :param node: Value supplied for ``node``.
    :param namespace: Value supplied for ``namespace``.
    :param section_name: Value supplied for ``section_name``.
    :return: Parsed variable-to-expression mapping with identity-preserving keys.
    """
    if not isinstance(node, ast.Dict):
        raise ValueError(f"Section '{section_name}' must be a dictionary")
    else:
        result: Dict[Var, Expr] = dict()

    index: int
    for index in range(len(node.keys)):
        key_node: ast.expr | None = node.keys[index]
        value_node: ast.expr = node.values[index]
        if not isinstance(key_node, ast.Name):
            raise ValueError(f"Keys in '{section_name}' must be variable names")
        else:
            key_symbol: Expr | None = namespace.get(key_node.id, None)
        if not isinstance(key_symbol, Var):
            raise ValueError(f"Unknown variable '{key_node.id}' in '{section_name}'")
        elif key_symbol in result:
            raise ValueError(f"Variable '{key_node.id}' is repeated in '{section_name}'")
        else:
            expression: Expr | Comparison = _parse_symbolic_ast_node(value_node, namespace)
        if isinstance(expression, Comparison):
            raise ValueError(f"Comparisons are not supported in '{section_name}'")
        else:
            result[key_symbol] = expression
    return result


def _parse_symbolic_ast_node(node: ast.expr, namespace: Mapping[str, Expr]) -> Expr | Comparison:
    """Convert one safe AST expression while preserving symbolic identities.

    The Engine parser deliberately accepts unary functions only. Dynamic
    templates also contain binary symbolic functions such as ``atan2``. This
    editor-side walker therefore handles the expression structure explicitly
    and delegates unary function-name validation to the Engine parser.

    :param node: Parsed Python expression node.
    :param namespace: Allowed symbolic identities by name.
    :return: Parsed symbolic expression or comparison.
    """
    expression: Expr | Comparison
    if isinstance(node, ast.Constant):
        value: object = node.value
        if isinstance(value, (int, float, complex)):
            expression = Const(value)
        else:
            raise ValueError(f"Unsupported constant {value!r}")
    elif isinstance(node, ast.Name):
        symbol: Expr | None = namespace.get(node.id, None)
        if isinstance(symbol, Expr):
            expression = symbol
        else:
            raise ValueError(f"Unknown symbol '{node.id}'")
    elif isinstance(node, ast.BinOp):
        expression = _parse_symbolic_binary_operation(node, namespace)
    elif isinstance(node, ast.UnaryOp):
        expression = _parse_symbolic_unary_operation(node, namespace)
    elif isinstance(node, ast.Call):
        expression = _parse_symbolic_function_call(node, namespace)
    elif isinstance(node, ast.Compare):
        expression = _parse_symbolic_comparison(node, namespace)
    else:
        raise ValueError(f"Unsupported expression node {node.__class__.__name__}")
    return expression


def _parse_symbolic_binary_operation(node: ast.BinOp,
                                     namespace: Mapping[str, Expr]) -> Expr:
    """Parse one supported arithmetic binary operation.

    :param node: Binary-operation AST node.
    :param namespace: Allowed symbolic identities by name.
    :return: Symbolic binary expression.
    """
    left: Expr | Comparison = _parse_symbolic_ast_node(node.left, namespace)
    right: Expr | Comparison = _parse_symbolic_ast_node(node.right, namespace)
    if not isinstance(left, Expr) or not isinstance(right, Expr):
        raise ValueError("Arithmetic operations require symbolic operands")
    else:
        pass

    operator_text: str
    if isinstance(node.op, ast.Add):
        operator_text = "+"
    elif isinstance(node.op, ast.Sub):
        operator_text = "-"
    elif isinstance(node.op, ast.Mult):
        operator_text = "*"
    elif isinstance(node.op, ast.Div):
        operator_text = "/"
    elif isinstance(node.op, ast.Pow):
        operator_text = "**"
    else:
        raise ValueError(f"Unsupported binary operator {node.op.__class__.__name__}")
    return BinOp(left, operator_text, right)


def _parse_symbolic_unary_operation(node: ast.UnaryOp,
                                    namespace: Mapping[str, Expr]) -> Expr:
    """Parse unary plus or minus.

    :param node: Unary-operation AST node.
    :param namespace: Allowed symbolic identities by name.
    :return: Symbolic operand or negation.
    """
    operand: Expr | Comparison = _parse_symbolic_ast_node(node.operand, namespace)
    if not isinstance(operand, Expr):
        raise ValueError("Unary operations require a symbolic operand")
    elif isinstance(node.op, ast.UAdd):
        return operand
    elif isinstance(node.op, ast.USub):
        return UnOp("-", operand)
    else:
        raise ValueError(f"Unsupported unary operator {node.op.__class__.__name__}")


def _parse_symbolic_function_call(node: ast.Call,
                                  namespace: Mapping[str, Expr]) -> Expr:
    """Parse a supported named unary or binary symbolic function.

    :param node: Function-call AST node.
    :param namespace: Allowed symbolic identities by name.
    :return: Symbolic function expression.
    """
    if not isinstance(node.func, ast.Name):
        raise ValueError("Only named symbolic functions are supported")
    elif len(node.keywords) > 0:
        raise ValueError("Keyword arguments are not supported in symbolic functions")
    else:
        function_name: str = node.func.id
    function_arity: int | None = get_symbolic_parser_function_arity(function_name)
    if function_arity is None:
        raise ValueError(f"Unsupported symbolic function '{function_name}'")
    elif len(node.args) != function_arity:
        raise ValueError(f"Unsupported arguments for symbolic function '{function_name}'")
    else:
        pass

    # Parse every argument through the DAE walker first so aliases retain their
    # exact staged Expr identities. The Engine parser then owns the canonical
    # function-name and arity validation for both unary and binary calls.
    temporary_namespace: Dict[str, Expr] = dict(namespace)
    temporary_names: List[str] = list()
    argument_index: int
    for argument_index in range(len(node.args)):
        argument: Expr | Comparison = _parse_symbolic_ast_node(
            node.args[argument_index],
            namespace,
        )
        if not isinstance(argument, Expr):
            raise ValueError("Symbolic functions require expression arguments")
        else:
            temporary_name: str = f"__dae_function_argument_{argument_index}"
            temporary_namespace[temporary_name] = argument
            temporary_names.append(temporary_name)
    argument_source: str = ", ".join(temporary_names)
    parsed: Expr | Comparison = string_to_symbolic(
        f"{function_name}({argument_source})",
        temporary_namespace,
    )
    if isinstance(parsed, Expr):
        return parsed
    else:
        raise ValueError("A symbolic function cannot return a comparison")


def _parse_symbolic_comparison(node: ast.Compare,
                               namespace: Mapping[str, Expr]) -> Comparison:
    """Parse one non-chained comparison.

    :param node: Comparison AST node.
    :param namespace: Allowed symbolic identities by name.
    :return: Symbolic comparison.
    """
    if len(node.ops) != 1 or len(node.comparators) != 1:
        raise ValueError("Only simple two-sided comparisons are supported")
    else:
        left: Expr | Comparison = _parse_symbolic_ast_node(node.left, namespace)
        right: Expr | Comparison = _parse_symbolic_ast_node(node.comparators[0], namespace)
    if not isinstance(left, Expr) or not isinstance(right, Expr):
        raise ValueError("Comparisons require symbolic operands")
    elif isinstance(node.ops[0], ast.Lt):
        return left < right
    elif isinstance(node.ops[0], ast.LtE):
        return left <= right
    elif isinstance(node.ops[0], ast.Gt):
        return left > right
    elif isinstance(node.ops[0], ast.GtE):
        return left >= right
    elif isinstance(node.ops[0], ast.Eq):
        return left == right
    else:
        raise ValueError(f"Unsupported comparison operator {node.ops[0].__class__.__name__}")


def _validate_required_sections(required: Sequence[str], parsed: Mapping[str, object]) -> None:
    """
    Require each supported section exactly once.

    :param required: Value supplied for ``required``.
    :param parsed: Value supplied for ``parsed``.
    :return: None.
    """
    section_name: str
    for section_name in required:
        if section_name not in parsed:
            raise ValueError(f"Missing required DAE section '{section_name}'")
        else:
            pass


def block_has_advanced_logic(block: Block) -> bool:
    """
    :param block: Symbolic block used by the operation.
    :return: Whether unsupported advanced symbolic fields are present.
    """
    result: bool = False
    child: Block
    for child in block.get_all_blocks():
        if (
            child.inequalities
            or child.discrete_eqs
            or child.boolean_guards
            or child.reformulated_vars
        ):
            result = True
        else:
            pass
    return result


def resolve_block_documentation_url(
        block_type_name: str,
        block_name: str,
        block: Block | None = None,
) -> str | None:
    """Resolve the online catalogue documentation URL for one library block.

    The returned page describes the original predefined block. A working copy
    edited in the Dynamic Model Editor can intentionally differ from it.

    :param block_type_name: Persisted diagram node type.
    :param block_name: Symbolic template or block name used to refine the lookup.
    :param block: Optional symbolic block used to identify one procedural primitive.
    :return: ReadTheDocs URL or ``None`` for a genuinely custom block.
    """
    # A native procedural template carries its semantic identity in the Engine
    # entry itself. This remains valid after the user renames the canvas block
    # and avoids encoding GUI-only suffixes in symbolic names.
    normalized_block_type: str = block_type_name.upper()
    relative_path: str | None
    if (
            normalized_block_type == BlockType.PROCEDURAL_LOGIC.name
            and block is not None
            and len(block.procedural_logic) > 0
    ):
        procedural_entry: object = block.procedural_logic[0]
        if isinstance(procedural_entry, ProceduralLogicBase):
            relative_path = None
            procedural_descriptor: ProceduralBlockTemplateDescriptor
            for procedural_descriptor in get_dynamic_library_procedural_descriptors():
                if procedural_descriptor.logic_tpe == procedural_entry.logic_tpe:
                    relative_path = procedural_descriptor.documentation_relative_path
                    break
                else:
                    pass
        else:
            relative_path = _get_documentation_relative_path(block_type_name, block_name)
    else:
        # Reuse the single catalogue mapping and only translate its Sphinx
        # source path into the HTML path published by ReadTheDocs.
        relative_path = _get_documentation_relative_path(block_type_name, block_name)
    if relative_path is None:
        result: str | None = None
    else:
        normalized_path: str = relative_path.replace("\\", "/")
        if normalized_path.endswith(".md"):
            html_path: str = normalized_path[:-3] + ".html"
        else:
            html_path = normalized_path + ".html"
        result = f"https://veragrid.readthedocs.io/en/latest/md_source/dyn_templates/{html_path}"
    return result


def _get_documentation_relative_path(block_type_name: str, block_name: str) -> str | None:
    """Return an explicit documentation mapping for supported catalogue types.

    :param block_type_name: Persisted diagram node type.
    :param block_name: Symbolic template or block name.
    :return: Documentation path relative to ``dyn_templates`` or ``None``.
    """
    normalized: str = block_type_name.upper()
    normalized_block_name: str = re.sub(r"[^A-Z0-9]+", "_", block_name.upper()).strip("_")
    catalogue_type_match: re.Match[str] | None = re.search(r"__(\d+)$", block_name)
    if normalized == "TEMPLATE" and catalogue_type_match is not None:
        # Every generated Basic Block Catalog page is keyed by the immutable
        # imported type id. Display names are not unique and can contain
        # punctuation, while the ``__<typ_id>`` suffix survives serialization.
        return f"library/catalog/typ_{catalogue_type_match.group(1)}.md"
    else:
        pass
    # Use persisted native types, not editable display names, for the RMS
    # components, using the same RMS documentation section as other devices.
    rms_pages: Dict[BlockType, str] = dict((
        (BlockType.GFL_VSC_HVDC_RMS, "hvdc_vsc_gfl.md"),
        (BlockType.VSC_PLL_RMS, "vsc_pll.md"),
        (BlockType.VSC_ELECTRICAL_RMS, "vsc_electrical.md"),
        (BlockType.VSC_ACTIVE_CONTROL_RMS, "vsc_active_control.md"),
        (BlockType.VSC_REACTIVE_CONTROL_RMS, "vsc_reactive_control.md"),
        (BlockType.VSC_CURRENT_LIMITER_RMS, "vsc_current_limiter.md"),
        (BlockType.VSC_VD_HAT_RMS, "vsc_vd_hat.md"),
        (BlockType.VSC_VQ_HAT_RMS, "vsc_vq_hat.md"),
        (BlockType.VSC_DC_LINK_RMS, "vsc_dc_link.md"),
        (BlockType.DC_LINE_RMS, "dc_line.md"),
        (BlockType.VOLTAGE_SOURCE_RMS, "voltage_source.md"),
    ))
    native_type: BlockType | None = BlockType.__members__.get(normalized, None)
    rms_page: str | None = rms_pages.get(native_type, None) if native_type is not None else None
    if rms_page is not None:
        return "RMS/" + rms_page
    else:
        pass
    mapping: Dict[str, str] = dict((("GENERIC", "library/generic.md"), ("CONST", "library/constant.md"), ("GAIN", "library/gain.md"), ("ABS", "library/absolute_value.md"), ("SUM", "library/sum.md"), ("PRODUCT", "library/product.md"), ("FROM_GOTO", "library/from_goto.md"), ("LINE_RMS", "RMS/line.md"), ("LOAD_RMS", "RMS/load.md"), ("GENRAW", "RMS/genrou_genrow.md"), ("GENQEC", "RMS/genqec.md"), ("GOV_RMS", "RMS/governor.md"), ("STAB_RMS", "RMS/stabilizer.md"), ("EXCITER_RMS", "RMS/exciter.md"), ("EMT_GENERATOR", "EMT/sauer_pai_generator.md"), ("GOV_EMT", "EMT/governor.md"), ("STAB_EMT", "EMT/stabilizer.md"), ("EXCITER_EMT", "EMT/exciter.md"), ("EMT_PI_LINE", "EMT/pi_line_abc.md"), ("EMT_BERGERON_LINE", "EMT/bergeron_line_abc.md"), ("EMT_JMARTI_LINE", "EMT/jmarti_line.md"), ("EMT_DC_LINE", "EMT/dc_line.md"), ("EXP_LOAD_EMT", "library/exp_load_emt.md"), ("ZIP_LOAD_EMT", "EMT/zip_load_abc.md"), ("DC_LOAD_EMT", "EMT/dc_load.md"), ("EMT_THEVENIN", "EMT/thevenin_generator.md"), ("TRAFO_EMT", "library/trafo_emt.md"), ("XFMR_TRANSFORMER", "library/xfmr_transformer.md"), ("INDUCTION_MOTOR_EMT", "EMT/single_cage_induction_motor.md"), ("PV_POWER_PLANT_EMT", "EMT/pv_plant_grid_following.md"), ("PV_EMT", "EMT/pv_plant_grid_following.md"), ("COMPLETE_PSEUDO_VSC_EMT", "EMT/full_pseudo_converter.md"), ("GFL_CONVERTER_RMS", "RMS/converter.md"), ("BESS_EMT", "EMT/bess.md"), ("BATTERY_EMT", "library/battery_emt.md"), ("VOLTAGE_SOURCE_EMT", "library/voltage_source_emt.md"), ("CURRENT_SOURCE_EMT", "library/current_source_emt.md"), ("CONTROLLED_VOLTAGE_SOURCE_EMT", "library/controlled_voltage_source_emt.md"), ("CONTROLLED_CURRENT_SOURCE_EMT", "library/controlled_current_source_emt.md"), ("ARBITRARY_WAVEFORM_VOLTAGE_SOURCE_EMT", "library/arbitrary_waveform_voltage_source_emt.md"), ("ARBITRARY_WAVEFORM_CURRENT_SOURCE_EMT", "library/arbitrary_waveform_current_source_emt.md"), ("BALANCED_3PH_VOLTAGE_SOURCE_EMT", "library/balanced_3ph_voltage_source_emt.md"), ("BALANCED_3PH_CURRENT_SOURCE_EMT", "library/balanced_3ph_current_source_emt.md"), ("CONTROLLED_BALANCED_3PH_VOLTAGE_SOURCE_EMT", "library/controlled_balanced_3ph_voltage_source_emt.md"), ("CONTROLLED_BALANCED_3PH_CURRENT_SOURCE_EMT", "library/controlled_balanced_3ph_current_source_emt.md"), ("DC_VOLTAGE_SOURCE_EMT", "library/dc_voltage_source_emt.md"), ("DC_CURRENT_SOURCE_EMT", "library/dc_current_source_emt.md"), ("CONTROLLED_DC_VOLTAGE_SOURCE_EMT", "library/controlled_dc_voltage_source_emt.md"), ("CONTROLLED_DC_CURRENT_SOURCE_EMT", "library/controlled_dc_current_source_emt.md"), ("STEP_VOLTAGE_SOURCE_EMT", "library/step_voltage_source_emt.md"), ("STEP_CURRENT_SOURCE_EMT", "library/step_current_source_emt.md"), ("RAMP_VOLTAGE_SOURCE_EMT", "library/ramp_voltage_source_emt.md"), ("RAMP_CURRENT_SOURCE_EMT", "library/ramp_current_source_emt.md"), ("DOUBLE_EXPONENTIAL_CURRENT_SOURCE_EMT", "library/double_exponential_current_source_emt.md"), ("HEIDLER_CURRENT_SOURCE_EMT", "library/heidler_current_source_emt.md"), ("CIGRE_SURGE_CURRENT_SOURCE_EMT", "library/cigre_surge_current_source_emt.md"), ("R_LOAD_EMT", "library/r_load_emt.md"), ("L_LOAD_EMT", "library/l_load_emt.md"), ("C_LOAD_EMT", "library/c_load_emt.md"), ("RLC_COMBO_EMT", "library/rlc_combo_emt.md"), ("GROUND_EMT", "library/ground_emt.md"), ("GROUNDING_LINK_EMT", "library/grounding_link_emt.md"), ("SWITCH_EMT", "library/switch_emt.md"), ("FAULT_EMT", "EMT/fault.md"), ("NONLINEAR_RESISTOR_EMT", "library/nonlinear_resistor_emt.md"), ("INVERSE_LOOKUP_ARRAY", "library/inverse-lookup-array-object-linear.md"), ("LOOKUP_ARRAY_LINEAR", "library/lookup_array.md"), ("LOOKUP_ARRAY_SPLINE", "library/lookup_array.md"), ("LOOKUP_MATRIX_LINEAR", "library/lookup_matrix.md"), ("LOOKUP_MATRIX_SPLINE", "library/lookup_matrix.md"), ("PI_CURRENT_CONTROLLER", "library/pi_current_controller.md"), ("PI_POWER_CONTROLLER", "library/pi_power_controller.md"), ("PLL_TRANSFORM_RMS", "library/pll_transformer.md"),))
    relative_path: str | None = mapping.get(normalized, None)
    if relative_path is not None:
        return relative_path
    elif normalized_block_name.startswith("COMPLETE_GENERATOR_RMS_TEMPLATE") or \
            normalized_block_name.startswith("COMPLETE_GENERATOR_PHASOR_RMS_TEMPLATE") or \
            normalized_block_name.startswith("COMPLETE_GENERATOR_RMS"):
        return "RMS/complete_generator.md"
    elif normalized_block_name.startswith("COMPLETE_GENERATOR_EMT_TEMPLATE") or \
            normalized_block_name.startswith("COMPLETE_GENERATOR_EMT"):
        return "EMT/complete_generator.md"
    elif normalized_block_name.startswith("GENROW_RMS_TEMPLATE") or \
            normalized_block_name.startswith("GENROU_RMS_TEMPLATE") or \
            normalized_block_name.startswith("GENROU_GENROW"):
        return "RMS/genrou_genrow.md"
    elif normalized_block_name.startswith("LINE_RMS_TEMPLATE"):
        return "RMS/line.md"
    elif normalized_block_name.startswith("LOAD_RMS_TEMPLATE"):
        return "RMS/load.md"
    elif normalized_block_name.startswith("VOLTAGE_SOURCE_RMS"):
        return "RMS/voltage_source.md"
    elif normalized_block_name.startswith("DISTRIBUTED_PV") or \
            normalized_block_name.startswith("PVD1"):
        return "RMS/distributed_pv.md"
    elif normalized_block_name.startswith("ESD1") or \
            normalized_block_name.startswith("BATTERY_RMS"):
        return "RMS/battery.md"
    elif normalized_block_name.startswith("TRANSFORMER2W_RMS") or \
            normalized_block_name.startswith("2W_TRANSFORMER") or \
            normalized_block_name.startswith("RMS_TRAFO_TEMPLATE"):
        return "RMS/2w_transformer.md"
    elif normalized_block_name.startswith("GFM_VSC") or \
            normalized_block_name.startswith("VSC_RMS_TEMPLATE"):
        return "RMS/gfm_vsc.md"
    elif normalized_block_name.startswith("THEVENIN") or \
            normalized_block_name.startswith("EMT_THEVENIN"):
        return "EMT/thevenin_generator.md"
    elif normalized_block_name.startswith("IDEAL_CONVERTER"):
        return "EMT/ideal_converter.md"
    elif normalized_block_name.startswith("FULL_PSEUDO") or \
            normalized_block_name.startswith("PSEUDO_CONVERTER"):
        return "EMT/full_pseudo_converter.md"
    elif normalized_block_name.startswith("SWITCHED_CONVERTER"):
        return "EMT/switched_converter.md"
    elif normalized_block_name.startswith("DC_LOAD"):
        return "EMT/dc_load.md"
    elif normalized_block_name.startswith("DC_LINE"):
        return "EMT/dc_line.md"
    elif normalized_block_name.startswith("TRANSFORMER_EMT_TEMPLATE"):
        return "EMT/transformer.md"
    elif normalized_block_name.startswith("XFMR_EMT_TEMPLATE"):
        return "EMT/xfmr.md"
    elif normalized_block_name.startswith("SHUNT_C") or \
            normalized_block_name.startswith("C_SHUNT"):
        return "EMT/shunt_c_abc.md"
    elif normalized_block_name.startswith("SHUNT_L") or \
            normalized_block_name.startswith("L_SHUNT"):
        return "EMT/shunt_l_abc.md"
    elif normalized_block_name.startswith("SHUNT_R") or \
            normalized_block_name.startswith("R_SHUNT"):
        return "EMT/shunt_r_abc.md"
    elif normalized_block_name.startswith("EXPONENTIAL_LOAD") or \
            normalized_block_name.startswith("EXP_LOAD_EMT"):
        return "EMT/exponential_load_abc.md"
    elif normalized_block_name.startswith("ZIP_LOAD"):
        return "EMT/zip_load_abc.md"
    elif normalized_block_name.startswith("PI_LINE") or normalized_block_name == "PI":
        return "EMT/pi_line_abc.md"
    elif normalized_block_name.startswith("BERGERON_LINE") or normalized_block_name == "BERGERON":
        return "EMT/bergeron_line_abc.md"
    elif normalized_block_name.startswith("SINGLE_CAGE_INDUCTION_MOTOR") or \
            normalized_block_name.startswith("INDUCTION_MOTOR_EMT_TEMPLATE"):
        return "EMT/single_cage_induction_motor.md"
    elif normalized_block_name.startswith("DOUBLE_CAGE_INDUCTION_MOTOR"):
        return "EMT/double_cage_induction_motor.md"
    elif normalized_block_name.startswith("INDUCTION_MOTOR_DOUBLE_CAGE"):
        return "EMT/double_cage_induction_motor.md"
    elif normalized_block_name.startswith("BESS"):
        return "EMT/bess.md"
    elif normalized_block_name.startswith("PV_PLANT") or \
            normalized_block_name.startswith("PV_AVM_GRID_FOLLOWING"):
        return "EMT/pv_plant_grid_following.md"
    elif normalized_block_name.startswith("VSC_GRID_FORMING") or \
            normalized_block_name.startswith("VSC_GRIDFORMING") or \
            normalized_block_name.startswith("GFM_EMT"):
        return "EMT/vsc_grid_forming_gfm.md"
    elif normalized_block_name.startswith("PLL_TRANSFORM_RMS") or \
            normalized_block_name.startswith("PHASE_LOCKED_LOOP"):
        return "library/pll_transformer.md"
    else:
        return None


class RetainedModeDraftTableModel(QtCore.QAbstractTableModel):
    """Qt projection of retained modes owned by the runtime draft collection."""

    modeNameChanged = Signal(object, str, str)
    __slots__ = ("_collection", "_rows")

    def __init__(self,
                 collection: RuntimeLogicDraftCollection,
                 parent: QtCore.QObject | None = None) -> None:
        """Create an editable projection without duplicating runtime semantics.

        :param collection: Detached runtime draft collection used by Validate and Apply.
        :param parent: Owning Qt object.
        :return: None.
        """
        super().__init__(parent)
        self._collection: RuntimeLogicDraftCollection = collection
        self._rows: List[RuntimeModeDraft] = collection.get_active_modes()

    def reload(self, collection: RuntimeLogicDraftCollection) -> None:
        """Rebind rows after source parsing or a successful Apply.

        :param collection: Replacement runtime draft collection.
        :return: None.
        """
        self.beginResetModel()
        self._collection = collection
        self._rows = collection.get_active_modes()
        self.endResetModel()

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """Return the number of visible retained modes.

        :param parent: Qt parent index; retained modes form a flat source model.
        :return: Number of active mode drafts.
        """
        if parent.isValid():
            result: int = 0
        else:
            result = len(self._rows)
        return result

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """Return Name, Type, empty value, and Output columns.

        :param parent: Qt parent index; retained modes form a flat source model.
        :return: Four columns matching the property tree.
        """
        if parent.isValid():
            result: int = 0
        else:
            result = 4
        return result

    def get_row(self, row_index: int) -> RuntimeModeDraft | None:
        """Return one retained-mode draft by source row.

        :param row_index: Flat source-model row.
        :return: Mode draft or ``None`` outside the model.
        """
        if 0 <= row_index < len(self._rows):
            result: RuntimeModeDraft | None = self._rows[row_index]
        else:
            result = None
        return result

    def data(self,
             index: QtCore.QModelIndex,
             role: int = Qt.ItemDataRole.DisplayRole) -> object:
        """Return retained-mode structure without exposing initialization values.

        :param index: Requested source index.
        :param role: Qt display or edit role.
        :return: Requested mode value or ``None`` for unsupported roles.
        """
        row: RuntimeModeDraft | None = self.get_row(index.row())
        if row is None or role not in (
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.EditRole,
                Qt.ItemDataRole.ToolTipRole):
            result: object = None
        elif index.column() == 0:
            result = row.get_name()
        elif index.column() == 1:
            result = self.tr("Retained mode")
        else:
            result = None
        return result

    def flags(self, index: QtCore.QModelIndex) -> Qt.ItemFlag:
        """Allow inline mode renaming while keeping Python code authoritative.

        :param index: Requested source index.
        :return: Qt item flags for the represented cell.
        """
        if not index.isValid():
            result: Qt.ItemFlag = Qt.ItemFlag.NoItemFlags
        else:
            result = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            if index.column() == 0:
                result |= Qt.ItemFlag.ItemIsEditable
            else:
                pass
        return result

    def setData(self,
                index: QtCore.QModelIndex,
                value: object,
                role: int = Qt.ItemDataRole.EditRole) -> bool:
        """Stage a mode name without exposing a second initialization editor.

        :param index: Edited source index.
        :param value: New inline text.
        :param role: Qt edit role.
        :return: Whether the draft accepted the structural edit.
        """
        row: RuntimeModeDraft | None = self.get_row(index.row())
        if row is None or role != Qt.ItemDataRole.EditRole:
            accepted: bool = False
        elif index.column() == 0:
            name: str = str(value).strip()
            if len(name) > 0 and name.isidentifier() and not keyword.iskeyword(name):
                old_name: str = row.get_name()
                row.set_name(name)
                if old_name != name:
                    self.modeNameChanged.emit(row.get_owner(), old_name, name)
                else:
                    pass
                accepted = True
            else:
                accepted = False
        else:
            accepted = False
        if accepted:
            self.dataChanged.emit(
                index,
                index,
                list((Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole,)),
            )
        else:
            pass
        return accepted

    def remove_mode(self, row_index: int) -> tuple[bool, str]:
        """Stage deletion through the runtime collection's dependency rules.

        :param row_index: Visible source row selected in the property tree.
        :return: Success flag and an optional blocking message.
        """
        selected_mode: RuntimeModeDraft | None = self.get_row(row_index)
        if selected_mode is None:
            return False, self.tr("Select one retained mode.")
        else:
            collection_modes: List[RuntimeModeDraft] = self._collection.get_modes()
        collection_index: int = -1
        candidate_index: int
        candidate_mode: RuntimeModeDraft
        for candidate_index, candidate_mode in enumerate(collection_modes):
            if candidate_mode is selected_mode:
                collection_index = candidate_index
            else:
                pass
        removed: bool
        message: str
        removed, message = self._collection.remove_mode(collection_index)
        if removed:
            self.reload(self._collection)
        else:
            pass
        return removed, message


def build_block_property_header_row(
        label_item: QtGui.QStandardItem,
) -> List[QtGui.QStandardItem]:
    """Build a complete non-editable structural row for the property tree.

    Every header row needs one real item per visible column so the native
    alternating-row background and row selection extend across the full table.

    :param label_item: First-column item carrying the category or block label.
    :return: Four-item structural row matching the property-tree schema.
    """
    items: List[QtGui.QStandardItem] = list((
        label_item,
        QtGui.QStandardItem(),
        QtGui.QStandardItem(),
        QtGui.QStandardItem(),
    ))
    item: QtGui.QStandardItem
    for item in items:
        item.setEditable(False)
    return items


class BlockPropertyTreeModel(QtGui.QStandardItemModel):
    """Present structural and symbol drafts in a single owner-grouped tree.

    Leaf items store persistent source indexes, not copies of editable values.
    All reads and writes therefore use the existing validation/apply models.
    """

    aboutToRebuild = Signal()
    rebuilt = Signal()
    pendingNameChanged = Signal(str, str)
    existingNameChangeRequested = Signal(object)
    __slots__ = ("_root_block", "_symbols", "_parameters", "_modes", "_structure")

    def __init__(self, root: Block, symbols: BlockSymbolDraftModel,
                 parameters: BlockParameterDraftModel,
                 modes: RetainedModeDraftTableModel,
                 structure: BlockStructuralSettingsModel,
                 parent: QtCore.QObject | None = None) -> None:
        """Connect the hierarchy to the existing staged models.

        :param root: Block whose recursive owners are displayed.
        :param symbols: Authoritative symbol draft used by Apply.
        :param parameters: Existing dynamic-parameter expression drafts.
        :param modes: Retained-mode projection backed by runtime drafts.
        :param structure: General structural settings, excluding special settings.
        :param parent: Owning Qt object.
        :return: None.
        """
        super().__init__(parent)
        self._root_block: Block = root
        self._symbols: BlockSymbolDraftModel = symbols
        self._parameters: BlockParameterDraftModel = parameters
        self._modes: RetainedModeDraftTableModel = modes
        self._structure: BlockStructuralSettingsModel = structure
        self.setHorizontalHeaderLabels(
            list((
                self.tr("Name"),
                self.tr("Type"),
                self.tr("Value / PF reference"),
                self.tr("Output"),
            ))
        )
        self._symbols.rowsInserted.connect(self.rebuild)
        self._symbols.rowsRemoved.connect(self.rebuild)
        self._symbols.modelReset.connect(self.rebuild)
        self._parameters.modelReset.connect(self.refresh_values)
        self._modes.rowsInserted.connect(self.rebuild)
        self._modes.rowsRemoved.connect(self.rebuild)
        self._modes.modelReset.connect(self.rebuild)
        self._structure.rowsInserted.connect(self.rebuild)
        self._structure.rowsRemoved.connect(self.rebuild)
        self._structure.modelReset.connect(self.rebuild)
        self._symbols.dataChanged.connect(self.refresh_values)
        self._parameters.dataChanged.connect(self.refresh_values)
        self._modes.dataChanged.connect(self.refresh_values)
        self._structure.dataChanged.connect(self.refresh_values)
        self.rebuild()

    def prepare_to_delete(self) -> None:
        """Disconnect source models before this tree model is deleted.

        :return: None.
        """
        # The tree model subscribes to several sibling source models. Break
        # those receiver links explicitly so a later GC pass cannot keep this
        # Python-backed model alive through queued model/view notifications.
        disconnect_qobject_from_receiver(self._symbols, self)
        disconnect_qobject_from_receiver(self._parameters, self)
        disconnect_qobject_from_receiver(self._modes, self)
        disconnect_qobject_from_receiver(self._structure, self)

    def append_source_row(self, parent_item: QtGui.QStandardItem,
                          source_index: QtCore.QModelIndex) -> None:
        """Attach an unpopulated display row referencing an existing draft.

        :param parent_item: Owner or structural group receiving the leaf.
        :param source_index: First-column index in the backing draft model.
        :return: None.
        """
        items: List[QtGui.QStandardItem] = list(QtGui.QStandardItem() for _ in range(4))
        items[0].setData(QtCore.QPersistentModelIndex(source_index), Qt.ItemDataRole.UserRole)
        parent_item.appendRow(items)

    @QtCore.Slot()
    def rebuild(self) -> None:
        """Rebuild owner groups after symbol insertion, removal or rebinding.

        :return: None.
        """
        # Notify the view before replacing the owner hierarchy.
        self.aboutToRebuild.emit()
        # Remove only data rows. QStandardItemModel.clear() also removes its
        # columns, which makes QHeaderView discard the user/configured widths.
        # A narrow default Name section clips every deeply indented leaf and
        # makes valid names appear blank after Apply.
        existing_row_count: int = self.rowCount()
        if existing_row_count > 0:
            self.removeRows(0, existing_row_count)
        else:
            pass
        # Empty categories convey no useful information. The independent Add
        # symbol form remains available, and its source-model insertion signal
        # rebuilds this tree when the first row of a category is staged.
        if self._structure.rowCount() > 0:
            structure_group: QtGui.QStandardItem = QtGui.QStandardItem(
                BlockSymbolCategory.GENERAL.value
            )
            structure_group.setEditable(False)
            structure_group.setData(BlockSymbolCategory.GENERAL, Qt.ItemDataRole.UserRole + 2)
            self.appendRow(build_block_property_header_row(label_item=structure_group))
            row_index: int
            for row_index in range(self._structure.rowCount()):
                self.append_source_row(structure_group, self._structure.index(row_index, 0))
        else:
            pass

        has_parameters: bool = False
        has_variables: bool = False
        symbol_index: int
        for symbol_index in range(self._symbols.rowCount()):
            symbol_row: BlockSymbolDraftRow | None = self._symbols.get_row(symbol_index)
            if symbol_row is None:
                pass
            elif symbol_row.get_kind() in (
                    BlockSymbolKind.PARAMETER,
                    BlockSymbolKind.EVENT_PARAMETER):
                has_parameters = True
            else:
                has_variables = True

        visible_categories: List[BlockSymbolCategory] = list()
        if has_parameters:
            visible_categories.append(BlockSymbolCategory.PARAMETERS)
        else:
            pass
        if has_variables:
            visible_categories.append(BlockSymbolCategory.VARIABLES)
        else:
            pass
        if self._modes.rowCount() > 0:
            visible_categories.append(BlockSymbolCategory.RETAINED_MODES)
        else:
            pass

        # Once a category has data, retain every recursive owner branch so the
        # hierarchy remains aligned with the Equation owner and Add selectors.
        category: BlockSymbolCategory
        for category in visible_categories:
            category_group: QtGui.QStandardItem = QtGui.QStandardItem(category.value)
            category_group.setEditable(False)
            category_group.setData(category, Qt.ItemDataRole.UserRole + 2)
            self.appendRow(build_block_property_header_row(label_item=category_group))
            owner_index: int
            owner: Block
            for owner_index, owner in enumerate(self._root_block.get_all_blocks()):
                owner_item: QtGui.QStandardItem = QtGui.QStandardItem(f"{owner.name} [{owner_index + 1}]")
                owner_item.setEditable(False)
                owner_item.setData(owner, Qt.ItemDataRole.UserRole + 1)
                owner_item.setData(category, Qt.ItemDataRole.UserRole + 2)
                category_group.appendRow(build_block_property_header_row(label_item=owner_item))
                if category == BlockSymbolCategory.RETAINED_MODES:
                    mode_index: int
                    for mode_index in range(self._modes.rowCount()):
                        mode: RuntimeModeDraft | None = self._modes.get_row(mode_index)
                        if mode is not None and mode.get_owner() is owner:
                            self.append_source_row(owner_item, self._modes.index(mode_index, 0))
                        else:
                            pass
                else:
                    for symbol_index in range(self._symbols.rowCount()):
                        row: BlockSymbolDraftRow | None = self._symbols.get_row(symbol_index)
                        if row is None or row.get_owner() is not owner:
                            pass
                        else:
                            is_parameter: bool = row.get_kind() in (
                                BlockSymbolKind.PARAMETER, BlockSymbolKind.EVENT_PARAMETER,
                            )
                            if is_parameter == (category == BlockSymbolCategory.PARAMETERS):
                                self.append_source_row(owner_item, self._symbols.index(symbol_index, 0))
                            else:
                                pass
        self.rebuilt.emit()

    def source_index(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        """Resolve a tree leaf without parsing names or owner labels.

        :param index: Tree cell, possibly a category or owner branch.
        :return: Persistent source row converted to an ordinary model index.
        """
        if not index.isValid():
            return QtCore.QModelIndex()
        else:
            stored: object = super().data(index.siblingAtColumn(0), Qt.ItemDataRole.UserRole)
        if isinstance(stored, QtCore.QPersistentModelIndex) and stored.isValid():
            return QtCore.QModelIndex(stored)
        else:
            return QtCore.QModelIndex()

    def symbol_row(self, index: QtCore.QModelIndex) -> BlockSymbolDraftRow | None:
        """Return a symbol draft for a leaf, excluding structural rows.

        :param index: Tree cell selected or edited by the user.
        :return: Existing draft row, or None for a non-symbol node.
        """
        source: QtCore.QModelIndex = self.source_index(index)
        if source.isValid() and source.model() is self._symbols:
            return self._symbols.get_row(source.row())
        else:
            return None

    def retained_mode_row(self, index: QtCore.QModelIndex) -> RuntimeModeDraft | None:
        """Return a retained-mode draft for one tree leaf.

        :param index: Tree cell selected or edited by the user.
        :return: Runtime mode draft or ``None`` for another row type.
        """
        source: QtCore.QModelIndex = self.source_index(index)
        if source.isValid() and source.model() is self._modes:
            result: RuntimeModeDraft | None = self._modes.get_row(source.row())
        else:
            result = None
        return result

    def data(self, index: QtCore.QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        """Read values directly from the underlying drafts.

        :param index: Requested tree cell.
        :param role: Qt display, edit, tooltip or checkbox role.
        :return: Source data or the category/owner label.
        """
        source: QtCore.QModelIndex = self.source_index(index)
        if not source.isValid() or role >= Qt.ItemDataRole.UserRole:
            return super().data(index, role)
        elif source.model() is self._structure:
            if index.column() in (0, 2):
                return self._structure.data(source.siblingAtColumn(index.column() // 2), role)
            else:
                return None
        elif source.model() is self._modes:
            return self._modes.data(source.siblingAtColumn(index.column()), role)
        else:
            row: BlockSymbolDraftRow | None = self._symbols.get_row(source.row())
        if row is None:
            return None
        elif index.column() != 2:
            source_columns: tuple[int, ...] = (1, 2, 4, 3)
            requested_role: int = Qt.ItemDataRole.DisplayRole if role == Qt.ItemDataRole.ToolTipRole else role
            return self._symbols.data(source.siblingAtColumn(source_columns[index.column()]), requested_role)
        elif row.get_kind() == BlockSymbolKind.EVENT_PARAMETER:
            value_index: QtCore.QModelIndex = self._parameters.find_value_index(row.get_owner(), row.get_variable())
            if value_index.isValid():
                return self._parameters.data(value_index, role)
            elif role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                return row.get_value_text()
            else:
                return None
        elif row.get_kind() == BlockSymbolKind.PARAMETER and row.get_static_reference() is None:
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                return row.get_value_text()
            elif role == Qt.ItemDataRole.ToolTipRole:
                return self.tr(
                    "Fixed local value. Select a device initialization mapping only "
                    "when this value must come from the associated grid device."
                )
            else:
                return None
        elif role == Qt.ItemDataRole.ToolTipRole:
            external_reference: VarPowerFlowReferenceType | None = row.get_external_reference()
            static_reference: ParamPowerFlowReferenceType | None = row.get_static_reference()
            if static_reference is not None and not row.supports_static_reference():
                return self.tr(
                    "Invalid device initialization mapping: the target is not declared "
                    "in this block's parameters or event_dict."
                )
            elif external_reference is not None:
                return self.tr(
                    "Power-flow reference; variable mappings are used for initialization."
                )
            else:
                return None
        elif role == Qt.ItemDataRole.DisplayRole:
            reference: ParamPowerFlowReferenceType | VarPowerFlowReferenceType | None = (
                row.get_static_reference()
            )
            if reference is None:
                reference = row.get_external_reference()
            else:
                pass
            if reference is not None:
                return reference.name
            else:
                return ""
        else:
            return self._symbols.data(source.siblingAtColumn(4), role)

    def flags(self, index: QtCore.QModelIndex) -> Qt.ItemFlag:
        """Expose only the edits supported by each backing draft.

        :param index: Tree cell queried by the view.
        :return: Selection, editing and output-checkbox permissions.
        """
        source: QtCore.QModelIndex = self.source_index(index)
        if not source.isValid():
            return super().flags(index)
        elif source.model() is self._structure:
            if index.column() == 2:
                return self._structure.flags(source.siblingAtColumn(1))
            else:
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        elif source.model() is self._modes:
            return self._modes.flags(source.siblingAtColumn(index.column()))
        else:
            row: BlockSymbolDraftRow | None = self.symbol_row(index)
        if index.column() == 0 and row is not None:
            # Both existing and pending symbols use the native inline item
            # editor. Existing identities are still renamed by the owning
            # Dynamic Editor through a synchronous request from setData().
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        elif (index.column() == 2
              and row is not None
              and (row.get_kind() == BlockSymbolKind.EVENT_PARAMETER
                   or (row.get_kind() == BlockSymbolKind.PARAMETER
                       and row.get_static_reference() is None))):
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        elif index.column() == 1:
            # Role changes remain in the add-symbol form; existing rows expose
            # their role as read-only descriptive data.
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        else:
            columns: tuple[int, ...] = (1, 2, 4, 3)
            return self._symbols.flags(source.siblingAtColumn(columns[index.column()]))

    def setData(self, index: QtCore.QModelIndex, value: object,
                role: int = Qt.ItemDataRole.EditRole) -> bool:
        """Forward cell edits to the models used by Validate and Apply.

        :param index: Edited tree cell.
        :param value: Editor value or checkbox state.
        :param role: Qt edit role.
        :return: Whether the backing model accepted the edit.
        """
        source: QtCore.QModelIndex = self.source_index(index)
        if not source.isValid() or role >= Qt.ItemDataRole.UserRole:
            return super().setData(index, value, role)
        elif source.model() is self._structure:
            if index.column() == 2:
                return self._structure.setData(source.siblingAtColumn(1), value, role)
            else:
                return False
        elif source.model() is self._modes:
            return self._modes.setData(
                source.siblingAtColumn(index.column()),
                value,
                role,
            )
        else:
            row: BlockSymbolDraftRow | None = self.symbol_row(index)
        if index.column() == 2 and row is not None and row.get_kind() == BlockSymbolKind.EVENT_PARAMETER:
            value_index: QtCore.QModelIndex = self._parameters.find_value_index(row.get_owner(), row.get_variable())
            if value_index.isValid():
                return self._parameters.setData(value_index, value, role)
            elif role == Qt.ItemDataRole.EditRole:
                if is_finite_real_number_text(value):
                    row.set_value_text(str(value))
                    self.dataChanged.emit(index, index)
                    return True
                else:
                    return False
            else:
                return False
        elif (index.column() == 2
              and row is not None
              and row.get_kind() == BlockSymbolKind.PARAMETER
              and row.get_static_reference() is None):
            if role == Qt.ItemDataRole.EditRole and is_finite_real_number_text(value):
                row.set_value_text(str(value))
                self.dataChanged.emit(index, index)
                return True
            else:
                return False
        else:
            columns: tuple[int, ...] = (1, 2, 4, 3)
            if (
                index.column() == 0
                and row is not None
                and role == Qt.ItemDataRole.EditRole
            ):
                old_name: str = row.get_name()
                new_name: str = str(value).strip()
                if not new_name.isidentifier() or keyword.iskeyword(new_name):
                    return False
                elif new_name == old_name:
                    return True
                else:
                    pass
                if row.is_new():
                    # Pending rows do not yet have an Engine identity, so the
                    # draft model can rename them locally after checking the
                    # complete visible namespace.
                    other_index: int
                    for other_index in range(self._symbols.rowCount()):
                        other_row: BlockSymbolDraftRow | None = self._symbols.get_row(other_index)
                        if other_row is not None and other_row is not row and other_row.get_name() == new_name:
                            return False
                        else:
                            pass
                    accepted: bool = self._symbols.setData(source.siblingAtColumn(1), new_name, role)
                    if accepted:
                        self.pendingNameChanged.emit(old_name, row.get_name())
                    else:
                        pass
                    return accepted
                else:
                    # Existing variables may belong to a connected alias
                    # component. The central editor validates and propagates
                    # that complete component before the cell accepts the edit.
                    variable: Var | None = row.get_variable()
                    if variable is None:
                        return False
                    else:
                        request: BlockVariableRenameRequest = BlockVariableRenameRequest(
                            variable=variable,
                            requested_name=new_name,
                        )
                        self.existingNameChangeRequested.emit(request)
                    if request.is_successful():
                        self.dataChanged.emit(
                            index,
                            index,
                            list((Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole,)),
                        )
                        return True
                    else:
                        return False
            elif index.column() == 2 and isinstance(value, ParamPowerFlowReferenceType):
                return self._symbols.setData(source.siblingAtColumn(4), f"ParamPowerFlowReferenceType.{value.name}", role)
            elif index.column() == 2 and isinstance(value, VarPowerFlowReferenceType):
                return self._symbols.setData(source.siblingAtColumn(4), f"VarPowerFlowReferenceType.{value.name}", role)
            elif index.column() == 2 and value is None:
                return self._symbols.setData(source.siblingAtColumn(4), "None", role)
            else:
                return self._symbols.setData(source.siblingAtColumn(columns[index.column()]), value, role)

    @QtCore.Slot()
    def refresh_values(self) -> None:
        """Repaint source changes without rebuilding expanded owner branches.

        :return: None.
        """
        group_row: int
        for group_row in range(self.rowCount()):
            group: QtCore.QModelIndex = self.index(group_row, 0)
            child_row: int
            for child_row in range(self.rowCount(group)):
                child: QtCore.QModelIndex = self.index(child_row, 0, group)
                self.dataChanged.emit(child, child.siblingAtColumn(3))
                if self.rowCount(child) > 0:
                    self.dataChanged.emit(self.index(0, 0, child), self.index(self.rowCount(child) - 1, 3, child))
                else:
                    pass


class BlockPropertyValueDelegate(StructuralSettingDelegate):
    """Use existing structural editors and typed power-flow reference combos."""

    __slots__ = ()

    def createEditor(self, parent: QtWidgets.QWidget, option: QtWidgets.QStyleOptionViewItem,
                     index: QtCore.QModelIndex) -> QtWidgets.QWidget:
        """Select an expression editor, mapping combo or structural editor.

        :param parent: Owning view viewport.
        :param option: Native view style options.
        :param index: Tree value cell.
        :return: Editor appropriate for the represented property.
        """
        model: QtCore.QAbstractItemModel | None = index.model()
        if isinstance(model, BlockPropertyTreeModel):
            source: QtCore.QModelIndex = model.source_index(index)
            row: BlockSymbolDraftRow | None = model.symbol_row(index)
        else:
            source = QtCore.QModelIndex()
            row = None
        if source.isValid() and isinstance(source.model(), BlockStructuralSettingsModel):
            return super().createEditor(parent, option, source.siblingAtColumn(1))
        elif row is None or row.get_kind() == BlockSymbolKind.EVENT_PARAMETER:
            return QtWidgets.QLineEdit(parent)
        else:
            combo: QtWidgets.QComboBox = QtWidgets.QComboBox(parent)
            if row.supports_static_reference():
                # The same compact editor exposes the optional device source and
                # the local literal. Keeping it editable lets an unmapped fixed
                # parameter retain normal numeric editing.
                combo.setEditable(True)
                combo.addItem(row.get_value_text(), None)
                static_reference: ParamPowerFlowReferenceType
                for static_reference in ParamPowerFlowReferenceType:
                    if static_reference == ParamPowerFlowReferenceType.NOTHING:
                        pass
                    else:
                        combo.addItem(f"ParamPowerFlowReferenceType.{static_reference.name}", static_reference)
            else:
                combo.addItem(self.tr("None"), None)
                external_reference: VarPowerFlowReferenceType
                for external_reference in VarPowerFlowReferenceType:
                    combo.addItem(f"VarPowerFlowReferenceType.{external_reference.name}", external_reference)
            return combo

    def setModelData(self, editor: QtWidgets.QWidget, model: QtCore.QAbstractItemModel,
                     index: QtCore.QModelIndex) -> None:
        """Pass mapping enums independently of their displayed labels.

        :param editor: Active text, mapping or structural editor.
        :param model: Backing tree model.
        :param index: Edited value cell.
        :return: None.
        """
        if isinstance(model, BlockPropertyTreeModel) and isinstance(editor, QtWidgets.QComboBox):
            row: BlockSymbolDraftRow | None = model.symbol_row(index)
            if row is not None:
                selected_data: object = editor.currentData()
                if row.get_kind() == BlockSymbolKind.PARAMETER and selected_data is None:
                    # First detach a former device mapping, then stage the local
                    # literal through the now-unmapped parameter branch.
                    mapping_cleared: bool = model.setData(
                        index,
                        None,
                        Qt.ItemDataRole.EditRole,
                    )
                    if mapping_cleared and is_finite_real_number_text(editor.currentText()):
                        model.setData(
                            index,
                            editor.currentText(),
                            Qt.ItemDataRole.EditRole,
                        )
                    else:
                        pass
                else:
                    model.setData(index, selected_data, Qt.ItemDataRole.EditRole)
            else:
                super().setModelData(editor, model, index)
        else:
            super().setModelData(editor, model, index)


class DynamicBlockPropertiesDialog(QtWidgets.QDialog):
    """Property editor content for one Dynamic Model Editor block."""

    _PROPERTY_BASE_COLUMN_WIDTHS: tuple[int, int, int, int] = (170, 100, 230, 60)

    # Symbolic UIDs are wider than Qt's 32-bit ``int`` signal type.
    blockApplied = Signal(object)
    structuralRebuildRequested = Signal(object)
    variableRenameRequested = Signal(object)
    outputExportChangesRequested = Signal(object)
    symbolRemovalsRequested = Signal(object)
    addToPlotRequested = Signal(object, object, object)
    closed = Signal()

    __slots__ = (
        "ui",
        "_block",
        "_block_type_name",
        "_structural_block_type",
        "_structural_builder",
        "_general_structural_model",
        "_special_structural_model",
        "_var_factory",
        "_parameter_model",
        "_symbol_model",
        "_retained_mode_model",
        "_property_tree_model",
        "_runtime_logic_drafts",
        "_procedural_add_menu",
        "_namespace",
        "_equation_buffers",
        "_active_equation_buffer_index",
        "_loading_equation_buffer",
        "_dae_editor",
        "_prepared_to_delete",
        "_draft_has_changes",
        "_property_columns_initialized",
        "_read_only",
    )

    def __init__(self,
                 block: Block,
                 block_type_name: str,
                 var_factory: VarFactory,
                 parent: QtWidgets.QWidget | None = None,
                 structural_block_type: BlockType | None = None,
                 structural_builder: TemplateDefinition | None = None,
                 dark_theme: bool = False) -> None:
        """
        Create a four-tab editor around detached property and equation drafts.

        The Qt Designer form owns the complete page topology. Python only
        installs block-dependent models, editors, and context-menu workflows.

        :param block: Symbolic block edited by this transaction.
        :param block_type_name: Persisted diagram-node type name.
        :param var_factory: Factory that owns symbolic variables.
        :param parent: Owning Dynamic Model Editor widget.
        :param structural_block_type: Optional catalogue type used for rebuilding.
        :param structural_builder: Optional initialized structural template builder.
        :param dark_theme: Whether the Python editor uses the dark palette.
        :return: None.
        """
        super().__init__(parent)

        # Designer remains the source of truth for the four visible pages.
        self.ui: Ui_DynamicBlockPropertiesDialog = Ui_DynamicBlockPropertiesDialog()
        self.ui.setupUi(self)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # Preserve the authoritative block and optional structural rebuild data.
        self._block: Block = block
        self._block_type_name: str = block_type_name
        self._structural_block_type: BlockType | None = structural_block_type
        self._structural_builder: TemplateDefinition | None = structural_builder
        self._var_factory: VarFactory = var_factory

        # Provider-owned bindings cannot be reconstructed by the catalogue
        # editor, so the complete dialogue becomes observational for this Block.
        self._read_only: bool = False
        owned_block: Block
        for owned_block in block.get_all_blocks():
            procedural_entry: ProceduralLogicBase
            for procedural_entry in owned_block.procedural_logic:
                if procedural_entry.logic_tpe == ProceduralLogicType.ManufacturerNativeController:
                    self._read_only = True
                else:
                    pass

        # Separate ordinary settings from large model-specific configuration.
        general_structural_properties: List[TemplateProp] = list()
        special_structural_properties: List[TemplateProp] = list()
        if structural_builder is not None:
            general_structural_properties, special_structural_properties = split_structural_template_properties(
                structural_builder
            )
        else:
            pass
        self._general_structural_model: BlockStructuralSettingsModel = BlockStructuralSettingsModel(
            general_structural_properties,
            self,
        )
        self._special_structural_model: BlockStructuralSettingsModel = BlockStructuralSettingsModel(
            special_structural_properties,
            self,
        )

        # All edits stay detached until Apply validates the complete transaction.
        self._parameter_model: BlockParameterDraftModel = BlockParameterDraftModel(block, self)
        self._symbol_model: BlockSymbolDraftModel = BlockSymbolDraftModel(block, self)

        # Build one source buffer for every direct or nested equation owner.
        self._equation_buffers: List[BlockCodeBuffer] = list()
        child_block: Block
        for child_block in block.get_all_blocks():
            self._equation_buffers.append(BlockCodeBuffer(child_block))
        self._runtime_logic_drafts: RuntimeLogicDraftCollection = (
            self._build_runtime_logic_drafts_from_buffers()
        )
        self._retained_mode_model: RetainedModeDraftTableModel = RetainedModeDraftTableModel(
            self._runtime_logic_drafts,
            self,
        )
        self._property_tree_model: BlockPropertyTreeModel = BlockPropertyTreeModel(
            block,
            self._symbol_model,
            self._parameter_model,
            self._retained_mode_model,
            self._general_structural_model,
            self,
        )

        # The DAE page owns a specialized editor inserted into its Designer
        # container, while every surrounding control comes directly from the UI.
        self._namespace: Dict[str, Expr] = build_block_symbol_namespace(block)
        self._namespace = self._runtime_logic_drafts.build_validation_namespace(self._namespace)
        self._active_equation_buffer_index: int = self._find_initial_equation_buffer_index()
        self._loading_equation_buffer: bool = False
        self._dae_editor: DaeCodeEditor = DaeCodeEditor(
            self.ui.dae_editor_container,
            self._namespace,
            dark_theme=dark_theme,
        )
        # Procedural-logic insertion belongs to the DAE page because it edits
        # source rather than adding a property-tree row.
        self._procedural_add_menu: QtWidgets.QMenu = QtWidgets.QMenu(self.ui.procedural_add_button)
        self._procedural_add_menu.setToolTipsVisible(True)

        # toast manager
        self.toast_manager = ToastManager(parent=self, position_top=False)

        self._prepared_to_delete: bool = False
        self._draft_has_changes: bool = False
        self._property_columns_initialized: bool = False

        self._configure_procedural_menu()
        self._build_ui()
        self._connect_signals()
        if self._read_only:
            # Inspection remains available, while every route that can mutate
            # source, symbols, properties, or structural settings is disabled.
            self.setWindowTitle(
                self.tr("Block properties - {name} (read-only manufacturer model)").format(
                    name=self._block.name
                )
            )
            self.ui.apply_button.setEnabled(False)
            self.ui.apply_button.setToolTip(
                self.tr("Manufacturer model bindings are managed by their provider and are read-only here.")
            )
            self.ui.procedural_add_button.setEnabled(False)
            self.ui.property_tree.setEditTriggers(
                QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
            )
            self.ui.property_tree.setContextMenuPolicy(
                QtCore.Qt.ContextMenuPolicy.NoContextMenu
            )
            property_action: QtGui.QAction
            for property_action in self.ui.property_tree.actions():
                property_action.setEnabled(False)
            self.ui.special_settings_table.setEditTriggers(
                QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
            )
            self._dae_editor.setReadOnly(True)
        else:
            pass
        self._refresh_dae_language_context()
        self._clear_dae_validation_feedback()
        self.refresh_draft_state()

    def prepare_to_delete(self) -> None:
        """Detach Qt models and document resources before binary destruction.

        PySide wrappers may outlive their C++ children until Python performs a
        later garbage-collection pass. Explicitly sever the model/view and
        document relationships while every object is still valid.

        :return: None.
        """
        if self._prepared_to_delete:
            pass
        else:
            self._prepared_to_delete = True
            self._disconnect_child_signals()
            self._property_tree_model.prepare_to_delete()
            self._procedural_add_menu.clear()
            self._procedural_add_menu.deleteLater()
            self._dae_editor.prepare_to_delete()
            self.ui.dae_editor_layout.removeWidget(self._dae_editor)
            self._dae_editor.deleteLater()
            self.ui.property_tree.closePersistentEditor(self.ui.property_tree.currentIndex())
            self.ui.property_tree.setItemDelegateForColumn(2, None)
            self.ui.property_tree.setModel(None)
            self.ui.special_settings_table.closePersistentEditor(
                self.ui.special_settings_table.currentIndex()
            )
            self.ui.special_settings_table.setItemDelegateForColumn(1, None)
            self.ui.special_settings_table.setModel(None)
            self.ui.latex_selection_tree.clear()
            self.ui.latex_source_preview.clear()
            self.ui.equation_owner_combo.clear()
            self._property_tree_model.deleteLater()
            self._retained_mode_model.deleteLater()
            self._symbol_model.deleteLater()
            self._parameter_model.deleteLater()
            self._special_structural_model.deleteLater()
            self._general_structural_model.deleteLater()

    def _disconnect_child_signals(self) -> None:
        """Disconnect child signals targeting this dialog before deletion.

        :return: None.
        """
        # Qt keeps signal/slot links in C++ objects. Each Designer child that
        # emits into this dialog must drop that receiver before the child tree
        # is queued for deletion.
        child: QtCore.QObject
        for child in self.findChildren(QtCore.QObject):
            disconnect_qobject_from_receiver(child, self)
        disconnect_qobject_from_receiver(self._property_tree_model, self)

    def set_dark_mode(self) -> None:
        """Apply the dark palette to source editors owned by this dialogue.

        :return: None.
        """
        self._dae_editor.set_dark_mode()

    def set_light_mode(self) -> None:
        """Apply the light palette to source editors owned by this dialogue.

        :return: None.
        """
        self._dae_editor.set_light_mode()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Confirm unapplied edits and release owned Qt resources.

        :param event: Incoming close event.
        :return: None.
        """
        requires_confirmation: bool = (
            not self._prepared_to_delete
            and self.has_unapplied_changes()
        )
        if requires_confirmation:
            selected_button: QtWidgets.QMessageBox.StandardButton = (
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("Unsaved Block Properties changes"),
                    self.tr(
                        "Block Properties contains changes that have not been applied. "
                        "Discard those changes and close the editor?"
                    ),
                    QtWidgets.QMessageBox.StandardButton.Discard
                    | QtWidgets.QMessageBox.StandardButton.Cancel,
                    QtWidgets.QMessageBox.StandardButton.Cancel,
                )
            )
            discard_changes: bool = (
                selected_button == QtWidgets.QMessageBox.StandardButton.Discard
            )
        else:
            discard_changes = True

        if discard_changes:
            self.prepare_to_delete()
            self.closed.emit()
            QtWidgets.QDialog.closeEvent(self, event)
        else:
            event.ignore()
            self.raise_()
            self.activateWindow()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """Expand the property tree after Qt creates the visible layout.

        :param event: Incoming show event.
        :return: None.
        """
        QtWidgets.QDialog.showEvent(self, event)
        if self._property_columns_initialized:
            pass
        else:
            self._fit_initial_property_columns()
            self._property_columns_initialized = True
        self.filter_properties(self.ui.property_search.text())

    def _fit_initial_property_columns(self) -> None:
        """Fill the initial property-tree viewport with weighted columns.

        Value keeps its established editing width. Any additional room in the
        default dialogue is distributed across Name, Type, and Output, after
        which all sections remain manually resizable.

        :return: None.
        """
        header: QtWidgets.QHeaderView = self.ui.property_tree.header()
        base_widths: tuple[int, int, int, int] = self._PROPERTY_BASE_COLUMN_WIDTHS
        available_width: int = max(
            self.ui.property_tree.viewport().width(),
            sum(base_widths),
        )
        extra_width: int = available_width - sum(base_widths)
        name_extra: int = int(extra_width * 0.4)
        type_extra: int = int(extra_width * 0.3)
        output_extra: int = extra_width - name_extra - type_extra
        initial_widths: List[int] = list((
            base_widths[0] + name_extra,
            base_widths[1] + type_extra,
            base_widths[2],
            base_widths[3] + output_extra,
        ))
        column_index: int
        for column_index in range(header.count()):
            header.resizeSection(column_index, initial_widths[column_index])

    def _find_initial_equation_buffer_index(self) -> int:
        """
        Prefer the first recursive block that contains editable equations.

        :return: Index of the first recursive block containing editable equations.
        """
        result: int = 0
        index: int
        buffer: BlockCodeBuffer
        found: bool = False
        for index, buffer in enumerate(self._equation_buffers):
            candidate: Block = buffer.get_block()
            has_supported_content: bool = bool(
                candidate.state_eqs
                or candidate.algebraic_eqs
                or candidate.init_eqs
                or candidate.diff_init_eqs
            )
            if has_supported_content and not found:
                result = index
                found = True
            else:
                pass
        return result

    def _build_ui(self) -> None:
        """
        Bind block-dependent behavior to the four Designer-owned pages.

        General options contains only the property tree, DAE model contains the
        Python editor, LaTeX rendering contains export controls, and Special
        configuration is removed when the block has no special properties.

        :return: None.
        """
        self.setWindowTitle(self.tr("Block properties - {name}").format(name=self._block.name))
        self.setModal(False)

        # General options owns only the searchable property hierarchy.
        self.ui.property_tree.setModel(self._property_tree_model)
        self.ui.property_tree.setItemDelegateForColumn(
            2,
            BlockPropertyValueDelegate(self.ui.property_tree),
        )
        property_header: QtWidgets.QHeaderView = self.ui.property_tree.header()
        configure_interactive_table_header(
            property_header,
            list(self._PROPERTY_BASE_COLUMN_WIDTHS),
        )
        self.restore_property_tree()

        # Populate the DAE owner selector once so tab changes never recreate or
        # discard an editor document, cursor, undo stack, or staged code.
        buffer_index: int
        equation_buffer: BlockCodeBuffer
        for buffer_index, equation_buffer in enumerate(self._equation_buffers):
            owner_block: Block = equation_buffer.get_block()
            owner_label: str = f"{owner_block.name} [{buffer_index + 1}]"
            self.ui.equation_owner_combo.addItem(owner_label, buffer_index)
        self.ui.equation_owner_combo.setCurrentIndex(self._active_equation_buffer_index)
        active_buffer: BlockCodeBuffer = self._equation_buffers[self._active_equation_buffer_index]
        self._dae_editor.setPlainText(active_buffer.get_code())
        self._dae_editor.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        fixed_font: QtGui.QFont = QtGui.QFontDatabase.systemFont(
            QtGui.QFontDatabase.SystemFont.FixedFont
        )
        self._dae_editor.setFont(fixed_font)
        self._dae_editor.update_line_number_area_width(0)
        self.ui.dae_editor_layout.addWidget(self._dae_editor, 1)

        # LaTeX rendering reads the same buffers and exposes independent block
        # and equation-section selection without duplicating the DAE editor.
        self.ui.latex_source_preview.setFont(self._dae_editor.font())
        configure_interactive_table_header(
            self.ui.latex_selection_tree.header(),
            list((640, 170)),
        )
        self._rebuild_latex_selection_tree()

        # Structured settings remain a fourth tab only for templates that
        # actually expose special rebuild properties.
        special_table: QtWidgets.QTableView = self.ui.special_settings_table
        special_table.setModel(self._special_structural_model)
        special_table.setItemDelegateForColumn(
            1,
            StructuralSettingDelegate(special_table),
        )
        configure_interactive_table_header(
            special_table.horizontalHeader(),
            list((320, 760)),
        )
        special_table.horizontalHeader().setStretchLastSection(True)
        special_index: int = self.ui.tab_widget.indexOf(self.ui.special_settings_page)
        if self._special_structural_model.rowCount() > 0:
            pass
        else:
            self.ui.tab_widget.removeTab(special_index)

        self.ui.tab_widget.setCurrentWidget(self.ui.general_page)

    def _configure_procedural_menu(self) -> None:
        """
        Populate the DAE procedural-logic insertion menu.

        :return: None.
        """
        current_group_label: str | None = None
        procedural_descriptor: ProceduralBlockTemplateDescriptor
        for procedural_descriptor in get_dynamic_library_procedural_descriptors():
            group_label: str = procedural_descriptor.category_path[0]
            if group_label != current_group_label:
                self._procedural_add_menu.addSection(self.tr(group_label))
                current_group_label = group_label
            else:
                pass

            logic_tpe: ProceduralLogicType = procedural_descriptor.logic_tpe
            logic_action: QtGui.QAction = gf.add_menu_entry(
                menu=self._procedural_add_menu,
                text=procedural_descriptor.display_label,
                icon_path=":/Icons/icons/dyn_add.png",
            )
            logic_action.setData(logic_tpe)
            procedural_help: str | None = get_procedural_logic_help_by_code_name(
                logic_tpe.value
            )
            if procedural_help is not None:
                logic_action.setToolTip(procedural_help)
                logic_action.setStatusTip(procedural_help)
            else:
                pass
        self.ui.procedural_add_button.setMenu(self._procedural_add_menu)

    def show_add_symbol_dialog(self,
                               category: BlockSymbolCategory,
                               owner: Block | None) -> None:
        """
        Open the add-property form selected from the property-tree context menu.

        :param category: Variable, parameter, or retained-mode category to add.
        :param owner: Preferred owner resolved from the clicked tree branch.
        :return: None.
        """
        if self._read_only:
            pass
        else:
            # The dialog is created only for this invocation. The safe executor
            # owns deferred destruction, so no hidden standby widget survives.
            owners: list[Block] = list(self._block.get_all_blocks())
            dialog: AddSymbolDialog = AddSymbolDialog(
                category=category,
                owners=owners,
                preferred_owner=owner,
                parent=self,
            )
            dialog_result: int = exec_dialog_safely(dialog=dialog)
            selection: AddSymbolSelection | None = dialog.get_selection()
            if dialog_result == QtWidgets.QDialog.DialogCode.Accepted and selection is not None:
                self._stage_add_symbol_selection(selection=selection)
            else:
                pass

    @QtCore.Slot()
    def restore_property_tree(self) -> None:
        """Expand owner branches and restore spanning category rows after rebuilding.

        :return: None.
        """
        # Category and owner rows are structural headers, so they keep spanning
        # after each model rebuild while the property tree remains fully open.
        group_row: int
        for group_row in range(self._property_tree_model.rowCount()):
            group: QtCore.QModelIndex = self._property_tree_model.index(group_row, 0)
            self.ui.property_tree.setFirstColumnSpanned(group_row, QtCore.QModelIndex(), True)
            owner_row: int
            for owner_row in range(self._property_tree_model.rowCount(group)):
                owner_index: QtCore.QModelIndex = self._property_tree_model.index(owner_row, 0, group)
                owner: object = owner_index.data(Qt.ItemDataRole.UserRole + 1)
                if isinstance(owner, Block):
                    self.ui.property_tree.setFirstColumnSpanned(owner_row, group, True)
                else:
                    pass
        self.filter_properties(self.ui.property_search.text())

    @QtCore.Slot(str)
    def filter_properties(self, search_text: str) -> None:
        """Filter leaves while retaining matching ancestor categories and owners.

        :param search_text: Case-insensitive property or owner search.
        :return: None.
        """
        self._filter_property_branch(QtCore.QModelIndex(), search_text.strip().casefold(), False)
        self._expand_property_tree_branch(QtCore.QModelIndex())

    def _expand_property_tree_branch(self, parent: QtCore.QModelIndex) -> None:
        """Expand every property-tree branch below one parent index.

        :param parent: Parent branch to expand recursively.
        :return: None.
        """
        row: int
        for row in range(self._property_tree_model.rowCount(parent)):
            index: QtCore.QModelIndex = self._property_tree_model.index(row, 0, parent)
            if self._property_tree_model.rowCount(index) > 0:
                self.ui.property_tree.setExpanded(index, True)
                self._expand_property_tree_branch(index)
            else:
                pass

    def _select_retained_mode_in_tree(self, owner: Block, mode_name: str) -> None:
        """Reveal and select one newly staged retained mode.

        :param owner: Direct block receiving the new mode.
        :param mode_name: Name inserted into the retained-mode dictionary.
        :return: None.
        """
        category_row: int
        for category_row in range(self._property_tree_model.rowCount()):
            category_index: QtCore.QModelIndex = self._property_tree_model.index(
                category_row,
                0,
            )
            category: object = category_index.data(Qt.ItemDataRole.UserRole + 2)
            if category == BlockSymbolCategory.RETAINED_MODES:
                owner_row: int
                for owner_row in range(self._property_tree_model.rowCount(category_index)):
                    owner_index: QtCore.QModelIndex = self._property_tree_model.index(
                        owner_row,
                        0,
                        category_index,
                    )
                    row_owner: object = owner_index.data(Qt.ItemDataRole.UserRole + 1)
                    if row_owner is owner:
                        mode_row: int
                        for mode_row in range(self._property_tree_model.rowCount(owner_index)):
                            mode_index: QtCore.QModelIndex = self._property_tree_model.index(
                                mode_row,
                                0,
                                owner_index,
                            )
                            if str(mode_index.data()) == mode_name:
                                self.ui.property_tree.expand(category_index)
                                self.ui.property_tree.expand(owner_index)
                                self.ui.property_tree.setCurrentIndex(mode_index)
                                self.ui.property_tree.scrollTo(mode_index)
                            else:
                                pass
                    else:
                        pass
            else:
                pass

    def _filter_property_branch(self, parent: QtCore.QModelIndex, query: str, ancestor_matches: bool) -> bool:
        """Apply a recursive visibility filter without sorting the DAE lists.

        :param parent: Branch whose immediate children are examined.
        :param query: Normalized search text.
        :param ancestor_matches: Whether the owner's label already matched.
        :return: Whether at least one child should remain visible.
        """
        any_match: bool = False
        row: int
        for row in range(self._property_tree_model.rowCount(parent)):
            index: QtCore.QModelIndex = self._property_tree_model.index(row, 0, parent)
            matches: bool = ancestor_matches or len(query) == 0
            column: int
            for column in range(4):
                if query in str(index.siblingAtColumn(column).data()).casefold():
                    matches = True
                else:
                    pass
            if self._property_tree_model.rowCount(index) > 0:
                matches = self._filter_property_branch(index, query, matches)
                if matches and len(query) > 0:
                    self.ui.property_tree.setExpanded(index, True)
                else:
                    pass
            else:
                pass
            self.ui.property_tree.setRowHidden(row, parent, not matches)
            any_match = any_match or matches
        return any_match

    @QtCore.Slot()
    def rename_property_symbol(self) -> None:
        """Start inline editing of the selected symbol's Name cell.

        :return: None.
        """
        index: QtCore.QModelIndex = self.ui.property_tree.currentIndex().siblingAtColumn(0)
        row: BlockSymbolDraftRow | None = self._property_tree_model.symbol_row(index)
        mode: RuntimeModeDraft | None = self._property_tree_model.retained_mode_row(index)
        if row is not None or mode is not None:
            self.ui.property_tree.edit(index)
        else:
            pass

    @QtCore.Slot()
    def delete_property_symbol(self) -> None:
        """Delete only a selected symbol, never a category or an owner branch.

        :return: None.
        """
        selected_index: QtCore.QModelIndex = self.ui.property_tree.currentIndex()
        row: BlockSymbolDraftRow | None = self._property_tree_model.symbol_row(selected_index)
        mode: RuntimeModeDraft | None = self._property_tree_model.retained_mode_row(selected_index)
        if row is not None or mode is not None:
            self._delete_selected_symbol(self.ui.property_tree)
        else:
            pass

    def _connect_signals(self) -> None:
        """
        Connect actions with explicit named slots.

        :return: None.
        """
        self.ui.apply_button.clicked.connect(self.apply_changes)
        self.ui.validate_code_button.clicked.connect(self.validate_complete_dae_code)
        self._dae_editor.textChanged.connect(self.on_dae_code_changed)
        self.ui.equation_owner_combo.currentIndexChanged.connect(self.on_equation_owner_changed)
        self._procedural_add_menu.triggered.connect(self.insert_procedural_logic)
        self._symbol_model.dataChanged.connect(self.on_symbol_draft_changed)
        self._symbol_model.rowsInserted.connect(self.refresh_draft_state)
        self._symbol_model.rowsRemoved.connect(self.refresh_draft_state)
        self._symbol_model.modelReset.connect(self.refresh_draft_state)
        self._parameter_model.dataChanged.connect(self.refresh_draft_state)
        self._parameter_model.modelReset.connect(self.refresh_draft_state)
        self._general_structural_model.dataChanged.connect(self.refresh_draft_state)
        self._general_structural_model.modelReset.connect(self.refresh_draft_state)
        self._special_structural_model.dataChanged.connect(self.refresh_draft_state)
        self._special_structural_model.modelReset.connect(self.refresh_draft_state)
        self._retained_mode_model.dataChanged.connect(self.on_retained_mode_draft_changed)
        self._retained_mode_model.rowsInserted.connect(self.refresh_draft_state)
        self._retained_mode_model.rowsRemoved.connect(self.refresh_draft_state)
        self._retained_mode_model.modelReset.connect(self.refresh_draft_state)
        self._retained_mode_model.modeNameChanged.connect(
            self.on_retained_mode_name_changed
        )
        self.ui.property_tree.customContextMenuRequested.connect(self.show_symbol_context_menu)
        self.ui.property_search.textChanged.connect(self.filter_properties)
        self._property_tree_model.rebuilt.connect(self.restore_property_tree)
        self._property_tree_model.pendingNameChanged.connect(self.on_pending_symbol_renamed)
        self._property_tree_model.existingNameChangeRequested.connect(
            self.on_existing_symbol_name_change_requested
        )
        rename_action: QtGui.QAction = QtGui.QAction(self.tr("Rename"), self.ui.property_tree)
        rename_action.setShortcut(QtGui.QKeySequence(Qt.Key.Key_F2))
        rename_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        rename_action.triggered.connect(self.rename_property_symbol)
        self.ui.property_tree.addAction(rename_action)
        delete_action: QtGui.QAction = QtGui.QAction(self.tr("Delete"), self.ui.property_tree)
        delete_action.setShortcut(QtGui.QKeySequence(Qt.Key.Key_Delete))
        delete_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        delete_action.triggered.connect(self.delete_property_symbol)
        self.ui.property_tree.addAction(delete_action)
        self.ui.dae_code_search.textChanged.connect(self.update_dae_code_search)
        self.ui.dae_code_search.returnPressed.connect(self.find_next_dae_code_match)
        self.ui.dae_search_previous_button.clicked.connect(self.find_previous_dae_code_match)
        self.ui.dae_search_next_button.clicked.connect(self.find_next_dae_code_match)
        self.ui.latex_select_all_button.clicked.connect(self.select_all_latex_sections)
        self.ui.latex_clear_button.clicked.connect(self.clear_latex_sections)
        self.ui.latex_selection_tree.itemChanged.connect(self.on_latex_selection_changed)
        self.ui.export_rendered_button.clicked.connect(self.export_rendered_equations_pdf)

    def has_unapplied_changes(self) -> bool:
        """Return the cached transaction state exposed to the dock host.

        :return: Whether the complete Block Properties draft differs from its
            most recently accepted model state.
        """
        return self._draft_has_changes

    @QtCore.Slot()
    def refresh_draft_state(self) -> None:
        """Recompute and publish whether Block Properties owns pending edits.

        Code, symbols, parameter expressions and structural settings form one
        transaction. The comparison is also run after every edit so manually
        restoring the accepted value unlocks the rest of VeraGrid immediately.

        :return: None.
        """
        if self._prepared_to_delete or self._loading_equation_buffer:
            pass
        else:
            has_changes: bool = (
                self._general_structural_model.has_changes()
                or self._special_structural_model.has_changes()
                or self._parameter_model.has_changes()
                or self._symbol_model.has_changes()
            )
            if not has_changes:
                equation_buffer: BlockCodeBuffer
                for equation_buffer in self._equation_buffers:
                    if equation_buffer.has_changes():
                        has_changes = True
                    else:
                        pass
            else:
                pass
            if has_changes != self._draft_has_changes:
                self._draft_has_changes = has_changes
            else:
                pass

    @QtCore.Slot(str)
    def update_dae_code_search(self, search_text: str) -> None:
        """Refresh Python-code matches without running DAE validation.

        :param search_text: User-entered source-code query.
        :return: None.
        """
        match_count: int = self._dae_editor.set_search_text(search_text)
        has_query: bool = len(search_text.strip()) > 0
        has_matches: bool = match_count > 0
        self.ui.dae_search_previous_button.setEnabled(has_matches)
        self.ui.dae_search_next_button.setEnabled(has_matches)
        if not has_query:
            self.ui.dae_code_search.setToolTip("")
        elif has_matches:
            self.ui.dae_code_search.setToolTip(self.tr("1 / {count}").format(count=match_count))
        else:
            self.ui.dae_code_search.setToolTip(self.tr("No matches"))

    @QtCore.Slot()
    def find_previous_dae_code_match(self) -> None:
        """Select the previous Python-code search match.

        :return: None.
        """
        active_match: int
        match_count: int
        active_match, match_count = self._dae_editor.move_to_search_match(-1)
        self._update_dae_search_position(active_match, match_count)

    @QtCore.Slot()
    def find_next_dae_code_match(self) -> None:
        """Select the next Python-code search match.

        :return: None.
        """
        active_match: int
        match_count: int
        active_match, match_count = self._dae_editor.move_to_search_match(1)
        self._update_dae_search_position(active_match, match_count)

    def _update_dae_search_position(self, active_match: int, match_count: int) -> None:
        """Update the compact Python-code search counter.

        :param active_match: One-based active match number.
        :param match_count: Total number of source-code matches.
        :return: None.
        """
        if match_count > 0:
            self.ui.dae_code_search.setToolTip(
                self.tr("{active} / {count}").format(active=active_match, count=match_count)
            )
        else:
            self.ui.dae_code_search.setToolTip(self.tr("No matches"))

    def _get_latex_section_count(self,
                                 draft: BlockEquationDraft,
                                 section: EquationExportSection) -> int:
        """Return the equation count for one selectable export section.

        :param draft: Parsed equations for one internal block.
        :param section: Section whose size is requested.
        :return: Number of equations available for export.
        """
        if section == EquationExportSection.STATE:
            result: int = len(draft.get_state_eqs())
        elif section == EquationExportSection.ALGEBRAIC:
            result = len(draft.get_algebraic_eqs())
        elif section == EquationExportSection.INITIALIZATION:
            result = len(draft.get_init_eqs())
        else:
            result = len(draft.get_diff_init_eqs())
        return result

    def _rebuild_latex_selection_tree(self) -> None:
        """
        Rebuild block/section choices while retaining checked selections.

        :return: None.
        """
        selected_keys: set[tuple[int, str]] = set()
        root_index: int
        for root_index in range(self.ui.latex_selection_tree.topLevelItemCount()):
            old_root: QtWidgets.QTreeWidgetItem = self.ui.latex_selection_tree.topLevelItem(root_index)
            child_index: int
            for child_index in range(old_root.childCount()):
                old_child: QtWidgets.QTreeWidgetItem = old_root.child(child_index)
                if old_child.checkState(0) == Qt.CheckState.Checked:
                    selected_owner: object = old_child.data(0, Qt.ItemDataRole.UserRole + 2)
                    section_value: object = old_child.data(0, Qt.ItemDataRole.UserRole + 1)
                    if isinstance(selected_owner, Block) and isinstance(section_value, str):
                        selected_keys.add((selected_owner.uid, section_value))
                    else:
                        pass
                else:
                    pass

        # Rebuilding creates and checks several items. Suppress intermediate
        # change notifications so the source view is regenerated once from the
        # complete selection tree rather than from partially constructed state.
        previous_signal_state: bool = self.ui.latex_selection_tree.blockSignals(True)
        self.ui.latex_selection_tree.clear()
        buffer_index: int
        buffer: BlockCodeBuffer
        for buffer_index, buffer in enumerate(self._equation_buffers):
            owner_block: Block = buffer.get_block()
            root_item: QtWidgets.QTreeWidgetItem = QtWidgets.QTreeWidgetItem(
                list((owner_block.name, "",))
            )
            root_item.setFlags(
                root_item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            root_item.setCheckState(0, Qt.CheckState.Unchecked)
            self.ui.latex_selection_tree.addTopLevelItem(root_item)
            try:
                draft: BlockEquationDraft = parse_equation_code(buffer.get_code(), self._namespace)
            except (TypeError, ValueError):
                draft = BlockEquationDraft(list(), list(), dict(), dict())

            section: EquationExportSection
            for section in EquationExportSection:
                section_count: int = self._get_latex_section_count(draft, section)
                section_item: QtWidgets.QTreeWidgetItem = QtWidgets.QTreeWidgetItem(
                    list((section.value, str(section_count),))
                )
                section_item.setData(0, Qt.ItemDataRole.UserRole, buffer_index)
                section_item.setData(0, Qt.ItemDataRole.UserRole + 1, section.value)
                # Keep the owner object: its UID may exceed Qt's integer range,
                # and its identity survives buffer reordering after Apply.
                section_item.setData(0, Qt.ItemDataRole.UserRole + 2, owner_block)
                if section_count > 0:
                    section_item.setFlags(section_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    if (owner_block.uid, section.value) in selected_keys:
                        section_item.setCheckState(0, Qt.CheckState.Checked)
                    else:
                        section_item.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    section_item.setFlags(section_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                root_item.addChild(section_item)
            self._synchronize_latex_block_check_state(root_item)
            root_item.setExpanded(True)
        self.ui.latex_selection_tree.blockSignals(previous_signal_state)
        self.refresh_latex_source_preview()

    def _set_latex_block_sections_check_state(self,
                                              root_item: QtWidgets.QTreeWidgetItem,
                                              check_state: Qt.CheckState) -> None:
        """Set every selectable equation section below one block.

        Empty sections remain disabled and unchecked because they do not
        contribute any equation to the generated LaTeX document.

        :param root_item: Top-level block item whose sections must be updated.
        :param check_state: Checked or unchecked state to apply.
        :return: None.
        """
        child_index: int
        for child_index in range(root_item.childCount()):
            child_item: QtWidgets.QTreeWidgetItem = root_item.child(child_index)
            is_enabled: bool = bool(child_item.flags() & Qt.ItemFlag.ItemIsEnabled)
            is_checkable: bool = bool(child_item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
            if is_enabled and is_checkable:
                child_item.setCheckState(0, check_state)
            else:
                pass

    def _synchronize_latex_block_check_state(self,
                                             root_item: QtWidgets.QTreeWidgetItem) -> None:
        """Reflect the selectable child states in one block checkbox.

        :param root_item: Top-level block item whose state must be recalculated.
        :return: None.
        """
        selectable_count: int = 0
        checked_count: int = 0
        child_index: int
        for child_index in range(root_item.childCount()):
            child_item: QtWidgets.QTreeWidgetItem = root_item.child(child_index)
            is_enabled: bool = bool(child_item.flags() & Qt.ItemFlag.ItemIsEnabled)
            is_checkable: bool = bool(child_item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
            if is_enabled and is_checkable:
                selectable_count += 1
                if child_item.checkState(0) == Qt.CheckState.Checked:
                    checked_count += 1
                else:
                    pass
            else:
                pass

        if checked_count == 0:
            root_state: Qt.CheckState = Qt.CheckState.Unchecked
        elif checked_count == selectable_count:
            root_state = Qt.CheckState.Checked
        else:
            root_state = Qt.CheckState.PartiallyChecked
        root_item.setCheckState(0, root_state)

    @QtCore.Slot(QtWidgets.QTreeWidgetItem, int)
    def on_latex_selection_changed(self,
                                   changed_item: QtWidgets.QTreeWidgetItem,
                                   changed_column: int) -> None:
        """Regenerate copyable source after one equation-group selection changes.

        :param changed_item: Tree item whose checked state changed.
        :param changed_column: Tree column that emitted the change.
        :return: None.
        """
        if changed_column == 0:
            previous_signal_state: bool = self.ui.latex_selection_tree.blockSignals(True)
            parent_item: QtWidgets.QTreeWidgetItem | None = changed_item.parent()
            if parent_item is None:
                requested_state: Qt.CheckState = changed_item.checkState(0)
                if requested_state == Qt.CheckState.Checked:
                    self._set_latex_block_sections_check_state(changed_item, Qt.CheckState.Checked)
                elif requested_state == Qt.CheckState.Unchecked:
                    self._set_latex_block_sections_check_state(changed_item, Qt.CheckState.Unchecked)
                else:
                    pass
                self._synchronize_latex_block_check_state(changed_item)
            else:
                self._synchronize_latex_block_check_state(parent_item)
            self.ui.latex_selection_tree.blockSignals(previous_signal_state)
        else:
            pass
        self.refresh_latex_source_preview()

    def refresh_latex_source_preview(self) -> None:
        """Show copy-ready LaTeX for all currently selected valid equations.

        Invalid DAE drafts leave the source view empty. The normal validation
        action remains responsible for displaying diagnostics, so merely
        changing a selection never introduces unrelated red error feedback.

        :return: None.
        """
        try:
            drafts: List[BlockEquationDraft] = self._parse_all_equation_buffers_for_export()
            entries: List[EquationExportEntry] = self._build_selected_equation_entries(drafts)
        except (TypeError, ValueError):
            latex_source: str = ""
        else:
            latex_source = build_latex_source(entries)
        self.ui.latex_source_preview.setPlainText(latex_source)

    @QtCore.Slot()
    def select_all_latex_sections(self) -> None:
        """
        Select every non-empty block equation section for PDF export.

        :return: None.
        """
        previous_signal_state: bool = self.ui.latex_selection_tree.blockSignals(True)
        root_index: int
        for root_index in range(self.ui.latex_selection_tree.topLevelItemCount()):
            root_item: QtWidgets.QTreeWidgetItem = self.ui.latex_selection_tree.topLevelItem(root_index)
            self._set_latex_block_sections_check_state(root_item, Qt.CheckState.Checked)
            self._synchronize_latex_block_check_state(root_item)
        self.ui.latex_selection_tree.blockSignals(previous_signal_state)
        self.refresh_latex_source_preview()

    @QtCore.Slot()
    def clear_latex_sections(self) -> None:
        """
        Clear every equation-section PDF selection.

        :return: None.
        """
        previous_signal_state: bool = self.ui.latex_selection_tree.blockSignals(True)
        root_index: int
        for root_index in range(self.ui.latex_selection_tree.topLevelItemCount()):
            root_item: QtWidgets.QTreeWidgetItem = self.ui.latex_selection_tree.topLevelItem(root_index)
            self._set_latex_block_sections_check_state(root_item, Qt.CheckState.Unchecked)
            self._synchronize_latex_block_check_state(root_item)
        self.ui.latex_selection_tree.blockSignals(previous_signal_state)
        self.refresh_latex_source_preview()

    def _parse_all_equation_buffers_for_export(self) -> List[BlockEquationDraft]:
        """Parse every equation buffer before creating a PDF.

        :return: Drafts aligned with ``self._equation_buffers``.
        :raises ValueError: If any buffer contains invalid DAE code.
        """
        validation_namespace: Dict[str, Expr] = self._build_joint_validation_namespace()
        drafts: List[BlockEquationDraft] = list()
        buffer: BlockCodeBuffer
        for buffer in self._equation_buffers:
            draft: BlockEquationDraft = parse_equation_code(buffer.get_code(), validation_namespace)
            self._validate_equation_variable_counts(buffer.get_block(), draft)
            drafts.append(draft)
        return drafts

    def _build_selected_equation_entries(self,
                                         drafts: Sequence[BlockEquationDraft]) -> List[EquationExportEntry]:
        """Build ordered entries for every checked block/section pair.

        :param drafts: Parsed drafts aligned with the dialogue equation buffers.
        :return: Selected PDF entries.
        """
        entries: List[EquationExportEntry] = list()
        root_index: int
        for root_index in range(self.ui.latex_selection_tree.topLevelItemCount()):
            root_item: QtWidgets.QTreeWidgetItem = self.ui.latex_selection_tree.topLevelItem(root_index)
            child_index: int
            for child_index in range(root_item.childCount()):
                child_item: QtWidgets.QTreeWidgetItem = root_item.child(child_index)
                if child_item.checkState(0) == Qt.CheckState.Checked:
                    buffer_value: object = child_item.data(0, Qt.ItemDataRole.UserRole)
                    section_value: object = child_item.data(0, Qt.ItemDataRole.UserRole + 1)
                    if isinstance(buffer_value, int) and isinstance(section_value, str):
                        buffer: BlockCodeBuffer = self._equation_buffers[buffer_value]
                        owner_block: Block = buffer.get_block()
                        draft: BlockEquationDraft = drafts[buffer_value]
                        section: EquationExportSection = EquationExportSection(section_value)
                        entries.extend(self._build_section_entries(owner_block, section, draft))
                    else:
                        pass
                else:
                    pass
        return entries

    def _build_section_entries(self,
                               owner_block: Block,
                               section: EquationExportSection,
                               draft: BlockEquationDraft) -> List[EquationExportEntry]:
        """Convert one selected parsed section into PDF entries.

        :param owner_block: Internal block owning the equations and differential variables.
        :param section: Selected equation section.
        :param draft: Parsed equations for the owner.
        :return: Ordered PDF entries for the section.
        """
        if section == EquationExportSection.STATE:
            state_differential_variables: List[Var | None] = (
                order_state_differential_variables(
                    owner_block.state_vars,
                    owner_block.diff_vars,
                )
            )
            result: List[EquationExportEntry] = build_state_equation_entries(
                owner_block.name,
                draft.get_state_eqs(),
                state_differential_variables,
            )
        elif section == EquationExportSection.ALGEBRAIC:
            residual_expressions: List[Expr] = list(draft.get_algebraic_eqs())
            result = build_list_equation_entries(
                owner_block.name,
                section,
                residual_expressions,
            )
        elif section == EquationExportSection.INITIALIZATION:
            result = build_mapping_equation_entries(
                owner_block.name,
                section,
                draft.get_init_eqs(),
            )
        else:
            result = build_mapping_equation_entries(
                owner_block.name,
                section,
                draft.get_diff_init_eqs(),
            )
        return result

    @QtCore.Slot()
    def export_rendered_equations_pdf(self) -> None:
        """Validate selected equations and export rendered mathematical notation.

        :return: None.
        """
        try:
            drafts: List[BlockEquationDraft] = self._parse_all_equation_buffers_for_export()
        except (TypeError, ValueError) as error:
            self._show_validation_error(str(error))
            return

        entries: List[EquationExportEntry] = self._build_selected_equation_entries(drafts)
        if len(entries) == 0:
            self._show_validation_error(self.tr("Select at least one non-empty equation group."))
            return
        else:
            pass

        suggested_name: str = build_equation_pdf_suggested_name(self._block.name)
        selected_path: str
        selected_filter: str
        selected_path, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            self.tr("Save dynamic equations PDF"),
            suggested_name,
            self.tr("PDF documents (*.pdf)"),
        )
        _unused_selected_filter: str = selected_filter
        if len(selected_path) == 0:
            return
        elif not selected_path.lower().endswith(".pdf"):
            selected_path = f"{selected_path}.pdf"
        else:
            pass

        try:
            write_equation_pdf(
                file_path=selected_path,
                root_block_name=self._block.name,
                entries=entries,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            self._show_validation_error(
                self.tr("The PDF could not be created: {message}").format(message=str(error))
            )
        else:
            self.toast_manager.show_info_toast(
                self.tr("Equation PDF created: {path}").format(path=selected_path),
            )

    @QtCore.Slot(QtCore.QModelIndex, QtCore.QModelIndex, list)
    def on_symbol_draft_changed(self,
                                top_left: QtCore.QModelIndex,
                                bottom_right: QtCore.QModelIndex,
                                roles: List[int]) -> None:
        """
        Rebuild editing names after an editable symbol cell changes.

        :param top_left: Value supplied for ``top_left``.
        :param bottom_right: Value supplied for ``bottom_right``.
        :param roles: Value supplied for ``roles``.
        :return: None.
        """
        _unused_top_left: QtCore.QModelIndex = top_left
        _unused_bottom_right: QtCore.QModelIndex = bottom_right
        _unused_roles: List[int] = roles
        if self._loading_equation_buffer:
            # Internal rename refreshes repaint the property tree before the
            # renamed DAE source is loaded. Its caller performs one complete
            # language-context refresh after installing that source.
            pass
        else:
            # A cell edit is a draft operation. Keep language assistance in
            # sync without rejecting the edit because another code section is
            # temporarily incomplete.
            self._namespace = self._build_staged_editing_namespace()
            self._refresh_dae_language_context()
            self._clear_dae_validation_feedback()

    @QtCore.Slot(QtCore.QModelIndex, QtCore.QModelIndex, list)
    def on_retained_mode_draft_changed(
            self,
            top_left: QtCore.QModelIndex,
            bottom_right: QtCore.QModelIndex,
            roles: List[int],
    ) -> None:
        """Project an inline retained-mode name edit back into its owner buffer.

        :param top_left: First changed retained-mode source index.
        :param bottom_right: Last changed retained-mode source index.
        :param roles: Qt roles changed by the inline editor.
        :return: None.
        """
        _unused_bottom_right: QtCore.QModelIndex = bottom_right
        _unused_roles: List[int] = roles
        mode: RuntimeModeDraft | None = self._retained_mode_model.get_row(top_left.row())
        if mode is None or self._loading_equation_buffer or top_left.column() != 0:
            pass
        else:
            synchronized: bool = self._synchronize_retained_mode_owner_source(
                mode.get_owner()
            )
            if synchronized:
                self._namespace = self._build_staged_editing_namespace()
                self._refresh_dae_language_context()
                self._clear_dae_validation_feedback()
            else:
                pass

    @QtCore.Slot(object, str, str)
    def on_retained_mode_name_changed(self,
                                      owner_object: object,
                                      old_name: str,
                                      new_name: str) -> None:
        """Rename retained-mode references throughout every staged code buffer.

        Retained modes share the recursive model namespace, so equations or
        procedural entries owned by another internal block may consume them.
        Token-aware replacement keeps all those staged references aligned while
        the Engine identities remain untouched until Apply.

        :param owner_object: Direct mode owner emitted by the source model.
        :param old_name: Previous retained-mode identifier.
        :param new_name: Accepted retained-mode identifier.
        :return: None.
        """
        if not isinstance(owner_object, Block) or old_name == new_name:
            pass
        else:
            buffer_index: int
            buffer: BlockCodeBuffer
            for buffer_index, buffer in enumerate(self._equation_buffers):
                updated_code: str = replace_dae_identifier(
                    buffer.get_code(),
                    old_name,
                    new_name,
                )
                buffer.set_code(updated_code)
                if buffer_index == self._active_equation_buffer_index:
                    self._loading_equation_buffer = True
                    self._dae_editor.setPlainText(updated_code)
                    self._loading_equation_buffer = False
                else:
                    pass

    def _synchronize_retained_mode_owner_source(self, owner: Block) -> bool:
        """Write active retained-mode drafts into one owner's code buffer.

        :param owner: Direct block whose mode dictionary changed.
        :return: Whether the source buffer was synchronized.
        """
        target_index: int = self._find_equation_buffer_index(owner)
        if target_index < 0:
            self._show_validation_error(
                self.tr("The retained mode owner has no Python-code buffer.")
            )
            result: bool = False
        else:
            target_buffer: BlockCodeBuffer = self._equation_buffers[target_index]
            try:
                updated_code: str = synchronize_retained_mode_source(
                    code=target_buffer.get_code(),
                    owner=owner,
                    modes=self._runtime_logic_drafts.get_active_modes(),
                )
            except (TypeError, ValueError) as error:
                self._show_validation_error(str(error))
                result = False
            else:
                target_buffer.set_code(updated_code)
                if target_index == self._active_equation_buffer_index:
                    self._loading_equation_buffer = True
                    self._dae_editor.setPlainText(updated_code)
                    self._loading_equation_buffer = False
                else:
                    pass
                self.refresh_draft_state()
                result = True
        return result

    def _find_equation_buffer_index(self, owner: Block) -> int:
        """Find the Python-code buffer belonging to one direct block owner.

        Every recursive block normally owns exactly one buffer. Centralizing
        this identity lookup keeps all add, delete, and synchronization paths
        consistent when a structural rebuild replaces child objects.

        :param owner: Direct block whose buffer is requested.
        :return: Buffer index, or ``-1`` when the owner is no longer present.
        """
        result: int = -1
        buffer_index: int
        buffer: BlockCodeBuffer
        for buffer_index, buffer in enumerate(self._equation_buffers):
            if buffer.get_block() is owner:
                result = buffer_index
            else:
                pass
        return result

    def _build_runtime_logic_drafts_from_buffers(self) -> RuntimeLogicDraftCollection:
        """Parse retained modes and procedural entries from every owner buffer.

        :return: Detached recursive runtime draft collection.
        """
        owner_code: List[tuple[Block, str]] = list()
        buffer: BlockCodeBuffer
        for buffer in self._equation_buffers:
            owner_code.append((buffer.get_block(), buffer.get_code()))
        return build_runtime_logic_drafts_from_code(
            root=self._block,
            owner_code=owner_code,
        )

    def _build_joint_validation_namespace(self) -> Dict[str, Expr]:
        """Build the staged DAE namespace including retained runtime modes.

        :return: Namespace shared by DAE code and procedural expressions.
        """
        symbol_namespace: Dict[str, Expr] = self._symbol_model.build_validation_namespace(
            build_block_symbol_namespace(self._block)
        )
        self._runtime_logic_drafts = self._build_runtime_logic_drafts_from_buffers()
        self._retained_mode_model.reload(self._runtime_logic_drafts)
        return self._runtime_logic_drafts.build_validation_namespace(symbol_namespace)

    def _build_staged_editing_namespace(self) -> Dict[str, Expr]:
        """Build language assistance from staged symbols without model validation.

        The detached runtime collection is intentionally not rebuilt from the
        source buffers here. Python code may contain placeholders while the
        user adds the retained modes, variables, or parameters that will replace
        them. Validate model and Apply changes perform the authoritative parse.

        :return: Permissive namespace used by completion and highlighting.
        """
        symbol_namespace: Dict[str, Expr] = self._symbol_model.build_editing_namespace(
            build_block_symbol_namespace(self._block)
        )
        return self._runtime_logic_drafts.build_validation_namespace(symbol_namespace)

    def _refresh_dae_language_context(self) -> None:
        """Synchronize parser, completer, and highlighter after draft changes.

        :return: None.
        """
        active_buffer: BlockCodeBuffer = self._equation_buffers[
            self._active_equation_buffer_index
        ]
        retained_mode_names: List[str] = list()
        runtime_mode: RuntimeModeDraft
        for runtime_mode in self._runtime_logic_drafts.get_active_modes():
            retained_mode_names.append(runtime_mode.get_name())
        language_context: DaeLanguageContext = build_dialogue_dae_language_context(
            namespace=self._namespace,
            symbol_model=self._symbol_model,
            root_block=self._block,
            equation_owner=active_buffer.get_block(),
            retained_mode_names=retained_mode_names,
        )
        self._dae_editor.set_language_context(language_context)

    def _stage_add_symbol_selection(self, selection: AddSymbolSelection) -> None:
        """Project one accepted add-property request into the detached models.

        :param selection: Typed values collected by the focused child dialog.
        :return: None.
        """
        owner: Block = selection.get_owner()
        name: str = selection.get_name()
        kind: BlockSymbolKind = selection.get_kind()
        if kind == BlockSymbolKind.MODE_PARAMETER:
            self._insert_retained_mode(owner=owner, name=name)
        else:
            external_reference: VarPowerFlowReferenceType | None = selection.get_external_reference()
            creates_derivative: bool = selection.creates_derivative()
            self._symbol_model.add_symbol(
                owner=owner,
                name=name,
                kind=kind,
                exported=selection.is_exported(),
                value=selection.get_value(),
                create_derivative=creates_derivative,
                external_reference=external_reference,
                static_reference=selection.get_static_reference(),
            )
            # Declaration insertion remains permissive while procedural code
            # contains placeholders; full semantic validation occurs on Apply.
            self._namespace = self._build_staged_editing_namespace()
            self._synchronize_dae_variable_declarations_for_block(owner)
            initialization_inserted: bool = self._insert_default_initialization_for_new_symbol(
                owner=owner,
                name=name,
                kind=kind,
                external_reference=external_reference,
                creates_derivative=creates_derivative,
            )
            self._refresh_dae_language_context()
            if initialization_inserted:
                self._clear_dae_validation_feedback()
            else:
                pass

    def _insert_default_initialization_for_new_symbol(
            self,
            owner: Block,
            name: str,
            kind: BlockSymbolKind,
            external_reference: VarPowerFlowReferenceType | None,
            creates_derivative: bool,
    ) -> bool:
        """Insert deterministic initialization entries for a new variable.

        Inputs are supplied by their graphical connection, parameters own their
        value dictionaries, and power-flow variables already have an external
        initialization source. Block-owned algebraic/state variables receive a
        zero initial expression; a requested derivative receives its own zero
        derivative initialization.

        :param owner: Direct block receiving the staged symbol.
        :param name: New variable identifier.
        :param kind: Primary staged variable role.
        :param external_reference: Optional power-flow initialization source.
        :param creates_derivative: Whether a state also created ``d_<name>``.
        :return: Whether the owner source remained synchronized.
        """
        target_index: int = self._find_equation_buffer_index(owner)
        if target_index < 0:
            self._show_validation_error(
                self.tr("The selected owner has no Python-code buffer.")
            )
            result: bool = False
        else:
            target_buffer: BlockCodeBuffer = self._equation_buffers[target_index]
            updated_code: str = target_buffer.get_code()
            owns_initial_expression: bool = kind in (
                BlockSymbolKind.STATE,
                BlockSymbolKind.ALGEBRAIC,
                BlockSymbolKind.OUTPUT_ONLY,
            )
            try:
                if owns_initial_expression and external_reference is None:
                    updated_code = insert_source_before_section_closing_line(
                        code=updated_code,
                        section_name="init_eqs",
                        insertion_lines=list((f"    {name}: 0.0,",)),
                    )
                else:
                    pass
                if kind == BlockSymbolKind.STATE and creates_derivative:
                    updated_code = insert_source_before_section_closing_line(
                        code=updated_code,
                        section_name="diff_init_eqs",
                        insertion_lines=list((f"    d_{name}: 0.0,",)),
                    )
                else:
                    pass
            except (TypeError, ValueError) as error:
                self._show_validation_error(str(error))
                result = False
            else:
                target_buffer.set_code(updated_code)
                if target_index == self._active_equation_buffer_index:
                    self._loading_equation_buffer = True
                    self._dae_editor.setPlainText(updated_code)
                    self._loading_equation_buffer = False
                else:
                    pass
                self.refresh_draft_state()
                result = True
        return result

    def _remove_initialization_for_deleted_symbol(self,
                                                  owner: Block,
                                                  name: str,
                                                  kind: BlockSymbolKind,
                                                  associated_derivative_names: Sequence[str]) -> bool:
        """Remove initialization entries that cannot survive a symbol deletion.

        :param owner: Direct block losing the staged symbol.
        :param name: Deleted symbol identifier.
        :param kind: Deleted symbol's primary DAE role.
        :param associated_derivative_names: Derivatives removed with a state.
        :return: Whether the owner's code buffer remained synchronized.
        """
        target_index: int = self._find_equation_buffer_index(owner)
        if target_index < 0:
            self._show_validation_error(
                self.tr("The selected owner has no Python-code buffer.")
            )
            result: bool = False
        else:
            target_buffer: BlockCodeBuffer = self._equation_buffers[target_index]
            updated_code: str = target_buffer.get_code()
            ordinary_names: List[str] = list()
            derivative_names: List[str] = list()
            if kind in (
                    BlockSymbolKind.STATE,
                    BlockSymbolKind.ALGEBRAIC,
                    BlockSymbolKind.OUTPUT_ONLY):
                ordinary_names.append(name)
            else:
                pass
            if kind == BlockSymbolKind.STATE:
                derivative_names.extend(associated_derivative_names)
            elif kind == BlockSymbolKind.DIFFERENTIAL:
                derivative_names.append(name)
            else:
                pass
            try:
                updated_code = remove_source_dictionary_entries(
                    code=updated_code,
                    section_name="init_eqs",
                    entry_names=ordinary_names,
                )
                updated_code = remove_source_dictionary_entries(
                    code=updated_code,
                    section_name="diff_init_eqs",
                    entry_names=derivative_names,
                )
            except (TypeError, ValueError) as error:
                self._show_validation_error(str(error))
                result = False
            else:
                target_buffer.set_code(updated_code)
                if target_index == self._active_equation_buffer_index:
                    self._loading_equation_buffer = True
                    self._dae_editor.setPlainText(updated_code)
                    self._loading_equation_buffer = False
                else:
                    pass
                self.refresh_draft_state()
                result = True
        return result

    def _insert_retained_mode(
            self,
            owner: Block,
            name: str,
    ) -> bool:
        """Insert a zero-initialized retained mode into its owner's source.

        :param owner: Direct block owner selected in the add-symbol form.
        :param name: New retained-mode identifier.
        :return: ``True`` when the retained mode was staged successfully.
        """
        initial_expression: str = "0.0"
        target_index: int = self._find_equation_buffer_index(owner)
        if target_index < 0:
            self._show_validation_error(self.tr("The selected owner has no Python-code buffer."))
            result: bool = False
        else:
            target_buffer: BlockCodeBuffer = self._equation_buffers[target_index]
            previous_code: str = target_buffer.get_code()
            try:
                updated_code: str = insert_source_before_section_closing_line(
                    code=previous_code,
                    section_name="retained_modes",
                    insertion_lines=list((f"    {name}: {initial_expression},",)),
                )
            except (TypeError, ValueError) as error:
                self._show_validation_error(str(error))
                result = False
            else:
                # Stage the declaration both in source and in the lightweight
                # runtime collection. Do not parse unrelated procedural entries:
                # they may intentionally remain incomplete until this mode exists.
                target_buffer.set_code(updated_code)
                self._runtime_logic_drafts.add_mode(
                    owner=owner,
                    name=name,
                    initial_expression=initial_expression,
                )
                self._retained_mode_model.reload(self._runtime_logic_drafts)
                self._namespace = self._build_staged_editing_namespace()
                if target_index == self._active_equation_buffer_index:
                    self._loading_equation_buffer = True
                    self._dae_editor.setPlainText(updated_code)
                    self._loading_equation_buffer = False
                else:
                    # The retained mode belongs to the selected add-symbol owner.
                    # Show that owner's buffer immediately so the new dictionary
                    # entry is visible instead of leaving an unrelated owner in the
                    # Python editor and making the successful insertion look lost.
                    self.ui.equation_owner_combo.setCurrentIndex(target_index)
                self._refresh_dae_language_context()
                self._clear_dae_validation_feedback()
                self._select_retained_mode_in_tree(owner, name)
                self.refresh_draft_state()
                result = True
        return result

    @QtCore.Slot(QtGui.QAction)
    def insert_procedural_logic(self, action: QtGui.QAction) -> None:
        """Insert a complete typed procedural skeleton into the active owner.

        :param action: Menu action carrying the selected procedural type.
        :return: None.
        """
        selected_data: object = action.data()
        editable_types: set[ProceduralLogicType] = set()
        descriptor: ProceduralBlockTemplateDescriptor
        for descriptor in get_dynamic_library_procedural_descriptors():
            editable_types.add(descriptor.logic_tpe)
        if (
                not isinstance(selected_data, ProceduralLogicType)
                or selected_data not in editable_types
        ):
            self._show_validation_error(self.tr("Select a valid procedural logic type."))
            return
        else:
            active_buffer: BlockCodeBuffer = self._equation_buffers[
                self._active_equation_buffer_index
            ]
            relative_lines: List[str]
            first_placeholder: str | None
            relative_lines, first_placeholder = build_procedural_logic_call_lines(
                selected_data
            )
            snippet_lines: List[str] = list()
            relative_line: str
            for relative_line in relative_lines:
                snippet_lines.append(f"    {relative_line}")
        try:
            updated_code: str = insert_source_before_section_closing_line(
                code=active_buffer.get_code(),
                section_name="procedural_logic",
                insertion_lines=snippet_lines,
            )
        except ValueError as error:
            self._show_validation_error(str(error))
        else:
            active_buffer.set_code(updated_code)
            self._loading_equation_buffer = True
            self._dae_editor.setPlainText(updated_code)
            self._loading_equation_buffer = False
            # Place the caret at the first required reference or text value so
            # insertion naturally continues as an edit instead of jumping to
            # the beginning of a potentially long model source.
            inserted_source: str = "\n".join(snippet_lines)
            inserted_start: int = updated_code.rfind(inserted_source)
            if first_placeholder is not None and inserted_start >= 0:
                placeholder_start: int = updated_code.find(
                    first_placeholder,
                    inserted_start,
                )
            else:
                placeholder_start = -1
            cursor: QtGui.QTextCursor = self._dae_editor.textCursor()
            if placeholder_start >= 0 and first_placeholder is not None:
                cursor.setPosition(placeholder_start)
                cursor.setPosition(
                    placeholder_start + len(first_placeholder),
                    QtGui.QTextCursor.MoveMode.KeepAnchor,
                )
            elif inserted_start >= 0:
                cursor.setPosition(inserted_start)
            else:
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            self._dae_editor.setTextCursor(cursor)
            self._dae_editor.setFocus()
            self._clear_dae_validation_feedback()
            self.refresh_draft_state()

    def _synchronize_dae_variable_declarations_for_block(self, owner: Block) -> None:
        """Project one owner's staged variable order into its DAE buffer.

        :param owner: Block whose Variables-table rows changed.
        :return: None.
        """
        state_names: List[str] = self._symbol_model.get_role_names(
            owner,
            BlockSymbolKind.STATE,
        )
        algebraic_names: List[str] = self._symbol_model.get_role_names(
            owner,
            BlockSymbolKind.ALGEBRAIC,
        )
        differential_names: List[str] = self._symbol_model.get_role_names(
            owner,
            BlockSymbolKind.DIFFERENTIAL,
        )
        buffer_index: int = self._find_equation_buffer_index(owner)
        if buffer_index < 0:
            self._show_validation_error(
                self.tr("The selected owner has no Python-code buffer.")
            )
        else:
            equation_buffer: BlockCodeBuffer = self._equation_buffers[buffer_index]
            previous_code: str = equation_buffer.get_code()
            updated_code: str = synchronize_dae_variable_declarations(
                code=previous_code,
                state_names=state_names,
                algebraic_names=algebraic_names,
                differential_names=differential_names,
            )
            if updated_code != previous_code:
                equation_buffer.set_code(updated_code)
                if buffer_index == self._active_equation_buffer_index:
                    previous_cursor: QtGui.QTextCursor = self._dae_editor.textCursor()
                    previous_length: int = len(previous_code)
                    position_from_end: int = previous_length - previous_cursor.position()
                    anchor_from_end: int = previous_length - previous_cursor.anchor()
                    updated_length: int = len(updated_code)
                    updated_position: int = max(0, updated_length - position_from_end)
                    updated_anchor: int = max(0, updated_length - anchor_from_end)
                    self._loading_equation_buffer = True
                    self._dae_editor.setPlainText(updated_code)
                    self._loading_equation_buffer = False
                    restored_cursor: QtGui.QTextCursor = self._dae_editor.textCursor()
                    restored_cursor.setPosition(min(updated_anchor, updated_length))
                    restored_cursor.setPosition(
                        min(updated_position, updated_length),
                        QtGui.QTextCursor.MoveMode.KeepAnchor,
                    )
                    self._dae_editor.setTextCursor(restored_cursor)
                    self.update_dae_code_search(self.ui.dae_code_search.text())
                else:
                    pass
            else:
                pass
            self.refresh_draft_state()

    @QtCore.Slot(QtCore.QPoint)
    def show_symbol_context_menu(self, position: QtCore.QPoint) -> None:
        """
        Offer all property additions exclusively through the tree menu.

        The empty tree background remains actionable so a model without any
        current variables or parameters can still receive its first symbol.

        :param position: Click location in the property-tree viewport.
        :return: None.
        """
        self._show_symbol_context_menu(self.ui.property_tree, position)

    def _show_symbol_context_menu(self,
                                  table: QtWidgets.QAbstractItemView,
                                  position: QtCore.QPoint) -> None:
        """
        Offer additions everywhere and rename/delete only on property leaves.

        :param table: Property tree that received the context-menu request.
        :param position: Viewport-local click position.
        :return: None.
        """
        clicked_index: QtCore.QModelIndex = table.indexAt(position)
        source_row: BlockSymbolDraftRow | None = None
        source_mode: RuntimeModeDraft | None = None
        owner: Block | None = self._block

        if clicked_index.isValid():
            table.setCurrentIndex(clicked_index)
            source_row = self._get_selected_symbol_row(table)
            source_mode = self._property_tree_model.retained_mode_row(clicked_index)

            # A leaf resolves its owner directly; an owner branch stores the
            # typed Block in a dedicated item role.
            if source_row is not None:
                owner = source_row.get_owner()
            elif source_mode is not None:
                owner = source_mode.get_owner()
            else:
                branch_index: QtCore.QModelIndex = clicked_index.siblingAtColumn(0)
                branch_owner: object = branch_index.data(Qt.ItemDataRole.UserRole + 1)
                if isinstance(branch_owner, Block):
                    owner = branch_owner
                else:
                    pass
        else:
            pass

        menu: QtWidgets.QMenu = QtWidgets.QMenu(parent=table)
        add_variable_action: QtGui.QAction = gf.add_menu_entry(
            menu=menu,
            text=self.tr("Add variable..."),
            icon_path=":/Icons/icons/plus.png",
        )
        add_parameter_action: QtGui.QAction = gf.add_menu_entry(
            menu=menu,
            text=self.tr("Add parameter..."),
            icon_path=":/Icons/icons/plus.png",
        )
        add_retained_mode_action: QtGui.QAction = gf.add_menu_entry(
            menu=menu,
            text=self.tr("Add retained mode..."),
            icon_path=":/Icons/icons/dyn_add.png",
        )
        menu.addSeparator()

        add_to_plot_action: QtGui.QAction | None
        rename_action: QtGui.QAction | None
        delete_action: QtGui.QAction | None
        if source_row is not None:
            selected_variable: Var | None = source_row.get_variable()
            add_to_plot_action = gf.add_menu_entry(
                menu=menu,
                text=self.tr("Add to plot..."),
                icon_path=":/Icons/icons/rms_plots.png",
            )
            add_to_plot_action.setEnabled(selected_variable is not None)
            if selected_variable is None:
                add_to_plot_action.setToolTip(
                    self.tr("Apply the new symbol before adding it to a plot")
                )
            else:
                pass
            menu.addSeparator()
        else:
            add_to_plot_action = None

        if source_row is not None or source_mode is not None:
            rename_action = gf.add_menu_entry(
                menu=menu,
                text=self.tr("Rename"),
                icon_path=":/Icons/icons/edit.png",
            )
            delete_action = gf.add_menu_entry(
                menu=menu,
                text=self.tr("Delete"),
                icon_path=":/Icons/icons/delete.png",
            )
        else:
            rename_action = None
            delete_action = None

        selected_action: QtGui.QAction | None = menu.exec(
            table.viewport().mapToGlobal(position)
        )
        if selected_action is add_variable_action:
            self.show_add_symbol_dialog(BlockSymbolCategory.VARIABLES, owner)
        elif selected_action is add_parameter_action:
            self.show_add_symbol_dialog(BlockSymbolCategory.PARAMETERS, owner)
        elif selected_action is add_retained_mode_action:
            self.show_add_symbol_dialog(BlockSymbolCategory.RETAINED_MODES, owner)
        elif add_to_plot_action is not None and selected_action is add_to_plot_action:
            selected_variable = source_row.get_variable() if source_row is not None else None
            if selected_variable is not None and source_row is not None:
                global_position: QtCore.QPoint = table.viewport().mapToGlobal(position)
                self.addToPlotRequested.emit(
                    selected_variable,
                    source_row.get_kind(),
                    global_position,
                )
            else:
                pass
        elif rename_action is not None and selected_action is rename_action:
            self.rename_property_symbol()
        elif delete_action is not None and selected_action is delete_action:
            self._delete_selected_symbol(table)
        else:
            pass

    def _get_selected_symbol_row(self,
                                 table: QtWidgets.QAbstractItemView) -> BlockSymbolDraftRow | None:
        """Resolve the single selected proxy row to its symbol draft.

        :param table: Variable or parameter table containing the selection.
        :return: Selected source row, or ``None`` without one valid selection.
        """
        selection_model: QtCore.QItemSelectionModel | None = table.selectionModel()
        if selection_model is None:
            return None
        else:
            selected_rows: List[QtCore.QModelIndex] = selection_model.selectedRows()
        if len(selected_rows) != 1:
            return None
        else:
            pass
        proxy_model: QtCore.QAbstractItemModel | None = table.model()
        if isinstance(proxy_model, BlockPropertyTreeModel):
            return proxy_model.symbol_row(selected_rows[0])
        else:
            return None

    @QtCore.Slot(object)
    def on_existing_symbol_name_change_requested(self, request: object) -> None:
        """Apply one inline existing-symbol rename through the central editor.

        The property table owns only detached drafts. Existing variables can
        also be connected to aliases in other internal blocks, so the central
        Dynamic Editor remains the single owner of the complete rename.

        :param request: Synchronous rename request created by the tree model.
        :return: None.
        """
        if not isinstance(request, BlockVariableRenameRequest):
            return
        else:
            selected_variable: Var = request.get_variable()

        # Capture every row independently before the editor propagates the
        # alias component. Connected variables can share one stable UID while
        # still using different local names, so a UID-keyed dictionary would
        # lose all but the last old name and leave stale identifiers in DAE
        # source owned by the other connected blocks.
        old_names_by_row: List[tuple[BlockSymbolDraftRow, str]] = list()
        selected_old_name: str = selected_variable.name
        row_index: int
        for row_index in range(self._symbol_model.rowCount()):
            draft_row: BlockSymbolDraftRow | None = self._symbol_model.get_row(row_index)
            if draft_row is not None:
                draft_variable: Var | None = draft_row.get_variable()
            else:
                draft_variable = None
            if draft_variable is not None:
                old_names_by_row.append((draft_row, draft_variable.name))
            else:
                pass

        self.variableRenameRequested.emit(request)
        if request.is_successful():
            rename_pairs: List[tuple[str, str]] = list()
            selected_rename_pair: tuple[str, str] = (selected_old_name, request.get_new_name())
            if selected_old_name != request.get_new_name():
                rename_pairs.append(selected_rename_pair)
            else:
                pass

            old_name: str
            for draft_row, old_name in old_names_by_row:
                draft_variable = draft_row.get_variable()
                if draft_variable is not None:
                    if old_name != draft_variable.name:
                        rename_pair: tuple[str, str] = (old_name, draft_variable.name)
                        if rename_pair not in rename_pairs:
                            rename_pairs.append(rename_pair)
                        else:
                            pass
                    else:
                        pass
                else:
                    pass

            self._rename_detached_drafts(rename_pairs)
            self.toast_manager.show_info_toast(
                self.tr("Variable renamed to '{name}'.").format(name=request.get_new_name()),
            )
        else:
            pass

    @QtCore.Slot(str, str)
    def on_pending_symbol_renamed(self, old_name: str, new_name: str) -> None:
        """Synchronize names before a newly added symbol has an Engine identity.

        :param old_name: Previous pending identifier.
        :param new_name: New identifier accepted in the tree.
        :return: None.
        """
        self._rename_detached_drafts(list(((old_name, new_name),)))
        self._property_tree_model.refresh_values()

    def _rename_detached_drafts(self, rename_pairs: Sequence[tuple[str, str]]) -> None:
        """Keep code and parameter expressions aligned with complete renames.

        :param rename_pairs: All aliases changed by the editor or a pending row.
        :return: None.
        """
        equation_buffer: BlockCodeBuffer
        for equation_buffer in self._equation_buffers:
            old_name: str
            new_name: str
            for old_name, new_name in rename_pairs:
                equation_buffer.rename_identifier(old_name, new_name)

        self._parameter_model.rename_draft_identifiers(rename_pairs)
        row_index: int
        for row_index in range(self._symbol_model.rowCount()):
            pending_row: BlockSymbolDraftRow | None = self._symbol_model.get_row(row_index)
            if pending_row is not None and pending_row.is_new():
                pending_text: str = pending_row.get_value_text()
                for old_name, new_name in rename_pairs:
                    pending_text = replace_dae_identifier(pending_text, old_name, new_name)
                pending_row.set_value_text(pending_text)
            else:
                pass
        # Load the renamed source before rehighlighting it. Rehighlighting
        # can emit a document change; while the editor still showed the
        # old source, that signal wrote the stale text back over the newly
        # updated active buffer.
        self._loading_equation_buffer = True
        self._symbol_model.refresh_existing_names()
        self._namespace = self._build_staged_editing_namespace()
        active_buffer: BlockCodeBuffer = self._equation_buffers[self._active_equation_buffer_index]
        self._dae_editor.setPlainText(active_buffer.get_code())
        self._refresh_dae_language_context()
        self._loading_equation_buffer = False
        self._clear_dae_validation_feedback()
        self.refresh_draft_state()

    def _delete_selected_symbol(self, table: QtWidgets.QAbstractItemView) -> None:
        """Stage deletion of the single selected proxy row.

        :param table: Table containing the selected row.
        :return: None.
        """
        selection_model: QtCore.QItemSelectionModel | None = table.selectionModel()
        if selection_model is None:
            return
        else:
            selected_rows: List[QtCore.QModelIndex] = selection_model.selectedRows()
        if len(selected_rows) != 1:
            return
        else:
            pass
        proxy_model: QtCore.QAbstractItemModel | None = table.model()
        removed_owner: Block | None = None
        removed_mode_owner: Block | None = None
        removed_name: str = ""
        removed_kind: BlockSymbolKind | None = None
        removed_derivative_names: List[str] = list()
        removal_message: str = ""
        if isinstance(proxy_model, BlockPropertyTreeModel):
            source_index: QtCore.QModelIndex = proxy_model.source_index(selected_rows[0])
            if source_index.model() is self._retained_mode_model:
                selected_mode: RuntimeModeDraft | None = self._retained_mode_model.get_row(
                    source_index.row()
                )
                if selected_mode is not None:
                    removed_mode_owner = selected_mode.get_owner()
                else:
                    pass
                removed: bool
                removed, removal_message = self._retained_mode_model.remove_mode(
                    source_index.row()
                )
            else:
                selected_row: BlockSymbolDraftRow | None = self._symbol_model.get_row(
                    source_index.row()
                )
                if selected_row is not None:
                    removed_owner = selected_row.get_owner()
                    removed_name = selected_row.get_name()
                    removed_kind = selected_row.get_kind()
                    if removed_kind == BlockSymbolKind.STATE:
                        selected_variable: Var | None = selected_row.get_variable()
                        candidate_index: int
                        for candidate_index in range(self._symbol_model.rowCount()):
                            candidate_row: BlockSymbolDraftRow | None = self._symbol_model.get_row(
                                candidate_index
                            )
                            if candidate_row is not None:
                                candidate_variable: Var | None = candidate_row.get_variable()
                                staged_derivative: bool = (
                                    candidate_row.get_kind() == BlockSymbolKind.DIFFERENTIAL
                                    and candidate_row.get_derivative_base_row() is selected_row
                                )
                                existing_derivative: bool = (
                                    candidate_row.get_kind() == BlockSymbolKind.DIFFERENTIAL
                                    and selected_variable is not None
                                    and candidate_variable is not None
                                    and candidate_variable.base_var is selected_variable
                                )
                                if staged_derivative or existing_derivative:
                                    removed_derivative_names.append(candidate_row.get_name())
                                else:
                                    pass
                            else:
                                pass
                    else:
                        pass
                else:
                    pass
                removed = self._symbol_model.remove_symbol(source_index.row())
        else:
            removed = False
        if removed:
            if removed_mode_owner is not None:
                synchronized: bool = self._synchronize_retained_mode_owner_source(
                    removed_mode_owner
                )
            elif removed_owner is not None:
                self._synchronize_dae_variable_declarations_for_block(removed_owner)
                if removed_kind is not None:
                    synchronized = self._remove_initialization_for_deleted_symbol(
                        owner=removed_owner,
                        name=removed_name,
                        kind=removed_kind,
                        associated_derivative_names=removed_derivative_names,
                    )
                else:
                    synchronized = False
            else:
                synchronized = False
            if synchronized:
                self._namespace = self._build_staged_editing_namespace()
                self._refresh_dae_language_context()
                self._clear_dae_validation_feedback()
            else:
                pass
        elif len(removal_message) > 0:
            self._show_validation_error(removal_message)
        else:
            pass

    @QtCore.Slot()
    def on_dae_code_changed(self) -> None:
        """
        Persist edits and clear stale diagnostics until Validate is pressed.

        :return: None.
        """
        if self._loading_equation_buffer:
            pass
        else:
            active_buffer: BlockCodeBuffer = self._equation_buffers[self._active_equation_buffer_index]
            active_buffer.set_code(self._dae_editor.toPlainText())
            # A source preview must never present LaTeX generated from an older
            # equation draft. It is rebuilt from the new text when the user
            # changes the selection or validates the complete DAE model.
            self.ui.latex_source_preview.clear()
            self._clear_dae_validation_feedback()
            self.update_dae_code_search(self.ui.dae_code_search.text())
            self.refresh_draft_state()

    @QtCore.Slot(int)
    def on_equation_owner_changed(self, combo_index: int) -> None:
        """
        Switch source buffers without flattening equations across child blocks.

        :param combo_index: Value supplied for ``combo_index``.
        :return: None.
        """
        selected_data: object = self.ui.equation_owner_combo.itemData(combo_index)
        if isinstance(selected_data, int) and 0 <= selected_data < len(self._equation_buffers):
            self._active_equation_buffer_index = selected_data
            selected_buffer: BlockCodeBuffer = self._equation_buffers[selected_data]
            self._loading_equation_buffer = True
            self._dae_editor.setPlainText(selected_buffer.get_code())
            self._refresh_dae_language_context()
            self._loading_equation_buffer = False
            self._clear_dae_validation_feedback()
            self.update_dae_code_search(self.ui.dae_code_search.text())
        else:
            pass

    def validate_dae_code(self) -> bool:
        """
        Validate the active DAE buffer and show explicit inline feedback.

        :return: True when the active DAE code is valid; otherwise False.
        """
        active_buffer: BlockCodeBuffer = self._equation_buffers[self._active_equation_buffer_index]
        self._refresh_dae_language_context()
        code: str = self._dae_editor.toPlainText()
        diagnostics: List[DaeCodeDiagnostic] = self._dae_editor.build_current_diagnostics()
        if len(diagnostics) > 0:
            self._show_dae_validation_diagnostics(diagnostics)
            return False
        else:
            pass
        try:
            equation_draft: BlockEquationDraft = self._dae_editor.parse_current_code()
            self._validate_equation_variable_counts(active_buffer.get_block(), equation_draft)
        except (ValueError, TypeError) as error:
            diagnostic: DaeCodeDiagnostic = build_semantic_dae_diagnostic(code, str(error))
            self._show_dae_validation_diagnostics(list((diagnostic,)))
            return False
        else:
            self._dae_editor.set_diagnostics(list())
            self._show_dae_validation_message(self.tr("Model code is valid."), "color: #16825d;")
            self._rebuild_latex_selection_tree()
            return True

    @QtCore.Slot()
    def validate_complete_dae_code(self) -> None:
        """
        Validate every recursive equation buffer and focus its first inline error.

        :return: None.
        """
        runtime_warnings: List[str] = list()
        try:
            symbol_namespace: Dict[str, Expr] = self._symbol_model.build_validation_namespace(
                build_block_symbol_namespace(self._block)
            )
            self._runtime_logic_drafts = self._build_runtime_logic_drafts_from_buffers()
            self._retained_mode_model.reload(self._runtime_logic_drafts)
            runtime_validation: RuntimeLogicValidationResult = self._runtime_logic_drafts.validate(
                symbol_namespace
            )
            if not runtime_validation.is_valid():
                self._show_validation_error(runtime_validation.get_errors()[0])
                return
            else:
                runtime_warnings = runtime_validation.get_warnings()
                validation_namespace: Dict[str, Expr] = self._runtime_logic_drafts.build_validation_namespace(
                    symbol_namespace
                )
            pending_expressions: List[tuple[Block, Var, Expr]] = self._parameter_model.get_pending_event_expressions(
                validation_namespace
            )
            pending_expressions.extend(self._symbol_model.get_new_event_expressions(validation_namespace))
            validate_event_parameter_expression_dependencies(self._block, pending_expressions)
        except (ValueError, TypeError) as error:
            active_code: str = self._equation_buffers[
                self._active_equation_buffer_index
            ].get_code()
            source_diagnostics: List[DaeCodeDiagnostic] = build_dae_code_diagnostics(
                active_code,
                self._namespace,
            )
            if len(source_diagnostics) > 0:
                self._show_dae_validation_diagnostics(source_diagnostics)
            else:
                self._show_validation_error(str(error))
            return

        valid: bool = True
        invalid_index: int = -1
        invalid_message: str = ""
        buffer_index: int
        buffer: BlockCodeBuffer
        for buffer_index, buffer in enumerate(self._equation_buffers):
            if valid:
                buffer_code: str = buffer.get_code()
                diagnostics: List[DaeCodeDiagnostic] = build_dae_code_diagnostics(
                    buffer_code,
                    validation_namespace,
                )
                if len(diagnostics) > 0:
                    valid = False
                    invalid_index = buffer_index
                    invalid_message = diagnostics[0].get_message()
                else:
                    pass
            else:
                pass
            if valid:
                try:
                    equation_draft: BlockEquationDraft = parse_equation_code(
                        buffer_code,
                        validation_namespace,
                    )
                    self._validate_equation_variable_counts(buffer.get_block(), equation_draft)
                except (ValueError, TypeError) as error:
                    valid = False
                    invalid_index = buffer_index
                    invalid_message = str(error)
                else:
                    pass
            else:
                pass
        if valid:
            self._namespace = validation_namespace
            self._refresh_dae_language_context()
            active_valid: bool = self.validate_dae_code()
            if active_valid and len(runtime_warnings) > 0:
                self._show_dae_validation_message(
                    self.tr("Model is valid. Warning: {message}").format(
                        message=runtime_warnings[0]
                    ),
                    "color: #9a6700;",
                )
            else:
                pass
        else:
            if invalid_index != self._active_equation_buffer_index:
                self.ui.equation_owner_combo.setCurrentIndex(invalid_index)
            else:
                pass
            visible_code: str = self._equation_buffers[invalid_index].get_code()
            visible_diagnostics: List[DaeCodeDiagnostic] = build_dae_code_diagnostics(
                visible_code,
                validation_namespace,
            )
            if len(visible_diagnostics) == 0:
                visible_diagnostics.append(
                    build_semantic_dae_diagnostic(visible_code, invalid_message)
                )
            else:
                pass
            self._show_dae_validation_diagnostics(visible_diagnostics)

    def _validate_equation_variable_counts(self,
                                           block: Block,
                                           equation_draft: BlockEquationDraft) -> None:
        """Validate equation counts, declarations, and initialization owners.

        Output exposure is deliberately absent from this rule: checking or
        unchecking Output only changes the public interface and never changes a
        variable's DAE role or its equation. Initialization equations belong
        to state, algebraic, and direct output-only variables. Runtime event
        parameters store their scalar value or initialization expression
        directly in ``event_dict`` and therefore have exactly one source.

        :param block: Equation owner being validated.
        :param equation_draft: Parsed equations staged for that owner.
        :return: None.
        :raises ValueError: If a DAE variable/equation count is inconsistent.
        """
        state_count: int = self._symbol_model.get_role_count(block, BlockSymbolKind.STATE)
        algebraic_count: int = self._symbol_model.get_role_count(block, BlockSymbolKind.ALGEBRAIC)
        legacy_output_count: int = self._symbol_model.get_role_count(
            block,
            BlockSymbolKind.OUTPUT_ONLY,
        )
        state_equation_count: int = len(equation_draft.get_state_eqs())
        algebraic_equation_count: int = len(equation_draft.get_algebraic_eqs())
        initializable_names: set[str] = set(
            self._symbol_model.get_initializable_names(block)
        )
        initialized_variable: Var
        for initialized_variable in equation_draft.get_init_eqs():
            if initialized_variable.name in initializable_names:
                pass
            else:
                raise ValueError(
                    f"Variable '{initialized_variable.name}' is not state, "
                    "algebraic, or a direct output and cannot own an initialization equation. "
                    "Put an event parameter's initialization expression in "
                    "General options instead"
                )
        self._validate_variable_declaration(
            block=block,
            equation_draft=equation_draft,
            section_name="state_vars",
            kind=BlockSymbolKind.STATE,
        )
        self._validate_variable_declaration(
            block=block,
            equation_draft=equation_draft,
            section_name="algebraic_vars",
            kind=BlockSymbolKind.ALGEBRAIC,
        )
        self._validate_variable_declaration(
            block=block,
            equation_draft=equation_draft,
            section_name="diff_vars",
            kind=BlockSymbolKind.DIFFERENTIAL,
        )
        if state_count != state_equation_count:
            raise ValueError(
                f"Block '{block.name}' has {state_count} state variables but "
                f"{state_equation_count} state equations"
            )
        else:
            pass
        minimum_algebraic_equation_count: int = algebraic_count
        maximum_algebraic_equation_count: int = algebraic_count + legacy_output_count
        # Current blocks require one equation per algebraic variable. Older
        # files may additionally contain equation-backed variables represented
        # only in out_vars; accept at most one equation for each such legacy
        # output so users can repair and extend those models in the dialogue.
        if (algebraic_equation_count < minimum_algebraic_equation_count
                or algebraic_equation_count > maximum_algebraic_equation_count):
            raise ValueError(
                f"Block '{block.name}' has {algebraic_count} algebraic variables but "
                f"{algebraic_equation_count} algebraic equations; "
                f"{legacy_output_count} legacy outputs may own an additional equation"
            )
        else:
            pass

    def _validate_variable_declaration(self,
                                       block: Block,
                                       equation_draft: BlockEquationDraft,
                                       section_name: str,
                                       kind: BlockSymbolKind) -> None:
        """Require a present generated declaration to match the staged table order.

        Older hand-written buffers may omit the declaration for compatibility.
        When present, the declaration is an explicit ordering contract and must
        remain synchronized with symbol additions, removals, and reclassification.

        :param block: Block owning the declared variables.
        :param equation_draft: Parsed source containing optional declarations.
        :param section_name: Declaration section being checked.
        :param kind: Symbol-table role corresponding to the declaration.
        :return: None.
        :raises ValueError: If declared and staged names differ or are reordered.
        """
        declared_variables: List[Var] | None = equation_draft.get_variable_declaration(section_name)
        if declared_variables is None:
            return
        else:
            declared_names: List[str] = list()
            declared_variable: Var
            for declared_variable in declared_variables:
                declared_names.append(declared_variable.name)
            expected_names: List[str] = self._symbol_model.get_role_names(block, kind)

        if declared_names != expected_names:
            raise ValueError(
                f"Block '{block.name}' has {kind.value.lower()} variables ordered as "
                f"{expected_names}, but {section_name} declares {declared_names}"
            )
        else:
            pass

    @QtCore.Slot()
    def apply_changes(self) -> None:
        """
        Validate the complete draft and atomically apply it to the source block.

        :return: None.
        """
        if self._read_only:
            self.toast_manager.show_info_toast(
                self.tr("Manufacturer model bindings are read-only in Block Properties.")
            )
            return
        else:
            pass

        parsed_buffers: List[tuple[Block, BlockEquationDraft]] = list()
        pending_static_values: List[tuple[Const, float | complex]] = list()
        pending_event_expressions: List[tuple[Block, Var, Expr]] = list()
        try:
            symbol_namespace: Dict[str, Expr] = self._symbol_model.build_validation_namespace(
                build_block_symbol_namespace(self._block)
            )
            self._runtime_logic_drafts = self._build_runtime_logic_drafts_from_buffers()
            self._retained_mode_model.reload(self._runtime_logic_drafts)
            runtime_validation: RuntimeLogicValidationResult = self._runtime_logic_drafts.validate(
                symbol_namespace
            )
            if not runtime_validation.is_valid():
                self._show_validation_error(runtime_validation.get_errors()[0])
                return
            else:
                validation_namespace: Dict[str, Expr] = self._runtime_logic_drafts.build_validation_namespace(
                    symbol_namespace
                )
            pending_static_values = self._parameter_model.get_pending_static_values()
            pending_event_expressions = self._parameter_model.get_pending_event_expressions(
                validation_namespace
            )
            pending_event_expressions.extend(self._symbol_model.get_new_event_expressions(validation_namespace))
            validate_event_parameter_expression_dependencies(
                root_block=self._block,
                pending_expressions=pending_event_expressions,
            )
        except (ValueError, TypeError) as error:
            self._show_validation_error(str(error))
            return

        buffer_index: int
        buffer: BlockCodeBuffer
        for buffer_index, buffer in enumerate(self._equation_buffers):
            code: str = buffer.get_code()
            diagnostics: List[DaeCodeDiagnostic] = build_dae_code_diagnostics(
                code,
                validation_namespace,
            )
            if len(diagnostics) > 0:
                self._show_equation_buffer_diagnostics(buffer_index, diagnostics)
                return
            else:
                pass
            try:
                parsed_draft: BlockEquationDraft = parse_equation_code(code, validation_namespace)
                self._validate_equation_variable_counts(buffer.get_block(), parsed_draft)
            except (ValueError, TypeError) as error:
                semantic_diagnostic: DaeCodeDiagnostic = build_semantic_dae_diagnostic(
                    code,
                    str(error),
                )
                self._show_equation_buffer_diagnostics(
                    buffer_index,
                    list((semantic_diagnostic,)),
                )
                return
            else:
                parsed_buffers.append((buffer.get_block(), parsed_draft))

        structural_changes: bool = (
            self._general_structural_model.has_changes()
            or self._special_structural_model.has_changes()
        )
        has_new_symbols: bool = self._symbol_model.has_new_symbols()
        has_symbol_changes: bool = self._symbol_model.has_symbol_changes()
        has_mapping_changes: bool = self._symbol_model.has_mapping_changes()
        runtime_logic_changes: bool = False
        runtime_buffer: BlockCodeBuffer
        for runtime_buffer in self._equation_buffers:
            if runtime_buffer.has_runtime_changes():
                runtime_logic_changes = True
            else:
                pass
        has_new_modes: bool = self._runtime_logic_drafts.has_new_modes()
        output_export_changes: List[tuple[Block, Var, bool]] = self._symbol_model.get_output_export_changes()
        existing_symbol_removals: List[tuple[Block, Var]] = (
            self._symbol_model.get_existing_symbol_removals()
        )
        if structural_changes:
            changed_equations: bool = False
            equation_buffer: BlockCodeBuffer
            for equation_buffer in self._equation_buffers:
                if equation_buffer.has_changes():
                    changed_equations = True
                else:
                    pass
            if (
                    changed_equations
                    or has_symbol_changes
                    or has_mapping_changes
                    or runtime_logic_changes
                    or len(output_export_changes) > 0):
                self._show_validation_error(
                    self.tr(
                        "Apply structural settings separately from DAE-code or symbol-interface changes."
                    )
                )
                return
            elif self._structural_block_type is None or self._structural_builder is None:
                self._show_validation_error(self.tr("This block has no safe structural rebuild adapter."))
                return
            else:
                try:
                    named_parameter_values: List[tuple[str, float | complex]] = (
                        self._parameter_model.get_pending_named_values(validation_namespace)
                    )
                except (TypeError, ValueError) as error:
                    self._show_validation_error(str(error))
                    return
                rebuild_request: BlockStructuralEditRequest = BlockStructuralEditRequest(
                    block=self._block,
                    block_type=self._structural_block_type,
                    builder=self._structural_builder,
                    parameter_values=named_parameter_values,
                )
                self.structuralRebuildRequested.emit(rebuild_request)
            if rebuild_request.is_successful():
                self.blockApplied.emit(self._block.uid)
                self._refresh_after_apply(rebuilt_structure=True)
                self.toast_manager.show_info_toast(
                    self.tr("Block structure rebuilt with the selected settings."),
                )
                self.close()
                return
            else:
                self._show_validation_error(rebuild_request.get_error_message())
                return
        else:
            pass

        constant: Const
        numeric_value: float | complex
        for constant, numeric_value in pending_static_values:
            constant.value = numeric_value

        # Structural symbol changes are delayed until every text and numeric
        # field has passed validation. New Vars then become the authoritative
        # parser identities for the final equation trees.
        if len(output_export_changes) > 0:
            # The editor must detach existing arrows while the old port indexes
            # are still valid. The model mutation immediately follows the
            # synchronous signal delivery.
            self.outputExportChangesRequested.emit(output_export_changes)
        else:
            pass
        if len(existing_symbol_removals) > 0:
            # Interface wrappers are direct graphical children rather than
            # symbol rows. The host needs the original identities to remove
            # those projections before the owning port list is changed.
            self.symbolRemovalsRequested.emit(existing_symbol_removals)
        else:
            pass
        self._symbol_model.apply_to_blocks(self._var_factory)
        symbol_namespace: Dict[str, Expr] = build_block_symbol_namespace(self._block)
        if runtime_logic_changes:
            self._namespace = self._runtime_logic_drafts.apply_to_blocks(
                self._var_factory,
                symbol_namespace,
            )
        else:
            self._namespace = self._runtime_logic_drafts.build_validation_namespace(symbol_namespace)

        # Reparse changed event expressions after symbol application so their
        # trees bind to the authoritative VarFactory identities rather than any
        # detached variables used only for draft validation.
        pending_event_expressions = self._parameter_model.get_pending_event_expressions(
            self._namespace
        )
        validate_event_parameter_expression_dependencies(
            root_block=self._block,
            pending_expressions=pending_event_expressions,
        )
        event_owner: Block
        event_variable: Var
        event_expression: Expr
        for event_owner, event_variable, event_expression in pending_event_expressions:
            if event_variable in event_owner.event_dict:
                # An explicit value edit selects the local expression as the
                # initialization source. Remove any former device source so the
                # GUI cannot leave two competing initializers active.
                mapping_keys_to_remove: List[ParamPowerFlowReferenceType] = list()
                mapping_key: ParamPowerFlowReferenceType
                mapped_variable: Var | None
                for mapping_key, mapped_variable in event_owner.api_obj_mapping.items():
                    if mapped_variable is event_variable:
                        mapping_keys_to_remove.append(mapping_key)
                    else:
                        pass
                for mapping_key in mapping_keys_to_remove:
                    del event_owner.api_obj_mapping[mapping_key]
                event_owner.event_dict[event_variable] = event_expression
            else:
                pass
        if has_new_symbols or has_new_modes:
            # Newly created symbols replace their temporary validation Vars, so
            # parse once more against the authoritative factory identities.
            parsed_buffers.clear()
            for buffer in self._equation_buffers:
                final_draft: BlockEquationDraft = parse_equation_code(buffer.get_code(), self._namespace)
                parsed_buffers.append((buffer.get_block(), final_draft))
        else:
            # Connection removal can restore a variable's pre-alias name. The
            # already validated drafts retain the exact Var identities and avoid
            # reparsing now-stale display text after that legitimate rename.
            pass

        target_block: Block
        equation_draft: BlockEquationDraft
        for target_block, equation_draft in parsed_buffers:
            target_block.state_eqs = equation_draft.get_state_eqs()
            target_block.algebraic_eqs = equation_draft.get_algebraic_eqs()
            target_block.init_eqs = equation_draft.get_init_eqs()
            target_block.diff_init_eqs = equation_draft.get_diff_init_eqs()

        # The owning editor may repair aliases or expose additional interface
        # blocks while rebuilding its scene. Refresh only after that callback.
        self.blockApplied.emit(self._block.uid)
        self._refresh_after_apply(rebuilt_structure=False)
        if runtime_logic_changes:
            status_message: str = self.tr("DAE and runtime-logic changes applied to the editor working copy.")
        elif block_has_advanced_logic(self._block):
            status_message = self.tr(
                "Changes applied. Advanced inequalities/discrete/boolean logic was preserved unchanged."
            )
        else:
            status_message = self.tr("Changes applied to the editor working copy.")
        self.toast_manager.show_info_toast(status_message)
        self.close()

    def _reload_applied_models(self) -> None:
        """Reload property models and runtime drafts from the current block.

        Reusing the table models keeps the tree delegates and signals attached.
        Runtime drafts are recreated because structural edits can replace owners.

        :return: None.
        """
        general_properties: List[TemplateProp] = list()
        special_properties: List[TemplateProp] = list()
        if self._structural_builder is not None:
            general_properties, special_properties = split_structural_template_properties(self._structural_builder)
        else:
            pass
        self._general_structural_model.reload(general_properties)
        self._special_structural_model.reload(special_properties)
        self._parameter_model.reload(self._block)
        self._symbol_model.reload(self._block)

        # Structural regeneration can replace owner objects. Keep a temporary
        # model-backed draft until the source buffers are rebuilt below.
        self._namespace = build_block_symbol_namespace(self._block)
        self._runtime_logic_drafts = RuntimeLogicDraftCollection(self._block)
        self._retained_mode_model.reload(self._runtime_logic_drafts)
        self._namespace = self._runtime_logic_drafts.build_validation_namespace(self._namespace)

    def _refresh_after_apply(self, rebuilt_structure: bool) -> None:
        """Rebind the complete properties page to the successfully applied model.

        :param rebuilt_structure: Regenerate source when a builder replaced the model.
        :return: None.
        """
        if self._prepared_to_delete:
            return
        else:
            active_owner: Block = self._equation_buffers[self._active_equation_buffer_index].get_block()

        # Keep accepted author text for surviving owners, but never reuse a
        # buffer belonging to a removed child or a regenerated structural model.
        old_buffers: Dict[int, BlockCodeBuffer] = dict()
        buffer: BlockCodeBuffer
        for buffer in self._equation_buffers:
            old_buffers[buffer.get_block().uid] = buffer
        rename_pairs: List[tuple[str, str]] = list()
        row_index: int
        for row_index in range(self._symbol_model.rowCount()):
            row: BlockSymbolDraftRow | None = self._symbol_model.get_row(row_index)
            variable: Var | None = row.get_variable() if row is not None else None
            if row is not None and variable is not None and row.get_name() != variable.name:
                rename_pairs.append((row.get_name(), variable.name))
            else:
                pass

        previous_owner_signals: bool = self.ui.equation_owner_combo.blockSignals(True)
        self._loading_equation_buffer = True
        try:
            self._reload_applied_models()

            # Rebuild the source-owner selector from current block identities.
            # Add-property dialogs are created lazily from this same list.
            self._equation_buffers.clear()
            self.ui.equation_owner_combo.clear()
            self._active_equation_buffer_index = 0
            owner_index: int
            owner: Block
            for owner_index, owner in enumerate(self._block.get_all_blocks()):
                refreshed_buffer: BlockCodeBuffer = BlockCodeBuffer(owner)
                old_buffer: BlockCodeBuffer | None = old_buffers.get(owner.uid, None)
                if not rebuilt_structure and old_buffer is not None and old_buffer.get_block() is owner:
                    accepted_source: str = old_buffer.get_code()
                    old_name: str
                    new_name: str
                    for old_name, new_name in rename_pairs:
                        accepted_source = replace_dae_identifier(accepted_source, old_name, new_name)
                    accepted_source = synchronize_dae_variable_declarations(
                        accepted_source,
                        self._symbol_model.get_role_names(owner, BlockSymbolKind.STATE),
                        self._symbol_model.get_role_names(owner, BlockSymbolKind.ALGEBRAIC),
                        self._symbol_model.get_role_names(owner, BlockSymbolKind.DIFFERENTIAL),
                    )
                    refreshed_buffer.accept_source(accepted_source)
                else:
                    pass
                self._equation_buffers.append(refreshed_buffer)
                owner_label: str = f"{owner.name} [{owner_index + 1}]"
                self.ui.equation_owner_combo.addItem(owner_label, owner_index)
                if owner is active_owner:
                    self._active_equation_buffer_index = owner_index
                else:
                    pass
            # Refresh the visible document and previews only once all model
            # identities are current, without firing intermediate owner changes.
            self.ui.equation_owner_combo.setCurrentIndex(self._active_equation_buffer_index)
            self._runtime_logic_drafts = self._build_runtime_logic_drafts_from_buffers()
            self._retained_mode_model.reload(self._runtime_logic_drafts)
            symbol_namespace: Dict[str, Expr] = self._symbol_model.build_validation_namespace(
                build_block_symbol_namespace(self._block)
            )
            self._namespace = self._runtime_logic_drafts.build_validation_namespace(
                symbol_namespace
            )
            active_buffer: BlockCodeBuffer = self._equation_buffers[self._active_equation_buffer_index]
            if self._dae_editor.toPlainText() != active_buffer.get_code():
                cursor_position: int = self._dae_editor.textCursor().position()
                self._dae_editor.setPlainText(active_buffer.get_code())
                cursor: QtGui.QTextCursor = self._dae_editor.textCursor()
                cursor.setPosition(min(cursor_position, self._dae_editor.document().characterCount() - 1))
                self._dae_editor.setTextCursor(cursor)
            else:
                pass
            self._refresh_dae_language_context()
            self._rebuild_latex_selection_tree()
            self.setWindowTitle(self.tr("Block properties - {name}").format(name=self._block.name))
            self._clear_dae_validation_feedback()
        finally:
            self._loading_equation_buffer = False
            self.ui.equation_owner_combo.blockSignals(previous_owner_signals)
        self.refresh_draft_state()

    def _show_equation_buffer_diagnostics(self,
                                          buffer_index: int,
                                          diagnostics: Sequence[DaeCodeDiagnostic]) -> None:
        """Switch to one equation owner and show its source-local errors.

        :param buffer_index: Index of the invalid equation buffer.
        :param diagnostics: Diagnostics to underline in that buffer.
        :return: None.
        """
        self.ui.tab_widget.setCurrentWidget(self.ui.dae_model_page)
        if buffer_index != self._active_equation_buffer_index:
            self.ui.equation_owner_combo.setCurrentIndex(buffer_index)
        else:
            pass
        self._dae_editor.set_diagnostics(diagnostics)
        if len(diagnostics) > 0:
            self._show_dae_validation_diagnostics(diagnostics)
        else:
            self._show_dae_validation_message(
                self.tr("Invalid DAE code."),
                "color: #b42318;",
            )

    def _clear_dae_validation_feedback(self) -> None:
        """Remove stale validation marks while preserving the edited source.

        :return: None.
        """
        self._dae_editor.set_diagnostics(list())

    def _show_dae_validation_message(self, message: str, style_sheet: str) -> None:
        """Display one-line DAE validation feedback as a toast.

        :param message: Human-readable result of validating the DAE source.
        :param style_sheet: Qt style sheet that conveys the result severity.
        :return: None.
        """
        message_parts: List[str] = message.split()
        single_line_message: str = " ".join(message_parts)
        if "#b42318" in style_sheet:
            self.toast_manager.show_error_toast(single_line_message)
        elif "#9a6700" in style_sheet:
            self.toast_manager.show_warning_toast(single_line_message)
        else:
            self.toast_manager.show_info_toast(single_line_message)

    def _show_dae_validation_diagnostics(
            self,
            diagnostics: Sequence[DaeCodeDiagnostic]) -> None:
        """Show exact source diagnostics after an explicit validation request.

        :param diagnostics: Ordered diagnostics for the visible source buffer.
        :return: None.
        """
        self.ui.tab_widget.setCurrentWidget(self.ui.dae_model_page)
        self._dae_editor.set_diagnostics(diagnostics)
        if len(diagnostics) > 0:
            first_diagnostic: DaeCodeDiagnostic = diagnostics[0]
            self._show_dae_validation_message(
                self.tr("DAE validation failed at line {line}: {message}").format(
                    line=first_diagnostic.get_line(),
                    message=first_diagnostic.get_message(),
                ),
                "color: #b42318;",
            )
        else:
            pass

    def _show_validation_error(self, message: str) -> None:
        """
        Display validation feedback without modifying the source block.

        :param message: Value supplied for ``message``.
        :return: None.
        """
        self.ui.tab_widget.setCurrentWidget(self.ui.dae_model_page)
        self._show_dae_validation_message(
            self.tr("Nothing was applied: {message}").format(message=message),
            "color: #b42318;",
        )
