# MIT License
#
# Copyright (c) 2021-2022 Yunosuke Ohsugi
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""Module setting up ui of widgets window."""
from __future__ import annotations

from typing import Any

from GridCal.ThirdParty.qdarktheme.qtpy.QtCore import QAbstractTableModel, QModelIndex, Qt
from GridCal.ThirdParty.qdarktheme.qtpy.QtGui import QIcon, QStandardItem, QStandardItemModel, QTextOption
from GridCal.ThirdParty.qdarktheme.qtpy.QtWidgets import (
    QCheckBox,
    QColumnView,
    QComboBox,
    QDateTimeEdit,
    QDial,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLCDNumber,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableView,
    QTabWidget,
    QTextEdit,
    QToolBox,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class _Group1(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Buttons")

        # Widgets
        group_push = QGroupBox("Push Button")
        group_tool = QGroupBox("Tool Button")
        group_radio = QGroupBox("Radio Button")
        group_checkbox = QGroupBox("Check Box")

        push_btn, push_btn_toggled = QPushButton("NORMAL"), QPushButton("TOGGLED")
        push_btn_flat, push_btn_flat_toggled = QPushButton("NORMAL"), QPushButton("TOGGLED")
        tool_btn, tool_btn_toggled, tool_btn_text, tool_btn_menu = (QToolButton() for _ in range(4))
        radio_btn_1, radio_btn_2 = QRadioButton("Normal 1"), QRadioButton("Normal 2")
        checkbox, checkbox_tristate = QCheckBox("Normal"), QCheckBox("Tristate")

        # Setup widgets
        self.setCheckable(True)
        push_btn_flat.setFlat(True)
        push_btn_flat_toggled.setFlat(True)
        for btn in (push_btn_toggled, push_btn_flat_toggled):
            btn.setCheckable(True)
            btn.setChecked(True)

        tool_btn.setIcon(QIcon("icons:favorite_border_24dp.svg"))
        tool_btn_toggled.setIcon(QIcon("icons:favorite_border_24dp.svg"))
        tool_btn_text.setIcon(QIcon("icons:favorite_border_24dp.svg"))
        tool_btn_menu.setIcon(QIcon("icons:favorite_border_24dp.svg"))
        tool_btn_text.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tool_btn_text.setText("Text")
        tool_btn_menu.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        tool_btn_toggled.setCheckable(True)
        tool_btn_toggled.setChecked(True)

        radio_btn_1.setChecked(True)
        checkbox.setChecked(True)
        checkbox_tristate.setTristate(True)
        checkbox_tristate.setCheckState(Qt.CheckState.PartiallyChecked)

        # Layout
        g_layout_push = QGridLayout()
        g_layout_push.addWidget(QLabel("Normal"), 0, 0)
        g_layout_push.addWidget(push_btn, 1, 0)
        g_layout_push.addWidget(push_btn_toggled, 2, 0)
        g_layout_push.addWidget(QLabel("Flat"), 0, 1)
        g_layout_push.addWidget(push_btn_flat, 1, 1)
        g_layout_push.addWidget(push_btn_flat_toggled, 2, 1)
        group_push.setLayout(g_layout_push)

        v_layout_tool = QVBoxLayout()
        v_layout_tool.addWidget(tool_btn)
        v_layout_tool.addWidget(tool_btn_toggled)
        v_layout_tool.addWidget(tool_btn_text)
        v_layout_tool.addWidget(tool_btn_menu)
        group_tool.setLayout(v_layout_tool)

        v_layout_radio = QVBoxLayout()
        v_layout_radio.addWidget(radio_btn_1)
        v_layout_radio.addWidget(radio_btn_2)
        group_radio.setLayout(v_layout_radio)

        v_layout_checkbox = QVBoxLayout()
        v_layout_checkbox.addWidget(checkbox)
        v_layout_checkbox.addWidget(checkbox_tristate)
        group_checkbox.setLayout(v_layout_checkbox)

        g_layout_main = QGridLayout(self)
        g_layout_main.addWidget(group_push, 0, 0)
        g_layout_main.addWidget(group_tool, 0, 1)
        g_layout_main.addWidget(group_radio, 1, 0)
        g_layout_main.addWidget(group_checkbox, 1, 1)


class _Group2(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Line boxes")
        # Widgets
        group_spinbox = QGroupBox("Spinbox")
        group_combobox = QGroupBox("Combobox")
        group_editable = QGroupBox("Line edit")
        group_date = QGroupBox("Date time edit")

        spinbox, spinbox_suffix = QSpinBox(), QSpinBox()
        combobox, combobox_line_edit = QComboBox(), QComboBox()
        line_edit = QLineEdit()
        date_time_edit, date_time_edit_calendar = QDateTimeEdit(), QDateTimeEdit()

        # Setup widgets
        self.setCheckable(True)
        spinbox_suffix.setSuffix(" m")

        combobox.addItems(("Item 1", "Item 2", "Item 3"))
        combobox_line_edit.addItems(("Item 1", "Item 2", "Item 3"))
        combobox_line_edit.setEditable(True)

        line_edit.setPlaceholderText("Placeholder text")
        date_time_edit_calendar.setCalendarPopup(True)

        # Layout
        v_layout_spin = QVBoxLayout()
        v_layout_spin.addWidget(spinbox)
        v_layout_spin.addWidget(spinbox_suffix)
        group_spinbox.setLayout(v_layout_spin)

        v_layout_combo = QVBoxLayout()
        v_layout_combo.addWidget(combobox)
        v_layout_combo.addWidget(combobox_line_edit)
        group_combobox.setLayout(v_layout_combo)

        v_layout_line_edit = QVBoxLayout()
        v_layout_line_edit.addWidget(line_edit)
        group_editable.setLayout(v_layout_line_edit)

        v_layout_date = QVBoxLayout()
        v_layout_date.addWidget(date_time_edit)
        v_layout_date.addWidget(date_time_edit_calendar)
        group_date.setLayout(v_layout_date)

        g_layout_main = QGridLayout(self)
        g_layout_main.addWidget(group_spinbox, 0, 0)
        g_layout_main.addWidget(group_combobox, 0, 1)
        g_layout_main.addWidget(group_editable, 1, 0)
        g_layout_main.addWidget(group_date, 1, 1)


class _TableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._data = [[i * 10 + j for j in range(4)] for i in range(5)]

    def data(self, index: QModelIndex, role: int) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            return self._data[index.row()][index.column()]
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 1:
            return Qt.CheckState.Checked if index.row() % 2 == 0 else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.EditRole and index.column() == 2:
            return self._data[index.row()][index.column()]  # pragma: no cover
        return None

    def rowCount(self, index) -> int:  # noqa: N802
        return len(self._data)

    def columnCount(self, index) -> int:  # noqa: N802
        return len(self._data[0])

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        flag = super().flags(index)
        if index.column() == 1:
            flag |= Qt.ItemFlag.ItemIsUserCheckable
        elif index.column() in (2, 3):
            flag |= Qt.ItemFlag.ItemIsEditable
        return flag  # type: ignore

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = ...
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return ["Normal", "Checkbox", "Spinbox", "LineEdit"][section]
        return section * 100


class _Group3(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Scroll area and QTabWidget (QGroupBox.flat = True)")

        # Widgets
        tab_widget = QTabWidget()
        tab_text_edit = QTextEdit()
        tab_table = QTableView()
        tab_list = QListWidget()
        tab_tree = QTreeWidget()
        tab_column = QColumnView()
        btn_toggle_alternating = QPushButton("Alternating")

        # Setup widgets
        self.setCheckable(True)
        self.setFlat(True)
        tab_widget.setTabsClosable(True)
        tab_widget.setMovable(True)
        tab_text_edit.append("<b>PyQtDarkTheme</b>")
        tab_text_edit.append("Dark theme for PySide and PyQt.")
        tab_text_edit.append("This project is licensed under the MIT license.")
        tab_text_edit.append('<a href="https://pyqtdarktheme.readthedocs.io">PyQtDarkTheme Doc</a>')
        tab_text_edit.setWordWrapMode(QTextOption.WrapMode.NoWrap)

        tab_table.setModel(_TableModel())
        tab_table.setSortingEnabled(True)

        tab_list.addItems([f"Item {i+1}" for i in range(30)])

        tab_tree.setColumnCount(2)
        for i in range(5):
            item = QTreeWidgetItem([f"Item {i+1}" for _ in range(2)])
            for j in range(2):
                item.addChild(QTreeWidgetItem([f"Child Item {i+1}_{j+1}" for _ in range(2)]))
            tab_tree.insertTopLevelItem(i, item)

        tab_column_model = QStandardItemModel()
        tab_column_model.setHorizontalHeaderLabels(("Header 1", "Header 2"))
        for row in range(5):
            item = QStandardItem(f"Item {row+1}")
            for column in range(15):
                item.setChild(column, QStandardItem(f"Child Item {row+1}_{column+1}"))
            tab_column_model.setItem(row, item)
        tab_column.setModel(tab_column_model)

        def toggle_alternating(checked: bool):
            tab_table.setAlternatingRowColors(checked)
            tab_list.setAlternatingRowColors(checked)
            tab_tree.setAlternatingRowColors(checked)
            tab_column.setAlternatingRowColors(checked)

        btn_toggle_alternating.setCheckable(True)
        btn_toggle_alternating.toggled.connect(toggle_alternating)
        btn_toggle_alternating.setChecked(True)

        # layout
        tab_widget.addTab(tab_table, "Table")
        tab_widget.addTab(tab_text_edit, "Text Edit")
        tab_widget.addTab(tab_list, "List")
        tab_widget.addTab(tab_tree, "Tree")
        tab_widget.addTab(tab_column, "Column")

        v_layout_main = QVBoxLayout(self)
        v_layout_main.addWidget(tab_widget)
        v_layout_main.addWidget(btn_toggle_alternating)


class _Group4(QGroupBox):
    def __init__(self) -> None:
        super().__init__("QToolBox")
        # Widgets
        toolbox = QToolBox()
        h_slider, v_slider = QSlider(Qt.Orientation.Horizontal), QSlider(Qt.Orientation.Vertical)
        dial_ticks = QDial()
        progressbar = QProgressBar()
        lcd_number = QLCDNumber()

        # Setup widgets
        self.setCheckable(True)
        # If the slider value is 50, it is not clear which orientation is active.
        h_slider.setValue(30)
        v_slider.setValue(30)
        dial_ticks.setNotchesVisible(True)
        progressbar.setValue(50)
        lcd_number.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
        lcd_number.display(123)

        # Layout
        slider_component = QWidget()
        v_layout = QVBoxLayout(slider_component)
        v_layout.addWidget(h_slider)
        v_layout.addWidget(v_slider)
        toolbox.addItem(slider_component, "Slider")
        toolbox.addItem(dial_ticks, "Dial")
        toolbox.addItem(progressbar, "Progress Bar")
        toolbox.addItem(lcd_number, "LCD Number")
        QVBoxLayout(self).addWidget(toolbox)


class WidgetsUI:
    """The ui class of widgets window."""

    def setup_ui(self, win: QWidget) -> None:
        """Set up ui."""
        # Widgets
        h_splitter_1, h_splitter_2 = QSplitter(Qt.Orientation.Horizontal), QSplitter(
            Qt.Orientation.Horizontal
        )

        # Setup widgets
        h_splitter_1.setMinimumHeight(350)  # Fix bug layout crush

        # Layout
        h_splitter_1.addWidget(_Group1())
        h_splitter_1.addWidget(_Group2())
        h_splitter_2.addWidget(_Group3())
        h_splitter_2.addWidget(_Group4())

        widget_container = QWidget()
        v_layout = QVBoxLayout(widget_container)
        v_layout.addWidget(h_splitter_1)
        v_layout.addWidget(h_splitter_2)

        scroll_area = QScrollArea()
        scroll_area.setWidget(widget_container)

        v_main_layout = QVBoxLayout(win)
        v_main_layout.addWidget(scroll_area)
