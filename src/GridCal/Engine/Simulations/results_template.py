# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
import json
from typing import List

import numpy as np

from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable


class ResultsTemplate:

    def __init__(self, name='',
                 available_results: List[ResultTypes] = list(),
                 data_variables: List[str] = list()):
        """
        Results template class
        :param name: Name of the class
        :param available_results: list of stuff to represent the results
        :param data_variables: list of class variables to persist to disk
        """
        self.name = name
        self.available_results: List[ResultTypes] = available_results
        self.data_variables: List[str] = data_variables

    def consolidate_after_loading(self):
        pass

    def get_results_dict(self):
        data = dict()

        return data

    def get_arrays(self):
        return {var_name: getattr(self, var_name) for var_name in self.data_variables}

    def to_json(self, file_name):
        """
        Export as json
        :param file_name: File name
        """

        with open(file_name, "w") as output_file:
            json_str = json.dumps(self.get_results_dict())
            output_file.write(json_str)

    def apply_new_rates(self, rates):
        pass

    def apply_new_time_series_rates(self, rates):
        pass

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        pass
