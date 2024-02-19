import re
import sys
from PySide6.QtGui import QSyntaxHighlighter, QBrush, QFont, QFontMetrics
from PySide6.QtGui import QTextCharFormat, QColor
from PySide6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit


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

        # self.highlight_rules = [
        #     (r'\bdef\b', cyan),
        #     (r'\bclass\b', cyan),
        #     (r'\bif\b', cyan),
        #     (r'\belif\b', cyan),
        #     (r'\belse\b', cyan),
        #     (r'\bfor\b', cyan),
        #     (r'\bwhile\b', cyan),
        #     (r'\btry\b', cyan),
        #     (r'\bexcept\b', cyan),
        #     (r'\bimport\b', magenta),
        #     (r'\bfrom\b', magenta),
        #     (r'\bas\b', magenta),
        #     (r'\bTrue\b|\bFalse\b', red),
        #     (r'\band\b', red),
        #     (r'\bor\b', red),
        #     (r'\bnot\b', red),
        #     (r'\bin\b', red),
        #     (r'\breturn\b', red),
        #     (r'\byield\b', red),
        #     (r'\bwith\b', red),
        #     (r'\bas\b', red),
        #     (r'\bglobal\b', red),
        #     (r'\bnonlocal\b', red),
        #     (r'\bpass\b', dark_gray),
        #     (r'\bbreak\b', dark_gray),
        #     (r'\bcontinue\b', dark_gray),
        #     (r'\btry\b', dark_gray),
        #     (r'\bexcept\b', dark_gray),
        #     (r'\bfinally\b', dark_gray),
        #     (r'\bassert\b', dark_gray),
        #     (r'\bdef\b', dark_green),
        #     (r'\blambda\b', dark_green),
        #     (r'\bwhile\b', dark_green),
        #     (r'\bif\b', dark_green),
        #     (r'\belif\b', dark_green),
        #     (r'\belse\b', dark_green),
        #     (r'\bfor\b', dark_green),
        #     (r'\bin\b', dark_green),
        #     (r'\bbreak\b', dark_green),
        #     (r'\bcontinue\b', dark_green),
        #     (r'\bpass\b', dark_green),
        #     (r'\bdel\b', dark_green),
        #     (r'\btry\b', dark_green),
        #     (r'\bexcept\b', dark_green),
        #     (r'\bfinally\b', dark_green),
        #     (r'\bas\b', teal),
        #     (r'\bimport\b', teal),
        #     (r'\bfrom\b', teal),
        #     (r'\bwith\b', teal),
        #     (r'\bTrue\b|\bFalse\b', teal),
        #     (r'\bNone\b', deep_purple),
        #     (r'\bint\b', deep_purple),
        #     (r'\bfloat\b', deep_purple),
        #     (r'\bstr\b', deep_purple),
        #     (r'\blist\b', deep_purple),
        #     (r'\btuple\b', deep_purple),
        #     (r'\bset\b', deep_purple),
        #     (r'\bdict\b', deep_purple),
        #     (r'\blen\b', deep_purple),
        #     (r'\bprint\b', deep_purple),
        #     (r'\binput\b', amber),
        #     (r'\bopen\b', amber),
        #     (r'\bmin\b', amber),
        #     (r'\bmax\b', amber),
        #     (r'\bsum\b', amber),
        #     (r'\babs\b', amber),
        #     (r'\bround\b', amber),
        #     (r'\bord\b', amber),
        #     (r'\bchr\b', amber),
        #     (r'\ball\b', pink),
        #     (r'\bany\b', pink),
        #     (r'\bzip\b', pink),
        #     (r'\benumerate\b', pink),
        #     (r'\bsorted\b', pink),
        #     (r'#.*$', pink),
        #     (r'".*?"', pink),
        #     (r"'.*?'", pink),
        #     (r'\b(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?\b', yellow),
        #     (r'\bprint\b', green),  # Highlight 'print' in green
        #     (r'\+', yellow),  # Highlight math operations
        #     (r'-', yellow),
        #     (r'\*', yellow),
        #     (r'/', yellow),
        #     # Add more highlighting rules as needed
        # ]

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


class CodeEditorWidget(QPlainTextEdit):
    """
    CodeEditorWidget
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set the font for your widget
        font = QFont("Consolas", 10)  # Replace "Consolas" with your preferred monospaced font
        self.setFont(font)

        # Set tab width to 4 spaces
        font_metrics = QFontMetrics(font)
        tab_stop_width = font_metrics.horizontalAdvance(' ' * 4)  # Width of 4 spaces in the selected font
        self.setTabStopDistance(tab_stop_width)

        self.highlighter = PythonHighlighter(self.document())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QMainWindow()
    editor = CodeEditorWidget()
    window.setCentralWidget(editor)

    window.setGeometry(100, 100, 800, 600)
    window.show()

    sys.exit(app.exec())
