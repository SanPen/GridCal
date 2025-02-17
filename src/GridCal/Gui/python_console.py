# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import io
import sys
import code
from typing import Dict, Any
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication, QTextEdit, QMainWindow
from PySide6.QtCore import Qt, QEvent, QObject
from GridCal.Gui.python_highlighter import PythonHighlighter


class PythonConsole(QTextEdit):
    def __init__(self, banner: str = ""):
        super().__init__()

        self.interpreter = code.InteractiveConsole(locals=globals())

        font = QFont("Consolas", 10)  # Replace "Consolas" with your preferred monospaced font

        # Source code
        self.setFont(font)
        font_metrics = QFontMetrics(font)  # Set tab width to 4 spaces
        tab_stop_width = font_metrics.horizontalAdvance(' ' * 4)  # Width of 4 spaces in the selected font
        self.setTabStopDistance(tab_stop_width)

        # Enable syntax highlighting
        PythonHighlighter(self.document())

        # Initialize output area
        self.setReadOnly(False)
        self.setAcceptRichText(False)
        self.prompt_text = ">>> "  # Prompt indicator
        self.history = []  # Command history
        self.history_index = -1
        self.append_output(banner)
        self.append_output(self.prompt_text)

        # Store last cursor position (after prompt)
        self.last_cursor_pos = self.textCursor().position()

        self.setPlaceholderText(banner + "\nEnter Python code here\nType Ctrl + Enter to run")

        # Install event filter to capture Enter key
        self.installEventFilter(self)

    def reset(self):
        """
        Create a new interactive console object
        """
        self.interpreter = code.InteractiveConsole(locals=globals())

    def eventFilter(self, watched: QObject, event: QEvent):
        """
        Event filter to capture Enter key presses.
        """
        if watched == self and event.type() == QEvent.Type.KeyPress:
            cursor = self.textCursor()
            if event.key() == Qt.Key.Key_Return:
                self.process_input()
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                # Prevent deleting past outputs
                if cursor.position() <= self.last_cursor_pos:
                    return True
            elif event.key() == Qt.Key.Key_Up:
                # Navigate command history
                if self.history and self.history_index > 0:
                    self.history_index -= 1
                    self.replace_current_input(self.history[self.history_index])
                    return True
            elif event.key() == Qt.Key.Key_Down:
                # Navigate forward in history
                if self.history and self.history_index < len(self.history) - 1:
                    self.history_index += 1
                    self.replace_current_input(self.history[self.history_index])
                    return True
            elif event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_C:
                # Allow Ctrl+C for copying text
                return False
        return super().eventFilter(watched, event)

    def clear(self):
        super().clear()
        self.append_output(">>> ")

    def process_input(self):
        """
        Capture user input, execute it, and append results.
        """
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.setTextCursor(cursor)

        # Extract last entered line
        text = self.toPlainText().split("\n")
        if not text:
            return

        # Extract input from the last prompt
        last_line = text[-1].replace(self.prompt_text, "", 1).strip()
        if not last_line:
            self.append_output(self.prompt_text)
            return

        # Store command in history
        self.history.append(last_line)
        self.history_index = len(self.history)

        # Execute command
        # self.append_output("\n")  # Newline for readability
        self.execute(last_line)

        # Append new prompt
        self.append_output(self.prompt_text)

    def execute(self, command: str):
        """
        Run a command and display output.
        """

        try:
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()

            success = self.interpreter.runcode(command)
            stdout_output = sys.stdout.getvalue()
            stderr_output = sys.stderr.getvalue()
            sys.stdout = old_stdout
            sys.stderr = old_stderr

            if stdout_output:
                self.append_output(stdout_output)
            if stderr_output:
                self.append_output(stderr_output)

        except Exception as e:
            self.append_output(str(e))

    def append_output(self, text: str):
        """
        Append text to the console.
        """
        self.append(text)
        self.moveCursor(self.textCursor().MoveOperation.End)
        self.last_cursor_pos = self.textCursor().position()

    def replace_current_input(self, text: str):
        """
        Replace the current input line with the given text.
        """
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        # Remove previous input after the last prompt
        cursor.setPosition(self.last_cursor_pos, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self.setTextCursor(cursor)

    def add_var(self, name: str, val: Any) -> None:
        """
        Add variable to the interpreter
        :param name: name of the variable
        :param val: value or pointer
        """
        self.interpreter.locals[name] = val

    def push_vars(self, vars_dict: Dict[str, Any]) -> None:
        """
        Add vars to the interpreter
        :param vars_dict: dictionary of var name -> value or function pointer
        :return: None
        """
        for key, value in vars_dict.items():
            self.add_var(key, value)

if __name__ == "__main__":

    class ConsoleMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("PySide6 Python Console")
            console = PythonConsole(banner="Welcome to Python Console!")
            self.setCentralWidget(console)

    app = QApplication(sys.argv)
    window = ConsoleMainWindow()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())
