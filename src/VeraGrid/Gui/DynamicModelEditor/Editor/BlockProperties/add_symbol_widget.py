# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'add_symbol_widget.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit,
    QSizePolicy, QSpacerItem, QStackedWidget, QVBoxLayout,
    QWidget)

class Ui_AddSymbolDialog(object):
    def setupUi(self, AddSymbolDialog):
        if not AddSymbolDialog.objectName():
            AddSymbolDialog.setObjectName(u"AddSymbolDialog")
        AddSymbolDialog.resize(640, 420)
        AddSymbolDialog.setMinimumSize(QSize(560, 360))
        AddSymbolDialog.setModal(True)
        self.verticalLayout = QVBoxLayout(AddSymbolDialog)
        self.verticalLayout.setSpacing(10)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(12, 12, 12, 12)
        self.dialog_heading = QLabel(AddSymbolDialog)
        self.dialog_heading.setObjectName(u"dialog_heading")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        self.dialog_heading.setFont(font)

        self.verticalLayout.addWidget(self.dialog_heading)

        self.dialog_description = QLabel(AddSymbolDialog)
        self.dialog_description.setObjectName(u"dialog_description")
        self.dialog_description.setWordWrap(True)

        self.verticalLayout.addWidget(self.dialog_description)

        self.heading_separator = QFrame(AddSymbolDialog)
        self.heading_separator.setObjectName(u"heading_separator")
        self.heading_separator.setFrameShape(QFrame.Shape.HLine)
        self.heading_separator.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout.addWidget(self.heading_separator)

        self.common_form_layout = QFormLayout()
        self.common_form_layout.setObjectName(u"common_form_layout")
        self.common_form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.common_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)
        self.common_form_layout.setHorizontalSpacing(12)
        self.common_form_layout.setVerticalSpacing(8)
        self.new_symbol_owner_label = QLabel(AddSymbolDialog)
        self.new_symbol_owner_label.setObjectName(u"new_symbol_owner_label")

        self.common_form_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.new_symbol_owner_label)

        self.new_symbol_owner = QComboBox(AddSymbolDialog)
        self.new_symbol_owner.setObjectName(u"new_symbol_owner")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.new_symbol_owner.sizePolicy().hasHeightForWidth())
        self.new_symbol_owner.setSizePolicy(sizePolicy)

        self.common_form_layout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.new_symbol_owner)

        self.new_symbol_name_label = QLabel(AddSymbolDialog)
        self.new_symbol_name_label.setObjectName(u"new_symbol_name_label")

        self.common_form_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.new_symbol_name_label)

        self.new_symbol_name = QLineEdit(AddSymbolDialog)
        self.new_symbol_name.setObjectName(u"new_symbol_name")
        sizePolicy.setHeightForWidth(self.new_symbol_name.sizePolicy().hasHeightForWidth())
        self.new_symbol_name.setSizePolicy(sizePolicy)
        self.new_symbol_name.setClearButtonEnabled(True)

        self.common_form_layout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.new_symbol_name)

        self.new_symbol_kind_label = QLabel(AddSymbolDialog)
        self.new_symbol_kind_label.setObjectName(u"new_symbol_kind_label")

        self.common_form_layout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.new_symbol_kind_label)

        self.new_symbol_kind = QComboBox(AddSymbolDialog)
        self.new_symbol_kind.setObjectName(u"new_symbol_kind")
        sizePolicy.setHeightForWidth(self.new_symbol_kind.sizePolicy().hasHeightForWidth())
        self.new_symbol_kind.setSizePolicy(sizePolicy)

        self.common_form_layout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.new_symbol_kind)

        self.new_symbol_kind_description = QLabel(AddSymbolDialog)
        self.new_symbol_kind_description.setObjectName(u"new_symbol_kind_description")
        self.new_symbol_kind_description.setWordWrap(True)

        self.common_form_layout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.new_symbol_kind_description)


        self.verticalLayout.addLayout(self.common_form_layout)

        self.symbol_options_stack = QStackedWidget(AddSymbolDialog)
        self.symbol_options_stack.setObjectName(u"symbol_options_stack")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.symbol_options_stack.sizePolicy().hasHeightForWidth())
        self.symbol_options_stack.setSizePolicy(sizePolicy1)
        self.variable_page = QWidget()
        self.variable_page.setObjectName(u"variable_page")
        self.variable_form_layout = QFormLayout(self.variable_page)
        self.variable_form_layout.setObjectName(u"variable_form_layout")
        self.variable_form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.variable_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)
        self.variable_form_layout.setHorizontalSpacing(12)
        self.variable_form_layout.setVerticalSpacing(8)
        self.variable_options_label = QLabel(self.variable_page)
        self.variable_options_label.setObjectName(u"variable_options_label")

        self.variable_form_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.variable_options_label)

        self.new_variable_options = QWidget(self.variable_page)
        self.new_variable_options.setObjectName(u"new_variable_options")
        self.new_variable_options_layout = QHBoxLayout(self.new_variable_options)
        self.new_variable_options_layout.setSpacing(14)
        self.new_variable_options_layout.setObjectName(u"new_variable_options_layout")
        self.new_variable_options_layout.setContentsMargins(0, 0, 0, 0)
        self.new_symbol_exported = QCheckBox(self.new_variable_options)
        self.new_symbol_exported.setObjectName(u"new_symbol_exported")

        self.new_variable_options_layout.addWidget(self.new_symbol_exported)

        self.new_state_derivative = QCheckBox(self.new_variable_options)
        self.new_state_derivative.setObjectName(u"new_state_derivative")

        self.new_variable_options_layout.addWidget(self.new_state_derivative)

        self.new_variable_options_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.new_variable_options_layout.addItem(self.new_variable_options_spacer)


        self.variable_form_layout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.new_variable_options)

        self.new_external_reference_label = QLabel(self.variable_page)
        self.new_external_reference_label.setObjectName(u"new_external_reference_label")

        self.variable_form_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.new_external_reference_label)

        self.new_external_reference = QComboBox(self.variable_page)
        self.new_external_reference.setObjectName(u"new_external_reference")
        sizePolicy.setHeightForWidth(self.new_external_reference.sizePolicy().hasHeightForWidth())
        self.new_external_reference.setSizePolicy(sizePolicy)
        self.new_external_reference.setEditable(True)
        self.new_external_reference.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.new_external_reference.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.new_external_reference.setMinimumContentsLength(24)
        self.new_external_reference.setMaxVisibleItems(16)

        self.variable_form_layout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.new_external_reference)

        self.symbol_options_stack.addWidget(self.variable_page)
        self.parameter_page = QWidget()
        self.parameter_page.setObjectName(u"parameter_page")
        self.parameter_form_layout = QFormLayout(self.parameter_page)
        self.parameter_form_layout.setObjectName(u"parameter_form_layout")
        self.parameter_form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.parameter_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)
        self.parameter_form_layout.setHorizontalSpacing(12)
        self.parameter_form_layout.setVerticalSpacing(8)
        self.new_parameter_value_label = QLabel(self.parameter_page)
        self.new_parameter_value_label.setObjectName(u"new_parameter_value_label")

        self.parameter_form_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.new_parameter_value_label)

        self.new_parameter_value = QDoubleSpinBox(self.parameter_page)
        self.new_parameter_value.setObjectName(u"new_parameter_value")
        sizePolicy.setHeightForWidth(self.new_parameter_value.sizePolicy().hasHeightForWidth())
        self.new_parameter_value.setSizePolicy(sizePolicy)
        self.new_parameter_value.setDecimals(12)
        self.new_parameter_value.setMinimum(-10000000000000000159028911097599180468360808563945281389781327557747838772170381060813469985856815104.000000000000000)
        self.new_parameter_value.setMaximum(10000000000000000159028911097599180468360808563945281389781327557747838772170381060813469985856815104.000000000000000)

        self.parameter_form_layout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.new_parameter_value)

        self.new_static_reference_label = QLabel(self.parameter_page)
        self.new_static_reference_label.setObjectName(u"new_static_reference_label")

        self.parameter_form_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.new_static_reference_label)

        self.new_static_reference = QComboBox(self.parameter_page)
        self.new_static_reference.setObjectName(u"new_static_reference")
        sizePolicy.setHeightForWidth(self.new_static_reference.sizePolicy().hasHeightForWidth())
        self.new_static_reference.setSizePolicy(sizePolicy)
        self.new_static_reference.setEditable(True)
        self.new_static_reference.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.new_static_reference.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.new_static_reference.setMinimumContentsLength(24)
        self.new_static_reference.setMaxVisibleItems(16)

        self.parameter_form_layout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.new_static_reference)

        self.symbol_options_stack.addWidget(self.parameter_page)
        self.retained_mode_page = QWidget()
        self.retained_mode_page.setObjectName(u"retained_mode_page")
        self.retained_mode_layout = QVBoxLayout(self.retained_mode_page)
        self.retained_mode_layout.setObjectName(u"retained_mode_layout")
        self.retained_mode_description = QLabel(self.retained_mode_page)
        self.retained_mode_description.setObjectName(u"retained_mode_description")
        self.retained_mode_description.setWordWrap(True)

        self.retained_mode_layout.addWidget(self.retained_mode_description)

        self.retained_mode_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.retained_mode_layout.addItem(self.retained_mode_spacer)

        self.symbol_options_stack.addWidget(self.retained_mode_page)

        self.verticalLayout.addWidget(self.symbol_options_stack)

        self.vertical_spacer = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.vertical_spacer)

        self.add_symbol_status_label = QLabel(AddSymbolDialog)
        self.add_symbol_status_label.setObjectName(u"add_symbol_status_label")
        self.add_symbol_status_label.setVisible(False)
        self.add_symbol_status_label.setWordWrap(True)
        self.add_symbol_status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.verticalLayout.addWidget(self.add_symbol_status_label)

        self.button_box = QDialogButtonBox(AddSymbolDialog)
        self.button_box.setObjectName(u"button_box")
        self.button_box.setOrientation(Qt.Orientation.Horizontal)
        self.button_box.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout.addWidget(self.button_box)


        self.retranslateUi(AddSymbolDialog)
        self.button_box.rejected.connect(AddSymbolDialog.reject)

        self.symbol_options_stack.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(AddSymbolDialog)
    # setupUi

    def retranslateUi(self, AddSymbolDialog):
        AddSymbolDialog.setWindowTitle(QCoreApplication.translate("AddSymbolDialog", u"Add block property", None))
        self.dialog_heading.setText(QCoreApplication.translate("AddSymbolDialog", u"Add block property", None))
        self.dialog_description.setText(QCoreApplication.translate("AddSymbolDialog", u"Define a new property for the selected block.", None))
        self.new_symbol_owner_label.setText(QCoreApplication.translate("AddSymbolDialog", u"Owner block", None))
        self.new_symbol_name_label.setText(QCoreApplication.translate("AddSymbolDialog", u"Name", None))
        self.new_symbol_name.setPlaceholderText(QCoreApplication.translate("AddSymbolDialog", u"Enter a valid symbol name", None))
        self.new_symbol_kind_label.setText(QCoreApplication.translate("AddSymbolDialog", u"Variable type", None))
        self.new_symbol_kind_description.setText(QCoreApplication.translate("AddSymbolDialog", u"Choose how this symbol participates in the dynamic model.", None))
        self.variable_options_label.setText(QCoreApplication.translate("AddSymbolDialog", u"Options", None))
        self.new_symbol_exported.setText(QCoreApplication.translate("AddSymbolDialog", u"Expose as output", None))
        self.new_state_derivative.setText(QCoreApplication.translate("AddSymbolDialog", u"Create derivative variable", None))
#if QT_CONFIG(tooltip)
        self.new_external_reference_label.setToolTip(QCoreApplication.translate("AddSymbolDialog", u"Power-flow variable used to initialize this dynamic variable.", None))
#endif // QT_CONFIG(tooltip)
        self.new_external_reference_label.setText(QCoreApplication.translate("AddSymbolDialog", u"Power-flow initialization source", None))
        self.new_parameter_value_label.setText(QCoreApplication.translate("AddSymbolDialog", u"Local initial value", None))
        self.new_static_reference_label.setText(QCoreApplication.translate("AddSymbolDialog", u"Device initial value", None))
        self.retained_mode_description.setText(QCoreApplication.translate("AddSymbolDialog", u"Retained modes preserve discrete state between simulation steps.", None))
        self.add_symbol_status_label.setText("")
    # retranslateUi
