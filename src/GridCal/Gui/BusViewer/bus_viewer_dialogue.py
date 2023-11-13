# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import sys
from PySide6 import QtWidgets

from typing import List, Union
from GridCal.Gui.BusViewer.gui import Ui_BusViewerWindow, QMainWindow
from GridCal.Gui.GridEditorWidget import BusBranchEditorWidget, generate_bus_branch_diagram
import GridCalEngine.Core.Devices as dev
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Core.Devices.Substation import Bus


class BusViewerWidget(QMainWindow):

    def __init__(self, circuit: MultiCircuit, root_bus: dev.Bus, name='', parent=None, view_toolbar=True,
                 default_bus_voltage: float = 10.0):
        """

        :param circuit:
        :param root_bus:
        :param parent:
        """
        QMainWindow.__init__(self, parent)
        self.ui = Ui_BusViewerWindow()
        self.ui.setupUi(self)

        self.name = name

        self.default_bus_voltage = default_bus_voltage

        self.root_bus = root_bus
        self.bus_id = self.root_bus.name + ' ' + self.root_bus.code

        self.setWindowTitle('Bus Viewer ' + self.bus_id)

        self.circuit = circuit

        # list of bus and branch indices displayed
        self.branch_idx = list()
        self.bus_idx = list()

        # create grid editor o
        self.grid_editor = BusBranchEditorWidget(circuit=self.circuit,
                                                 diagram=None,
                                                 default_bus_voltage=self.default_bus_voltage)

        # delete all widgets
        for i in reversed(range(self.ui.editorLayout.count())):
            self.ui.editorLayout.itemAt(i).widget().deleteLater()

        # add the widgets
        self.ui.editorLayout.addWidget(self.grid_editor)

        # create editor and show the root bus
        self.draw()

        # button clicks
        self.ui.drawButton.clicked.connect(self.draw)

        # toolbar clicks
        self.ui.actiondraw.triggered.connect(self.draw)
        self.ui.actionExpand_nodes.triggered.connect(self.expand_node_distances)
        self.ui.actionScrink_nodes.triggered.connect(self.shrink_node_distances)
        self.ui.actionAdjust_to_window_size.triggered.connect(self.center_nodes)

        self.ui.toolBar.setVisible(view_toolbar)

    @property
    def diagram(self) -> dev.BusBranchDiagram:
        """
        Get the diagram object
        :return: BusBranchDiagram
        """
        return self.grid_editor.diagram

    @diagram.setter
    def diagram(self, val: dev.BusBranchDiagram):
        """
        Set the diagram object
        :param val: BusBranchDiagram
        """
        self.grid_editor.diagram = val

    @staticmethod
    def msg(text: str, title: str = "Warning"):
        """
        Message box
        :param text: Text to display
        :param title: Name of the window
        """
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msg.setText(text)
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle(title)
        # msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        retval = msg.exec_()

    def auto_layout(self, sel: str):
        """

        :param sel: selection graph algorithm
        :return:
        """
        if self.grid_editor is not None:
            self.grid_editor.auto_layout(sel=sel)

    def expand_node_distances(self):
        """
        Move the nodes more separated
        """
        if self.grid_editor is not None:
            self.grid_editor.expand_node_distances()

    def shrink_node_distances(self):
        """
        Move the nodes closer
        """
        if self.grid_editor is not None:
            self.grid_editor.shrink_node_distances()

    def center_nodes(self, margin_factor: float = 0.1, buses: Union[None, List[Bus]] = None):
        """
        Center the nodes in the screen
        """
        if self.grid_editor is not None:
            self.grid_editor.center_nodes(margin_factor=margin_factor,
                                          buses=buses)

    def colour_results(self, **kwargs):
        """
        Colour the results
        :param kwargs:
        :return:
        """
        if self.grid_editor is not None:
            self.grid_editor.colour_results(**kwargs)

    def get_selection_api_objects(self):
        """
        Get a list of the API objects from the selection
        :return: List[EditableDevice]
        """
        return self.grid_editor.get_selection_api_objects()

    def new_editor(self):
        """
        Create new editor
        """
        self.grid_editor = BusBranchEditorWidget(circuit=self.circuit,
                                                 diagram=None,
                                                 default_bus_voltage=self.default_bus_voltage)

        # delete all widgets
        for i in reversed(range(self.ui.editorLayout.count())):
            self.ui.editorLayout.itemAt(i).widget().deleteLater()

        # add the widgets
        self.ui.editorLayout.addWidget(self.grid_editor)

    def draw(self):
        """
        Redraw
        :return:
        """

        self.new_editor()
        self.branch_idx = list()
        self.bus_idx = list()

        bus_dict = self.circuit.get_bus_index_dict()

        # get max expansion level
        max_level = self.ui.levelSpinBox.value()

        # get all Branches
        all_branches = self.circuit.get_branches()
        branch_dict = {b: i for i, b in enumerate(all_branches)}

        # sel bus label
        self.ui.busNameLabel.setText(self.bus_id)

        # create a pool of buses
        bus_pool = [(self.root_bus, 0)]  # store the bus objects and their level from the root

        buses = set()
        selected_branches = set()

        while len(bus_pool) > 0:

            # search the next bus
            bus, level = bus_pool.pop()

            self.bus_idx.append(bus_dict[bus])

            # add searched bus
            buses.add(bus)

            if level < max_level:

                for i, br in enumerate(all_branches):

                    if br.bus_from == bus:
                        bus_pool.append((br.bus_to, level + 1))
                        selected_branches.add(br)

                    elif br.bus_to == bus:
                        bus_pool.append((br.bus_from, level + 1))
                        selected_branches.add(br)

                    else:
                        pass

        # sort Branches
        lines = list()
        dc_lines = list()
        transformers2w = list()
        transformers3w = list()
        hvdc_lines = list()
        vsc_converters = list()
        upfc_devices = list()

        for obj in selected_branches:

            self.branch_idx.append(branch_dict[obj])

            if obj.device_type == DeviceType.LineDevice:
                lines.append(obj)

            elif obj.device_type == DeviceType.DCLineDevice:
                dc_lines.append(obj)

            elif obj.device_type == DeviceType.Transformer2WDevice:
                transformers2w.append(obj)

            elif obj.device_type == DeviceType.Transformer3WDevice:
                transformers3w.append(obj)

            elif obj.device_type == DeviceType.HVDCLineDevice:
                hvdc_lines.append(obj)

            elif obj.device_type == DeviceType.VscDevice:
                vsc_converters.append(obj)

            elif obj.device_type == DeviceType.UpfcDevice:
                upfc_devices.append(obj)

            elif obj.device_type == DeviceType.BranchDevice:
                # we need to convert it :D
                obj2 = dev.convert_branch(obj)
                lines.append(obj2)  # call this again, but this time it is not a Branch object
            else:
                raise Exception('Unrecognized branch type ' + obj.device_type.value)

        # Draw schematic subset
        diagram = generate_bus_branch_diagram(buses=list(buses),
                                              lines=lines,
                                              dc_lines=dc_lines,
                                              transformers2w=transformers2w,
                                              transformers3w=transformers3w,
                                              hvdc_lines=hvdc_lines,
                                              vsc_devices=vsc_converters,
                                              upfc_devices=upfc_devices,
                                              explode_factor=1.0,
                                              prog_func=None,
                                              text_func=print,
                                              name=self.root_bus.name + 'vecinity')

        self.grid_editor.set_data(self.circuit, diagram=diagram)

        self.center_nodes()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    circuit_ = MultiCircuit()
    circuit_.add_bus(dev.Bus('bus1'))
    window = BusViewerWidget(circuit=circuit_, root_bus=circuit_.buses[0])
    window.resize(int(1.61 * 700.0), 600)  # golden ratio
    window.show()
    sys.exit(app.exec())
