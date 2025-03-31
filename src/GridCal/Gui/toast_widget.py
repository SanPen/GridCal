from typing import Optional, Callable, List
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication, QPushButton
from PySide6.QtCore import QTimer, Qt, QPoint


class ToastWidget(QWidget):
    def __init__(self, parent: QWidget,
        message: str,
        duration: int = 2000,
        max_width: Optional[int] = None,
        offset_y: int = 0,
        position_top: bool = False,
        on_close: Optional[Callable[['ToastWidget'], None]] = None):
        """

        :param parent:
        :param message: Message to display
        :param duration: Duration of the toast (ms)
        :param max_width: Max width of the toast
        :param offset_y: y axis offset (px)
        :param position_top: Position on top?
        :param on_close: what to call on close
        """
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.setStyleSheet("""
            QLabel {
                background-color: rgba(16, 191, 137, 160);
                color: white;
                padding: 8px 12px;
                border-radius: 10px;
                font-size: 12pt;
            }
        """)

        layout: QVBoxLayout = QVBoxLayout(self)
        label: QLabel = QLabel(message)
        label.setWordWrap(True)

        parent_width: int = parent.width()
        max_width = max_width or int(parent_width * 0.9)
        label.setMaximumWidth(max_width)

        layout.addWidget(label)
        layout.setContentsMargins(0, 0, 0, 0)
        self.adjustSize()

        self._offset_y: int = offset_y
        self._position_top: bool = position_top
        self._on_close: Optional[Callable[['ToastWidget'], None]] = on_close
        self._reposition()

        self.show()
        QTimer.singleShot(duration, self.close_toast)

    def _reposition(self) -> None:
        """
        Reposition a widget upon the creation of another toast
        :return:
        """
        parent: QWidget = self.parentWidget()  # type: ignore
        parent_rect = parent.geometry()
        y = (
            20 + self._offset_y
            if self._position_top
            else parent_rect.height() - self.height() - 20 - self._offset_y
        )
        self.move(
            parent.mapToGlobal(QPoint(
                (parent_rect.width() - self.width()) // 2,
                y
            ))
        )

    def update_offset(self, offset_y: int) -> None:
        """
        Update offset
        :param offset_y:
        :return:
        """
        self._offset_y = offset_y
        self._reposition()

    def close_toast(self) -> None:
        """
        Close toast
        :return:
        """
        self.close()
        if self._on_close:
            self._on_close(self)



class ToastManager:

    def __init__(self, parent: QWidget, position_top: bool = False) -> None:
        """

        :param parent:
        :param position_top:
        """
        self.parent: QWidget = parent
        self.position_top: bool = position_top
        self.active_toasts: List[ToastWidget] = []

    def show_toast(self, message: str, duration: int = 2000) -> None:
        """
        Show toast
        :param message: Message to display
        :param duration: duration in ms
        """
        offset_y: int = sum(toast.height() + 10 for toast in self.active_toasts)
        toast: ToastWidget = ToastWidget(
            parent=self.parent,
            message=message,
            duration=duration,
            offset_y=offset_y,
            position_top=self.position_top,
            on_close=self.remove_toast
        )
        self.active_toasts.append(toast)

    def remove_toast(self, toast: ToastWidget) -> None:
        """
        Remove toast
        :param toast: ToastWidget
        """
        if toast in self.active_toasts:
            self.active_toasts.remove(toast)
            # Re-stack remaining toasts
            offset_y: int = 0
            for t in self.active_toasts:
                t.update_offset(offset_y)
                offset_y += t.height() + 10


# Example usage
if __name__ == "__main__":
    app: QApplication = QApplication([])

    main_win: QWidget = QWidget()
    main_win.setWindowTitle("Stacked Toast Demo")
    main_win.setFixedSize(400, 300)

    layout_: QVBoxLayout = QVBoxLayout(main_win)

    toast_manager_bottom = ToastManager(main_win, position_top=False)
    toast_manager_top = ToastManager(main_win, position_top=True)

    btn_bottom: QPushButton = QPushButton("Show Bottom Toast")
    btn_bottom.clicked.connect(lambda: toast_manager_bottom.show_toast("Bottom Toast Message"))
    layout_.addWidget(btn_bottom)

    btn_top: QPushButton = QPushButton("Show Top Toast")
    btn_top.clicked.connect(lambda: toast_manager_top.show_toast("Top Toast Message"))
    layout_.addWidget(btn_top)

    main_win.show()
    app.exec()
