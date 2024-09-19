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
from __future__ import annotations

import os
from typing import List, Callable, Union, TYPE_CHECKING
from io import StringIO
import zipfile
from GridCalEngine.basic_structures import Logger

if TYPE_CHECKING:
    from GridCalEngine.Simulations.types import DRIVER_OBJECTS, RESULTS_OBJECTS


def export_results(results_list: List[RESULTS_OBJECTS],
                   file_name: str,
                   text_func: Union[Callable[[str], None], None] = None,
                   progress_func: Union[Callable[[float], None], None] = None,
                   logger: Logger = Logger()):
    """
    Constructor
    :param results_list: list of GridCal simulation results
    :param file_name: name of the file where to save (.zip)
    :param text_func: text function
    :param progress_func: progress function
    :param logger: logging object
    """

    # try:
    path, fname = os.path.split(file_name)

    if text_func is not None:
        text_func('Flushing ' + fname + ' into ' + fname + '...')

    # open zip file for writing
    try:
        with zipfile.ZipFile(file_name, 'w', zipfile.ZIP_DEFLATED) as myzip:

            n = len(results_list)

            for k, results in enumerate(results_list):

                # deactivate plotting
                results.deactivate_plotting()

                if progress_func is not None:
                    progress_func((k + 1) / n * 100.0)

                if isinstance(results.available_results, dict):
                    available_res = [e for tpe, lst in results.available_results.items() for e in lst]
                else:
                    available_res = results.available_results

                for available_result in available_res:

                    # ge the result type definition
                    result_name = str(available_result.value)

                    if text_func is not None:
                        text_func('flushing ' + results.name + ' ' + result_name)

                    # save the DataFrame to the buffer
                    mdl = results.mdl(result_type=available_result)

                    if mdl is not None:
                        with StringIO() as buffer:
                            filename = results.name + ' ' + result_name + '.csv'
                            try:
                                mdl.save_to_csv(buffer)
                                myzip.writestr(filename, buffer.getvalue())
                            except ValueError:
                                logger.add_error('Value error', filename)
                    else:
                        logger.add_info('No results for ' + results.name + ' - ' + result_name)

                # reactivate plotting
                results.activate_plotting()

    except PermissionError:
        logger.add('Permission error.\nDo you have the file open?')

    # post events
    if text_func is not None:
        text_func('Done!')


def export_drivers(drivers_list: List[DRIVER_OBJECTS],
                   file_name: str,
                   text_func: Union[Callable[[str], None], None] = None,
                   progress_func: Union[Callable[[float], None], None] = None,
                   logger: Logger = Logger()):
    """
    Constructor
    :param drivers_list: list of GridCal simulation drivers
    :param file_name: name of the file where to save (.zip)
    :param text_func: text function
    :param progress_func: progress function
    :param logger: logging object
    """

    results_list = [drv.results for drv in drivers_list]

    export_results(results_list=results_list,
                   file_name=file_name,
                   text_func=text_func,
                   progress_func=progress_func,
                   logger=logger)
