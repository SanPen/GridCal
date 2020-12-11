import os
import string
import sys
from random import randint
from enum import Enum
import numpy as np
from numpy.random import default_rng
import networkx as nx
from PySide2.QtWidgets import *

from GridCal.Gui.BusViewer.gui import *
from GridCal.Gui.GridEditorWidget import *
from GridCal.Engine.Devices import *
from GridCal.Engine.Core.multi_circuit import MultiCircuit


class BusViewerGUI(QMainWindow):

    def __init__(self, circuit: MultiCircuit, root_bus: Bus, parent=None, ):
        """

        :param circuit:
        :param root_bus:
        :param parent:
        """
        QMainWindow.__init__(self, parent)
        self.ui = Ui_BusViewerWindow()
        self.ui.setupUi(self)

        self.root_bus = root_bus
        self.bus_id = self.root_bus.name + ' ' + self.root_bus.code

        self.setWindowTitle('Bus Viewer ' + self.bus_id)

        self.circuit = circuit

        # list of bus and branch indices displayed
        self.branch_idx = list()
        self.bus_idx = list()

        # create grid editor o
        self.grid_editor = None

        # create editor and show the root bus
        self.draw()

        # button clicks
        self.ui.drawButton.clicked.connect(self.draw)

        # toolbar clicks
        self.ui.actiondraw.triggered.connect(self.draw)
        self.ui.actionExpand_nodes.triggered.connect(self.bigger_nodes)
        self.ui.actionScrink_nodes.triggered.connect(self.smaller_nodes)
        self.ui.actionAdjust_to_window_size.triggered.connect(self.center_nodes)

    def msg(self, text, title="Warning"):
        """
        Message box
        :param text: Text to display
        :param title: Name of the window
        """
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText(text)
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle(title)
        # msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()

    def bigger_nodes(self):
        """
        Move the nodes more separated
        """
        if self.grid_editor is not None:
            self.grid_editor.bigger_nodes()

    def smaller_nodes(self):
        """
        Move the nodes closer
        """
        if self.grid_editor is not None:
            self.grid_editor.smaller_nodes()

    def center_nodes(self):
        """
        Center the nodes in the screen
        """
        if self.grid_editor is not None:
            # self.grid_editor.align_schematic()
            self.grid_editor.center_nodes()

    def new_editor(self):
        """
        Create new editor
        """
        self.grid_editor = GridEditor(self.circuit)

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

        # get all branches
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

        # sort branches
        lines = list()
        dc_lines = list()
        transformers2w = list()
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

            elif obj.device_type == DeviceType.HVDCLineDevice:
                hvdc_lines.append(obj)

            elif obj.device_type == DeviceType.VscDevice:
                vsc_converters.append(obj)

            elif obj.device_type == DeviceType.UpfcDevice:
                upfc_devices.append(obj)

            elif obj.device_type == DeviceType.BranchDevice:
                # we need to convert it :D
                obj2 = convert_branch(obj)
                lines.append(obj2)  # call this again, but this time it is not a Branch object
            else:
                raise Exception('Unrecognized branch type ' + obj.device_type.value)

        # Draw schematic subset
        self.grid_editor.add_elements_to_schematic(buses=list(buses),
                                                   lines=lines,
                                                   dc_lines=dc_lines,
                                                   transformers2w=transformers2w,
                                                   hvdc_lines=hvdc_lines,
                                                   vsc_devices=vsc_converters,
                                                   upfc_devices=upfc_devices,
                                                   explode_factor=1.0,
                                                   prog_func=None,
                                                   text_func=print)
        self.grid_editor.center_nodes()


if __name__ == "__main__":

    app = QApplication(sys.argv)
    circuit_ = MultiCircuit()
    circuit_.add_bus(Bus('bus1'))
    window = BusViewerGUI(circuit=circuit_, root_bus=circuit_.buses[0])
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

