# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


import pandas as pd
import zipfile


def open_data_frame_from_zip(file_name_zip, file_name):
    """
    Open the csv files from a zip file
    :param file_name_zip: name of the zip file
    :param file_name: name of the file within the zip file
    :return: DataFrame
    """

    # open the zip file
    try:
        zip_file_pointer = zipfile.ZipFile(file_name_zip)
    except zipfile.BadZipFile:
        return None

    # create a buffer to read the file
    file_pointer = zip_file_pointer.open(file_name)

    # make pandas read the file
    try:
        df = pd.read_csv(file_pointer, index_col=0)
        return df
    except EOFError:
        return None
    except zipfile.BadZipFile:
        return None


    