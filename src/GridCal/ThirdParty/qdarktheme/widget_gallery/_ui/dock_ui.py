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
"""Module setting up ui of dock window."""
from __future__ import annotations

from GridCal.ThirdParty.qdarktheme.qtpy.QtCore import Qt
from GridCal.ThirdParty.qdarktheme.qtpy.QtWidgets import QDockWidget, QMainWindow, QTextEdit, QVBoxLayout, QWidget


class DockUI:
    """The ui class of dock window."""

    def setup_ui(self, win: QWidget) -> None:
        """Set up ui."""
        # Widgets
        left_dock = QDockWidget("Left dock")
        right_dock = QDockWidget("Right dock")
        top_dock = QDockWidget("Top dock")
        bottom_dock = QDockWidget("Bottom dock")

        # Setup widgets
        left_dock.setWidget(QTextEdit("This is the left widget."))
        right_dock.setWidget(QTextEdit("This is the right widget."))
        top_dock.setWidget(QTextEdit("This is the top widget."))
        bottom_dock.setWidget(QTextEdit("This is the bottom widget."))
        for dock in (left_dock, right_dock, top_dock, bottom_dock):
            dock.setAllowedAreas(
                Qt.DockWidgetArea.LeftDockWidgetArea
                | Qt.DockWidgetArea.RightDockWidgetArea
                | Qt.DockWidgetArea.BottomDockWidgetArea
                | Qt.DockWidgetArea.TopDockWidgetArea
            )

        # Layout
        main_win = QMainWindow()
        main_win.setCentralWidget(QTextEdit("This is the central widget."))
        main_win.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, left_dock)
        main_win.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, right_dock)
        main_win.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, top_dock)
        main_win.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, bottom_dock)

        layout = QVBoxLayout(win)
        layout.addWidget(main_win)
        layout.setContentsMargins(0, 0, 0, 0)
