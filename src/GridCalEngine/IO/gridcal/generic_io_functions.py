# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import json


def parse_config_df(df, data=None):
    if data is None:
        data = dict()

    if 'BaseMVA' in df.index:
        data["baseMVA"] = float(df.at['BaseMVA', 'Value'])
    elif 'baseMVA' in df.index:
        data["baseMVA"] = float(df.at['baseMVA', 'Value'])
    else:
        data["baseMVA"] = 100

    if 'version' in df.index:
        data["version"] = float(df.at['version', 'Value'])

    if 'name' in df.index:
        data["name"] = df.at['name', 'Value']
    elif 'Name' in df.index:
        data["name"] = df.at['Name', 'Value']
    else:
        data["name"] = 'Grid'

    if 'Comments' in df.index:
        data["Comments"] = df.at['Comments', 'Value']
    else:
        data["Comments"] = ''

    if 'ModelVersion' in df.index:
        data["ModelVersion"] = df.at['ModelVersion', 'Value']
    else:
        data["ModelVersion"] = 1

    if 'UserName' in df.index:
        data["UserName"] = df.at['UserName', 'Value']
    else:
        pass

    return data


class CustomJSONizer(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.int32, np.int64)):  # Handle NumPy integers
            return int(obj)
        elif isinstance(obj, (np.float32, np.float64)):  # Handle NumPy floats
            return float(obj)
        elif isinstance(obj, np.bool_):  # Handle NumPy boolean
            return bool(obj)
        elif isinstance(obj, np.ndarray):  # Convert NumPy arrays to lists
            return obj.tolist()
        return super().default(obj)
