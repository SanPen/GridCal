# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Block Properties editor for static one-dimensional lookup tables."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.SpecialConfigTabs.lookup_1d_config_tab_gui import (
    Ui_Lookup1DConfigTab,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.SpecialConfigTabs.special_config_tab import (
    SpecialConfigTabWidget,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.SpecialConfigTabs.table_configuration_data import (
    CurveTableDraft,
    generate_curve_points_from_expression,
    normalize_curve_points,
)
from VeraGridEngine.enumerations import BlockType
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp


def get_lookup_1d_builder_points(
        builder: TemplateDefinition,
) -> tuple[tuple[float, float], ...]:
    """Read a safe immutable point sequence from a lookup builder.

    The fallback is only used for a malformed in-memory builder. Persisted
    lookup blocks are recovered into ``points`` before Block Properties creates
    this tab, so valid legacy files retain their exact table values.

    :param builder: Lookup template builder owned by Block Properties.
    :return: At least two finite ``(x, y)`` rows.
    """
    points_property: TemplateProp | None = builder.params_dict.get("points", None)
    result: list[tuple[float, float]] = list()
    if points_property is not None and isinstance(points_property.value, (list, tuple)):
        candidate_row: object
        for candidate_row in points_property.value:
            if isinstance(candidate_row, (list, tuple)) and len(candidate_row) == 2:
                try:
                    x_value: float = float(candidate_row[0])
                    y_value: float = float(candidate_row[1])
                except (TypeError, ValueError):
                    result.clear()
                    break
                else:
                    if math.isfinite(x_value) and math.isfinite(y_value):
                        result.append((x_value, y_value))
                    else:
                        result.clear()
                        break
            else:
                result.clear()
                break
    else:
        pass

    if len(result) >= 2:
        return tuple(result)
    else:
        return ((0.0, 0.0), (1.0, 1.0))


class Lookup1DTableModel(QtCore.QAbstractTableModel):
    """Qt table adapter around a detached two-column curve draft."""

    draftChanged = QtCore.Signal()

    __slots__ = ("_draft", "_read_only")

    def __init__(self,
                 points: Sequence[Sequence[float]],
                 parent: QtCore.QObject | None = None) -> None:
        """Create a numeric table model without modifying the builder.

        :param points: Initial accepted lookup rows.
        :param parent: QObject that owns this table model.
        :return: None.
        """
        QtCore.QAbstractTableModel.__init__(self, parent)
        self._draft: CurveTableDraft = CurveTableDraft(points)
        self._read_only: bool = False

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """Return the number of lookup points.

        :param parent: Parent model index, unused by this flat table.
        :return: Number of point rows.
        """
        if parent.isValid():
            return 0
        else:
            return len(self._draft.get_points())

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """Return the fixed x/y column count.

        :param parent: Parent model index, unused by this flat table.
        :return: Two columns.
        """
        if parent.isValid():
            return 0
        else:
            return 2

    def data(self,
             index: QtCore.QModelIndex,
             role: int = int(QtCore.Qt.ItemDataRole.DisplayRole)) -> object:
        """Return one formatted coordinate for display or editing.

        :param index: Requested table cell.
        :param role: Qt item-data role.
        :return: Coordinate text, or ``None`` for unsupported requests.
        """
        points: tuple[tuple[float, float], ...] = self._draft.get_points()
        valid_index: bool = (
            index.isValid()
            and 0 <= index.row() < len(points)
            and 0 <= index.column() < 2
        )
        if valid_index and role in (
                int(QtCore.Qt.ItemDataRole.DisplayRole),
                int(QtCore.Qt.ItemDataRole.EditRole),
        ):
            return f"{points[index.row()][index.column()]:.12g}"
        else:
            return None

    def setData(self,
                index: QtCore.QModelIndex,
                value: object,
                role: int = int(QtCore.Qt.ItemDataRole.EditRole)) -> bool:
        """Stage one finite numeric cell and announce the curve change.

        :param index: Edited table cell.
        :param value: Candidate numeric value supplied by Qt.
        :param role: Qt item-data role.
        :return: Whether the value was accepted.
        """
        points: tuple[tuple[float, float], ...] = self._draft.get_points()
        valid_index: bool = (
            index.isValid()
            and 0 <= index.row() < len(points)
            and 0 <= index.column() < 2
        )
        if role == int(QtCore.Qt.ItemDataRole.EditRole) and valid_index and not self._read_only:
            try:
                numeric_value: float = float(value)
                if index.column() == 0:
                    accepted: bool = self._draft.set_point(
                        row_index=index.row(),
                        x_value=numeric_value,
                        y_value=points[index.row()][1],
                    )
                else:
                    accepted = self._draft.set_point(
                        row_index=index.row(),
                        x_value=points[index.row()][0],
                        y_value=numeric_value,
                    )
            except (TypeError, ValueError):
                accepted = False
        else:
            accepted = False

        if accepted:
            roles: list[int] = list((
                int(QtCore.Qt.ItemDataRole.DisplayRole),
                int(QtCore.Qt.ItemDataRole.EditRole),
            ))
            self.dataChanged.emit(index, index, roles)
            self.draftChanged.emit()
        else:
            pass
        return accepted

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """Expose editable coordinate cells unless the tab is read-only.

        :param index: Requested table cell.
        :return: Qt flags for that cell.
        """
        if not index.isValid():
            result: QtCore.Qt.ItemFlag = QtCore.Qt.ItemFlag.NoItemFlags
        elif self._read_only:
            result = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        else:
            result = (
                QtCore.Qt.ItemFlag.ItemIsEnabled
                | QtCore.Qt.ItemFlag.ItemIsSelectable
                | QtCore.Qt.ItemFlag.ItemIsEditable
            )
        return result

    def headerData(self,
                   section: int,
                   orientation: QtCore.Qt.Orientation,
                   role: int = int(QtCore.Qt.ItemDataRole.DisplayRole)) -> object:
        """Return x/y headers and one-based point numbers.

        :param section: Header section index.
        :param orientation: Header orientation.
        :param role: Qt item-data role.
        :return: Header text, or ``None`` for unsupported requests.
        """
        if role == int(QtCore.Qt.ItemDataRole.DisplayRole):
            if orientation == QtCore.Qt.Orientation.Horizontal and 0 <= section < 2:
                result: object = ("x", "y")[section]
            elif orientation == QtCore.Qt.Orientation.Vertical and section >= 0:
                result = str(section + 1)
            else:
                result = None
        else:
            result = None
        return result

    def add_point(self) -> None:
        """Append a valid point extrapolated from the current final interval.

        :return: None.
        """
        points: tuple[tuple[float, float], ...] = self._draft.get_points()
        point_count: int = len(points)
        if point_count == 0:
            new_x: float = 0.0
            new_y: float = 0.0
        elif point_count == 1:
            new_x = points[0][0] + 1.0
            new_y = points[0][1]
        else:
            interval: float = points[point_count - 1][0] - points[point_count - 2][0]
            if interval > 0.0:
                pass
            else:
                interval = 1.0
            new_x = points[point_count - 1][0] + interval
            new_y = points[point_count - 1][1]

        # Extremely large finite coordinates can overflow during extrapolation.
        # Retaining the final x value keeps the draft finite and lets normal
        # duplicate-axis validation explain what the user must correct.
        if math.isfinite(new_x):
            pass
        else:
            new_x = points[point_count - 1][0]

        self.beginInsertRows(QtCore.QModelIndex(), point_count, point_count)
        inserted: bool = self._draft.insert_point(point_count, new_x, new_y)
        self.endInsertRows()
        if inserted:
            self.draftChanged.emit()
        else:
            pass

    def remove_rows_by_index(self, row_indexes: Sequence[int]) -> None:
        """Remove selected point rows as one model reset.

        :param row_indexes: Candidate zero-based row indexes.
        :return: None.
        """
        valid_rows: set[int] = set()
        row_index: int
        point_count: int = len(self._draft.get_points())
        for row_index in row_indexes:
            if 0 <= row_index < point_count:
                valid_rows.add(row_index)
            else:
                pass
        if len(valid_rows) > 0:
            self.beginResetModel()
            self._draft.remove_rows(tuple(valid_rows))
            self.endResetModel()
            self.draftChanged.emit()
        else:
            pass

    def sort_by_x(self) -> None:
        """Sort points stably by x and keep each coordinate pair together.

        :return: None.
        """
        previous_points: tuple[tuple[float, float], ...] = self._draft.get_points()
        self.beginResetModel()
        self._draft.sort_by_x()
        self.endResetModel()
        if self._draft.get_points() != previous_points:
            self.draftChanged.emit()
        else:
            pass

    def replace_points(self, points: Sequence[Sequence[float]]) -> None:
        """Replace the complete draft and normalize its x ordering.

        :param points: Complete replacement point table.
        :return: None.
        """
        normalized_points: tuple[tuple[float, float], ...] = normalize_curve_points(points)
        self.beginResetModel()
        self._draft.set_points(normalized_points)
        self._draft.sort_by_x()
        self.endResetModel()
        self.draftChanged.emit()

    def reload(self, points: Sequence[Sequence[float]]) -> None:
        """Replace the table and its clean baseline after a successful Apply.

        :param points: Current accepted builder points.
        :return: None.
        """
        reloaded_draft: CurveTableDraft = CurveTableDraft(points)
        self.beginResetModel()
        self._draft = reloaded_draft
        self.endResetModel()

    def get_points(self) -> tuple[tuple[float, float], ...]:
        """Return the immutable staged point sequence.

        :return: Current lookup rows.
        """
        return self._draft.get_points()

    def has_changes(self) -> bool:
        """Return whether the table differs from its accepted baseline.

        :return: Whether this model owns pending edits.
        """
        return self._draft.has_changes()

    def get_validation_error(self, strictly_monotonic_y: bool) -> str | None:
        """Validate cardinality and lookup-axis ordering.

        :param strictly_monotonic_y: Whether inverse lookup output values must also be monotonic.
        :return: First validation message, or ``None`` when valid.
        """
        return self._draft.validate(
            minimum_point_count=2,
            strictly_increasing_x=True,
            strictly_monotonic_y=strictly_monotonic_y,
        )

    def set_read_only(self, read_only: bool) -> None:
        """Change whether coordinate cells advertise an editable flag.

        :param read_only: Whether editing must be disabled.
        :return: None.
        """
        if self._read_only != read_only:
            self._read_only = read_only
            self.layoutChanged.emit()
        else:
            pass


class Lookup1DConfigTab(SpecialConfigTabWidget):
    """Inline table-and-chart editor for a static one-dimensional lookup."""

    __slots__ = ("ui", "_block_type", "_table_model", "_shortcuts")

    def __init__(self,
                 builder: TemplateDefinition,
                 block_type: BlockType,
                 parent: QtWidgets.QWidget | None = None,
                 dark_theme: bool = False) -> None:
        """Build the block-specific lookup editor from its own Designer form.

        :param builder: Detached lookup builder owned by Block Properties.
        :param block_type: Concrete lookup variant controlling validation.
        :param parent: Owning Block Properties tab widget.
        :param dark_theme: Whether the chart uses the dark application palette.
        :return: None.
        """
        SpecialConfigTabWidget.__init__(
            self,
            builder=builder,
            tab_title=QtCore.QCoreApplication.translate(
                "SpecialConfigTabs",
                "Table configuration",
            ),
            parent=parent,
        )
        self.ui: Ui_Lookup1DConfigTab = Ui_Lookup1DConfigTab()
        self.ui.setupUi(self)
        self._block_type: BlockType = block_type
        self._table_model: Lookup1DTableModel = Lookup1DTableModel(
            points=get_lookup_1d_builder_points(builder),
            parent=self,
        )
        self._shortcuts: list[QtGui.QShortcut] = list()

        # The model/view table stretches both numeric columns evenly, while the
        # chart receives most of the horizontal space like the Q-curve editor.
        self.ui.points_table.setModel(self._table_model)
        self.ui.points_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.ui.content_splitter.setStretchFactor(0, 2)
        self.ui.content_splitter.setStretchFactor(1, 3)
        self._load_generator_limits_from_points()

        # Configure the chart once; data replacements below automatically
        # recalculate both axis ranges as rows are edited, added, or removed.
        self.ui.plotter.apply_theme(dark=dark_theme)
        self.ui.plotter.setTitle(self.tr("Lookup curve"))
        self.ui.plotter.set_axis_titles("x", "y")
        self.ui.plotter.set_legend_visible(False)
        self.ui.plotter.set_tight_axis_layout(True)

        self.ui.add_row_button.clicked.connect(self.add_point)
        self.ui.remove_rows_button.clicked.connect(self.remove_selected_points)
        self.ui.sort_button.clicked.connect(self.sort_points)
        self.ui.generate_function_button.clicked.connect(self.generate_function_points)
        self._table_model.draftChanged.connect(self._on_draft_changed)
        self._install_shortcuts()
        self._refresh_plot()

    def _load_generator_limits_from_points(self) -> None:
        """Initialize generator limits from the current lookup point table.

        :return: None.
        """
        points: tuple[tuple[float, float], ...] = self._table_model.get_points()
        point_count: int = len(points)
        if point_count >= 2:
            self.ui.function_x_minimum_spin_box.setValue(points[0][0])
            self.ui.function_x_maximum_spin_box.setValue(points[point_count - 1][0])
            self.ui.function_point_count_spin_box.setValue(point_count)
        else:
            pass

    def _install_shortcuts(self) -> None:
        """Install the table row-removal shortcut.

        :return: None.
        """
        delete_shortcut: QtGui.QShortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Delete),
            self.ui.points_table,
        )
        delete_shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        delete_shortcut.activated.connect(self.remove_selected_points)
        self._shortcuts.append(delete_shortcut)

    @QtCore.Slot()
    def _on_draft_changed(self) -> None:
        """Refresh the chart and propagate the transaction dirty state.

        :return: None.
        """
        self._refresh_plot()
        self.draftChanged.emit()

    def _refresh_plot(self) -> None:
        """Render the current rows as a line plus visible lookup points.

        :return: None.
        """
        points: tuple[tuple[float, float], ...] = self._table_model.get_points()
        point_count: int = len(points)
        x_values: np.ndarray = np.empty(point_count, dtype=float)
        y_values: np.ndarray = np.empty(point_count, dtype=float)
        point_index: int
        for point_index in range(point_count):
            x_values[point_index] = points[point_index][0]
            y_values[point_index] = points[point_index][1]

        series_data: list[tuple[np.ndarray, np.ndarray, str | None]] = list((
            (x_values, y_values, "#2563eb"),
            (x_values, y_values, "#2563eb"),
        ))
        updated: bool = self.ui.plotter.replace_xy_series_data(series_data)
        if updated:
            pass
        else:
            self.ui.plotter.clear()
            self.ui.plotter.add_line_series(
                name="",
                x_values=x_values,
                y_values=y_values,
                color="#2563eb",
            )
            self.ui.plotter.add_scatter_series(
                name="",
                x_values=x_values,
                y_values=y_values,
                color="#2563eb",
            )
        self.ui.plotter.setTitle(self.tr("Lookup curve"))
        self.ui.plotter.set_axis_titles("x", "y")
        self.ui.plotter.set_legend_visible(False)
        self.ui.plotter.set_tight_axis_layout(True)
        self.ui.plotter.reset_viewport()
        self.ui.plotter.redraw()

    @QtCore.Slot()
    def add_point(self) -> None:
        """Append one point while preserving a valid x interval by default.

        :return: None.
        """
        self._table_model.add_point()
        last_row: int = self._table_model.rowCount() - 1
        if last_row >= 0:
            self.ui.points_table.setCurrentIndex(self._table_model.index(last_row, 0))
        else:
            pass

    @QtCore.Slot()
    def remove_selected_points(self) -> None:
        """Remove rows containing selected cells, or the final row otherwise.

        :return: None.
        """
        selected_indexes: list[QtCore.QModelIndex] = list(
            self.ui.points_table.selectedIndexes()
        )
        selected_rows: set[int] = set()
        selected_index: QtCore.QModelIndex
        for selected_index in selected_indexes:
            selected_rows.add(selected_index.row())
        if len(selected_rows) == 0 and self._table_model.rowCount() > 0:
            selected_rows.add(self._table_model.rowCount() - 1)
        else:
            pass
        self._table_model.remove_rows_by_index(tuple(selected_rows))

    @QtCore.Slot()
    def sort_points(self) -> None:
        """Sort table rows by x without changing x/y associations.

        :return: None.
        """
        self._table_model.sort_by_x()

    @QtCore.Slot()
    def generate_function_points(self) -> None:
        """Replace the draft with evenly sampled points from ``f(x)``.

        Invalid expressions leave the current table untouched and display the
        parser or evaluation problem beside the generator controls.

        :return: None.
        """
        generated_result: tuple[
            tuple[tuple[float, float], ...],
            str | None,
        ] = generate_curve_points_from_expression(
            expression_text=self.ui.function_expression_line_edit.text(),
            x_minimum=self.ui.function_x_minimum_spin_box.value(),
            x_maximum=self.ui.function_x_maximum_spin_box.value(),
            point_count=self.ui.function_point_count_spin_box.value(),
        )
        generated_points: tuple[tuple[float, float], ...] = generated_result[0]
        validation_error: str | None = generated_result[1]
        if validation_error is None:
            self.ui.function_error_label.clear()
            self._table_model.replace_points(generated_points)
        else:
            self.ui.function_error_label.setText(validation_error)

    def has_changes(self) -> bool:
        """Return whether lookup points differ from the accepted builder state.

        :return: Whether this tab owns pending edits.
        """
        return self._table_model.has_changes()

    def get_validation_error(self) -> str | None:
        """Validate the table for its concrete lookup variant.

        :return: First actionable error, or ``None`` when the table is valid.
        """
        points_property: TemplateProp | None = self.get_builder().params_dict.get(
            "points",
            None,
        )
        if points_property is None:
            result: str | None = self.tr(
                "This lookup builder does not expose a points configuration."
            )
        else:
            result = self._table_model.get_validation_error(
                strictly_monotonic_y=self._block_type == BlockType.INVERSE_LOOKUP_ARRAY
            )
        return result

    def apply_draft_to_builder(self) -> None:
        """Copy validated points into the detached lookup builder.

        The clean baseline is intentionally not advanced here. Block
        Properties reloads it only after the structural rebuild succeeds.

        :return: None.
        """
        points_property: TemplateProp | None = self.get_builder().params_dict.get(
            "points",
            None,
        )
        if points_property is not None:
            points_property.value = self._table_model.get_points()
        else:
            pass

    def reload_from_builder(self) -> None:
        """Reload accepted points after a successful structural rebuild.

        :return: None.
        """
        self._table_model.reload(get_lookup_1d_builder_points(self.get_builder()))
        self._load_generator_limits_from_points()
        self.ui.function_error_label.clear()
        self._refresh_plot()

    def set_read_only(self, read_only: bool) -> None:
        """Disable both controls and model editing for provider-owned blocks.

        :param read_only: Whether editing must be disabled.
        :return: None.
        """
        SpecialConfigTabWidget.set_read_only(self, read_only)
        self._table_model.set_read_only(read_only)

    def prepare_to_delete(self) -> None:
        """Release the chart, shortcuts, and table model before parent deletion.

        :return: None.
        """
        if self.is_prepared_to_delete():
            pass
        else:
            self.ui.add_row_button.clicked.disconnect(self.add_point)
            self.ui.remove_rows_button.clicked.disconnect(self.remove_selected_points)
            self.ui.sort_button.clicked.disconnect(self.sort_points)
            self.ui.generate_function_button.clicked.disconnect(self.generate_function_points)
            self._table_model.draftChanged.disconnect(self._on_draft_changed)
            shortcut: QtGui.QShortcut
            for shortcut in self._shortcuts:
                shortcut.setEnabled(False)
                shortcut.deleteLater()
            self._shortcuts.clear()
            self.ui.points_table.setModel(None)
            self.ui.plotter.dispose()
            self._table_model.deleteLater()
            SpecialConfigTabWidget.prepare_to_delete(self)
