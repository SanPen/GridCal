from typing import Optional, Callable, List
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import QTimer, Qt, QPoint


class ToastWidget(QWidget):

    def __init__(self, parent: QWidget,
                 message: str,
                 duration: int = 2000,
                 toast_type: str = "veragrid",
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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        background_color = {
            "veragrid": "rgba(16, 191, 137, 160)",  # veragrid color
            "info": "rgba(46, 204, 113, 220)",  # green
            "warning": "rgba(241, 196, 15, 220)",  # yellow
            "error": "rgba(231, 76, 60, 220)"  # red
        }.get(toast_type, "rgba(50, 50, 50, 220)")  # fallback

        text_color = {
            "veragrid": "white",
            "info": "white",
            "warning": "black",
            "error": "white"
        }.get(toast_type, "white")

        self.setStyleSheet(f"""
                    QLabel {{
                        background-color: {background_color};
                        color: {text_color};
                        padding: 8px 12px;
                        border-radius: 10px;
                        font-size: 12pt;
                    }}
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

    def show_toast(self, message: str, duration: int = 2000, toast_type: str = "veragrid") -> None:
        """
        Show toast
        :param message: Message to display
        :param duration: duration in ms
        :param toast_type: type of toast (veragrid, info, error, warning)
        """
        offset_y: int = sum(toast.height() + 10 for toast in self.active_toasts)
        toast: ToastWidget = ToastWidget(
            parent=self.parent,
            message=message,
            duration=duration,
            toast_type=toast_type,
            offset_y=offset_y,
            position_top=self.position_top,
            on_close=self.remove_toast
        )
        self.active_toasts.append(toast)

    def show_error_toast(self, message: str, duration: int = 2000):
        """
        Show error toast
        :param message: Message to display
        :param duration: duration in ms
        """
        self.show_toast(message=message, duration=duration, toast_type="error")

    def show_warning_toast(self, message: str, duration: int = 2000):
        """
        Show warning toast
        :param message: Message to display
        :param duration: duration in ms
        """
        self.show_toast(message=message, duration=duration, toast_type="warning")

    def show_info_toast(self, message: str, duration: int = 2000):
        """
        Show info toast
        :param message: Message to display
        :param duration: duration in ms
        """
        self.show_toast(message=message, duration=duration, toast_type="info")

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
