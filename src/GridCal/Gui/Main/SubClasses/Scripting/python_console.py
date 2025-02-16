# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import io
import sys
import code
from PySide6.QtWidgets import QApplication, QTextEdit, QPushButton, QVBoxLayout, QWidget, QMainWindow, QSplitter, QCompleter
from PySide6.QtCore import Qt, QEvent, QObject, QStringListModel
from PySide6.QtGui import QFont
from GridCal.Gui.Main.SubClasses.Scripting.python_highlighter import PythonHighlighter
import builtins


class PythonConsole(QWidget):
    def __init__(self, banner: str = ""):
        QWidget.__init__(self)

        self.interpreter = code.InteractiveConsole(locals=globals())

        # Main layout
        layout = QVBoxLayout()

        # Splitter for input and output
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Set the font for the console
        font = QFont("Consolas", 10, QFont.Weight.Normal)  # Adjust family, size, and weight as needed


        # Text output area
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(font)
        PythonHighlighter(self.output.document())
        splitter.addWidget(self.output)

        # Multi-line input area with autocompletion
        self.input_area = QTextEdit()
        self.input_area.setPlaceholderText("Enter Python code here...type Ctrl + Enter to run")
        self.input_area.setFont(font)
        PythonHighlighter(self.input_area.document())
        splitter.addWidget(self.input_area)

        # Set splitter sizes to 80% for output and 20% for input
        splitter.setSizes([800, 200])

        layout.addWidget(splitter)

        # Send button
        send_button = QPushButton("Send")
        send_button.clicked.connect(self.execute_command)
        layout.addWidget(send_button)

        self.setLayout(layout)

        # Install event filter to handle Ctrl+Enter
        self.input_area.installEventFilter(self)

        # Set up IntelliSense
        self.setup_intellisense()

        self.append_output(banner)

    def setup_intellisense(self):
        # Gather names from builtins and globals
        keywords = set(dir(builtins)) | set(globals().keys())
        self.completer = QCompleter()
        self.completer.setModel(QStringListModel(sorted(keywords)))
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setWidget(self.input_area)

    def eventFilter(self, watched: QObject, event: QEvent):
        """
        Event filter to capture Ctrl + Enter
        :param watched:
        :param event:
        :return:
        """
        if watched == self.input_area and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.ControlModifier:
                self.execute_command()
                return True
        return super().eventFilter(watched, event)

    def execute(self, command: str):
        """
        Run a command
        :param command: Python command to run
        """
        self.append_output(f">>> {command}")

        try:
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()

            ret = self.interpreter.runcode(command)
            stdout_output = sys.stdout.getvalue()
            stderr_output = sys.stderr.getvalue()
            sys.stdout = old_stdout
            sys.stderr = old_stderr

            if stdout_output:
                self.append_output(stdout_output)
            if stderr_output:
                self.append_output(stderr_output)

            if ret:
                self.append_output(str(ret))

        except Exception as e:
            self.append_output(str(e))

    def execute_command(self):
        """
        Run command
        :return:
        """
        command = self.input_area.toPlainText()
        self.input_area.clear()
        self.execute(command)

    def append_output(self, text: str):
        """
        Add some text to the output
        :param text: text to append
        """
        self.output.append(text)


if __name__ == "__main__":

    class ConsoleMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("PySide6 Python Console")
            console = PythonConsole(banner="Hohoi")
            self.setCentralWidget(console)

    app = QApplication(sys.argv)
    window = ConsoleMainWindow()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())
