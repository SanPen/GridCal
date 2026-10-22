# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Deterministic lifecycle stress coverage for the native QWidget renderer."""

from __future__ import annotations

import faulthandler
import multiprocessing
import queue
import time
import traceback
from typing import Any

import numpy as np
import pytest
from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from VeraGrid.Gui.PlotDialogue.qt_chart_widget import (
    ChartContentType,
    ChartSeriesType,
    GraphsWidget,
    PolarAngleUnit,
    format_chart_value,
)
from VeraGrid.Gui.PlotDialogue.qt_rhi_line_chart_widget import RhiLineChartWidget


@pytest.mark.parametrize("x_values", ((0.0, 10.0), (10.0, 0.0), (5.0, 5.0)))
def test_line_hover_calculates_coordinates(qt_app: QtWidgets.QApplication,
                                          x_values: tuple[float, float]) -> None:
    """Calculate hover text between samples without storing point tooltips.

    :param qt_app: Shared Qt application.
    :param x_values: Ascending, descending, or vertical segment coordinates.
    :return: None.
    """
    chart: GraphsWidget = GraphsWidget()
    chart.resize(800, 600)
    chart.add_line_series(name="Generator A", x_values=np.array(x_values),
                          y_values=np.array((0.0, 10.0)))
    rect: QtCore.QRectF = chart._get_plot_rect()
    position: QtCore.QPointF = chart._map_xy_point(5.0, 5.0, rect)
    assert chart.get_point_tooltip_at(position) == "Generator A\nx: 5\ny: 5"
    assert not chart._series[0].has_point_tooltips()
    assert chart.get_point_tooltip_at(QtCore.QPointF(-1.0, -1.0)) is None
    if x_values[0] != x_values[1]:
        assert chart.get_point_tooltip_at(chart._map_xy_point(5.0, 8.0, rect)) is None
    else:
        assert chart.get_point_tooltip_at(chart._map_xy_point(5.0, 8.0, rect)) is not None
    chart.set_series_visible(0, False)
    assert chart.get_point_tooltip_at(position) is None
    chart.close()


def test_line_hover_accepts_nearby_pointer(qt_app: QtWidgets.QApplication) -> None:
    """Allow a five-pixel gap without selecting a more distant line.

    :param qt_app: Shared Qt application.
    :return: None.
    """
    chart: GraphsWidget = GraphsWidget()
    chart.resize(800, 600)
    chart.add_line_series(name="Power", x_values=np.array((0.0, 10.0)),
                          y_values=np.array((5.0, 5.0)))
    position: QtCore.QPointF = chart._map_xy_point(5.0, 5.0, chart._get_plot_rect())
    assert chart.get_point_tooltip_at(position + QtCore.QPointF(0.0, 5.0)) == "Power\nx: 5\ny: 5"
    assert chart.get_point_tooltip_at(position + QtCore.QPointF(0.0, 6.0)) is None
    chart.close()


def test_line_hover_formats_datetime_coordinates(qt_app: QtWidgets.QApplication) -> None:
    """Format hovered time coordinates using the existing date formatter.

    :param qt_app: Shared Qt application.
    :return: None.
    """
    chart: GraphsWidget = GraphsWidget()
    chart.resize(800, 600)
    chart.add_line_series(name="Load", x_values=np.array(("2030-01-01", "2030-01-03"), dtype="datetime64[ms]"),
                          y_values=np.array((0.0, 10.0)))
    midpoint: float = float(np.datetime64("2030-01-02", "ms").astype(np.int64))
    position: QtCore.QPointF = chart._map_xy_point(midpoint, 5.0, chart._get_plot_rect())
    assert chart.get_point_tooltip_at(position) == "Load\nx: 02/01/2030\n00:00:00\ny: 5"
    chart.close()


@pytest.mark.parametrize("cleanup", ("hide", "dispose", "delete", "parent"))
def test_visible_hover_tooltip_survives_chart_cleanup(qt_app: QtWidgets.QApplication,
                                                     cleanup: str) -> None:
    """Dismiss a live Qt tooltip when its chart is hidden or destroyed.

    :param qt_app: Shared Qt application.
    :param cleanup: Lifecycle transition to exercise.
    :return: None.
    """
    owner: QtWidgets.QDialog = QtWidgets.QDialog()
    chart: GraphsWidget = GraphsWidget(parent=owner)
    chart.resize(800, 600)
    chart.add_line_series(name="Power", x_values=np.array((0.0, 10.0)),
                          y_values=np.array((5.0, 5.0)))
    owner.show()
    chart.show()
    qt_app.processEvents()
    position: QtCore.QPointF = chart._map_xy_point(5.0, 5.0, chart._get_plot_rect())
    global_position: QtCore.QPointF = QtCore.QPointF(chart.mapToGlobal(position.toPoint()))
    event: QtGui.QMouseEvent = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove, position, global_position,
        QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    chart.mouseMoveEvent(event)
    assert QtWidgets.QToolTip.text() == "Power\nx: 5\ny: 5"
    if cleanup == "hide":
        chart.hide()
    elif cleanup == "dispose":
        chart.dispose()
    elif cleanup == "delete":
        chart.deleteLater()
    else:
        owner.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    # Qt delays tooltip dismissal; allow its own timer and deferred deletion to run.
    QtTest.QTest.qWait(400)
    assert not QtWidgets.QToolTip.isVisible()
    if cleanup != "parent":
        owner.deleteLater()
    else:
        pass
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


class ObjectDestructionProbe:
    """Record the deferred native destruction of one Qt-owned chart widget."""

    __slots__ = ("destroyed_count",)

    def __init__(self) -> None:
        """Create an empty destruction counter.

        :return: None.
        """
        self.destroyed_count: int = 0

    def mark_destroyed(self, destroyed_object: QtCore.QObject | None = None) -> None:
        """Record Qt's native destruction signal.

        :param destroyed_object: QObject instance being destroyed by Qt.
        :return: None.
        """
        _ = destroyed_object
        self.destroyed_count += 1


def test_datetime_axis_tick_format_includes_date_and_time() -> None:
    """Display datetime ticks as day/month/year and 24-hour time.

    :return: None.
    """
    formatted_value: str = format_chart_value(value=1_700_000_000_000.0, is_datetime=True)
    date_part: str
    time_part: str
    date_part, time_part = formatted_value.split("\n")
    assert tuple(len(date_component) for date_component in date_part.split("/")) == (2, 2, 4)
    assert tuple(len(time_component) for time_component in time_part.split(":")) == (2, 2, 2)


def test_manual_axis_borders_clip_extreme_data_and_parse_datetime(
        qt_app: QtWidgets.QApplication) -> None:
    """Allow finite user limits to keep extreme values outside the visible range.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    _ = qt_app
    chart: GraphsWidget = GraphsWidget()
    chart.resize(720, 420)
    chart.add_line_series(
        name="Outlier",
        x_values=np.asarray((0.0, 1.0, 2.0)),
        y_values=np.asarray((1.0, 2.0, 1.0e20)),
    )
    chart._edit_x_minimum()
    chart._axis_limit_editor.setText("0")
    chart._apply_axis_input_range()
    chart._edit_x_maximum()
    chart._axis_limit_editor.setText("2")
    chart._apply_axis_input_range()
    chart._edit_y_minimum()
    chart._axis_limit_editor.setText("0")
    chart._apply_axis_input_range()
    chart._edit_y_maximum()
    chart._axis_limit_editor.setText("5")
    chart._apply_axis_input_range()
    assert chart.axis_x.get_range() == (0.0, 2.0)
    assert chart.axis_y.get_range() == (0.0, 5.0)
    chart._edit_y_maximum()
    chart._axis_limit_editor.setText("inf")
    chart._apply_axis_input_range()
    assert chart.axis_y.get_range() == (0.0, 5.0)
    chart.axis_x.set_zoom(2.0)
    chart.axis_y.set_zoom(2.0)
    chart._center_from_context_menu()
    assert chart.axis_x.get_zoom() == 1.0
    assert chart.axis_y.get_zoom() == 1.0
    assert chart.axis_y.get_range()[1] > 1.0e20

    date_axis: GraphsWidget = GraphsWidget()
    date_axis._x_is_datetime = True
    date_axis.axis_x.set_range(0.0, 2_000.0)
    date_axis._edit_x_minimum()
    date_axis._axis_limit_editor.setText("01/01/1970 00:00:01")
    date_axis._apply_axis_input_range()
    assert date_axis.axis_x.get_range() == (1_000.0, 2_000.0)
    chart.dispose()
    date_axis.dispose()


def test_axis_limit_editor_uses_chart_theme_palette(qt_app: QtWidgets.QApplication) -> None:
    """Keep the temporary axis limit field visually aligned with chart labels.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    _ = qt_app
    chart: GraphsWidget = GraphsWidget()
    assert chart._axis_limit_editor.palette().color(QtGui.QPalette.ColorRole.Base) == chart._plot_color
    assert chart._axis_limit_editor.palette().color(QtGui.QPalette.ColorRole.Text) == chart._label_color
    chart.dispose()


def test_axis_border_context_action_edits_limit_without_changing_center_gesture(
        qt_app: QtWidgets.QApplication) -> None:
    """Expose axis edits in the context menu and preserve plot double-click reset.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    chart: GraphsWidget = GraphsWidget()
    chart.resize(640, 420)
    chart.add_line_series(
        name="Line",
        x_values=np.asarray((0.0, 1.0, 2.0)),
        y_values=np.asarray((0.0, 1.0, 2.0)),
    )
    chart.show()
    qt_app.processEvents()
    global_position: QtCore.QPoint = chart.mapToGlobal(QtCore.QPoint(40, 40))
    context_event: QtGui.QContextMenuEvent = QtGui.QContextMenuEvent(
        QtGui.QContextMenuEvent.Reason.Mouse,
        QtCore.QPoint(40, 40),
        global_position,
    )
    chart.contextMenuEvent(context_event)
    qt_app.processEvents()
    menus: list[QtWidgets.QMenu] = chart.findChildren(QtWidgets.QMenu)
    assert len(menus) == 1
    axis_action: QtGui.QAction
    for axis_action in menus[0].actions():
        if axis_action.text() == "Edit Y maximum…":
            axis_action.trigger()
            break
        else:
            pass
    assert chart._axis_limit_editor.isVisible()
    chart._axis_limit_editor.setText("1.5")
    enter_event: QtGui.QKeyEvent = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_Return,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    QtWidgets.QApplication.sendEvent(chart._axis_limit_editor, enter_event)
    assert chart.axis_y.get_range()[1] == 1.5
    assert not chart._axis_limit_editor.isVisible()

    chart.axis_x.set_zoom(2.0)
    chart.axis_y.set_zoom(2.0)
    plot_rect: QtCore.QRectF = chart._get_plot_rect()
    center_double_click: QtGui.QMouseEvent = make_mouse_event(
        event_type=QtCore.QEvent.Type.MouseButtonDblClick,
        widget=chart,
        local_position=plot_rect.center(),
        button=QtCore.Qt.MouseButton.LeftButton,
        buttons=QtCore.Qt.MouseButton.LeftButton,
    )
    chart.mouseDoubleClickEvent(center_double_click)
    assert chart.axis_x.get_zoom() == 1.0
    assert chart.axis_y.get_zoom() == 1.0
    assert chart.axis_y.get_range()[1] > 2.0
    chart.dispose()
    chart.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


def make_wheel_event(widget: GraphsWidget, delta_y: int) -> QtGui.QWheelEvent:
    """Build one wheel event centered in the visible chart widget.

    :param widget: Target chart receiving the zoom operation.
    :param delta_y: Vertical wheel delta in Qt angle units.
    :return: Native wheel event for the widget.
    """
    local_position: QtCore.QPointF = QtCore.QPointF(widget.width() * 0.5, widget.height() * 0.5)
    global_position: QtCore.QPointF = QtCore.QPointF(widget.mapToGlobal(local_position.toPoint()))
    return QtGui.QWheelEvent(
        local_position,
        global_position,
        QtCore.QPoint(0, 0),
        QtCore.QPoint(0, delta_y),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def make_mouse_event(event_type: QtCore.QEvent.Type,
                     widget: GraphsWidget,
                     local_position: QtCore.QPointF,
                     button: QtCore.Qt.MouseButton,
                     buttons: QtCore.Qt.MouseButton,
                     modifiers: QtCore.Qt.KeyboardModifier = QtCore.Qt.KeyboardModifier.NoModifier
                     ) -> QtGui.QMouseEvent:
    """Build one mouse event in the chart coordinate system.

    :param event_type: Qt mouse event type.
    :param widget: Target chart receiving the input operation.
    :param local_position: Pointer position in chart pixels.
    :param button: Button that caused the event.
    :param buttons: Buttons held while the event is delivered.
    :param modifiers: Keyboard modifiers held during the gesture.
    :return: Native mouse event for the widget.
    """
    global_position: QtCore.QPointF = QtCore.QPointF(widget.mapToGlobal(local_position.toPoint()))
    return QtGui.QMouseEvent(
        event_type,
        local_position,
        global_position,
        button,
        buttons,
        modifiers,
    )


def paint_chart_to_image(widget: GraphsWidget) -> QtGui.QImage:
    """Render the current chart to an owned raster paint device.

    :param widget: Chart whose full paint path is exercised.
    :return: Non-null image containing the chart rendering.
    """
    image: QtGui.QImage = QtGui.QImage(
        widget.size(),
        QtGui.QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(QtGui.QColor("#ffffff"))
    painter: QtGui.QPainter = QtGui.QPainter(image)
    widget.render(painter, QtCore.QPoint(0, 0))
    painter.end()
    return image


def delete_chart_owner(owner: QtWidgets.QDialog,
                       chart: GraphsWidget,
                       probe: ObjectDestructionProbe,
                       app: QtWidgets.QApplication) -> None:
    """Dispose and destroy one QWidget chart through its parent-child owner tree.

    :param owner: Dialog owning the chart through a Qt layout.
    :param chart: Chart whose Python buffers must be released.
    :param probe: Recorder attached to the chart destruction signal.
    :param app: Shared Qt application that receives deferred deletions.
    :return: None.
    """
    owner.reject()
    chart.deleteLater()
    owner.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()
    assert probe.destroyed_count == 1


def drag_select_zoom(chart: GraphsWidget) -> None:
    """Deliver one left-button selection across the current chart data area.

    :param chart: Visible native chart receiving the zoom gesture.
    :return: None.
    """
    plot_rect: QtCore.QRectF = chart._get_plot_rect()
    start_position: QtCore.QPointF = QtCore.QPointF(
        plot_rect.left() + plot_rect.width() * 0.25,
        plot_rect.top() + plot_rect.height() * 0.25,
    )
    end_position: QtCore.QPointF = QtCore.QPointF(
        plot_rect.left() + plot_rect.width() * 0.75,
        plot_rect.top() + plot_rect.height() * 0.75,
    )
    chart.mousePressEvent(make_mouse_event(
        event_type=QtCore.QEvent.Type.MouseButtonPress,
        widget=chart,
        local_position=start_position,
        button=QtCore.Qt.MouseButton.LeftButton,
        buttons=QtCore.Qt.MouseButton.LeftButton,
    ))
    chart.mouseMoveEvent(make_mouse_event(
        event_type=QtCore.QEvent.Type.MouseMove,
        widget=chart,
        local_position=end_position,
        button=QtCore.Qt.MouseButton.NoButton,
        buttons=QtCore.Qt.MouseButton.LeftButton,
    ))
    chart.mouseReleaseEvent(make_mouse_event(
        event_type=QtCore.QEvent.Type.MouseButtonRelease,
        widget=chart,
        local_position=end_position,
        button=QtCore.Qt.MouseButton.LeftButton,
        buttons=QtCore.Qt.MouseButton.NoButton,
    ))


def test_chart_widget_rectangle_zoom_covers_every_native_renderer(
        qt_app: QtWidgets.QApplication) -> None:
    """Verify every chart mode accepts a left-drag zoom without retained Qt items.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    owner: QtWidgets.QDialog = QtWidgets.QDialog()
    layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(owner)
    chart: GraphsWidget = GraphsWidget(parent=owner)
    layout.addWidget(chart)
    owner.resize(720, 520)
    owner.show()
    qt_app.processEvents()

    chart.add_line_series(
        name="XY",
        x_values=np.array((0.0, 1.0, 2.0, 3.0), dtype=float),
        y_values=np.array((1.0, 3.0, 2.0, 4.0), dtype=float),
    )
    drag_select_zoom(chart=chart)
    assert chart.axis_x.get_zoom() > 1.0
    assert chart.axis_y.get_zoom() > 1.0

    assert chart.set_cumulative_area_series(
        x_values=np.array((0.0, 1.0, 2.0, 3.0), dtype=float),
        series_names=("A", "B"),
        series_values=(
            np.array((1.0, 2.0, 1.0, 2.0), dtype=float),
            np.array((2.0, 1.0, 2.0, 1.0), dtype=float),
        ),
    )
    drag_select_zoom(chart=chart)
    assert chart.axis_x.get_zoom() > 1.0
    assert chart.axis_y.get_zoom() > 1.0

    chart.add_horizontal_bar_series(
        labels=("A", "B", "C"),
        values=np.array((1.0, -2.0, 3.0), dtype=float),
        positive_color="#0f766e",
        negative_color="#dc2626",
    )
    drag_select_zoom(chart=chart)
    assert chart.axis_x.get_zoom() > 1.0

    assert chart.set_histogram(
        values=np.array((-2.0, -1.0, 0.0, 1.0, 2.0), dtype=float),
        bin_count=3,
    )
    drag_select_zoom(chart=chart)
    assert chart.axis_x.get_zoom() > 1.0
    assert chart.axis_y.get_zoom() > 1.0

    assert chart.set_polar_series(
        series_names=("Polar",),
        angle_values=(np.array((0.0, 90.0, 180.0, 270.0), dtype=float),),
        radius_values=(np.array((1.0, 0.5, 0.8, 1.2), dtype=float),),
        angle_unit=PolarAngleUnit.DEGREES,
    )
    drag_select_zoom(chart=chart)
    assert chart.axis_y.get_zoom() > 1.0

    chart.dispose()
    owner.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    qt_app.processEvents()


def test_line_decimation_preserves_spikes_for_dense_series(
        qt_app: QtWidgets.QApplication) -> None:
    """Retain local peaks and dips when a long line is reduced to screen pixels.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    chart: GraphsWidget = GraphsWidget()
    chart.resize(400, 260)
    source_x: np.ndarray = np.linspace(0.0, 1.0, 10000, dtype=float)
    source_y: np.ndarray = np.zeros(len(source_x), dtype=float)
    source_y[4321] = 20.0
    source_y[7654] = -10.0
    chart.add_line_series(name='Spikes', x_values=source_x, y_values=source_y)
    plot_rect: QtCore.QRectF = chart._get_plot_rect()
    retained_indices: np.ndarray = chart._sample_xy_indices(
        x_data=chart._series[0].get_x_data(),
        y_data=chart._series[0].get_y_data(),
        x_is_monotonic=chart._series[0].get_x_is_monotonic(),
        plot_rect=plot_rect,
        visible_line_count=2224,
    )
    assert len(retained_indices) <= 500000 // 2224
    assert 4321 in retained_indices
    assert 7654 in retained_indices
    chart.dispose()
    chart.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    qt_app.processEvents()


def test_chart_widget_stress_replaces_data_paints_and_destroys_cleanly(
        qt_app: QtWidgets.QApplication) -> None:
    """Stress XY updates, input, paint, mode changes, and deferred destruction.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    random_generator: np.random.Generator = np.random.default_rng(91627)
    cycle_index: int

    for cycle_index in range(48):
        owner: QtWidgets.QDialog = QtWidgets.QDialog()
        layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(owner)
        chart: GraphsWidget = GraphsWidget(parent=owner)
        probe: ObjectDestructionProbe = ObjectDestructionProbe()
        chart.destroyed.connect(probe.mark_destroyed)
        layout.addWidget(chart)
        owner.resize(640 + cycle_index * 4, 460 + cycle_index * 3)
        owner.show()
        app.processEvents()

        source_x: np.ndarray = np.linspace(-8.0, 8.0, 2048, dtype=float)
        source_y: np.ndarray = np.sin(source_x) + random_generator.normal(0.0, 0.01, len(source_x))
        source_y[17] = np.nan
        source_y[31] = np.inf
        chart.setTitle(f"Stress cycle {cycle_index}")
        chart.set_axis_titles("X", "Y")
        chart.add_line_series(name="Line", x_values=source_x, y_values=source_y, color="#2563eb")
        chart.add_scatter_series(
            name="Points",
            x_values=source_x[::256],
            y_values=source_y[::256],
            color="#f97316",
            point_tooltips=tuple(f"Point {point_index}" for point_index in range(8)),
        )
        assert len(chart._series) == 2
        assert chart._series[0].get_series_type() == ChartSeriesType.LINE
        assert chart._series[1].get_series_type() == ChartSeriesType.SCATTER
        scatter_point: QtCore.QPointF = chart._map_xy_point(
            x_value=float(chart._series[1].get_x_data()[0]),
            y_value=float(chart._series[1].get_y_data()[0]),
            plot_rect=chart._get_plot_rect(),
        )
        assert chart.get_point_tooltip_at(position=scatter_point) == "Point 0"

        # ChartSeries copies inputs, so a producer changing its own buffer cannot
        # race the QWidget paint path through shared NumPy memory.
        first_chart_value: float = float(chart._series[0].get_y_data()[1])
        source_y[1] = 999999.0
        assert float(chart._series[0].get_y_data()[1]) == first_chart_value

        update_index: int
        stable_series: tuple[object, ...] = tuple(chart._series)
        for update_index in range(16):
            update_x: np.ndarray = np.linspace(-8.0, 8.0, 1024 + update_index, dtype=float)
            update_line_y: np.ndarray = np.cos(update_x * float(update_index + 1) * 0.1)
            update_scatter_x: np.ndarray = update_x[::128]
            update_scatter_y: np.ndarray = update_line_y[::128]
            assert chart.replace_xy_series_data(
                series_data=(
                    (update_x, update_line_y, "#2563eb"),
                    (update_scatter_x, update_scatter_y, "#f97316"),
                )
            )
            assert tuple(chart._series) == stable_series
            owner.resize(640 + update_index * 11, 460 + update_index * 7)
            chart.redraw()
            app.processEvents()
            image: QtGui.QImage = paint_chart_to_image(widget=chart)
            assert not image.isNull()

        # Invalid replacements must leave the existing owned series untouched.
        assert not chart.replace_xy_series_data(
            series_data=((np.array((0.0, 1.0)), np.array((0.0, 1.0)), "#2563eb"),)
        )
        assert tuple(chart._series) == stable_series

        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=120))
        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=120))
        assert chart.axis_x.get_zoom() > 1.0
        assert chart.axis_y.get_zoom() > 1.0
        wheel_zoom: float = chart.axis_x.get_zoom()
        plot_rect: QtCore.QRectF = chart._get_plot_rect()
        x_zoom_before_selection: float = chart.axis_x.get_zoom()
        y_zoom_before_selection: float = chart.axis_y.get_zoom()
        press_position: QtCore.QPointF = QtCore.QPointF(chart.width() * 0.45, chart.height() * 0.45)
        move_position: QtCore.QPointF = QtCore.QPointF(chart.width() * 0.62, chart.height() * 0.57)
        chart.mousePressEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonPress,
            widget=chart,
            local_position=press_position,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
        ))
        chart.mouseMoveEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseMove,
            widget=chart,
            local_position=move_position,
            button=QtCore.Qt.MouseButton.NoButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
        ))
        assert chart._zoom_selection is not None
        selection_rect: QtCore.QRectF = chart._zoom_selection
        selection_aspect: float = selection_rect.width() / selection_rect.height()
        assert not np.isclose(selection_aspect, plot_rect.width() / plot_rect.height())
        assert not paint_chart_to_image(widget=chart).isNull()
        chart.mouseReleaseEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonRelease,
            widget=chart,
            local_position=move_position,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.NoButton,
        ))
        assert chart.axis_x.get_zoom() > wheel_zoom
        assert chart.axis_y.get_zoom() > wheel_zoom
        adjusted_plot: QtCore.QRectF = chart._get_plot_rect()
        assert np.isclose(adjusted_plot.width(), plot_rect.width())
        assert np.isclose(adjusted_plot.height(), plot_rect.height())
        assert np.isclose(
            chart.axis_x.get_zoom() * selection_rect.width() / plot_rect.width(),
            x_zoom_before_selection,
        )
        assert np.isclose(
            chart.axis_y.get_zoom() * selection_rect.height() / plot_rect.height(),
            y_zoom_before_selection,
        )
        assert chart._zoom_selection is None
        chart.reset_viewport()
        assert chart.axis_x.get_pan() == 0.0
        assert chart.axis_y.get_pan() == 0.0

        chart.mousePressEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonPress,
            widget=chart,
            local_position=press_position,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
            modifiers=QtCore.Qt.KeyboardModifier.ControlModifier,
        ))
        chart.mouseMoveEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseMove,
            widget=chart,
            local_position=move_position,
            button=QtCore.Qt.MouseButton.NoButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
            modifiers=QtCore.Qt.KeyboardModifier.ControlModifier,
        ))
        chart.mouseReleaseEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonRelease,
            widget=chart,
            local_position=move_position,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.NoButton,
            modifiers=QtCore.Qt.KeyboardModifier.ControlModifier,
        ))
        assert chart._zoom_origin is None
        assert chart.axis_x.get_pan() != 0.0
        assert chart.axis_y.get_pan() != 0.0
        chart.reset_viewport()
        assert chart.axis_x.get_zoom() == 1.0
        assert chart.axis_y.get_zoom() == 1.0
        assert chart.axis_x.get_pan() == 0.0
        assert chart.axis_y.get_pan() == 0.0

        # Every renderer mode must tolerate a real paint and zoom cycle.
        assert chart.set_cumulative_area_series(
            x_values=np.array((0.0, 1.0, 2.0, 3.0), dtype=float),
            series_names=("Wind", "Solar"),
            series_values=(
                np.array((1.0, 1.5, np.nan, 2.0), dtype=float),
                np.array((0.5, 0.7, 1.2, 0.6), dtype=float),
            ),
        )
        assert chart._content_type == ChartContentType.CUMULATIVE_AREA
        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=120))
        assert not paint_chart_to_image(widget=chart).isNull()

        chart.add_horizontal_bar_series(
            labels=("A", "B", "C", "D"),
            values=np.array((2.0, -1.0, np.nan, 3.0), dtype=float),
            positive_color="#0f766e",
            negative_color="#dc2626",
        )
        assert chart._content_type == ChartContentType.HORIZONTAL_BAR
        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=-120))
        assert not paint_chart_to_image(widget=chart).isNull()

        assert chart.set_histogram(
            values=np.array((-3.0, -1.0, -1.0, 0.0, 2.0, 4.0, np.nan, np.inf), dtype=float),
            bin_count=5,
        )
        assert chart._content_type == ChartContentType.HISTOGRAM
        histogram_series: tuple[object, ...] = tuple(chart._series)
        assert not chart.set_histogram(values=np.array((1.0, 2.0), dtype=float), bin_count=0)
        assert tuple(chart._series) == histogram_series
        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=120))
        assert not paint_chart_to_image(widget=chart).isNull()

        assert chart.set_polar_series(
            series_names=("Polar",),
            angle_values=(np.array((0.0, 90.0, 180.0, 270.0, 360.0), dtype=float),),
            radius_values=(np.array((1.0, 0.5, 1.2, np.nan, 1.0), dtype=float),),
            angle_unit=PolarAngleUnit.DEGREES,
        )
        assert chart._content_type == ChartContentType.POLAR
        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=120))
        assert not paint_chart_to_image(widget=chart).isNull()

        assert chart.set_polar_series(
            series_names=("Polar points",),
            angle_values=(np.array((0.0, 90.0, 180.0, 270.0), dtype=float),),
            radius_values=(np.array((1.0, 0.6, 1.1, 0.8), dtype=float),),
            angle_unit=PolarAngleUnit.DEGREES,
            connect_points=False,
        )
        assert chart._series[0].get_series_type() == ChartSeriesType.POLAR_SCATTER
        assert not paint_chart_to_image(widget=chart).isNull()

        # Explicit disposal must empty Python buffers before Qt deletes the C++ widget.
        chart.dispose()
        assert chart._disposed
        assert len(chart._series) == 0
        chart.add_line_series(
            name="Ignored after disposal",
            x_values=np.array((0.0, 1.0)),
            y_values=np.array((0.0, 1.0)),
        )
        assert len(chart._series) == 0
        delete_chart_owner(owner=owner, chart=chart, probe=probe, app=app)


def test_chart_widget_validates_tooltips_and_rejects_invalid_mode_data(
        qt_app: QtWidgets.QApplication) -> None:
    """Verify failed public inputs cannot partly mutate an active chart.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    owner: QtWidgets.QDialog = QtWidgets.QDialog()
    layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(owner)
    chart: GraphsWidget = GraphsWidget(parent=owner)
    probe: ObjectDestructionProbe = ObjectDestructionProbe()
    chart.destroyed.connect(probe.mark_destroyed)
    layout.addWidget(chart)
    owner.resize(720, 520)
    owner.show()
    app.processEvents()

    chart.add_scatter_series(
        name="Buses",
        x_values=np.array((0.0, np.nan, 2.0), dtype=float),
        y_values=np.array((1.0, 2.0, 3.0), dtype=float),
        point_tooltips=("Bus A", "Dropped", "Bus C"),
    )
    assert len(chart._series) == 1
    assert chart._series[0].has_point_tooltips()
    assert chart._series[0].get_point_tooltip(point_index=0) == "Bus A"
    assert chart._series[0].get_point_tooltip(point_index=1) == "Bus C"
    assert not chart.set_series_point_tooltips(series_index=0, point_tooltips=("Only one",))
    assert not chart.set_series_point_tooltips(series_index=1, point_tooltips=("Missing", "series"))

    stable_series: tuple[object, ...] = tuple(chart._series)
    assert not chart.set_cumulative_area_series(
        x_values=np.array((0.0, 1.0), dtype=float),
        series_names=("Invalid",),
        series_values=(np.array((1.0,), dtype=float),),
    )
    assert tuple(chart._series) == stable_series
    assert not chart.set_polar_series(
        series_names=("Invalid",),
        angle_values=(np.array((0.0, 1.0), dtype=float),),
        radius_values=(np.array((-1.0, np.nan), dtype=float),),
    )
    assert tuple(chart._series) == stable_series
    assert not chart.set_polar_series(
        series_names=("Mismatched",),
        angle_values=(np.array((0.0, 1.0), dtype=float),),
        radius_values=(np.array((1.0,), dtype=float),),
    )
    assert tuple(chart._series) == stable_series

    chart.dispose()
    delete_chart_owner(owner=owner, chart=chart, probe=probe, app=app)


def test_dense_random_chart_reuses_vertices_during_zoom_and_pan(
        qt_app: QtWidgets.QApplication) -> None:
    """Stress random line batches and prove unchanged paints skip repacking.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    random_generator: np.random.Generator = np.random.default_rng(20260920)
    owner: QtWidgets.QDialog = QtWidgets.QDialog()
    chart: GraphsWidget = GraphsWidget(parent=owner)
    probe: ObjectDestructionProbe = ObjectDestructionProbe()
    chart.destroyed.connect(probe.mark_destroyed)
    chart.set_rhi_line_rendering(enabled=True, series_threshold=32)
    chart.resize(1100, 720)
    point_count: int = 12000
    x_values: np.ndarray = np.linspace(0.0, 120.0, point_count, dtype=float)
    series_index: int
    for series_index in range(48):
        noise: np.ndarray = random_generator.normal(0.0, 0.08, point_count)
        frequency: float = float(random_generator.uniform(0.05, 1.5))
        phase: float = float(random_generator.uniform(-np.pi, np.pi))
        y_values: np.ndarray = np.sin(x_values * frequency + phase) + noise + series_index * 0.01
        chart.add_line_series(
            name=f"random {series_index}",
            x_values=x_values,
            y_values=y_values,
            color=QtGui.QColor.fromHsv((series_index * 47) % 360, 190, 190),
        )
    plot_rect: QtCore.QRectF = chart._get_plot_rect()
    assert chart._prepare_rhi_line_layer(plot_rect=plot_rect)
    assert chart._rhi_line_widget is not None
    first_revision: int = chart._rhi_line_widget._data_revision
    repeat_index: int
    for repeat_index in range(12):
        assert chart._prepare_rhi_line_layer(plot_rect=plot_rect)
        assert chart._rhi_line_widget._data_revision == first_revision
    image: QtGui.QImage = QtGui.QImage(
        chart.size(), QtGui.QImage.Format.Format_ARGB32_Premultiplied
    )
    painter: QtGui.QPainter = QtGui.QPainter(image)
    chart.paint_to_painter(painter=painter, paint_lines=False)
    painter.end()
    assert not image.isNull()
    chart._center_from_context_menu()
    assert chart.axis_x.get_zoom() == 1.0
    assert chart.axis_y.get_zoom() == 1.0

    gesture_index: int
    for gesture_index in range(12):
        plot_rect = chart._get_plot_rect()
        x_zoom_before_selection: float = chart.axis_x.get_zoom()
        y_zoom_before_selection: float = chart.axis_y.get_zoom()
        selection_start: QtCore.QPointF = QtCore.QPointF(
            plot_rect.left() + plot_rect.width() * 0.25,
            plot_rect.top() + plot_rect.height() * 0.25,
        )
        selection_end: QtCore.QPointF = QtCore.QPointF(
            plot_rect.left() + plot_rect.width() * 0.72,
            plot_rect.top() + plot_rect.height() * 0.60,
        )
        chart.mousePressEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonPress,
            widget=chart,
            local_position=selection_start,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
        ))
        chart.mouseMoveEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseMove,
            widget=chart,
            local_position=selection_end,
            button=QtCore.Qt.MouseButton.NoButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
        ))
        assert chart._zoom_selection is not None
        selection_rect: QtCore.QRectF = chart._zoom_selection
        selection_aspect: float = selection_rect.width() / selection_rect.height()
        assert not np.isclose(selection_aspect, plot_rect.width() / plot_rect.height())
        assert chart._pan_position is None
        assert chart.axis_x.get_pan() == 0.0
        assert chart.axis_y.get_pan() == 0.0
        assert chart._rhi_selection_overlay is not None
        assert not chart._rhi_selection_overlay.isHidden()
        overlay_image: QtGui.QImage = QtGui.QImage(
            chart.size(), QtGui.QImage.Format.Format_ARGB32_Premultiplied
        )
        overlay_image.fill(QtCore.Qt.GlobalColor.transparent)
        overlay_painter: QtGui.QPainter = QtGui.QPainter(overlay_image)
        chart._rhi_selection_overlay.render(overlay_painter, QtCore.QPoint(0, 0))
        overlay_painter.end()
        overlay_probe: QtCore.QPoint = QtCore.QPoint(
            int(chart._zoom_selection.left() + chart._zoom_selection.width() * 0.35),
            int(chart._zoom_selection.top() + chart._zoom_selection.height() * 0.35),
        )
        assert overlay_image.pixelColor(overlay_probe).alpha() > 0
        assert chart._zoom_origin is not None
        assert selection_rect.width() >= 6.0
        assert selection_rect.height() >= 6.0
        image = QtGui.QImage(chart.size(), QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        painter = QtGui.QPainter(image)
        chart.paint_to_painter(painter=painter, paint_lines=False)
        painter.end()
        assert not image.isNull()
        selection_probe: QtCore.QPoint = QtCore.QPoint(
            int(selection_rect.left() + selection_rect.width() * 0.35),
            int(selection_rect.top() + selection_rect.height() * 0.35),
        )
        assert image.pixelColor(selection_probe) != chart._plot_color
        chart.mouseReleaseEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonRelease,
            widget=chart,
            local_position=selection_end,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.NoButton,
        ))
        assert chart._rhi_selection_overlay.isHidden()
        assert chart._zoom_selection is None
        adjusted_plot: QtCore.QRectF = chart._get_plot_rect()
        assert np.isclose(adjusted_plot.width(), plot_rect.width())
        assert np.isclose(adjusted_plot.height(), plot_rect.height())
        assert np.isclose(
            chart.axis_x.get_zoom() * selection_rect.width() / plot_rect.width(),
            x_zoom_before_selection,
        )
        assert np.isclose(
            chart.axis_y.get_zoom() * selection_rect.height() / plot_rect.height(),
            y_zoom_before_selection,
        )
        chart.wheelEvent(make_wheel_event(widget=chart, delta_y=120))
        assert chart.axis_x.get_zoom() > 1.0
        assert chart.axis_y.get_zoom() > 1.0
        assert chart._prepare_rhi_line_layer(plot_rect=chart._get_plot_rect())
        assert chart._rhi_line_widget._data_revision > first_revision
        first_revision = chart._rhi_line_widget._data_revision
        chart.reset_viewport()
        plot_rect = chart._get_plot_rect()
        pan_start: QtCore.QPointF = QtCore.QPointF(
            plot_rect.left() + plot_rect.width() * 0.35,
            plot_rect.top() + plot_rect.height() * 0.4,
        )
        pan_end: QtCore.QPointF = QtCore.QPointF(
            pan_start.x() + float(random_generator.uniform(8.0, 48.0)),
            pan_start.y() + float(random_generator.uniform(-24.0, 24.0)),
        )
        chart.mousePressEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonPress,
            widget=chart,
            local_position=pan_start,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
            modifiers=QtCore.Qt.KeyboardModifier.ControlModifier,
        ))
        chart.mouseMoveEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseMove,
            widget=chart,
            local_position=pan_end,
            button=QtCore.Qt.MouseButton.NoButton,
            buttons=QtCore.Qt.MouseButton.LeftButton,
            modifiers=QtCore.Qt.KeyboardModifier.ControlModifier,
        ))
        chart.mouseReleaseEvent(make_mouse_event(
            event_type=QtCore.QEvent.Type.MouseButtonRelease,
            widget=chart,
            local_position=pan_end,
            button=QtCore.Qt.MouseButton.LeftButton,
            buttons=QtCore.Qt.MouseButton.NoButton,
            modifiers=QtCore.Qt.KeyboardModifier.ControlModifier,
        ))
        assert chart.axis_x.get_pan() != 0.0 or chart.axis_y.get_pan() != 0.0
        assert chart._prepare_rhi_line_layer(plot_rect=chart._get_plot_rect())
        assert chart._rhi_line_widget._data_revision > first_revision
        first_revision = chart._rhi_line_widget._data_revision
        image = QtGui.QImage(chart.size(), QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        painter = QtGui.QPainter(image)
        chart.paint_to_painter(painter=painter, paint_lines=False)
        painter.end()
        assert not image.isNull()
        chart.reset_viewport()

    assert chart._prepare_rhi_line_layer(plot_rect=chart._get_plot_rect())
    chart.dispose()
    assert chart._rhi_line_widget is not None
    assert chart._rhi_line_widget._disposed
    assert chart._rhi_line_widget._vertices.size == 0
    assert chart._rhi_line_widget._buffer is None
    assert chart._rhi_line_widget._pipeline is None
    delete_chart_owner(owner=owner, chart=chart, probe=probe, app=qt_app)


def exercise_seeded_random_gui_operations(
        app: QtWidgets.QApplication,
        message_queue: Any,
        seed: int) -> None:
    """Exercise random mode changes and input sequences across Qt lifetimes.

    :param app: QApplication owned by the crash-contained child process.
    :param message_queue: Parent-visible queue used as a progress heartbeat.
    :param seed: Reproducible random operation seed.
    :return: None.
    """
    random_generator: np.random.Generator = np.random.default_rng(seed)
    window_index: int
    for window_index in range(6):
        owner: QtWidgets.QDialog = QtWidgets.QDialog()
        layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(owner)
        chart: GraphsWidget = GraphsWidget(parent=owner)
        probe: ObjectDestructionProbe = ObjectDestructionProbe()
        chart.destroyed.connect(probe.mark_destroyed)
        layout.addWidget(chart)
        chart.resize(520, 360)
        owner.show()
        app.processEvents()
        try:
            operation_trace: list[str] = list()
            operation_index: int
            for operation_index in range(36):
                operation: int = int(random_generator.integers(0, 9))
                point_count: int = int(random_generator.integers(2, 80))
                series_count: int = int(random_generator.integers(1, 7))
                x_values: np.ndarray = np.linspace(-10.0, 10.0, point_count, dtype=float)
                series_index: int
                if operation == 0:
                    names: list[str] = list()
                    values: list[np.ndarray] = list()
                    for series_index in range(series_count):
                        names.append(f"series {series_index}")
                        values.append(random_generator.normal(size=point_count))
                    if bool(random_generator.integers(0, 2)):
                        values[0][int(random_generator.integers(0, point_count))] = np.nan
                    else:
                        pass
                    accepted: bool = chart.set_line_series(
                        x_values=x_values,
                        series_names=names,
                        series_values=values,
                    )
                    assert accepted, f"seed {seed}, operation trace: {operation_trace}"
                    operation_trace.append("replace lines")
                elif operation == 1:
                    names = list()
                    values = list()
                    for series_index in range(series_count):
                        names.append(f"area {series_index}")
                        values.append(random_generator.normal(size=point_count))
                    accepted = chart.set_cumulative_area_series(
                        x_values=x_values,
                        series_names=names,
                        series_values=values,
                    )
                    assert accepted, f"seed {seed}, operation trace: {operation_trace}"
                    operation_trace.append("replace areas")
                elif operation == 2:
                    histogram_values: np.ndarray = random_generator.normal(size=point_count * 3)
                    if bool(random_generator.integers(0, 2)):
                        histogram_values[int(random_generator.integers(0, len(histogram_values)))] = np.nan
                    else:
                        pass
                    accepted = chart.set_histogram(
                        values=histogram_values,
                        bin_count=int(random_generator.integers(1, 20)),
                    )
                    assert accepted, f"seed {seed}, operation trace: {operation_trace}"
                    operation_trace.append("replace histogram")
                elif operation == 3:
                    bar_count: int = int(random_generator.integers(1, 12))
                    chart.add_horizontal_bar_series(
                        labels=tuple(f"bar {series_index}" for series_index in range(bar_count)),
                        values=random_generator.normal(size=bar_count),
                        positive_color="#0f766e",
                        negative_color="#dc2626",
                    )
                    assert chart._content_type == ChartContentType.HORIZONTAL_BAR
                    operation_trace.append("replace bars")
                elif operation == 4:
                    angles: np.ndarray = np.linspace(0.0, 360.0, point_count, dtype=float)
                    radii: np.ndarray = np.abs(random_generator.normal(size=point_count))
                    accepted = chart.set_polar_series(
                        series_names=("random polar",),
                        angle_values=(angles,),
                        radius_values=(radii,),
                        angle_unit=PolarAngleUnit.DEGREES,
                        connect_points=bool(random_generator.integers(0, 2)),
                    )
                    assert accepted, f"seed {seed}, operation trace: {operation_trace}"
                    operation_trace.append("replace polar")
                elif operation == 5:
                    if chart.get_series_count() > 0:
                        visible_index: int = int(random_generator.integers(0, chart.get_series_count()))
                        chart.set_series_visible(
                            series_index=visible_index,
                            visible=bool(random_generator.integers(0, 2)),
                        )
                    else:
                        chart.clear()
                    operation_trace.append("toggle visibility")
                elif operation == 6:
                    chart.wheelEvent(make_wheel_event(
                        widget=chart,
                        delta_y=120 if bool(random_generator.integers(0, 2)) else -120,
                    ))
                    operation_trace.append("wheel zoom")
                elif operation == 7:
                    if chart._content_type == ChartContentType.XY and chart.get_series_count() > 0:
                        drag_select_zoom(chart=chart)
                        if bool(random_generator.integers(0, 2)):
                            chart.reset_viewport()
                        else:
                            pass
                    else:
                        chart.reset_viewport()
                    operation_trace.append("selection zoom")
                else:
                    chart.resize(
                        int(random_generator.integers(320, 1200)),
                        int(random_generator.integers(240, 800)),
                    )
                    chart.setVisible(bool(random_generator.integers(0, 2)))
                    chart.show()
                    operation_trace.append("resize and show")

                app.processEvents()
                chart.repaint()
                image: QtGui.QImage = paint_chart_to_image(widget=chart)
                assert not image.isNull(), f"seed {seed}, operation trace: {operation_trace}"
                message_queue.put(
                    f"seed={seed} window={window_index + 1}/6 "
                    f"action={operation_index + 1}/36 trace={operation_trace[-4:]}"
                )

        finally:
            if not chart._disposed:
                delete_chart_owner(owner=owner, chart=chart, probe=probe, app=app)
            else:
                pass


def run_seeded_random_gui_operations_in_child(message_queue: Any, seed: int) -> None:
    """Run the random chart sequence in a process that can safely crash.

    :param message_queue: Parent-visible queue for progress and Python failures.
    :param seed: Reproducible random operation seed.
    :return: None.
    """
    faulthandler.enable()
    message_queue.put(f"starting chart GUI fuzz seed={seed}")
    try:
        app: QtWidgets.QApplication = QtWidgets.QApplication(
            list(("chart-gui-fuzz", "-platform", "offscreen"))
        )
        exercise_seeded_random_gui_operations(app=app, message_queue=message_queue, seed=seed)
        message_queue.put(f"chart GUI fuzz completed seed={seed}")
    except Exception:
        message_queue.put(traceback.format_exc())
        raise


@pytest.mark.parametrize("seed", (20260921, 20260922, 8675309))
def test_seeded_random_gui_operations_survive_repaint_and_close(
        qt_app: QtWidgets.QApplication,
        seed: int) -> None:
    """Fuzz chart modes and lifetimes in a child process with a watchdog.

    :param qt_app: Shared parent Qt application; the fuzz worker owns its own.
    :param seed: Reproducible random operation seed.
    :return: None.
    """
    _ = qt_app
    process_context: multiprocessing.context.BaseContext = multiprocessing.get_context("spawn")
    message_queue: Any = process_context.Queue()
    process: multiprocessing.Process = process_context.Process(
        target=run_seeded_random_gui_operations_in_child,
        args=(message_queue, seed),
    )
    process.start()
    last_message: str = "no child progress received"
    last_progress_time_s: float = time.monotonic()
    timeout_s: float = 90.0
    while process.is_alive() and time.monotonic() - last_progress_time_s <= timeout_s:
        try:
            queued_message: object = message_queue.get(timeout=1.0)
            last_message = queued_message if isinstance(queued_message, str) else repr(queued_message)
            last_progress_time_s = time.monotonic()
        except queue.Empty:
            pass

    if process.is_alive():
        process.terminate()
        process.join(10.0)
        raise AssertionError(f"chart GUI fuzz timed out after {timeout_s}s: {last_message}")
    else:
        process.join(10.0)

    try:
        while True:
            queued_message = message_queue.get_nowait()
            last_message = queued_message if isinstance(queued_message, str) else repr(queued_message)
    except queue.Empty:
        pass
    finally:
        message_queue.close()
        message_queue.join_thread()

    assert process.exitcode == 0, last_message


def test_chart_context_and_save_dialogs_do_not_retain_or_reenter_chart(
        qt_app: QtWidgets.QApplication) -> None:
    """Open and close chart menus and save dialogs without nested event loops.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    owner: QtWidgets.QDialog = QtWidgets.QDialog()
    chart: GraphsWidget = GraphsWidget(parent=owner)
    chart.resize(640, 420)
    owner.show()
    chart.show()
    app.processEvents()
    cycle_index: int
    for cycle_index in range(8):
        global_position: QtCore.QPoint = chart.mapToGlobal(QtCore.QPoint(30, 30))
        context_event: QtGui.QContextMenuEvent = QtGui.QContextMenuEvent(
            QtGui.QContextMenuEvent.Reason.Mouse,
            QtCore.QPoint(30, 30),
            global_position,
        )
        chart.contextMenuEvent(context_event)
        app.processEvents()
        chart_menus: list[QtWidgets.QMenu] = chart.findChildren(QtWidgets.QMenu)
        assert len(chart_menus) == 1
        chart_menus[0].close()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        assert len(chart.findChildren(QtWidgets.QMenu)) == 0

        chart._save_image_from_context_menu()
        assert chart._active_save_dialog is not None
        assert chart._active_save_dialog.parent() is chart
        chart._active_save_dialog.close()
        app.processEvents()
        assert chart._active_save_dialog is None

    context_position: QtCore.QPoint = chart.mapToGlobal(QtCore.QPoint(20, 20))
    final_context_event: QtGui.QContextMenuEvent = QtGui.QContextMenuEvent(
        QtGui.QContextMenuEvent.Reason.Mouse,
        QtCore.QPoint(20, 20),
        context_position,
    )
    chart.contextMenuEvent(final_context_event)
    app.processEvents()
    assert len(chart.findChildren(QtWidgets.QMenu)) == 1
    chart.dispose()
    app.processEvents()
    assert len(chart.findChildren(QtWidgets.QMenu)) == 0
    owner.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()


def test_rhi_widget_copies_and_releases_all_cpu_buffers(
        qt_app: QtWidgets.QApplication) -> None:
    """Keep caller arrays isolated and release renderer-owned arrays explicitly.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    _ = qt_app
    renderer: RhiLineChartWidget = RhiLineChartWidget()
    vertices: np.ndarray = np.asarray(((-1.0, -1.0), (1.0, 1.0)), dtype=np.float32)
    lengths: np.ndarray = np.asarray((2,), dtype=np.int32)
    assert renderer.set_vertices(
        vertices=vertices,
        series_lengths=lengths,
        series_colors=(QtGui.QColor("#2563eb"),),
    )
    vertices.fill(0.0)
    lengths[0] = 0
    assert renderer._vertices[1, 0] == 1.0
    assert renderer._series_lengths[0] == 2

    renderer.clear_data()
    assert renderer._vertices.size == 0
    assert renderer._series_lengths.size == 0
    assert renderer._series_first_vertices.size == 0
    assert renderer._vertex_count == 0

    renderer.dispose()
    assert renderer._disposed
    assert renderer._vertices.size == 0
    assert renderer._buffer is None
    assert renderer._pipeline is None
    assert not renderer.set_vertices(
        vertices=np.asarray(((0.0, 0.0), (1.0, 1.0)), dtype=np.float32),
        series_lengths=(2,),
        series_colors=(QtGui.QColor("#2563eb"),),
    )
    renderer.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


def test_chart_colors_follow_application_palette_changes(qt_app: QtWidgets.QApplication) -> None:
    """Keep the painter theme aligned with Qt palette changes after construction.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    _ = qt_app
    chart: GraphsWidget = GraphsWidget()
    dark_palette: QtGui.QPalette = QtGui.QPalette(chart.palette())
    dark_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#202020"))
    chart.setPalette(dark_palette)
    assert chart._background_color == QtGui.QColor("#171c24")
    assert chart._plot_color == QtGui.QColor("#202834")
    assert chart._label_color == QtGui.QColor("#e7edf5")
    assert chart._grid_color == QtGui.QColor("#445164")

    light_palette: QtGui.QPalette = QtGui.QPalette(chart.palette())
    light_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#ffffff"))
    chart.setPalette(light_palette)
    assert chart._background_color == QtGui.QColor("#ffffff")
    assert chart._plot_color == QtGui.QColor("#f7fbff")
    assert chart._label_color == QtGui.QColor("#17324a")
    assert chart._grid_color == QtGui.QColor("#cbd5e1")

    chart.dispose()
    chart.deleteLater()
    QtWidgets.QApplication.sendPostedEvents(None)
