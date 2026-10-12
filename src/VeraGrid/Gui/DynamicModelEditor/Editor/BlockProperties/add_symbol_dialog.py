# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Focused controller and typed result for the Dynamic Editor add-property form."""

from __future__ import annotations

import keyword

from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.add_symbol_widget import Ui_AddSymbolDialog
from VeraGridEngine.enumerations import (
    BlockSymbolCategory,
    BlockSymbolKind,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
)
from VeraGridEngine.Utils.Symbolic.block import Block


def symbol_kind_supports_export(kind: BlockSymbolKind) -> bool:
    """Return whether a newly declared symbol can be exposed as output.

    :param kind: Primary role selected for the new symbol.
    :return: Whether the output option applies to the role.
    """
    return kind not in (
        BlockSymbolKind.PARAMETER,
        BlockSymbolKind.EVENT_PARAMETER,
        BlockSymbolKind.MODE_PARAMETER,
        BlockSymbolKind.INPUT,
    )


def symbol_kind_supports_external_reference(kind: BlockSymbolKind) -> bool:
    """Return whether a symbol can use a power-flow initialization source.

    :param kind: Primary role selected for the new symbol.
    :return: Whether the power-flow source selector applies to the role.
    """
    return kind not in (
        BlockSymbolKind.PARAMETER,
        BlockSymbolKind.EVENT_PARAMETER,
        BlockSymbolKind.MODE_PARAMETER,
        BlockSymbolKind.INPUT,
    )


class AddSymbolSelection:
    """Typed values accepted by the add-property dialog."""

    __slots__ = (
        "_owner",
        "_name",
        "_kind",
        "_exported",
        "_value",
        "_create_derivative",
        "_external_reference",
        "_static_reference",
    )

    def __init__(
            self,
            owner: Block,
            name: str,
            kind: BlockSymbolKind,
            exported: bool,
            value: float | None,
            create_derivative: bool,
            external_reference: VarPowerFlowReferenceType | None,
            static_reference: ParamPowerFlowReferenceType | None,
    ) -> None:
        """Store one complete and validated add-property request.

        :param owner: Block that will own the new symbol.
        :param name: Valid Python identifier for the symbol.
        :param kind: Primary symbolic role.
        :param exported: Whether the symbol is also exposed as output.
        :param value: Local numeric initial value, or ``None`` for device initialization.
        :param create_derivative: Whether a state receives a derivative variable.
        :param external_reference: Optional power-flow initialization source.
        :param static_reference: Optional device-backed initial-value mapping.
        :return: None.
        """
        self._owner: Block = owner
        self._name: str = name
        self._kind: BlockSymbolKind = kind
        self._exported: bool = exported
        self._value: float | None = value
        self._create_derivative: bool = create_derivative
        self._external_reference: VarPowerFlowReferenceType | None = external_reference
        self._static_reference: ParamPowerFlowReferenceType | None = static_reference

    def get_owner(self) -> Block:
        """Return the block that will own the symbol.

        :return: Selected owner block.
        """
        return self._owner

    def get_name(self) -> str:
        """Return the validated symbol name.

        :return: Python identifier entered by the user.
        """
        return self._name

    def get_kind(self) -> BlockSymbolKind:
        """Return the primary symbolic role.

        :return: Selected symbol kind.
        """
        return self._kind

    def is_exported(self) -> bool:
        """Return whether the symbol must also be an output.

        :return: Output-exposure state.
        """
        return self._exported

    def get_value(self) -> float | None:
        """Return the selected local parameter value source.

        :return: Numeric value, or ``None`` when a device mapping is selected.
        """
        return self._value

    def creates_derivative(self) -> bool:
        """Return whether a derivative variable must accompany the state.

        :return: Derivative-creation state.
        """
        return self._create_derivative

    def get_external_reference(self) -> VarPowerFlowReferenceType | None:
        """Return the optional power-flow initialization source.

        :return: Selected external reference or ``None``.
        """
        return self._external_reference

    def get_static_reference(self) -> ParamPowerFlowReferenceType | None:
        """Return the optional static-parameter device mapping.

        :return: Selected static reference or ``None``.
        """
        return self._static_reference


class AddSymbolDialog(QtWidgets.QDialog):
    """Focused dialog that collects one typed block-property declaration."""

    __slots__ = ("_ui", "_category", "_selection")

    def __init__(
            self,
            category: BlockSymbolCategory,
            owners: list[Block],
            preferred_owner: Block | None,
            parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Build a category-specific property form.

        :param category: Property category selected by the context-menu action.
        :param owners: Blocks that may own the new property.
        :param preferred_owner: Owner resolved from the clicked tree branch.
        :param parent: Optional owning widget.
        :return: None.
        """
        super().__init__(parent)
        self._ui: Ui_AddSymbolDialog = Ui_AddSymbolDialog()
        self._ui.setupUi(self)
        self._category: BlockSymbolCategory = category
        self._selection: AddSymbolSelection | None = None

        # Every invocation starts from current model objects, so structural
        # rebuilds can never leave stale owner pointers inside a standby form.
        self._populate_owners(owners=owners, preferred_owner=preferred_owner)
        self._populate_mapping_choices()
        self._configure_category()
        self._configure_searchable_combo(
            combo=self._ui.new_external_reference,
            placeholder=self.tr("Search power-flow variables"),
        )
        self._configure_searchable_combo(
            combo=self._ui.new_static_reference,
            placeholder=self.tr("Search device parameters"),
        )
        self._update_controls()

        self._ui.new_symbol_kind.currentIndexChanged.connect(self._update_controls)
        self._ui.new_static_reference.currentIndexChanged.connect(self._update_controls)
        add_button: QtWidgets.QPushButton | None = self._ui.button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        if add_button is not None:
            add_button.clicked.connect(self._accept_selection)
        else:
            pass
        self._ui.new_symbol_name.setFocus()

    def get_selection(self) -> AddSymbolSelection | None:
        """Return the values accepted by the user.

        :return: Complete selection after acceptance, otherwise ``None``.
        """
        return self._selection

    def _populate_owners(self, owners: list[Block], preferred_owner: Block | None) -> None:
        """Populate the owner selector from current model identities.

        :param owners: Blocks that may own the new symbol.
        :param preferred_owner: Owner inferred from the context-menu location.
        :return: None.
        """
        selected_index: int = 0
        owner_index: int
        owner: Block
        for owner_index, owner in enumerate(owners):
            owner_label: str = f"{owner.name} [{owner_index + 1}]"
            self._ui.new_symbol_owner.addItem(owner_label, owner)
            if owner is preferred_owner:
                selected_index = owner_index
            else:
                pass
        self._ui.new_symbol_owner.setCurrentIndex(selected_index)

    def _populate_mapping_choices(self) -> None:
        """Populate mapping selectors while preserving enum values as item data.

        :return: None.
        """
        self._ui.new_external_reference.addItem(self.tr("None"), None)
        external_reference: VarPowerFlowReferenceType
        for external_reference in VarPowerFlowReferenceType:
            if external_reference == VarPowerFlowReferenceType.NOTHING:
                pass
            else:
                self._ui.new_external_reference.addItem(
                    external_reference.value,
                    external_reference,
                )

        self._ui.new_static_reference.addItem(self.tr("Use local numeric value"), None)
        static_reference: ParamPowerFlowReferenceType
        for static_reference in ParamPowerFlowReferenceType:
            excluded_reference: bool = static_reference == ParamPowerFlowReferenceType.NOTHING
            if excluded_reference:
                pass
            else:
                self._ui.new_static_reference.addItem(static_reference.value, static_reference)

    def _configure_searchable_combo(self, combo: QtWidgets.QComboBox, placeholder: str) -> None:
        """Enable substring search without permitting new free-form values.

        :param combo: Enum-backed selector to configure.
        :param placeholder: Search hint shown by its line editor.
        :return: None.
        """
        combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        completer: QtWidgets.QCompleter | None = combo.completer()
        if completer is not None:
            completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        else:
            pass
        line_edit: QtWidgets.QLineEdit | None = combo.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText(placeholder)
            line_edit.setClearButtonEnabled(True)
        else:
            pass

    def _configure_category(self) -> None:
        """Configure the single page selected before the dialog was opened.

        :return: None.
        """
        add_button: QtWidgets.QPushButton | None = self._ui.button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        self._ui.new_symbol_kind.clear()
        if self._category == BlockSymbolCategory.VARIABLES:
            self._ui.new_symbol_kind.addItem(self.tr("Input"), BlockSymbolKind.INPUT)
            self._ui.new_symbol_kind.addItem(self.tr("State"), BlockSymbolKind.STATE)
            self._ui.new_symbol_kind.addItem(self.tr("Algebraic"), BlockSymbolKind.ALGEBRAIC)
            self._ui.symbol_options_stack.setCurrentWidget(self._ui.variable_page)
            self._ui.new_symbol_kind_label.setText(self.tr("Variable type"))
            heading: str = self.tr("Add variable")
            description: str = self.tr("Declare a variable owned by the selected dynamic block.")
        elif self._category == BlockSymbolCategory.PARAMETERS:
            self._ui.new_symbol_kind.addItem(self.tr("Dynamic parameter"), BlockSymbolKind.EVENT_PARAMETER)
            self._ui.new_symbol_kind.addItem(self.tr("Static parameter"), BlockSymbolKind.PARAMETER)
            self._ui.symbol_options_stack.setCurrentWidget(self._ui.parameter_page)
            self._ui.new_symbol_kind_label.setText(self.tr("Parameter type"))
            self._ui.new_parameter_value_label.setText(self.tr("Local initial value"))
            self._ui.new_static_reference_label.setText(self.tr("Device initial value"))
            heading = self.tr("Add parameter")
            description = self.tr("Declare a configurable value owned by the selected dynamic block.")
        elif self._category == BlockSymbolCategory.RETAINED_MODES:
            self._ui.new_symbol_kind.addItem(self.tr("Retained mode"), BlockSymbolKind.MODE_PARAMETER)
            self._ui.symbol_options_stack.setCurrentWidget(self._ui.retained_mode_page)
            heading = self.tr("Add retained mode")
            description = self.tr("Declare discrete state that persists between simulation steps.")
        else:
            heading = self.tr("Add block property")
            description = self.tr("Define a new property for the selected block.")

        shows_kind_selector: bool = self._category != BlockSymbolCategory.RETAINED_MODES
        self._ui.new_symbol_kind_label.setVisible(shows_kind_selector)
        self._ui.new_symbol_kind.setVisible(shows_kind_selector)
        self._ui.new_symbol_kind_description.setVisible(shows_kind_selector)
        self._ui.dialog_heading.setText(heading)
        self._ui.dialog_description.setText(description)
        self.setWindowTitle(heading)
        if add_button is not None:
            add_button.setText(heading)
        else:
            pass

    @QtCore.Slot(int)
    def _update_controls(self, unused_index: int = 0) -> None:
        """Show only options that apply to the selected symbol kind.

        :param unused_index: Combo index supplied by Qt.
        :return: None.
        """
        _unused_index: int = unused_index
        selected_data: object = self._ui.new_symbol_kind.currentData()
        if isinstance(selected_data, BlockSymbolKind):
            supports_export: bool = symbol_kind_supports_export(kind=selected_data)
            supports_external: bool = symbol_kind_supports_external_reference(kind=selected_data)
            shows_variable_options: bool = supports_export or selected_data == BlockSymbolKind.STATE
            shows_initial_value: bool = selected_data in (
                BlockSymbolKind.PARAMETER,
                BlockSymbolKind.EVENT_PARAMETER,
            )
            shows_static_mapping: bool = selected_data in (
                BlockSymbolKind.PARAMETER,
                BlockSymbolKind.EVENT_PARAMETER,
            )

            self._ui.new_symbol_exported.setVisible(supports_export)
            self._ui.new_symbol_exported.setEnabled(supports_export)
            self._ui.new_state_derivative.setVisible(selected_data == BlockSymbolKind.STATE)
            self._ui.new_external_reference_label.setVisible(supports_external)
            self._ui.new_external_reference.setVisible(supports_external)
            self._ui.variable_options_label.setVisible(shows_variable_options)
            self._ui.new_variable_options.setVisible(shows_variable_options)
            self._ui.new_parameter_value_label.setVisible(shows_initial_value)
            self._ui.new_parameter_value.setVisible(shows_initial_value)
            self._ui.new_static_reference_label.setVisible(shows_static_mapping)
            self._ui.new_static_reference.setVisible(shows_static_mapping)
            uses_local_parameter_value: bool = (
                not shows_static_mapping
                or self._ui.new_static_reference.currentData() is None
            )
            self._ui.new_parameter_value_label.setEnabled(uses_local_parameter_value)
            self._ui.new_parameter_value.setEnabled(uses_local_parameter_value)
            if supports_export:
                pass
            else:
                self._ui.new_symbol_exported.setChecked(False)
            if selected_data == BlockSymbolKind.STATE:
                pass
            else:
                self._ui.new_state_derivative.setChecked(False)
            self._ui.new_symbol_kind_description.setText(
                self._get_kind_description(kind=selected_data)
            )
        else:
            self._ui.new_symbol_exported.setEnabled(False)
            self._ui.variable_options_label.setVisible(False)
            self._ui.new_variable_options.setVisible(False)
            self._ui.new_parameter_value_label.setVisible(False)
            self._ui.new_parameter_value.setVisible(False)
            self._ui.new_static_reference_label.setVisible(False)
            self._ui.new_static_reference.setVisible(False)
            self._ui.new_external_reference_label.setVisible(False)
            self._ui.new_external_reference.setVisible(False)

    def _get_kind_description(self, kind: BlockSymbolKind) -> str:
        """Return a short user-facing explanation for one symbol kind.

        :param kind: Symbol kind selected in the dialog.
        :return: Translated explanation text.
        """
        if kind == BlockSymbolKind.INPUT:
            description: str = self.tr("Receives its value from an incoming block connection.")
        elif kind == BlockSymbolKind.STATE:
            description = self.tr("Represents a differential state integrated during the simulation.")
        elif kind == BlockSymbolKind.ALGEBRAIC:
            description = self.tr("Represents a value solved by the algebraic equations.")
        elif kind == BlockSymbolKind.EVENT_PARAMETER:
            description = self.tr(
                "May change during the simulation and can optionally start from a grid-device value."
            )
        elif kind == BlockSymbolKind.PARAMETER:
            description = self.tr(
                "Remains fixed during the simulation and can optionally start from a grid-device value."
            )
        elif kind == BlockSymbolKind.MODE_PARAMETER:
            description = self.tr("Preserves discrete state between simulation steps.")
        else:
            description = self.tr("Choose how this symbol participates in the dynamic model.")
        return description

    def _show_error(self, message: str) -> None:
        """Display a validation error next to the form that caused it.

        :param message: Human-readable validation failure.
        :return: None.
        """
        self._ui.add_symbol_status_label.setStyleSheet("color: #b42318;")
        self._ui.add_symbol_status_label.setText(
            self.tr("Nothing was added: {message}").format(message=message)
        )
        self._ui.add_symbol_status_label.show()

    def _has_unmatched_text(self, combo: QtWidgets.QComboBox) -> bool:
        """Return whether an editable enum selector contains a free-form value.

        :param combo: Enum-backed editable combo box.
        :return: ``True`` when its text does not identify an available item.
        """
        current_text: str = combo.currentText().strip()
        return combo.currentIndex() < 0 and len(current_text) > 0

    @QtCore.Slot()
    def _accept_selection(self) -> None:
        """Validate the form and accept one fully typed selection.

        :return: None.
        """
        name: str = self._ui.new_symbol_name.text().strip()
        selected_kind: object = self._ui.new_symbol_kind.currentData()
        selected_owner: object = self._ui.new_symbol_owner.currentData()
        if len(name) == 0 or not name.isidentifier() or keyword.iskeyword(name):
            self._show_error(self.tr("Enter a valid Python symbol name."))
        elif not isinstance(selected_kind, BlockSymbolKind):
            self._show_error(self.tr("Select a valid symbol type."))
        elif not isinstance(selected_owner, Block):
            self._show_error(self.tr("Select a valid owner block."))
        elif (symbol_kind_supports_external_reference(kind=selected_kind)
              and self._has_unmatched_text(combo=self._ui.new_external_reference)):
            self._show_error(self.tr("Select a power-flow initialization source from the list."))
        elif (selected_kind in (BlockSymbolKind.PARAMETER, BlockSymbolKind.EVENT_PARAMETER)
              and self._has_unmatched_text(combo=self._ui.new_static_reference)):
            self._show_error(self.tr("Select a device initialization source from the list."))
        else:
            external_data: object = self._ui.new_external_reference.currentData()
            static_data: object = self._ui.new_static_reference.currentData()
            external_reference: VarPowerFlowReferenceType | None
            static_reference: ParamPowerFlowReferenceType | None
            parameter_value: float | None
            if (symbol_kind_supports_external_reference(kind=selected_kind)
                    and isinstance(external_data, VarPowerFlowReferenceType)):
                external_reference = external_data
            else:
                external_reference = None
            if (selected_kind in (BlockSymbolKind.PARAMETER, BlockSymbolKind.EVENT_PARAMETER)
                    and isinstance(static_data, ParamPowerFlowReferenceType)):
                static_reference = static_data
            else:
                static_reference = None
            if static_reference is None:
                parameter_value = self._ui.new_parameter_value.value()
            else:
                # The problem builder supplies this value from the mapped
                # static device; the stored Const(None) records that contract.
                parameter_value = None

            self._selection = AddSymbolSelection(
                owner=selected_owner,
                name=name,
                kind=selected_kind,
                exported=self._ui.new_symbol_exported.isChecked(),
                value=parameter_value,
                create_derivative=self._ui.new_state_derivative.isChecked(),
                external_reference=external_reference,
                static_reference=static_reference,
            )
            self.accept()
