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
"""Module for QtGui."""
from GridCal.ThirdParty.qdarktheme.qtpy.qt_compat import QT_API, qt_import_error

if QT_API is None:
    raise qt_import_error
if QT_API == "PySide6":
    from PySide6.QtGui import *  # type: ignore  # noqa: F403
elif QT_API == "PyQt6":
    from PyQt6.QtGui import *  # type: ignore  # noqa: F403
elif QT_API == "PyQt5":
    from PyQt5.QtGui import *  # type: ignore  # noqa: F403
    from PyQt5.QtWidgets import QAction, QActionGroup, QShortcut  # type: ignore
elif QT_API == "PySide2":
    from PySide2.QtGui import *  # type: ignore  # noqa: F403
    from PySide2.QtWidgets import QAction, QActionGroup, QShortcut  # type: ignore

if QT_API in ["PyQt5", "PySide2"]:
    QAction = QAction  # type: ignore  # noqa: SIM909
    QActionGroup = QActionGroup  # type: ignore  # noqa: SIM909
    QShortcut = QShortcut  # type: ignore  # noqa: SIM909
