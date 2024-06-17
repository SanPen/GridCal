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
from typing import Callable, Dict, Union, List, Any
from PySide6.QtCore import QThread, Signal
from PySide6 import QtCore
from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.gridcal.remote import gather_model_as_jsons_for_communication, RemoteInstruction, RemoteJob
from GridCalEngine.Devices.multi_circuit import MultiCircuit


async def send_json_data(json_data: Dict[str, Union[str, Dict[str, Dict[str, str]]]], endpoint_url: str):
    """
    Send a file along with instructions about the file
    :param json_data: Json with te model
    :param endpoint_url: Web socket URL to connect to
    :return service response
    """

    response = requests.post(endpoint_url, json=json_data, stream=True)

    # return server response
    return response.json()


class JobsModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with a pandas data frame
    """

    def __init__(self):
        """
        """
        QtCore.QAbstractTableModel.__init__(self)
        self.jobs: List[RemoteJob] = list()
        self.headers = ["Job id", "User", "Grid name", "Job Type", "Status", "Progress"]

    def clear(self):
        """
        Clear jobs
        """
        self.jobs.clear()

    def parse_data(self, data: List[Dict[str, Union[str, Dict[str, Any]]]]):
        """
        Parse the data from the server
        :param data:
        :return:
        """
        self.jobs.clear()
        self.beginResetModel()
        for job_data in data:
            job = RemoteJob(data=job_data)
            self.jobs.append(job)

        self.endResetModel()

    def flags(self, index: QtCore.QModelIndex):
        """

        :param index:
        :return:
        """
        return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def rowCount(self, parent: Union[QtCore.QModelIndex, QtCore.QPersistentModelIndex] = ...) -> int:
        """

        :param parent:
        :return:
        """
        return len(self.jobs)

    def columnCount(self, parent: Union[QtCore.QModelIndex, QtCore.QPersistentModelIndex] = ...) -> int:
        """

        :param parent:
        :return:
        """
        return len(self.headers)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
        """

        :param index:
        :param role:
        :return:
        """
        if index.isValid() and role == QtCore.Qt.ItemDataRole.DisplayRole:

            job = self.jobs[index.row()]

            # "id_tag", "Grid name", "Job Type", "Status"
            if index.column() == 0:
                return job.id_tag
            elif index.column() == 1:
                return job.instruction.user
            elif index.column() == 2:
                return job.grid_name
            elif index.column() == 3:
                return job.instruction.operation.value
            elif index.column() == 4:
                return job.status.value
            elif index.column() == 4:
                return job.progress
            else:
                return ""
        return None

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param index:
        :param value:
        :param role:
        :return:
        """
        return None

    def headerData(self,
                   section: int,
                   orientation: QtCore.Qt.Orientation,
                   role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param section:
        :param orientation:
        :param role:
        :return:
        """
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return self.headers[section]
            # elif orientation == QtCore.Qt.Orientation.Vertical:
            #     return self.jobs[section].id_tag

        return None


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

        self.data_model = JobsModel()

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

    def report_status(self, txt: str):
        """

        :param txt:
        :return:
        """
        if self.status_func is not None:
            self.status_func(txt)

    def base_url(self):
        """
        Base URL of the service
        :return:
        """
        return f"http://{self.url}:{self.port}"

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
            response = requests.get(f"{self.base_url()}/",
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

    def get_jobs(self) -> bool:
        """
        Try connecting to the server
        :return: ok?
        """
        # Make a GET request to the root endpoint
        try:
            response = requests.get(f"{self.base_url()}/jobs_list",
                                    headers={
                                        "API-Key": self.pwd
                                    },
                                    timeout=2)

            # Check if the request was successful
            if response.status_code == 200:
                # Print the response body
                # print("Response Body:", response.json())
                self.data_model.parse_data(data=response.json())
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

    def send_data(self, circuit: MultiCircuit, instruction: RemoteInstruction) -> None:
        """
        
        :param circuit: 
        :param instruction:
        :return: 
        """
        # websocket_url = f"ws://{self.url}:{self.port}/process_file"
        websocket_url = f"{self.base_url()}/upload"

        if self.is_running():
            model_data = gather_model_as_jsons_for_communication(circuit=circuit, instruction=instruction)

            response = asyncio.get_event_loop().run_until_complete(send_json_data(json_data=model_data,
                                                                                  endpoint_url=websocket_url))

            self.get_jobs()

    def delete_job(self, job_id: str, api_key: str) -> dict:
        """
        Delete a specific job by ID using the REST API.

        :param job_id: The ID of the job to delete
        :param api_key: The API key for authentication
        :return: Response from the server
        """
        url = f"{self.base_url()}/jobs/{job_id}"
        headers = {
            "accept": "application/json",
            "API-Key": api_key
        }
        response = requests.delete(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

        self.get_jobs()

    def download_results(self, job_id: str, api_key: str, local_filename: str):
        """

        :param job_id:
        :param api_key:
        :param local_filename:
        :return:
        """
        url = f"{self.base_url()}/download_results/{job_id}"

        headers = {
            "accept": "application/json",
            "API-Key": api_key
        }

        print("Started download...")

        chunk_size = 1024 * 1024  # 1 MB
        sent = 0
        # Stream the download to avoid loading the entire file into memory
        with requests.get(url, headers=headers, stream=True) as response:

            if response.status_code == 200:

                with open(local_filename, "wb") as file:
                    for chunk in response.iter_content(chunk_size=chunk_size):  # 1MB chunks
                        if chunk:  # Filter out keep-alive chunks
                            file.write(chunk)
                            sent += chunk_size
                            self.progress_text.emit(f"Sent {sent / chunk_size} MBytes")

            else:
                print(response.status_code, response.text)

        self.progress_text.emit(f"Downloaded file saved as {local_filename}")
        print(f"Downloaded file saved as {local_filename}")

    def cancel_job(self, job_id: str, api_key: str) -> dict:
        """
        Cancel a specific job by ID using the REST API.

        :param job_id: The ID of the job to cancel
        :param api_key: The API key for authentication
        :return: Response from the server
        """
        url = f"{self.base_url()}/jobs/{job_id}/cancel"
        headers = {
            "accept": "application/json",
            "API-Key": api_key
        }
        response = requests.post(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

        self.get_jobs()

    def run(self) -> None:
        """
        run the file save procedure
        """
        self.__cancel__ = False
        self.__pause__ = False

        self.report_status("Trying to connect")
        ok = self.server_connect()

        if ok:

            # get the running jobs
            self.get_jobs()

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

        self.data_model.clear()
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
