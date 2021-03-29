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


    