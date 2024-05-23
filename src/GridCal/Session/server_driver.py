# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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

import time
import requests
import asyncio
import websockets
import numpy as np
import json
from typing import Callable, Dict, Any, Union
from PySide6.QtCore import QThread, Signal
from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.gridcal.pack_unpack import gather_model_as_jsons_for_communication
from GridCalEngine.Devices.multi_circuit import MultiCircuit


class CustomJsonizer(json.JSONEncoder):
    """
    Class to serialize json while catching unserializable data like np._bool
    """

    def default(self, obj):
        """
        Override the default
        :param obj:
        :return:
        """
        return super().encode(bool(obj)) if isinstance(obj, np.bool_) else super().default(obj)


async def try_send(ws, chunk: str) -> bool:
    """
    Send a chunk of data to the websocket server
    :param ws:
    :param chunk: text chunk
    :return: success?
    """
    n_retry = 0
    while n_retry < 10:
        try:
            await ws.send(chunk.encode(encoding='utf-8'))
            return True
        except websockets.exceptions.ConnectionClosedError as e:
            n_retry += 1

    return False


def upload_progress_monitor(encoder, read, total):
    # Your progress monitoring logic here
    print(f"Progress: {read}/{total} bytes")


async def send_json_data(json_data: Dict[str, Union[str, Dict[str, Dict[str, str]]]], endpoint_url: str):
    """
    Send a file along with instructions about the file
    :param json_data: Json with te model
    :param endpoint_url: Web socket URL to connect to
    """

    response = requests.post(endpoint_url, json=json_data, stream=True)

    # Print server response
    print(response.json())


class ServerDriver(QThread):
    """
    Server driver
    """
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    sync_event = Signal()
    items_processed_event = Signal()

    def __init__(self, url: str, port: int, pwd: str, sleep_time: int = 2, status_func: Callable[[str], None] = None):
        """
        Constructor
        :param url: Server URL
        :param port: Server port
        :param pwd: Server password
        :param sleep_time: Sleep time (s)
        :param status_func: a text function pointer
        """
        QThread.__init__(self)

        self.url = url
        self.port = port
        self.pwd = pwd
        self.sleep_time = sleep_time
        self.status_func: Callable[[str], None] = status_func
        self.__running__ = False

        self.logger = Logger()

        self.__cancel__ = False
        self.__pause__ = False

    def set_values(self, url: str, port: int, pwd: str, sleep_time: int = 2, status_func: Callable[[str], None] = None):
        """
        Set the values
        :param url: Server URL
        :param port: Server port
        :param pwd: Server password
        :param sleep_time: Sleep time (s)
        :param status_func: a text function pointer
        """
        self.url = url
        self.port = port
        self.pwd = pwd
        self.sleep_time = sleep_time
        self.status_func: Callable[[str], None] = status_func
        self.__running__ = False
        self.logger = Logger()

    def is_running(self) -> bool:
        """
        Check if the server is running
        :return:
        """
        return self.__running__

    def server_connect(self) -> bool:
        """
        Try connecting to the server
        :return: ok?
        """
        # Make a GET request to the root endpoint
        try:
            response = requests.get(f"http://{self.url}:{self.port}/",
                                    headers={
                                        "API-Key": self.pwd
                                    },
                                    timeout=2)

            # Check if the request was successful
            if response.status_code == 200:
                # Print the response body
                # print("Response Body:", response.json())
                return True
            else:
                # Print error message
                self.logger.add_error(msg=f"Response error", value=response.text)
                return False
        except ConnectionError as e:
            self.logger.add_error(msg=f"Connection error", value=str(e))
            return False
        except Exception as e:
            self.logger.add_error(msg=f"General exception error", value=str(e))
            return False

    def report_status(self, txt: str):
        """

        :param txt:
        :return:
        """
        if self.status_func is not None:
            self.status_func(txt)

    def send_data(self, circuit: MultiCircuit, instructions_json: Dict[str, Any]) -> None:
        """
        
        :param circuit: 
        :param instructions_json: 
        :return: 
        """
        # websocket_url = f"ws://{self.url}:{self.port}/process_file"
        websocket_url = f"http://{self.url}:{self.port}/upload"

        if self.is_running():
            model_data = gather_model_as_jsons_for_communication(circuit=circuit,
                                                                 instructions_json=instructions_json)

            asyncio.get_event_loop().run_until_complete(send_json_data(json_data=model_data,
                                                                       endpoint_url=websocket_url))

    def run(self) -> None:
        """
        run the file save procedure
        """
        self.__cancel__ = False
        self.__pause__ = False

        self.report_status("Trying to connect")
        ok = self.server_connect()

        if ok:
            while not self.__cancel__:

                if not self.__pause__:
                    self.report_status("Sync" if ok else "Server not responding")
                    self.__running__ = True

                    # sleep
                    time.sleep(self.sleep_time)

                else:
                    self.report_status("Sync paused" if ok else "Server not responding")
                    self.__running__ = False

                    # sleep 1 second to catch other events
                    time.sleep(self.sleep_time)

                # check if alive
                ok = self.server_connect()
        else:
            # bad connection
            self.report_status("Could not connect")
            self.__running__ = False
            self.done_signal.emit()
            return None

        self.report_status("Sync stop")
        self.__running__ = False
        self.done_signal.emit()

    def cancel(self) -> None:
        """
        Cancel the sync checking
        """
        self.__running__ = False
        self.__cancel__ = True

    def pause(self):
        """
        Pause the sync checking
        """
        self.__pause__ = True

    def resume(self):
        """
        Resume the sync checking
        """
        self.__pause__ = False

    def process_issues(self):
        """
        Process all the issues
        :return:
        """

        self.items_processed_event.emit()
