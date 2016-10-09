__author__ = 'Santiago Penate Vera'
"""
This class is the handler of the main gui of the ETF.
"""

import sys

try:
    from gui.main.gui import *
except:
    from GridCal_project.GridCal.GUI.MainGui.gui import *


class MainGUI(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)

        # Slots connection
        #QtCore.QObject.connect(self.ui.launchPowerFlowButton,QtCore.SIGNAL('clicked()'), self.launch_power_flow_study)

        #QtCore.QObject.connect(self.ui.launchShortCircuitButton, QtCore.SIGNAL('clicked()'), self.launch_short_circuit_study)

        self.ui.plotwidget.setTitle("Network graph")
        self.ui.plotwidget.canvas.set_graph_mode()
        # import random
        # randomNumbers = random.sample(range(0, 10), 10)
        # self.ui.plotwidget.canvas.ax.clear()
        # self.ui.plotwidget.canvas.ax.plot(randomNumbers)
        # self.ui.plotwidget.canvas.draw()

        self.draw_sample_graph()

    def draw_sample_graph(self):
        import networkx as nx
        g = nx.Graph()
        g.add_edge(1, 2)
        g.add_edge(1, 3)
        g.add_edge(3, 4)
        g.add_edge(3, 5)
        g.add_edge(2, 5)

        self.ui.plotwidget.canvas.ax.clear()
        nx.draw(g, ax=self.ui.plotwidget.canvas.ax)

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MainGUI()
    window.show()
    sys.exit(app.exec_())
