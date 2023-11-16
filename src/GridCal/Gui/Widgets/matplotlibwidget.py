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

from PySide6 import QtWidgets
import matplotlib

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as Navigationtoolbar
from matplotlib.figure import Figure

from matplotlib import pyplot as plt
plt.style.use('fivethirtyeight')


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
        self.zoom_x_limits = None
        self.zoom_y_limits = None

        self.fig = Figure()
        try:
            self.ax = self.fig.add_subplot(111, facecolor='white')
        except Exception as ex:
            self.ax = self.fig.add_subplot(111, axisbg='white')

        FigureCanvas.__init__(self, self.fig)
        FigureCanvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

        scale = 1.2
        f = self.zoom_factory(self.ax, base_scale=scale)
        # p = self.pan_factory(self.ax)

        self.dragged = None
        self.element_dragged = None
        self.pick_pos = (0, 0)
        self.is_point = False
        self.index = None

        # Connect events and callbacks
        # self.fig.canvas.mpl_connect("pick_event", self.on_pick_event)
        # self.fig.canvas.mpl_connect("button_release_event", self.on_release_event)

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

            xdata = event.xdata  # get event x location
            ydata = event.ydata  # get event y location

            if event.button == 'down':
                # deal with zoom in
                scale_factor = 1 / base_scale
            elif event.button == 'up':
                # deal with zoom out
                scale_factor = base_scale
            else:
                # deal with something that should never happen
                scale_factor = 1

            new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
            new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor

            relx = (cur_xlim[1] - xdata)/(cur_xlim[1] - cur_xlim[0])
            rely = (cur_ylim[1] - ydata)/(cur_ylim[1] - cur_ylim[0])

            self.zoom_x_limits = [xdata - new_width * (1-relx), xdata + new_width * relx]
            self.zoom_y_limits = [ydata - new_height * (1-rely), ydata + new_height * rely]

            ax.set_xlim(self.zoom_x_limits )
            ax.set_ylim(self.zoom_y_limits)
            ax.figure.canvas.draw()

        fig = ax.get_figure()  # get the figure of interest
        fig.canvas.mpl_connect('scroll_event', zoom)

        return zoom

    def rec_zoom(self):
        self.zoom_x_limits = self.ax.get_xlim()
        self.zoom_y_limits = self.ax.get_ylim()

    def set_last_zoom(self):
        if self.zoom_x_limits is not None:
            self.ax.set_xlim(self.zoom_x_limits )
            self.ax.set_ylim(self.zoom_y_limits)

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
        fig.canvas.mpl_connect('button_press_event', onPress)
        fig.canvas.mpl_connect('button_release_event', onRelease)
        fig.canvas.mpl_connect('motion_notify_event', onMotion)

        # return the function
        return onMotion


class MatplotlibWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)

        self.frame = QtWidgets.QWidget()
        self.canvas = MplCanvas()
        self.canvas.setParent(self.frame)
        self.mpltoolbar = Navigationtoolbar(self.canvas, self.frame)
        self.vbl = QtWidgets.QVBoxLayout()
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

    def clear(self, force=False):
        """
        Clear the interface
        Args:
            force: Remove the object and create a new one (brute force)

        Returns:

        """
        if force:
            self.canvas.fig.clear()
            self.canvas.ax = self.canvas.fig.add_subplot(111)
            # self.canvas.ax.clear()
            # self.canvas = MplCanvas()
        else:
            self.canvas.ax.clear()
        self.redraw()

    def redraw(self):
        """
        Redraw the interface
        Returns:

        """
        self.canvas.ax.figure.canvas.draw()

    def plot(self, x, y, title='', xlabel='', ylabel=''):
        """
        Plot series
        Args:
            x: X values
            y: Y values
            title: Title
            xlabel: Label for X
            ylabel: Label for Y

        Returns:

        """
        self.setTitle(title)
        self.canvas.ax.plot(x, y)
        self.canvas.ax.set_xlabel(xlabel)
        self.canvas.ax.set_ylabel(ylabel)
        self.redraw()



