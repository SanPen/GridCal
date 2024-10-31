# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import zipfile
from typing import List, Union, Callable
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit


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
