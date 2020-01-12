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

from io import StringIO
import os
from random import randint, seed
import pandas as pd
import zipfile
from typing import List, Dict

from GridCal.Engine.IO.generic_io_functions import parse_config_df


def save_data_frames_to_zip(dfs: Dict[str, pd.DataFrame], filename_zip="file.zip",
                            text_func=None, progress_func=None):
    """
    Save a list of DataFrames to a zip file without saving to disk the csv files
    :param dfs: dictionary of pandas dataFrames {name: DataFrame}
    :param filename_zip: file name where to save all
    :param text_func: pointer to function that prints the names
    :param progress_func: pointer to function that prints the progress 0~100
    """

    n = len(dfs)

    # open zip file for writing
    with zipfile.ZipFile(filename_zip, 'w', zipfile.ZIP_DEFLATED) as myzip:

        # for each DataFrame and name...
        i = 0
        for name, df in dfs.items():

            # compose the csv file name
            filename = name + ".csv"

            if text_func is not None:
                text_func('Flushing ' + name + ' to ' + filename_zip + '...')

            if progress_func is not None:
                progress_func((i + 1) / n * 100)

            # open a string buffer
            with StringIO() as buffer:

                # save the DataFrame to the buffer
                df.to_csv(buffer, index=False)

                # save the buffer to the zip file
                myzip.writestr(filename, buffer.getvalue())

            i += 1

    print('All DataFrames flushed to zip!')


def open_data_frames_from_zip(file_name_zip, text_func=None, progress_func=None):
    """
    Open the csv files from a zip file
    :param file_name_zip: name of the zip file
    :param text_func: pointer to function that prints the names
    :param progress_func: pointer to function that prints the progress 0~100
    :return: list of DataFrames
    """

    # open the zip file
    try:
        zip_file_pointer = zipfile.ZipFile(file_name_zip)
    except zipfile.BadZipFile:
        return None

    names = zip_file_pointer.namelist()

    n = len(names)
    data = dict()

    # for each file in the zip file...
    for i, file_name in enumerate(names):

        # split the file name into name and extension
        name, extension = os.path.splitext(file_name)

        if text_func is not None:
            text_func('Unpacking ' + name + ' from ' + file_name_zip)

        if progress_func is not None:
            progress_func((i + 1) / n * 100)

        if extension == '.csv':

            # create a buffer to read the file
            file_pointer = zip_file_pointer.open(file_name)

            if name.lower() == "config":
                try:
                    df = pd.read_csv(file_pointer, index_col=0)
                    data = parse_config_df(df, data)
                except EOFError:
                    return None
                except zipfile.BadZipFile:
                    return None
            else:
                # make pandas read the file
                try:
                    df = pd.read_csv(file_pointer)
                except EOFError:
                    return None
                except zipfile.BadZipFile:
                    return None

            # append the DataFrame to the list
            data[name] = df

    return data


if __name__ == '__main__':

    # Generate some random values to put in the csv file.
    seed(42)  # Causes random numbers always be the same for testing.
    data = [[randint(0, 100) for _ in range(10)] for _ in range(10)]
    df1 = pd.DataFrame(data)

    seed(44)  # Causes random numbers always be the same for testing.
    data = [[randint(0, 100) for _ in range(10)] for _ in range(10)]
    df2 = pd.DataFrame(data)

    # save
    save_data_frames_to_zip({'Data1': df1, 'Data2': df2}, 'some_file.gridcal')

    # read and print
    df_list = open_data_frames_from_zip(file_name_zip='some_file.gridcal')

    for name, df in df_list.items():
        print()
        print(name)
        print(df)
