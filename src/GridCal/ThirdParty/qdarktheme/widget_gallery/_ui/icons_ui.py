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
"""The ui to show Qt standard icons."""
from __future__ import annotations

from GridCal.ThirdParty.qdarktheme.qtpy.QtCore import Qt
from GridCal.ThirdParty.qdarktheme.qtpy.QtWidgets import (
    QGridLayout,
    QScrollArea,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class IconsUi:
    """The ui class to show Qt standard icons."""

    def setup_ui(self, win: QWidget) -> None:
        """Set up ui."""
        widget_container = QWidget()
        layout = QGridLayout(widget_container)
        standard_pixmap_names = sorted(
            attr for attr in dir(QStyle.StandardPixmap) if attr.startswith("SP_")
        )
        if len(standard_pixmap_names) == 0:
            standard_pixmap_names = sorted(attr for attr in dir(QStyle) if attr.startswith("SP_"))

        for i, name in enumerate(standard_pixmap_names):
            button = QToolButton()
            button.setText(f":{name}:")
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

            pixmap = getattr(QStyle.StandardPixmap, name)
            icon = win.style().standardIcon(pixmap)
            button.setIcon(icon)
            layout.addWidget(button, int(i / 4), i % 4)

        scroll_area = QScrollArea()
        scroll_area.setWidget(widget_container)

        v_main_layout = QVBoxLayout(win)
        v_main_layout.addWidget(scroll_area)
