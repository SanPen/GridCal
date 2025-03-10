# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import os
from typing import Dict, Union, Any
from uuid import uuid4, getnode
import numpy as np

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import (SimulationTypes, JobStatus)
from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.gridcal.pack_unpack import gather_model_as_jsons
from GridCalEngine.IO.file_system import get_create_gridcal_folder
from GridCalEngine.Simulations.driver_handler import create_driver
from GridCalEngine.Simulations.types import DRIVER_OBJECTS, RESULTS_OBJECTS

try:
    import requests

    REQUESTS_AVAILABLE = True
except AttributeError as e:
    print(f"GridCalEngine/IO/gridcal/remote.py: Error with requests -> {e}")
    REQUESTS_AVAILABLE = False


class RemoteInstruction:
    """
    Remote instruction class
    """

    def __init__(self,
                 operation: Union[None, SimulationTypes] = None,
                 data: Union[None, Dict[str, Dict[str, str]]] = None):
        """
        RemoteInstruction
        :param operation: SimulationTypes
        :param data: data previously generated with get_data()
        """
        if data is None:
            self.operation: Union[None, SimulationTypes] = operation

            # get the proper function to find the user depending on the platform
            if 'USERNAME' in os.environ:
                self.user = os.environ["USERNAME"]
            elif 'USER' in os.environ:
                self.user = os.environ["USER"]
            else:
                self.user = ''

            self.mac = str(getnode())

        else:
            self.operation: Union[None, SimulationTypes] = None
            self.user = ""
            self.mac = ""
            self.parse_data(data)

    def get_data(self) -> Dict[str, str]:
        """

        :return:
        """
        return {
            'operation': self.operation.value if self.operation is not None else None,
            "user": self.user,
            "mac": self.mac
        }

    def parse_data(self, data: Dict[str, Dict[str, str]]):
        """

        :param data:
        :return:
        """
        self.operation = SimulationTypes(data['operation'])
        self.user = data['user']


class RemoteJob:
    """
    Remote job class
    """

    def __init__(self,
                 grid: Union[None, MultiCircuit] = None,
                 instruction: Union[None, RemoteInstruction] = None,
                 data: Union[None, Dict[str, Any]] = None):
        """

        :param grid:
        :param instruction:
        """
        self.id_tag = uuid4().hex

        self.__grid: MultiCircuit = grid
        self.grid_name = grid.name if grid is not None else ""

        self.instruction: RemoteInstruction = instruction

        self.status: JobStatus = JobStatus.Waiting

        self.progress: str = ""

        if data is not None:
            self.parse_data(data)

    def cancel(self):
        """

        :return:
        """
        self.status = JobStatus.Cancelled

    def get_data(self) -> dict:
        """

        :return:
        """
        return {
            "id_tag": self.id_tag,
            "grid_name": self.grid_name,
            "instruction": self.instruction.get_data(),
            "status": self.status.value,
            "progress": self.progress
        }

    def parse_data(self, data: Dict[str, Any]):
        """

        :param data:
        :return:
        """
        self.id_tag = data['id_tag']
        self.grid_name = data['grid_name']
        self.progress = data['progress']
        self.status = JobStatus(data['status'])
        self.instruction = RemoteInstruction(data=data['instruction'])


def get_certificate_path() -> str:
    """
    Get a path to the certificates
    :return:
    """
    return os.path.join(get_create_gridcal_folder(), "server_cert.pem")


def get_certificate(base_url: str, certificate_path: str, pwd: str, logger: Logger = Logger()) -> bool:
    """
    Try connecting to the server
    :return: ok?
    """
    # Make a GET request to the root endpoint
    if REQUESTS_AVAILABLE:
        try:
            response = requests.get(f"{base_url}/get_cert",
                                    headers={"API-Key": pwd},
                                    verify=False,
                                    timeout=2)

            # Save the certificate to a file

            with open(certificate_path, "wb") as cert_file:
                cert_file.write(response.content)

            # Check if the request was successful
            if response.status_code == 200:
                # Print the response body
                # print("Response Body:", response.json())
                # self.data_model.parse_data(data=response.json())
                return True
            else:
                # Print error message
                logger.add_error(msg=f"Response error", value=response.text)
                return False
        except ConnectionError as e:
            logger.add_error(msg=f"Connection error", value=str(e))
            return False
        except Exception as e:
            logger.add_error(msg=f"General exception error", value=str(e))
            return False
    else:
        logger.add_error(msg=f"requests not available due to an error on import")
        return False


def gather_model_as_jsons_for_communication(circuit: MultiCircuit,
                                            instruction: RemoteInstruction) -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    Create a Json with the same information expected for loading with `parse_gridcal_data`
    :param circuit: MultiCircuit
    :param instruction: RemoteInstruction
    :return: JSON like data
    """

    data = {
        'name': circuit.name,
        'baseMVA': circuit.Sbase,
        'Comments': circuit.comments,
        'ModelVersion': circuit.model_version,
        'UserName': circuit.user_name,
        'sender_id': uuid4().hex,
        'instruction': instruction.get_data(),
        'model_data': gather_model_as_jsons(circuit=circuit),
        'diagrams': []
    }
    return data


def send_json_data(json_data: Dict[str, Union[str, Dict[str, Dict[str, str]]]],
                         endpoint_url: str,
                         certificate: str) -> Any:
    """
    Send a file along with instructions about the file
    :param json_data: Json with te model
    :param endpoint_url: Web socket URL to connect to
    :param certificate: SSL certificate path
    :return service response
    """

    if REQUESTS_AVAILABLE:
        response = requests.post(
            url=endpoint_url,
            json=json_data,
            stream=True,
            verify=certificate
        )

        # return server response
        return response.json()
    else:
        print(f"Requests not available due to an error on import")


def run_job(grid: MultiCircuit, job: RemoteJob) -> DRIVER_OBJECTS | None:
    """
    Function to run a job, this is a simple function
    :param grid: MultiCircuit
    :param job: RemoteJob
    :return: DRIVER_OBJECTS or None
    """

    driver: DRIVER_OBJECTS | None = create_driver(
        grid=grid,
        driver_tpe=job.instruction.operation,
        time_indices=None
    )

    if driver is not None:
        job.status = JobStatus.Running
        driver.run()
        job.status = JobStatus.Done

    return driver
