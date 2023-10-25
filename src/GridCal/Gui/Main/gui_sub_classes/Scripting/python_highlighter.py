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

import re

from PySide6.QtGui import QSyntaxHighlighter, QBrush
from PySide6.QtGui import QTextCharFormat, QColor


class PythonHighlighter(QSyntaxHighlighter):
    """
    PythonHighlighter
    """

    def __init__(self, document):

        super().__init__(document)

        # Define RGB colors for a dark theme
        cyan = QColor(0, 183, 235)
        magenta = QColor(233, 30, 99)
        yellow = QColor(255, 235, 59)
        red = QColor(244, 67, 54)
        dark_gray = QColor(96, 125, 139)
        dark_green = QColor(76, 175, 80)
        green = QColor(139, 195, 74)
        light_blue = QColor(33, 150, 243)
        orange = QColor(255, 152, 0)
        purple = QColor(156, 39, 176)
        pink = QColor(233, 30, 99)
        teal = QColor(0, 150, 136)
        deep_purple = QColor(103, 58, 183)
        amber = QColor(255, 193, 7)

        self.highlight_rules = [
            (r'\bdef\b\s+([a-zA-Z_]\w*)', cyan),  # Highlight function names
            (r'\bclass\b\s+([a-zA-Z_]\w*)', magenta),  # Highlight class names
            (r'\bif\b|\belse\b|\bwhile\b|\bfor\b|\bin\b|\bbreak\b|'
             r'\bcontinue\b|\bpass\b|\btry\b|\bexcept\b|\bfinally\b|\bassert\b', light_blue),
            (r'\bimport\b|\bfrom\b|\bas\b|\bglobal\b|\bnonlocal\b|\breturn\b|\byield\b|\bwith\b', teal),
            (r'\b|\band\b|\bor\b|\bnot\b|\bin\b', teal),
            (r'\bTrue\b|\bFalse', magenta),
            (r'\bNone\b|\bint\b|\bfloat\b|\bstr\b|\blist\b|\btuple\b|\bset\b|\bdict\b|\blen\b|\bprint\b', deep_purple),
            (r'\binput\b|\bopen\b|\bmin\b|\bmax\b|\bsum\b|\babs\b|\bround\b|\bord\b|\bchr\b', amber),
            (r'\ball\b|\bany\b|\bzip\b|\benumerate\b|\bsorted\b', pink),
            (r'#.*$', dark_gray),
            (r'".*?"', pink),
            (r"'.*?'", pink),
            (r'\b(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?\b', yellow),
            (r'\bprint\b', green),  # Highlight 'print' in green
            (r'\+', purple),  # Highlight math operations
            (r'-', purple),
            (r'\*', purple),
            (r'/', purple),
            (r'def', red),
            (r'=', orange),
            (r'<', orange),
            (r'>', orange),
            (r'class', red),
            (r'self', dark_green),
            # Add more highlighting rules as needed
        ]

    def highlightBlock(self, text):
        """
        Search the text to highlight
        :param text: some text to highlight
        """
        for pattern, color in self.highlight_rules:
            frmt = QTextCharFormat()
            frmt.setForeground(QBrush(color))

            for match in re.finditer(pattern, text, re.IGNORECASE):
                start, end = match.span()
                self.setFormat(start, end - start, frmt)