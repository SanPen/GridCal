from PySide2.QtGui import QPalette, QColor





def css_rgb(color, a=False):
    """Get a CSS `rgb` or `rgba` string from a `QtGui.QColor`."""
    return ("rgba({}, {}, {}, {})" if a else "rgb({}, {}, {})").format(*color.getRgb())


class QDarkPalette(QPalette):
    """Dark palette for a Qt application meant to be used with the Fusion theme."""
    def __init__(self, *__args):
        super().__init__(*__args)

        self.WHITE = QColor(255, 255, 255)
        self.BLACK = QColor(0, 0, 0)
        self.RED = QColor(255, 0, 0)
        self.PRIMARY = QColor(53, 53, 53)
        self.SECONDARY = QColor(35, 35, 35)
        self.TERTIARY = QColor(42, 130, 218)

        # Set all the colors based on the constants in globals
        self.setColor(QPalette.Window,          self.PRIMARY)
        self.setColor(QPalette.WindowText,      self.WHITE)
        self.setColor(QPalette.Base,            self.SECONDARY)
        self.setColor(QPalette.AlternateBase,   self.PRIMARY)
        self.setColor(QPalette.ToolTipBase,     self.WHITE)
        self.setColor(QPalette.ToolTipText,     self.WHITE)
        self.setColor(QPalette.Text,            self.WHITE)
        self.setColor(QPalette.Button,          self.PRIMARY)
        self.setColor(QPalette.ButtonText,      self.WHITE)
        self.setColor(QPalette.BrightText,      self.RED)
        self.setColor(QPalette.Link,            self.TERTIARY)
        self.setColor(QPalette.Highlight,       self.TERTIARY)
        self.setColor(QPalette.HighlightedText, self.BLACK)

    def set_stylesheet(self, app):
        """
        Static method to set the tooltip stylesheet to a `QtWidgets.QApplication`
        """
        app.setStyleSheet("QToolTip {{"
                          "color: {white};"
                          "background-color: {tertiary};"
                          "border: 1px solid {white};"
                          "}}".format(white=css_rgb(self.WHITE), tertiary=css_rgb(self.TERTIARY)))

    def set_app(self, app):
        """
        Set the Fusion theme and this palette to a `QtWidgets.QApplication`.
        """
        app.setStyle("Fusion")
        app.setPalette(self)
        self.set_stylesheet(app)
