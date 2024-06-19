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
import os
from typing import Dict, Union, Any
from uuid import uuid4, getnode
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import (SimulationTypes, JobStatus)
from GridCalEngine.IO.gridcal.pack_unpack import gather_model_as_jsons
from GridCalEngine.IO.gridcal.zip_interface import save_results_in_zip


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

    def get_data(self):
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


