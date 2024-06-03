"""Generic Sliders with internal python-based models

This module reimplements most of the logic from qslider.cpp in python:
https://code.woboq.org/qt5/qtbase/src/widgets/widgets/qslider.cpp.html

This probably looks like tremendous overkill at first (and it may be!),
since a it's possible to acheive a very reasonable "float slider" by
scaling input float values to some internal integer range for the QSlider,
and converting back to float when getting `value()`.  However, one still
runs into overflow limitations due to the internal integer model.

In order to circumvent them, one needs to reimplement more and more of
the attributes from QSliderPrivate in order to have the slider behave
like a native slider (with all of the proper signals and options).
So that's what `_GenericSlider` is below.

`_GenericRangeSlider` is a variant that expects `value()` and
`sliderPosition()` to be a sequence of scalars rather than a single
scalar (with one handle per item), and it forms the basis of
QRangeSlider.

src: https://github.com/rsgalloway/QRangeSlider
"""

from typing import Generic, TypeVar
from dataclasses import dataclass, replace
import platform
import re
from PySide6 import QtGui, QtWidgets
from PySide6.QtGui import QBrush, QColor, QGradient, QLinearGradient, QPalette, QRadialGradient
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, Qt, Signal, Property
from PySide6.QtWidgets import QApplication, QSlider, QStyle, QStyleOptionSlider, QStylePainter
from typing import Generic, List, Sequence, Tuple, TypeVar, Union
# from ._range_style import RangeSliderStyle, update_styles_from_stylesheet

_T = TypeVar("_T")

SC_NONE = QStyle.SubControl.SC_None
SC_HANDLE = QStyle.SubControl.SC_SliderHandle
SC_GROOVE = QStyle.SubControl.SC_SliderGroove
SC_TICKMARKS = QStyle.SubControl.SC_SliderTickmarks

CC_SLIDER = QStyle.ComplexControl.CC_Slider
QOVERFLOW = 2 ** 31 - 1

SC_BAR = QStyle.SubControl.SC_ScrollBarSubPage


def _event_position(ev: QEvent) -> QPoint:
    # safe for Qt6, Qt5, and hoverEvent
    evp = getattr(ev, "position", getattr(ev, "pos", None))
    pos = evp() if evp else QPoint()
    if isinstance(pos, QPointF):
        pos = pos.toPoint()
    return pos


def _sliderValueFromPosition(minimum: float, maximum: float, position: int, span: int, upsideDown: bool = False) -> float:
    """Converts the given pixel `position` to a value.

    0 maps to the `min` parameter, `span` maps to `max` and other values are
    distributed evenly in-between.

    By default, this function assumes that the maximum value is on the right
    for horizontal items and on the bottom for vertical items. Set the
    `upsideDown` parameter to True to reverse this behavior.
    """

    if span <= 0 or position <= 0:
        return maximum if upsideDown else minimum
    if position >= span:
        return minimum if upsideDown else maximum
    rng = maximum - minimum
    tmp = minimum + position * rng / span
    return maximum - tmp if upsideDown else tmp + minimum



@dataclass
class RangeSliderStyle:
    brush_active: str | None = None
    brush_inactive: str | None = None
    brush_disabled: str | None = None
    pen_active: str | None = None
    pen_inactive: str | None = None
    pen_disabled: str | None = None
    vertical_thickness: float | None = None
    horizontal_thickness: float | None = None
    tick_offset: float | None = None
    tick_bar_alpha: float | None = None
    v_offset: float | None = None
    h_offset: float | None = None
    has_stylesheet: bool = False

    def brush(self, opt: QStyleOptionSlider) -> QBrush:
        cg = opt.palette.currentColorGroup()
        attr = {
            QPalette.Active: "brush_active",  # 0
            QPalette.Disabled: "brush_disabled",  # 1
            QPalette.Inactive: "brush_inactive",  # 2
        }[cg]
        _val = getattr(self, attr)
        if not _val:
            if self.has_stylesheet:
                # if someone set a general style sheet but didn't specify
                # :active, :inactive, etc... then Qt just uses whatever they
                # DID specify
                for i in ("active", "inactive", "disabled"):
                    _val = getattr(self, f"brush_{i}")
                    if _val:
                        break
            else:
                _val = getattr(SYSTEM_STYLE, attr)

        if _val is None:
            return QBrush()

        if isinstance(_val, str):
            val = QColor(_val)
            if not val.isValid():
                val = parse_color(_val, default_attr=attr)
        else:
            val = _val

        if opt.tickPosition != QSlider.NoTicks:
            val.setAlphaF(self.tick_bar_alpha or SYSTEM_STYLE.tick_bar_alpha)

        return QBrush(val)

    def pen(self, opt: QStyleOptionSlider) -> Qt.PenStyle | QColor:
        cg = opt.palette.currentColorGroup()
        attr = {
            QPalette.Active: "pen_active",  # 0
            QPalette.Disabled: "pen_disabled",  # 1
            QPalette.Inactive: "pen_inactive",  # 2
        }[cg]
        val = getattr(self, attr) or getattr(SYSTEM_STYLE, attr)
        if not val:
            return Qt.NoPen
        if isinstance(val, str):
            val = QColor(val)
        if opt.tickPosition != QSlider.NoTicks:
            val.setAlphaF(self.tick_bar_alpha or SYSTEM_STYLE.tick_bar_alpha)

        return val

    def offset(self, opt: QStyleOptionSlider) -> int:
        tp = opt.tickPosition
        off = 0
        if not self.has_stylesheet:
            if opt.orientation == Qt.Horizontal:
                off += self.h_offset or SYSTEM_STYLE.h_offset or 0
            else:
                off += self.v_offset or SYSTEM_STYLE.v_offset or 0
            if tp == QSlider.TicksAbove:
                off += self.tick_offset or SYSTEM_STYLE.tick_offset
            elif tp == QSlider.TicksBelow:
                off -= self.tick_offset or SYSTEM_STYLE.tick_offset
        return off

    def thickness(self, opt: QStyleOptionSlider) -> float:
        if opt.orientation == Qt.Horizontal:
            return self.horizontal_thickness or SYSTEM_STYLE.horizontal_thickness
        else:
            return self.vertical_thickness or SYSTEM_STYLE.vertical_thickness


# ##########  System-specific default styles ############

BASE_STYLE = RangeSliderStyle(
    brush_active="#3B88FD",
    brush_inactive="#8F8F8F",
    brush_disabled="#BBBBBB",
    pen_active=None,
    pen_inactive=None,
    pen_disabled=None,
    vertical_thickness=4,
    horizontal_thickness=4,
    tick_offset=0,
    tick_bar_alpha=0.3,
    v_offset=0,
    h_offset=0,
    has_stylesheet=False,
)

CATALINA_STYLE = replace(
    BASE_STYLE,
    brush_active="#3B88FD",
    brush_inactive="#8F8F8F",
    brush_disabled="#D2D2D2",
    horizontal_thickness=3,
    vertical_thickness=3,
    tick_bar_alpha=0.3,
    tick_offset=4,
)

BIG_SUR_STYLE = replace(
    CATALINA_STYLE,
    brush_active="#0A81FE",
    brush_inactive="#D5D5D5",
    brush_disabled="#E6E6E6",
    tick_offset=0,
    horizontal_thickness=4,
    vertical_thickness=4,
    h_offset=-2,
    tick_bar_alpha=0.2,
)

WINDOWS_STYLE = replace(
    BASE_STYLE,
    brush_active="#550179D7",
    brush_inactive="#330179D7",
    brush_disabled=None,
)

LINUX_STYLE = replace(
    BASE_STYLE,
    brush_active="#44A0D9",
    brush_inactive="#44A0D9",
    brush_disabled="#44A0D9",
    pen_active="#286384",
    pen_inactive="#286384",
    pen_disabled="#286384",
)

SYSTEM = platform.system()
if SYSTEM == "Darwin":
    if int(platform.mac_ver()[0].split(".", maxsplit=1)[0]) >= 11:
        SYSTEM_STYLE = BIG_SUR_STYLE
    else:
        SYSTEM_STYLE = CATALINA_STYLE
elif SYSTEM == "Windows":
    SYSTEM_STYLE = WINDOWS_STYLE
elif SYSTEM == "Linux":
    SYSTEM_STYLE = LINUX_STYLE
else:
    SYSTEM_STYLE = BASE_STYLE


# ################ Stylesheet parsing logic ########################

qlineargrad_pattern = re.compile(
    r"""
    qlineargradient\(
        x1:\s*(?P<x1>\d*\.?\d+),\s*
        y1:\s*(?P<y1>\d*\.?\d+),\s*
        x2:\s*(?P<x2>\d*\.?\d+),\s*
        y2:\s*(?P<y2>\d*\.?\d+),\s*
        stop:0\s*(?P<stop0>\S+),.*
        stop:1\s*(?P<stop1>\S+)
    \)""",
    re.X,
)

qradial_pattern = re.compile(
    r"""
    qradialgradient\(
        cx:\s*(?P<cx>\d*\.?\d+),\s*
        cy:\s*(?P<cy>\d*\.?\d+),\s*
        radius:\s*(?P<radius>\d*\.?\d+),\s*
        fx:\s*(?P<fx>\d*\.?\d+),\s*
        fy:\s*(?P<fy>\d*\.?\d+),\s*
        stop:0\s*(?P<stop0>\S+),.*
        stop:1\s*(?P<stop1>\S+)
    \)""",
    re.X,
)

rgba_pattern = re.compile(
    r"""
    rgba?\(
        (?P<r>\d+),\s*
        (?P<g>\d+),\s*
        (?P<b>\d+),?\s*(?P<a>\d+)?\)
    """,
    re.X,
)


def parse_color(color: str, default_attr) -> QColor | QGradient:
    """
    
    :param color:
    :param default_attr:
    :return:
    """
    qc = QColor(color)
    if qc.isValid():
        return qc

    match = rgba_pattern.search(color)
    if match:
        rgba = [int(x) if x else 255 for x in match.groups()]
        return QColor(*rgba)

    # try linear gradient:
    match = qlineargrad_pattern.search(color)
    if match:
        grad = QLinearGradient(*[float(i) for i in match.groups()[:4]])
        grad.setColorAt(0, QColor(match.groupdict()["stop0"]))
        grad.setColorAt(1, QColor(match.groupdict()["stop1"]))
        return grad

    # try linear gradient:
    match = qradial_pattern.search(color)
    if match:
        grad = QRadialGradient(*[float(i) for i in match.groups()[:5]])
        grad.setColorAt(0, QColor(match.groupdict()["stop0"]))
        grad.setColorAt(1, QColor(match.groupdict()["stop1"]))
        return grad

    # fallback to dark gray
    return QColor(getattr(SYSTEM_STYLE, default_attr))


class _GenericSlider(QSlider, Generic[_T]):
    valueChanged = Signal(float)
    sliderMoved = Signal(float)
    rangeChanged = Signal(float, float)

    MAX_DISPLAY = 5000

    def __init__(self, *args, **kwargs) -> None:

        self._minimum = 0.0
        self._maximum = 99.0
        self._pageStep = 10.0
        self._value: _T = 0.0  # type: ignore
        self._position: _T = 0.0
        self._singleStep = 1.0
        self._offsetAccumulated = 0.0
        self._blocktracking = False
        self._tickInterval = 0.0
        self._pressedControl = SC_NONE
        self._hoverControl = SC_NONE
        self._hoverRect = QRect()
        self._clickOffset = 0.0

        # for keyboard nav
        self._repeatMultiplier = 1  # TODO
        # for wheel nav
        self._offset_accum = 0.0
        # fraction of total range to scroll when holding Ctrl while scrolling
        self._control_fraction = 0.04

        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_Hover)

    # ###############  QtOverrides  #######################

    def value(self) -> _T:  # type: ignore
        return self._value

    def setValue(self, value: _T) -> None:
        value = self._bound(value)
        if self._value == value and self._position == value:
            return
        self._value = value
        if self._position != value:
            self._setPosition(value)
            if self.isSliderDown():
                self.sliderMoved.emit(self.sliderPosition())
        self.sliderChange(self.SliderChange.SliderValueChange)
        self.valueChanged.emit(self.value())

    def sliderPosition(self) -> _T:  # type: ignore
        return self._position

    def setSliderPosition(self, pos: _T) -> None:
        position = self._bound(pos)
        if position == self._position:
            return
        self._setPosition(position)
        self._doSliderMove()

    def singleStep(self) -> float:  # type: ignore
        return self._singleStep

    def setSingleStep(self, step: float) -> None:
        if step != self._singleStep:
            self._setSteps(step, self._pageStep)

    def pageStep(self) -> float:  # type: ignore
        return self._pageStep

    def setPageStep(self, step: float) -> None:
        if step != self._pageStep:
            self._setSteps(self._singleStep, step)

    def minimum(self) -> float:  # type: ignore
        return self._minimum

    def setMinimum(self, min: float) -> None:
        self.setRange(min, max(self._maximum, min))

    def maximum(self) -> float:  # type: ignore
        return self._maximum

    def setMaximum(self, max: float) -> None:
        self.setRange(min(self._minimum, max), max)

    def setRange(self, min: float, max_: float) -> None:
        oldMin, self._minimum = self._minimum, float(min)
        oldMax, self._maximum = self._maximum, float(max(min, max_))

        if oldMin != self._minimum or oldMax != self._maximum:
            # self.sliderChange(self.SliderRangeChange)
            self.rangeChanged.emit(self._minimum, self._maximum)
            self.setValue(self._value)  # re-bound

    def tickInterval(self) -> float:  # type: ignore
        return self._tickInterval

    def setTickInterval(self, ts: float) -> None:
        self._tickInterval = max(0.0, ts)
        self.update()

    def triggerAction(self, action: QSlider.SliderAction) -> None:
        self._blocktracking = True
        # other actions here
        # self.actionTriggered.emit(action)  # FIXME: type not working for all Qt
        self._blocktracking = False
        self.setValue(self._position)

    def initStyleOption(self, option: QStyleOptionSlider) -> None:
        option.initFrom(self)
        option.subControls = SC_NONE
        option.activeSubControls = SC_NONE
        option.orientation = self.orientation()
        option.tickPosition = self.tickPosition()
        option.upsideDown = (
            self.invertedAppearance() != (option.direction == Qt.RightToLeft)
            if self.orientation() == Qt.Horizontal
            else not self.invertedAppearance()
        )
        option.direction = Qt.LeftToRight  # we use the upsideDown option instead
        # option.sliderValue = self._value  # type: ignore
        # option.singleStep = self._singleStep  # type: ignore
        if self.orientation() == Qt.Horizontal:
            option.state |= QStyle.State_Horizontal

        # scale style option to integer space
        option.minimum = 0
        option.maximum = self.MAX_DISPLAY
        option.tickInterval = self._to_qinteger_space(self._tickInterval)
        option.pageStep = self._to_qinteger_space(self._pageStep)
        option.singleStep = self._to_qinteger_space(self._singleStep)
        self._fixStyleOption(option)

    def event(self, ev: QEvent) -> bool:
        if ev.type() == QEvent.WindowActivate:
            self.update()
        elif ev.type() in (QEvent.HoverEnter, QEvent.HoverMove):
            self._updateHoverControl(_event_position(ev))
        elif ev.type() == QEvent.HoverLeave:
            self._hoverControl = SC_NONE
            lastHoverRect, self._hoverRect = self._hoverRect, QRect()
            self.update(lastHoverRect)
        return super().event(ev)

    def mousePressEvent(self, ev: QtGui.QMouseEvent) -> None:
        if self._minimum == self._maximum or ev.buttons() ^ ev.button():
            ev.ignore()
            return

        ev.accept()

        pos = _event_position(ev)

        # If the mouse button used is allowed to set the value
        if ev.button() in (Qt.LeftButton, Qt.MiddleButton):
            self._updatePressedControl(pos)
            if self._pressedControl == SC_HANDLE:
                opt = self._styleOption
                sr = self.style().subControlRect(CC_SLIDER, opt, SC_HANDLE, self)
                offset = sr.center() - sr.topLeft()
                new_pos = self._pixelPosToRangeValue(self._pick(pos - offset))
                self.setSliderPosition(new_pos)
                self.triggerAction(QSlider.SliderMove)
                self.setRepeatAction(QSlider.SliderNoAction)

            self.update()
        # elif: deal with PageSetButtons
        else:
            ev.ignore()

        if self._pressedControl != SC_NONE:
            self.setRepeatAction(QSlider.SliderNoAction)
            self._setClickOffset(pos)
            self.update()
            self.setSliderDown(True)

    def mouseMoveEvent(self, ev: QtGui.QMouseEvent) -> None:
        # TODO: add pixelMetric(QStyle::PM_MaximumDragDistance, &opt, this);
        if self._pressedControl == SC_NONE:
            ev.ignore()
            return
        ev.accept()
        pos = self._pick(_event_position(ev))
        newPosition = self._pixelPosToRangeValue(pos - self._clickOffset)
        self.setSliderPosition(newPosition)

    def mouseReleaseEvent(self, ev: QtGui.QMouseEvent) -> None:
        if self._pressedControl == SC_NONE or ev.buttons():
            ev.ignore()
            return

        ev.accept()
        oldPressed = self._pressedControl
        self._pressedControl = SC_NONE
        self.setRepeatAction(QSlider.SliderNoAction)
        if oldPressed != SC_NONE:
            self.setSliderDown(False)
        self.update()

    def wheelEvent(self, e: QtGui.QWheelEvent) -> None:

        e.ignore()
        vertical = bool(e.angleDelta().y())
        delta = e.angleDelta().y() if vertical else e.angleDelta().x()
        if e.inverted():
            delta *= -1

        orientation = Qt.Vertical if vertical else Qt.Horizontal
        if self._scrollByDelta(orientation, e.modifiers(), delta):
            e.accept()

    def paintEvent(self, ev: QtGui.QPaintEvent) -> None:
        painter = QStylePainter(self)
        opt = self._styleOption

        # draw groove and ticks
        opt.subControls = SC_GROOVE
        if opt.tickPosition != QSlider.NoTicks:
            opt.subControls |= SC_TICKMARKS
        painter.drawComplexControl(CC_SLIDER, opt)

        self._draw_handle(painter, opt)

    # ###############  Implementation Details  #######################

    def _type_cast(self, val):
        return val

    def _setPosition(self, val):
        self._position = val

    def _bound(self, value: _T) -> _T:
        return self._type_cast(max(self._minimum, min(self._maximum, value)))

    def _fixStyleOption(self, option):
        option.sliderPosition = self._to_qinteger_space(self._position - self._minimum)
        option.sliderValue = self._to_qinteger_space(self._value - self._minimum)

    def _to_qinteger_space(self, val, _max=None):
        _max = _max or self.MAX_DISPLAY
        low = (self._maximum - self._minimum) * _max
        if low > 0:
            return int(min(QOVERFLOW, val / low))
        else:
            return 0

    def _pick(self, pt: QPoint) -> int:
        return pt.x() if self.orientation() == Qt.Horizontal else pt.y()

    def _setSteps(self, single: float, page: float):
        self._singleStep = single
        self._pageStep = page
        self.sliderChange(QSlider.SliderStepsChange)

    def _doSliderMove(self):
        if not self.hasTracking():
            self.update()
        if self.isSliderDown():
            self.sliderMoved.emit(self.sliderPosition())
        if self.hasTracking() and not self._blocktracking:
            self.triggerAction(QSlider.SliderMove)

    @property
    def _styleOption(self):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        return opt

    def _updateHoverControl(self, pos: QPoint) -> bool:
        lastHoverRect = self._hoverRect
        lastHoverControl = self._hoverControl
        doesHover = self.testAttribute(Qt.WA_Hover)
        if lastHoverControl != self._newHoverControl(pos) and doesHover:
            self.update(lastHoverRect)
            self.update(self._hoverRect)
            return True
        return not doesHover

    def _newHoverControl(self, pos: QPoint) -> QStyle.SubControl:
        opt = self._styleOption
        opt.subControls = QStyle.SubControl.SC_All

        handleRect = self.style().subControlRect(CC_SLIDER, opt, SC_HANDLE, self)
        grooveRect = self.style().subControlRect(CC_SLIDER, opt, SC_GROOVE, self)
        tickmarksRect = self.style().subControlRect(CC_SLIDER, opt, SC_TICKMARKS, self)

        if handleRect.contains(pos):
            self._hoverRect = handleRect
            self._hoverControl = SC_HANDLE
        elif grooveRect.contains(pos):
            self._hoverRect = grooveRect
            self._hoverControl = SC_GROOVE
        elif tickmarksRect.contains(pos):
            self._hoverRect = tickmarksRect
            self._hoverControl = SC_TICKMARKS
        else:
            self._hoverRect = QRect()
            self._hoverControl = SC_NONE
        return self._hoverControl

    def _setClickOffset(self, pos: QPoint):
        hr = self.style().subControlRect(CC_SLIDER, self._styleOption, SC_HANDLE, self)
        self._clickOffset = self._pick(pos - hr.topLeft())

    def _updatePressedControl(self, pos: QPoint):
        self._pressedControl = SC_HANDLE

    def _draw_handle(self, painter, opt):
        opt.subControls = SC_HANDLE
        if self._pressedControl:
            opt.activeSubControls = self._pressedControl
            opt.state |= QStyle.State_Sunken
        else:
            opt.activeSubControls = self._hoverControl

        painter.drawComplexControl(CC_SLIDER, opt)

    # from QSliderPrivate.pixelPosToRangeValue
    def _pixelPosToRangeValue(self, pos: int) -> float:
        opt = self._styleOption

        gr = self.style().subControlRect(CC_SLIDER, opt, SC_GROOVE, self)
        sr = self.style().subControlRect(CC_SLIDER, opt, SC_HANDLE, self)

        if self.orientation() == Qt.Horizontal:
            sliderLength = sr.width()
            sliderMin = gr.x()
            sliderMax = gr.right() - sliderLength + 1
        else:
            sliderLength = sr.height()
            sliderMin = gr.y()
            sliderMax = gr.bottom() - sliderLength + 1
        return _sliderValueFromPosition(
            self._minimum,
            self._maximum,
            pos - sliderMin,
            sliderMax - sliderMin,
            opt.upsideDown,
        )

    def _scrollByDelta(self, orientation, modifiers, delta: int) -> bool:
        steps_to_scroll = 0.0
        pg_step = self._pageStep

        # in Qt scrolling to the right gives negative values.
        if orientation == Qt.Horizontal:
            delta *= -1
        offset = delta / 120
        if modifiers & Qt.ShiftModifier:
            # Scroll one page regardless of delta:
            steps_to_scroll = max(-pg_step, min(pg_step, offset * pg_step))
            self._offset_accum = 0
        elif modifiers & Qt.ControlModifier:
            _range = self._maximum - self._minimum
            steps_to_scroll = offset * _range * self._control_fraction
            self._offset_accum = 0
        else:
            # Calculate how many lines to scroll. Depending on what delta is (and
            # offset), we might end up with a fraction (e.g. scroll 1.3 lines). We can
            # only scroll whole lines, so we keep the reminder until next event.
            wheel_scroll_lines = QApplication.wheelScrollLines()
            steps_to_scrollF = wheel_scroll_lines * offset * self._effectiveSingleStep()
            # Check if wheel changed direction since last event:
            if self._offset_accum != 0 and (offset / self._offset_accum) < 0:
                self._offset_accum = 0

            self._offset_accum += steps_to_scrollF

            # Don't scroll more than one page in any case:
            steps_to_scroll = max(-pg_step, min(pg_step, self._offset_accum))
            self._offset_accum -= self._offset_accum

            if steps_to_scroll == 0:
                # We moved less than a line, but might still have accumulated partial
                # scroll, unless we already are at one of the ends.
                effective_offset = self._offset_accum
                if self.invertedControls():
                    effective_offset *= -1
                if self._has_scroll_space_left(effective_offset):
                    return True
                self._offset_accum = 0
                return False

        if self.invertedControls():
            steps_to_scroll *= -1

        prevValue = self._value
        self._execute_scroll(steps_to_scroll, modifiers)
        if prevValue == self._value:
            self._offset_accum = 0
            return False
        return True

    def _has_scroll_space_left(self, offset):
        return (offset > 0 and self._value < self._maximum) or (
            offset < 0 and self._value < self._minimum
        )

    def _execute_scroll(self, steps_to_scroll, modifiers):
        self._setPosition(self._bound(self._overflowSafeAdd(steps_to_scroll)))
        self.triggerAction(QSlider.SliderMove)

    def _effectiveSingleStep(self) -> float:
        return self._singleStep * self._repeatMultiplier

    def _overflowSafeAdd(self, add: float) -> float:
        newValue = self._value + add
        if add > 0 and newValue < self._value:
            newValue = self._maximum
        elif add < 0 and newValue > self._value:
            newValue = self._minimum
        return newValue

    # def keyPressEvent(self, ev: QtGui.QKeyEvent) -> None:
    #     return  # TODO


class _GenericRangeSlider(_GenericSlider[Tuple], Generic[_T]):
    """MultiHandle Range Slider widget.

    Same API as QSlider, but `value`, `setValue`, `sliderPosition`, and
    `setSliderPosition` are all sequences of integers.

    The `valueChanged` and `sliderMoved` signals also both emit a tuple of
    integers.
    """

    # Emitted when the slider value has changed, with the new slider values
    valueChanged = Signal(tuple)

    # Emitted when sliderDown is true and the slider moves
    # This usually happens when the user is dragging the slider
    # The value is the positions of *all* handles.
    sliderMoved = Signal(tuple)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # list of values
        self._value: List[_T] = [20, 80]

        # list of current positions of each handle. same length as _value
        # If tracking is enabled (the default) this will be identical to _value
        self._position: List[_T] = [20, 80]

        # which handle is being pressed/hovered
        self._pressedIndex = 0
        self._hoverIndex = 0

        # whether bar length is constant when dragging the bar
        # if False, the bar can shorten when dragged beyond min/max
        self._bar_is_rigid = True
        # whether clicking on the bar moves all handles, or just the nearest handle
        self._bar_moves_all = True
        self._should_draw_bar = True

        # color
        self._style = RangeSliderStyle()
        self.setStyleSheet("")
        update_styles_from_stylesheet(self)

    # ###############  New Public API  #######################

    def barIsRigid(self) -> bool:
        """Whether bar length is constant when dragging the bar.

        If False, the bar can shorten when dragged beyond min/max. Default is True.
        """
        return self._bar_is_rigid

    def setBarIsRigid(self, val: bool = True) -> None:
        """Whether bar length is constant when dragging the bar.

        If False, the bar can shorten when dragged beyond min/max. Default is True.
        """
        self._bar_is_rigid = bool(val)

    def barMovesAllHandles(self) -> bool:
        """Whether clicking on the bar moves all handles (default), or just the nearest."""
        return self._bar_moves_all

    def setBarMovesAllHandles(self, val: bool = True) -> None:
        """Whether clicking on the bar moves all handles (default), or just the nearest."""
        self._bar_moves_all = bool(val)

    def barIsVisible(self) -> bool:
        """Whether to show the bar between the first and last handle."""
        return self._should_draw_bar

    def setBarVisible(self, val: bool = True) -> None:
        """Whether to show the bar between the first and last handle."""
        self._should_draw_bar = bool(val)

    def hideBar(self) -> None:
        self.setBarVisible(False)

    def showBar(self) -> None:
        self.setBarVisible(True)

    # ###############  QtOverrides  #######################

    def value(self) -> Tuple[_T, ...]:
        """Get current value of the widget as a tuple of integers."""
        return tuple(self._value)

    def sliderPosition(self):
        """Get current value of the widget as a tuple of integers.

        If tracking is enabled (the default) this will be identical to value().
        """
        return tuple(float(i) for i in self._position)

    def setSliderPosition(self, pos: Union[float, Sequence[float]], index=None) -> None:
        """Set current position of the handles with a sequence of integers.

        If `pos` is a sequence, it must have the same length as `value()`.
        If it is a scalar, index will be
        """
        if isinstance(pos, (list, tuple)):
            val_len = len(self.value())
            if len(pos) != val_len:
                msg = f"'sliderPosition' must have same length as 'value()' ({val_len})"
                raise ValueError(msg)
            pairs = list(enumerate(pos))
        else:
            pairs = [(self._pressedIndex if index is None else index, pos)]

        for idx, position in pairs:
            self._position[idx] = self._bound(position, idx)

        self._doSliderMove()

    def setStyleSheet(self, styleSheet: str) -> None:
        # sub-page styles render on top of the lower sliders and don't work here.
        override = f"""
            \n{type(self).__name__}::sub-page:horizontal {{background: none}}
            \n{type(self).__name__}::sub-page:vertical {{background: none}}
        """
        return super().setStyleSheet(styleSheet + override)

    def event(self, ev: QEvent) -> bool:
        if ev.type() == QEvent.StyleChange:
            update_styles_from_stylesheet(self)
        return super().event(ev)

    def mouseMoveEvent(self, ev: QtGui.QMouseEvent) -> None:
        if self._pressedControl == SC_BAR:
            ev.accept()
            delta = self._clickOffset - self._pixelPosToRangeValue(self._pick(ev.position()))
            self._offsetAllPositions(-delta, self._sldPosAtPress)
        else:
            super().mouseMoveEvent(ev)

    # ###############  Implementation Details  #######################

    def _setPosition(self, val):
        self._position = list(val)

    def _bound(self, value, index=None):
        if isinstance(value, (list, tuple)):
            return type(value)(self._bound(v) for v in value)
        pos = super()._bound(value)
        if index is not None:
            pos = self._neighbor_bound(pos, index)
        return self._type_cast(pos)

    def _neighbor_bound(self, val, index):
        # make sure we don't go lower than any preceding index:
        min_dist = self.singleStep()
        _lst = self._position
        if index > 0:
            val = max(_lst[index - 1] + min_dist, val)
        # make sure we don't go higher than any following index:
        if index < (len(_lst) - 1):
            val = min(_lst[index + 1] - min_dist, val)
        return val

    def _getBarColor(self):
        return self._style.brush(self._styleOption)

    def _setBarColor(self, color):
        self._style.brush_active = color

    barColor = Property(QtGui.QBrush, _getBarColor, _setBarColor)

    def _offsetAllPositions(self, offset: float, ref=None) -> None:
        if ref is None:
            ref = self._position
        if self._bar_is_rigid:
            # NOTE: This assumes monotonically increasing slider positions
            if offset > 0 and ref[-1] + offset > self.maximum():
                offset = self.maximum() - ref[-1]
            elif ref[0] + offset < self.minimum():
                offset = self.minimum() - ref[0]
        self.setSliderPosition([i + offset for i in ref])

    def _fixStyleOption(self, option):
        pass

    @property
    def _optSliderPositions(self):
        return [self._to_qinteger_space(p - self._minimum) for p in self._position]

    # SubControl Positions

    def _handleRect(self, handle_index: int, opt: QStyleOptionSlider = None) -> QRect:
        """Return the QRect for all handles."""
        opt = opt or self._styleOption
        opt.sliderPosition = self._optSliderPositions[handle_index]
        return self.style().subControlRect(CC_SLIDER, opt, SC_HANDLE, self)

    def _barRect(self, opt: QStyleOptionSlider) -> QRect:
        """Return the QRect for the bar between the outer handles."""
        r_groove = self.style().subControlRect(CC_SLIDER, opt, SC_GROOVE, self)
        r_bar = QRectF(r_groove)
        hdl_low, hdl_high = self._handleRect(0, opt), self._handleRect(-1, opt)

        thickness = self._style.thickness(opt)
        offset = self._style.offset(opt)

        if opt.orientation == Qt.Horizontal:
            r_bar.setTop(r_bar.center().y() - thickness / 2 + offset)
            r_bar.setHeight(thickness)
            r_bar.setLeft(hdl_low.center().x())
            r_bar.setRight(hdl_high.center().x())
        else:
            r_bar.setLeft(r_bar.center().x() - thickness / 2 + offset)
            r_bar.setWidth(thickness)
            r_bar.setBottom(hdl_low.center().y())
            r_bar.setTop(hdl_high.center().y())

        return r_bar

    # Painting

    def _drawBar(self, painter: QStylePainter, opt: QStyleOptionSlider):
        brush = self._style.brush(opt)
        r_bar = self._barRect(opt)
        if isinstance(brush, QtGui.QGradient):
            brush.setStart(r_bar.topLeft())
            brush.setFinalStop(r_bar.bottomRight())
        painter.setPen(self._style.pen(opt))
        painter.setBrush(brush)
        painter.drawRect(r_bar)

    def _draw_handle(self, painter: QStylePainter, opt: QStyleOptionSlider):
        if self._should_draw_bar:
            self._drawBar(painter, opt)

        opt.subControls = SC_HANDLE
        pidx = self._pressedIndex if self._pressedControl == SC_HANDLE else -1
        hidx = self._hoverIndex if self._hoverControl == SC_HANDLE else -1
        for idx, pos in enumerate(self._optSliderPositions):
            opt.sliderPosition = pos
            # make pressed handles appear sunken
            if idx == pidx:
                opt.state |= QStyle.State_Sunken
            else:
                opt.state = opt.state & ~QStyle.State_Sunken
            opt.activeSubControls = SC_HANDLE if idx == hidx else SC_NONE
            painter.drawComplexControl(CC_SLIDER, opt)

    def _updateHoverControl(self, pos):
        old_hover = self._hoverControl, self._hoverIndex
        self._hoverControl, self._hoverIndex = self._getControlAtPos(pos)
        if (self._hoverControl, self._hoverIndex) != old_hover:
            self.update()

    def _updatePressedControl(self, pos):
        opt = self._styleOption
        self._pressedControl, self._pressedIndex = self._getControlAtPos(pos, opt)

    def _setClickOffset(self, pos):
        if self._pressedControl == SC_BAR:
            self._clickOffset = self._pixelPosToRangeValue(self._pick(pos))
            self._sldPosAtPress = tuple(self._position)
        elif self._pressedControl == SC_HANDLE:
            hr = self._handleRect(self._pressedIndex)
            self._clickOffset = self._pick(pos - hr.topLeft())

    # NOTE: this is very much tied to mousepress... not a generic "get control"
    def _getControlAtPos(
        self, pos: QPoint, opt: QStyleOptionSlider = None
    ) -> Tuple[QStyle.SubControl, int]:
        """Update self._pressedControl based on ev.pos()."""
        opt = opt or self._styleOption

        if isinstance(pos, QPointF):
            pos = pos.toPoint()

        for i in range(len(self._position)):
            if self._handleRect(i, opt).contains(pos):
                return (SC_HANDLE, i)

        click_pos = self._pixelPosToRangeValue(self._pick(pos))
        for i, p in enumerate(self._position):
            if p > click_pos:
                if i > 0:
                    # the click was in an internal segment
                    if self._bar_moves_all:
                        return (SC_BAR, i)
                    avg = (self._position[i - 1] + self._position[i]) / 2
                    return (SC_HANDLE, i - 1 if click_pos < avg else i)
                # the click was below the minimum slider
                return (SC_HANDLE, 0)
        # the click was above the maximum slider
        return (SC_HANDLE, len(self._position) - 1)

    def _execute_scroll(self, steps_to_scroll, modifiers):
        if modifiers & Qt.AltModifier:
            self._spreadAllPositions(shrink=steps_to_scroll < 0)
        else:
            self._offsetAllPositions(steps_to_scroll)
        self.triggerAction(QSlider.SliderMove)

    def _has_scroll_space_left(self, offset):
        return (offset > 0 and max(self._value) < self._maximum) or (
            offset < 0 and min(self._value) < self._minimum
        )

    def _spreadAllPositions(self, shrink=False, gain=1.1, ref=None) -> None:
        if ref is None:
            ref = self._position
        # if self._bar_is_rigid:  # TODO

        if shrink:
            gain = 1 / gain
        center = abs(ref[-1] + ref[0]) / 2
        self.setSliderPosition([((i - center) * gain) + center for i in ref])


def update_styles_from_stylesheet(obj: _GenericRangeSlider):
    """

    :param obj:
    :return:
    """
    qss = obj.styleSheet()

    parent = obj.parent()
    while parent is not None:
        qss = parent.styleSheet() + qss
        parent = parent.parent()
    qss = QApplication.instance().styleSheet() + qss
    if not qss:
        return

    # Find bar height/width
    for orient, dim in (("horizontal", "height"), ("vertical", "width")):
        match = re.search(rf"Slider::groove:{orient}\s*{{\s*([^}}]+)}}", qss, re.S)
        if match:
            for line in reversed(match.groups()[0].splitlines()):
                bgrd = re.search(rf"{dim}\s*:\s*(\d+)", line)
                if bgrd:
                    thickness = float(bgrd.groups()[-1])
                    setattr(obj._style, f"{orient}_thickness", thickness)
                    obj._style.has_stylesheet = True


class _IntMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._singleStep = 1

    def _type_cast(self, value) -> int:
        return int(round(value))


class _FloatMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._singleStep = 0.01
        self._pageStep = 0.1

    def _type_cast(self, value) -> float:
        return float(value)


class QDoubleSlider(_FloatMixin, _GenericSlider[float]):
    pass


class QIntSlider(_IntMixin, _GenericSlider[int]):
    # mostly just an example... use QSlider instead.
    valueChanged = Signal(int)


class QRangeSlider(_IntMixin, _GenericRangeSlider):
    pass


class QDoubleRangeSlider(_FloatMixin, QRangeSlider):
    pass


class QRangeSlider3(_IntMixin, _GenericRangeSlider):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._start_val: int = 0
        self._center_value: int = 0
        self._end_val: int = 0
        self.setValue((0, 50, 100))

    def startValue(self):
        return int(self._start_val)

    def endValue(self):
        return int(self._end_val)

    def centerValue(self):
        return int(self._center_value)

    def setValue(self, val: Tuple[int, int, int]):
        """

        :param val:
        """
        if isinstance(val, tuple) or isinstance(val, list):
            self._start_val, self._center_value, self._end_val = val
            super().setValue(val)
        else:
            self.setCenterValue(val=val)

    def setStart(self, val: int):
        """

        :param val:
        """
        self._end_val = val
        super().setValue((self._start_val, self._center_value, self._end_val))

    def setCenterValue(self, val: int):
        """

        :param val:
        """
        self._center_value = val

        if self._center_value > self._end_val:
            self._end_val = self._center_value

        if self._center_value < self._start_val:
            self._start_val = self._center_value

        super().setValue((self._start_val, self._center_value, self._end_val))

    def setEnd(self, val: int):
        """

        :param val:
        """
        self._start_val = val
        super().setValue((self._start_val, self._center_value, self._end_val))

    def setRange(self, min: float, max_: float) -> None:
        oldMin, self._minimum = self._minimum, float(min)
        oldMax, self._maximum = self._maximum, float(max(min, max_))

        if oldMin != self._minimum or oldMax != self._maximum:
            # self.sliderChange(self.SliderRangeChange)
            self.rangeChanged.emit(self._minimum, self._maximum)
            self.setValue((self._minimum, self._minimum, self._maximum))  # re-bound


# ----------------------------------------------------------------------------------------------------------------------




QSS = """
QSlider {
    min-height: 15px;
}

QSlider::groove:horizontal {
    border: 0px;
    background: #37c871;
    height: 20px;
    border-radius: 10px;
}

QSlider::handle {
    background: #cccccc;
    height: 15px;
    width: 15px;
    border-radius: 15px;
}

QSlider::sub-page:horizontal {
    background: #37c871;
    border-top-left-radius: 10px;
    border-bottom-left-radius: 10px;
}

QRangeSlider {
    qproperty-barColor: q#37c871;
}
"""


class DemoRangeSliderWidget(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()

        reg_hslider = QSlider(Qt.Horizontal)
        reg_hslider.setValue(50)
        range_hslider = QRangeSlider(Qt.Horizontal)
        range_hslider.setValue((20, 80))

        multi_range_hslider = QRangeSlider3(Qt.Horizontal)
        # multi_range_hslider.setValue((0, 33, 66))
        # multi_range_hslider.setStart(20)
        # multi_range_hslider.setCenterValue(40)
        # multi_range_hslider.setEnd(60)
        multi_range_hslider.setRange(0, 0)
        # multi_range_hslider.setTickPosition(QSlider.TicksAbove)

        styled_reg_hslider = QSlider(Qt.Horizontal)
        styled_reg_hslider.setValue(50)
        styled_reg_hslider.setStyleSheet(QSS)

        styled_range_hslider = QRangeSlider(Qt.Horizontal)
        styled_range_hslider.setValue((20, 80, 90))
        styled_range_hslider.setStyleSheet(QSS)

        reg_vslider = QtWidgets.QSlider(Qt.Vertical)
        reg_vslider.setValue(50)
        range_vslider = QRangeSlider(Qt.Vertical)
        range_vslider.setValue((22, 77))

        tick_vslider = QtWidgets.QSlider(Qt.Vertical)
        tick_vslider.setValue(55)
        tick_vslider.setTickPosition(QtWidgets.QSlider.TicksRight)

        range_tick_vslider = QRangeSlider(Qt.Vertical)
        range_tick_vslider.setValue((22, 77))
        range_tick_vslider.setTickPosition(QtWidgets.QSlider.TicksLeft)

        szp = QtWidgets.QSizePolicy.Maximum
        left = QtWidgets.QWidget()
        left.setLayout(QtWidgets.QVBoxLayout())
        left.setContentsMargins(2, 2, 2, 2)
        label1 = QtWidgets.QLabel("Regular QSlider Unstyled")
        label2 = QtWidgets.QLabel("QRangeSliders Unstyled")
        label3 = QtWidgets.QLabel("Styled Sliders (using same stylesheet)")
        label1.setSizePolicy(szp, szp)
        label2.setSizePolicy(szp, szp)
        label3.setSizePolicy(szp, szp)
        left.layout().addWidget(label1)
        left.layout().addWidget(reg_hslider)
        left.layout().addWidget(label2)
        left.layout().addWidget(range_hslider)
        left.layout().addWidget(multi_range_hslider)
        left.layout().addWidget(label3)
        left.layout().addWidget(styled_reg_hslider)
        left.layout().addWidget(styled_range_hslider)

        right = QtWidgets.QWidget()
        right.setLayout(QtWidgets.QHBoxLayout())
        right.setContentsMargins(15, 5, 5, 0)
        right.layout().setSpacing(30)
        right.layout().addWidget(reg_vslider)
        right.layout().addWidget(range_vslider)
        right.layout().addWidget(tick_vslider)
        right.layout().addWidget(range_tick_vslider)

        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().addWidget(left)
        self.layout().addWidget(right)
        self.setGeometry(600, 300, 580, 300)
        self.activateWindow()
        self.show()


if __name__ == "__main__":

    import sys
    from pathlib import Path
    import GridCal.ThirdParty.qdarktheme as qdarktheme

    dest = Path("../Main/screenshots")
    dest.mkdir(exist_ok=True)

    qdarktheme.enable_hi_dpi()
    app = QApplication(sys.argv)
    # app.setStyle('Fusion')  # ['Breeze', 'Oxygen', 'QtCurve', 'Windows', 'Fusion']

    # Apply the complete dark theme to your Qt App.
    qdarktheme.setup_theme(
        theme='auto',
        custom_colors={
            "primary": "#00aa88ff",
            "primary>list.selectionBackground": "#00aa88be"
        }
    )
    demo = DemoRangeSliderWidget()

    if "-snap" in sys.argv:
        import platform

        QtWidgets.QApplication.processEvents()
        demo.grab().save(str(dest / f"demo_{platform.system().lower()}.png"))
    else:
        app.exec()
