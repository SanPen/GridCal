# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import re

from PySide6.QtGui import QSyntaxHighlighter, QBrush
from PySide6.QtGui import QTextCharFormat, QColor, QFont


class PythonHighlighter(QSyntaxHighlighter):
    """
    PythonHighlighter
    """

    def __init__(self, document):

        super().__init__(document)

        # Define RGB colors for a dark theme
        cyan = QColor(0, 183, 235)
        magenta = QColor(233, 30, 99)
        # yellow = QColor(255, 235, 59)
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
            (r'\bdef\b\s+([a-zA-Z_]\w*)', cyan, False),  # Highlight function names
            (r'\bclass\b\s+([a-zA-Z_]\w*)', magenta, False),  # Highlight class names
            (r'\bif\b|\belse\b|\bwhile\b|\bfor\b|\bin\b|\bbreak\b|'
             r'\bcontinue\b|\bpass\b|\btry\b|\bexcept\b|\bfinally\b|\bassert\b', light_blue, True),
            (r'\bimport\b|\bfrom\b|\bas\b|\bglobal\b|\bnonlocal\b|\breturn\b|\byield\b|\bwith\b', teal, True),
            (r'\b|\band\b|\bor\b|\bnot\b|\bin\b', teal, True),
            (r'\bTrue\b|\bFalse', magenta, True),
            (r'\bNone\b|\bint\b|\bfloat\b|\bstr\b|\blist\b|\btuple\b|\bset\b|\bdict\b|\blen\b', deep_purple, True),
            (r'\binput\b|\bopen\b|\bmin\b|\bmax\b|\bsum\b|\babs\b|\bround\b|\bord\b|\bchr\b|\brange\b', amber, True),
            (r'\ball\b|\bany\b|\bzip\b|\benumerate\b|\bsorted\b', pink, True),
            (r'#.*$', dark_gray, False),
            (r'".*?"', pink, False),
            (r"'.*?'", pink, False),
            (r'\b(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?\b', dark_green, False),
            (r'\bprint\b', green, True),  # Highlight 'print' in green
            (r'\+', purple, False),  # Highlight math operations
            (r'-', purple, False),
            (r'\*', purple, False),
            (r'/', purple, False),
            (r'def', red, True),
            (r'=', orange, False),
            (r'<', orange, False),
            (r'>', orange, False),
            (r'class', red, True),
            (r'self', dark_green, False),
            # Add more highlighting rules as needed
        ]

    def highlightBlock(self, text):
        """
        Search the text to highlight
        :param text: some text to highlight
        """
        for pattern, color, bold in self.highlight_rules:
            frmt = QTextCharFormat()
            frmt.setForeground(QBrush(color))

            if bold:
                frmt.setFontWeight(QFont.Weight.Bold)

            for match in re.finditer(pattern, text, re.IGNORECASE):
                start, end = match.span()
                self.setFormat(start, end - start, frmt)
