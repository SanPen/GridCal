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
"""Module for QtWidgets."""
from __future__ import annotations

from collections.abc import Sequence

from GridCal.ThirdParty.qdarktheme.qtpy.qt_compat import QT_API

if QT_API == "PySide6":
    from PySide6.QtWidgets import *  # type: ignore  # noqa: F403
elif QT_API == "PyQt6":
    from PyQt6.QtWidgets import *  # type: ignore  # noqa: F403
elif QT_API == "PyQt5":
    from PyQt5.QtWidgets import *  # type: ignore # noqa: F403
elif QT_API == "PySide2":
    from PySide2.QtWidgets import *  # type: ignore  # noqa: F403


class Application(QApplication):  # type: ignore  # noqa: F405
    """Override QApplication."""

    def __init__(self, args: Sequence[str] | None = None) -> None:
        """Override QApplication method."""
        super().__init__(args)

    def exec(self) -> int:
        """Override QApplication method."""
        if hasattr(super(), "exec"):
            return super().exec()
        return super().exec()

    def exit(self, returnCode: int = 0) -> None:  # noqa: N803
        """Override QApplication method."""
        return super().exit(returnCode)


QApplication = Application
