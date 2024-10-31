# MIT License
#
# Copyright (c) 2021-2022 Yunosuke Ohsugi
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
from GridCal.ThirdParty.qdarktheme._color import Color
from GridCal.ThirdParty.qdarktheme._icon.svg import Svg
from GridCal.ThirdParty.qdarktheme.qtpy.QtCore import QPoint, QRect, QRectF, QSize, Qt
from GridCal.ThirdParty.qdarktheme.qtpy.QtGui import (
    QGuiApplication,
    QIcon,
    QIconEngine,
    QImage,
    QPainter,
    QPalette,
    QPixmap,
)
from GridCal.ThirdParty.qdarktheme.qtpy.QtSvg import QSvgRenderer


class SvgIconEngine(QIconEngine):
    """A custom QIconEngine that can render an SVG buffer."""

    def __init__(self, svg: Svg) -> None:
        """Initialize icon engine."""
        super().__init__()
        self._svg = svg

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state):
        """Paint the icon int ``rect`` using ``painter``."""
        palette = QGuiApplication.palette()

        if mode == QIcon.Mode.Disabled:
            rgba = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text).getRgb()
            color = Color.from_rgba(*rgba)
        else:
            rgba = palette.text().color().getRgb()
            color = Color.from_rgba(*rgba)
        self._svg.colored(color)

        svg_byte = str(self._svg).encode("utf-8")
        renderer = QSvgRenderer(svg_byte)  # type: ignore
        renderer.render(painter, QRectF(rect))

    def clone(self):
        """Required to subclass abstract QIconEngine."""
        return SvgIconEngine(self._svg)

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State):
        """Return the icon as a pixmap with requested size, mode, and state."""
        # Make size to square.
        min_size = min(size.width(), size.height())
        size.setHeight(min_size)
        size.setWidth(min_size)

        img = QImage(size, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        pixmap = QPixmap.fromImage(img, Qt.ImageConversionFlag.NoFormatConversion)
        size.width()
        self.paint(QPainter(pixmap), QRect(QPoint(0, 0), size), mode, state)
        return pixmap
