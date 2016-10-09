from PyQt4.QtGui import *
from PyQt4 import QtGui

from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4 import NavigationToolbar2QT as Navigationtoolbar
from matplotlib.figure import Figure

from numpy import take

# from matplotlib import pyplot as plt
# plt.ion()


class MplCanvas(FigureCanvas):

    def __init__(self):

        self.press = None
        self.cur_xlim = None
        self.cur_ylim = None
        self.x0 = None
        self.y0 = None
        self.x1 = None
        self.y1 = None
        self.xpress = None
        self.ypress = None

        self.fig = Figure()
        self.ax = self.fig.add_subplot(111, axisbg='white')

        FigureCanvas.__init__(self, self.fig)
        FigureCanvas.setSizePolicy(self, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

        scale = 1.2
        f = self.zoom_factory(self.ax, base_scale=scale)
        # p = self.pan_factory(self.ax)

    def setTitle(self, text):
        """
        Sets the figure title
        """
        self.fig.suptitle(text)

    def set_graph_mode(self):
        """
        Sets the borders to nicely display graphs
        """
        self.fig.subplots_adjust(left=0, bottom=0, right=1, top=0.9, wspace=0, hspace=0)

    def zoom_factory(self, ax, base_scale=1.2):
        """
        Mouse zoom handler
        """
        def zoom(event):
            cur_xlim = ax.get_xlim()
            cur_ylim = ax.get_ylim()

            xdata = event.xdata # get event x location
            ydata = event.ydata # get event y location

            if event.button == 'down':
                # deal with zoom in
                scale_factor = 1 / base_scale
            elif event.button == 'up':
                # deal with zoom out
                scale_factor = base_scale
            else:
                # deal with something that should never happen
                scale_factor = 1
                print(event.button)

            new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
            new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor

            relx = (cur_xlim[1] - xdata)/(cur_xlim[1] - cur_xlim[0])
            rely = (cur_ylim[1] - ydata)/(cur_ylim[1] - cur_ylim[0])

            ax.set_xlim([xdata - new_width * (1-relx), xdata + new_width * (relx)])
            ax.set_ylim([ydata - new_height * (1-rely), ydata + new_height * (rely)])
            ax.figure.canvas.draw()

        fig = ax.get_figure() # get the figure of interest
        fig.canvas.mpl_connect('scroll_event', zoom)

        return zoom

    def pan_factory(self, ax):
        """
        Mouse pan handler
        """
        def onPress(event):
            if event.inaxes != ax:
                return
            self.cur_xlim = ax.get_xlim()
            self.cur_ylim = ax.get_ylim()
            self.press = self.x0, self.y0, event.xdata, event.ydata
            self.x0, self.y0, self.xpress, self.ypress = self.press

        def onRelease(event):
            self.press = None
            ax.figure.canvas.draw()

        def onMotion(event):
            if self.press is None:
                return
            if event.inaxes != ax:
                return
            dx = event.xdata - self.xpress
            dy = event.ydata - self.ypress
            self.cur_xlim -= dx
            self.cur_ylim -= dy
            ax.set_xlim(self.cur_xlim)
            ax.set_ylim(self.cur_ylim)

            ax.figure.canvas.draw()

        fig = ax.get_figure()  # get the figure of interest

        # attach the call back
        fig.canvas.mpl_connect('button_press_event',onPress)
        fig.canvas.mpl_connect('button_release_event',onRelease)
        fig.canvas.mpl_connect('motion_notify_event',onMotion)

        # return the function
        return onMotion


class MatplotlibWidget(QtGui.QWidget):

    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)

        self.frame = QWidget()
        self.canvas = MplCanvas()
        self.canvas.setParent(self.frame)
        self.mpltoolbar = Navigationtoolbar(self.canvas, self.frame)
        self.vbl = QtGui.QVBoxLayout()
        self.vbl.addWidget(self.canvas)
        self.vbl.addWidget(self.mpltoolbar)

        self.setLayout(self.vbl)

        self.mpltoolbar.toggleViewAction()

    def setTitle(self, text):
        """
        Sets the figure title
        """
        self.canvas.setTitle(text)

    def get_axis(self):
        return self.canvas.ax

    def get_figure(self):
        return self.canvas.fig

    def clear(self):
        self.canvas.ax.clear()

    def redraw(self):
        self.canvas.ax.figure.canvas.draw()

    def plot(self, x, y, title='', xlabel='', ylabel=''):
        self.setTitle(title)
        self.canvas.ax.plot(x, y)
        self.redraw()



