import sys
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from GridCal.Gui.GridEditorWidget import GridEditor
from GridCal.Engine.IO.file_handler import FileOpen


class AddObjectsThreaded(QThread):

    def __init__(self, editor: GridEditor, explode_factor=1.0):
        QThread.__init__(self)

        self.editor = editor

        self.explode_factor = explode_factor

    def run(self):
        """
        run the file open procedure
        """
        # clear all
        self.editor.diagramView.scene_.clear()

        # first create the buses
        for bus in self.editor.circuit.buses:
            bus.graphic_obj = self.editor.add_api_bus(bus, self.explode_factor)

        for branch in self.editor.circuit.branches:
            branch.graphic_obj = self.editor.add_api_branch(branch)

        # figure limits
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize

        # Align lines
        for bus in self.editor.circuit.buses:
            bus.graphic_obj.arrange_children()
            # get the item position
            x = bus.graphic_obj.pos().x()
            y = bus.graphic_obj.pos().y()

            # compute the boundaries of the grid
            max_x = max(max_x, x)
            min_x = min(min_x, x)
            max_y = max(max_y, y)
            min_y = min(min_y, y)

        # set the figure limits
        self.editor.set_limits(min_x, max_x, min_y, max_y)
        #  center the view
        self.editor.center_nodes()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    fname = r'C:\Users\PENVERSA\Documents\Git\GridCal\Grids_and_profiles\grids\1354 Pegase.xlsx'
    circuit = FileOpen(fname).open()

    view = GridEditor(circuit)
    view.resize(600, 400)
    view.show()

    thr = AddObjectsThreaded(editor=view)
    thr.start()

    sys.exit(app.exec_())
