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
from __future__ import annotations

import darkdetect

from GridCal.ThirdParty.qdarktheme import _os_appearance
from GridCal.ThirdParty.qdarktheme.qtpy.QtCore import QCoreApplication, QEvent, QObject, QThread, Signal


class OSThemeSwitchListener(QThread):
    """Listener to detect to change OS's theme."""

    sig_run = Signal(bool)
    _sig_listen_os_theme = Signal()

    def __init__(self, callable) -> None:
        """Initialize listener."""
        super().__init__()
        self.setProperty("is_running", True)
        self._theme = darkdetect.theme()
        self._accent = _os_appearance.accent()
        self.sig_run.connect(lambda state: self.setProperty("is_running", state))
        self._sig_listen_os_theme.connect(callable)

    def eventFilter(self, q_object: QObject, event: QEvent) -> bool:  # noqa: N802
        """Override QObject.eventFilter.

        This override is for Mac.
        Qt can listen to change OS's theme on only mac and changed QPalette automatically.
        So enable to listen to change OS's theme via palette change event.
        """
        if (
            self.property("is_running")
            and q_object == QCoreApplication.instance()
            and event.type() == QEvent.Type.ApplicationPaletteChange
        ):
            accent = _os_appearance.accent()
            theme = darkdetect.theme()
            if self._theme != theme or self._accent != accent:
                self._theme = theme
                self._accent = accent
                self._sig_listen_os_theme.emit()
                return True
        return super().eventFilter(q_object, event)

    def run(self) -> None:
        """Override QThread.run.

        This override is for except Mac.
        Qt cannot listen to change OS's theme on except Mac.
        Use ``darkdetect.listener`` to detect to change OS's theme.
        """
        darkdetect.listener(
            lambda theme: self.property("is_running") and self._sig_listen_os_theme.emit()
        )

    def kill(self) -> None:
        """Kill thread."""
        self.terminate()
        self.deleteLater()
