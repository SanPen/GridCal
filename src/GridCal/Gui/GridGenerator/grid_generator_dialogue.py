import sys
import numpy as np
from numpy.random import default_rng
import networkx as nx
from PySide6 import QtWidgets

from GridCal.Gui.GridGenerator.gui import Ui_MainWindow
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Utils.ThirdParty.SyntheticNetworks.rpgm_algo import RpgAlgorithm


class GridGeneratorGUI(QtWidgets.QDialog):

    def __init__(self, parent=None, ):
        """

        :param parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Grid Generator')

        self.g = RpgAlgorithm()
        self.circuit = MultiCircuit()
        self.applied = False

        self.ui.applyButton.clicked.connect(self.apply)
        self.ui.previewButton.clicked.connect(self.preview)

    def msg(self, text, title="Warning"):
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

    def fill_graph(self):
        """
        # set desired parameters and perform algorithm
        :return:
        """
        self.g = RpgAlgorithm()

        n = self.ui.nodes_spinBox.value()
        n0 = 10
        r = self.ui.ratio_SpinBox.value()
        if n0 >= n:
            n0 = n - 1

        self.g.set_params(n=n, n0=n0, r=r)
        self.g.initialise()
        self.g.grow()

    def preview(self):
        """

        :return:
        """
        self.fill_graph()
        G = nx.Graph(self.g.edges)
        pos = {i: (self.g.lat[i], self.g.lon[i]) for i in range(self.g.added_nodes)}

        self.ui.plotwidget.clear()
        nx.draw(G,
                ax=self.ui.plotwidget.get_axis(),
                pos=pos,
                with_labels=True,
                node_color='lightblue')
        self.ui.plotwidget.redraw()

    def apply(self):
        """
        Create graph, then the circuit and close
        :return: Nothing
        """
        self.fill_graph()

        self.circuit = MultiCircuit()

        explosion_factor = 10000.0

        # number of nodes
        n = self.g.added_nodes

        # assign the load and generation buses
        genbus = self.ui.generation_nodes_SpinBox.value()
        loadbus = self.ui.load_nodes_SpinBox.value()

        if (genbus + loadbus) > 100:
            s = genbus + loadbus
            genbus /= s
            loadbus /= s

        gen_buses_num = int(np.floor(n * genbus / 100))
        load_buses_num = int(np.floor(n * loadbus / 100))

        rng = default_rng()
        numbers = rng.choice(n, size=gen_buses_num + load_buses_num, replace=False)

        gen_buses = numbers[:gen_buses_num]
        load_buses = numbers[gen_buses_num:]

        pmax = self.ui.power_SpinBox.value()

        # generate buses
        bus_dict = dict()
        for i in range(n):
            bus = dev.Bus(name='Bus ' + str(i + 1),
                          xpos=self.g.lat[i] * explosion_factor,
                          ypos=-self.g.lon[i] * explosion_factor)

            bus_dict[i] = bus

            self.circuit.add_bus(bus)

        # generate loads
        factor = np.random.random(load_buses_num)
        factor /= factor.sum()
        pf = self.ui.power_factor_SpinBox.value()
        for k, i in enumerate(load_buses):
            bus = bus_dict[i]
            p = pmax * factor[k]
            q = p * pf
            load = dev.Load(name='Load@bus' + str(i + 1), P=p, Q=q)
            self.circuit.add_load(bus, load)

        # generate generators
        factor = np.random.random(gen_buses_num)
        factor /= factor.sum()
        for k, i in enumerate(gen_buses):
            bus = bus_dict[i]
            gen = dev.Generator(name='Generator@bus' + str(i + 1),
                                P=pmax * factor[k])
            self.circuit.add_generator(bus, gen)

        # generate lines
        r = self.ui.r_SpinBox.value()
        x = self.ui.x_SpinBox.value()
        b = self.ui.b_SpinBox.value()

        for f, t in self.g.edges:
            dx = (self.g.lat[f] - self.g.lat[t]) * explosion_factor
            dy = (self.g.lon[f] - self.g.lon[t]) * explosion_factor
            m = np.sqrt(dx * dx + dy * dy) / 10.0  # divided by 10 to have more meaningful values

            b1 = bus_dict[f]
            b2 = bus_dict[t]
            lne = dev.Line(bus_from=b1,
                           bus_to=b2,
                           name='Line ' + str(f) + '-' + str(t),
                           r=r * m,
                           x=x * m,
                           b=b * m,
                           length=m)
            self.circuit.add_line(lne)

        # quit
        self.applied = True
        self.close()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = GridGeneratorGUI()
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec())
