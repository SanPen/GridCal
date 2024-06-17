"""Module allowing for `python -m qdarktheme.widget_gallery`."""
import sys

import GridCal.ThirdParty.qdarktheme as qdarktheme
from GridCal.ThirdParty.qdarktheme.qtpy.QtWidgets import QApplication
from GridCal.ThirdParty.qdarktheme.widget_gallery.main_window import WidgetGallery

if __name__ == "__main__":
    qdarktheme.enable_hi_dpi()
    app = QApplication(sys.argv)
    qdarktheme.setup_theme("auto")
    win = WidgetGallery()
    win.show()
    app.exec()
