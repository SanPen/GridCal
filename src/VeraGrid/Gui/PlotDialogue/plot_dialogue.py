# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Reusable native Qt plot window and its small public plotting API."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.dialog_lifecycle import is_dialog_available
from VeraGrid.Gui.PlotDialogue.plot_dialogue_ui import Ui_PlotDialogue
from VeraGrid.Gui.PlotDialogue.plot_export import save_chart_image
from VeraGrid.Gui.PlotDialogue.qt_chart_widget import ChartContentType, ChartSeries, GraphsWidget, PolarAngleUnit


class PlotSeries:
    """Retain one selectable time series for the lifetime of a plot dialog."""

    __slots__ = ('group', 'unit', 'name', 'x_values', 'y_values', 'color')

    def __init__(self,
                 group: str,
                 unit: str,
                 name: str,
                 x_values: np.ndarray,
                 y_values: np.ndarray,
                 color: str) -> None:
        """Copy one candidate series so source result tables may be released.

        :param group: Source category displayed in the shared tree.
        :param unit: Y axis unit required by this series.
        :param name: Visible series name.
        :param x_values: Time or numeric coordinates.
        :param y_values: Numeric series values.
        :param color: Stable chart palette colour used by the tree label.
        :return: None.
        """
        self.group: str = group
        self.unit: str = unit
        self.name: str = name
        self.x_values: np.ndarray = np.asarray(x_values).copy()
        self.y_values: np.ndarray = np.asarray(y_values, dtype=float).copy()
        self.color: str = color


class PlotDialogue(QtWidgets.QMainWindow):
    """Own one or more native QWidget charts in explicitly owned Qt tabs."""

    __slots__ = ('ui', 'chart', '_tab_charts', '_series_selector_override',
                 '_use_rhi_for_many_series', '_series_catalog', '_plot_series_indices',
                 '_series_catalog_enabled', '_series_tree_initialized', '_active_save_dialog',
                 '_closed')

    def __init__(self,
                 title: str = 'Plot',
                 parent: QtWidgets.QWidget | None = None,
                 use_rhi_for_many_series: bool = False) -> None:
        """Create the retained chart dialog and its Qt-owned child hierarchy.

        :param title: Initial dialog and chart title.
        :param parent: Optional Qt owner for the complete dialog hierarchy.
        :param use_rhi_for_many_series: Whether dense XY lines and cumulative areas may use QRhi.
        :return: None.
        """
        QtWidgets.QMainWindow.__init__(self, parent)
        # Closed plots are disposable: Qt must destroy their complete child hierarchy.
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.ui: Ui_PlotDialogue = Ui_PlotDialogue()
        self.ui.setupUi(self)
        self.setWindowFlags(
            self.windowFlags()
            | QtCore.Qt.WindowType.CustomizeWindowHint
            | QtCore.Qt.WindowType.WindowMaximizeButtonHint
        )
        self.chart: GraphsWidget = self.ui.plotwidget
        self._tab_charts: list[GraphsWidget] = [self.chart]
        self._series_selector_override: bool | None = None
        self._use_rhi_for_many_series: bool = use_rhi_for_many_series
        self._series_catalog: list[PlotSeries] = list()
        self._plot_series_indices: list[list[int]] = [list()]
        self._series_catalog_enabled: bool = False
        self._series_tree_initialized: bool = False
        self._active_save_dialog: QtWidgets.QFileDialog | None = None
        self._closed: bool = False
        self.chart.set_rhi_line_rendering(enabled=use_rhi_for_many_series)
        self.ui.plotSplitter.setStretchFactor(0, 0)
        self.ui.plotSplitter.setStretchFactor(1, 1)
        self.ui.seriesSelectorFrame.setMaximumWidth(360)
        self.setWindowTitle(title)
        self.chart.setTitle(title)

        # All callbacks are delivered in this dialog's GUI thread; no worker
        # or queued ownership crosses the chart lifetime boundary.
        self.ui.actionSaveImage.triggered.connect(self.save_image)
        self.ui.actionResetView.triggered.connect(self.center_data)
        self.ui.actionopencloseTree.triggered.connect(self._toggle_series_selector)
        self.ui.plotTabs.currentChanged.connect(self._refresh_series_selector)
        self.ui.seriesSearchLineEdit.textChanged.connect(self._filter_series_selector)
        self.ui.seriesTreeWidget.itemChanged.connect(self._set_series_visibility)
        self.ui.selectAllButton.clicked.connect(self.select_all_series)
        self.ui.selectNoneButton.clicked.connect(self.select_no_series)
        self.ui.actionCDF.toggled.connect(self._transform_current_plot)
        self.ui.actionAbs.toggled.connect(self._transform_current_plot)
        self.ui.actionTranspose.toggled.connect(self._transform_current_plot)
        self.ui.actionStacked_plot.toggled.connect(self._transform_current_plot)
        self.ui.actionBar_plot.toggled.connect(self._transform_current_plot)
        self.ui.actionx_y.triggered.connect(self._create_xy_plot)
        self.ui.actionAddPlot.triggered.connect(self._add_plot_from_toolbar)
        self.ui.plotTabs.tabCloseRequested.connect(self._close_plot_tab)

    def open_from_context_menu(self) -> None:
        """Present the retained window after the native context menu unwinds."""
        QtCore.QTimer.singleShot(0, self, self._show_and_activate)

    def _show_and_activate(self) -> None:
        """Bring the plot forward unless it was closed before delivery."""
        if not self._closed:
            self.show()
            self.raise_()
            self.activateWindow()

    def done(self, result: int) -> None:
        """Release every tab buffer before Qt tears down the parent-child widgets.

        :param result: Qt dialog result code.
        :return: None.
        """
        self._release_plot_resources()
        _ = result
        QtWidgets.QMainWindow.close(self)

    def _release_plot_resources(self) -> None:
        """Release chart and auxiliary dialog resources exactly once.

        :return: None.
        """
        if not self._closed:
            self._closed = True
            # Stop tree callbacks before Qt destroys its child items with this dialog.
            self.ui.seriesTreeWidget.blockSignals(True)
            self.ui.seriesTreeWidget.clear()
            self.ui.seriesTreeWidget.blockSignals(False)
            self.ui.seriesSelectorFrame.setVisible(False)
            save_dialog: QtWidgets.QFileDialog | None = self._active_save_dialog
            self._active_save_dialog = None
            if save_dialog is not None:
                if is_dialog_available(save_dialog):
                    # Prevent picker callbacks from reentering a plot during teardown.
                    save_dialog.blockSignals(True)
                    save_dialog.close()
            chart: GraphsWidget
            for chart in self._tab_charts:
                chart.dispose()
            self._tab_charts.clear()
            self._plot_series_indices.clear()
            self._series_catalog.clear()
        else:
            pass

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Release plot resources when the native close button is used.

        :param event: Qt close event delivered by the window system.
        :return: None.
        """
        # Stop tree callbacks before Qt destroys its child items with this dialog.
        self._release_plot_resources()
        QtWidgets.QMainWindow.closeEvent(self, event)

    def reject(self) -> None:
        """Close the plot window through the dialog-compatible API.

        :return: None.
        """
        self.done(0)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """Refresh the optional series selector before Qt makes the dialog visible.

        :param event: Qt visibility event delivered on the dialog owner thread.
        :return: None.
        """
        self._refresh_series_selector()
        QtWidgets.QMainWindow.showEvent(self, event)

    def get_current_chart(self) -> GraphsWidget:
        """Return the chart owned by the currently selected tab.

        :return: Current tab chart, or the initial chart when no tab is selected.
        """
        current_index: int = self.ui.plotTabs.currentIndex()
        if 0 <= current_index < len(self._tab_charts):
            return self._tab_charts[current_index]
        else:
            return self.chart

    def add_tab(self, title: str) -> GraphsWidget:
        """Create one additional Qt-owned chart tab and make it current.

        :param title: Text displayed in the new tab.
        :return: Newly owned chart widget for the tab.
        """
        tab_page: QtWidgets.QWidget = QtWidgets.QWidget(parent=self.ui.plotTabs)
        tab_layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(tab_page)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_chart: GraphsWidget = GraphsWidget(parent=tab_page)
        tab_chart.set_rhi_line_rendering(enabled=self._use_rhi_for_many_series)
        tab_layout.addWidget(tab_chart)
        self._tab_charts.append(tab_chart)
        self._plot_series_indices.append(list())
        tab_index: int = self.ui.plotTabs.addTab(tab_page, title)
        self.ui.plotTabs.setCurrentIndex(tab_index)
        self._refresh_series_selector()
        return tab_chart

    def _add_plot_from_toolbar(self, checked: bool = False) -> None:
        """Duplicate the active plot into an independently editable tab.

        :param checked: QAction state, unused by this momentary action.
        :return: None.
        """
        _ = checked
        source: GraphsWidget = self.get_current_chart()
        source_index: int = self.ui.plotTabs.currentIndex()
        title: str = self.ui.plotTabs.tabText(source_index)
        target: GraphsWidget = self.add_tab(title=self.tr('{title} copy').format(title=title))
        source.copy_plot_to(target)
        self._plot_series_indices[-1] = self._plot_series_indices[source_index].copy()
        self._refresh_series_selector()

    def _transform_current_plot(self, checked: bool = False) -> None:
        """Apply the toolbar switches to the active plot.

        :param checked: Emitted switch state; the actions supply the full state.
        :return: None.
        """
        # Stacked areas and categorical bars are alternative views of the same signals.
        sender: QtCore.QObject | None = self.sender()
        actions_to_clear: list[QtGui.QAction] = list()
        if checked and sender == self.ui.actionStacked_plot:
            actions_to_clear = [self.ui.actionBar_plot, self.ui.actionTranspose]
        elif checked and sender == self.ui.actionBar_plot:
            actions_to_clear = [self.ui.actionStacked_plot, self.ui.actionTranspose, self.ui.actionCDF]
        else:
            pass
        action: QtGui.QAction
        for action in actions_to_clear:
            action.blockSignals(True)
            action.setChecked(False)
            action.blockSignals(False)
        accepted: bool = self.get_current_chart().set_value_transforms(
            cdf=self.ui.actionCDF.isChecked(), absolute=self.ui.actionAbs.isChecked(),
            transpose=self.ui.actionTranspose.isChecked(),
            stacked=self.ui.actionStacked_plot.isChecked(), bar=self.ui.actionBar_plot.isChecked())
        self._refresh_series_selector()
        if not accepted:
            QtWidgets.QMessageBox.information(self, self.tr('Plot view'),
                                              self.tr('This view needs nonempty series with matching sample coordinates.'))
        else:
            pass

    def _create_xy_plot(self, checked: bool = False) -> None:
        """Ask for two stored signals and plot their paired values in a new tab.

        :param checked: Unused momentary action state.
        :return: None.
        """
        _ = checked
        chart: GraphsWidget = self.get_current_chart()
        if chart._content_type != ChartContentType.XY or chart.get_series_count() < 2:
            QtWidgets.QMessageBox.information(self, self.tr('X,Y plot'),
                                              self.tr('The current plot needs at least two XY series.'))
            return
        else:
            pass
        picker: QtWidgets.QDialog = QtWidgets.QDialog(self)
        picker.setWindowTitle(self.tr('Select X and Y series'))
        layout: QtWidgets.QFormLayout = QtWidgets.QFormLayout(picker)
        x_selector: QtWidgets.QComboBox = QtWidgets.QComboBox(picker)
        y_selector: QtWidgets.QComboBox = QtWidgets.QComboBox(picker)
        series_index: int
        for series_index in range(chart.get_series_count()):
            label: str = f'{series_index + 1}: {chart.get_series_name(series_index)}'
            x_selector.addItem(label)
            y_selector.addItem(label)
        y_selector.setCurrentIndex(1)
        layout.addRow(self.tr('X'), x_selector)
        layout.addRow(self.tr('Y'), y_selector)
        buttons: QtWidgets.QDialogButtonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=picker)
        buttons.accepted.connect(picker.accept)
        buttons.rejected.connect(picker.reject)
        layout.addRow(buttons)
        result: int = picker.exec()
        # The nested event loop may have destroyed the plot and its picker.
        if is_dialog_available(self) and not self._closed and is_dialog_available(picker):
            if result == QtWidgets.QDialog.DialogCode.Accepted:
                self.create_xy_plot(x_selector.currentIndex(), y_selector.currentIndex())
            else:
                pass
        else:
            pass
        if is_dialog_available(picker):
            picker.deleteLater()
        else:
            pass

    def create_xy_plot(self, x_index: int, y_index: int) -> bool:
        """Create a new scatter tab when the chosen signals share sample coordinates.

        :param x_index: Active chart series supplying horizontal values.
        :param y_index: Active chart series supplying vertical values.
        :return: Whether a new plot was created.
        """
        chart: GraphsWidget = self.get_current_chart()
        if (chart._content_type == ChartContentType.XY
                and 0 <= x_index < chart.get_series_count()
                and 0 <= y_index < chart.get_series_count()):
            x_series: ChartSeries = chart._series[x_index]
            y_series: ChartSeries = chart._series[y_index]
            if np.array_equal(x_series.get_x_data(), y_series.get_x_data()) and x_series.get_x_data().size > 0:
                target: GraphsWidget = self.add_tab(self.tr('X,Y plot'))
                target._catalog_detached = True
                self.set_scatter_series(x_series.get_y_data(), [y_series.get_name()],
                                        [y_series.get_y_data()], [y_series.get_color().name()],
                                        x_axis_title=x_series.get_name(), y_axis_title=y_series.get_name())
                return True
            else:
                QtWidgets.QMessageBox.information(self, self.tr('X,Y plot'),
                                                  self.tr('Choose series with matching sample coordinates.'))
        else:
            pass
        return False

    def _close_plot_tab(self, tab_index: int) -> None:
        """Dispose a chart before removing its Qt-owned tab page.

        :param tab_index: Requested tab index from QTabWidget.
        :return: None.
        """
        if 0 <= tab_index < len(self._tab_charts) and len(self._tab_charts) > 1:
            chart: GraphsWidget = self._tab_charts.pop(tab_index)
            self._plot_series_indices.pop(tab_index)
            chart.dispose()
            tab_page: QtWidgets.QWidget | None = self.ui.plotTabs.widget(tab_index)
            self.ui.plotTabs.removeTab(tab_index)
            if tab_page is not None:
                tab_page.deleteLater()
            else:
                pass
            self.chart = self._tab_charts[0]
            self._refresh_series_selector()
        else:
            pass

    def set_current_tab_title(self, title: str) -> None:
        """Set the visible name of the selected plot tab.

        :param title: New text for the selected tab.
        :return: None.
        """
        tab_index: int = self.ui.plotTabs.currentIndex()
        if tab_index >= 0:
            self.ui.plotTabs.setTabText(tab_index, title)
        else:
            pass

    def register_time_series(self,
                             group: str,
                             unit: str,
                             x_values: Sequence[float] | np.ndarray,
                             series_names: Sequence[str],
                             series_values: Sequence[Sequence[float] | np.ndarray]) -> None:
        """Add selectable series to the dialog-wide tree without opening a tab.

        :param group: Source category such as profile inputs or OPF results.
        :param unit: Shared Y axis unit for these candidate series.
        :param x_values: Time or numeric coordinates shared by the series.
        :param series_names: Candidate series names.
        :param series_values: Candidate numeric values.
        :return: None.
        """
        self._series_catalog_enabled = True
        if len(series_names) == len(series_values):
            series_index: int
            for series_index in range(len(series_names)):
                candidate: PlotSeries = PlotSeries(
                    group=group,
                    unit=unit,
                    name=series_names[series_index],
                    x_values=np.asarray(x_values),
                    y_values=np.asarray(series_values[series_index]),
                    color=self.chart.make_series_color(
                        color_name=None,
                        series_index=len(self._series_catalog),
                    ).name(),
                )
                if (candidate.x_values.ndim == 1 and candidate.y_values.ndim == 1
                        and candidate.x_values.size > 0
                        and candidate.x_values.size == candidate.y_values.size
                        and bool(np.any(np.isfinite(candidate.y_values)))):
                    self._series_catalog.append(candidate)
                    self._series_tree_initialized = False
                else:
                    pass
        else:
            pass

    def select_default_catalog_series(self) -> bool:
        """Plot the first available power unit, falling back to the first unit.

        :return: Whether at least one candidate series was selected.
        """
        default_series: PlotSeries | None = None
        candidate: PlotSeries
        for candidate in self._series_catalog:
            if default_series is None:
                default_series = candidate
            else:
                pass
            if candidate.unit.casefold() in ('mw', 'kw', 'w'):
                default_series = candidate
                break
            else:
                pass
        selected_indices: list[int] = list()
        if default_series is not None:
            series_index: int
            for series_index in range(len(self._series_catalog)):
                candidate = self._series_catalog[series_index]
                if (candidate.unit == default_series.unit
                        and bool(np.array_equal(candidate.x_values, default_series.x_values))):
                    selected_indices.append(series_index)
                else:
                    pass
        else:
            pass
        if len(selected_indices) > 0:
            self._series_catalog_enabled = True
            self._plot_series_indices[self.ui.plotTabs.currentIndex()] = selected_indices
            default_title: str = default_series.unit if default_series is not None else self.tr('Plot')
            self.set_current_tab_title(title=default_title if default_title != '' else self.tr('Plot'))
            self._rebuild_catalog_chart()
            return True
        else:
            return False

    def _rebuild_catalog_chart(self) -> None:
        """Replace the selected chart from its catalog membership in one mutation.

        :return: None.
        """
        tab_index: int = self.ui.plotTabs.currentIndex()
        if 0 <= tab_index < len(self._plot_series_indices):
            selected_indices: list[int] = self._plot_series_indices[tab_index]
            if len(selected_indices) > 0:
                first_series: PlotSeries = self._series_catalog[selected_indices[0]]
                x_values: np.ndarray = first_series.x_values
                series_names: list[str] = list()
                series_values: list[np.ndarray] = list()
                series_colors: list[str] = list()
                series_index: int
                for series_index in selected_indices:
                    candidate: PlotSeries = self._series_catalog[series_index]
                    series_names.append(candidate.name)
                    series_values.append(candidate.y_values)
                    series_colors.append(candidate.color)
                chart: GraphsWidget = self.get_current_chart()
                cdf: bool = chart._cdf_enabled
                absolute: bool = chart._abs_enabled
                transpose: bool = chart._transpose_enabled
                stacked: bool = chart._stacked_enabled
                bar: bool = chart._bar_enabled
                if chart.set_line_series(
                        x_values=x_values,
                        series_names=series_names,
                        series_values=series_values,
                        colors=series_colors):
                    chart.set_axis_titles(self.tr('Time'), first_series.unit)
                    chart.setTitle(self.windowTitle())
                    if cdf or absolute or transpose or stacked or bar:
                        chart.set_value_transforms(cdf, absolute, transpose, stacked, bar)
                    else:
                        pass
                else:
                    pass
            else:
                self.get_current_chart().clear()
            self._refresh_series_selector()
        else:
            pass

    def set_line_series(self,
                        x_values: Sequence[float] | np.ndarray,
                        series_names: Sequence[str],
                        series_values: Sequence[Sequence[float] | np.ndarray],
                        colors: Sequence[str | None] | None = None,
                        title: str = '',
                        x_axis_title: str = '',
                        y_axis_title: str = '') -> bool:
        """Replace the chart with one or more line series sharing an X axis.

        :param x_values: Numeric or NumPy datetime coordinates.
        :param series_names: Visible legend name for each line.
        :param series_values: Y value buffer for each line.
        :param colors: Optional Qt colour for each line.
        :param title: Visible plot title.
        :param x_axis_title: Horizontal axis caption.
        :param y_axis_title: Vertical axis caption.
        :return: Whether every buffer was shape-compatible.
        """
        chart: GraphsWidget = self.get_current_chart()
        accepted: bool = chart.set_line_series(
            x_values=x_values,
            series_names=series_names,
            series_values=series_values,
            colors=colors,
        )
        if accepted:
            chart.setTitle(title)
            chart.set_axis_titles(x_axis_title, y_axis_title)
            self._refresh_series_selector()
            return True
        else:
            return False

    def set_time_series(self,
                        time_values: Sequence[float] | np.ndarray,
                        series_names: Sequence[str],
                        series_values: Sequence[Sequence[float] | np.ndarray],
                        colors: Sequence[str | None] | None = None,
                        title: str = '',
                        y_axis_title: str = '') -> bool:
        """Replace the chart with lines using a NumPy datetime X axis.

        :param time_values: NumPy datetime coordinates or numeric timestamps.
        :param series_names: Visible legend name for each line.
        :param series_values: Y value buffer for each line.
        :param colors: Optional Qt colour for each line.
        :param title: Visible plot title.
        :param y_axis_title: Vertical axis caption.
        :return: Whether every buffer was shape-compatible.
        """
        return self.set_line_series(
            x_values=time_values,
            series_names=series_names,
            series_values=series_values,
            colors=colors,
            title=title,
            x_axis_title=self.tr('Time'),
            y_axis_title=y_axis_title,
        )

    def set_scatter_series(self,
                           x_values: Sequence[float] | np.ndarray,
                           series_names: Sequence[str],
                           series_values: Sequence[Sequence[float] | np.ndarray],
                           colors: Sequence[str | None] | None = None,
                           point_tooltips: Sequence[Sequence[str] | None] | None = None,
                           title: str = '',
                           x_axis_title: str = '',
                           y_axis_title: str = '') -> bool:
        """Replace the selected tab with unconnected XY point series.

        :param x_values: Horizontal numeric coordinates shared by every series.
        :param series_names: Visible legend name for each point series.
        :param series_values: Vertical values paired with each series name.
        :param colors: Optional Qt colour for each series.
        :param point_tooltips: Optional hover text for each series point.
        :param title: Visible plot title.
        :param x_axis_title: Horizontal axis caption.
        :param y_axis_title: Vertical axis caption.
        :return: Whether every input buffer was accepted.
        """
        chart: GraphsWidget = self.get_current_chart()
        accepted: bool = chart.set_scatter_series(
            x_values=x_values,
            series_names=series_names,
            series_values=series_values,
            colors=colors,
            point_tooltips=point_tooltips,
        )
        if accepted:
            chart.setTitle(title)
            chart.set_axis_titles(x_axis_title, y_axis_title)
            self._refresh_series_selector()
        else:
            pass
        return accepted

    def set_cumulative_area_series(self,
                                   x_values: Sequence[float] | np.ndarray,
                                   series_names: Sequence[str],
                                   series_values: Sequence[Sequence[float] | np.ndarray],
                                   colors: Sequence[str | None] | None = None,
                                   title: str = '',
                                   x_axis_title: str = '',
                                   y_axis_title: str = '') -> bool:
        """Replace the chart with stacked cumulative areas sharing one X axis.

        :param x_values: Numeric or NumPy datetime coordinates.
        :param series_names: Visible legend name for each cumulative band.
        :param series_values: Y value buffer for each cumulative band.
        :param colors: Optional Qt colour for each band.
        :param title: Visible plot title.
        :param x_axis_title: Horizontal axis caption.
        :param y_axis_title: Vertical axis caption.
        :return: Whether the native chart accepted every finite buffer.
        """
        chart: GraphsWidget = self.get_current_chart()
        accepted: bool = chart.set_cumulative_area_series(
            x_values=x_values,
            series_names=series_names,
            series_values=series_values,
            colors=colors,
        )
        if accepted:
            chart.setTitle(title)
            chart.set_axis_titles(x_axis_title, y_axis_title)
            self._refresh_series_selector()
        else:
            pass
        return accepted

    def set_polar_series(self,
                         series_names: Sequence[str],
                         angle_values: Sequence[Sequence[float] | np.ndarray],
                         radius_values: Sequence[Sequence[float] | np.ndarray],
                         colors: Sequence[str | None] | None = None,
                         title: str = '',
                         radius_title: str = '',
                         angle_unit: PolarAngleUnit = PolarAngleUnit.RADIANS,
                         connect_points: bool = True) -> bool:
        """Replace the chart with native polar lines and circular sample points.

        :param series_names: Visible legend name for each polar line.
        :param angle_values: Angle buffer for each series.
        :param radius_values: Non-negative radial buffer for each series.
        :param colors: Optional Qt colour for each polar line.
        :param title: Visible plot title.
        :param radius_title: Radial axis caption.
        :param angle_unit: Unit used by every angle buffer.
        :param connect_points: Whether consecutive polar samples are joined.
        :return: Whether the native chart accepted every finite buffer.
        """
        chart: GraphsWidget = self.get_current_chart()
        accepted: bool = chart.set_polar_series(
            series_names=series_names,
            angle_values=angle_values,
            radius_values=radius_values,
            colors=colors,
            angle_unit=angle_unit,
            connect_points=connect_points,
        )
        if accepted:
            chart.setTitle(title)
            chart.set_axis_titles('', radius_title)
            self._refresh_series_selector()
        else:
            pass
        return accepted

    def set_histogram(self,
                      values: Sequence[float] | np.ndarray,
                      bin_count: int,
                      title: str = '',
                      x_axis_title: str = '',
                      y_axis_title: str = '') -> bool:
        """Replace the selected tab with one native numeric histogram.

        :param values: Numeric samples from which bin frequencies are calculated.
        :param bin_count: Positive number of equal-width bins.
        :param title: Visible chart title.
        :param x_axis_title: Horizontal numeric axis caption.
        :param y_axis_title: Vertical frequency axis caption.
        :return: Whether the chart accepted the complete finite sample set.
        """
        chart: GraphsWidget = self.get_current_chart()
        accepted: bool = chart.set_histogram(
            values=values,
            bin_count=bin_count,
            name='',
        )
        if accepted:
            chart.setTitle(title)
            chart.set_axis_titles(x_axis_title, y_axis_title)
            self._refresh_series_selector()
        else:
            pass
        return accepted

    def add_histogram_tab(self,
                          tab_title: str,
                          values: Sequence[float] | np.ndarray,
                          bin_count: int,
                          title: str = '',
                          x_axis_title: str = '',
                          y_axis_title: str = '') -> bool:
        """Create a tab that owns one native numeric histogram.

        :param tab_title: Text displayed for the new tab.
        :param values: Numeric samples from which bin frequencies are calculated.
        :param bin_count: Positive number of equal-width bins.
        :param title: Visible chart title.
        :param x_axis_title: Horizontal numeric axis caption.
        :param y_axis_title: Vertical frequency axis caption.
        :return: Whether the new tab chart accepted the complete finite sample set.
        """
        tab_chart: GraphsWidget = self.add_tab(title=tab_title)
        accepted: bool = tab_chart.set_histogram(
            values=values,
            bin_count=bin_count,
            name='',
        )
        if accepted:
            tab_chart.setTitle(title)
            tab_chart.set_axis_titles(x_axis_title, y_axis_title)
            self._refresh_series_selector()
            return True
        else:
            return False

    def _refresh_series_selector(self, current_index: int = -1) -> None:
        """Show a coloured searchable legend only for charts with many named series.

        :param current_index: Tab index provided by Qt and otherwise unused.
        :return: None.
        """
        _ = current_index
        active_chart: GraphsWidget = self.get_current_chart()
        supports_views: bool = active_chart._content_type in (ChartContentType.XY, ChartContentType.CUMULATIVE_AREA)
        self.ui.actionCDF.setEnabled(supports_views and not active_chart._bar_enabled)
        self.ui.actionAbs.setEnabled(supports_views)
        self.ui.actionTranspose.setEnabled(supports_views and not active_chart._bar_enabled
                                          and not active_chart._stacked_enabled)
        self.ui.actionStacked_plot.setEnabled(supports_views)
        self.ui.actionBar_plot.setEnabled(supports_views)
        self.ui.actionStacked_plot.blockSignals(True)
        self.ui.actionBar_plot.blockSignals(True)
        self.ui.actionStacked_plot.setChecked(active_chart._stacked_enabled)
        self.ui.actionBar_plot.setChecked(active_chart._bar_enabled)
        self.ui.actionStacked_plot.blockSignals(False)
        self.ui.actionBar_plot.blockSignals(False)
        self.ui.actionTranspose.blockSignals(True)
        self.ui.actionTranspose.setChecked(active_chart._transpose_enabled)
        self.ui.actionTranspose.blockSignals(False)
        self.ui.actionCDF.blockSignals(True)
        self.ui.actionAbs.blockSignals(True)
        self.ui.actionCDF.setChecked(active_chart._cdf_enabled)
        self.ui.actionAbs.setChecked(active_chart._abs_enabled)
        self.ui.actionCDF.blockSignals(False)
        self.ui.actionAbs.blockSignals(False)
        if self._series_catalog_enabled and not self.get_current_chart()._catalog_detached:
            self._refresh_catalog_tree()
            return
        else:
            pass
        chart: GraphsWidget = self.get_current_chart()
        named_series_count: int = 0
        series_index: int
        for series_index in range(chart.get_series_count()):
            if chart.get_series_name(series_index=series_index) != '':
                named_series_count += 1
            else:
                pass

        automatic_visibility: bool = named_series_count > 20
        selector_visible: bool = automatic_visibility
        if self._series_selector_override is not None:
            selector_visible = self._series_selector_override
        else:
            pass
        chart.set_legend_visible(visible=not selector_visible)
        self.ui.seriesSelectorFrame.setVisible(selector_visible)
        self.ui.actionopencloseTree.setChecked(selector_visible)
        self.ui.seriesTreeWidget.blockSignals(True)
        self.ui.seriesTreeWidget.clear()
        self._series_tree_initialized = False
        group_items: dict[str, QtWidgets.QTreeWidgetItem] = dict()
        for series_index in range(chart.get_series_count()):
            series_name: str = chart.get_series_name(series_index=series_index)
            if series_name != '':
                lowered_name: str = series_name.casefold()
                if "optimal power flow" in lowered_name or "opf" in lowered_name:
                    group_name: str = self.tr("OPF Time Series")
                elif "power flow" in lowered_name:
                    group_name = self.tr("Power Flow Time Series")
                elif self.ui.plotTabs.tabText(self.ui.plotTabs.currentIndex()).casefold().startswith("profiles"):
                    group_name = self.tr("Profile Inputs")
                else:
                    group_name = self.tr("Series")
                group_item: QtWidgets.QTreeWidgetItem | None = group_items.get(group_name, None)
                if group_item is None:
                    group_item = QtWidgets.QTreeWidgetItem(self.ui.seriesTreeWidget, [group_name])
                    group_items[group_name] = group_item
                else:
                    pass
                tree_item: QtWidgets.QTreeWidgetItem = QtWidgets.QTreeWidgetItem(group_item, [series_name])
                tree_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, series_index)
                tree_item.setFlags(tree_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                tree_item.setCheckState(
                    0,
                    QtCore.Qt.CheckState.Checked if chart.get_series_visible(series_index=series_index)
                    else QtCore.Qt.CheckState.Unchecked,
                )
                tree_item.setForeground(0, QtGui.QBrush(chart.get_series_color(series_index=series_index)))
            else:
                pass
        self.ui.seriesTreeWidget.expandAll()
        self.ui.seriesTreeWidget.blockSignals(False)
        self._filter_series_selector(text=self.ui.seriesSearchLineEdit.text())

    def _toggle_series_selector(self, visible: bool) -> None:
        """Apply the toolbar action's requested series-list visibility.

        :param visible: Checked state of the list visibility action.
        :return: None.
        """
        self._series_selector_override = visible
        self.ui.seriesSelectorFrame.setVisible(visible)
        chart: GraphsWidget = self.get_current_chart()
        if self._series_catalog_enabled and not self.get_current_chart()._catalog_detached:
            chart.set_legend_overlay(enabled=True)
            chart.set_legend_visible(visible=True)
        else:
            chart.set_legend_visible(visible=not visible)

    def set_series_selector_visible(self, visible: bool) -> None:
        """Set whether named series are controlled through the checkbox list.

        :param visible: Whether the searchable selector should be shown.
        :return: None.
        """
        self._series_selector_override = visible
        self.ui.seriesSelectorFrame.setVisible(visible)
        self.ui.actionopencloseTree.setChecked(visible)
        self._refresh_series_selector()

    def select_all_series(self, checked: bool = False) -> None:
        """Show every series currently listed for the selected chart.

        :param checked: Button state ignored by this momentary action.
        :return: None.
        """
        _ = checked
        self._set_all_series_visibility(visible=True)

    def select_no_series(self, checked: bool = False) -> None:
        """Hide every series currently listed for the selected chart.

        :param checked: Button state ignored by this momentary action.
        :return: None.
        """
        _ = checked
        self._set_all_series_visibility(visible=False)

    def _set_all_series_visibility(self, visible: bool) -> None:
        """Update tree check states and chart data without item callbacks per row.

        :param visible: Whether every named series should be rendered.
        :return: None.
        """
        if self._series_catalog_enabled and not self.get_current_chart()._catalog_detached:
            self._set_catalog_visibility(visible=visible)
            return
        else:
            pass
        chart: GraphsWidget = self.get_current_chart()
        self.ui.seriesTreeWidget.blockSignals(True)
        tree_item_index: int
        for tree_item_index in range(self.ui.seriesTreeWidget.topLevelItemCount()):
            group_item: QtWidgets.QTreeWidgetItem = self.ui.seriesTreeWidget.topLevelItem(tree_item_index)
            child_index: int
            for child_index in range(group_item.childCount()):
                tree_item: QtWidgets.QTreeWidgetItem = group_item.child(child_index)
                tree_item.setCheckState(0, QtCore.Qt.CheckState.Checked if visible
                                        else QtCore.Qt.CheckState.Unchecked)
                series_index_value: object = tree_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                if isinstance(series_index_value, int):
                    chart.set_series_visible(series_index=series_index_value, visible=visible)
                else:
                    pass
        self.ui.seriesTreeWidget.blockSignals(False)
        chart.update()
        self._filter_series_selector(text=self.ui.seriesSearchLineEdit.text())

    def _filter_series_selector(self, text: str) -> None:
        """Hide legend rows that do not match the user search text.

        :param text: Case-insensitive text that must occur in a series name.
        :return: None.
        """
        search_text: str = text.casefold()
        item_index: int
        for item_index in range(self.ui.seriesTreeWidget.topLevelItemCount()):
            group_item: QtWidgets.QTreeWidgetItem = self.ui.seriesTreeWidget.topLevelItem(item_index)
            has_visible_child: bool = False
            child_index: int
            for child_index in range(group_item.childCount()):
                parent_item: QtWidgets.QTreeWidgetItem = group_item.child(child_index)
                if parent_item.childCount() > 0:
                    has_visible_grandchild: bool = False
                    grandchild_index: int
                    for grandchild_index in range(parent_item.childCount()):
                        tree_item: QtWidgets.QTreeWidgetItem = parent_item.child(grandchild_index)
                        visible: bool = search_text in tree_item.text(0).casefold()
                        tree_item.setHidden(not visible)
                        has_visible_grandchild = has_visible_grandchild or visible
                    parent_item.setHidden(not has_visible_grandchild)
                    has_visible_child = has_visible_child or has_visible_grandchild
                else:
                    visible = search_text in parent_item.text(0).casefold()
                    parent_item.setHidden(not visible)
                    has_visible_child = has_visible_child or visible
            group_item.setHidden(not has_visible_child)

    def _set_series_visibility(self, tree_item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        """Apply one tree checkbox change to a chart series or complete group.

        :param tree_item: Qt-owned group or series row whose check state changed.
        :param column: Changed tree column.
        :return: None.
        """
        _ = column
        visible: bool = tree_item.checkState(0) == QtCore.Qt.CheckState.Checked
        if self._series_catalog_enabled and not self.get_current_chart()._catalog_detached:
            series_index_value: object = tree_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(series_index_value, int):
                self._set_catalog_series_visible(series_index=series_index_value, visible=visible)
            else:
                pass
            return
        else:
            pass
        chart: GraphsWidget = self.get_current_chart()
        if tree_item.parent() is None:
            self.ui.seriesTreeWidget.blockSignals(True)
            for child_index in range(tree_item.childCount()):
                child_item: QtWidgets.QTreeWidgetItem = tree_item.child(child_index)
                series_index_value: object = child_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                if isinstance(series_index_value, int):
                    chart.set_series_visible(series_index=series_index_value, visible=visible)
                else:
                    pass
                child_item.setCheckState(0, QtCore.Qt.CheckState.Checked if visible
                                         else QtCore.Qt.CheckState.Unchecked)
            self.ui.seriesTreeWidget.blockSignals(False)
        else:
            series_index_value = tree_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(series_index_value, int):
                chart.set_series_visible(series_index=series_index_value, visible=visible)
            else:
                pass
        chart.update()

    def _refresh_catalog_tree(self) -> None:
        """Build the shared source/unit tree once and update active-plot checks.

        :return: None.
        """
        chart: GraphsWidget = self.get_current_chart()
        selector_visible: bool = True
        if self._series_selector_override is not None:
            selector_visible = self._series_selector_override
        else:
            pass
        self.ui.seriesSelectorFrame.setVisible(selector_visible)
        self.ui.actionopencloseTree.setChecked(selector_visible)
        chart.set_legend_overlay(enabled=True)
        chart.set_legend_visible(visible=True)
        self.ui.seriesTreeWidget.blockSignals(True)
        if not self._series_tree_initialized:
            self.ui.seriesTreeWidget.clear()
            source_items: dict[str, QtWidgets.QTreeWidgetItem] = dict()
            unit_items: dict[tuple[str, str], QtWidgets.QTreeWidgetItem] = dict()
            series_index: int
            for series_index in range(len(self._series_catalog)):
                candidate: PlotSeries = self._series_catalog[series_index]
                source_item: QtWidgets.QTreeWidgetItem | None = source_items.get(candidate.group, None)
                if source_item is None:
                    source_item = QtWidgets.QTreeWidgetItem(self.ui.seriesTreeWidget, [candidate.group])
                    source_items[candidate.group] = source_item
                else:
                    pass
                unit_key: tuple[str, str] = (candidate.group, candidate.unit)
                unit_item: QtWidgets.QTreeWidgetItem | None = unit_items.get(unit_key, None)
                if unit_item is None:
                    unit_label: str = candidate.unit if candidate.unit != '' else self.tr('No unit')
                    unit_item = QtWidgets.QTreeWidgetItem(source_item, [unit_label])
                    unit_items[unit_key] = unit_item
                else:
                    pass
                tree_item: QtWidgets.QTreeWidgetItem = QtWidgets.QTreeWidgetItem(unit_item, [candidate.name])
                tree_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, series_index)
                tree_item.setFlags(tree_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                tree_item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
                tree_item.setForeground(0, QtGui.QBrush(QtGui.QColor(candidate.color)))
            self.ui.seriesTreeWidget.expandAll()
            self._series_tree_initialized = True
        else:
            pass
        tab_index: int = self.ui.plotTabs.currentIndex()
        selected_indices: list[int] = list()
        if 0 <= tab_index < len(self._plot_series_indices):
            selected_indices = self._plot_series_indices[tab_index]
        else:
            pass
        for item_index in range(self.ui.seriesTreeWidget.topLevelItemCount()):
            group_item: QtWidgets.QTreeWidgetItem = self.ui.seriesTreeWidget.topLevelItem(item_index)
            child_index: int
            for child_index in range(group_item.childCount()):
                unit_item = group_item.child(child_index)
                series_child_index: int
                for series_child_index in range(unit_item.childCount()):
                    tree_item = unit_item.child(series_child_index)
                    series_index_value: object = tree_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                    checked: bool = isinstance(series_index_value, int) and series_index_value in selected_indices
                    tree_item.setCheckState(0, QtCore.Qt.CheckState.Checked if checked
                                            else QtCore.Qt.CheckState.Unchecked)
        self.ui.seriesTreeWidget.blockSignals(False)
        self._filter_series_selector(text=self.ui.seriesSearchLineEdit.text())

    def _set_catalog_series_visible(self, series_index: int, visible: bool) -> None:
        """Add or remove one unit-compatible candidate from the active chart.

        :param series_index: Position in the dialog-wide source catalog.
        :param visible: Whether the candidate belongs to this plot.
        :return: None.
        """
        tab_index: int = self.ui.plotTabs.currentIndex()
        if 0 <= tab_index < len(self._plot_series_indices) and 0 <= series_index < len(self._series_catalog):
            selected_indices: list[int] = self._plot_series_indices[tab_index]
            candidate: PlotSeries = self._series_catalog[series_index]
            selected_unit: str = ''
            if len(selected_indices) > 0:
                selected_unit = self._series_catalog[selected_indices[0]].unit
                selected_x_values: np.ndarray = self._series_catalog[selected_indices[0]].x_values
            else:
                selected_x_values = candidate.x_values
                pass
            compatible: bool = (
                (selected_unit == '' or selected_unit == candidate.unit)
                and bool(np.array_equal(selected_x_values, candidate.x_values))
            )
            if compatible and visible and series_index not in selected_indices:
                selected_indices.append(series_index)
                self._rebuild_catalog_chart()
            elif compatible and not visible and series_index in selected_indices:
                selected_indices.remove(series_index)
                self._rebuild_catalog_chart()
            else:
                self._refresh_catalog_tree()
        else:
            pass

    def _set_catalog_visibility(self, visible: bool) -> None:
        """Select or clear compatible series in the active catalog-backed plot.

        :param visible: Whether all candidates of the selected unit are shown.
        :return: None.
        """
        tab_index: int = self.ui.plotTabs.currentIndex()
        if 0 <= tab_index < len(self._plot_series_indices):
            selected_indices: list[int] = self._plot_series_indices[tab_index]
            selected_unit: str = ''
            if len(selected_indices) > 0:
                selected_unit = self._series_catalog[selected_indices[0]].unit
                selected_x_values: np.ndarray = self._series_catalog[selected_indices[0]].x_values
            elif len(self._series_catalog) > 0:
                selected_unit = self._series_catalog[0].unit
                selected_x_values = self._series_catalog[0].x_values
            else:
                selected_x_values = np.empty(0, dtype=float)
                pass
            if visible and selected_unit != '':
                selected_indices.clear()
                series_index: int
                for series_index in range(len(self._series_catalog)):
                    candidate: PlotSeries = self._series_catalog[series_index]
                    if (candidate.unit == selected_unit
                            and bool(np.array_equal(candidate.x_values, selected_x_values))):
                        selected_indices.append(series_index)
                    else:
                        pass
            elif not visible:
                selected_indices.clear()
            else:
                pass
            self._rebuild_catalog_chart()
        else:
            pass

    def center_data(self, checked: bool = False) -> None:
        """Reset the chart zoom and pan from the toolbar action.

        :param checked: QAction state ignored by the non-checkable action.
        :return: None.
        """
        _ = checked
        self.get_current_chart().reset_viewport()

    def save_image(self, checked: bool = False) -> None:
        """Ask for a PNG or SVG path and export the current native chart.

        :param checked: QAction state ignored by the non-checkable action.
        :return: None.
        """
        _ = checked
        if not is_dialog_available(self._active_save_dialog):
            file_dialog: QtWidgets.QFileDialog = QtWidgets.QFileDialog(self, self.tr('Save plot image'))
            file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
            file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.AnyFile)
            file_dialog.setOption(QtWidgets.QFileDialog.Option.DontUseNativeDialog, True)
            file_dialog.setNameFilters([self.tr('SVG image (*.svg)'), self.tr('PNG image (*.png)')])
            file_dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
            file_dialog.fileSelected.connect(self._save_selected_image)
            file_dialog.finished.connect(self._clear_active_save_dialog)
            file_dialog.destroyed.connect(self._clear_active_save_dialog)
            self._active_save_dialog = file_dialog
            file_dialog.open()
        else:
            self._active_save_dialog.raise_()
            self._active_save_dialog.activateWindow()

    def _save_selected_image(self, file_name: str) -> None:
        """Export the current chart after the non-modal file chooser selects a path.

        :param file_name: User-selected destination.
        :return: None.
        """
        if file_name != '':
            output_path: Path = Path(file_name)
            if output_path.suffix == '' and self._active_save_dialog is not None:
                selected_filter: str = self._active_save_dialog.selectedNameFilter().casefold()
                output_path = output_path.with_suffix('.svg' if 'svg' in selected_filter else '.png')
            else:
                pass
            self.save_image_to_file(file_name=str(output_path))
        else:
            pass

    def _clear_active_save_dialog(self, result: object = None) -> None:
        """Drop the reference after the child save dialog has finished.

        :param result: Dialog result code or destroyed object.
        :return: None.
        """
        _ = result
        if self.sender() is self._active_save_dialog:
            self._active_save_dialog = None
        else:
            pass

    def save_image_to_file(self, file_name: str) -> bool:
        """Export the current chart without opening a file dialog.

        :param file_name: Target PNG or SVG filename.
        :return: Whether a non-empty image file was created.
        """
        return save_chart_image(chart=self.get_current_chart(), file_name=file_name)
