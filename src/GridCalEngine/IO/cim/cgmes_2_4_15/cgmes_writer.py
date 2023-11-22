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
import zipfile
from typing import List, Union, Callable
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_circuit import CgmesCircuit


def write_cgmes(filename_zip: str, model: CgmesCircuit, profiles: List[cgmesProfile],
                text_func: Union[Callable, None] = None,
                progress_func: Union[Callable, None] = None):
    """
    Write a CGMES model to a zip file
    :param filename_zip: name of the zip file
    :param model: CgmesCircuit
    :param profiles: list of profiles to export
    :param text_func: text callback function (optional)
    :param progress_func: progress callback function (optional)
    """
    # get the cgmes XML per profile
    data = model.get_model_xml(profiles)

    n = len(data)

    # open zip file for writing
    with zipfile.ZipFile(filename_zip, 'w', zipfile.ZIP_DEFLATED) as f_zip_ptr:

        # for each CGMES profile of the list
        i = 0
        for profile, txt in data.items():
            filename = 'model_{}.xml'.format(profile.value)

            if text_func is not None:
                text_func('Saving {}'.format(filename))

            f_zip_ptr.writestr(filename, txt)  # save the buffer to the zip file

            if progress_func is not None:
                progress_func((i + 1) / n * 100)
            i += 1

    if text_func is not None:
        text_func('done! see: {}'.format(filename_zip))
