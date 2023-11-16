# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from PySide6.QtGui import QPalette, QColor


def css_rgb(color, a=False):
    """Get a CSS `rgb` or `rgba` string from a `QtGui.QColor`."""
    return ("rgba({}, {}, {}, {})" if a else "rgb({}, {}, {})").format(*color.getRgb())


class QDarkPalette(QPalette):
    """Dark palette for a Qt application meant to be used with the Fusion theme."""
    def __init__(self, *__args):
        super().__init__(*__args)

        self.WHITE = QColor(255, 255, 255)
        self.BLACK = QColor(0, 0, 0)
        self.RED = QColor(255, 0, 0)
        self.PRIMARY = QColor(53, 53, 53)
        self.SECONDARY = QColor(35, 35, 35)
        self.TERTIARY = QColor(42, 130, 218)

        # Set all the colors based on the constants in globals
        self.setColor(QPalette.Window,          self.PRIMARY)
        self.setColor(QPalette.WindowText,      self.WHITE)
        self.setColor(QPalette.Base,            self.SECONDARY)
        self.setColor(QPalette.AlternateBase,   self.PRIMARY)
        self.setColor(QPalette.ToolTipBase,     self.WHITE)
        self.setColor(QPalette.ToolTipText,     self.WHITE)
        self.setColor(QPalette.Text,            self.WHITE)
        self.setColor(QPalette.Button,          self.PRIMARY)
        self.setColor(QPalette.ButtonText,      self.WHITE)
        self.setColor(QPalette.BrightText,      self.RED)
        self.setColor(QPalette.Link,            self.TERTIARY)
        self.setColor(QPalette.Highlight,       self.TERTIARY)
        self.setColor(QPalette.HighlightedText, self.BLACK)

    def set_stylesheet(self, app):
        """
        Static method to set the tooltip stylesheet to a `QtWidgets.QApplication`
        """
        app.setStyleSheet("QToolTip {{"
                          "color: {white};"
                          "background-color: {tertiary};"
                          "border: 1px solid {white};"
                          "}}".format(white=css_rgb(self.WHITE), tertiary=css_rgb(self.TERTIARY)))

    def set_app(self, app):
        """
        Set the Fusion theme and this palette to a `QtWidgets.QApplication`.
        """
        app.setStyle("Fusion")
        app.setPalette(self)
        self.set_stylesheet(app)
