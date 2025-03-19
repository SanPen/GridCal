from PySide6.QtWidgets import QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QPushButton, QVBoxLayout, QWidget
from PySide6.QtCore import Qt
import sys


def handle_item_changed(item, column):
    if item.parent() is None:  # Root item
        state = item.checkState(0)
        for i in range(item.childCount()):
            item.child(i).setCheckState(0, state)


class ObjectComparatorGUI(QMainWindow):
    def __init__(self, base_list, new_list):
        super().__init__()
        self.base_list = base_list
        self.new_list = new_list
        self.initUI()
        self.populate_tree()

    def initUI(self):
        self.setWindowTitle("Object List Comparator")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Property", "Base Value", "New Value", "Action"])
        self.tree.itemChanged.connect(handle_item_changed)
        layout.addWidget(self.tree)

        self.apply_button = QPushButton("Apply Selected Changes")
        self.apply_button.clicked.connect(self.apply_changes)
        layout.addWidget(self.apply_button)

        central_widget.setLayout(layout)

    def populate_tree(self):
        self.tree.clear()

        base_dict = {obj.id: obj for obj in self.base_list}
        new_dict = {obj.id: obj for obj in self.new_list}

        for obj_id in new_dict.keys() | base_dict.keys():
            base_obj = base_dict.get(obj_id)
            new_obj = new_dict.get(obj_id)

            if base_obj and new_obj:
                differences = self.compare_objects(base_obj, new_obj)
                if differences:
                    parent_item = QTreeWidgetItem(self.tree, [f"Object {obj_id}", "", "", "Modified"])
                    parent_item.setCheckState(0, Qt.CheckState.Unchecked)
                    parent_item.setBackground(0, Qt.GlobalColor.blue)
                    for prop, (base_val, new_val) in differences.items():
                        child_item = QTreeWidgetItem(parent_item, [prop, str(base_val), str(new_val), "Modified"])
                        child_item.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    continue

            elif base_obj:
                parent_item = QTreeWidgetItem(self.tree, [f"Object {obj_id}", "", "", "Removed"])
                parent_item.setCheckState(0, Qt.CheckState.Unchecked)
                parent_item.setBackground(0, Qt.GlobalColor.red)

            elif new_obj:
                parent_item = QTreeWidgetItem(self.tree, [f"Object {obj_id}", "", "", "Added"])
                parent_item.setCheckState(0, Qt.CheckState.Unchecked)
                parent_item.setBackground(0, Qt.GlobalColor.green)

    def compare_objects(self, base_obj, new_obj):
        differences = {}
        base_attrs = vars(base_obj)
        new_attrs = vars(new_obj)

        for attr in base_attrs.keys() | new_attrs.keys():
            base_val = base_attrs.get(attr, None)
            new_val = new_attrs.get(attr, None)
            if base_val != new_val:
                differences[attr] = (base_val, new_val)

        return differences

    def apply_changes(self):
        for i in range(self.tree.topLevelItemCount()):
            obj_item = self.tree.topLevelItem(i)
            obj_id_text = obj_item.text(0)
            if "Object" in obj_id_text:
                obj_id = int(obj_id_text.split(" ")[1])
            else:
                continue

            base_obj = next((obj for obj in self.base_list if obj.id == obj_id), None)
            new_obj = next((obj for obj in self.new_list if obj.id == obj_id), None)

            if not base_obj or not new_obj:
                continue

            for j in range(obj_item.childCount()):
                child_item = obj_item.child(j)
                if child_item.checkState(0) == Qt.CheckState.Checked:
                    prop = child_item.text(0)
                    new_val = child_item.text(2)
                    setattr(base_obj, prop, new_val)

        print("Changes applied to base list")
        self.populate_tree()


class ExampleObject:
    def __init__(self, obj_id, **attributes):
        self.id = obj_id
        for key, value in attributes.items():
            setattr(self, key, value)

    def __repr__(self):
        return f"Object({self.id}, {vars(self)})"


if __name__ == "__main__":

    base_list = [ExampleObject(1, name="A", value=10),
                 ExampleObject(2, name="B", value=20),
                 ExampleObject(4, name="C", value=50)]

    new_list = [ExampleObject(1, name="A", value=15),
                ExampleObject(2, name="B", value=20),
                ExampleObject(3, name="C", value=30)]

    app = QApplication(sys.argv)
    window = ObjectComparatorGUI(base_list, new_list)
    window.show()
    sys.exit(app.exec())