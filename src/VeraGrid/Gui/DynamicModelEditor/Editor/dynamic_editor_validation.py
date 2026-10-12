# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Typed validation results and their Dynamic Editor presentation dialog."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QDialog

from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_editor_validation_dialog import Ui_ValidationSectionDialog
from VeraGridEngine.enumerations import ValidationFilterType
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var

def collect_block_tree(root_block: Block) -> list[Block]:
    """
    Collect one root block and all nested descendant blocks.

    :param root_block: Root block to traverse.
    :return: Flat block list in pre-order.
    """
    collected_blocks: list[Block] = list((root_block,))
    child_block: Block

    for child_block in root_block.children:
        collected_blocks.extend(collect_block_tree(root_block=child_block))

    return collected_blocks


def format_validation_block_label(block: Block) -> str:
    """
    Return one stable validation label for a block.

    :param block: Block to label.
    :return: User-facing label with the block name and uid suffix.
    """
    block_name: str = block.name if block.name else QtCore.QCoreApplication.translate(
        "DynamicBlockEditorGUI",
        "Unnamed block",
    )
    uid_suffix: str = str(block.uid)[-8:]
    return f"{block_name} [{uid_suffix}]"


class ValidationNameEntry:
    """Track the symbolic identities registered under one visible name."""

    __slots__ = ("_name", "_uids")

    def __init__(self, name: str) -> None:
        """Create an empty identity group for one variable name.

        :param name: Symbolic variable name represented by this entry.
        :return: None.
        """
        self._name: str = name
        self._uids: set[int] = set()

    def get_name(self) -> str:
        """Return the symbolic name represented by this entry.

        :return: Symbolic variable name.
        """
        return self._name

    def add_uid(self, uid: int) -> None:
        """Register one symbolic identity for the represented name.

        :param uid: Stable variable identity to register.
        :return: None.
        """
        self._uids.add(uid)

    def has_multiple_uids(self) -> bool:
        """Return whether the name belongs to more than one variable.

        :return: ``True`` when the name is duplicated by identity.
        """
        return len(self._uids) > 1


def get_or_create_validation_name_entry(
        name_entries: list[ValidationNameEntry],
        name: str,
) -> ValidationNameEntry:
    """Return the duplicate-check entry for one name, creating it if absent.

    :param name_entries: Ordered duplicate-check entries for one block.
    :param name: Symbolic variable name to resolve.
    :return: Existing or newly created name entry.
    """
    name_entry: ValidationNameEntry
    for name_entry in name_entries:
        if name_entry.get_name() == name:
            return name_entry
        else:
            pass

    new_entry: ValidationNameEntry = ValidationNameEntry(name=name)
    name_entries.append(new_entry)
    return new_entry


def append_vars_to_name_entries(
        name_entries: list[ValidationNameEntry],
        vars_list: list[Var],
) -> None:
    """
    Register one list of variables into the duplicate-name entries.

    :param name_entries: Mutable identity groups indexed by their typed name property.
    :param vars_list: Variables to register.
    :return: None.
    """
    var: Var
    for var in vars_list:
        name_entry: ValidationNameEntry = get_or_create_validation_name_entry(
            name_entries=name_entries,
            name=var.name,
        )
        name_entry.add_uid(uid=var.uid)


class ValidationRow:
    """
    Row of validation output associated with one block.
    """

    __slots__ = ("_block_uid", "_block_label", "_details", "_highlight_block")

    def __init__(self, block_uid: int, block_label: str) -> None:
        """
        Build one validation row.

        :param block_uid: Stable identity of the validated block.
        :param block_label: Human-readable block label.
        :return: None.
        """
        self._block_uid: int = block_uid
        self._block_label: str = block_label
        self._details: list[str] = list()
        self._highlight_block: bool = False

    def get_block_label(self) -> str:
        """
        Return the user-facing block label.

        :return: Block label.
        """
        return self._block_label

    def get_block_uid(self) -> int:
        """Return the stable identity of the validated block.

        :return: Block uid.
        """
        return self._block_uid

    def get_details(self) -> list[str]:
        """
        Return the row detail lines.

        :return: Detail lines.
        """
        return self._details

    def add_detail(self, detail: str) -> None:
        """
        Append one validation detail line.

        :param detail: Detail text to append.
        :return: None.
        """
        self._details.append(detail)

    def set_highlight_block(self, val: bool) -> None:
        """
        Store whether the owning block should be highlighted.

        :param val: Whether to highlight the whole block.
        :return: None.
        """
        self._highlight_block = val

    def get_highlight_block(self) -> bool:
        """
        Return whether the owning block should be highlighted.

        :return: Block highlight flag.
        """
        return self._highlight_block

class ValidationSection:
    """
    Group of validation rows for one validation rule family.
    """

    __slots__ = ("_title", "_rows")

    def __init__(self, title: str) -> None:
        """
        Build one validation section.

        :param title: Section title.
        :return: None.
        """
        self._title: str = title
        self._rows: list[ValidationRow] = list()

    def get_title(self) -> str:
        """
        Return the section title.

        :return: Title text.
        """
        return self._title

    def get_rows(self) -> list[ValidationRow]:
        """
        Return the section rows.

        :return: Ordered validation rows.
        """
        return self._rows

    def get_or_create_row(self, block: Block) -> ValidationRow:
        """Return the row for one block, creating it when absent.

        :param block: Validated block owning the row.
        :return: Existing or newly appended validation row.
        """
        row: ValidationRow
        for row in self._rows:
            if row.get_block_uid() == block.uid:
                return row
            else:
                pass

        new_row: ValidationRow = ValidationRow(
            block_uid=block.uid,
            block_label=format_validation_block_label(block=block),
        )
        self._rows.append(new_row)
        return new_row


class ValidationTraversalNode:
    """
    Recursive validation context for one block and its inherited mappings.
    """

    __slots__ = ("_block", "_effective_external_vars", "_children")

    def __init__(self, block: Block, effective_external_vars: set[Var]) -> None:
        """Create one node in the recursive validation context.

        :param block: Symbolic block represented by this traversal node.
        :param effective_external_vars: External variables inherited at this level.
        :return: None.
        """
        self._block: Block = block
        self._effective_external_vars: set[Var] = set(effective_external_vars)
        self._children: list[ValidationTraversalNode] = list()

    def get_block(self) -> Block:
        """Return the symbolic block represented by this node.

        :return: Traversal block.
        """
        return self._block

    def get_effective_external_vars(self) -> set[Var]:
        """Return external variables visible at this traversal level.

        :return: Effective external-variable set.
        """
        return self._effective_external_vars

    def get_children(self) -> list["ValidationTraversalNode"]:
        """Return the ordered child traversal nodes.

        :return: Child validation contexts.
        """
        return self._children

    def add_child(self, child_node: "ValidationTraversalNode") -> None:
        """Append one child validation context.

        :param child_node: Child context to append.
        :return: None.
        """
        self._children.append(child_node)


def collect_local_external_vars(block: Block) -> set[Var]:
    """
    Collect the local external-mapping variables defined on one block.

    :param block: Block to inspect.
    :return: Local external variables.
    """
    local_external_vars: set[Var] = set()
    mapped_var: Var | None
    for mapped_var in block.external_mapping.values():
        if isinstance(mapped_var, Var):
            local_external_vars.add(mapped_var)
        else:
            pass
    return local_external_vars


def build_validation_traversal_node(block: Block, inherited_external_vars: set[Var]) -> ValidationTraversalNode:
    """
    Build one recursive validation traversal node from the block hierarchy.

    :param block: Block to convert.
    :param inherited_external_vars: External variables visible from parent levels.
    :return: Recursive traversal node.
    """
    effective_external_vars: set[Var] = set(inherited_external_vars)
    local_external_vars: set[Var] = collect_local_external_vars(block=block)
    effective_external_vars.update(local_external_vars)

    node: ValidationTraversalNode = ValidationTraversalNode(
        block=block,
        effective_external_vars=set(effective_external_vars),
    )

    child_block: Block
    for child_block in block.children:
        child_node: ValidationTraversalNode = build_validation_traversal_node(
            block=child_block,
            inherited_external_vars=set(effective_external_vars),
        )
        node.add_child(child_node=child_node)

    return node


def collect_validation_traversal_list(root_node: ValidationTraversalNode) -> list[ValidationTraversalNode]:
    """
    Flatten one recursive validation traversal tree.

    :param root_node: Root traversal node.
    :return: Flat traversal-node list.
    """
    flat_nodes: list[ValidationTraversalNode] = list((root_node,))
    child_node: ValidationTraversalNode
    for child_node in root_node.get_children():
        flat_nodes.extend(collect_validation_traversal_list(root_node=child_node))
    return flat_nodes


def add_validation_detail(section: ValidationSection, block: Block, detail: str) -> None:
    """
    Append one formatted validation detail to a section.

    :param section: Mutable validation section.
    :param block: Validated block owning the detail.
    :param detail: One validation detail for that block.
    :return: None.
    """
    row: ValidationRow = section.get_or_create_row(block=block)
    row.add_detail(detail=detail)


class ValidationFilterChoice:
    """Typed filter option exposed by the validation-results combo box."""

    __slots__ = ("_label", "_filter_type", "_section")

    def __init__(
            self,
            label: str,
            filter_type: ValidationFilterType,
            section: ValidationSection | None,
    ) -> None:
        """Create one validation-result filter choice.

        :param label: User-facing combo-box label.
        :param filter_type: Scope represented by this filter choice.
        :param section: Optional validation section to display exclusively.
        :return: None.
        """
        self._label: str = label
        self._filter_type: ValidationFilterType = filter_type
        self._section: ValidationSection | None = section

    def get_label(self) -> str:
        """Return the user-facing filter label.

        :return: Filter label.
        """
        return self._label

    def is_issues_only(self) -> bool:
        """Return whether this choice excludes successful checks.

        :return: Issues-only state.
        """
        return self._filter_type == ValidationFilterType.ISSUES_ONLY

    def includes_section(self, section: ValidationSection, has_issues: bool) -> bool:
        """Return whether one validation section belongs in this filter.

        :param section: Candidate validation section.
        :param has_issues: Whether the section contains reported issue rows.
        :return: Whether the section must be rendered.
        """
        if self._filter_type == ValidationFilterType.ALL_CHECKS:
            return True
        elif self._filter_type == ValidationFilterType.ISSUES_ONLY:
            return has_issues
        elif self._filter_type == ValidationFilterType.SECTION:
            return self._section is section
        else:
            return False


class ValidationSectionDialog(QDialog):
    """
    Dialog showing model-consistency results grouped by validation section.
    """

    __slots__ = (
        "_section_results",
        "_ui",
        "_show_issues_button",
        "_filter_choices",
        "_table_model",
        "_issue_icon",
        "_ok_icon",
    )

    issuesRequested: QtCore.Signal = QtCore.Signal(object)
    # Symbolic UIDs may exceed Qt's 32-bit integer signal payload.
    issueSelected: QtCore.Signal = QtCore.Signal(object)

    def __init__(
            self,
            section_results: list[ValidationSection],
            parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """
        Build one validation-results dialog.

        :param section_results: Ordered validation sections to render.
        :param parent: Optional parent widget.
        :return: None.
        """
        super().__init__(parent)
        self._section_results: list[ValidationSection] = section_results
        self._ui: Ui_ValidationSectionDialog = Ui_ValidationSectionDialog()
        self._ui.setupUi(self)

        # A single standard item model keeps all result scrolling and sizing in
        # the table view, instead of nesting one manually sized table per check.
        self._table_model: QtGui.QStandardItemModel = QtGui.QStandardItemModel(self)
        self._table_model.setColumnCount(4)
        self._table_model.setHorizontalHeaderLabels(
            list((self.tr("Status"), self.tr("Check"), self.tr("Block"), self.tr("Details"),))
        )
        self._ui.resultsTableView.setModel(self._table_model)

        table_header: QtWidgets.QHeaderView = self._ui.resultsTableView.horizontalHeader()
        table_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)

        # Standard Qt status icons follow the active platform and theme without
        # imposing fixed light-theme foreground colours on the result table.
        self._issue_icon: QtGui.QIcon = self.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_MessageBoxWarning
        )
        self._ok_icon: QtGui.QIcon = self.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_DialogApplyButton
        )

        self._filter_choices: list[ValidationFilterChoice] = list()
        self._populate_filter_choices()
        self._update_summary()
        self._refresh_table(filter_index=0)
        self._ui.resultsFilterComboBox.currentIndexChanged.connect(self._refresh_table)
        self._ui.resultsTableView.doubleClicked.connect(self._show_selected_issue_in_model)

        self._show_issues_button: QtWidgets.QPushButton = self._ui.showIssuesButton
        self._show_issues_button.setEnabled(self._has_any_issue_rows())
        self._show_issues_button.clicked.connect(self._show_issues_in_model)

    def _populate_filter_choices(self) -> None:
        """Populate the result filter with overview and section choices.

        :return: None.
        """
        self._filter_choices.clear()
        self._ui.resultsFilterComboBox.clear()

        all_checks_choice: ValidationFilterChoice = ValidationFilterChoice(
            label=self.tr("All checks"),
            filter_type=ValidationFilterType.ALL_CHECKS,
            section=None,
        )
        issues_only_choice: ValidationFilterChoice = ValidationFilterChoice(
            label=self.tr("Issues only"),
            filter_type=ValidationFilterType.ISSUES_ONLY,
            section=None,
        )
        self._filter_choices.append(all_checks_choice)
        self._filter_choices.append(issues_only_choice)

        section: ValidationSection
        for section in self._section_results:
            section_choice: ValidationFilterChoice = ValidationFilterChoice(
                label=section.get_title(),
                filter_type=ValidationFilterType.SECTION,
                section=section,
            )
            self._filter_choices.append(section_choice)

        filter_choice: ValidationFilterChoice
        for filter_choice in self._filter_choices:
            self._ui.resultsFilterComboBox.addItem(filter_choice.get_label())

    def _update_summary(self) -> None:
        """Display aggregate validation counts above the table.

        :return: None.
        """
        issue_section_count: int = 0
        finding_count: int = 0
        section: ValidationSection
        for section in self._section_results:
            rows: list[ValidationRow] = section.get_rows()
            if len(rows) > 0:
                issue_section_count = issue_section_count + 1
            else:
                pass

            row: ValidationRow
            for row in rows:
                finding_count = finding_count + len(row.get_details())

        check_count: int = len(self._section_results)
        if finding_count == 0:
            summary_text: str = self.tr("{check_count} checks · No issues found").format(
                check_count=check_count
            )
        else:
            summary_text = self.tr(
                "{check_count} checks · {issue_section_count} checks with issues · {finding_count} findings"
            ).format(
                check_count=check_count,
                issue_section_count=issue_section_count,
                finding_count=finding_count,
            )
        self._ui.summaryLabel.setText(summary_text)

    def _refresh_table(self, filter_index: int) -> None:
        """Rebuild the visible rows for one selected validation filter.

        :param filter_index: Index of the selected typed filter choice.
        :return: None.
        """
        existing_row_count: int = self._table_model.rowCount()
        if existing_row_count > 0:
            self._table_model.removeRows(0, existing_row_count)
        else:
            pass

        if 0 <= filter_index < len(self._filter_choices):
            filter_choice: ValidationFilterChoice = self._filter_choices[filter_index]
        else:
            filter_choice = self._filter_choices[0]

        section: ValidationSection
        for section in self._section_results:
            rows: list[ValidationRow] = section.get_rows()
            has_issues: bool = len(rows) > 0
            if filter_choice.includes_section(section=section, has_issues=has_issues):
                if has_issues:
                    row: ValidationRow
                    for row in rows:
                        self._append_issue_table_row(section=section, row=row)
                else:
                    self._append_success_table_row(section=section)
            else:
                pass

        has_visible_rows: bool = self._table_model.rowCount() > 0
        self._ui.resultsTableView.setVisible(has_visible_rows)
        self._ui.emptyStateLabel.setVisible(not has_visible_rows)
        if has_visible_rows:
            self._ui.resultsTableView.resizeRowsToContents()
        else:
            if filter_choice.is_issues_only() and not self._has_any_issue_rows():
                self._ui.emptyStateLabel.setText(self.tr("No issues found."))
            else:
                self._ui.emptyStateLabel.setText(self.tr("No validation results match this filter."))

    def _append_issue_table_row(self, section: ValidationSection, row: ValidationRow) -> None:
        """Append one issue-bearing block row to the shared results model.

        :param section: Validation check that reported the issue.
        :param row: Block-level validation result.
        :return: None.
        """
        status_item: QtGui.QStandardItem = QtGui.QStandardItem(self._issue_icon, self.tr("Issue"))
        status_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        check_item: QtGui.QStandardItem = QtGui.QStandardItem(section.get_title())
        block_item: QtGui.QStandardItem = QtGui.QStandardItem(row.get_block_label())
        details_text: str = "\n".join(row.get_details())
        detail_item: QtGui.QStandardItem = QtGui.QStandardItem(details_text)
        detail_item.setToolTip(details_text)

        # Every visible cell carries the stable block identity so selection is
        # independent from translated labels and duplicate block names.
        # Block identities are UUID-v4 integers and therefore use 128 bits.
        # QVariant integer conversion cannot represent that complete range, so
        # the item model stores the lossless decimal representation instead.
        block_uid_text: str = str(row.get_block_uid())
        status_item.setData(block_uid_text, QtCore.Qt.ItemDataRole.UserRole)
        check_item.setData(block_uid_text, QtCore.Qt.ItemDataRole.UserRole)
        block_item.setData(block_uid_text, QtCore.Qt.ItemDataRole.UserRole)
        detail_item.setData(block_uid_text, QtCore.Qt.ItemDataRole.UserRole)

        table_items: list[QtGui.QStandardItem] = list()
        table_items.append(status_item)
        table_items.append(check_item)
        table_items.append(block_item)
        table_items.append(detail_item)
        self._table_model.appendRow(table_items)

    def _append_success_table_row(self, section: ValidationSection) -> None:
        """Append one compact successful-check row to the shared results model.

        :param section: Validation check with no reported issues.
        :return: None.
        """
        status_item: QtGui.QStandardItem = QtGui.QStandardItem(self._ok_icon, self.tr("OK"))
        status_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        check_item: QtGui.QStandardItem = QtGui.QStandardItem(section.get_title())
        block_item: QtGui.QStandardItem = QtGui.QStandardItem("—")
        detail_item: QtGui.QStandardItem = QtGui.QStandardItem(self.tr("No issues found"))

        table_items: list[QtGui.QStandardItem] = list()
        table_items.append(status_item)
        table_items.append(check_item)
        table_items.append(block_item)
        table_items.append(detail_item)
        self._table_model.appendRow(table_items)

    def get_section_results(self) -> list[ValidationSection]:
        """
        Return the rendered validation sections.

        :return: Ordered validation sections.
        """
        return self._section_results

    def _has_any_issue_rows(self) -> bool:
        """
        Return whether the dialog contains at least one issue row.

        :return: ``True`` when any section contains one issue row.
        """
        section: ValidationSection

        # The action button is only useful when the validation pipeline found at
        # least one row that can be projected back onto the visible scene.
        for section in self._section_results:
            if len(section.get_rows()) > 0:
                return True
            else:
                pass

        return False

    def _show_issues_in_model(self) -> None:
        """
        Request issue highlighting on the owning dynamic editor.

        :return: None.
        """
        if self._has_any_issue_rows():
            # The dialog publishes intent and does not depend on its parent
            # implementation, keeping the reusable results view decoupled.
            self.issuesRequested.emit(self.get_section_results())
            self.accept()
        else:
            pass

    def _show_selected_issue_in_model(self, index: QtCore.QModelIndex) -> None:
        """Request navigation to the block represented by one result row.

        :param index: Double-clicked result-table index.
        :return: None.
        """
        block_uid_data: object = index.data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(block_uid_data, str) and block_uid_data.isdecimal():
            # Conversion occurs in Python, whose integers preserve the complete
            # UUID value without passing it through a bounded QVariant integer.
            block_uid: int = int(block_uid_data)
            self.issueSelected.emit(block_uid)
            self.accept()
        else:
            # Successful summary rows deliberately carry no block identity.
            pass

def build_validation_row_highlight_metadata(section_results: list[ValidationSection]) -> None:
    """
    Mark every reported validation row for block-level scene highlighting.

    :param section_results: Validation sections to annotate.
    :return: None.
    """
    section: ValidationSection
    for section in section_results:
        row: ValidationRow
        for row in section.get_rows():
            # Every remaining validation section reports block-level issues.
            row.set_highlight_block(val=True)
