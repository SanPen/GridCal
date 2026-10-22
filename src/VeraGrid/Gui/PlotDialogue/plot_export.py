# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Native Qt image export for :class:`GraphsWidget`."""

from pathlib import Path

from PySide6 import QtCore, QtGui
from PySide6.QtSvg import QSvgGenerator

from VeraGrid.Gui.PlotDialogue.qt_chart_widget import GraphsWidget


def save_chart_image(chart: GraphsWidget, file_name: str) -> bool:
    """Save a QWidget chart to a PNG raster or SVG vector image.

    :param chart: Live GUI-thread chart that owns the Python data buffers.
    :param file_name: Target path ending in ``.png`` or ``.svg``.
    :return: Whether Qt wrote a non-empty output file.
    """
    output_path: Path = Path(file_name)
    suffix: str = output_path.suffix.lower()
    image_size: QtCore.QSize = chart.size()
    if image_size.width() > 1 and image_size.height() > 1:
        if suffix == '.png':
            image: QtGui.QImage = QtGui.QImage(image_size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(QtCore.Qt.GlobalColor.transparent)
            painter: QtGui.QPainter = QtGui.QPainter(image)
            try:
                chart.paint_to_painter(painter=painter)
            finally:
                painter.end()
            saved: bool = image.save(str(output_path), 'PNG')
        elif suffix == '.svg':
            generator: QSvgGenerator = QSvgGenerator()
            generator.setFileName(str(output_path))
            generator.setSize(image_size)
            generator.setViewBox(QtCore.QRect(0, 0, image_size.width(), image_size.height()))
            generator.setTitle(chart.windowTitle())
            generator.setDescription('A chart exported by VeraGrid')
            painter = QtGui.QPainter(generator)
            try:
                chart.paint_to_painter(painter=painter)
            finally:
                painter.end()
            saved = output_path.is_file() and output_path.stat().st_size > 0
        else:
            saved = False
    else:
        saved = False
    return saved
