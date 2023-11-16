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
from io import StringIO, TextIOWrapper, BytesIO
from typing import List
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_circuit import CgmesCircuit


def write_cgmes(filename_zip: str, model: CgmesCircuit, profiles: List[cgmesProfile]):

    # get the cgmes XML per profile
    data = model.get_model_xml(profiles)

    # open zip file for writing
    with zipfile.ZipFile(filename_zip, 'w', zipfile.ZIP_DEFLATED) as f_zip_ptr:

        # for each CGMES profile of the list
        for profile, txt in data.items():
            filename = 'model_{}.xml'.format(profile.value)
            print('Saving', filename)
            f_zip_ptr.writestr(filename, txt)  # save the buffer to the zip file

    print("done! see", filename_zip)