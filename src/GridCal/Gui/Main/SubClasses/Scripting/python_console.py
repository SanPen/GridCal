import io
import sys
import code
from PySide6.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget, QMainWindow
from PySide6.QtCore import Qt, QEvent, QObject
from GridCal.Gui.Main.SubClasses.Scripting.python_highlighter import PythonHighlighter
import builtins


class PythonConsole(QTextEdit):
    def __init__(self, banner: str = ""):
        super().__init__()

        self.interpreter = code.InteractiveConsole(locals=globals())

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

        # Install event filter to capture Enter key
        self.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent):
        """
        Event filter to capture Enter key presses.
        """
        if watched == self and event.type() == QEvent.KeyPress:
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
            elif event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key.Key_C:
                # Allow Ctrl+C for copying text
                return False
        return super().eventFilter(watched, event)

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
        # self.append_output(f"{self.prompt_text}{command}")

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

            # if not success:
            #     self.append_output("(Complete)")

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
