from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QDialogButtonBox
)
from PySide6.QtCore import Qt


class ComboBoxDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ComboBox Dialog")

        # Create layout
        main_layout = QVBoxLayout()

        # Create horizontal layout for labels and comboboxes
        combo_layout = QHBoxLayout()

        # Create labels and comboboxes
        label1 = QLabel("Label 1")
        self.combo_box1 = QComboBox()
        self.combo_box1.addItems(["Option 1", "Option 2", "Option 3"])

        label2 = QLabel("Label 2")
        self.combo_box2 = QComboBox()
        self.combo_box2.addItems(["Option A", "Option B", "Option C"])

        # Create vertical layout for first label and combobox
        vbox1 = QVBoxLayout()
        vbox1.addWidget(label1)
        vbox1.addWidget(self.combo_box1)

        # Create vertical layout for second label and combobox
        vbox2 = QVBoxLayout()
        vbox2.addWidget(label2)
        vbox2.addWidget(self.combo_box2)

        # Add vertical layouts to horizontal layout
        combo_layout.addLayout(vbox1)
        combo_layout.addLayout(vbox2)

        # Add horizontal layout to main layout
        main_layout.addLayout(combo_layout)

        # Create and add buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # Align the button box to the bottom-right
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(button_box)

        # Add button layout to main layout
        main_layout.addLayout(button_layout)

        # Set main layout
        self.setLayout(main_layout)

    def accept(self):
        selected_option1 = self.combo_box1.currentText()
        selected_option2 = self.combo_box2.currentText()
        print(f"Accepted: {selected_option1}, {selected_option2}")
        super().accept()

    def reject(self):
        print("Canceled")
        super().reject()


if __name__ == "__main__":
    app = QApplication([])

    dialog = ComboBoxDialog()
    if dialog.exec() == QDialog.Accepted:
        print("Dialog accepted")
    else:
        print("Dialog canceled")

    app.exec()
