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

import platform

from GridCal.ThirdParty.qdarktheme._icon.icon_engine import SvgIconEngine
from GridCal.ThirdParty.qdarktheme._icon.svg import Svg
from GridCal.ThirdParty.qdarktheme._resources.standard_icons import NEW_STANDARD_ICON_MAP
from GridCal.ThirdParty.qdarktheme.qtpy.QtGui import QIcon
from GridCal.ThirdParty.qdarktheme.qtpy.QtWidgets import QProxyStyle, QStyle, QStyleOption


class QDarkThemeStyle(QProxyStyle):
    """Style proxy to improve theme."""

    def __init__(self):
        """Initialize style proxy."""
        super().__init__()

    def standardIcon(  # noqa: N802
        self, standard_icon: QStyle.StandardPixmap, option: QStyleOption | None, widget
    ) -> QIcon:
        """Implement QProxyStyle.standardIcon."""
        icon_info = NEW_STANDARD_ICON_MAP.get(standard_icon)
        if icon_info is None:
            return super().standardIcon(standard_icon, option, widget)

        os_list = icon_info.get("os")
        if os_list is not None and platform.system() not in os_list:
            return super().standardIcon(standard_icon, option, widget)

        rotate = icon_info.get("rotate", 0)
        svg = Svg(icon_info["id"]).rotate(rotate)
        icon_engine = SvgIconEngine(svg)
        return QIcon(icon_engine)
