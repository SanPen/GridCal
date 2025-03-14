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
"""Module loading QPalette."""
from __future__ import annotations

from functools import partial

from GridCal.ThirdParty.qdarktheme._template.engine import Template


def q_palette(mk_template: partial[Template], color_map: dict[str, str | dict], for_stylesheet: bool):
    """Generate QPalette."""
    from GridCal.ThirdParty.qdarktheme.qtpy.QtGui import QColor, QPalette

    def _mk_q_color(text: str):
        template = mk_template(text)
        color_format = template.render(color_map)
        return QColor(color_format)

    palette = QPalette()

    if not for_stylesheet:
        # base
        palette.setColor(QPalette.ColorRole.WindowText, _mk_q_color("{{ foreground|color|palette }}"))
        palette.setColor(
            QPalette.ColorRole.Button, _mk_q_color("{{ treeSectionHeader.background|color|palette }}")
        )
        palette.setColor(QPalette.ColorRole.ButtonText, _mk_q_color("{{ primary|color|palette }}"))
        palette.setColor(QPalette.ColorRole.Base, _mk_q_color("{{ background|color|palette }}"))
        palette.setColor(QPalette.ColorRole.Window, _mk_q_color("{{ background|color|palette }}"))
        palette.setColor(QPalette.ColorRole.Highlight, _mk_q_color("{{ primary|color|palette }}"))
        palette.setColor(
            QPalette.ColorRole.HighlightedText, _mk_q_color("{{ background|color|palette }}")
        )
        palette.setColor(
            QPalette.ColorRole.AlternateBase,
            _mk_q_color("{{ list.alternateBackground|color|palette }}"),
        )
        palette.setColor(
            QPalette.ColorRole.ToolTipBase, _mk_q_color('{{ background|color(state="popup")|palette }}')
        )
        palette.setColor(QPalette.ColorRole.ToolTipText, _mk_q_color("{{ foreground|color|palette }}"))
        if hasattr(QPalette.ColorRole, "Foreground"):
            palette.setColor(
                QPalette.ColorRole.Foreground,  # type: ignore
                _mk_q_color("{{ foreground|color|palette }}"),
            )

        palette.setColor(QPalette.ColorRole.Light, _mk_q_color("{{ border|color|palette }}"))
        palette.setColor(QPalette.ColorRole.Midlight, _mk_q_color("{{ border|color|palette }}"))
        palette.setColor(QPalette.ColorRole.Dark, _mk_q_color("{{ background|color|palette }}"))
        palette.setColor(QPalette.ColorRole.Mid, _mk_q_color("{{ border|color|palette }}"))
        palette.setColor(QPalette.ColorRole.Shadow, _mk_q_color("{{ border|color|palette }}"))

        # disabled
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.WindowText,
            _mk_q_color('{{ foreground|color(state="disabled")|palette }}'),
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.ButtonText,
            _mk_q_color('{{ foreground|color(state="disabled")|palette }}'),
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.Highlight,
            _mk_q_color('{{ foreground|color(state="disabledSelectionBackground")|palette }}'),
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.HighlightedText,
            _mk_q_color('{{ foreground|color(state="disabled")|palette }}'),
        )

        # inactive
        palette.setColor(
            QPalette.ColorGroup.Inactive,
            QPalette.ColorRole.Highlight,
            _mk_q_color('{{ primary|color(state="list.inactiveSelectionBackground")|palette }}'),
        )
        palette.setColor(
            QPalette.ColorGroup.Inactive,
            QPalette.ColorRole.HighlightedText,
            _mk_q_color("{{ foreground|color|palette }}"),
        )

    palette.setColor(
        QPalette.ColorRole.Text, _mk_q_color('{{ foreground|color(state="icon")|palette }}')
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        _mk_q_color('{{ foreground|color(state="disabled")|palette }}'),
    )
    palette.setColor(QPalette.ColorRole.Link, _mk_q_color("{{ primary|color|palette }}"))
    palette.setColor(QPalette.ColorRole.LinkVisited, _mk_q_color("{{ linkVisited|color|palette }}"))
    if hasattr(QPalette.ColorRole, "PlaceholderText"):
        palette.setColor(
            QPalette.ColorRole.PlaceholderText,
            _mk_q_color('{{ foreground|color(state="input.placeholder")|palette }}'),
        )

    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Link,
        _mk_q_color('{{ foreground|color(state="disabledSelectionBackground")|palette }}'),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.LinkVisited,
        _mk_q_color('{{ foreground|color(state="disabled")|palette }}'),
    )

    return palette
