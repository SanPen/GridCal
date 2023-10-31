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

from typing import Dict
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager
from PySide6.QtGui import QFont


class ConsoleWidget(RichJupyterWidget):
    """
    Convenience class for a live IPython console widget.
    We can replace the standard banner using the customBanner argument
    """

    def __init__(self, customBanner: str = None, *args: object, **kwargs: object) -> None:
        """
        
        :param customBanner: 
        :param args: 
        :param kwargs: 
        """
        RichJupyterWidget.__init__(self, *args, **kwargs)

        if customBanner is not None:
            self.banner = customBanner

        self.font_size = 6
        self.gui_completion = 'droplist'
        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=False)
        self.kernel_manager.kernel.gui = 'qt'
        self.kernel_client = kernel_client = self._kernel_manager.client()
        kernel_client.start_channels()

        # Set the font for the console
        font = QFont("Consolas", 10, QFont.Normal)  # Adjust family, size, and weight as needed
        self.setFont(font)

        def stop():
            """
            
            :return: 
            """
            kernel_client.stop_channels()
            self.kernel_manager.shutdown_kernel()
            # guisupport.get_app_qt().exit()

        self.exit_requested.connect(stop)

    def set_dark_theme(self):
        """
        Set the dark theme
        """

        self.setStyleSheet("""
                            QWidget {
                                font-family: Consolas;
                                font-size: 10pt;
                                font-weight: normal;
                            }
                            background-color: #222;
                            color: #fff;
                            """)

    def set_light_theme(self):
        """
        Set the light theme
        """

        self.setStyleSheet("""
                            QWidget {
                                font-family: Consolas;
                                font-size: 10pt;
                                font-weight: normal;
                            }
                            background-color: #fff; /* White background */
                            color: #333; /* Dark text color */
                            """)

    def push_vars(self, variableDict: Dict[str, object]) -> None:
        """
        Given a dictionary containing name / value pairs, push those variables
        to the IPython console widget
        """
        self.kernel_manager.kernel.shell.push(variableDict)

    def clear(self):
        """
        Clears the terminal
        """
        self._control.clear()

        # self.kernel_manager

    def print_text(self, text):
        """
        Prints some plain text to the console
        """
        self._append_plain_text(text)

    def execute_command(self, command):
        """
        Execute a command in the frame of the console widget
        """
        self.execute(source=command, hidden=False, interactive=True)
