# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Small QWidget chart renderer with explicit Python ownership of chart data."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from enum import Enum, auto
from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
import shiboken6
from VeraGrid.Gui.PlotDialogue.qt_rhi_line_chart_widget import RhiLineChartWidget


class ChartSeriesType(Enum):
    """Rendering primitive stored by :class:`ChartSeries`."""

    LINE = auto()
    SCATTER = auto()
    HORIZONTAL_BAR = auto()
    CUMULATIVE_AREA = auto()
    POLAR = auto()
    POLAR_SCATTER = auto()
    HISTOGRAM = auto()


class ChartContentType(Enum):
    """Coordinate system currently drawn by :class:`GraphsWidget`."""

    XY = auto()
    HORIZONTAL_BAR = auto()
    CUMULATIVE_AREA = auto()
    POLAR = auto()
    HISTOGRAM = auto()


class PolarAngleUnit(Enum):
    """Unit used by the angle buffers of a polar series."""

    RADIANS = auto()
    DEGREES = auto()


def calculate_tight_axis_padding(minimum: float, maximum: float) -> float:
    """Calculate a proportional margin for one finite data interval.

    :param minimum: Lowest finite data value represented on the axis.
    :param maximum: Highest finite data value represented on the axis.
    :return: Five-percent padding based on the span, or on the value magnitude for a constant interval.
    """
    # A varying signal is framed from its actual excursion so short time
    # windows and small-amplitude results do not inherit an arbitrary margin.
    span: float = maximum - minimum
    if span > 0.0:
        padding: float = span * 0.05
    else:
        # A constant signal still needs a non-degenerate axis. Its magnitude
        # supplies a meaningful scale, with a small neutral range at zero.
        magnitude: float = max(abs(minimum), abs(maximum))
        if magnitude > 0.0:
            padding = magnitude * 0.05
        else:
            padding = 0.05
    return padding


class ChartAxis:
    """Value axis state held in Python and consumed by the painter only."""

    __slots__ = ("_title", "_minimum", "_maximum", "_zoom", "_pan")

    def __init__(self) -> None:
        """Create a one-unit visible range without native QObject ownership.

        :return: None.
        """
        self._title: str = ""
        self._minimum: float = 0.0
        self._maximum: float = 1.0
        self._zoom: float = 1.0
        self._pan: float = 0.0

    def set_title(self, title: str) -> None:
        """Set the axis caption rendered around the plot area.

        :param title: Axis caption.
        :return: None.
        """
        self._title = title

    def get_title(self) -> str:
        """Return the current axis caption.

        :return: Axis caption.
        """
        return self._title

    def set_range(self, minimum: float, maximum: float) -> None:
        """Set a finite non-degenerate data range.

        :param minimum: Lowest data value.
        :param maximum: Highest data value.
        :return: None.
        """
        if np.isfinite(minimum) and np.isfinite(maximum) and maximum > minimum:
            self._minimum = minimum
            self._maximum = maximum
        else:
            self._minimum = 0.0
            self._maximum = 1.0

    def get_range(self) -> tuple[float, float]:
        """Return the complete unzoomed data range.

        :return: Minimum and maximum data values.
        """
        return self._minimum, self._maximum

    def set_zoom(self, zoom: float) -> None:
        """Set a bounded viewport magnification.

        :param zoom: Requested viewport magnification.
        :return: None.
        """
        if np.isfinite(zoom):
            self._zoom = min(max(zoom, 1.0), 20.0)
        else:
            self._zoom = 1.0

    def get_zoom(self) -> float:
        """Return the viewport magnification.

        :return: Viewport magnification.
        """
        return self._zoom

    def set_pan(self, pan: float) -> None:
        """Set the data-unit offset from the complete range centre.

        :param pan: Data-unit viewport offset.
        :return: None.
        """
        if np.isfinite(pan):
            self._pan = pan
        else:
            self._pan = 0.0

    def get_pan(self) -> float:
        """Return the data-unit viewport offset.

        :return: Data-unit viewport offset.
        """
        return self._pan

    def reset_viewport(self) -> None:
        """Show the complete range without a pan offset.

        :return: None.
        """
        self._zoom = 1.0
        self._pan = 0.0

    def get_visual_range(self) -> tuple[float, float]:
        """Return the range currently visible after zoom and pan.

        :return: Minimum and maximum displayed values.
        """
        span: float = (self._maximum - self._minimum) / self._zoom
        centre: float = (self._minimum + self._maximum) * 0.5 + self._pan
        return centre - span * 0.5, centre + span * 0.5

    def set_visual_range(self, minimum: float, maximum: float) -> None:
        """Set the visible range selected by a chart rectangle.

        :param minimum: Lower selected data value.
        :param maximum: Upper selected data value.
        :return: None.
        """
        full_span: float = self._maximum - self._minimum
        selected_span: float = maximum - minimum
        if (np.isfinite(minimum) and np.isfinite(maximum) and full_span > 0.0
                and selected_span > 0.0):
            selected_centre: float = (minimum + maximum) * 0.5
            full_centre: float = (self._minimum + self._maximum) * 0.5
            # Rectangle zoom must preserve narrow selections; wheel zoom still uses set_zoom().
            self._zoom = max(full_span / selected_span, 1.0)
            self.set_pan(selected_centre - full_centre)
        else:
            pass


class ChartSeries:
    """One Python-owned chart series with private NumPy point buffers."""

    __slots__ = (
        "_series_type",
        "_name",
        "_x_data",
        "_y_data",
        "_color",
        "_dashed",
        "_point_tooltips",
        "_visible",
        "_x_is_monotonic",
    )

    def __init__(self,
                 series_type: ChartSeriesType,
                 name: str,
                 x_data: np.ndarray,
                 y_data: np.ndarray,
                 color: QtGui.QColor,
                 point_tooltips: Sequence[str] | None = None,
                 copy_buffers: bool = True,
                 x_is_monotonic: bool | None = None,
                 dashed: bool = False) -> None:
        """Create a series whose buffers are owned by this Python object.

        :param series_type: Rendering primitive for the point buffers.
        :param name: Legend label.
        :param x_data: Already validated horizontal point values.
        :param y_data: Already validated vertical point values.
        :param color: Visible series colour.
        :param point_tooltips: Optional text paired with scatter points.
        :param copy_buffers: Whether data belongs to a caller and must be copied.
        :param x_is_monotonic: Known X ordering, when already established by a batch owner.
        :param dashed: Whether a line series uses a dashed stroke.
        :return: None.
        """
        self._series_type: ChartSeriesType = series_type
        self._name: str = name
        self._x_data: np.ndarray = np.zeros(0, dtype=float)
        self._y_data: np.ndarray = np.zeros(0, dtype=float)
        self._color: QtGui.QColor = QtGui.QColor(color)
        self._dashed: bool = dashed
        self._point_tooltips: list[str] = list()
        self._visible: bool = True
        self._x_is_monotonic: bool = True
        self.replace_data(
            x_data=x_data,
            y_data=y_data,
            color=color,
            copy_buffers=copy_buffers,
            x_is_monotonic=x_is_monotonic,
        )
        self.set_point_tooltips(point_tooltips=point_tooltips)

    def get_series_type(self) -> ChartSeriesType:
        """Return the primitive used to paint this series.

        :return: Series primitive.
        """
        return self._series_type

    def get_name(self) -> str:
        """Return the legend label.

        :return: Legend label.
        """
        return self._name

    def get_x_data(self) -> np.ndarray:
        """Return the private horizontal buffer for GUI-thread painting.

        :return: Horizontal values owned by this series.
        """
        return self._x_data

    def get_y_data(self) -> np.ndarray:
        """Return the private vertical buffer for GUI-thread painting.

        :return: Vertical values owned by this series.
        """
        return self._y_data

    def get_color(self) -> QtGui.QColor:
        """Return the value-type colour used while painting.

        :return: Series colour.
        """
        return QtGui.QColor(self._color)

    def get_dashed(self) -> bool:
        """Return whether this line uses a dashed stroke.

        :return: Whether the painter renders this series with dashes.
        """
        return self._dashed

    def get_visible(self) -> bool:
        """Return whether the painter must draw this series.

        :return: Whether this series is included in the current plot.
        """
        return self._visible

    def set_visible(self, visible: bool) -> None:
        """Set whether the painter includes this series.

        :param visible: New drawing state.
        :return: None.
        """
        self._visible = visible

    def get_x_is_monotonic(self) -> bool:
        """Return whether X values are sorted in ascending order.

        :return: Whether search-based viewport sampling is safe.
        """
        return self._x_is_monotonic

    def set_point_tooltips(self, point_tooltips: Sequence[str] | None) -> bool:
        """Set optional text paired with every retained scatter point.

        :param point_tooltips: Text in the same order as the private point buffer.
        :return: Whether the text count matched the point count.
        """
        if point_tooltips is None:
            self._point_tooltips.clear()
            return True
        elif len(point_tooltips) == len(self._x_data):
            tooltip_index: int
            tooltip_values: list[str] = list()
            for tooltip_index in range(len(point_tooltips)):
                tooltip_values.append(str(point_tooltips[tooltip_index]))
            self._point_tooltips = tooltip_values
            return True
        else:
            self._point_tooltips.clear()
            return False

    def get_point_tooltip(self, point_index: int) -> str | None:
        """Return optional text for one point in the private buffer.

        :param point_index: Index in the private point buffer.
        :return: Tooltip text, or ``None`` when this series has no text there.
        """
        if 0 <= point_index < len(self._point_tooltips):
            return self._point_tooltips[point_index]
        else:
            return None

    def has_point_tooltips(self) -> bool:
        """Return whether this series has text for all retained points.

        :return: Whether point tooltip text is available.
        """
        return len(self._point_tooltips) == len(self._x_data) and len(self._point_tooltips) > 0

    def replace_data(self,
                     x_data: np.ndarray,
                     y_data: np.ndarray,
                     color: QtGui.QColor,
                     copy_buffers: bool = True,
                     x_is_monotonic: bool | None = None) -> None:
        """Replace both private point buffers after caller-side validation.

        :param x_data: Finite horizontal values.
        :param y_data: Finite vertical values.
        :param color: New visible series colour.
        :param copy_buffers: Whether data belongs to a caller and must be copied.
        :param x_is_monotonic: Known X ordering, when already established by a batch owner.
        :return: None.
        """
        # The batch API has already made its own arrays, allowing one X buffer to be shared safely.
        if copy_buffers:
            self._x_data = np.ascontiguousarray(x_data, dtype=float).copy()
            self._y_data = np.ascontiguousarray(y_data, dtype=float).copy()
        else:
            self._x_data = np.ascontiguousarray(x_data, dtype=float)
            self._y_data = np.ascontiguousarray(y_data, dtype=float)
        self._color = QtGui.QColor(color)
        if x_is_monotonic is None:
            self._x_is_monotonic = bool(np.all(self._x_data[1:] >= self._x_data[:-1]))
        else:
            self._x_is_monotonic = x_is_monotonic
        if len(self._point_tooltips) != len(self._x_data):
            self._point_tooltips.clear()
        else:
            pass

    def release_data(self) -> None:
        """Drop NumPy references before the owning QWidget is destroyed.

        :return: None.
        """
        self._x_data = np.zeros(0, dtype=float)
        self._y_data = np.zeros(0, dtype=float)
        self._point_tooltips.clear()
        self._visible = False
        self._x_is_monotonic = True


def prepare_chart_points(x_values: Sequence[float] | np.ndarray,
                         y_values: Sequence[float] | np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Validate paired numeric values and return isolated finite buffers.

    :param x_values: Candidate horizontal values.
    :param y_values: Candidate vertical values.
    :return: Finite copied point buffers, or ``None`` for incompatible inputs.
    """
    x_data: np.ndarray = np.asarray(x_values, dtype=float)
    y_data: np.ndarray = np.asarray(y_values, dtype=float)
    if x_data.ndim == 1 and y_data.ndim == 1 and len(x_data) == len(y_data):
        finite_mask: np.ndarray = np.isfinite(x_data) & np.isfinite(y_data)
        return np.ascontiguousarray(x_data[finite_mask], dtype=float), np.ascontiguousarray(y_data[finite_mask], dtype=float)
    else:
        return None


def prepare_chart_point_tooltips(x_values: np.ndarray,
                                 y_values: Sequence[float] | np.ndarray,
                                 point_tooltips: Sequence[str] | None) -> list[str] | None:
    """Filter optional point text with the finite values retained for drawing.

    :param x_values: Candidate numeric horizontal values.
    :param y_values: Candidate vertical values.
    :param point_tooltips: Optional text in source-point order.
    :return: Text in retained-point order, or ``None`` without valid metadata.
    """
    if point_tooltips is not None:
        y_data: np.ndarray = np.asarray(y_values, dtype=float)
        if (x_values.ndim == 1 and y_data.ndim == 1
                and len(point_tooltips) == len(x_values) and len(x_values) == len(y_data)):
            finite_mask: np.ndarray = np.isfinite(x_values) & np.isfinite(y_data)
            retained_tooltips: list[str] = list()
            tooltip_index: int
            for tooltip_index in range(len(point_tooltips)):
                if finite_mask[tooltip_index]:
                    retained_tooltips.append(str(point_tooltips[tooltip_index]))
                else:
                    pass
            return retained_tooltips
        else:
            return None
    else:
        return None


def prepare_chart_x_values(x_values: Sequence[float] | np.ndarray) -> tuple[np.ndarray, bool]:
    """Convert numeric or NumPy datetime horizontal coordinates to floats.

    :param x_values: Candidate horizontal values.
    :return: Milliseconds or numeric values, plus whether date labels are needed.
    """
    raw_x_values: np.ndarray = np.asarray(x_values)
    if np.issubdtype(raw_x_values.dtype, np.datetime64):
        x_data: np.ndarray = raw_x_values.astype("datetime64[ms]").astype(np.int64).astype(float)
        x_data[np.isnat(raw_x_values)] = np.nan
        return x_data, True
    else:
        return np.asarray(x_values, dtype=float), False


def format_chart_value(value: float, is_datetime: bool) -> str:
    """Format one axis tick without storing any Qt date-time object.

    :param value: Numeric tick value.
    :param is_datetime: Whether the value represents epoch milliseconds.
    :return: Visible tick text.
    """
    if is_datetime:
        # Epoch coordinates are absolute values, so their labels must not move
        # with the workstation time zone.
        date_value: QtCore.QDateTime = QtCore.QDateTime.fromMSecsSinceEpoch(
            int(value),
            QtCore.Qt.TimeSpec.UTC,
        )
        return date_value.toString("dd/MM/yyyy\nHH:mm:ss")
    elif abs(value) >= 10000.0 or (0.0 < abs(value) < 0.01):
        return f"{value:.2e}"
    else:
        return f"{value:.4g}"


class ChartSelectionOverlay(QtWidgets.QWidget):
    """Paint a transient zoom rectangle above a native QRhi child widget."""

    __slots__ = ("_selection", "_plot_rect")

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        """Create a transparent, input-pass-through chart overlay.

        :param parent: Chart whose plot-selection rectangle is shown.
        :return: None.
        """
        super().__init__(parent)
        self._selection: QtCore.QRectF | None = None
        self._plot_rect: QtCore.QRectF = QtCore.QRectF()
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.hide()

    def set_selection(self,
                      selection: QtCore.QRectF | None,
                      plot_rect: QtCore.QRectF) -> None:
        """Show the current rectangle above QRhi-rendered lines.

        :param selection: Current drag rectangle in chart coordinates.
        :param plot_rect: Plot bounds used to clip the selection.
        :return: None.
        """
        if selection is not None:
            self._selection = QtCore.QRectF(selection)
            self._plot_rect = QtCore.QRectF(plot_rect)
            self.update()
            self.show()
            self.raise_()
        else:
            self._selection = None
            self.hide()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the translucent selection rectangle without touching plot data.

        :param event: Paint request delivered by QWidget.
        :return: None.
        """
        _ = event
        if self._selection is not None:
            visible_selection: QtCore.QRectF = self._selection.intersected(self._plot_rect)
            if visible_selection.width() > 0.0 and visible_selection.height() > 0.0:
                painter: QtGui.QPainter = QtGui.QPainter(self)
                selection_color: QtGui.QColor = QtGui.QColor("#2563eb")
                fill_color: QtGui.QColor = QtGui.QColor(selection_color)
                fill_color.setAlpha(48)
                painter.setPen(QtGui.QPen(selection_color, 1.0, QtCore.Qt.PenStyle.DashLine))
                painter.setBrush(QtGui.QBrush(fill_color))
                painter.drawRect(visible_selection)
                painter.end()
            else:
                pass
        else:
            pass


class GraphsWidget(QtWidgets.QWidget):
    """Paint native line, scatter, area, bar, polar, and histogram charts."""

    __slots__ = (
        "_stacked_enabled", "_bar_enabled", "_row_labels", "_transform_source", "_cdf_enabled", "_abs_enabled", "_transpose_enabled", "_catalog_detached",
        "axis_x",
        "axis_y",
        "_series",
        "_content_type",
        "_bar_labels",
        "_title",
        "_has_points",
        "_x_min",
        "_x_max",
        "_y_min",
        "_y_max",
        "_x_is_datetime", "_y_is_datetime",
        "_pan_position",
        "_pan_button",
        "_zoom_origin",
        "_zoom_selection",
        "_disposed",
        "_background_color",
        "_plot_color",
        "_label_color",
        "_grid_color",
        "_legend_visible",
        "_legend_overlay",
        "_equal_axis_scale",
        "_rhi_line_widget",
        "_rhi_selection_overlay",
        "_rhi_line_enabled",
        "_rhi_line_threshold",
        "_rhi_line_failed",
        "_rhi_line_cache_key",
        "_active_save_dialog",
        "_axis_limit_editor",
        "_editing_axis_index",
        "_editing_minimum",
        "_tight_axis_layout",
    )

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Create a single QWidget chart with Python-owned state only.

        :param parent: Parent Qt widget that owns this chart widget.
        :return: None.
        """
        QtWidgets.QWidget.__init__(self, parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.DefaultContextMenu)

        # The axes and series are plain Python values, so QWidget owns every native object involved.
        self._stacked_enabled: bool = False
        self._bar_enabled: bool = False
        self._row_labels: dict[float, str] = dict()
        self._catalog_detached: bool = False
        self._transform_source: GraphsWidget | None = None
        self._cdf_enabled: bool = False
        self._abs_enabled: bool = False
        self._transpose_enabled: bool = False
        self.axis_x: ChartAxis = ChartAxis()
        self.axis_y: ChartAxis = ChartAxis()
        self._series: list[ChartSeries] = list()
        self._content_type: ChartContentType = ChartContentType.XY
        self._bar_labels: list[str] = list()
        self._title: str = ""
        self._has_points: bool = False
        self._x_min: float = 0.0
        self._x_max: float = 1.0
        self._y_min: float = 0.0
        self._y_max: float = 1.0
        self._x_is_datetime: bool = False
        self._y_is_datetime: bool = False
        self._pan_position: QtCore.QPointF | None = None
        self._pan_button: QtCore.Qt.MouseButton | None = None
        self._zoom_origin: QtCore.QPointF | None = None
        self._zoom_selection: QtCore.QRectF | None = None
        self._disposed: bool = False
        self._background_color: QtGui.QColor = QtGui.QColor("#ffffff")
        self._plot_color: QtGui.QColor = QtGui.QColor("#f7fbff")
        self._label_color: QtGui.QColor = QtGui.QColor("#17324a")
        self._grid_color: QtGui.QColor = QtGui.QColor("#cbd5e1")
        self._legend_visible: bool = True
        self._legend_overlay: bool = False
        self._equal_axis_scale: bool = False
        self._rhi_line_widget: RhiLineChartWidget | None = None
        self._rhi_selection_overlay: ChartSelectionOverlay | None = None
        self._rhi_line_enabled: bool = False
        self._rhi_line_threshold: int = 64
        self._rhi_line_failed: bool = False
        self._rhi_line_cache_key: tuple[object, ...] | None = None
        self._active_save_dialog: QtWidgets.QFileDialog | None = None
        self._axis_limit_editor: QtWidgets.QLineEdit = QtWidgets.QLineEdit(self)
        self._axis_limit_editor.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._axis_limit_editor.setFont(self.font())
        self._axis_limit_editor.setFrame(True)
        self._axis_limit_editor.hide()
        self._axis_limit_editor.returnPressed.connect(self._apply_axis_input_range)
        self._axis_limit_editor.editingFinished.connect(self._apply_axis_input_range)
        self._editing_axis_index: int = -1
        self._editing_minimum: bool = False
        self._tight_axis_layout: bool = False
        self.apply_theme(dark=self.palette().color(QtGui.QPalette.ColorRole.Window).lightness() < 128)
        self._set_axis_ranges()

    def sizeHint(self) -> QtCore.QSize:
        """Return a useful initial size while allowing layout expansion.

        :return: Preferred chart size.
        """
        return QtCore.QSize(560, 360)

    def minimumSizeHint(self) -> QtCore.QSize:
        """Return a small usable chart size for narrow editor panels.

        :return: Minimum preferred chart size.
        """
        return QtCore.QSize(240, 180)

    def apply_theme(self, dark: bool) -> None:
        """Set paint colours from the surrounding Qt Widgets palette choice.

        :param dark: Whether the surrounding application uses a dark palette.
        :return: None.
        """
        if dark:
            background_color: QtGui.QColor = QtGui.QColor("#171c24")
            plot_color: QtGui.QColor = QtGui.QColor("#202834")
            label_color: QtGui.QColor = QtGui.QColor("#e7edf5")
            grid_color: QtGui.QColor = QtGui.QColor("#445164")
        else:
            background_color = QtGui.QColor("#ffffff")
            plot_color = QtGui.QColor("#f7fbff")
            label_color = QtGui.QColor("#17324a")
            grid_color = QtGui.QColor("#cbd5e1")
        if (self._background_color != background_color or self._plot_color != plot_color
                or self._label_color != label_color or self._grid_color != grid_color):
            self._background_color = background_color
            self._plot_color = plot_color
            self._label_color = label_color
            self._grid_color = grid_color
            if self._can_mutate():
                self.update()
            else:
                pass
        else:
            pass
        editor_palette: QtGui.QPalette = QtGui.QPalette(self._axis_limit_editor.palette())
        editor_palette.setColor(QtGui.QPalette.ColorRole.Base, plot_color)
        editor_palette.setColor(QtGui.QPalette.ColorRole.Text, label_color)
        self._axis_limit_editor.setPalette(editor_palette)

    def setTitle(self, title: str) -> None:
        """Set the visible plot title.

        :param title: Plot title.
        :return: None.
        """
        if self._can_mutate():
            self._title = title
            self.update()
        else:
            pass

    def set_axis_titles(self, x_title: str, y_title: str) -> None:
        """Set the labels shown on both axes.

        :param x_title: Horizontal axis title.
        :param y_title: Vertical axis title.
        :return: None.
        """
        if self._can_mutate():
            self.axis_x.set_title(x_title)
            self.axis_y.set_title(y_title)
            self.update()
        else:
            pass

    def set_equal_axis_scale(self, enabled: bool) -> None:
        """Keep horizontal and vertical data units at the same visual scale.

        :param enabled: Whether the XY plot area must be square.
        :return: None.
        """
        if self._can_mutate() and self._equal_axis_scale != enabled:
            self._equal_axis_scale = enabled
            self.update()
        else:
            pass

    def reset_viewport(self) -> None:
        """Show every stored data point and clear the current pan offset.

        :return: None.
        """
        if self._can_mutate():
            self.axis_x.reset_viewport()
            self.axis_y.reset_viewport()
            self.update()
        else:
            pass

    def _begin_axis_limit_edit(self, axis_index: int, minimum: bool) -> None:
        """Show the editor over the selected endpoint label.

        :param axis_index: Zero for X or one for Y.
        :param minimum: Whether the lower endpoint is being edited.
        :return: None.
        """
        axis: ChartAxis = self.axis_x if axis_index == 0 else self.axis_y
        border_value: float = axis.get_visual_range()[0 if minimum else 1]
        is_datetime: bool = self._x_is_datetime if axis_index == 0 else self._y_is_datetime
        if is_datetime:
            # Use UTC both here and while parsing so editing a displayed limit
            # returns exactly the same epoch coordinate on every workstation.
            editor_date: QtCore.QDateTime = QtCore.QDateTime.fromMSecsSinceEpoch(
                int(border_value),
                QtCore.Qt.TimeSpec.UTC,
            )
            editor_text: str = editor_date.toString("dd/MM/yyyy HH:mm:ss")
            editor_width: int = 150
        else:
            editor_text = f"{border_value:.12g}"
            editor_width = 100
        plot_rect: QtCore.QRectF = self._get_plot_rect()
        if axis_index == 0:
            anchor_x: float = plot_rect.left() if minimum else plot_rect.right()
            editor_x: int = int(anchor_x - editor_width * 0.5)
            editor_y: int = int(plot_rect.bottom() + 2.0)
        else:
            editor_x = 2
            anchor_y: float = plot_rect.bottom() if minimum else plot_rect.top()
            editor_y = int(anchor_y - 11.0)
        self._editing_axis_index = axis_index
        self._editing_minimum = minimum
        self._axis_limit_editor.setToolTip(self.tr("Enter a finite axis limit and press Enter"))
        self._axis_limit_editor.setGeometry(editor_x, editor_y, editor_width, 22)
        self._axis_limit_editor.setText(editor_text)
        self._axis_limit_editor.show()
        self._axis_limit_editor.raise_()
        self._axis_limit_editor.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
        self._axis_limit_editor.selectAll()

    def _apply_axis_input_range(self) -> None:
        """Apply one edited border when it forms a finite, ordered axis range.

        :return: None.
        """
        if self._can_mutate() and self._editing_axis_index in (0, 1):
            axis: ChartAxis = self.axis_x if self._editing_axis_index == 0 else self.axis_y
            current_minimum: float
            current_maximum: float
            current_minimum, current_maximum = axis.get_visual_range()
            is_datetime: bool = self._x_is_datetime if self._editing_axis_index == 0 else self._y_is_datetime
            border_value: float | None = self._parse_axis_input(self._axis_limit_editor.text(), is_datetime)
            if border_value is not None:
                requested_minimum: float = border_value if self._editing_minimum else current_minimum
                requested_maximum: float = current_maximum if self._editing_minimum else border_value
                if requested_maximum > requested_minimum:
                    axis.set_range(requested_minimum, requested_maximum)
                    axis.reset_viewport()
                else:
                    pass
            else:
                pass
            self._axis_limit_editor.hide()
            self._editing_axis_index = -1
            self.update()
        else:
            self._axis_limit_editor.hide()

    def _parse_axis_input(self, text: str, is_datetime: bool) -> float | None:
        """Parse a finite numeric border or a displayed date-time border.

        :param text: Editor contents to validate.
        :param is_datetime: Whether this X axis uses epoch milliseconds.
        :return: Finite border value, or ``None`` when invalid.
        """
        if is_datetime:
            local_date_value: QtCore.QDateTime = QtCore.QDateTime.fromString(
                text,
                "dd/MM/yyyy HH:mm:ss",
            )
            if local_date_value.isValid():
                # Rebuild the parsed calendar fields as UTC instead of letting
                # Qt attach the machine's local time zone implicitly.
                utc_date_value: QtCore.QDateTime = QtCore.QDateTime(
                    local_date_value.date(),
                    local_date_value.time(),
                    QtCore.Qt.TimeSpec.UTC,
                )
                return float(utc_date_value.toMSecsSinceEpoch())
            else:
                return None
        else:
            try:
                numeric_value: float = float(text)
            except ValueError:
                return None
            if np.isfinite(numeric_value):
                return numeric_value
            else:
                return None

    def get_series_count(self) -> int:
        """Return the number of Python-owned chart series.

        :return: Number of series in display order.
        """
        return len(self._series)

    def get_series_name(self, series_index: int) -> str:
        """Return one series name without exposing the owning series object.

        :param series_index: Position in display order.
        :return: Series name, or an empty string for an invalid position.
        """
        if 0 <= series_index < len(self._series):
            return self._series[series_index].get_name()
        else:
            return ''

    def get_series_color(self, series_index: int) -> QtGui.QColor:
        """Return one series colour without exposing the owning series object.

        :param series_index: Position in display order.
        :return: Series colour, or an invalid colour for an invalid position.
        """
        if 0 <= series_index < len(self._series):
            return self._series[series_index].get_color()
        else:
            return QtGui.QColor()

    def get_series_visible(self, series_index: int) -> bool:
        """Return the display state of one series.

        :param series_index: Position in display order.
        :return: Whether the selected series is painted.
        """
        if 0 <= series_index < len(self._series):
            return self._series[series_index].get_visible()
        else:
            return False

    def set_series_visible(self, series_index: int, visible: bool) -> bool:
        """Set one series display state and schedule a single paint pass.

        :param series_index: Position in display order.
        :param visible: Whether the painter includes the selected series.
        :return: Whether the series position was valid while the chart was active.
        """
        if self._can_mutate() and 0 <= series_index < len(self._series):
            self._series[series_index].set_visible(visible=visible)
            self.update()
            return True
        else:
            return False

    def set_legend_visible(self, visible: bool) -> None:
        """Set whether the in-plot legend reserves part of the data area.

        :param visible: Whether named series are painted above the axes.
        :return: None.
        """
        if self._can_mutate() and self._legend_visible != visible:
            self._legend_visible = visible
            self.update()
        else:
            pass

    def set_legend_overlay(self, enabled: bool) -> None:
        """Draw the visible legend over the data area without reserving height.

        :param enabled: Whether the legend overlays the upper plot area.
        :return: None.
        """
        if self._can_mutate() and self._legend_overlay != enabled:
            self._legend_overlay = enabled
            self.update()
        else:
            pass

    def set_tight_axis_layout(self, enabled: bool) -> None:
        """Use data-scaled margins for both chart axes.

        :param enabled: Whether both axis margins follow their finite data ranges.
        :return: None.
        """
        if self._can_mutate():
            self._tight_axis_layout = enabled
            self._set_axis_ranges()
            self.update()
        else:
            pass

    def set_line_series(self,
                        x_values: Sequence[float] | np.ndarray,
                        series_names: Sequence[str],
                        series_values: Sequence[Sequence[float] | np.ndarray],
                        colors: Sequence[str | None] | None = None) -> bool:
        """Replace the chart with line series that share one isolated X buffer.

        :param x_values: Numeric or NumPy datetime coordinates shared by every line.
        :param series_names: Visible name for each line.
        :param series_values: One Y buffer for each name in display order.
        :param colors: Optional Qt colour for each line.
        :return: Whether every input buffer had a compatible finite shape.
        """
        series_count: int = len(series_names)
        if self._can_mutate() and series_count > 0 and len(series_values) == series_count:
            if colors is None:
                color_values: list[str | None] = list()
                series_index: int
                for series_index in range(series_count):
                    color_values.append(None)
            elif len(colors) == series_count:
                color_values = list(colors)
            else:
                return False

            x_data: np.ndarray
            is_datetime: bool
            x_data, is_datetime = prepare_chart_x_values(x_values=x_values)
            if x_data.ndim == 1 and len(x_data) > 0:
                pass
            else:
                return False
            x_is_finite: bool = bool(np.all(np.isfinite(x_data)))
            x_is_monotonic: bool = bool(np.all(x_data[1:] >= x_data[:-1]))
            values_data: list[np.ndarray] = list()
            all_values_finite: bool = True
            series_index: int
            for series_index in range(series_count):
                y_data: np.ndarray = np.asarray(series_values[series_index], dtype=float)
                if y_data.ndim == 1 and len(y_data) == len(x_data):
                    values_data.append(y_data)
                    all_values_finite = all_values_finite and bool(np.all(np.isfinite(y_data)))
                else:
                    return False

            new_series: list[ChartSeries] = list()
            has_points: bool = False
            minimum_x: float = 0.0
            maximum_x: float = 1.0
            minimum_y: float = 0.0
            maximum_y: float = 1.0
            if x_is_finite and all_values_finite:
                # One private X array prevents 2,224 identical copies for wide time-series tables.
                retained_x_data: np.ndarray = np.ascontiguousarray(x_data, dtype=float).copy()
                for series_index in range(series_count):
                    retained_y_data: np.ndarray = np.ascontiguousarray(values_data[series_index], dtype=float).copy()
                    new_series.append(ChartSeries(
                        series_type=ChartSeriesType.LINE,
                        name=str(series_names[series_index]),
                        x_data=retained_x_data,
                        y_data=retained_y_data,
                        color=self.make_series_color(
                            color_name=color_values[series_index],
                            series_index=series_index,
                        ),
                        copy_buffers=False,
                        x_is_monotonic=x_is_monotonic,
                    ))
                    if has_points:
                        minimum_y = min(minimum_y, float(np.min(retained_y_data)))
                        maximum_y = max(maximum_y, float(np.max(retained_y_data)))
                    else:
                        minimum_x = float(np.min(retained_x_data))
                        maximum_x = float(np.max(retained_x_data))
                        minimum_y = float(np.min(retained_y_data))
                        maximum_y = float(np.max(retained_y_data))
                        has_points = True
            else:
                for series_index in range(series_count):
                    points: tuple[np.ndarray, np.ndarray] | None = prepare_chart_points(
                        x_values=x_data,
                        y_values=values_data[series_index],
                    )
                    if points is not None and len(points[0]) > 0:
                        new_series.append(ChartSeries(
                            series_type=ChartSeriesType.LINE,
                            name=str(series_names[series_index]),
                            x_data=points[0],
                            y_data=points[1],
                            color=self.make_series_color(
                                color_name=color_values[series_index],
                                series_index=series_index,
                            ),
                            copy_buffers=False,
                        ))
                        if has_points:
                            minimum_x = min(minimum_x, float(np.min(points[0])))
                            maximum_x = max(maximum_x, float(np.max(points[0])))
                            minimum_y = min(minimum_y, float(np.min(points[1])))
                            maximum_y = max(maximum_y, float(np.max(points[1])))
                        else:
                            minimum_x = float(np.min(points[0]))
                            maximum_x = float(np.max(points[0]))
                            minimum_y = float(np.min(points[1]))
                            maximum_y = float(np.max(points[1]))
                            has_points = True
                    else:
                        return False

            # Validate and allocate first, then replace every old buffer in one GUI-thread mutation.
            self.clear()
            self._tight_axis_layout = True
            self._series = new_series
            self._has_points = has_points
            self._x_min = minimum_x
            self._x_max = maximum_x
            self._y_min = minimum_y
            self._y_max = maximum_y
            self._x_is_datetime = is_datetime
            self._set_axis_ranges()
            self.update()
            return True
        else:
            return False

    def set_scatter_series(self,
                           x_values: Sequence[float] | np.ndarray,
                           series_names: Sequence[str],
                           series_values: Sequence[Sequence[float] | np.ndarray],
                           colors: Sequence[str | None] | None = None,
                           point_tooltips: Sequence[Sequence[str] | None] | None = None) -> bool:
        """Replace the chart with one or more unconnected XY point series.

        :param x_values: Horizontal numeric coordinates shared by every series.
        :param series_names: Visible legend name for each point series.
        :param series_values: Vertical values paired with each series name.
        :param colors: Optional Qt colour for each series.
        :param point_tooltips: Optional hover text for each series point.
        :return: Whether every input buffer had a compatible finite shape.
        """
        series_count: int = len(series_names)
        x_data: np.ndarray = np.asarray(x_values, dtype=float)
        if not self._can_mutate() or series_count == 0 or len(series_values) != series_count:
            return False
        else:
            pass
        if x_data.ndim != 1 or len(x_data) == 0 or not bool(np.any(np.isfinite(x_data))):
            return False
        else:
            pass
        if colors is None:
            color_values: list[str | None] = [None] * series_count
        elif len(colors) == series_count:
            color_values = list(colors)
        else:
            return False
        if point_tooltips is None:
            tooltip_values: list[Sequence[str] | None] = [None] * series_count
        elif len(point_tooltips) == series_count:
            tooltip_values = list(point_tooltips)
        else:
            return False
        series_index: int
        for series_index in range(series_count):
            y_data: np.ndarray = np.asarray(series_values[series_index], dtype=float)
            if y_data.ndim != 1 or len(y_data) != len(x_data) or not bool(np.any(np.isfinite(y_data))):
                return False
            else:
                pass

        # Validate the complete input before replacing the visible chart.
        self.clear()
        for series_index in range(series_count):
            self.add_scatter_series(
                name=str(series_names[series_index]),
                x_values=x_data,
                y_values=np.asarray(series_values[series_index], dtype=float),
                color=color_values[series_index],
                point_tooltips=tooltip_values[series_index],
            )
        return self.get_series_count() == series_count

    def set_cumulative_area_series(
            self,
            x_values: Sequence[float] | np.ndarray,
            series_names: Sequence[str],
            series_values: Sequence[Sequence[float] | np.ndarray],
            colors: Sequence[str | None] | None = None) -> bool:
        """Replace the chart with stacked cumulative areas sharing one X axis.

        :param x_values: Numeric or NumPy datetime coordinates shared by every area.
        :param series_names: Visible name for each cumulative band.
        :param series_values: One value buffer for each name in display order.
        :param colors: Optional Qt colour for each band.
        :return: Whether every input buffer had a compatible finite shape.
        """
        if self._can_mutate() and len(series_names) == len(series_values) and len(series_names) > 0:
            x_data: np.ndarray
            is_datetime: bool
            x_data, is_datetime = prepare_chart_x_values(x_values=x_values)
            if x_data.ndim != 1:
                return False
            else:
                pass
            valid_mask: np.ndarray = np.isfinite(x_data)
            values_data: list[np.ndarray] = list()
            series_index: int
            for series_index in range(len(series_values)):
                value_data: np.ndarray = np.asarray(series_values[series_index], dtype=float)
                if value_data.ndim == 1 and len(value_data) == len(x_data):
                    values_data.append(value_data)
                    valid_mask &= np.isfinite(value_data)
                else:
                    return False

            if colors is None:
                color_values: list[str | None] = list()
                for series_index in range(len(series_names)):
                    color_values.append(None)
            elif len(colors) == len(series_names):
                color_values = list(colors)
            else:
                return False

            if np.any(valid_mask):
                retained_x_data: np.ndarray = np.ascontiguousarray(x_data[valid_mask], dtype=float)
                new_series: list[ChartSeries] = list()
                cumulative_positive: np.ndarray = np.zeros(len(retained_x_data), dtype=float)
                cumulative_negative: np.ndarray = np.zeros(len(retained_x_data), dtype=float)
                minimum_value: float = 0.0
                maximum_value: float = 0.0
                for series_index in range(len(values_data)):
                    retained_data: np.ndarray = np.ascontiguousarray(
                        values_data[series_index][valid_mask],
                        dtype=float,
                    )
                    positive_values: np.ndarray = np.maximum(retained_data, 0.0)
                    negative_values: np.ndarray = np.minimum(retained_data, 0.0)
                    cumulative_positive += positive_values
                    cumulative_negative += negative_values
                    minimum_value = min(minimum_value, float(np.min(cumulative_negative)))
                    maximum_value = max(maximum_value, float(np.max(cumulative_positive)))
                    new_series.append(
                        ChartSeries(
                            series_type=ChartSeriesType.CUMULATIVE_AREA,
                            name=str(series_names[series_index]),
                            x_data=retained_x_data,
                            y_data=retained_data,
                            color=self._make_cumulative_area_color(
                                color_name=color_values[series_index],
                                series_index=series_index,
                                series_count=len(series_names),
                            ),
                        )
                    )

                # Release the old Python buffers before swapping the chart mode.
                self.clear()
                self._tight_axis_layout = True
                self._content_type = ChartContentType.CUMULATIVE_AREA
                self._stacked_enabled = True
                self._series = new_series
                self._has_points = True
                self._x_min = float(np.min(retained_x_data))
                self._x_max = float(np.max(retained_x_data))
                self._y_min = minimum_value
                self._y_max = maximum_value
                self._x_is_datetime = is_datetime
                self._set_axis_ranges()
                self.update()
                return True
            else:
                return False
        else:
            return False

    def set_polar_series(
            self,
            series_names: Sequence[str],
            angle_values: Sequence[Sequence[float] | np.ndarray],
            radius_values: Sequence[Sequence[float] | np.ndarray],
            colors: Sequence[str | None] | None = None,
            angle_unit: PolarAngleUnit = PolarAngleUnit.RADIANS,
            connect_points: bool = True) -> bool:
        """Replace the chart with line series in polar coordinates.

        :param series_names: Visible name for each polar line.
        :param angle_values: Angle buffer for each series.
        :param radius_values: Non-negative radial buffer for each series.
        :param colors: Optional Qt colour for each polar line.
        :param angle_unit: Unit used by every angle buffer.
        :param connect_points: Whether consecutive samples are joined by line segments.
        :return: Whether every input series had compatible finite coordinates.
        """
        series_count: int = len(series_names)
        if (self._can_mutate() and series_count > 0 and len(angle_values) == series_count
                and len(radius_values) == series_count):
            if colors is None:
                color_values: list[str | None] = list()
                series_index: int
                for series_index in range(series_count):
                    color_values.append(None)
            elif len(colors) == series_count:
                color_values = list(colors)
            else:
                return False

            new_series: list[ChartSeries] = list()
            maximum_radius: float = 0.0
            series_index: int
            for series_index in range(series_count):
                angles: np.ndarray = np.asarray(angle_values[series_index], dtype=float)
                radii: np.ndarray = np.asarray(radius_values[series_index], dtype=float)
                if angles.ndim == 1 and radii.ndim == 1 and len(angles) == len(radii):
                    finite_mask: np.ndarray = np.isfinite(angles) & np.isfinite(radii) & (radii >= 0.0)
                    if np.any(finite_mask):
                        retained_angles: np.ndarray = np.ascontiguousarray(angles[finite_mask], dtype=float)
                        retained_radii: np.ndarray = np.ascontiguousarray(radii[finite_mask], dtype=float)
                        if angle_unit == PolarAngleUnit.DEGREES:
                            retained_angles = np.deg2rad(retained_angles)
                        elif angle_unit == PolarAngleUnit.RADIANS:
                            pass
                        else:
                            return False
                        maximum_radius = max(maximum_radius, float(np.max(retained_radii)))
                        if connect_points:
                            series_type: ChartSeriesType = ChartSeriesType.POLAR
                        else:
                            series_type = ChartSeriesType.POLAR_SCATTER
                        new_series.append(
                            ChartSeries(
                                series_type=series_type,
                                name=str(series_names[series_index]),
                                x_data=retained_angles,
                                y_data=retained_radii,
                                color=self.make_series_color(
                                    color_name=color_values[series_index],
                                    series_index=series_index,
                                ),
                            )
                        )
                    else:
                        return False
                else:
                    return False

            self.clear()
            self._content_type = ChartContentType.POLAR
            self._series = new_series
            self._has_points = True
            self._x_min = 0.0
            self._x_max = 2.0 * np.pi
            self._y_min = 0.0
            self._y_max = max(maximum_radius, 1.0)
            self._x_is_datetime = False
            self.axis_x.set_range(self._x_min, self._x_max)
            self.axis_y.set_range(0.0, self._y_max * 1.05)
            self.axis_x.reset_viewport()
            self.axis_y.reset_viewport()
            self.update()
            return True
        else:
            return False

    def clear(self, force: bool = False) -> None:
        """Release all chart data and restore a neutral numeric viewport.

        :param force: Accepted for compatibility with former chart callers.
        :return: None.
        """
        _ = force
        if self._is_owner_thread():
            if self._transform_source is not None:
                self._transform_source.dispose()
                self._transform_source.deleteLater()
                self._transform_source = None
            else:
                pass
            self._stacked_enabled = False
            self._bar_enabled = False
            self._row_labels.clear()
            self._cdf_enabled = False
            self._abs_enabled = False
            self._transpose_enabled = False
            series: ChartSeries
            for series in self._series:
                series.release_data()
            self._series.clear()
            self._content_type = ChartContentType.XY
            self._bar_labels.clear()
            self._has_points = False
            self._x_min = 0.0
            self._x_max = 1.0
            self._y_min = 0.0
            self._y_max = 1.0
            self._x_is_datetime = False
            self._y_is_datetime = False
            self._legend_visible = True
            self._equal_axis_scale = False
            self._tight_axis_layout = False
            self.axis_x.reset_viewport()
            self.axis_y.reset_viewport()
            self._set_axis_ranges()
            self._rhi_line_cache_key = None
            if self._rhi_line_widget is not None:
                self._rhi_line_widget.clear_data()
                self._rhi_line_widget.hide()
            else:
                pass
            if self._rhi_selection_overlay is not None:
                self._rhi_selection_overlay.set_selection(None, QtCore.QRectF())
            else:
                pass
            if not self._disposed:
                self.update()
            else:
                pass
        else:
            pass

    def copy_plot_to(self, target: GraphsWidget) -> None:
        """Copy retained plot data and display settings without sharing buffers.

        :param target: Empty chart receiving the independent copy.
        :return: None.
        """
        target.clear()
        target._stacked_enabled = self._stacked_enabled
        target._bar_enabled = self._bar_enabled
        target._row_labels = self._row_labels.copy()
        target._catalog_detached = self._catalog_detached
        target._series = deepcopy(self._series)
        target._content_type = self._content_type
        target._bar_labels = self._bar_labels.copy()
        target._title = self._title
        target._x_is_datetime = self._x_is_datetime
        target._y_is_datetime = self._y_is_datetime
        target._legend_visible = self._legend_visible
        target._legend_overlay = self._legend_overlay
        target._equal_axis_scale = self._equal_axis_scale
        target._tight_axis_layout = self._tight_axis_layout
        target.axis_x = deepcopy(self.axis_x)
        target.axis_y = deepcopy(self.axis_y)
        target._reset_data_bounds()
        series: ChartSeries
        for series in target._series:
            if series.get_x_data().size > 0:
                target._include_points(series.get_x_data(), series.get_y_data())
            else:
                pass
        target._cdf_enabled = self._cdf_enabled
        target._abs_enabled = self._abs_enabled
        target._transpose_enabled = self._transpose_enabled
        if self._transform_source is not None:
            target._transform_source = GraphsWidget(parent=target)
            target._transform_source.hide()
            self._transform_source.copy_plot_to(target._transform_source)
        else:
            pass
        target.update()

    def set_value_transforms(self, cdf: bool, absolute: bool, transpose: bool = False,
                             stacked: bool = False, bar: bool = False) -> bool:
        """Redraw XY values from an independent source so switches are reversible.

        :param cdf: Sort values against probability coordinates from zero to one.
        :param absolute: Take absolute values before sorting.
        :param transpose: Swap coordinates and captions after applying value transforms.
        :param stacked: Use the existing cumulative area renderer.
        :param bar: Use grouped vertical bars with source row labels.
        :return: Whether the requested view can represent the stored data.
        """
        if self._content_type in (ChartContentType.XY, ChartContentType.CUMULATIVE_AREA):
            if self._transform_source is None:
                retained_source: GraphsWidget = GraphsWidget(parent=self)
                retained_source.hide()
                self.copy_plot_to(retained_source)
                self._transform_source = retained_source
            else:
                pass
            source: GraphsWidget = self._transform_source
            if ((stacked or bar) and (transpose or len(source._series) == 0)
                    or (stacked and bar) or (bar and cdf)):
                return False
            else:
                pass
            # Stacked bands must share coordinates; reject incompatible data before mutation.
            if stacked:
                reference: np.ndarray = source._series[0].get_x_data()
                if reference.size == 0:
                    return False
                else:
                    pass
                candidate: ChartSeries
                for candidate in source._series:
                    if not np.array_equal(reference, candidate.get_x_data()):
                        return False
                    else:
                        pass
            else:
                pass
            self._content_type = ChartContentType.XY
            self._bar_enabled = bar
            self._bar_labels.clear()
            bar_coordinates: np.ndarray = np.empty(0, dtype=float)
            bar_order: np.ndarray = np.empty(0, dtype=np.int64)
            if bar:
                first_positions: np.ndarray
                bar_coordinates, first_positions = np.unique(
                    np.concatenate([entry.get_x_data() for entry in source._series]), return_index=True)
                # Prefer the table's row order even when individual series have missing samples.
                row_order: dict[float, int] = dict(zip(source._row_labels, range(len(source._row_labels))))
                category_order: np.ndarray = np.array([
                    row_order.get(float(coordinate), len(row_order) + int(position))
                    for coordinate, position in zip(bar_coordinates, first_positions)], dtype=np.int64)
                bar_order = np.argsort(np.argsort(category_order))
                coordinate: float
                for coordinate in bar_coordinates[np.argsort(category_order)]:
                    label: str | None = source._row_labels.get(float(coordinate), None)
                    self._bar_labels.append(label if label is not None else format_chart_value(
                        float(coordinate), source._x_is_datetime))
            else:
                pass
            self._reset_data_bounds()
            series_index: int
            original: ChartSeries
            for series_index, original in enumerate(source._series):
                values: np.ndarray = np.abs(original.get_y_data()) if absolute else original.get_y_data().copy()
                coordinates: np.ndarray = original.get_x_data().copy()
                if cdf:
                    values = np.sort(values)
                    coordinates = np.linspace(0.0, 1.0, values.size)
                else:
                    pass
                # Transpose last so the switches have a consistent, reversible order.
                if transpose:
                    coordinates, values = values, coordinates
                else:
                    pass
                if bar:
                    coordinates = bar_order[np.searchsorted(bar_coordinates, coordinates)].astype(float)
                else:
                    pass
                visible: bool = self._series[series_index].get_visible()
                self._series[series_index] = deepcopy(original)
                if original.get_series_type() == ChartSeriesType.CUMULATIVE_AREA:
                    self._series[series_index] = ChartSeries(
                        ChartSeriesType.LINE, original.get_name(), coordinates, values, original.get_color())
                else:
                    pass
                self._series[series_index].set_visible(visible)
                self._series[series_index].replace_data(coordinates, values, original.get_color())
                if cdf:
                    # Sorted samples no longer correspond to the original point annotations.
                    self._series[series_index].set_point_tooltips(None)
                else:
                    pass
                if coordinates.size > 0:
                    self._include_points(coordinates, values)
                else:
                    pass
            if stacked:
                names: list[str] = [entry.get_name() for entry in self._series]
                buffers: list[np.ndarray] = [entry.get_y_data() for entry in self._series]
                colors: list[str] = [entry.get_color().name() for entry in self._series]
                visibility: list[bool] = [entry.get_visible() for entry in self._series]
                # The setter clears chart buffers; retain the reversible source separately.
                self._transform_source = None
                accepted: bool = self.set_cumulative_area_series(
                    self._series[0].get_x_data(), names, buffers, colors)
                self._transform_source = source
                if not accepted:
                    return False
                else:
                    pass
                self._row_labels = source._row_labels.copy()
                for series_index in range(len(visibility)):
                    self._series[series_index].set_visible(visibility[series_index])
            else:
                pass
            self._stacked_enabled = stacked
            self._bar_enabled = bar
            self._cdf_enabled = cdf
            self._abs_enabled = absolute
            self._transpose_enabled = transpose
            self._x_is_datetime = source._x_is_datetime and not cdf and not transpose and not bar
            self._y_is_datetime = source._x_is_datetime and not cdf and transpose
            x_title: str = self.tr('Probability') if cdf else source.axis_x.get_title()
            y_title: str = source.axis_y.get_title()
            self.axis_x.set_title(y_title if transpose else x_title)
            self.axis_y.set_title(x_title if transpose else y_title)
            self._set_axis_ranges()
            if cdf:
                if transpose:
                    self.axis_y.set_range(0.0, 1.0)
                else:
                    self.axis_x.set_range(0.0, 1.0)
            else:
                pass
            self.reset_viewport()
            return True
        else:
            return False

    def set_row_labels(self, x_values: np.ndarray, labels: Sequence[str]) -> None:
        """Retain source row captions for categorical plot views.

        :param x_values: Coordinates corresponding to the source rows.
        :param labels: Source row labels in coordinate order.
        :return: None.
        """
        coordinates: np.ndarray
        is_datetime: bool
        coordinates, is_datetime = prepare_chart_x_values(x_values)
        if coordinates.ndim == 1 and coordinates.size == len(labels):
            self._row_labels = dict(zip(coordinates, labels))
            if self._transform_source is not None:
                self._transform_source._row_labels = self._row_labels.copy()
            else:
                pass
        else:
            pass

    def replace_xy_series_data(
            self,
            series_data: Sequence[tuple[np.ndarray, np.ndarray, str | None]]) -> bool:
        """Replace stable line or scatter buffers without recreating series objects.

        :param series_data: New X values, Y values, and optional colours in series order.
        :return: Whether every existing XY series was updated.
        """
        if self._can_mutate() and self._content_type == ChartContentType.XY and len(series_data) == len(self._series):
            prepared_data: list[tuple[np.ndarray, np.ndarray, QtGui.QColor]] = list()
            series_index: int
            series_values: tuple[np.ndarray, np.ndarray, str | None]
            for series_index, series_values in enumerate(series_data):
                series: ChartSeries = self._series[series_index]
                points: tuple[np.ndarray, np.ndarray] | None = prepare_chart_points(
                    x_values=series_values[0],
                    y_values=series_values[1],
                )
                if points is not None and series.get_series_type() in (ChartSeriesType.LINE, ChartSeriesType.SCATTER):
                    color: QtGui.QColor = self.make_series_color(
                        color_name=series_values[2],
                        series_index=series_index,
                    )
                    prepared_data.append((points[0], points[1], color))
                else:
                    return False

            # Validate every replacement first, then make the state change as one GUI-thread operation.
            self._reset_data_bounds()
            for series_index, series_entry in enumerate(prepared_data):
                target_series: ChartSeries = self._series[series_index]
                x_data: np.ndarray = series_entry[0]
                y_data: np.ndarray = series_entry[1]
                target_series.replace_data(x_data=x_data, y_data=y_data, color=series_entry[2])
                if len(x_data) > 0:
                    self._include_points(x_data=x_data, y_data=y_data)
                else:
                    pass
            self._set_axis_ranges()
            self.update()
            return True
        else:
            return False

    def add_line_series(self,
                        name: str,
                        x_values: Sequence[float] | np.ndarray,
                        y_values: Sequence[float] | np.ndarray,
                        color: str | None = None,
                        dashed: bool = False) -> None:
        """Add one line series from paired finite numeric values.

        :param name: Series name used by the legend.
        :param x_values: Horizontal data values.
        :param y_values: Vertical data values.
        :param color: Optional line colour in Qt colour syntax.
        :param dashed: Whether the line uses a dashed stroke.
        :return: None.
        """
        x_data: np.ndarray
        is_datetime: bool
        x_data, is_datetime = prepare_chart_x_values(x_values=x_values)
        self._add_xy_series(
            series_type=ChartSeriesType.LINE,
            name=name,
            x_data=x_data,
            y_values=y_values,
            color=color,
            is_datetime=is_datetime,
            point_tooltips=None,
            dashed=dashed,
        )

    def add_scatter_series(self,
                           name: str,
                           x_values: Sequence[float] | np.ndarray,
                           y_values: Sequence[float] | np.ndarray,
                           color: str | None = None,
                           point_tooltips: Sequence[str] | None = None) -> None:
        """Add one circle-scatter series from paired finite numeric values.

        :param name: Series name used by the legend.
        :param x_values: Horizontal data values.
        :param y_values: Vertical data values.
        :param color: Optional circle colour in Qt colour syntax.
        :param point_tooltips: Optional text displayed while hovering each circle.
        :return: None.
        """
        x_data: np.ndarray = np.asarray(x_values, dtype=float)
        self._add_xy_series(
            series_type=ChartSeriesType.SCATTER,
            name=name,
            x_data=x_data,
            y_values=y_values,
            color=color,
            is_datetime=False,
            point_tooltips=point_tooltips,
            dashed=False,
        )

    def set_series_point_tooltips(self, series_index: int, point_tooltips: Sequence[str] | None) -> bool:
        """Set optional tooltip text for an existing scatter series.

        :param series_index: Position of the scatter series in chart display order.
        :param point_tooltips: Text in retained-point order, or ``None`` to clear it.
        :return: Whether the series and text count were valid.
        """
        if self._can_mutate() and 0 <= series_index < len(self._series):
            series: ChartSeries = self._series[series_index]
            if series.get_series_type() == ChartSeriesType.SCATTER:
                updated: bool = series.set_point_tooltips(point_tooltips=point_tooltips)
                self.update()
                return updated
            else:
                return False
        else:
            return False

    def get_point_tooltip_at(self, position: QtCore.QPointF) -> str | None:
        """Calculate line coordinates or return a labelled scatter point's tooltip.

        :param position: Pointer position in this widget's coordinates.
        :return: Tooltip text, or ``None`` when no eligible series is nearby.
        """
        if self._content_type == ChartContentType.XY:
            plot_rect: QtCore.QRectF = self._get_plot_rect()
            if plot_rect.contains(position):
                nearest_tooltip: str | None = None
                hover_distance: float = 5.0
                nearest_distance_squared: float = hover_distance * hover_distance
                series: ChartSeries
                for series in self._series:
                    if (series.get_visible() and series.get_series_type() == ChartSeriesType.SCATTER
                            and series.has_point_tooltips()):
                        x_data: np.ndarray = series.get_x_data()
                        y_data: np.ndarray = series.get_y_data()
                        point_index: int
                        for point_index in range(len(x_data)):
                            mapped_point: QtCore.QPointF = self._map_xy_point(
                                x_value=float(x_data[point_index]),
                                y_value=float(y_data[point_index]),
                                plot_rect=plot_rect,
                            )
                            delta_x: float = mapped_point.x() - position.x()
                            delta_y: float = mapped_point.y() - position.y()
                            distance_squared: float = delta_x * delta_x + delta_y * delta_y
                            if distance_squared <= nearest_distance_squared:
                                nearest_tooltip = series.get_point_tooltip(point_index=point_index)
                                nearest_distance_squared = distance_squared
                            else:
                                pass
                    elif series.get_visible() and series.get_series_type() == ChartSeriesType.LINE:
                        x_data = series.get_x_data()
                        y_data = series.get_y_data()
                        x_min: float
                        x_max: float
                        y_min: float
                        y_max: float
                        x_min, x_max = self.axis_x.get_visual_range()
                        y_min, y_max = self.axis_y.get_visual_range()
                        start: int = 0
                        stop: int = len(x_data)
                        # Clip ordered series to the same pixel tolerance used for hover detection.
                        if series.get_x_is_monotonic():
                            pointer_x: float = x_min + (position.x() - plot_rect.left()) * (x_max - x_min) / plot_rect.width()
                            tolerance: float = hover_distance * (x_max - x_min) / plot_rect.width()
                            start = max(0, int(np.searchsorted(x_data, pointer_x - tolerance)) - 1)
                            stop = min(stop, int(np.searchsorted(x_data, pointer_x + tolerance, side="right")) + 1)
                        else:
                            pass
                        if stop - start >= 2:
                            pixel_x: np.ndarray = plot_rect.left() + (x_data[start:stop] - x_min) * plot_rect.width() / (x_max - x_min)
                            pixel_y: np.ndarray = plot_rect.bottom() - (y_data[start:stop] - y_min) * plot_rect.height() / (y_max - y_min)
                            delta_x_values: np.ndarray = np.diff(pixel_x)
                            delta_y_values: np.ndarray = np.diff(pixel_y)
                            lengths_squared: np.ndarray = delta_x_values ** 2 + delta_y_values ** 2
                            # Project onto each segment, clamping to its endpoints (including duplicate points).
                            fractions: np.ndarray = np.clip(np.divide(
                                (position.x() - pixel_x[:-1]) * delta_x_values +
                                (position.y() - pixel_y[:-1]) * delta_y_values,
                                lengths_squared, out=np.zeros_like(lengths_squared), where=lengths_squared > 0.0,
                            ), 0.0, 1.0)
                            distances: np.ndarray = (
                                (pixel_x[:-1] + fractions * delta_x_values - position.x()) ** 2 +
                                (pixel_y[:-1] + fractions * delta_y_values - position.y()) ** 2
                            )
                            segment_index: int = int(np.argmin(distances))
                            if distances[segment_index] <= nearest_distance_squared:
                                fraction: float = float(fractions[segment_index])
                                data_index: int = start + segment_index
                                x_value: float = float(x_data[data_index] + fraction * (x_data[data_index + 1] - x_data[data_index]))
                                y_value: float = float(y_data[data_index] + fraction * (y_data[data_index + 1] - y_data[data_index]))
                                nearest_tooltip = "{}\nx: {}\ny: {}".format(
                                    series.get_name(), format_chart_value(x_value, self._x_is_datetime),
                                    format_chart_value(y_value, self._y_is_datetime),
                                )
                                nearest_distance_squared = float(distances[segment_index])
                            else:
                                pass
                        else:
                            pass
                    else:
                        pass
                return nearest_tooltip
            else:
                return None
        else:
            return None

    def add_horizontal_bar_series(self,
                                  labels: Sequence[str],
                                  values: Sequence[float] | np.ndarray,
                                  positive_color: str,
                                  negative_color: str) -> None:
        """Add horizontal positive and negative bars for named categories.

        :param labels: Category labels in display order.
        :param values: Values paired with ``labels``.
        :param positive_color: Bar colour for zero and positive values.
        :param negative_color: Bar colour for negative values.
        :return: None.
        """
        value_data: np.ndarray = np.asarray(values, dtype=float)
        if (self._can_mutate() and value_data.ndim == 1
                and len(labels) == len(value_data) and len(value_data) > 0):
            finite_mask: np.ndarray = np.isfinite(value_data)
            valid_values: np.ndarray = np.ascontiguousarray(value_data[finite_mask], dtype=float)
            valid_labels: list[str] = list()
            label_index: int
            for label_index in range(len(labels)):
                if finite_mask[label_index]:
                    valid_labels.append(str(labels[label_index]))
                else:
                    pass
            if len(valid_values) > 0:
                self.clear()
                category_positions: np.ndarray = np.arange(len(valid_values), dtype=float)
                positive_values: np.ndarray = np.maximum(valid_values, 0.0)
                negative_values: np.ndarray = np.minimum(valid_values, 0.0)
                self._content_type = ChartContentType.HORIZONTAL_BAR
                self._bar_labels = valid_labels
                positive_series: ChartSeries = ChartSeries(
                    series_type=ChartSeriesType.HORIZONTAL_BAR,
                    name=self.tr("Positive"),
                    x_data=category_positions,
                    y_data=positive_values,
                    color=self.make_series_color(color_name=positive_color, series_index=0),
                )
                negative_series: ChartSeries = ChartSeries(
                    series_type=ChartSeriesType.HORIZONTAL_BAR,
                    name=self.tr("Negative"),
                    x_data=category_positions,
                    y_data=negative_values,
                    color=self.make_series_color(color_name=negative_color, series_index=1),
                )
                self._series.append(positive_series)
                self._series.append(negative_series)
                self._x_min = min(0.0, float(np.min(valid_values)))
                self._x_max = max(0.0, float(np.max(valid_values)))
                self._y_min = -0.5
                self._y_max = float(len(valid_values)) - 0.5
                self._has_points = True
                self.axis_x.reset_viewport()
                self.axis_y.reset_viewport()
                self._set_axis_ranges()
                self.update()
            else:
                pass
        else:
            pass

    def set_histogram(self,
                      values: Sequence[float] | np.ndarray,
                      bin_count: int,
                      name: str = '',
                      color: str | None = None) -> bool:
        """Replace the chart with a finite numeric histogram.

        :param values: Sample values used to calculate bin frequencies.
        :param bin_count: Positive number of equal-width bins.
        :param name: Optional legend label for the histogram bars.
        :param color: Optional Qt colour for the histogram bars.
        :return: Whether the complete histogram was created.
        """
        value_data: np.ndarray = np.asarray(values, dtype=float)
        if self._can_mutate() and value_data.ndim == 1 and bin_count > 0:
            finite_values: np.ndarray = np.ascontiguousarray(value_data[np.isfinite(value_data)], dtype=float)
            if len(finite_values) > 0:
                counts: np.ndarray
                edges: np.ndarray
                counts, edges = np.histogram(finite_values, bins=bin_count)
                self.clear()
                self._content_type = ChartContentType.HISTOGRAM
                self._series.append(
                    ChartSeries(
                        series_type=ChartSeriesType.HISTOGRAM,
                        name=name,
                        x_data=edges,
                        y_data=counts.astype(float),
                        color=self.make_series_color(color_name=color, series_index=0),
                    )
                )
                self._has_points = True
                self._x_min = float(edges[0])
                self._x_max = float(edges[-1])
                self._y_min = 0.0
                self._y_max = max(float(np.max(counts)), 1.0)
                self._x_is_datetime = False
                self.axis_x.reset_viewport()
                self.axis_y.reset_viewport()
                self._set_axis_ranges()
                self.update()
                return True
            else:
                return False
        else:
            return False

    def redraw(self) -> None:
        """Request a QWidget paint pass when this chart is still active.

        :return: None.
        """
        if self._can_mutate():
            self.update()
        else:
            pass

    def dispose(self) -> None:
        """Drop every Python chart buffer before parent QWidget destruction.

        :return: None.
        """
        if not self._disposed and self._is_owner_thread():
            self._disposed = True
            self._pan_position = None
            self._pan_button = None
            self._zoom_origin = None
            self._zoom_selection = None
            self.unsetCursor()
            QtWidgets.QToolTip.hideText()
            chart_menu: QtWidgets.QMenu
            for chart_menu in self.findChildren(QtWidgets.QMenu):
                chart_menu.close()
            if self._active_save_dialog is not None:
                if shiboken6.isValid(self._active_save_dialog):
                    try:
                        self._active_save_dialog.fileSelected.disconnect(self._save_chart_to_file)
                    except (RuntimeError, TypeError):
                        pass
                    try:
                        self._active_save_dialog.finished.disconnect(self._clear_active_save_dialog)
                    except (RuntimeError, TypeError):
                        pass
                    try:
                        self._active_save_dialog.destroyed.disconnect(self._clear_active_save_dialog)
                    except (RuntimeError, TypeError):
                        pass
                    self._active_save_dialog.close()
                self._active_save_dialog = None
            else:
                pass
            if self._rhi_line_widget is not None:
                self._rhi_line_widget.renderFailed.disconnect(self._on_rhi_render_failed)
                self._rhi_line_widget.dispose()
            else:
                pass
            if self._rhi_selection_overlay is not None:
                self._rhi_selection_overlay.set_selection(None, QtCore.QRectF())
            else:
                pass
            self.clear()
        else:
            pass

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """Zoom value axes by a visible step from the mouse wheel.

        :param event: Mouse wheel event delivered by Qt Widgets.
        :return: None.
        """
        if self._can_mutate():
            delta_y: int = event.angleDelta().y()
            if delta_y > 0:
                multiplier: float = 1.25
                if self._content_type in (ChartContentType.XY, ChartContentType.CUMULATIVE_AREA,
                                          ChartContentType.HISTOGRAM):
                    self.axis_x.set_zoom(self.axis_x.get_zoom() * multiplier)
                    self.axis_y.set_zoom(self.axis_y.get_zoom() * multiplier)
                elif self._content_type == ChartContentType.POLAR:
                    self.axis_y.set_zoom(self.axis_y.get_zoom() * multiplier)
                else:
                    self.axis_x.set_zoom(self.axis_x.get_zoom() * multiplier)
                self.update()
                event.accept()
            elif delta_y < 0:
                multiplier = 0.8
                if self._content_type in (ChartContentType.XY, ChartContentType.CUMULATIVE_AREA,
                                          ChartContentType.HISTOGRAM):
                    self.axis_x.set_zoom(self.axis_x.get_zoom() * multiplier)
                    self.axis_y.set_zoom(self.axis_y.get_zoom() * multiplier)
                elif self._content_type == ChartContentType.POLAR:
                    self.axis_y.set_zoom(self.axis_y.get_zoom() * multiplier)
                else:
                    self.axis_x.set_zoom(self.axis_x.get_zoom() * multiplier)
                self.update()
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Start a selected-rectangle zoom or an explicit pan gesture.

        :param event: Mouse button press delivered by Qt Widgets.
        :return: None.
        """
        pan_requested: bool = (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and bool(event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier)
        )
        plot_rect: QtCore.QRectF = self._get_plot_rect()
        if self._can_mutate() and pan_requested and plot_rect.contains(event.position()):
            QtWidgets.QToolTip.hideText()
            self._pan_position = event.position()
            self._pan_button = event.button()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            event.accept()
        elif (self._can_mutate() and event.button() == QtCore.Qt.MouseButton.LeftButton
              and plot_rect.contains(event.position())):
            QtWidgets.QToolTip.hideText()
            self._zoom_origin = event.position()
            self._zoom_selection = QtCore.QRectF(event.position(), event.position())
            self._update_rhi_selection_overlay(plot_rect=plot_rect)
            self.setCursor(QtCore.Qt.CursorShape.CrossCursor)
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """Update an explicit pan or a left-button zoom selection.

        :param event: Pointer motion delivered by Qt Widgets.
        :return: None.
        """
        if self._can_mutate() and self._pan_position is not None:
            previous_position: QtCore.QPointF = self._pan_position
            current_position: QtCore.QPointF = event.position()
            delta: QtCore.QPointF = current_position - previous_position
            plot_rect: QtCore.QRectF = self._get_plot_rect()
            if plot_rect.width() > 0.0 and self._content_type != ChartContentType.POLAR:
                x_minimum: float
                x_maximum: float
                # Use the visible span so one drag covers the same screen distance at every zoom.
                x_minimum, x_maximum = self.axis_x.get_visual_range()
                self.axis_x.set_pan(
                    self.axis_x.get_pan() - delta.x() * (x_maximum - x_minimum) / plot_rect.width()
                )
            else:
                pass
            if self._content_type in (ChartContentType.XY, ChartContentType.CUMULATIVE_AREA,
                                      ChartContentType.HISTOGRAM) and plot_rect.height() > 0.0:
                y_minimum: float
                y_maximum: float
                # The visible span gives vertical panning the same zoom-consistent behaviour.
                y_minimum, y_maximum = self.axis_y.get_visual_range()
                self.axis_y.set_pan(
                    self.axis_y.get_pan() + delta.y() * (y_maximum - y_minimum) / plot_rect.height()
                )
            else:
                pass
            self._pan_position = current_position
            self.update()
            event.accept()
        elif self._can_mutate() and self._zoom_origin is not None:
            current_position: QtCore.QPointF = event.position()
            plot_rect = self._get_plot_rect()
            self._zoom_selection = QtCore.QRectF(self._zoom_origin, current_position).normalized()
            self._zoom_selection = self._zoom_selection.intersected(plot_rect)
            self._update_rhi_selection_overlay(plot_rect=plot_rect)
            self.update()
            event.accept()
        elif self._can_mutate():
            point_tooltip: str | None = self.get_point_tooltip_at(position=event.position())
            if point_tooltip is not None:
                QtWidgets.QToolTip.showText(event.globalPosition().toPoint(), point_tooltip,
                                           self, QtCore.QRect(), 3000)
            else:
                QtWidgets.QToolTip.hideText()
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """Apply a zoom selection or finish the current pan gesture.

        :param event: Mouse release event delivered by Qt Widgets.
        :return: None.
        """
        pan_released: bool = event.button() == self._pan_button
        if pan_released and self._pan_position is not None and self._pan_button is not None:
            self._pan_position = None
            self._pan_button = None
            self.unsetCursor()
            event.accept()
        elif event.button() == QtCore.Qt.MouseButton.LeftButton and self._zoom_origin is not None:
            selection: QtCore.QRectF | None = self._zoom_selection
            self._zoom_origin = None
            self._zoom_selection = None
            self._update_rhi_selection_overlay(plot_rect=self._get_plot_rect())
            self.unsetCursor()
            if selection is not None:
                self._apply_zoom_selection(selection=selection)
            else:
                pass
            event.accept()
        else:
            event.ignore()

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        """Dismiss hover text when closing the chart or switching plot tabs.

        :param event: Qt hide event delivered by Qt Widgets.
        :return: None.
        """
        QtWidgets.QToolTip.hideText()
        QtWidgets.QWidget.hideEvent(self, event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        """Hide a point tooltip after the pointer leaves this chart widget.

        :param event: Qt leave event delivered by Qt Widgets.
        :return: None.
        """
        _ = event
        QtWidgets.QToolTip.hideText()
        QtWidgets.QWidget.leaveEvent(self, event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        """Restore the full data range from a left-button double-click.

        :param event: Mouse double-click event delivered by Qt Widgets.
        :return: None.
        """
        if self._can_mutate() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._center_from_context_menu()
            event.accept()
        else:
            event.ignore()

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        """Offer image export and centering from the chart context menu.

        :param event: Context menu request delivered by Qt Widgets.
        :return: None.
        """
        if self._can_mutate():
            menu: QtWidgets.QMenu = QtWidgets.QMenu(self)
            menu.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
            save_action: QtGui.QAction = menu.addAction(self.tr("Save image…"))
            center_action: QtGui.QAction = menu.addAction(self.tr("Center data"))
            menu.addSeparator()
            x_minimum_action: QtGui.QAction = menu.addAction(self.tr("Edit X minimum…"))
            x_maximum_action: QtGui.QAction = menu.addAction(self.tr("Edit X maximum…"))
            y_minimum_action: QtGui.QAction = menu.addAction(self.tr("Edit Y minimum…"))
            y_maximum_action: QtGui.QAction = menu.addAction(self.tr("Edit Y maximum…"))
            save_action.triggered.connect(self._save_image_from_context_menu)
            center_action.triggered.connect(self._center_from_context_menu)
            x_minimum_action.triggered.connect(self._edit_x_minimum)
            x_maximum_action.triggered.connect(self._edit_x_maximum)
            y_minimum_action.triggered.connect(self._edit_y_minimum)
            y_maximum_action.triggered.connect(self._edit_y_maximum)
            menu.popup(event.globalPos())
            event.accept()
        else:
            event.ignore()

    def _edit_x_minimum(self, checked: bool = False) -> None:
        """Open the inline editor for the X lower border.

        :param checked: Unused QAction state.
        :return: None.
        """
        _ = checked
        self._begin_axis_limit_edit(axis_index=0, minimum=True)

    def _edit_x_maximum(self, checked: bool = False) -> None:
        """Open the inline editor for the X upper border.

        :param checked: Unused QAction state.
        :return: None.
        """
        _ = checked
        self._begin_axis_limit_edit(axis_index=0, minimum=False)

    def _edit_y_minimum(self, checked: bool = False) -> None:
        """Open the inline editor for the Y lower border.

        :param checked: Unused QAction state.
        :return: None.
        """
        _ = checked
        self._begin_axis_limit_edit(axis_index=1, minimum=True)

    def _edit_y_maximum(self, checked: bool = False) -> None:
        """Open the inline editor for the Y upper border.

        :param checked: Unused QAction state.
        :return: None.
        """
        _ = checked
        self._begin_axis_limit_edit(axis_index=1, minimum=False)

    def _save_image_from_context_menu(self, checked: bool = False) -> None:
        """Choose a PNG or SVG destination and export this chart.

        :param checked: Unused QAction state.
        :return: None.
        """
        _ = checked
        if self._active_save_dialog is None or not shiboken6.isValid(self._active_save_dialog):
            file_dialog: QtWidgets.QFileDialog = QtWidgets.QFileDialog(self, self.tr("Save chart"))
            file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
            file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.AnyFile)
            file_dialog.setOption(QtWidgets.QFileDialog.Option.DontUseNativeDialog, True)
            file_dialog.setNameFilters([self.tr("PNG image (*.png)"), self.tr("SVG image (*.svg)")])
            file_dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
            file_dialog.fileSelected.connect(self._save_chart_to_file)
            file_dialog.finished.connect(self._clear_active_save_dialog)
            file_dialog.destroyed.connect(self._clear_active_save_dialog)
            self._active_save_dialog = file_dialog
            file_dialog.open()
        else:
            self._active_save_dialog.raise_()
            self._active_save_dialog.activateWindow()

    def _save_chart_to_file(self, file_name: str) -> None:
        """Export the chart after the non-modal save dialog returns a path.

        :param file_name: Chosen image destination.
        :return: None.
        """
        if self._can_mutate() and file_name != "":
            output_path: Path = Path(file_name)
            if output_path.suffix == "" and self._active_save_dialog is not None:
                selected_filter: str = self._active_save_dialog.selectedNameFilter().casefold()
                output_path = output_path.with_suffix(".svg" if "svg" in selected_filter else ".png")
            else:
                pass
            from VeraGrid.Gui.PlotDialogue.plot_export import save_chart_image
            save_chart_image(chart=self, file_name=str(output_path))
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

    def _center_from_context_menu(self, checked: bool = False) -> None:
        """Restore auto-ranged data bounds after any manual border edits.

        :param checked: Unused QAction state.
        :return: None.
        """
        _ = checked
        if self._can_mutate():
            if self._content_type == ChartContentType.POLAR:
                self.axis_x.set_range(0.0, 2.0 * np.pi)
                self.axis_y.set_range(0.0, max(self._y_max, 1.0) * 1.05)
            else:
                self._set_axis_ranges()
            self.axis_x.reset_viewport()
            self.axis_y.reset_viewport()
            self.update()
        else:
            pass

    def _update_rhi_selection_overlay(self, plot_rect: QtCore.QRectF) -> None:
        """Keep the selection child above QRhi lines during mouse movement.

        :param plot_rect: Current chart data rectangle used to clip selection.
        :return: None.
        """
        if self._rhi_selection_overlay is not None:
            self._rhi_selection_overlay.setGeometry(self.rect())
            if (self._rhi_line_widget is not None and self._rhi_line_enabled
                    and not self._rhi_line_failed):
                self._rhi_selection_overlay.set_selection(
                    selection=self._zoom_selection,
                    plot_rect=plot_rect,
                )
            else:
                self._rhi_selection_overlay.set_selection(selection=None, plot_rect=plot_rect)
        else:
            pass

    def set_rhi_line_rendering(self, enabled: bool, series_threshold: int = 64) -> None:
        """Enable optional QRhi rendering for dense lines and cumulative areas.

        :param enabled: Whether QRhi may replace QPainter for supported plot types.
        :param series_threshold: Minimum visible XY line count for line replacement.
        :return: None.
        """
        if self._can_mutate():
            self._rhi_line_enabled = enabled
            self._rhi_line_threshold = max(series_threshold, 2)
            self._rhi_line_failed = False
            if enabled and self._rhi_line_widget is None:
                self._create_rhi_line_widget()
            else:
                pass
            self.update()
        else:
            pass

    def _create_rhi_line_widget(self) -> None:
        """Create the optional child renderer only when dense data needs it.

        :return: None.
        """
        rhi_widget: RhiLineChartWidget = RhiLineChartWidget(parent=self)
        rhi_widget.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        rhi_widget.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        rhi_widget.renderFailed.connect(self._on_rhi_render_failed)
        self._rhi_line_widget = rhi_widget
        selection_overlay: ChartSelectionOverlay = ChartSelectionOverlay(parent=self)
        self._rhi_selection_overlay = selection_overlay

    def _on_rhi_render_failed(self) -> None:
        """Fall back to QPainter after the optional QRhi surface fails.

        :return: None.
        """
        self._rhi_line_failed = True
        if self._rhi_line_widget is not None:
            self._rhi_line_widget.hide()
        else:
            pass
        self.update()

    def _prepare_rhi_line_layer(self, plot_rect: QtCore.QRectF) -> bool:
        """Prepare the QRhi overlay for supported dense chart geometry.

        :param plot_rect: Current data viewport used for clip-space transforms.
        :return: Whether QPainter should omit its line paths for this frame.
        """
        if self._content_type == ChartContentType.CUMULATIVE_AREA:
            # QRhi area fills are visually incorrect on the active backend;
            # keep the stacked profile on the verified painter path.
            self._rhi_line_cache_key = None
            if self._rhi_line_widget is not None:
                self._rhi_line_widget.hide()
            else:
                pass
            return False
        else:
            pass
        line_count: int = self._count_visible_lines()
        rhi_selected: bool = (
            self._rhi_line_enabled
            and not self._rhi_line_failed
            and not self._bar_enabled
            and self._content_type == ChartContentType.XY
            and line_count >= self._rhi_line_threshold
        )
        if rhi_selected and self._rhi_line_widget is None:
            self._create_rhi_line_widget()
        else:
            pass
        if rhi_selected and self._rhi_line_widget is not None:
            has_visible_non_line: bool = False
            series: ChartSeries
            for series in self._series:
                if (series.get_visible()
                        and (series.get_series_type() not in (ChartSeriesType.LINE,)
                             or series.get_dashed())):
                    has_visible_non_line = True
                else:
                    pass
            if not has_visible_non_line and plot_rect.width() > 2.0 and plot_rect.height() > 2.0:
                x_minimum: float
                x_maximum: float
                y_minimum: float
                y_maximum: float
                x_minimum, x_maximum = self.axis_x.get_visual_range()
                y_minimum, y_maximum = self.axis_y.get_visual_range()
                x_span: float = x_maximum - x_minimum
                y_span: float = y_maximum - y_minimum
                cache_series: list[tuple[int, int, int, int, int, int]] = list()
                for series in self._series:
                    if series.get_visible() and series.get_series_type() == ChartSeriesType.LINE:
                        x_data: np.ndarray = series.get_x_data()
                        y_data: np.ndarray = series.get_y_data()
                        color: QtGui.QColor = series.get_color()
                        cache_series.append((
                            id(x_data), id(y_data), x_data.size, y_data.size,
                            color.rgba(), int(series.get_x_is_monotonic()),
                        ))
                    else:
                        pass
                cache_key: tuple[object, ...] = (
                    tuple(cache_series), x_minimum, x_maximum, y_minimum, y_maximum,
                    plot_rect.x(), plot_rect.y(), plot_rect.width(), plot_rect.height(),
                    self._plot_color.rgba(), self._grid_color.rgba(),
                )
                self._rhi_line_widget.set_background_color(color=self._plot_color)
                if cache_key == self._rhi_line_cache_key:
                    self._rhi_line_widget.setGeometry(plot_rect.toAlignedRect())
                    self._rhi_line_widget.show()
                    return True
                else:
                    pass
                vertex_chunks: list[np.ndarray] = list()
                series_lengths: list[int] = list()
                series_colors: list[QtGui.QColor] = list()
                # QRhiWidget owns an opaque native surface, so its chart area and
                # grid must be drawn in the same GPU pass as its dense lines.
                tick_index: int = 0
                while tick_index < 6:
                    fraction: float = float(tick_index) / 5.0
                    x_position: float = -1.0 + 2.0 * fraction
                    y_position: float = -1.0 + 2.0 * fraction
                    vertical_grid: np.ndarray = np.asarray(
                        ((x_position, -1.0), (x_position, 1.0)), dtype=np.float32
                    )
                    horizontal_grid: np.ndarray = np.asarray(
                        ((-1.0, y_position), (1.0, y_position)), dtype=np.float32
                    )
                    vertex_chunks.append(vertical_grid)
                    vertex_chunks.append(horizontal_grid)
                    series_lengths.append(2)
                    series_lengths.append(2)
                    series_colors.append(self._grid_color)
                    series_colors.append(self._grid_color)
                    tick_index += 1
                for series in self._series:
                    if series.get_visible() and series.get_series_type() == ChartSeriesType.LINE:
                        x_data: np.ndarray = series.get_x_data()
                        y_data: np.ndarray = series.get_y_data()
                        sample_indices: np.ndarray = self._sample_xy_indices(
                            x_data=x_data,
                            y_data=y_data,
                            x_is_monotonic=series.get_x_is_monotonic(),
                            plot_rect=plot_rect,
                            visible_line_count=line_count,
                        )
                        if sample_indices.size >= 2 and x_span > 0.0 and y_span > 0.0:
                            line_vertices: np.ndarray = np.empty((sample_indices.size, 2), dtype=np.float32)
                            line_vertices[:, 0] = (
                                (x_data[sample_indices] - x_minimum) * (2.0 / x_span) - 1.0
                            ).astype(np.float32)
                            line_vertices[:, 1] = (
                                (y_data[sample_indices] - y_minimum) * (2.0 / y_span) - 1.0
                            ).astype(np.float32)
                            vertex_chunks.append(line_vertices)
                            series_lengths.append(int(sample_indices.size))
                            series_colors.append(series.get_color())
                        else:
                            pass
                    else:
                        pass
                if len(vertex_chunks) > 0:
                    packed_vertices: np.ndarray = np.concatenate(vertex_chunks, axis=0)
                    if self._rhi_line_widget.set_vertices(
                            vertices=packed_vertices,
                            series_lengths=series_lengths,
                            series_colors=series_colors):
                        self._rhi_line_cache_key = cache_key
                        self._rhi_line_widget.setGeometry(plot_rect.toAlignedRect())
                        self._rhi_line_widget.show()
                        return True
                    else:
                        self._rhi_line_cache_key = None
                        self._rhi_line_widget.hide()
                        return False
                else:
                    self._rhi_line_cache_key = None
                    self._rhi_line_widget.hide()
                    return False
            else:
                self._rhi_line_cache_key = None
                self._rhi_line_widget.hide()
                return False
        else:
            self._rhi_line_cache_key = None
            if self._rhi_line_widget is not None:
                self._rhi_line_widget.hide()
            else:
                pass
            return False

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the entire chart synchronously from Python-owned buffers.

        :param event: Paint request delivered only on this QWidget's GUI thread.
        :return: None.
        """
        _ = event
        plot_rect: QtCore.QRectF = self._get_plot_rect()
        use_rhi_lines: bool = self._prepare_rhi_line_layer(plot_rect=plot_rect)
        self._update_rhi_selection_overlay(plot_rect=plot_rect)
        painter: QtGui.QPainter = QtGui.QPainter(self)
        try:
            self.paint_to_painter(painter=painter, paint_lines=not use_rhi_lines)
        finally:
            painter.end()

    def paint_to_painter(self, painter: QtGui.QPainter, paint_lines: bool = True) -> None:
        """Paint the current chart into an already-active Qt paint device.

        :param painter: Active painter targeting this widget's native size.
        :param paint_lines: Whether XY line series use the CPU painter path.
        :return: None.
        """
        painter.save()
        try:
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            painter.fillRect(self.rect(), self._background_color)
            plot_rect: QtCore.QRectF = self._get_plot_rect()
            if plot_rect.width() > 2.0 and plot_rect.height() > 2.0:
                painter.fillRect(plot_rect, self._plot_color)
                if self._content_type == ChartContentType.HORIZONTAL_BAR:
                    self._paint_bar_axes(painter=painter, plot_rect=plot_rect)
                    painter.save()
                    try:
                        painter.setClipRect(plot_rect)
                        self._paint_horizontal_bars(painter=painter, plot_rect=plot_rect)
                    finally:
                        painter.restore()
                elif self._content_type == ChartContentType.CUMULATIVE_AREA:
                    self._paint_xy_axes(painter=painter, plot_rect=plot_rect)
                    painter.save()
                    try:
                        painter.setClipRect(plot_rect)
                        self._paint_cumulative_areas(painter=painter, plot_rect=plot_rect)
                    finally:
                        painter.restore()
                    self._paint_xy_grid(painter=painter, plot_rect=plot_rect)
                elif self._content_type == ChartContentType.POLAR:
                    self._paint_polar_axes(painter=painter, plot_rect=plot_rect)
                    painter.save()
                    try:
                        painter.setClipRect(plot_rect)
                        self._paint_polar_series(painter=painter, plot_rect=plot_rect)
                    finally:
                        painter.restore()
                elif self._content_type == ChartContentType.HISTOGRAM:
                    self._paint_xy_axes(painter=painter, plot_rect=plot_rect)
                    painter.save()
                    try:
                        painter.setClipRect(plot_rect)
                        self._paint_histogram(painter=painter, plot_rect=plot_rect)
                    finally:
                        painter.restore()
                else:
                    self._paint_xy_axes(painter=painter, plot_rect=plot_rect)
                    painter.save()
                    try:
                        painter.setClipRect(plot_rect)
                        if self._bar_enabled:
                            self._paint_vertical_bars(painter, plot_rect)
                        else:
                            self._paint_xy_series(painter=painter, plot_rect=plot_rect, paint_lines=paint_lines)
                    finally:
                        painter.restore()
                painter.setPen(QtGui.QPen(self._label_color, 1.0))
                # Restoring the clipped painter also restores the last series brush.
                painter.setBrush(QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))
                painter.drawRect(plot_rect)
                self._paint_zoom_selection(painter=painter, plot_rect=plot_rect)
            else:
                pass
            self._paint_title_and_legend(painter=painter, plot_rect=plot_rect)
        finally:
            painter.restore()

    def _apply_zoom_selection(self, selection: QtCore.QRectF) -> None:
        """Convert one screen rectangle into the corresponding visible value range.

        :param selection: Selection rectangle clipped to the chart data area.
        :return: None.
        """
        plot_rect: QtCore.QRectF = self._get_plot_rect()
        minimum_selection_size: float = 6.0
        if (self._can_mutate() and plot_rect.width() > 0.0 and plot_rect.height() > 0.0
                and selection.width() >= minimum_selection_size and selection.height() >= minimum_selection_size):
            x_minimum: float
            x_maximum: float
            y_minimum: float
            y_maximum: float
            x_minimum, x_maximum = self.axis_x.get_visual_range()
            y_minimum, y_maximum = self.axis_y.get_visual_range()
            x_span: float = x_maximum - x_minimum
            y_span: float = y_maximum - y_minimum
            selected_x_minimum: float = x_minimum + (selection.left() - plot_rect.left()) * x_span / plot_rect.width()
            selected_x_maximum: float = x_minimum + (selection.right() - plot_rect.left()) * x_span / plot_rect.width()
            selected_y_minimum: float = y_maximum - (selection.bottom() - plot_rect.top()) * y_span / plot_rect.height()
            selected_y_maximum: float = y_maximum - (selection.top() - plot_rect.top()) * y_span / plot_rect.height()
            if self._content_type in (ChartContentType.XY, ChartContentType.CUMULATIVE_AREA,
                                      ChartContentType.HISTOGRAM):
                self.axis_x.set_visual_range(selected_x_minimum, selected_x_maximum)
                self.axis_y.set_visual_range(selected_y_minimum, selected_y_maximum)
            elif self._content_type == ChartContentType.HORIZONTAL_BAR:
                self.axis_x.set_visual_range(selected_x_minimum, selected_x_maximum)
            elif self._content_type == ChartContentType.POLAR:
                selection_fraction: float = max(
                    selection.width() / plot_rect.width(),
                    selection.height() / plot_rect.height(),
                )
                if selection_fraction > 0.0:
                    self.axis_y.set_zoom(self.axis_y.get_zoom() / selection_fraction)
                else:
                    pass
            else:
                pass
            self.update()
        else:
            pass

    def _paint_zoom_selection(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint the current left-drag selection without retaining a Qt graphics item.

        :param painter: Active widget painter.
        :param plot_rect: Current data rectangle used to clip the selection.
        :return: None.
        """
        if self._zoom_selection is not None:
            visible_selection: QtCore.QRectF = self._zoom_selection.intersected(plot_rect)
            if visible_selection.width() > 0.0 and visible_selection.height() > 0.0:
                selection_color: QtGui.QColor = QtGui.QColor("#2563eb")
                fill_color: QtGui.QColor = QtGui.QColor(selection_color)
                fill_color.setAlpha(48)
                painter.save()
                try:
                    painter.setPen(QtGui.QPen(selection_color, 1.0, QtCore.Qt.PenStyle.DashLine))
                    painter.setBrush(QtGui.QBrush(fill_color))
                    painter.drawRect(visible_selection)
                finally:
                    painter.restore()
            else:
                pass
        else:
            pass

    def changeEvent(self, event: QtCore.QEvent) -> None:
        """Refresh chart colors when Qt applies a light or dark application theme.

        :param event: Palette or style change delivered by QWidget.
        :return: None.
        """
        QtWidgets.QWidget.changeEvent(self, event)
        if event.type() in (
                QtCore.QEvent.Type.PaletteChange,
                QtCore.QEvent.Type.ApplicationPaletteChange,
                QtCore.QEvent.Type.StyleChange,
        ):
            window_color: QtGui.QColor = self.palette().color(QtGui.QPalette.ColorRole.Window)
            self.apply_theme(dark=window_color.lightness() < 128)
        else:
            pass

    def event(self, event: QtCore.QEvent) -> bool:
        """Release Python buffers before a deferred QWidget deletion completes.

        :param event: Qt lifecycle event.
        :return: Whether Qt handled the event.
        """
        if event.type() == QtCore.QEvent.Type.DeferredDelete:
            self.dispose()
        else:
            pass
        return QtWidgets.QWidget.event(self, event)

    def _can_mutate(self) -> bool:
        """Return whether GUI-thread code may change chart state safely.

        :return: Whether the chart is active on its Qt owner thread.
        """
        return not self._disposed and self._is_owner_thread()

    def _is_owner_thread(self) -> bool:
        """Return whether the caller is running on this QWidget's Qt thread.

        :return: Whether the caller owns this QWidget's thread affinity.
        """
        return QtCore.QThread.currentThread() == self.thread()

    def _reset_data_bounds(self) -> None:
        """Reset accumulated XY limits before replacing every series buffer.

        :return: None.
        """
        self._has_points = False
        self._x_min = 0.0
        self._x_max = 1.0
        self._y_min = 0.0
        self._y_max = 1.0

    def _add_xy_series(self,
                       series_type: ChartSeriesType,
                       name: str,
                       x_data: np.ndarray,
                       y_values: Sequence[float] | np.ndarray,
                       color: str | None,
                       is_datetime: bool,
                       point_tooltips: Sequence[str] | None,
                       dashed: bool) -> None:
        """Append one validated XY series and expand the shared data range.

        :param series_type: Line or scatter primitive.
        :param name: Legend label.
        :param x_data: Numeric or converted date horizontal values.
        :param y_values: Candidate vertical values.
        :param color: Optional Qt colour name.
        :param is_datetime: Whether horizontal values represent milliseconds.
        :param point_tooltips: Optional text in source-point order.
        :param dashed: Whether a line series uses a dashed stroke.
        :return: None.
        """
        points: tuple[np.ndarray, np.ndarray] | None = prepare_chart_points(x_values=x_data, y_values=y_values)
        if self._can_mutate() and points is not None and self._content_type == ChartContentType.XY:
            series_index: int = len(self._series)
            series_color: QtGui.QColor = self.make_series_color(color_name=color, series_index=series_index)
            retained_tooltips: list[str] | None = prepare_chart_point_tooltips(
                x_values=x_data,
                y_values=y_values,
                point_tooltips=point_tooltips,
            )
            series: ChartSeries = ChartSeries(
                series_type=series_type,
                name=name,
                x_data=points[0],
                y_data=points[1],
                color=series_color,
                point_tooltips=retained_tooltips,
                dashed=dashed,
            )
            self._series.append(series)
            if len(points[0]) > 0:
                self._include_points(x_data=points[0], y_data=points[1])
            else:
                pass
            if is_datetime:
                self._x_is_datetime = True
            else:
                pass
            self._set_axis_ranges()
            self.update()
        else:
            pass

    def _include_points(self, x_data: np.ndarray, y_data: np.ndarray) -> None:
        """Expand shared XY data bounds to include a finite point buffer.

        :param x_data: Finite horizontal values.
        :param y_data: Finite vertical values.
        :return: None.
        """
        if self._has_points:
            self._x_min = min(self._x_min, float(np.min(x_data)))
            self._x_max = max(self._x_max, float(np.max(x_data)))
            self._y_min = min(self._y_min, float(np.min(y_data)))
            self._y_max = max(self._y_max, float(np.max(y_data)))
        else:
            self._x_min = float(np.min(x_data))
            self._x_max = float(np.max(x_data))
            self._y_min = float(np.min(y_data))
            self._y_max = float(np.max(y_data))
            self._has_points = True

    def _set_axis_ranges(self) -> None:
        """Set padded, non-degenerate axis ranges from current chart content.

        :return: None.
        """
        if self._tight_axis_layout:
            x_padding: float = calculate_tight_axis_padding(minimum=self._x_min, maximum=self._x_max)
            y_padding: float = calculate_tight_axis_padding(minimum=self._y_min, maximum=self._y_max)
        else:
            x_padding = max((self._x_max - self._x_min) * 0.05, 0.5)
            y_padding = max((self._y_max - self._y_min) * 0.05, 0.5)
        if self._bar_enabled and len(self._bar_labels) > 0:
            self.axis_x.set_range(-0.5, float(len(self._bar_labels)) - 0.5)
            self.axis_y.set_range(min(self._y_min, 0.0) - y_padding, max(self._y_max, 0.0) + y_padding)
        elif self._content_type == ChartContentType.HORIZONTAL_BAR:
            self.axis_x.set_range(self._x_min - x_padding, self._x_max + x_padding)
            self.axis_y.set_range(self._y_min, self._y_max)
        else:
            self.axis_x.set_range(self._x_min - x_padding, self._x_max + x_padding)
            self.axis_y.set_range(self._y_min - y_padding, self._y_max + y_padding)

    def make_series_color(self, color_name: str | None, series_index: int) -> QtGui.QColor:
        """Return a valid explicit or deterministic fallback series colour.

        :param color_name: Optional caller-provided Qt colour name.
        :param series_index: Position used to select a fallback colour.
        :return: Valid QColor value.
        """
        if color_name is not None:
            requested_color: QtGui.QColor = QtGui.QColor(color_name)
            if requested_color.isValid():
                return requested_color
            else:
                pass
        else:
            pass
        palette_colors: tuple[str, ...] = (
            "#2563eb",
            "#f97316",
            "#0f766e",
            "#dc2626",
            "#7c3aed",
            "#0891b2",
        )
        return QtGui.QColor(palette_colors[series_index % len(palette_colors)])

    def _make_cumulative_area_color(self,
                                    color_name: str | None,
                                    series_index: int,
                                    series_count: int) -> QtGui.QColor:
        """Match the former stacked-result Viridis colors without Matplotlib.

        :param color_name: Optional explicit color supplied by the caller.
        :param series_index: Position in the cumulative stack.
        :param series_count: Number of plotted series used to span the palette.
        :return: Explicit color or an interpolated Viridis color.
        """
        if color_name is not None:
            requested_color: QtGui.QColor = QtGui.QColor(color_name)
            if requested_color.isValid():
                return requested_color
            else:
                pass
        else:
            pass
        viridis_colors: tuple[tuple[int, int, int], ...] = (
            (68, 1, 84), (72, 40, 120), (62, 73, 137), (49, 104, 142),
            (38, 130, 142), (31, 158, 137), (53, 183, 121), (110, 206, 88),
            (181, 222, 43), (253, 231, 37),
        )
        if series_count > 1:
            palette_position: float = (
                float(series_index) * float(len(viridis_colors) - 1) / float(series_count - 1)
            )
        else:
            palette_position = 0.0
        lower_index: int = min(int(palette_position), len(viridis_colors) - 2)
        fraction: float = palette_position - float(lower_index)
        lower_color: tuple[int, int, int] = viridis_colors[lower_index]
        upper_color: tuple[int, int, int] = viridis_colors[lower_index + 1]
        red_value: int = round(float(lower_color[0]) + (float(upper_color[0]) - float(lower_color[0])) * fraction)
        green_value: int = round(float(lower_color[1]) + (float(upper_color[1]) - float(lower_color[1])) * fraction)
        blue_value: int = round(float(lower_color[2]) + (float(upper_color[2]) - float(lower_color[2])) * fraction)
        return QtGui.QColor(red_value, green_value, blue_value)

    def _get_plot_rect(self) -> QtCore.QRectF:
        """Return the data rectangle after title, legend, and axis margins.

        :return: Rectangle available to the data renderer.
        """
        title_space: float = 24.0 if self._title != "" else 4.0
        legend_space: float = (
            20.0 if self._legend_visible and not self._legend_overlay
            and len(self._visible_legend_series()) > 0 else 0.0
        )
        plot_rect: QtCore.QRectF = QtCore.QRectF(self.rect()).adjusted(
            74.0, title_space + legend_space + 4.0, -20.0, -58.0
        )
        if self._equal_axis_scale:
            # Equal numeric axis ranges require a square viewport for one unit
            # to occupy the same number of pixels in both directions. Center
            # that square within the full area left after chart decorations.
            plot_side: float = min(plot_rect.width(), plot_rect.height())
            horizontal_offset: float = (plot_rect.width() - plot_side) * 0.5
            vertical_offset: float = (plot_rect.height() - plot_side) * 0.5
            plot_rect.setRect(
                plot_rect.left() + horizontal_offset,
                plot_rect.top() + vertical_offset,
                plot_side,
                plot_side,
            )
        else:
            pass
        return plot_rect

    def _visible_legend_series(self) -> list[ChartSeries]:
        """Return named series to be painted in the legend.

        :return: Named series in display order.
        """
        visible_series: list[ChartSeries] = list()
        series: ChartSeries
        for series in self._series:
            if self._legend_visible and series.get_visible() and series.get_name() != "":
                visible_series.append(series)
            else:
                pass
        return visible_series

    def _paint_title_and_legend(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint title and legend above the available plot area.

        :param painter: Active painter for this paint event.
        :param plot_rect: Final data drawing rectangle.
        :return: None.
        """
        painter.setPen(QtGui.QPen(self._label_color))
        if self._title != "":
            title_font: QtGui.QFont = QtGui.QFont(painter.font())
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.drawText(QtCore.QRectF(8.0, 2.0, float(self.width() - 16), 22.0),
                             QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter,
                             self._title)
        else:
            pass

        legend_series: list[ChartSeries] = self._visible_legend_series()
        if len(legend_series) > 0:
            legend_y: float = plot_rect.top() - 20.0
            legend_x: float = plot_rect.left()
            normal_font: QtGui.QFont = QtGui.QFont(painter.font())
            normal_font.setBold(False)
            painter.setFont(normal_font)
            if self._legend_overlay:
                legend_width: float = 8.0
                for series in legend_series:
                    legend_width += float(painter.fontMetrics().horizontalAdvance(series.get_name()) + 34)
                legend_width = min(legend_width, max(0.0, plot_rect.width() - 8.0))
                overlay_rect: QtCore.QRectF = QtCore.QRectF(
                    plot_rect.left() + 4.0,
                    plot_rect.top() + 4.0,
                    legend_width,
                    22.0,
                )
                overlay_color: QtGui.QColor = QtGui.QColor(self._background_color)
                overlay_color.setAlpha(220)
                painter.setBrush(QtGui.QBrush(overlay_color))
                painter.setPen(QtGui.QPen(self._grid_color, 0.8))
                painter.drawRoundedRect(overlay_rect, 3.0, 3.0)
                legend_y = overlay_rect.top()
                legend_x = overlay_rect.left()
            else:
                pass
            series: ChartSeries
            for series in legend_series:
                item_width: float = float(painter.fontMetrics().horizontalAdvance(series.get_name()) + 34)
                if self._legend_overlay and legend_x + item_width > plot_rect.right() - 4.0:
                    break
                else:
                    pass
                marker_color: QtGui.QColor = series.get_color()
                painter.setBrush(QtGui.QBrush(marker_color))
                painter.setPen(QtGui.QPen(marker_color))
                painter.drawEllipse(QtCore.QPointF(legend_x + 5.0, legend_y + 9.0), 4.0, 4.0)
                painter.setPen(QtGui.QPen(self._label_color))
                legend_text: str = series.get_name()
                painter.drawText(QtCore.QPointF(legend_x + 13.0, legend_y + 14.0), legend_text)
                text_width: int = painter.fontMetrics().horizontalAdvance(legend_text)
                legend_x += float(text_width + 34)
                if not self._legend_overlay and legend_x > float(self.width() - 120):
                    break
                else:
                    pass
        else:
            pass

    def _paint_xy_axes(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint numeric grids, ticks, and captions for an XY chart.

        :param painter: Active painter for this paint event.
        :param plot_rect: Data drawing rectangle.
        :return: None.
        """
        x_minimum: float
        x_maximum: float
        y_minimum: float
        y_maximum: float
        x_minimum, x_maximum = self.axis_x.get_visual_range()
        y_minimum, y_maximum = self.axis_y.get_visual_range()
        grid_pen: QtGui.QPen = QtGui.QPen(self._grid_color, 1.0)
        painter.setPen(grid_pen)
        tick_index: int
        for tick_index in range(6):
            fraction: float = float(tick_index) / 5.0
            x_position: float = plot_rect.left() + plot_rect.width() * fraction
            y_position: float = plot_rect.bottom() - plot_rect.height() * fraction
            painter.drawLine(QtCore.QPointF(x_position, plot_rect.top()), QtCore.QPointF(x_position, plot_rect.bottom()))
            painter.drawLine(QtCore.QPointF(plot_rect.left(), y_position), QtCore.QPointF(plot_rect.right(), y_position))

            painter.setPen(QtGui.QPen(self._label_color))
            x_value: float = x_minimum + (x_maximum - x_minimum) * fraction
            y_value: float = y_minimum + (y_maximum - y_minimum) * fraction
            if not self._bar_enabled:
                painter.drawText(QtCore.QRectF(x_position - 42.0, plot_rect.bottom() + 2.0, 84.0, 34.0),
                                 QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                                 format_chart_value(value=x_value, is_datetime=self._x_is_datetime))
            else:
                pass
            painter.drawText(QtCore.QRectF(2.0, y_position - 9.0, plot_rect.left() - 9.0, 18.0),
                             QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter,
                             format_chart_value(value=y_value, is_datetime=self._y_is_datetime))
            painter.setPen(grid_pen)

        if self._bar_enabled:
            # Thin crowded category captions while retaining every bar in the data view.
            label_step: int = max(1, int(np.ceil(len(self._bar_labels) * 84.0 / plot_rect.width())))
            label_index: int
            for label_index in range(0, len(self._bar_labels), label_step):
                label_x: float = self._map_x_value(float(label_index), plot_rect)
                if plot_rect.left() <= label_x <= plot_rect.right():
                    painter.drawText(QtCore.QRectF(label_x - 42.0, plot_rect.bottom() + 2.0, 84.0, 34.0),
                                     QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                                     self._bar_labels[label_index])
                else:
                    pass
        else:
            pass
        painter.setPen(QtGui.QPen(self._label_color))
        painter.drawText(QtCore.QRectF(plot_rect.left(), plot_rect.bottom() + 36.0, plot_rect.width(), 20.0),
                         QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                         self.axis_x.get_title())
        # Preserve the standard distance to the Y axis when a square plot is
        # horizontally centered inside a wider chart widget.
        y_title_distance_from_plot: float = 59.0
        y_title_x: float = max(15.0, plot_rect.left() - y_title_distance_from_plot)
        painter.save()
        try:
            painter.translate(y_title_x, plot_rect.center().y())
            painter.rotate(-90.0)
            painter.drawText(QtCore.QRectF(-plot_rect.height() * 0.5, -10.0, plot_rect.height(), 20.0),
                             QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter,
                             self.axis_y.get_title())
        finally:
            painter.restore()

    def _paint_xy_grid(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint grid guides above opaque stacked areas, as Matplotlib did.

        :param painter: Active painter for this paint event.
        :param plot_rect: Data drawing rectangle.
        :return: None.
        """
        painter.save()
        try:
            painter.setClipRect(plot_rect)
            painter.setPen(QtGui.QPen(self._grid_color, 1.0))
            tick_index: int
            for tick_index in range(6):
                fraction: float = float(tick_index) / 5.0
                x_position: float = plot_rect.left() + plot_rect.width() * fraction
                y_position: float = plot_rect.bottom() - plot_rect.height() * fraction
                painter.drawLine(
                    QtCore.QPointF(x_position, plot_rect.top()),
                    QtCore.QPointF(x_position, plot_rect.bottom()),
                )
                painter.drawLine(
                    QtCore.QPointF(plot_rect.left(), y_position),
                    QtCore.QPointF(plot_rect.right(), y_position),
                )
        finally:
            painter.restore()

    def _paint_xy_series(self,
                         painter: QtGui.QPainter,
                         plot_rect: QtCore.QRectF,
                         paint_lines: bool = True) -> None:
        """Paint line paths and circular scatter markers inside the XY axes.

        :param painter: Active painter for this paint event.
        :param plot_rect: Data drawing rectangle.
        :param paint_lines: Whether line strips are delegated to the QRhi child.
        :return: None.
        """
        visible_line_count: int = self._count_visible_lines()
        series: ChartSeries
        for series in self._series:
            if paint_lines and series.get_visible() and series.get_series_type() == ChartSeriesType.LINE:
                self._paint_line_series(
                    painter=painter,
                    plot_rect=plot_rect,
                    series=series,
                    visible_line_count=visible_line_count,
                )
            elif series.get_visible() and series.get_series_type() == ChartSeriesType.SCATTER:
                self._paint_scatter_series(painter=painter, plot_rect=plot_rect, series=series)
            else:
                pass

    def _paint_line_series(self,
                           painter: QtGui.QPainter,
                           plot_rect: QtCore.QRectF,
                           series: ChartSeries,
                           visible_line_count: int) -> None:
        """Paint one sampled line path from an owned NumPy buffer.

        :param painter: Active painter for this paint event.
        :param plot_rect: Data drawing rectangle.
        :param series: Owned line series to draw.
        :param visible_line_count: Number of visible lines in the current plot.
        :return: None.
        """
        x_data: np.ndarray = series.get_x_data()
        y_data: np.ndarray = series.get_y_data()
        if len(x_data) > 0:
            indices: np.ndarray = self._sample_xy_indices(
                x_data=x_data,
                y_data=y_data,
                x_is_monotonic=series.get_x_is_monotonic(),
                plot_rect=plot_rect,
                visible_line_count=visible_line_count,
            )
            path: QtGui.QPainterPath = QtGui.QPainterPath()
            if len(indices) > 0:
                x_minimum: float
                x_maximum: float
                y_minimum: float
                y_maximum: float
                x_minimum, x_maximum = self.axis_x.get_visual_range()
                y_minimum, y_maximum = self.axis_y.get_visual_range()
                x_positions: np.ndarray = plot_rect.left() + (x_data[indices] - x_minimum) * plot_rect.width() / (x_maximum - x_minimum)
                y_positions: np.ndarray = plot_rect.bottom() - (y_data[indices] - y_minimum) * plot_rect.height() / (y_maximum - y_minimum)
                path.moveTo(float(x_positions[0]), float(y_positions[0]))
                point_index: int
                for point_index in range(1, len(indices)):
                    path.lineTo(float(x_positions[point_index]), float(y_positions[point_index]))
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                if series.get_dashed():
                    line_style: QtCore.Qt.PenStyle = QtCore.Qt.PenStyle.DashLine
                else:
                    line_style = QtCore.Qt.PenStyle.SolidLine
                painter.setPen(QtGui.QPen(series.get_color(), 1.8, line_style))
                painter.drawPath(path)
            else:
                pass
        else:
            pass

    def _paint_scatter_series(self,
                              painter: QtGui.QPainter,
                              plot_rect: QtCore.QRectF,
                              series: ChartSeries) -> None:
        """Paint circular markers from an owned NumPy buffer.

        :param painter: Active painter for this paint event.
        :param plot_rect: Data drawing rectangle.
        :param series: Owned scatter series to draw.
        :return: None.
        """
        x_data: np.ndarray = series.get_x_data()
        y_data: np.ndarray = series.get_y_data()
        if len(x_data) > 0:
            indices: np.ndarray = self._sample_indices(point_count=len(x_data), plot_rect=plot_rect)
            color: QtGui.QColor = series.get_color()
            painter.setPen(QtGui.QPen(color.darker(125), 1.0))
            painter.setBrush(QtGui.QBrush(color))
            point_index: int
            for point_index in range(len(indices)):
                data_index: int = int(indices[point_index])
                point: QtCore.QPointF = self._map_xy_point(
                    x_value=float(x_data[data_index]),
                    y_value=float(y_data[data_index]),
                    plot_rect=plot_rect,
                )
                # QRectF selects the bounded ellipse overload across PySide versions.
                marker_rect: QtCore.QRectF = QtCore.QRectF(
                    point.x() - 4.5,
                    point.y() - 4.5,
                    9.0,
                    9.0,
                )
                painter.drawEllipse(marker_rect)
        else:
            pass

    def _paint_histogram(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint the equal-width bin rectangles held by one histogram series.

        :param painter: Active painter clipped to the numeric plot rectangle.
        :param plot_rect: Rectangle used to map bin edges and frequencies.
        :return: None.
        """
        if (len(self._series) == 1 and self._series[0].get_visible()
                and self._series[0].get_series_type() == ChartSeriesType.HISTOGRAM):
            series: ChartSeries = self._series[0]
            edges: np.ndarray = series.get_x_data()
            counts: np.ndarray = series.get_y_data()
            if len(edges) == len(counts) + 1:
                color: QtGui.QColor = series.get_color()
                fill_color: QtGui.QColor = QtGui.QColor(color)
                fill_color.setAlpha(165)
                painter.setPen(QtGui.QPen(color.darker(120), 1.0))
                painter.setBrush(QtGui.QBrush(fill_color))
                baseline: QtCore.QPointF = self._map_xy_point(
                    x_value=float(edges[0]),
                    y_value=0.0,
                    plot_rect=plot_rect,
                )
                bin_index: int
                for bin_index in range(len(counts)):
                    left_point: QtCore.QPointF = self._map_xy_point(
                        x_value=float(edges[bin_index]),
                        y_value=0.0,
                        plot_rect=plot_rect,
                    )
                    right_point: QtCore.QPointF = self._map_xy_point(
                        x_value=float(edges[bin_index + 1]),
                        y_value=float(counts[bin_index]),
                        plot_rect=plot_rect,
                    )
                    # The baseline follows pan and zoom, preserving natural rectangle geometry.
                    rectangle: QtCore.QRectF = QtCore.QRectF(left_point, right_point).normalized()
                    rectangle.setBottom(baseline.y())
                    painter.drawRect(rectangle.normalized())
            else:
                pass
        else:
            pass

    def _paint_cumulative_areas(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint separate positive and negative cumulative area stacks.

        :param painter: Active painter clipped to the numeric plot rectangle.
        :param plot_rect: Rectangle used to map the shared X and Y coordinates.
        :return: None.
        """
        if len(self._series) > 0:
            point_count: int = len(self._series[0].get_x_data())
            indices: np.ndarray = self._sample_indices(point_count=point_count, plot_rect=plot_rect)
            cumulative_positive: np.ndarray = np.zeros(point_count, dtype=float)
            cumulative_negative: np.ndarray = np.zeros(point_count, dtype=float)
            series: ChartSeries
            for series in self._series:
                if series.get_series_type() == ChartSeriesType.CUMULATIVE_AREA:
                    x_data: np.ndarray = series.get_x_data()
                    y_data: np.ndarray = series.get_y_data()
                    positive_values: np.ndarray = np.maximum(y_data, 0.0)
                    negative_values: np.ndarray = np.minimum(y_data, 0.0)
                    upper_positive: np.ndarray = cumulative_positive + positive_values
                    upper_negative: np.ndarray = cumulative_negative + negative_values
                    if series.get_visible() and indices.size >= 2:
                        area_color: QtGui.QColor = series.get_color()
                        if np.any(positive_values != 0.0):
                            self._paint_cumulative_area_band(
                                painter=painter,
                                x_data=x_data,
                                lower_values=cumulative_positive,
                                upper_values=upper_positive,
                                indices=indices,
                                plot_rect=plot_rect,
                                color=area_color,
                                alpha=255,
                            )
                        else:
                            pass
                        if np.any(negative_values != 0.0):
                            self._paint_cumulative_area_band(
                                painter=painter,
                                x_data=x_data,
                                lower_values=cumulative_negative,
                                upper_values=upper_negative,
                                indices=indices,
                                plot_rect=plot_rect,
                                color=area_color,
                                alpha=153,
                            )
                        else:
                            pass
                    else:
                        pass
                    # Each original value contributes only to its matching sign stack.
                    cumulative_positive = upper_positive
                    cumulative_negative = upper_negative
                else:
                    pass
        else:
            pass

    def _paint_cumulative_area_band(self,
                                   painter: QtGui.QPainter,
                                   x_data: np.ndarray,
                                   lower_values: np.ndarray,
                                   upper_values: np.ndarray,
                                   indices: np.ndarray,
                                   plot_rect: QtCore.QRectF,
                                   color: QtGui.QColor,
                                   alpha: int) -> None:
        """Draw one filled strip between two cumulative boundaries.

        :param painter: Active painter clipped to the plot rectangle.
        :param x_data: Shared horizontal coordinates.
        :param lower_values: Lower edge for each original sample.
        :param upper_values: Upper edge for each original sample.
        :param indices: Ordered source samples selected for display.
        :param plot_rect: Numeric plot rectangle used for coordinate mapping.
        :param color: Original series color.
        :param alpha: Fill opacity matching the legacy Matplotlib positive or negative stack.
        :return: None.
        """
        first_index: int = int(indices[0])
        first_point: QtCore.QPointF = self._map_xy_point(
            x_value=float(x_data[first_index]),
            y_value=float(lower_values[first_index]),
            plot_rect=plot_rect,
        )
        path: QtGui.QPainterPath = QtGui.QPainterPath()
        path.moveTo(first_point)
        point_index: int
        for point_index in range(indices.size):
            data_index: int = int(indices[point_index])
            upper_point: QtCore.QPointF = self._map_xy_point(
                x_value=float(x_data[data_index]),
                y_value=float(upper_values[data_index]),
                plot_rect=plot_rect,
            )
            path.lineTo(upper_point)
        reverse_index: int
        for reverse_index in range(indices.size - 1, -1, -1):
            data_index = int(indices[reverse_index])
            lower_point: QtCore.QPointF = self._map_xy_point(
                x_value=float(x_data[data_index]),
                y_value=float(lower_values[data_index]),
                plot_rect=plot_rect,
            )
            path.lineTo(lower_point)
        path.closeSubpath()
        fill_color: QtGui.QColor = QtGui.QColor(color)
        fill_color.setAlpha(alpha)
        painter.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
        painter.setBrush(QtGui.QBrush(fill_color))
        painter.drawPath(path)

    def _get_polar_rect(self, plot_rect: QtCore.QRectF) -> QtCore.QRectF:
        """Return a centred square inside the available plot rectangle.

        :param plot_rect: Rectangle reserved for the plotted content.
        :return: Square used for radial grid geometry.
        """
        diameter: float = min(plot_rect.width(), plot_rect.height()) - 20.0
        if diameter > 2.0:
            return QtCore.QRectF(
                plot_rect.center().x() - diameter * 0.5,
                plot_rect.center().y() - diameter * 0.5,
                diameter,
                diameter,
            )
        else:
            return QtCore.QRectF()

    def _paint_polar_axes(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint the radial grid, angular guides, and radial labels.

        :param painter: Active painter used for the polar grid.
        :param plot_rect: Rectangle available to the polar content.
        :return: None.
        """
        polar_rect: QtCore.QRectF = self._get_polar_rect(plot_rect=plot_rect)
        if polar_rect.width() > 2.0:
            centre: QtCore.QPointF = polar_rect.center()
            outer_radius: float = polar_rect.width() * 0.5
            radial_minimum: float
            radial_maximum: float
            radial_minimum, radial_maximum = self.axis_y.get_visual_range()
            grid_pen: QtGui.QPen = QtGui.QPen(self._grid_color, 1.0)
            painter.setPen(grid_pen)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            circle_index: int
            for circle_index in range(1, 5):
                fraction: float = float(circle_index) / 4.0
                radius: float = outer_radius * fraction
                painter.drawEllipse(QtCore.QRectF(
                    centre.x() - radius,
                    centre.y() - radius,
                    radius * 2.0,
                    radius * 2.0,
                ))
                radial_value: float = radial_minimum + (radial_maximum - radial_minimum) * fraction
                painter.setPen(QtGui.QPen(self._label_color))
                painter.drawText(
                    QtCore.QPointF(centre.x() + 4.0, centre.y() - radius + 13.0),
                    format_chart_value(value=radial_value, is_datetime=False),
                )
                painter.setPen(grid_pen)

            ray_index: int
            for ray_index in range(12):
                angle: float = float(ray_index) * np.pi / 6.0
                end_point: QtCore.QPointF = QtCore.QPointF(
                    centre.x() + outer_radius * np.cos(angle),
                    centre.y() - outer_radius * np.sin(angle),
                )
                painter.drawLine(centre, end_point)
                if ray_index % 3 == 0:
                    painter.setPen(QtGui.QPen(self._label_color))
                    label_point: QtCore.QPointF = QtCore.QPointF(
                        centre.x() + (outer_radius + 14.0) * np.cos(angle),
                        centre.y() - (outer_radius + 14.0) * np.sin(angle),
                    )
                    painter.drawText(
                        QtCore.QRectF(label_point.x() - 18.0, label_point.y() - 9.0, 36.0, 18.0),
                        QtCore.Qt.AlignmentFlag.AlignCenter,
                        f'{ray_index * 30}°',
                    )
                    painter.setPen(grid_pen)

            painter.setPen(QtGui.QPen(self._label_color))
            painter.drawText(
                QtCore.QRectF(plot_rect.left(), plot_rect.bottom() + 28.0, plot_rect.width(), 20.0),
                QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                self.axis_y.get_title(),
            )
        else:
            pass

    def _paint_polar_series(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint every native polar line and its circular sample points.

        :param painter: Active painter clipped to the numeric plot rectangle.
        :param plot_rect: Rectangle used for the radial mapping.
        :return: None.
        """
        polar_rect: QtCore.QRectF = self._get_polar_rect(plot_rect=plot_rect)
        series: ChartSeries
        for series in self._series:
            if (series.get_visible()
                    and series.get_series_type() in (ChartSeriesType.POLAR, ChartSeriesType.POLAR_SCATTER)
                    and polar_rect.width() > 2.0):
                angles: np.ndarray = series.get_x_data()
                radii: np.ndarray = series.get_y_data()
                indices: np.ndarray = self._sample_indices(point_count=len(angles), plot_rect=polar_rect)
                if len(indices) > 0:
                    if series.get_series_type() == ChartSeriesType.POLAR:
                        path: QtGui.QPainterPath = QtGui.QPainterPath()
                        point_index: int
                        for point_index in range(len(indices)):
                            data_index: int = int(indices[point_index])
                            point: QtCore.QPointF = self._map_polar_point(
                                angle=float(angles[data_index]),
                                radius=float(radii[data_index]),
                                polar_rect=polar_rect,
                            )
                            if point_index == 0:
                                path.moveTo(point)
                            else:
                                path.lineTo(point)
                    else:
                        path = QtGui.QPainterPath()
                    color: QtGui.QColor = series.get_color()
                    if series.get_series_type() == ChartSeriesType.POLAR:
                        painter.setPen(QtGui.QPen(color, 1.8))
                        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                        painter.drawPath(path)
                    else:
                        pass
                    painter.setPen(QtGui.QPen(color.darker(125), 1.0))
                    painter.setBrush(QtGui.QBrush(color))
                    for point_index in range(len(indices)):
                        data_index = int(indices[point_index])
                        point = self._map_polar_point(
                            angle=float(angles[data_index]),
                            radius=float(radii[data_index]),
                            polar_rect=polar_rect,
                        )
                        painter.drawEllipse(QtCore.QRectF(point.x() - 3.0, point.y() - 3.0, 6.0, 6.0))
                else:
                    pass
            else:
                pass

    def _paint_bar_axes(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint numeric horizontal ticks and category labels for bar charts.

        :param painter: Active painter for this paint event.
        :param plot_rect: Data drawing rectangle.
        :return: None.
        """
        x_minimum: float
        x_maximum: float
        x_minimum, x_maximum = self.axis_x.get_visual_range()
        grid_pen: QtGui.QPen = QtGui.QPen(self._grid_color, 1.0)
        painter.setPen(grid_pen)
        tick_index: int
        for tick_index in range(6):
            fraction: float = float(tick_index) / 5.0
            x_position: float = plot_rect.left() + plot_rect.width() * fraction
            painter.drawLine(QtCore.QPointF(x_position, plot_rect.top()), QtCore.QPointF(x_position, plot_rect.bottom()))
            painter.setPen(QtGui.QPen(self._label_color))
            x_value: float = x_minimum + (x_maximum - x_minimum) * fraction
            painter.drawText(QtCore.QRectF(x_position - 42.0, plot_rect.bottom() + 5.0, 84.0, 18.0),
                             QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                             format_chart_value(value=x_value, is_datetime=False))
            painter.setPen(grid_pen)

        label_index: int
        for label_index in range(len(self._bar_labels)):
            y_position: float = self._map_bar_category(index=label_index, plot_rect=plot_rect)
            painter.setPen(QtGui.QPen(self._label_color))
            painter.drawText(QtCore.QRectF(2.0, y_position - 9.0, plot_rect.left() - 8.0, 18.0),
                             QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter,
                             self._bar_labels[label_index])
        painter.setPen(QtGui.QPen(self._label_color))
        painter.drawText(QtCore.QRectF(plot_rect.left(), plot_rect.bottom() + 28.0, plot_rect.width(), 20.0),
                         QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                         self.axis_x.get_title())

    def _paint_vertical_bars(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint grouped signed bars for each retained source row.

        :param painter: Active chart painter, clipped to the plot rectangle.
        :param plot_rect: Data drawing rectangle.
        :return: None.
        """
        visible_series: list[ChartSeries] = [entry for entry in self._series if entry.get_visible()]
        width: float = 0.8 / max(len(visible_series), 1)
        series_index: int
        series: ChartSeries
        for series_index, series in enumerate(visible_series):
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QBrush(series.get_color()))
            point_index: int
            for point_index in range(series.get_x_data().size):
                category: float = float(series.get_x_data()[point_index])
                left: float = category - 0.4 + width * series_index
                start: QtCore.QPointF = self._map_xy_point(left, 0.0, plot_rect)
                end: QtCore.QPointF = self._map_xy_point(
                    left + width, float(series.get_y_data()[point_index]), plot_rect)
                painter.drawRect(QtCore.QRectF(start, end).normalized())

    def _paint_horizontal_bars(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        """Paint horizontal bars from the two owned positive and negative buffers.

        :param painter: Active painter for this paint event.
        :param plot_rect: Data drawing rectangle.
        :return: None.
        """
        zero_x: float = self._map_x_value(value=0.0, plot_rect=plot_rect)
        bar_height: float = max(plot_rect.height() / max(len(self._bar_labels), 1) * 0.62, 2.0)
        series: ChartSeries
        for series in self._series:
            if series.get_visible() and series.get_series_type() == ChartSeriesType.HORIZONTAL_BAR:
                x_data: np.ndarray = series.get_x_data()
                y_data: np.ndarray = series.get_y_data()
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(QtGui.QBrush(series.get_color()))
                point_index: int
                for point_index in range(len(x_data)):
                    end_x: float = self._map_x_value(value=float(y_data[point_index]), plot_rect=plot_rect)
                    centre_y: float = self._map_bar_category(index=int(x_data[point_index]), plot_rect=plot_rect)
                    rectangle: QtCore.QRectF = QtCore.QRectF(
                        min(zero_x, end_x),
                        centre_y - bar_height * 0.5,
                        abs(end_x - zero_x),
                        bar_height,
                    )
                    painter.drawRect(rectangle)
            else:
                pass

    def _map_xy_point(self, x_value: float, y_value: float, plot_rect: QtCore.QRectF) -> QtCore.QPointF:
        """Map one XY data point into the current painter rectangle.

        :param x_value: Horizontal data coordinate.
        :param y_value: Vertical data coordinate.
        :param plot_rect: Data drawing rectangle.
        :return: Pixel coordinate for the painter.
        """
        x_position: float = self._map_x_value(value=x_value, plot_rect=plot_rect)
        y_minimum: float
        y_maximum: float
        y_minimum, y_maximum = self.axis_y.get_visual_range()
        y_fraction: float = (y_value - y_minimum) / (y_maximum - y_minimum)
        y_position: float = plot_rect.bottom() - y_fraction * plot_rect.height()
        return QtCore.QPointF(x_position, y_position)

    def _map_polar_point(self, angle: float, radius: float, polar_rect: QtCore.QRectF) -> QtCore.QPointF:
        """Map one polar coordinate into the radial drawing square.

        :param angle: Angle in radians.
        :param radius: Non-negative radial coordinate.
        :param polar_rect: Square used for the polar grid.
        :return: Point in widget coordinates.
        """
        radial_minimum: float
        radial_maximum: float
        radial_minimum, radial_maximum = self.axis_y.get_visual_range()
        radial_fraction: float = (radius - radial_minimum) / (radial_maximum - radial_minimum)
        bounded_fraction: float = min(max(radial_fraction, 0.0), 1.0)
        outer_radius: float = polar_rect.width() * 0.5
        centre: QtCore.QPointF = polar_rect.center()
        return QtCore.QPointF(
            centre.x() + outer_radius * bounded_fraction * np.cos(angle),
            centre.y() - outer_radius * bounded_fraction * np.sin(angle),
        )

    def _map_x_value(self, value: float, plot_rect: QtCore.QRectF) -> float:
        """Map one horizontal data value into the current painter rectangle.

        :param value: Horizontal data coordinate.
        :param plot_rect: Data drawing rectangle.
        :return: Pixel horizontal coordinate.
        """
        x_minimum: float
        x_maximum: float
        x_minimum, x_maximum = self.axis_x.get_visual_range()
        x_fraction: float = (value - x_minimum) / (x_maximum - x_minimum)
        return plot_rect.left() + x_fraction * plot_rect.width()

    def _map_bar_category(self, index: int, plot_rect: QtCore.QRectF) -> float:
        """Map one category index to its vertical bar-chart centre.

        :param index: Category index.
        :param plot_rect: Data drawing rectangle.
        :return: Pixel vertical coordinate.
        """
        y_minimum: float
        y_maximum: float
        y_minimum, y_maximum = self.axis_y.get_visual_range()
        fraction: float = (float(index) - y_minimum) / (y_maximum - y_minimum)
        return plot_rect.bottom() - fraction * plot_rect.height()

    def _sample_xy_indices(self,
                           x_data: np.ndarray,
                           y_data: np.ndarray,
                           x_is_monotonic: bool,
                           plot_rect: QtCore.QRectF,
                           visible_line_count: int = 1) -> np.ndarray:
        """Return line samples that preserve local extrema at screen resolution.

        :param x_data: Owned horizontal data values.
        :param y_data: Owned vertical data values.
        :param x_is_monotonic: Whether search-based viewport clipping is safe.
        :param plot_rect: Data drawing rectangle.
        :param visible_line_count: Visible lines sharing the frame vertex limit.
        :return: Ordered indices containing each pixel bucket's minimum and maximum.
        """
        if x_is_monotonic and len(x_data) > 0:
            x_minimum: float
            x_maximum: float
            x_minimum, x_maximum = self.axis_x.get_visual_range()
            first_index: int = max(int(np.searchsorted(x_data, x_minimum, side='left')) - 1, 0)
            last_index: int = min(int(np.searchsorted(x_data, x_maximum, side='right')) + 1, len(x_data))
            return self._sample_index_range(
                first_index=first_index,
                last_index=last_index,
                y_data=y_data,
                plot_rect=plot_rect,
                visible_line_count=visible_line_count,
            )
        else:
            return self._sample_index_range(
                first_index=0,
                last_index=len(x_data),
                y_data=y_data,
                plot_rect=plot_rect,
                visible_line_count=visible_line_count,
            )

    def _sample_index_range(self,
                            first_index: int,
                            last_index: int,
                            y_data: np.ndarray,
                            plot_rect: QtCore.QRectF,
                            visible_line_count: int) -> np.ndarray:
        """Keep each screen bucket's extrema from an ordered half-open data range.

        :param first_index: First retained data position.
        :param last_index: One past the last retained data position.
        :param y_data: Owned vertical values used to locate local extrema.
        :param plot_rect: Data drawing rectangle.
        :param visible_line_count: Visible lines sharing the frame vertex limit.
        :return: Ordered global positions for each bucket's minimum and maximum.
        """
        point_count: int = last_index - first_index
        # ponytail: cap aggregate path vertices at 500k; use this budget until profiling justifies a more complex renderer.
        maximum_points_per_series: int = max(500000 // max(visible_line_count, 1), 2)
        maximum_buckets: int = max(min(int(plot_rect.width()), maximum_points_per_series // 2), 1)
        if point_count > maximum_buckets:
            # Fixed-size NumPy chunks find extrema without Python work per source point.
            bucket_size: int = (point_count + maximum_buckets - 1) // maximum_buckets
            bucket_count: int = (point_count + bucket_size - 1) // bucket_size
            padded_count: int = bucket_count * bucket_size
            grouped_values: np.ndarray = np.full(padded_count, np.inf, dtype=float)
            visible_values: np.ndarray = y_data[first_index:last_index]
            grouped_values[:point_count] = visible_values
            grouped_values_2d: np.ndarray = grouped_values.reshape(bucket_count, bucket_size)
            bucket_offsets: np.ndarray = np.arange(bucket_count, dtype=int) * bucket_size
            minimum_positions: np.ndarray = bucket_offsets + np.argmin(grouped_values_2d, axis=1)
            grouped_values.fill(-np.inf)
            grouped_values[:point_count] = visible_values
            grouped_values_2d = grouped_values.reshape(bucket_count, bucket_size)
            maximum_positions: np.ndarray = bucket_offsets + np.argmax(grouped_values_2d, axis=1)
            retained_positions: np.ndarray = np.empty(bucket_count * 2, dtype=int)
            retained_positions[0::2] = minimum_positions
            retained_positions[1::2] = maximum_positions
            retained_positions.sort()
            return retained_positions + first_index
        else:
            return np.arange(first_index, last_index, dtype=int)

    def _sample_indices(self,
                        point_count: int,
                        plot_rect: QtCore.QRectF,
                        y_data: np.ndarray | None = None,
                        visible_line_count: int = 1) -> np.ndarray:
        """Bound painter work to useful screen resolution for large buffers.

        :param point_count: Number of available data points.
        :param plot_rect: Data drawing rectangle.
        :param y_data: Optional values for extrema-preserving downsampling.
        :param visible_line_count: Visible lines sharing the frame vertex limit.
        :return: Ordered indices that retain both series endpoints.
        """
        if y_data is not None:
            return self._sample_index_range(
                first_index=0,
                last_index=point_count,
                y_data=y_data,
                plot_rect=plot_rect,
                visible_line_count=visible_line_count,
            )
        else:
            maximum_points: int = max(int(plot_rect.width()) * 2, 2)
            if point_count > maximum_points:
                return np.linspace(0, point_count - 1, maximum_points, dtype=int)
            else:
                return np.arange(point_count, dtype=int)

    def _count_visible_lines(self) -> int:
        """Count visible lines so dense plots share one bounded paint budget.

        :return: Number of visible XY line series, with one as the empty fallback.
        """
        visible_line_count: int = 0
        series: ChartSeries
        for series in self._series:
            if series.get_visible() and series.get_series_type() == ChartSeriesType.LINE:
                visible_line_count += 1
            else:
                pass
        return max(visible_line_count, 1)
