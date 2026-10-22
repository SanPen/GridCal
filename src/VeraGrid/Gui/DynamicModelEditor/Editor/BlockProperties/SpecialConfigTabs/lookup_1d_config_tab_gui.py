# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'lookup_1d_config_tab.ui'
##
## Created by: Qt User Interface Compiler version 6.11.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDoubleSpinBox, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QSpacerItem, QSpinBox, QSplitter, QTableView,
    QVBoxLayout, QWidget)

from VeraGrid.Gui.PlotDialogue.qt_chart_widget import GraphsWidget
from VeraGrid.Gui.Icons.icons_rc import *

class Ui_Lookup1DConfigTab(object):
    def setupUi(self, Lookup1DConfigTab):
        if not Lookup1DConfigTab.objectName():
            Lookup1DConfigTab.setObjectName(u"Lookup1DConfigTab")
        Lookup1DConfigTab.resize(900, 600)
        self.main_layout = QVBoxLayout(Lookup1DConfigTab)
        self.main_layout.setObjectName(u"main_layout")
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.function_generator_group_box = QGroupBox(Lookup1DConfigTab)
        self.function_generator_group_box.setObjectName(u"function_generator_group_box")
        self.function_generator_group_box.setMaximumSize(QSize(16777215, 115))
        self.function_generator_layout = QGridLayout(self.function_generator_group_box)
        self.function_generator_layout.setObjectName(u"function_generator_layout")
        self.function_expression_label = QLabel(self.function_generator_group_box)
        self.function_expression_label.setObjectName(u"function_expression_label")

        self.function_generator_layout.addWidget(self.function_expression_label, 0, 0, 1, 1)

        self.function_expression_line_edit = QLineEdit(self.function_generator_group_box)
        self.function_expression_line_edit.setObjectName(u"function_expression_line_edit")

        self.function_generator_layout.addWidget(self.function_expression_line_edit, 0, 1, 1, 5)

        self.generate_function_button = QPushButton(self.function_generator_group_box)
        self.generate_function_button.setObjectName(u"generate_function_button")

        self.function_generator_layout.addWidget(self.generate_function_button, 0, 6, 1, 1)

        self.function_x_minimum_label = QLabel(self.function_generator_group_box)
        self.function_x_minimum_label.setObjectName(u"function_x_minimum_label")

        self.function_generator_layout.addWidget(self.function_x_minimum_label, 1, 0, 1, 1)

        self.function_x_minimum_spin_box = QDoubleSpinBox(self.function_generator_group_box)
        self.function_x_minimum_spin_box.setObjectName(u"function_x_minimum_spin_box")
        self.function_x_minimum_spin_box.setDecimals(12)
        self.function_x_minimum_spin_box.setMinimum(-10000000000000000159028911097599180468360808563945281389781327557747838772170381060813469985856815104.000000000000000)
        self.function_x_minimum_spin_box.setMaximum(10000000000000000159028911097599180468360808563945281389781327557747838772170381060813469985856815104.000000000000000)
        self.function_x_minimum_spin_box.setKeyboardTracking(False)

        self.function_generator_layout.addWidget(self.function_x_minimum_spin_box, 1, 1, 1, 1)

        self.function_x_maximum_label = QLabel(self.function_generator_group_box)
        self.function_x_maximum_label.setObjectName(u"function_x_maximum_label")

        self.function_generator_layout.addWidget(self.function_x_maximum_label, 1, 2, 1, 1)

        self.function_x_maximum_spin_box = QDoubleSpinBox(self.function_generator_group_box)
        self.function_x_maximum_spin_box.setObjectName(u"function_x_maximum_spin_box")
        self.function_x_maximum_spin_box.setDecimals(12)
        self.function_x_maximum_spin_box.setMinimum(-10000000000000000159028911097599180468360808563945281389781327557747838772170381060813469985856815104.000000000000000)
        self.function_x_maximum_spin_box.setMaximum(10000000000000000159028911097599180468360808563945281389781327557747838772170381060813469985856815104.000000000000000)
        self.function_x_maximum_spin_box.setValue(1.000000000000000)
        self.function_x_maximum_spin_box.setKeyboardTracking(False)

        self.function_generator_layout.addWidget(self.function_x_maximum_spin_box, 1, 3, 1, 1)

        self.function_point_count_label = QLabel(self.function_generator_group_box)
        self.function_point_count_label.setObjectName(u"function_point_count_label")

        self.function_generator_layout.addWidget(self.function_point_count_label, 1, 4, 1, 1)

        self.function_point_count_spin_box = QSpinBox(self.function_generator_group_box)
        self.function_point_count_spin_box.setObjectName(u"function_point_count_spin_box")
        self.function_point_count_spin_box.setMinimum(2)
        self.function_point_count_spin_box.setMaximum(10000)
        self.function_point_count_spin_box.setValue(21)
        self.function_point_count_spin_box.setKeyboardTracking(False)

        self.function_generator_layout.addWidget(self.function_point_count_spin_box, 1, 5, 1, 1)

        self.function_generator_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.function_generator_layout.addItem(self.function_generator_spacer, 1, 6, 1, 1)

        self.function_error_label = QLabel(self.function_generator_group_box)
        self.function_error_label.setObjectName(u"function_error_label")
        self.function_error_label.setWordWrap(True)

        self.function_generator_layout.addWidget(self.function_error_label, 2, 0, 1, 7)


        self.main_layout.addWidget(self.function_generator_group_box)

        self.content_splitter = QSplitter(Lookup1DConfigTab)
        self.content_splitter.setObjectName(u"content_splitter")
        self.content_splitter.setOrientation(Qt.Orientation.Horizontal)
        self.table_frame = QFrame(self.content_splitter)
        self.table_frame.setObjectName(u"table_frame")
        self.table_frame.setMinimumSize(QSize(280, 0))
        self.table_layout = QVBoxLayout(self.table_frame)
        self.table_layout.setObjectName(u"table_layout")
        self.table_layout.setContentsMargins(0, 0, 0, 0)
        self.points_table = QTableView(self.table_frame)
        self.points_table.setObjectName(u"points_table")
        self.points_table.setAlternatingRowColors(True)
        self.points_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.points_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)

        self.table_layout.addWidget(self.points_table)

        self.table_buttons_frame = QFrame(self.table_frame)
        self.table_buttons_frame.setObjectName(u"table_buttons_frame")
        self.table_buttons_frame.setMaximumSize(QSize(16777215, 40))
        self.table_buttons_layout = QHBoxLayout(self.table_buttons_frame)
        self.table_buttons_layout.setObjectName(u"table_buttons_layout")
        self.table_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.add_row_button = QPushButton(self.table_buttons_frame)
        self.add_row_button.setObjectName(u"add_row_button")
        self.add_row_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        icon = QIcon()
        icon.addFile(u":/Icons/icons/plus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.add_row_button.setIcon(icon)

        self.table_buttons_layout.addWidget(self.add_row_button)

        self.remove_rows_button = QPushButton(self.table_buttons_frame)
        self.remove_rows_button.setObjectName(u"remove_rows_button")
        self.remove_rows_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/minus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.remove_rows_button.setIcon(icon1)

        self.table_buttons_layout.addWidget(self.remove_rows_button)

        self.sort_button = QPushButton(self.table_buttons_frame)
        self.sort_button.setObjectName(u"sort_button")
        self.sort_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.table_buttons_layout.addWidget(self.sort_button)

        self.table_buttons_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.table_buttons_layout.addItem(self.table_buttons_spacer)


        self.table_layout.addWidget(self.table_buttons_frame)

        self.content_splitter.addWidget(self.table_frame)
        self.plot_frame = QFrame(self.content_splitter)
        self.plot_frame.setObjectName(u"plot_frame")
        self.plot_layout = QVBoxLayout(self.plot_frame)
        self.plot_layout.setObjectName(u"plot_layout")
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        self.plotter = GraphsWidget(self.plot_frame)
        self.plotter.setObjectName(u"plotter")

        self.plot_layout.addWidget(self.plotter)

        self.content_splitter.addWidget(self.plot_frame)

        self.main_layout.addWidget(self.content_splitter)


        self.retranslateUi(Lookup1DConfigTab)

        QMetaObject.connectSlotsByName(Lookup1DConfigTab)
    # setupUi

    def retranslateUi(self, Lookup1DConfigTab):
        self.function_generator_group_box.setTitle(QCoreApplication.translate("Lookup1DConfigTab", u"Generate points from f(x)", None))
        self.function_expression_label.setText(QCoreApplication.translate("Lookup1DConfigTab", u"f(x) =", None))
#if QT_CONFIG(tooltip)
        self.function_expression_line_edit.setToolTip(QCoreApplication.translate("Lookup1DConfigTab", u"Expression using x, pi, e, and supported symbolic functions; for example sin(pi*x) or x**2", None))
#endif // QT_CONFIG(tooltip)
        self.function_expression_line_edit.setText(QCoreApplication.translate("Lookup1DConfigTab", u"x", None))
        self.function_expression_line_edit.setPlaceholderText(QCoreApplication.translate("Lookup1DConfigTab", u"Example: sin(x)", None))
#if QT_CONFIG(tooltip)
        self.generate_function_button.setToolTip(QCoreApplication.translate("Lookup1DConfigTab", u"Replace the table with evenly spaced samples of f(x)", None))
#endif // QT_CONFIG(tooltip)
        self.generate_function_button.setText(QCoreApplication.translate("Lookup1DConfigTab", u"Generate", None))
        self.function_x_minimum_label.setText(QCoreApplication.translate("Lookup1DConfigTab", u"x min", None))
        self.function_x_maximum_label.setText(QCoreApplication.translate("Lookup1DConfigTab", u"x max", None))
        self.function_point_count_label.setText(QCoreApplication.translate("Lookup1DConfigTab", u"Points", None))
        self.function_error_label.setText("")
#if QT_CONFIG(tooltip)
        self.add_row_button.setToolTip(QCoreApplication.translate("Lookup1DConfigTab", u"Add point", None))
#endif // QT_CONFIG(tooltip)
        self.add_row_button.setText("")
#if QT_CONFIG(tooltip)
        self.remove_rows_button.setToolTip(QCoreApplication.translate("Lookup1DConfigTab", u"Remove selected points", None))
#endif // QT_CONFIG(tooltip)
        self.remove_rows_button.setText("")
#if QT_CONFIG(tooltip)
        self.sort_button.setToolTip(QCoreApplication.translate("Lookup1DConfigTab", u"Sort points by x", None))
#endif // QT_CONFIG(tooltip)
        self.sort_button.setText(QCoreApplication.translate("Lookup1DConfigTab", u"Sort by x", None))
        pass
    # retranslateUi
