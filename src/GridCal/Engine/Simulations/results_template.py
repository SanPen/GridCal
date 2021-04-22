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
from typing import List
from GridCal.Engine.Simulations.result_types import ResultTypes


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
