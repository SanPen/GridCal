import sys
import string
import random
from PySide6 import QtCore, QtWidgets, QtGui


class HeaderViewWithWordWrap(QtWidgets.QHeaderView):
    """
    HeaderViewWithWordWrap
    """
    def __init__(self):
        QtWidgets.QHeaderView.__init__(self, QtCore.Qt.Orientation.Horizontal)

    def sectionSizeFromContents(self, logicalIndex):
        """

        :param logicalIndex:
        :return:
        """
        if self.model():
            headerText = self.model().headerData(logicalIndex, self.orientation(), QtCore.Qt.ItemDataRole.DisplayRole)
            # options = self.viewOptions()

            metrics = QtGui.QFontMetrics(self.font())
            maxWidth = self.sectionSize(logicalIndex)
            rect = metrics.boundingRect(QtCore.QRect(0, 0, maxWidth, 5000),
                                        self.defaultAlignment() |
                                        QtCore.Qt.TextFlag.TextWordWrap |
                                        QtCore.Qt.TextFlag.TextExpandTabs,
                                        headerText, 4)
            return rect.size()
        else:
            return QtWidgets.QHeaderView.sectionSizeFromContents(self, logicalIndex)

    def paintSection(self, painter, rect, logicalIndex):
        """

        :param painter:
        :param rect:
        :param logicalIndex:
        :return:
        """
        if self.model():
            painter.save()
            self.model().hideHeaders()
            QtWidgets.QHeaderView.paintSection(self, painter, rect, logicalIndex)
            self.model().unhideHeaders()
            painter.restore()
            headerText = self.model().headerData(logicalIndex,
                                                 self.orientation(),
                                                 QtCore.Qt.ItemDataRole.DisplayRole)

            painter.drawText(QtCore.QRectF(rect), QtCore.Qt.TextFlag.TextWordWrap, headerText)
        else:
            QtWidgets.QHeaderView.paintSection(self, painter, rect, logicalIndex)


class Model(QtCore.QAbstractTableModel):
    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)
        self.model_cols_names = ["Very-very long name of my first column",
                                 "Very-very long name of my second column",
                                 "Very-very long name of my third column",
                                 "Very-very long name of my fourth column"]
        self.hide_headers_mode = False
        self._data = []
        for i in range(0, 10):
            row_data = []
            for j in range(0, len(self.model_cols_names)):
                row_data.append(''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6)))
            self._data.append(row_data)

    def hideHeaders(self):
        self.hide_headers_mode = True

    def unhideHeaders(self):
        self.hide_headers_mode = False

    def rowCount(self, parent):
        if parent.isValid():
            return 0
        else:
            return len(self._data)

    def columnCount(self, parent):
        return len(self.model_cols_names)

    def data(self, index, role):
        if not index.isValid():
            return None
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        row = index.row()
        if row < 0 or row >= len(self._data):
            return None

        column = index.column()
        if column < 0 or column >= len(self.model_cols_names):
            return None

        return self._data[row][column]

    def headerData(self, section, orientation, role):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        if orientation != QtCore.Qt.Orientation.Horizontal:
            return None
        if section < 0 or section >= len(self.model_cols_names):
            return None
        if self.hide_headers_mode is True:
            return None
        else:
            return self.model_cols_names[section]


class MainForm(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.model = Model()
        self.view = QtWidgets.QTableView()
        self.view.setModel(self.model)
        self.view.setHorizontalHeader(HeaderViewWithWordWrap())
        self.setCentralWidget(self.view)


def main():
    app = QtWidgets.QApplication(sys.argv)
    form = MainForm()
    form.show()
    app.exec()


if __name__ == '__main__':
    main()
